"""统一领域异常体系。

service 层只抛本模块定义的领域异常，禁止直接抛 fastapi.HTTPException；
HTTP 状态码与 OpenAI 兼容错误格式由 api/errors.py 的全局处理器统一映射。
本模块属于最底层，不得 import 任何其他 services 子模块（避免循环依赖）。

同时集中承载原本分散在各处的领域异常与错误消息清洗函数：
- ImageGenerationError（原 protocol/conversation.py）
- InvalidAccessTokenError / ImageTaskError 族（原 openai_backend_api.py）
- ImageStorageError（原 image_storage_service.py）
- Sub2apiError（原 sub2api_service.py 零散 RuntimeError）
"""
from __future__ import annotations

from typing import Any


def _error_detail(message: str) -> dict[str, str]:
    """构造 OpenAI 兼容层沿用的 detail 形态（{"error": <消息>}）。"""
    return {"error": message}


class DomainError(Exception):
    """领域异常基类。

    Attributes:
        status_code: api 层映射时使用的默认 HTTP 状态码。
        detail: 响应体 detail 字段内容；缺省为异常消息字符串。
    """

    status_code: int = 500

    def __init__(self, message: str = "", detail: object | None = None) -> None:
        super().__init__(message)
        self.detail: object = detail if detail is not None else str(message)


class InvalidRequestError(DomainError):
    """请求参数不满足协议要求（OpenAI 兼容层 400）。"""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message, detail=_error_detail(message))


class NotFoundError(DomainError):
    """目标资源不存在（404）。"""

    status_code = 404


class ThumbnailCreationError(DomainError):
    """图片缩略图生成失败（422）。"""

    status_code = 422


# ---------------------------------------------------------------------------
# 内容审核（content_filter）
# ---------------------------------------------------------------------------


class ContentFilterError(DomainError):
    """内容审核相关异常基类，api 层据此记录调用失败日志。"""


class ContentRejectedError(ContentFilterError):
    """请求内容被审核拒绝（敏感词或 AI 审核未通过，400）。"""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message, detail=_error_detail(message))


class ReviewConfigError(ContentFilterError):
    """AI 审核配置不完整（400）。"""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message, detail=_error_detail(message))


class ReviewUnavailableError(ContentFilterError):
    """AI 审核服务不可用且未开启 fail_open（503）。"""

    status_code = 503

    def __init__(self, message: str) -> None:
        super().__init__(message, detail=_error_detail(message))


# ---------------------------------------------------------------------------
# 图片生成链路（openai_backend_api / protocol/conversation）
# ---------------------------------------------------------------------------


class InvalidAccessTokenError(DomainError):
    """上游 access token 已失效，需刷新或重新登录账号。"""

    status_code = 502


class ImageTaskError(DomainError):
    """图片生成异常基类，携带上游会话 ID 供调用方清理对话。"""

    status_code = 502

    def __init__(self, message: str = "", conversation_id: str = "") -> None:
        super().__init__(message)
        self.conversation_id = conversation_id


class ImagePollTimeoutError(ImageTaskError):
    """图片结果轮询超时。"""


class ImageContentPolicyError(ImageTaskError):
    """图片生成被上游内容审核拦截。"""


class ImageStreamHardTimeoutError(DomainError):
    """图片 SSE 流读取超过硬上限时抛出，用于快速中断被挂起的长连接。"""

    status_code = 502


class ImageGenerationError(DomainError):
    """图片生成失败，可直接序列化为 OpenAI 兼容错误响应。"""

    status_code = 502

    def __init__(
        self,
        message: str,
        status_code: int = 502,
        error_type: str = "server_error",
        code: str | None = "upstream_error",
        param: str | None = None,
        account_email: str = "",
        conversation_id: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.param = param
        self.account_email = account_email
        self.conversation_id = conversation_id

    def to_openai_error(self) -> dict[str, Any]:
        error_dict = {
            "error": {
                "message": public_image_error_message(str(self)),
                "type": self.error_type,
                "param": self.param,
                "code": self.code,
            }
        }
        if self.account_email:
            error_dict["error"]["account_email"] = self.account_email
        return error_dict


# ---------------------------------------------------------------------------
# 错误消息清洗与判定（自 protocol/conversation.py 下沉，供低层模块使用）
# ---------------------------------------------------------------------------


def public_image_error_message(message: str) -> str:
    """清洗图片生成错误消息，隐藏上游内部细节后再对外返回。"""
    text = str(message or "").strip()
    lower = text.lower()
    if any(item in lower for item in ("backend-api/", "status=", "body=", "chatgpt.com", "upstreamhttperror")):
        return "The image generation request failed. Please try again later."
    return text or "The image generation request failed. Please try again later."


def is_token_invalid_error(message: str) -> bool:
    """判定错误消息是否表示 token 已失效。"""
    text = str(message or "").lower()
    return (
        "token_invalidated" in text
        or "token_revoked" in text
        or "authentication token has been invalidated" in text
        or "invalidated oauth token" in text
    )


def is_tls_connection_error(message: str) -> bool:
    """检测 TLS/SSL 连接错误，这类错误通常可以通过重试解决。"""
    text = str(message or "").lower()
    return (
        "curl: (35)" in text
        or "tls connect error" in text
        or "openssl_internal" in text
        or "ssl: wrong_version_number" in text
        or "ssl: certificate_verify_failed" in text
        or "connection aborted" in text
        or "remote disconnected" in text
        or "connection reset by peer" in text
    )


def is_connection_timeout_error(message: str) -> bool:
    """检测连接超时错误（如 curl 28），这类错误可通过同账号短等待重试解决。"""
    text = str(message or "").lower()
    return (
        "curl: (28)" in text
        or "operation timed out" in text
        or "connection timed out" in text
        or "read timed out" in text
        or "connect timeout" in text
    )


def image_stream_error_message(message: str) -> str:
    """把图片流式链路的底层错误消息改写为可对外的稳定文案。"""
    text = str(message or "")
    if is_token_invalid_error(text):
        return "image generation failed"
    if is_tls_connection_error(text):
        return "upstream image connection failed, please retry later"
    if is_connection_timeout_error(text):
        return "upstream connection timed out, please retry later"
    return text or "image generation failed"


# ---------------------------------------------------------------------------
# 存储与 sub2api
# ---------------------------------------------------------------------------


class ImageStorageError(DomainError):
    """图片存储（本地/WebDAV）操作失败。"""

    status_code = 400


class Sub2apiError(DomainError):
    """sub2api 服务器登录、拉取或导入失败。"""

    status_code = 502


class CpaError(DomainError):
    """CPA 池远端拉取或导入失败。"""

    status_code = 502


class CodexSourceAccountError(DomainError):
    """codex /responses 通道要求 codex 来源账号而实际不是（保持 502 兼容既有对外响应）。"""

    status_code = 502


class ModelUnavailableError(DomainError):
    """请求的模型没有任何可用账号支撑。"""

    status_code = 502

