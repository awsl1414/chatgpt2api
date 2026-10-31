"""从 OpenAI 兼容请求的消息/请求体中提取图片输入。

自 utils/helper.py 迁出（审计 B-高6）：远程图片拉取依赖代理配置
（services 层），不属于无业务依赖的纯工具，故按依赖方向落到 services。
"""
from __future__ import annotations

import base64
import mimetypes
import re
from urllib.parse import urlparse

from curl_cffi import requests

from services.config import config
from services.errors import InvalidRequestError
from services.proxy_service import proxy_settings

SUPPORTED_JSON_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_JSON_IMAGE_BYTES = 10 * 1024 * 1024
DATA_URL_IMAGE_RE = re.compile(r"^data:(?P<mime>[-+./\w]+);base64,(?P<data>.*)$", re.DOTALL)
REMOTE_IMAGE_TIMEOUT_SECONDS = 20


def _image_extension(mime_type: str) -> str:
    image_type = mime_type.split("/", 1)[1].split(";", 1)[0].lower() if "/" in mime_type else "png"
    return "jpg" if image_type == "jpeg" else image_type or "png"


def _decode_json_image_string(value: str, index: int, filename: str | None = None, mime_type: str | None = None) -> tuple[bytes, str, str]:
    text = value.strip()
    if not text:
        raise InvalidRequestError("image file is empty")
    match = DATA_URL_IMAGE_RE.match(text)
    if match:
        resolved_mime = (match.group("mime") or "image/png").lower()
        encoded = match.group("data")
    else:
        if text.startswith(("http://", "https://")):
            raise InvalidRequestError("remote image URLs are not supported")
        resolved_mime = (mime_type or "image/png").lower()
        encoded = text
    if resolved_mime == "image/jpg":
        resolved_mime = "image/jpeg"
    if resolved_mime not in SUPPORTED_JSON_IMAGE_MIME_TYPES:
        raise InvalidRequestError("unsupported image mime type")
    try:
        image_data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise InvalidRequestError("invalid base64 image data") from exc
    if not image_data:
        raise InvalidRequestError("image file is empty")
    if len(image_data) > MAX_JSON_IMAGE_BYTES:
        raise InvalidRequestError("image file is too large")
    return image_data, filename or f"image_{index}.{_image_extension(resolved_mime)}", resolved_mime


def _message_image_url(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("url") or value.get("image_url") or "").strip()
    return str(value or "").strip()


def _decode_message_image_url(value: object) -> tuple[bytes, str] | None:
    source = _message_image_url(value)
    if source.startswith("data:"):
        header, _, data = source.partition(",")
        mime = header.split(";")[0].removeprefix("data:") or "image/png"
        return base64.b64decode(data), mime
    if not source.startswith(("http://", "https://")):
        return None
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    # SSRF 部署开关：面向公网部署时可关闭远程拉取，仅保留 data:/base64 图片输入
    if not config.allow_remote_image_fetch:
        raise InvalidRequestError(
            "remote image fetching is disabled by server configuration (allow_remote_image_fetch)"
        )

    try:
        response = requests.get(
            source,
            headers={"Accept": "image/*,*/*;q=0.8", "User-Agent": "chatgpt2api vision fetcher"},
            timeout=REMOTE_IMAGE_TIMEOUT_SECONDS,
            allow_redirects=True,
            **proxy_settings.build_session_kwargs(),
        )
    except Exception as exc:
        raise InvalidRequestError(f"image_url fetch failed: {exc}") from exc
    if not 200 <= response.status_code < 300:
        raise InvalidRequestError(f"image_url fetch failed: HTTP {response.status_code}")
    content_length = str(response.headers.get("content-length") or "").strip()
    if content_length.isdigit() and int(content_length) > MAX_JSON_IMAGE_BYTES:
        raise InvalidRequestError("image_url exceeds 10MB limit")
    image_data = response.content
    if not image_data:
        raise InvalidRequestError("image_url returned empty content")
    if len(image_data) > MAX_JSON_IMAGE_BYTES:
        raise InvalidRequestError("image_url exceeds 10MB limit")
    mime = str(response.headers.get("content-type") or "image/png").split(";", 1)[0].lower()
    guessed_mime = mimetypes.guess_type(parsed.path)[0] or ""
    if mime and not mime.startswith("image/") and mime not in {"application/octet-stream", "binary/octet-stream"}:
        raise InvalidRequestError("image_url must point to an image")
    if not mime.startswith("image/") and guessed_mime.startswith("image/"):
        mime = guessed_mime
    if not mime.startswith("image/"):
        mime = "image/png"
    return image_data, mime


def _decode_message_image_object(item: dict[str, object]) -> tuple[bytes, str] | None:
    data = item.get("data")
    if isinstance(data, (bytes, bytearray)):
        return bytes(data), str(item.get("mime") or item.get("mime_type") or "image/png")
    for key in ("image_url", "url"):
        image = _decode_message_image_url(item.get(key))
        if image:
            return image
    value = item.get("b64_json") or item.get("base64")
    if isinstance(value, str) and value.strip():
        image_data, _, mime = _decode_json_image_string(
            value,
            1,
            mime_type=str(item.get("mime") or item.get("mime_type") or item.get("mimeType") or "image/png"),
        )
        return image_data, mime
    source = item.get("source")
    if isinstance(source, dict) and str(source.get("type") or "") == "base64":
        encoded = str(source.get("data") or "")
        mime = str(source.get("media_type") or source.get("mime_type") or "image/png")
        image_data, _, resolved_mime = _decode_json_image_string(encoded, 1, mime_type=mime)
        return image_data, resolved_mime
    return None


def extract_image_from_message_content(content: object) -> list[tuple[bytes, str]]:
    if not isinstance(content, list):
        return []
    images = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "image_url":
            image = _decode_message_image_url(item.get("image_url") or item.get("url") or item)
            if image:
                images.append(image)
        elif item_type in {"input_image", "image"}:
            image = _decode_message_image_object(item)
            if image:
                images.append(image)
    return images


def extract_chat_image(body: dict[str, object]) -> list[tuple[bytes, str]]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return []
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        images = extract_image_from_message_content(message.get("content"))
        if images:
            return images
    return []


def parse_image_count(raw_value: object) -> int:
    """解析生图数量参数 n，超出 1-4 范围或非整数时抛 InvalidRequestError。"""
    try:
        value = int(raw_value or 1)
    except (TypeError, ValueError) as exc:
        raise InvalidRequestError("n must be an integer") from exc
    if value < 1 or value > 4:
        raise InvalidRequestError("n must be between 1 and 4")
    return value
