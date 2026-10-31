"""账号服务 facade（审计 B-高3：account_service 上帝类拆分的组装层）。

实现已拆分至 ``services/account/`` 包：

- ``account/pool.py``：号池（CRUD、持久化、token 别名、图片槽位并发、统计）
- ``account/token_refresh.py``：access_token 刷新与 refresh_token keepalive
- ``account/password_login.py``：无头密码登录与重新登录编排
- ``account/progress.py``：泛型进度追踪器（refresh / relogin 两套实例配置）
- ``account/models.py``：账号 Pydantic 模型、归一化与判定函数

本模块只负责组装与委托，对外调用面（方法名、签名、返回形态，含测试依赖的
私有辅助方法）与拆分前完全一致；既有依赖方（api/、openai_backend_api、
model_service、cpa_service 等 10+ 模块）的 import 路径不变。
"""
from __future__ import annotations

from threading import Event, Thread
from typing import Any

from services.account.models import (
    ModelRouteProvider,
    account_matches_any_plan_type,
    account_matches_plan_type,
    account_matches_source_type,
    is_image_account_available,
    normalize_account_type,
    normalize_source_type,
    search_account_type,
)
from services.account.password_login import PasswordLoginService
from services.account.pool import AccountPool
from services.account.progress import ProgressTracker
from services.account.token_refresh import TokenRefreshService
from services.config import config
from services.remote_info import fetch_remote_info as _fetch_remote_info
from services.storage.base import StorageBackend
from utils.helper import anonymize_token
from utils.jwt import token_expires_in
from utils.log import logger


def _build_refresh_initial(total: int) -> dict:
    """刷新进度的初始状态（形态与拆分前一致）。"""
    return {
        "total": total,
        "processed": 0,
        "done": False,
        "error": None,
        "status_counts": {"正常": 0, "限流": 0, "异常": 0, "禁用": 0},
        "total_quota": 0,
    }


def _apply_refresh_update(progress: dict, payload: tuple[str, int]) -> None:
    """刷新单条进度：累加状态计数与总额度。payload 为 (status, quota)。

    额度只累计「正常」状态账号，与 AccountPool.get_stats 的 total_quota
    口径一致（审查 R3-L8），避免刷新进行中的展示值高于完成后的最终值。
    """
    status, quota = payload
    progress["status_counts"][status] = progress["status_counts"].get(status, 0) + 1
    if status == "正常":
        progress["total_quota"] += quota


def _build_relogin_initial(total: int) -> dict:
    """重新登录进度的初始状态（形态与拆分前一致）。"""
    return {
        "total": total,
        "processed": 0,
        "done": False,
        "error": None,
        "results": [],
    }


def _apply_relogin_update(progress: dict, payload: tuple[str, str, str | None]) -> None:
    """重登单条进度：追加单账号结果。payload 为 (token, status, error)。"""
    token, status, error = payload
    progress["results"].append({
        "token": anonymize_token(token),
        "status": status,
        "error": error,
    })


