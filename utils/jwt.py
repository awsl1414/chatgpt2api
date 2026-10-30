"""JWT payload 解码工具。

从 account_service 下沉的纯函数（审计 B-高2）：openai_backend_api 需要
解析 access token 的 JWT claims，但不应依赖账号池模块。
"""
from __future__ import annotations

import base64
import json


def decode_jwt_payload(token: str) -> dict:
    """解码 JWT 的 payload 段（不校验签名），失败时返回空 dict。"""
    try:
        payload = str(token or "").split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
