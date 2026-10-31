"""应用组装入口：FastAPI 实例、中间件栈、路由注册与生命周期管理。

中间件顺序约定（外→内）：CatchAllErrors → CORS → 路由；存储注入与后台
watcher（账号巡检/图片清理/备份调度）在此组装，protocol 层不直接依赖存储。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from threading import Event
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api import accounts, ai, image_tasks, system
from api.errors import install_exception_handlers
from api.support import resolve_web_asset
from services.account_service import start_limited_account_watcher
from services.backup_service import backup_service
from services.config import config
from services.image_service import start_image_cleanup_scheduler
from services.image_storage_service import image_storage_service
from services.protocol.image_stream import set_image_saver
from utils.log import logger


def create_app() -> FastAPI:
    app_version = config.app_version

    class CatchAllErrorsMiddleware:
        """兜底未捕获异常，统一返回 500 JSON 响应。

        注册在 CORSMiddleware 之后（位于其外侧）：CORSMiddleware 对内侧
        抛出的异常不做任何包装（异常直接绕过其 send 包装器），未捕获异常
        若不在这一层拦截，会一路穿透到 Starlette 最外层 ServerErrorMiddleware，
        返回的 500 缺失 CORS 头，浏览器端表现为 CORS 错误而掩盖真实错误
        （安全审查第 4 轮实测确认）。因此本中间件自行补与 CORS 配置一致的
        Access-Control-Allow-Origin 头（若调整 CORS 配置需同步此处）。
        堆栈经 logger 落日志，不回传客户端。
        """

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
            if scope["type"] != "http":
                await self._inner(scope, receive, send)
                return
            response_started = False

            async def send_wrapper(message: dict[str, Any]) -> None:
                nonlocal response_started
                if message["type"] == "http.response.start":
                    response_started = True
                await send(message)

            try:
                await self._inner(scope, receive, send_wrapper)
            except Exception:
                logger.exception({"event": "unhandled_exception", "path": scope.get("path", "")})
                if response_started:
                    # 响应已开始输出（流式），无法再补发错误响应，只能中断连接
                    return
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal Server Error"},
                    headers={"Access-Control-Allow-Origin": "*"},
                )
                await response(scope, receive, send)
    # 存储职责剥离（审计 B-中5）：protocol 层不直接依赖存储服务，
    # 图片落盘/上传回调由应用组装入口在此注入
    set_image_saver(lambda data, base_url: image_storage_service.save(data, base_url).url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop_event = Event()
        thread = start_limited_account_watcher(stop_event)
        cleanup_thread = start_image_cleanup_scheduler(stop_event)
        backup_service.start()
        config.cleanup_old_images()
        try:
            yield
        finally:
            stop_event.set()
            # 关停时给后台线程 1 秒让位退出，超时则随进程直接回收
            thread.join(timeout=1)
            cleanup_thread.join(timeout=1)
            backup_service.stop()

    app = FastAPI(title="chatgpt2api", version=app_version, lifespan=lifespan)
    install_exception_handlers(app)
    # 注册顺序即包裹顺序（后注册者更靠外）：兜底中间件最后注册，位于 CORS 外侧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CatchAllErrorsMiddleware)
    app.include_router(ai.create_router())
    app.include_router(accounts.create_router())
    app.include_router(image_tasks.create_router())
    app.include_router(system.create_router(app_version))

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_web(full_path: str):
        asset = resolve_web_asset(full_path)
        if asset is not None:
            return FileResponse(asset)
        if full_path.strip("/").startswith("_next/"):
            raise HTTPException(status_code=404, detail="Not Found")
        fallback = resolve_web_asset("")
        if fallback is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(fallback)

    return app
