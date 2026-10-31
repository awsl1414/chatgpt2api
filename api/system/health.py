"""健康检查路由：JSON 状态与 HTML 仪表盘。

健康判定口径：账号池中存在 active 账号即视为 healthy。
HTML 模板渲染收敛在 ``api/health_page``（审计 B-中2：路由层不内联大段模板）。
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from api.health_page import render_health_dashboard
from services.account_service import account_service
from services.config import config
from services.proxy_service import proxy_settings


def build_router(app_version: str) -> APIRouter:
    """构建健康检查子路由（挂载在 /health）。"""
    router = APIRouter()

    @router.get("/health", response_model=None)
    async def health_dashboard(format: str = Query(default="html")):
        stats = await run_in_threadpool(account_service.get_stats)
        storage = config.get_storage_backend()
        storage_health = await run_in_threadpool(storage.health_check)
        healthy = stats["active"] > 0

        stats_json = {
            "status": "ok" if healthy else "degraded",
            "healthy": healthy,
            "version": app_version,
            "storage": {"backend": storage.get_backend_info(), "health": storage_health},
            "proxy_runtime": proxy_settings.get_runtime_status(),
            "accounts": stats,
        }
        if format == "json":
            return stats_json
        # HTML 模板渲染收敛在 api/health_page（审计 B-中2：路由层不内联大段模板）
        return HTMLResponse(render_health_dashboard(stats, app_version, healthy))

    return router
