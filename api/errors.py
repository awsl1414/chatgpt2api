from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.errors import DomainError
from services.protocol.error_response import anthropic_error_response, openai_error_response


def _is_openai_compatible_path(path: str) -> bool:
    return path == "/v1" or path.startswith("/v1/")


def _is_anthropic_messages_path(path: str) -> bool:
    return path == "/v1/messages"


def _compatible_error_response(
    request: Request,
    detail: object,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    if _is_anthropic_messages_path(request.url.path):
        return anthropic_error_response(detail, status_code, headers=headers)
    return openai_error_response(detail, status_code, headers=headers)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """领域异常统一映射：/v1/* 走 OpenAI/Anthropic 兼容格式，其余返回 {"detail": ...}。

        响应逻辑与 HTTPException 处理器保持一致，保证迁移前后错误响应字节级兼容。
        """
        if _is_openai_compatible_path(request.url.path):
            return _compatible_error_response(request, exc.detail, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": jsonable_encoder(exc.detail)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if _is_openai_compatible_path(request.url.path):
            return _compatible_error_response(request, exc.detail, exc.status_code, exc.headers)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": jsonable_encoder(exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if _is_openai_compatible_path(request.url.path):
            return _compatible_error_response(request, exc.errors(), 422)
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})
