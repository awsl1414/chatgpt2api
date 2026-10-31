"""配置读写路由：管理端配置与第三方应用配置。

``POST /api/settings`` 接受任意顶层键，未知键由 config 层白名单校验后返回 400。
``SettingsUpdateRequest`` 同时被 proxy 子路由复用（运行时代理配置走同一宽松入参）。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from api.support import require_admin, require_identity
from services.config import config


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


def build_router() -> APIRouter:
    """构建配置子路由（挂载在 /api/settings 与 /api/third-party-apps）。"""
    router = APIRouter()

    @router.get("/api/settings")
    async def get_settings(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"config": config.get()}

    @router.get("/api/third-party-apps")
    async def get_third_party_apps(authorization: str | None = Header(default=None)):
        require_identity(authorization)
        return {"third_party_apps": config.get_third_party_apps_settings()}

    @router.post("/api/settings")
    async def save_settings(body: SettingsUpdateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"config": config.update(body.model_dump(mode="python"))}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    return router
