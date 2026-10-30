"""账号数据模型与判定函数（审计 B-高3 / B-中1）。

职责：
- ``Account``：账号的 Pydantic 模型，是账号字段清单与归一化规则的唯一权威定义，
  替代原先散落在 ``AccountService._normalize_account`` 中的裸 dict 手工归一化。
- ``parse_account``：等价于原 ``_normalize_account``——输入任意 dict（含
  ``accessToken`` 别名、codex 导出格式），产出归一化后的存储 dict；不合法时返回 None。
- 账号类型/来源的匹配与判定函数：供号池、路由与导出逻辑共用。

持久化兼容：``Account`` 配置 ``extra="allow"``，未声明的键原样保留；
``parse_account`` 的输出与原实现的归一化 dict 逐字段等价，``data/accounts.json``
的读写形态不变。号池内部继续以归一化 dict 存储账号（而非模型实例），保证
持久化与既有调用面字节级兼容；所有写入路径都经由本模块校验。

已知等价性边界（模糊测试 3000 组验证）：正常数据与单字段非法数据的行为与
原实现完全一致；仅当多个字段同时是垃圾值时，抛出的异常类型可能是
``ValueError`` 或 ``TypeError``（原实现按固定字段顺序、pydantic 按校验器
聚合顺序），调用方均不按类型区分这两种异常。

包内协议（``AccountPoolProtocol`` / ``ModelRouteProvider``）也集中在此，
使 token_refresh / password_login 等模块只依赖协议而不反向 import 号池。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


def now_str() -> str:
    """当前 UTC 时间的标准账号时间戳格式（原 ``AccountService._now``）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_time(value: object) -> datetime | None:
    """解析账号上的时间字段，兼容 ISO 格式与 ``%Y-%m-%d %H:%M:%S``。

    无时区信息时按 UTC 处理；无法解析时返回 None。
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def timestamp_to_iso(value: object) -> str:
    """把 Unix 时间戳转成 UTC+8 的 ISO 字符串，非法输入返回空串（导出文件用）。"""
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return ""
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz).isoformat()


class Account(BaseModel):
    """账号的 Pydantic 模型：字段清单与归一化规则的唯一权威定义。

    归一化语义逐字段复刻原 ``AccountService._normalize_account``：

    - 强转字段（quota/success/fail/invalid_count/proxy/source_type）保留原
      ``int()``/``str()`` 的宽松强转行为（含对非数值输入抛 ``ValueError``）。
    - 透传字段（type/status/各时间与错误字段）保留 ``x or 默认值`` 语义，
      不做 str 强转，因此注解为 ``Any``。
    - ``extra="allow"``：未声明的键（password、refresh_token 等扩展字段）
      原样保留，``model_dump()`` 会一并输出，持久化形态不变。
    """

    model_config = ConfigDict(extra="allow")

    # 原实现不对 access_token 做 str 强转（仅要求真值），故注解 Any
    access_token: Any
    type: Any = "free"
    status: Any = "正常"
    quota: int = 0
    email: Any = None
    user_id: Any = None
    proxy: str = ""
    source_type: str = "web"
    limits_progress: list[Any] = Field(default_factory=list)
    default_model_slug: Any = None
    restore_at: Any = None
    success: int = 0
    fail: int = 0
    invalid_count: int = 0
    last_used_at: Any = None
    last_invalid_at: Any = None
    last_refresh_error: Any = None
    last_refresh_error_at: Any = None
    last_token_refresh_at: Any = None
    last_token_refresh_error: Any = None
    last_token_refresh_error_at: Any = None
    created_at: Any = Field(default_factory=now_str)

    @field_validator("type", mode="before")
    @classmethod
    def _type_or_default(cls, value: Any) -> Any:
        return value or "free"

    @field_validator("status", mode="before")
    @classmethod
    def _status_or_default(cls, value: Any) -> Any:
        return value or "正常"

    @field_validator("quota", mode="before")
    @classmethod
    def _coerce_quota(cls, value: Any) -> int:
        # 原语义：None 视为 0，其余走 int()（非法输入抛 ValueError）
        return max(0, int(value if value is not None else 0))

    @field_validator("email", "user_id", "default_model_slug", "restore_at",
                     "last_invalid_at", "last_refresh_error", "last_refresh_error_at",
                     "last_token_refresh_at", "last_token_refresh_error",
                     "last_token_refresh_error_at",
                     mode="before")
    @classmethod
    def _truthy_or_none(cls, value: Any) -> Any:
        return value or None

    @field_validator("proxy", mode="before")
    @classmethod
    def _coerce_proxy(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("source_type", mode="before")
    @classmethod
    def _coerce_source_type(cls, value: Any) -> str:
        return normalize_source_type(value)

    @field_validator("limits_progress", mode="before")
    @classmethod
    def _coerce_limits_progress(cls, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @field_validator("success", "fail", "invalid_count", mode="before")
    @classmethod
    def _coerce_counter(cls, value: Any) -> int:
        # 原语义：int(x or 0)
        return int(value or 0)

    @field_validator("created_at", mode="before")
    @classmethod
    def _coerce_created_at(cls, value: Any) -> Any:
        return value or now_str()


def parse_account(item: object) -> dict | None:
    """把任意输入归一化为账号存储 dict；等价于原 ``_normalize_account``。

    处理顺序与原实现一致：accessToken 别名合并 → codex 导出格式还原
    （``type=codex`` 移到 ``export_type``）→ 字段默认值与强转。输入不是
    dict 或缺少真值 access_token 时返回 None；字段强转失败抛 ``ValueError``。
    """
    if not isinstance(item, dict):
        return None
    prepared = dict(item)
    access_token = prepared.get("access_token") or prepared.get("accessToken") or ""
    if not access_token:
        return None
    prepared.pop("accessToken", None)
    prepared["access_token"] = access_token
    # codex 是导出格式，不是号池套餐类型
    if str(prepared.get("type") or "").strip().lower() == "codex":
        prepared["export_type"] = "codex"
        prepared.pop("type", None)
    # 导出类型为 codex 且未显式声明来源时，来源标记为 codex
    source_type = prepared.get("source_type")
    if not source_type and str(prepared.get("export_type") or "").strip().lower() == "codex":
        source_type = "codex"
    prepared["source_type"] = normalize_source_type(source_type)
    try:
        account = Account.model_validate(prepared)
    except ValidationError as exc:
        raise ValueError(f"账号字段不合法: {exc}") from exc
    return account.model_dump()


def normalize_source_type(value: object) -> str:
    """来源类型归一化：空值回退 ``web``，统一小写。"""
    return str(value or "web").strip().lower() or "web"


def normalize_account_type(value: object) -> str | None:
    """套餐类型归一化：支持 free/plus/pro/prolite/team/business/enterprise 别名。"""
    raw = str(value or "").strip()
    if not raw:
        return None
    key = raw.lower().replace("-", "_").replace(" ", "_")
    compact = key.replace("_", "")
    aliases = {
        "free": "free",
        "plus": "Plus",
        "pro": "Pro",
        "prolite": "ProLite",
        "team": "Team",
        "business": "Team",
        "enterprise": "Enterprise",
    }
    return aliases.get(compact) or aliases.get(key) or raw


def search_account_type(payload: object) -> str | None:
    """在任意嵌套 payload（dict/list）中递归搜索套餐类型字段。"""
    if isinstance(payload, dict):
        for key in ("plan_type", "account_plan", "account_type", "subscription_type", "type"):
            plan = normalize_account_type(payload.get(key))
            if plan:
                return plan
        for value in payload.values():
            plan = search_account_type(value)
            if plan:
                return plan
    elif isinstance(payload, list):
        for value in payload:
            plan = search_account_type(value)
            if plan:
                return plan
    return None


def account_matches_plan_type(account: dict, plan_type: str | None = None) -> bool:
    """账号套餐类型是否匹配指定套餐（未指定时视为匹配）。"""
    if not plan_type:
        return True
    normalized_plan = normalize_account_type(plan_type)
    normalized_account = normalize_account_type(account.get("type"))
    if not normalized_plan or not normalized_account:
        return False
    return normalized_plan.lower() == normalized_account.lower()


def account_matches_source_type(account: dict, source_type: str | None = None) -> bool:
    """账号来源（web/codex）是否匹配指定来源（未指定时视为匹配）。"""
    if not source_type:
        return True
    return normalize_source_type(account.get("source_type")) == normalize_source_type(source_type)


def account_matches_any_plan_type(account: dict, plan_types: set[str] | tuple[str, ...] | None = None) -> bool:
    """账号套餐类型是否命中任一候选套餐（未指定时视为匹配）。"""
    if not plan_types:
        return True
    normalized_account = normalize_account_type(account.get("type"))
    normalized_plans = {
        normalized
        for plan_type in plan_types
        if (normalized := normalize_account_type(plan_type))
    }
    return bool(normalized_account and normalized_account in normalized_plans)


def is_image_account_available(account: dict) -> bool:
    """账号是否可用于生图：状态非禁用/限流/异常且有剩余额度。"""
    if not isinstance(account, dict):
        return False
    if account.get("status") in {"禁用", "限流", "异常"}:
        return False
    return int(account.get("quota") or 0) > 0


def account_payload_token(item: dict) -> str:
    """从导入 payload 中取 access_token（兼容 ``accessToken`` 别名）。"""
    return str(item.get("access_token") or item.get("accessToken") or "").strip()


def prepare_account_payload(item: dict) -> dict | None:
    """把导入 payload 预处理为号池入库形态；缺 access_token 时返回 None。

    与 ``parse_account`` 的差异：此处服务「导入合并」场景，额外处理
    ``plan_type`` 回填 ``type``、codex 导出格式到来源标记的映射。
    """
    if not isinstance(item, dict):
        return None
    access_token = account_payload_token(item)
    if not access_token:
        return None
    payload = dict(item)
    payload.pop("accessToken", None)
    payload["access_token"] = access_token
    # CPA/Codex 导出文件里的 `type=codex` 是导出格式，不是号池套餐类型。
    if str(payload.get("type") or "").strip().lower() == "codex":
        payload["export_type"] = "codex"
        payload["source_type"] = "codex"
        payload.pop("type", None)
    if str(payload.get("export_type") or "").strip().lower() == "codex":
        payload["source_type"] = "codex"
    if payload.get("plan_type") and not payload.get("type"):
        payload["type"] = str(payload.get("plan_type") or "").strip()
    return payload


class AccountPoolProtocol(Protocol):
    """号池能力协议：token_refresh / password_login 依赖此协议而非号池实现。

    由 ``account/pool.AccountPool`` 实现，组装层（services/account_service.py）
    负责注入，保证包内模块不反向 import 号池。
    """

    def resolve_access_token(self, access_token: str) -> str: ...

    def get_account(self, access_token: str) -> dict | None: ...

    def get_account_snapshot(self, access_token: str) -> tuple[str, dict | None]: ...

    def snapshot(self) -> list[dict]: ...

    def list_accounts(self) -> list[dict]: ...

    def update_account(self, access_token: str, updates: dict, quiet: bool = False) -> dict | None: ...

    def remove_invalid_token(self, access_token: str, event: str, quiet: bool = False) -> bool: ...

    def apply_token_rotation(self, old_access_token: str, token_data: dict, event: str) -> str: ...

    def record_token_refresh_error(self, access_token: str, event: str, error: str) -> None: ...


class ModelRouteProvider(Protocol):
    """模型路由查询接口（由 model_catalog_service 实现，组装层注入）。"""

    def route_for_model(self, model: str) -> Any:
        ...
