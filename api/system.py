"""系统管理路由：设置读写、图片管理、日志、备份、代理与健康监控。

阻塞 IO（磁盘/远端）统一经 run_in_threadpool 下放线程池。
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict

from api.health_page import render_health_dashboard
from api.support import require_admin, require_identity, resolve_image_base_url
from services.account_service import account_service
from services.backup_service import BackupError, backup_service
from services.config import config
from services.image_service import (
    compress_images,
    delete_images,
    delete_to_target,
    download_images_zip,
    get_image_download_response,
    get_image_response,
    get_thumbnail_response,
    list_images,
    storage_stats,
)
from services.errors import ImageStorageError
from services.image_storage_service import image_storage_service
from services.image_tags_service import delete_tag, get_all_tags, set_tags
from services.log_service import log_service
from services.model_service import model_catalog_service
from services.proxy_service import proxy_settings, test_clearance, test_proxy
from utils.log import logger


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProxyTestRequest(BaseModel):
    url: str = ""


class ClearanceTestRequest(BaseModel):
    target_url: str = "https://chatgpt.com"


class ImageDeleteRequest(BaseModel):
    paths: list[str] = []
    start_date: str = ""
    end_date: str = ""
    all_matching: bool = False

class ImageDownloadRequest(BaseModel):
    paths: list[str]

class ImageTagsRequest(BaseModel):
    path: str
    tags: list[str]

class LogDeleteRequest(BaseModel):
    ids: list[str] = []
class BackupDeleteRequest(BaseModel):
    key: str = ""


def create_router(app_version: str) -> APIRouter:
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

    @router.get("/api/images")
    async def get_images(request: Request, start_date: str = "", end_date: str = "", authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return await run_in_threadpool(
            list_images,
            resolve_image_base_url(request),
            start_date.strip(),
            end_date.strip(),
        )

    @router.get("/images/{image_path:path}", include_in_schema=False)
    async def get_image(image_path: str):
        return await run_in_threadpool(get_image_response, image_path)

    @router.get("/image-thumbnails/{image_path:path}", include_in_schema=False)
    async def get_image_thumbnail(image_path: str):
        return await run_in_threadpool(get_thumbnail_response, image_path)

    @router.post("/api/images/delete")
    async def delete_images_endpoint(body: ImageDeleteRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return await run_in_threadpool(
            delete_images,
            body.paths,
            start_date=body.start_date.strip(),
            end_date=body.end_date.strip(),
            all_matching=body.all_matching,
        )

    @router.post("/api/images/download")
    async def download_images_endpoint(body: ImageDownloadRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        buf = await run_in_threadpool(download_images_zip, body.paths)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="images.zip"'},
        )

    @router.get("/api/images/download/{image_path:path}")
    async def download_single_image_endpoint(image_path: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return await run_in_threadpool(get_image_download_response, image_path)

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

    @router.get("/api/storage/info")
    async def get_storage_info(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        storage = config.get_storage_backend()
        return {
            "backend": storage.get_backend_info(),
            "health": storage.health_check(),
        }

    @router.post("/api/backup/test")
    async def test_backup_connection(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"result": await run_in_threadpool(backup_service.test_connection)}
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

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

    @router.get("/api/backups")
    async def get_backups(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {
                "items": await run_in_threadpool(backup_service.list_backups),
                "state": backup_service.get_status(),
                "settings": backup_service.get_settings(),
            }
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.post("/api/backups/run")
    async def run_backup_endpoint(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"result": await run_in_threadpool(backup_service.run_backup)}
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.post("/api/backups/delete")
    async def delete_backup_endpoint(body: BackupDeleteRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            await run_in_threadpool(backup_service.delete_backup, body.key)
            return {"ok": True}
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.get("/api/backups/detail")
    async def get_backup_detail(key: str = "", authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            return {"item": await run_in_threadpool(backup_service.get_backup_detail, key)}
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.get("/api/backups/download")
    async def download_backup_endpoint(key: str = "", authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            item = await run_in_threadpool(backup_service.download_backup, key)
        except BackupError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        filename = str(item.get("name") or "backup.bin")
        quoted = quote(filename)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
            "Content-Length": str(int(item.get("size") or 0)),
        }
        return Response(
            content=bytes(item.get("payload") or b""),
            media_type=str(item.get("content_type") or "application/octet-stream"),
            headers=headers,
        )


    @router.get("/api/images/tags")
    async def list_image_tags(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"tags": get_all_tags()}

    @router.post("/api/images/tags")
    async def update_image_tags(body: ImageTagsRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        rel = body.path.strip().lstrip("/")
        if not rel:
            raise HTTPException(status_code=400, detail={"error": "path is required"})
        tags = set_tags(rel, body.tags)
        return {"ok": True, "tags": tags}

    @router.delete("/api/images/tags/{tag}")
    async def delete_image_tag(tag: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        count = delete_tag(tag)
        return {"ok": True, "removed_from": count}

    @router.get("/api/images/storage")
    async def get_image_storage(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return storage_stats()

    @router.post("/api/images/storage/compress")
    async def compress_all_images(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return await run_in_threadpool(compress_images)

    @router.post("/api/images/storage/cleanup-to-target")
    async def cleanup_to_target(
        target_free_mb: int = 500,
        dry_run: bool = False,
        authorization: str | None = Header(default=None),
    ):
        require_admin(authorization)
        return await run_in_threadpool(delete_to_target, target_free_mb, dry_run)

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
