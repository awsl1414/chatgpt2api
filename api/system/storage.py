"""存储后端信息与图片存储同步路由。

``/api/storage/info`` 返回当前存储后端信息与健康状态；
``/api/image-storage/*`` 面向 WebDAV 图片存储的连接测试与全量同步。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.support import require_admin
from services.config import config
from services.errors import ImageStorageError
from services.image_storage_service import image_storage_service


def build_info_router() -> APIRouter:
    """构建存储后端信息子路由（/api/storage/info）。

    该端点在拆分前位于备份连接测试之前，单独成路由以保持全局端点定义顺序。
    """
    router = APIRouter()

    @router.get("/api/storage/info")
    async def get_storage_info(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        storage = config.get_storage_backend()
        return {
            "backend": storage.get_backend_info(),
            "health": storage.health_check(),
        }

    return router


def build_router() -> APIRouter:
    """构建图片存储子路由（挂载在 /api/image-storage）。"""
    router = APIRouter()

    @router.post("/api/image-storage/test")
    async def test_image_storage_endpoint(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"result": await run_in_threadpool(image_storage_service.test_webdav)}

    @router.post("/api/image-storage/sync")
    async def sync_image_storage_endpoint(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"result": await run_in_threadpool(image_storage_service.sync_all)}
        except ImageStorageError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    return router