class AccountService:
    """账号池服务 facade：组装号池与刷新/重登/进度子服务并委托调用。"""

    def __init__(self, storage_backend: StorageBackend, model_routes: ModelRouteProvider | None = None):
        # 号池（存储与并发底层）
        self._pool = AccountPool(storage_backend)
        # 子服务
        self._refresh_progress = ProgressTracker(
            build_initial=_build_refresh_initial,
            apply_update=_apply_refresh_update,
        )
        self._relogin_progress = ProgressTracker(
            build_initial=_build_relogin_initial,
            apply_update=_apply_relogin_update,
            auto_complete=True,
        )
        self._refresher = TokenRefreshService(self._pool)
        self._login = PasswordLoginService(self._pool, self._relogin_progress)
        # 组装：回调注入（依赖方向见 account/__init__.py 说明）。
        # 回调用晚绑定闭包包装——调用时才解析 self 上的方法属性，保持与拆分前
        # 单类实现相同的实例属性查找语义（测试可对 service.fetch_remote_info /
        # service.refresh_access_token 打实例补丁）。
        self._pool.refresh_callback = lambda access_token, event="": self.refresh_access_token(access_token, event=event)
        self._pool.verify_callback = self._late_bound_verify
        self._refresher.verify_callback = self._late_bound_verify
        self._refresher.start_relogin = self._login.re_login_thread
        self._refresher.refresh_progress = self._refresh_progress
        self._pool.model_routes = model_routes
        # 兼容属性：既有代码可访问 .storage
        self.storage = self._pool.storage

    @property
    def model_routes(self) -> ModelRouteProvider | None:
        """模型路由提供方（model_service 组装时回填）。"""
        return self._pool.model_routes

    @model_routes.setter
    def model_routes(self, value: ModelRouteProvider | None) -> None:
        self._pool.model_routes = value

    def _late_bound_verify(self, access_token: str, event: str = "fetch_remote_info", *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        """晚绑定的远端校验入口：调用时解析 self.fetch_remote_info。

        参数按调用点原样透传（生图取 token 传 2 参、批量刷新传 3 参），
        保证对 fetch_remote_info 的实例补丁与拆分前签名兼容。
        """
        return self.fetch_remote_info(access_token, event, *args, **kwargs)

    # ---- token 解析与查询 ----

    def resolve_access_token(self, access_token: str) -> str:
        return self._pool.resolve_access_token(access_token)

    def get_account(self, access_token: str) -> dict | None:
        return self._pool.get_account(access_token)

    def list_accounts(self) -> list[dict]:
        return self._pool.list_accounts()

    def list_tokens(self) -> list[str]:
        return self._pool.list_tokens()

    def list_limited_tokens(self) -> list[str]:
        return self._pool.list_limited_tokens()

    def list_normal_tokens(self) -> list[str]:
        return self._pool.list_normal_tokens()

    # ---- token 刷新与 keepalive ----

    def refresh_access_token(self, access_token: str, *, force: bool = False, event: str = "refresh_access_token") -> str:
        return self._refresher.refresh_access_token(access_token, force=force, event=event)

    def list_expiring_access_tokens(self) -> list[str]:
        return self._refresher.list_expiring_access_tokens()

    def list_refresh_token_keepalive_tokens(self) -> list[str]:
        return self._refresher.list_refresh_token_keepalive_tokens()

    def keepalive_refresh_tokens(self, access_tokens: list[str]) -> dict[str, Any]:
        return self._refresher.keepalive_refresh_tokens(access_tokens)

    # ---- token 获取（文本 / 生图） ----

    def get_text_access_token(self, excluded_tokens: set[str] | None = None, model: str = "auto") -> str:
        return self._pool.get_text_access_token(excluded_tokens, model)

    def get_available_access_token(
        self,
        plan_type: str | None = None,
        source_type: str | None = None,
        plan_types: set[str] | tuple[str, ...] | None = None,
    ) -> str:
        return self._pool.get_available_access_token(plan_type, source_type, plan_types)

    def release_image_slot(self, access_token: str) -> None:
        self._pool.release_image_slot(access_token)

    def mark_text_used(self, access_token: str) -> None:
        self._pool.mark_text_used(access_token)

    def mark_image_result(self, access_token: str, success: bool) -> dict | None:
        return self._pool.mark_image_result(access_token, success)

    # ---- 账号 CRUD ----

    def add_account_items(self, items: list[dict]) -> dict:
        return self._pool.add_account_items(items)

    def add_accounts(self, tokens: list[str], source_type: str = "web") -> dict:
        return self._pool.add_accounts(tokens, source_type)

    def delete_accounts(self, tokens: list[str]) -> dict:
        return self._pool.delete_accounts(tokens)

    def update_account(self, access_token: str, updates: dict, quiet: bool = False) -> dict | None:
        return self._pool.update_account(access_token, updates, quiet=quiet)

    def remove_invalid_token(self, access_token: str, event: str, quiet: bool = False) -> bool:
        return self._pool.remove_invalid_token(access_token, event, quiet=quiet)

    # ---- 远端信息校验（编排已上移 remote_info，保留入口维持调用方与测试注入） ----

    def fetch_remote_info(
        self,
        access_token: str,
        event: str = "fetch_remote_info",
        defer_invalid_removal: bool = True,
    ) -> dict[str, Any] | None:
        """委托 services.remote_info.fetch_remote_info。"""
        return _fetch_remote_info(
            self,
            access_token,
            event=event,
            defer_invalid_removal=defer_invalid_removal,
        )

    # ---- 批量刷新与重新登录 ----

    def refresh_accounts(
        self,
        access_tokens: list[str],
        progress_id: str | None = None,
        defer_invalid_removal: bool = True,
    ) -> dict[str, Any]:
        return self._refresher.refresh_accounts(
            access_tokens,
            progress_id,
            defer_invalid_removal=defer_invalid_removal,
        )

    def re_login_accounts(self, access_tokens: list[str], progress_id: str | None = None) -> dict[str, Any]:
        return self._login.re_login_accounts(access_tokens, progress_id)

    # ---- 刷新进度追踪 ----

    def init_refresh_progress(self, progress_id: str, total: int) -> None:
        """初始化刷新进度记录。"""
        self._refresh_progress.start(progress_id, total)

    def update_refresh_progress(self, progress_id: str, token: str) -> None:
        """刷新单个账号后，更新进度计数。"""
        self._refresher.update_refresh_progress(progress_id, token)

    def finish_refresh_progress(self, progress_id: str, result: dict | None = None, error: str | None = None) -> None:
        """标记刷新完成。"""
        self._refresh_progress.finish(progress_id, result, error)

    def get_refresh_progress(self, progress_id: str) -> dict | None:
        """查询刷新进度。"""
        return self._refresh_progress.get(progress_id)

    def clean_refresh_progress(self, progress_id: str) -> None:
        """清理过期进度记录。"""
        self._refresh_progress.clean(progress_id)

    # ---- 重新登录进度追踪 ----

    def init_relogin_progress(self, progress_id: str, total: int) -> None:
        """初始化重新登录进度记录。"""
        self._relogin_progress.start(progress_id, total)

    def update_relogin_progress(self, progress_id: str, token: str, status: str, error: str | None = None) -> None:
        """更新单个重新登录进度。"""
        self._relogin_progress.update(progress_id, (token, status, error))

    def finish_relogin_progress(self, progress_id: str, result: dict | None = None, error: str | None = None) -> None:
        """标记重新登录完成。"""
        self._relogin_progress.finish(progress_id, result, error)

    def get_relogin_progress(self, progress_id: str) -> dict | None:
        """查询重新登录进度。"""
        return self._relogin_progress.get(progress_id)

    def clean_relogin_progress(self, progress_id: str) -> None:
        """清理过期进度记录。"""
        self._relogin_progress.clean(progress_id)

    # ---- 导出与统计 ----

    def build_export_items(self, access_tokens: list[str] | None = None) -> list[dict[str, str]]:
        return self._pool.build_export_items(access_tokens)

    def build_export_zip(self, access_tokens: list[str] | None = None) -> tuple[bytes, str]:
        """打包可导出账号为 zip（见 AccountPool.build_export_zip）。"""
        return self._pool.build_export_zip(access_tokens)

    def get_stats(self) -> dict:
        return self._pool.get_stats()

    def account_health(self) -> dict:
        return self._pool.account_health()

    # ---- 兼容委托：既有依赖方/测试直接引用的私有辅助 ----

    @staticmethod
    def _is_image_account_available(account: dict) -> bool:
        return is_image_account_available(account)

    @staticmethod
    def _normalize_account_type(value: object) -> str | None:
        return normalize_account_type(value)

    @staticmethod
    def _normalize_source_type(value: object) -> str:
        return normalize_source_type(value)

    @staticmethod
    def _search_account_type(payload: object) -> str | None:
        return search_account_type(payload)

    @classmethod
    def _account_matches_plan_type(cls, account: dict, plan_type: str | None = None) -> bool:
        return account_matches_plan_type(account, plan_type)

    @classmethod
    def _account_matches_source_type(cls, account: dict, source_type: str | None = None) -> bool:
        return account_matches_source_type(account, source_type)

    @classmethod
    def _account_matches_any_plan_type(cls, account: dict, plan_types: set[str] | tuple[str, ...] | None = None) -> bool:
        return account_matches_any_plan_type(account, plan_types)

    def _record_invalid_token_seen(
        self,
        access_token: str,
        event: str,
        error: str,
        defer_invalid_removal: bool = True,
    ) -> bool:
        return self._pool.record_invalid_token_seen(access_token, event, error, defer_invalid_removal)

    def _record_refresh_success(self, access_token: str) -> None:
        self._pool.record_refresh_success(access_token)

    @classmethod
    def _token_expires_in(cls, access_token: str) -> int | None:
        return token_expires_in(access_token)


account_service = AccountService(config.get_storage_backend())


def start_limited_account_watcher(stop_event: Event) -> Thread:
    """启动限流账号巡检后台线程，按配置间隔自动刷新与 keepalive。

    巡检范围：限流/正常/临期 access_token 合并去重后批量刷新；keepalive
    刷新 token 排除临期集合避免重复刷新。巡检异常只记日志，不中断循环。
    返回守护线程引用，由调用方（应用 lifespan）管理停止事件。

    调度编排属 service 层职责（审计 B-中2），与 image_service 的
    start_image_cleanup_scheduler 同一模式。
    """
    interval_seconds = config.refresh_account_interval_minute * 60

    def worker() -> None:
        while not stop_event.is_set():
            try:
                limited_tokens = account_service.list_limited_tokens()
                normal_tokens = account_service.list_normal_tokens()
                expiring_tokens = account_service.list_expiring_access_tokens()
                keepalive_tokens = account_service.list_refresh_token_keepalive_tokens()
                tokens = list(dict.fromkeys([*limited_tokens, *normal_tokens, *expiring_tokens]))
                expiring_token_set = set(expiring_tokens)
                keepalive_tokens = [token for token in keepalive_tokens if token not in expiring_token_set]
                if tokens:
                    logger.info({
                        "event": "account_watcher_check",
                        "limited": len(limited_tokens),
                        "normal": len(normal_tokens),
                        "expiring_access": len(expiring_tokens),
                    })
                    account_service.refresh_accounts(tokens)
                if keepalive_tokens:
                    logger.info({"event": "account_watcher_keepalive", "count": len(keepalive_tokens)})
                    result = account_service.keepalive_refresh_tokens(keepalive_tokens)
                    if result.get("errors"):
                        logger.warning({"event": "account_watcher_keepalive_errors", "errors": result["errors"]})
            except Exception as exc:
                logger.error({"event": "account_watcher_failed", "error": str(exc)})
            stop_event.wait(interval_seconds)

    thread = Thread(target=worker, name="account-watcher", daemon=True)
    thread.start()
    return thread
