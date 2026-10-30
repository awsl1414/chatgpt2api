"""账号远程信息校验编排（自 account_service 上移，审计 B-高2）。

调用上游 /backend-api/me 验证 token 有效性并回写账号池。该逻辑依赖
openai_backend_api，属于账号层之上的应用编排；account_service 仅保留
委托入口供既有调用方（含测试注入）使用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from services.errors import InvalidAccessTokenError
from services.openai_backend_api import OpenAIBackendAPI

if TYPE_CHECKING:
    from services.account_service import AccountService


def fetch_remote_info(
    accounts: AccountService,
    access_token: str,
    event: str = "fetch_remote_info",
    defer_invalid_removal: bool = True,
) -> dict[str, Any] | None:
    """校验 access token 的远端账号信息并更新账号池。

    参数：
    - `accounts`：账号池实例（依赖注入，避免本模块反向 import account 层）。
    - `access_token`：待校验的 token。
    - `event`：日志事件名。
    - `defer_invalid_removal`：失效 token 是否延迟移除。

    异常：
    - `InvalidAccessTokenError`：token 已失效且重试后仍失败。
    """
    if not access_token:
        raise ValueError("access_token is required")

    active_token = accounts.refresh_access_token(access_token, event=f"{event}:preflight") or access_token
    try:
        backend = OpenAIBackendAPI(active_token, account_reader=accounts)
        try:
            result = backend.get_user_info()
        finally:
            backend.close()
    except InvalidAccessTokenError as exc:
        refreshed_token = accounts.refresh_access_token(active_token, force=True, event=f"{event}:invalid_access_token")
        if refreshed_token and refreshed_token != active_token:
            try:
                backend = OpenAIBackendAPI(refreshed_token, account_reader=accounts)
                try:
                    result = backend.get_user_info()
                finally:
                    backend.close()
            except InvalidAccessTokenError as retry_exc:
                if accounts._record_invalid_token_seen(
                    refreshed_token,
                    event,
                    str(retry_exc),
                    defer_invalid_removal=defer_invalid_removal,
                ):
                    accounts.remove_invalid_token(refreshed_token, event)
                raise
            active_token = refreshed_token
        else:
            if accounts._record_invalid_token_seen(
                active_token,
                event,
                str(exc),
                defer_invalid_removal=defer_invalid_removal,
            ):
                accounts.remove_invalid_token(active_token, event)
            raise
    accounts._record_refresh_success(active_token)
    return accounts.update_account(active_token, result)
