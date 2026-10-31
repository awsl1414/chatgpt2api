"""ChatGPT web 对话请求 payload 构建。

把 OpenAI 兼容层传入的标准 chat messages 转换为 chatgpt.com web 端
`/backend-api/conversation`、`/backend-api/f/conversation/prepare` 所需的
消息结构与请求体；需要客户端状态的函数以 `api: BackendClient`
显式声明依赖（如图片输入需经 `api._upload_image` 上传）。
"""

import base64
from typing import Any

from services.backend.context import BackendClient
from services.config import config
from utils.helper import CODEX_IMAGE_PUBLIC_MODELS, new_uuid, split_image_model
from utils.thinking import normalize_thinking_effort



def api_messages_to_conversation_messages(api: BackendClient, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把标准 chat messages 转成 web conversation 所需的 messages。"""
    conversation_messages = []
    for item in messages:
        role = item.get("role", "user")
        content = item.get("content", "")
        if isinstance(content, str):
            conversation_messages.append({
                "id": new_uuid(),
                "author": {"role": role},
                "content": {"content_type": "text", "parts": [content]},
            })
            continue
        if not isinstance(content, list):
            raise RuntimeError("only string or list message content is supported")
        text_parts: list[str] = []
        image_inputs: list[tuple[bytes, str]] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "")
            if part_type == "text":
                text_parts.append(str(part.get("text") or ""))
            elif part_type == "image":
                data = part.get("data")
                mime = str(part.get("mime") or "image/png")
                if isinstance(data, (bytes, bytearray)):
                    image_inputs.append((bytes(data), mime))
        if not image_inputs:
            conversation_messages.append({
                "id": new_uuid(),
                "author": {"role": role},
                "content": {"content_type": "text", "parts": ["".join(text_parts)]},
            })
            continue
        if not api.access_token:
            raise RuntimeError("authenticated upstream account required for image input")
        uploaded: list[dict[str, Any]] = []
        for idx, (data, mime) in enumerate(image_inputs, start=1):
            ext_part = mime.split("/", 1)[1].split("+")[0] if "/" in mime else "png"
            extension = "jpg" if ext_part == "jpeg" else (ext_part or "png")
            b64 = base64.b64encode(data).decode("ascii")
            uploaded.append(api._upload_image(f"data:{mime};base64,{b64}", f"image_{idx}.{extension}"))
        parts: list[Any] = []
        for ref in uploaded:
            parts.append({
                "content_type": "image_asset_pointer",
                "asset_pointer": f"file-service://{ref['file_id']}",
                "width": ref["width"],
                "height": ref["height"],
                "size_bytes": ref["file_size"],
            })
        text = "".join(text_parts)
        if text:
            parts.append(text)
        conversation_messages.append({
            "id": new_uuid(),
            "author": {"role": role},
            "content": {"content_type": "multimodal_text", "parts": parts},
            "metadata": {
                "attachments": [{
                    "id": ref["file_id"],
                    "mimeType": ref["mime_type"],
                    "name": ref["file_name"],
                    "size": ref["file_size"],
                    "width": ref["width"],
                    "height": ref["height"],
                } for ref in uploaded],
            },
        })
    return conversation_messages

def conversation_payload(
        api: BackendClient,
        messages: list[dict[str, Any]],
        model: str,
        timezone: str,
        thinking_effort: str = "",
) -> dict[str, Any]:
    """把标准 messages 构造成 web 对话请求体。"""
    payload = {
        "action": "next",
        "messages": api_messages_to_conversation_messages(api, messages),
        "model": model,
        "parent_message_id": new_uuid(),
        "conversation_mode": {"kind": "primary_assistant"},
        "conversation_origin": None,
        "force_paragen": False,
        "force_paragen_model_slug": "",
        "force_rate_limit": False,
        "force_use_sse": True,
        "history_and_training_disabled": True,
        "reset_rate_limits": False,
        "suggestions": [],
        "supported_encodings": [],
        "system_hints": [],
        "timezone": timezone,
        "timezone_offset_min": -480,
        "variant_purpose": "comparison_implicit",
        "websocket_request_id": new_uuid(),
        "client_contextual_info": {
            "is_dark_mode": False,
            "time_since_loaded": 120,
            "page_height": 900,
            "page_width": 1400,
            "pixel_ratio": 2,
            "screen_height": 1440,
            "screen_width": 2560,
        },
    }
    normalized_effort = normalize_thinking_effort(
        thinking_effort or config.default_thinking_effort,
        passthrough_standard_max=True,
    )
    if normalized_effort:
        payload["thinking_effort"] = normalized_effort
    return payload

def image_model_settings(model: str) -> tuple[str, str]:
    """把标准图片模型名映射为上游模型及思考强度。"""
    _, base_model = split_image_model(model)
    if not base_model:
        return "auto", ""
    if base_model == "gpt-image-2":
        upstream_model = config.default_upstream_model_name
    elif base_model in CODEX_IMAGE_PUBLIC_MODELS:
        upstream_model = base_model
    else:
        return "auto", ""
    model_name, separator, suffix = upstream_model.rpartition("-")
    if separator and suffix.lower() in {"standard", "extended", "max"}:
        return model_name, suffix.lower()
    return upstream_model, normalize_thinking_effort(config.default_thinking_effort, passthrough_standard_max=True)
