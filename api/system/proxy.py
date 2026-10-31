"""代理路由：代理连通性测试、运行时代理配置读写、清障测试与上游模型目录。

``/api/upstream-models`` 归入本域：它服务于代理设置页的模型下拉，
拉取失败时降级为空列表，由前端回退为手填值。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api.system.settings import SettingsUpdateRequest
from api.support import require_admin
from services.config import config
from services.model_service import model_catalog_service
from services.proxy_service import proxy_settings, test_clearance, test_proxy
from utils.log import logger


class ProxyTestRequest(BaseModel):
    url: str = ""


class ClearanceTestRequest(BaseModel):
    target_url: str = "https://chatgpt.com"


def build_router() -> APIRouter:
    """构建代理子路由（挂载在 /api/proxy 与 /api/upstream-models）。"""
    router = APIRouter()

    @router.post("/api/proxy/test")
    async def test_proxy_endpoint(body: ProxyTestRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"result": await run_in_threadpool(test_proxy, (body.url or "").strip())}

    @router.get("/api/proxy/runtime")
    async def get_proxy_runtime_endpoint(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {
            "runtime": config.get_public_proxy_runtime_settings(),
            "status": proxy_settings.get_runtime_status(),
        }

    @router.post("/api/proxy/runtime")
    async def save_proxy_runtime_endpoint(body: SettingsUpdateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            config.update({"proxy_runtime": body.model_dump(mode="python")})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        return {
            "runtime": config.get_public_proxy_runtime_settings(),
            "status": proxy_settings.get_runtime_status(),
        }

    @router.get("/api/upstream-models")
    async def get_upstream_models(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            result = await run_in_threadpool(model_catalog_service.list_models)
        except Exception as exc:  # noqa: BLE001 - 目录拉取失败时降级为空列表，前端回退为手填值
            logger.warning({
                "event": "upstream_models_failed",
                "error_type": type(exc).__name__,
            })
            return {"models": []}
        data = result.get("data")
        models = [
            str(item.get("id") or "").strip()
            for item in (data or [])
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]
        return {"models": sorted(set(models))}

    @router.post("/api/proxy/clearance/test")
    async def test_proxy_clearance_endpoint(body: ClearanceTestRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"result": await run_in_threadpool(test_clearance, body.target_url)}

    return router
