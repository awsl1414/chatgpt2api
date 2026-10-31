"""通用工具集：模型名解析、上游 HTTP/SSE 原语与共享常量。

包含 /v1 模型名拆分（split_image_model）、codex 模型映射、
UpstreamHTTPError 与 SSE 流解析等纯工具；禁止依赖 services 层。
"""

import base64
import hashlib
import json
import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlparse

from curl_cffi import requests
from utils.log import logger

BASE_IMAGE_MODELS = {
    "gpt-image-2",
    "codex-gpt-image-2",
    # codex/responses 工具层 2.5 模型（2026-10-30 实测有效，见逆向仓库 docs/api/codex-image.md §6）
    "codex-gpt-image-2.5-flare",
    "codex-gpt-image-2.5-sunburst",
}
IMAGE_MODEL_PLAN_TYPES = ("plus", "team", "pro")
CODEX_IMAGE_MODEL = "codex-gpt-image-2"
# 走 codex/responses 通道的公开模型名；对应上游工具层模型 ID = 去掉 "codex-" 前缀
CODEX_IMAGE_PUBLIC_MODELS = {
    "codex-gpt-image-2",
    "codex-gpt-image-2.5-flare",
    "codex-gpt-image-2.5-sunburst",
}
PREFIXED_CODEX_IMAGE_MODELS = {
    f"{plan_type}-{model}"
    for plan_type in IMAGE_MODEL_PLAN_TYPES
    for model in CODEX_IMAGE_PUBLIC_MODELS
}
IMAGE_MODELS = BASE_IMAGE_MODELS | PREFIXED_CODEX_IMAGE_MODELS
PUBLIC_IMAGE_MODELS = BASE_IMAGE_MODELS | PREFIXED_CODEX_IMAGE_MODELS
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

def new_uuid() -> str:
    return str(uuid.uuid4())


def split_image_model(model: object) -> tuple[str | None, str | None]:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return None, None
    if normalized in BASE_IMAGE_MODELS:
        return None, normalized
    for plan_type in IMAGE_MODEL_PLAN_TYPES:
        prefix = f"{plan_type}-"
        if normalized.startswith(prefix):
            base_model = normalized[len(prefix):]
            if base_model in CODEX_IMAGE_PUBLIC_MODELS:
                return plan_type, base_model
    return None, None


def is_supported_image_model(model: object) -> bool:
    _, base_model = split_image_model(model)
    return base_model is not None


def is_codex_image_model(model: object) -> bool:
    _, base_model = split_image_model(model)
    return base_model in CODEX_IMAGE_PUBLIC_MODELS


def codex_image_tool_model(model: object) -> str:
    """codex-gpt-image-* 公开模型名 → 上游 codex/responses 工具层模型 ID。"""
    _, base_model = split_image_model(model)
    if base_model is None or not base_model.startswith("codex-"):
        return "gpt-image-2"
    return base_model[len("codex-"):]


def is_image_chat_request(body: dict[str, object]) -> bool:
    model = str(body.get("model") or "").strip()
    modalities = body.get("modalities")
    if is_supported_image_model(model):
        return True
    return isinstance(modalities, list) and "image" in {str(item or "").strip().lower() for item in modalities}


_UPSTREAM_BODY_LOG_LIMIT = 500


class UpstreamHTTPError(RuntimeError):
    """Raised when an upstream HTTP call returns a non-2xx status.

    Carries structured fields (status_code, body, retry_after) so callers can
    branch on status code instead of string-matching on str(exc). The full
    body is preserved on the instance; the formatted message truncates it
    to keep log lines reasonable.
    """

    def __init__(
        self,
        context: str,
        status_code: int,
        body: Any,
        retry_after: int | None = None,
    ) -> None:
        self.context = context
        self.status_code = status_code
        self.body = body
        self.retry_after = retry_after
        if isinstance(body, (dict, list)):
            try:
                body_str = json.dumps(body, ensure_ascii=False)
            except (TypeError, ValueError):
                body_str = repr(body)
        else:
            body_str = str(body)
        if len(body_str) > _UPSTREAM_BODY_LOG_LIMIT:
            body_str = body_str[:_UPSTREAM_BODY_LOG_LIMIT] + "…[truncated]"
        super().__init__(f"{context} failed: status={status_code}, body={body_str}")


