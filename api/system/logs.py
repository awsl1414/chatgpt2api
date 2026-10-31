"""日志路由：按类型与时间区间查询日志、按 id 删除日志。"""
from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api.support import require_admin
from services.log_service import log_service


class LogDeleteRequest(BaseModel):
    ids: list[str] = []


def build_router() -> APIRouter:
    """构建日志子路由（挂载在 /api/logs）。"""
    router = APIRouter()

    @router.get("/api/logs")
    async def get_logs(type: str = "", start_date: str = "", end_date: str = "", authorization: str | None = Header(default=None)):
        require_admin(authorization)
        items = await run_in_threadpool(
            log_service.list,
            type=type.strip(),
            start_date=start_date.strip(),
            end_date=end_date.strip(),
        )
        return {"items": items}

    @router.post("/api/logs/delete")
    async def delete_logs(body: LogDeleteRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return await run_in_threadpool(log_service.delete, body.ids)

    return router
