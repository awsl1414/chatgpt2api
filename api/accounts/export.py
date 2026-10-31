"""账号导出路由：把完整账号（含三件套 token）导出为 json 或 zip 下载。

zip 打包在 service 层完成；文件名时间戳以导出时刻为准。
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.accounts.common import download_timestamp, unique_tokens
from api.support import require_admin
from services.account_service import account_service


class AccountExportRequest(BaseModel):
    access_tokens: list[str] = Field(default_factory=list)
    format: Literal["json", "zip"] = "json"


def build_router() -> APIRouter:
    """构建账号导出子路由（挂载在 /api/accounts/export）。"""
    router = APIRouter()

    @router.post("/api/accounts/export")
    async def export_accounts(body: AccountExportRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        access_tokens = unique_tokens(body.access_tokens)
        items = account_service.build_export_items(access_tokens)
        if not items:
            raise HTTPException(
                status_code=400,
                detail={"error": "没有可导出的完整账号，需要同时有 access_token、refresh_token 和 id_token"},
            )

        timestamp = download_timestamp()
        if body.format == "zip":
            # zip 打包在 service 层完成（审计 B-中2），时间戳以导出时刻为准保持一致
            content, timestamp = account_service.build_export_zip(access_tokens)
            return Response(
                content,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="codex-accounts-{timestamp}.zip"'},
            )

        payload: dict[str, str] | list[dict[str, str]] = items[0] if len(items) == 1 else items
        return Response(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="codex-accounts-{timestamp}.json"'},
        )

    return router