def ensure_ok(response: requests.Response, context: str) -> None:
    if 200 <= response.status_code < 300:
        return
    body: Any = response.text
    try:
        body = response.json()
    except Exception:
        pass
    retry_after_header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
    retry_after: int | None = None
    if retry_after_header is not None:
        ra_str = str(retry_after_header).strip()
        if ra_str.isdigit():
            retry_after = int(ra_str)
    raise UpstreamHTTPError(context, response.status_code, body, retry_after=retry_after)


def sse_json_stream(items: Iterable[dict[str, Any]]) -> Iterator[str]:
    yield ": stream-open\n\n"
    try:
        for item in items:
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.warning({
            "event": "sse_stream_error",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        })
        error = exc.to_openai_error() if hasattr(exc, "to_openai_error") else {
            "error": {"message": str(exc), "type": exc.__class__.__name__}
        }
        yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def anthropic_sse_stream(items: Iterable[dict[str, Any]]) -> Iterator[str]:
    try:
        for item in items:
            event = str(item.get("type") or "message_delta") if isinstance(item, dict) else "message_delta"
            yield f"event: {event}\n"
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.warning({
            "event": "anthropic_sse_stream_error",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        })
        error = {"type": "error", "error": {"type": exc.__class__.__name__, "message": str(exc)}}
        yield "event: error\n"
        yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"


def iter_sse_payloads(response: requests.Response) -> Iterator[str]:
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else str(raw_line)
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload:
            yield payload


def save_images_from_text(text: str, prefix: str) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    matches = re.findall(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", text or "")
    saved_paths: list[Path] = []
    timestamp = int(time.time() * 1000)
    for index, data_url in enumerate(matches, start=1):
        header, encoded = data_url.split(",", 1)
        image_type = header.split(";")[0].removeprefix("data:image/").strip() or "png"
        extension = "jpg" if image_type == "jpeg" else image_type
        output_path = OUTPUT_DIR / f"{prefix}_{timestamp}_{index}.{extension}"
        output_path.write_bytes(base64.b64decode(encoded))
        saved_paths.append(output_path)
    return saved_paths


def anonymize_token(token: object) -> str:
    value = str(token or "").strip()
    if not value:
        return "token:empty"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"token:{digest}"


def extract_response_prompt(input_value: object) -> str:
    if isinstance(input_value, str):
        return input_value.strip()
    if isinstance(input_value, dict):
        role = str(input_value.get("role") or "").strip().lower()
        if role and role != "user":
            return ""
        return extract_prompt_from_message_content(input_value.get("content"))
    if not isinstance(input_value, list):
        return ""
    prompt_parts: list[str] = []
    for item in input_value:
        if isinstance(item, dict) and str(item.get("type") or "").strip() == "input_text":
            text = str(item.get("text") or "").strip()
            if text:
                prompt_parts.append(text)
            continue
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role and role != "user":
            continue
        prompt = extract_prompt_from_message_content(item.get("content"))
        if prompt:
            prompt_parts.append(prompt)
    return "\n".join(prompt_parts).strip()


def has_response_image_generation_tool(body: dict[str, object]) -> bool:
    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and str(tool.get("type") or "").strip() == "image_generation":
                return True
    tool_choice = body.get("tool_choice")
    return isinstance(tool_choice, dict) and str(tool_choice.get("type") or "").strip() == "image_generation"


def extract_prompt_from_message_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "text":
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
        elif item_type == "input_text":
            text = str(item.get("text") or item.get("input_text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def extract_chat_prompt(body: dict[str, object]) -> str:
    direct_prompt = str(body.get("prompt") or "").strip()
    if direct_prompt:
        return direct_prompt
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    prompt_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        prompt = extract_prompt_from_message_content(message.get("content"))
        if prompt:
            prompt_parts.append(prompt)
    return "\n".join(prompt_parts).strip()


def build_chat_image_markdown_content(image_result: dict[str, object]) -> str:
    image_items = image_result.get("data") if isinstance(image_result.get("data"), list) else []
    markdown_images: list[str] = []
    for index, item in enumerate(image_items, start=1):
        if not isinstance(item, dict):
            continue
        b64_json = str(item.get("b64_json") or "").strip()
        if b64_json:
            markdown_images.append(f"![image_{index}](data:image/png;base64,{b64_json})")
    return "\n\n".join(markdown_images) if markdown_images else "Image generation completed."
