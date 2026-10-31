"""图片文件路由：图片列表、原始文件与缩略图读取、删除与打包下载。

``/images/{path}`` 与 ``/image-thumbnails/{path}`` 是静态资源直出端点，
不参与 OpenAPI 文档；管理端接口一律要求 admin 身份。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.support import require_admin, resolve_image_base_url
from services.image_service import (
    delete_images,
    download_images_zip,
    get_image_download_response,
    get_image_response,
    get_thumbnail_response,
    list_images,
)


class ImageDeleteRequest(BaseModel):
    paths: list[str] = []
    start_date: str = ""
    end_date: str = ""
    all_matching: bool = False


class ImageDownloadRequest(BaseModel):
    paths: list[str]


def build_router() -> APIRouter:
    """构建图片文件子路由（挂载在 /api/images 与 /images、/image-thumbnails）。"""
    router = APIRouter()

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

    return router
