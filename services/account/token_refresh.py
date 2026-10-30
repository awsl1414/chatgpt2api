"""access_token 刷新与 refresh_token keepalive（审计 B-高3）。

职责：通过 OAuth refresh_token 换取新 access token（``_request_access_token_refresh``）、
按剩余有效期决定是否刷新（``refresh_access_token``）、refresh_token 周期性
keepalive（防 refresh token 长期不用被回收）、以及 ``refresh_accounts`` 批量
刷新编排（并发远端校验 + 进度上报 + 可选自动重登）。

依赖方向：通过 ``AccountPoolProtocol`` 读写号池（组装层注入），不 import pool；
远端校验与密码重登编排分别以 ``verify_callback`` / ``start_relogin`` 注入。
与 ``account/password_login`` 的关系：密码重登是刷新失败
（app_session_terminated）的兜底路径，由 ``start_relogin`` 回调衔接。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
from typing import Any, Callable

from curl_cffi import requests

from services.account.models import AccountPoolProtocol, parse_time
from services.config import config
from services.errors import is_tls_connection_error
from services.openai_oauth import platform_oauth_client_id, user_agent
from services.proxy_service import proxy_settings
from utils.helper import anonymize_token
from utils.jwt import token_needs_refresh, token_issued_at

# 批量刷新的远端校验回调：fetch_remote_info(token, event, defer_invalid_removal) -> dict | None
VerifyCallback = Callable[..., dict | None]
# 密码重登线程启动回调：(access_token, email, password, event, progress_id=None) -> None
StartReloginCallback = Callable[..., None]
# 进度上报回调（api/support 等外部进度查询沿用 facade 既有方法）
ProgressLogger = Callable[[str, str], None]


class TokenRefreshService:
    """access token 刷新与 refresh_token keepalive 服务。"""

    _ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 24 * 60 * 60
    _REFRESH_TOKEN_KEEPALIVE_SECONDS = 3 * 24 * 60 * 60
    _REFRESH_TOKEN_KEEPALIVE_ERROR_BACKOFF_SECONDS = 6 * 60 * 60
    _REFRESH_TOKEN_KEEPALIVE_BATCH_SIZE = 3
    _TOKEN_REFRESH_ERROR_BACKOFF_SECONDS = 5 * 60
    _OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"

    def __init__(self, pool: AccountPoolProtocol):
        self._pool = pool
        self._token_refresh_lock = Lock()
        # 由组装层注入：批量刷新的远端校验、密码重登线程启动、刷新进度追踪
        self.verify_callback: VerifyCallback | None = None
        self.start_relogin: StartReloginCallback | None = None
        self.refresh_progress: Any | None = None

    # ---- OAuth refresh ----

    def _request_access_token_refresh(self, refresh_token: str, account: dict | None = None) -> dict[str, str]:
        session = requests.Session(**proxy_settings.build_session_kwargs(account=account, impersonate="chrome110", verify=True))
        try:
            response = session.post(
                self._OAUTH_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": user_agent,
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": platform_oauth_client_id,
                },
                timeout=60,
            )
            data = response.json() if response.text else {}
            if response.status_code != 200 or not isinstance(data, dict) or not data.get("access_token"):
                detail = ""
                if isinstance(data, dict):
                    detail = str(data.get("error_description") or data.get("error") or data.get("message") or "")
                detail = detail or _safe_response_text(response)
                raise RuntimeError(f"oauth_refresh_http_{response.status_code}{': ' + detail if detail else ''}")
            return {
                "access_token": str(data.get("access_token") or "").strip(),
                "refresh_token": str(data.get("refresh_token") or refresh_token).strip(),
                "id_token": str(data.get("id_token") or "").strip(),
            }
        finally:
            session.close()

    def _recent_token_refresh_error(self, account: dict) -> bool:
        last_error_at = parse_time(account.get("last_token_refresh_error_at"))
        if last_error_at is None:
            return False
        return (datetime.now(timezone.utc) - last_error_at).total_seconds() < self._TOKEN_REFRESH_ERROR_BACKOFF_SECONDS

    def refresh_access_token(self, access_token: str, *, force: bool = False, event: str = "refresh_access_token") -> str:
        if not access_token:
            return ""
        with self._token_refresh_lock:
            resolved_token, account = self._pool.get_account_snapshot(access_token)
            if not account:
                return access_token
            active_token = str(account.get("access_token") or resolved_token or access_token)
            if not token_needs_refresh(active_token, skew_seconds=self._ACCESS_TOKEN_REFRESH_SKEW_SECONDS, force=force):
                return active_token
            refresh_token = str(account.get("refresh_token") or "").strip()
            if not refresh_token:
                return active_token
            if not force and self._recent_token_refresh_error(account):
                return active_token
            try:
                token_data = self._request_access_token_refresh(refresh_token, account)
            except Exception as exc:
                error_str = str(exc or "")
                self._pool.record_token_refresh_error(active_token, event, error_str)
                # 如果是 app_session_terminated 错误，尝试密码重新登录
                if "app_session_terminated" in error_str.lower():
                    # 获取账号信息（email, password）
                    email = str(account.get("email") or "").strip()
                    password = str(account.get("password") or "").strip()
                    if email and password and self.start_relogin is not None:
                        # 在后台线程执行密码重新登录
                        t = Thread(
                            target=self.start_relogin,
                            args=(active_token, email, password, event),
                            daemon=True,
                        )
                        t.start()
                return active_token
            return self._pool.apply_token_rotation(active_token, token_data, event)

    # ---- refresh_token keepalive ----

    def _recent_refresh_token_keepalive_error(self, account: dict, now: datetime) -> bool:
        last_error_at = parse_time(account.get("last_token_refresh_error_at"))
        if last_error_at is None:
            return False
        return (now - last_error_at).total_seconds() < self._REFRESH_TOKEN_KEEPALIVE_ERROR_BACKOFF_SECONDS

    def _refresh_token_keepalive_anchor(self, account: dict) -> datetime | None:
        return (
            parse_time(account.get("last_token_refresh_at"))
            or token_issued_at(str(account.get("access_token") or ""))
            or parse_time(account.get("created_at"))
        )

    def _refresh_token_keepalive_due_at(self, account: dict, now: datetime) -> datetime | None:
        if not str(account.get("refresh_token") or "").strip():
            return None
        if account.get("status") == "禁用":
            return None
        if self._recent_refresh_token_keepalive_error(account, now):
            return None
        anchor = self._refresh_token_keepalive_anchor(account)
        if anchor is None:
            return now
        due_at = anchor + timedelta(seconds=self._REFRESH_TOKEN_KEEPALIVE_SECONDS)
        return due_at if due_at <= now else None

    def list_expiring_access_tokens(self) -> list[str]:
        return [
            token
            for account in self._pool.snapshot()
            if str(account.get("refresh_token") or "").strip()
            and (token := str(account.get("access_token") or "").strip())
            and token_needs_refresh(token, skew_seconds=self._ACCESS_TOKEN_REFRESH_SKEW_SECONDS)
        ]

    def list_refresh_token_keepalive_tokens(self) -> list[str]:
        now = datetime.now(timezone.utc)
        due_items: list[tuple[datetime, str]] = []
        for account in self._pool.snapshot():
            due_at = self._refresh_token_keepalive_due_at(account, now)
            token = str(account.get("access_token") or "").strip()
            if due_at is not None and token:
                due_items.append((due_at, token))
        due_items.sort(key=lambda item: item[0])
        return [token for _, token in due_items[: self._REFRESH_TOKEN_KEEPALIVE_BATCH_SIZE]]

    def keepalive_refresh_tokens(self, access_tokens: list[str]) -> dict[str, Any]:
        access_tokens = list(dict.fromkeys(token for token in access_tokens if token))
        if not access_tokens:
            return {"refreshed": 0, "errors": [], "items": self._pool.list_accounts()}

        refreshed = 0
        errors = []
        for access_token in access_tokens:
            before = self._pool.resolve_access_token(access_token)
            after = self.refresh_access_token(before, force=True, event="refresh_token_keepalive")
            account = self._pool.get_account(after)
            if account and str(account.get("last_token_refresh_error") or "").strip():
                errors.append({
                    "token": anonymize_token(before),
                    "error": str(account.get("last_token_refresh_error") or "refresh token failed"),
                })
                continue
            if account:
                refreshed += 1

        return {
            "refreshed": refreshed,
            "errors": errors,
            "items": self._pool.list_accounts(),
            "relogined": 0,
        }

    # ---- 批量刷新编排 ----

    def update_refresh_progress(self, progress_id: str, token: str) -> None:
        """刷新单个账号后，按其最新状态/额度更新进度计数。"""
        account = self._pool.get_account(token)
        status = str(account.get("status") or "正常").strip() if account else "正常"
        quota = max(0, int(account.get("quota") or 0)) if account else 0
        if self.refresh_progress is not None:
            self.refresh_progress.update(progress_id, (status, quota))

    def refresh_accounts(
        self,
        access_tokens: list[str],
        progress_id: str | None = None,
        defer_invalid_removal: bool = True,
    ) -> dict[str, Any]:
        verify = self.verify_callback
        if verify is None:
            raise RuntimeError("TokenRefreshService.verify_callback 未注入（应由组装层设置）")
        access_tokens = list(dict.fromkeys(token for token in access_tokens if token))
        if not access_tokens:
            items = self._pool.list_accounts()
            result = {"refreshed": 0, "errors": [], "items": items, "relogined": 0}
            if progress_id and self.refresh_progress is not None:
                self.refresh_progress.finish(progress_id, result)
            return result

        refreshed = 0
        errors = []
        max_workers = min(10, len(access_tokens))

        if progress_id and self.refresh_progress is not None:
            self.refresh_progress.start(progress_id, len(access_tokens))

        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = {
                executor.submit(verify, token, "refresh_accounts", defer_invalid_removal): token
                for token in access_tokens
            }
            for future in as_completed(futures):
                token = futures[future]
                try:
                    account = future.result()
                except (KeyboardInterrupt, SystemExit):
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
                except Exception as exc:
                    error_str = str(exc)
                    # TLS/代理连接错误是网络问题，不计入账号失败
                    if not is_tls_connection_error(error_str):
                        errors.append({"token": anonymize_token(token), "error": error_str})
                else:
                    if account is not None:
                        refreshed += 1

                if progress_id:
                    self.update_refresh_progress(progress_id, token)
        except (KeyboardInterrupt, SystemExit):
            if progress_id and self.refresh_progress is not None:
                self.refresh_progress.finish(progress_id, error="cancelled")
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True, cancel_futures=True)

        # 自动重新登录异常账号（仅当配置开启时）
        relogined = 0
        if config.auto_relogin_after_refresh and self.start_relogin is not None:
            for token in access_tokens:
                account = self._pool.get_account(token)
                if not account:
                    continue
                status = str(account.get("status") or "").strip()
                if status != "异常":
                    continue
                email = str(account.get("email") or "").strip()
                password = str(account.get("password") or "").strip()
                if not email or not password:
                    continue
                t = Thread(
                    target=self.start_relogin,
                    args=(token, email, password, "auto_relogin_after_refresh"),
                    daemon=True,
                )
                t.start()
                relogined += 1

        result = {
            "refreshed": refreshed,
            "errors": errors,
            "items": self._pool.list_accounts(),
            "relogined": relogined,
        }

        if progress_id and self.refresh_progress is not None:
            self.refresh_progress.finish(progress_id, result)

        return result


def _safe_response_text(response: object, limit: int = 300) -> str:
    try:
        return str(getattr(response, "text", "") or "")[:limit]
    except Exception:
        return ""
