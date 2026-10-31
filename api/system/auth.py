"""身份与版本路由：登录态校验与版本查询。

``/auth/login`` 接受任意有效身份（admin 或普通 user），返回身份摘要与版本。
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from api.support import require_identity


def build_router(app_version: str) -> APIRouter:
    """构建身份/版本子路由（挂载在 /auth/login 与 /version）。"""
    router = APIRouter()

    @router.post("/auth/login")
    async def login(authorization: str | None = Header(default=None)):
        identity = require_identity(authorization)
        return {
            "ok": True,
            "version": app_version,
            "role": identity.get("role"),
            "subject_id": identity.get("id"),
            "name": identity.get("name"),
        }

    @router.get("/version")
    async def get_version():
        return {"version": app_version}

    return router
