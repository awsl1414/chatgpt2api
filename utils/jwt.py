"""JWT payload 解码与 token 过期时间工具。

从 account_service 下沉的纯函数（审计 B-高2/B-高3）：openai_backend_api 需要
解析 access token 的 JWT claims，token 刷新需要判断过期时间，但都不应依赖
账号池模块。
"""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone


def decode_jwt_payload(token: str) -> dict:
    """解码 JWT 的 payload 段（不校验签名），失败时返回空 dict。"""
    try:
        payload = str(token or "").split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def jwt_exp(token: str) -> int:
    """取 JWT 的 exp claim；缺失或非法时返回 0。"""
    try:
        return int(decode_jwt_payload(token).get("exp") or 0)
    except (TypeError, ValueError):
        return 0


def token_expires_in(access_token: str) -> int | None:
    """access token 距过期的秒数；无法解析 exp 时返回 None。"""
    exp = jwt_exp(access_token)
    if exp <= 0:
        return None
    return exp - int(time.time())


def token_needs_refresh(access_token: str, *, skew_seconds: int, force: bool = False) -> bool:
    """access token 是否需要刷新：剩余有效期不足 ``skew_seconds`` 秒。"""
    if force:
        return True
    remaining = token_expires_in(access_token)
    return remaining is not None and remaining <= skew_seconds


def token_issued_at(access_token: str) -> datetime | None:
    """取 JWT 的 iat claim 并转为 UTC datetime；缺失或非法时返回 None。"""
    try:
        iat = int(decode_jwt_payload(access_token).get("iat") or 0)
    except (TypeError, ValueError):
        return None
    if iat <= 0:
        return None
    return datetime.fromtimestamp(iat, tz=timezone.utc)
