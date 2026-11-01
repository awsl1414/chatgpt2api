"""OpenAI 风格消息 content 的纯工具函数。

`message_utils`（协议层语义规范化）与 `prompt_plan`（提示词事实源）都需要
「从 content 提取纯文本」「把消息列表规范化成上游结构」这类逻辑。二者分属
不同模块、且依赖纪律不允许 `prompt_plan` 反向 import `message_utils`，
因此把这段无业务依赖的纯逻辑下沉到此模块，双方共同 import。

本模块只依赖 `services.message_image`（图片分段抽取），不含任何配置读取或
业务决策。
"""
from __future__ import annotations

from typing import Any

from services.message_image import extract_image_from_message_content


def message_text(content: Any) -> str:
    """从消息 content（字符串或分段列表）中提取纯文本，忽略图片等其他分段类型。

    分段直接相连、不加分隔符，与 OpenAI 兼容层的既有语义一致。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and str(item.get("type") or "") in {"text", "input_text", "output_text"}:
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return ""


def normalize_message_list(messages: object) -> list[dict[str, Any]]:
    """把 OpenAI 风格的消息列表规范化为上游对话结构（不含任何 system 注入）。

    规则：
    - user 消息中的图片（base64 / bytes 分段）被抽取为 `{"type": "image", ...}` 分段，
      与文本分段并存；其余消息只保留纯文本；
    - 非 list 输入与非 dict 元素被忽略；
    - system 消息原样保留（是否折进提示词由调用方决策）。
    """
    normalized: list[dict[str, Any]] = []
    if not isinstance(messages, list):
        return normalized
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "user")
        content = message.get("content", "")
        text = message_text(content)
        images: list[tuple[bytes, str]] = []
        if role == "user":
            images.extend(extract_image_from_message_content(content))
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict) or part.get("type") != "image":
                        continue
                    data = part.get("data")
                    if isinstance(data, (bytes, bytearray)) and all(
                        existing[0] != bytes(data) for existing in images
                    ):
                        images.append((bytes(data), str(part.get("mime") or "image/png")))
        if images:
            parts: list[Any] = []
            if text:
                parts.append({"type": "text", "text": text})
            for data, mime in images:
                parts.append({"type": "image", "data": data, "mime": mime})
            normalized.append({"role": role, "content": parts})
        else:
            normalized.append({"role": role, "content": text})
    return normalized


def image_hint_text(prompt: str, size: str | None, quality: str) -> str:
    """把 size / quality 以中文提示拼进生图提示词；`quality == "auto"` 时不注入质量句。"""
    hints: list[str] = []
    if size:
        hints.append(f"输出图片尺寸为 {size}。")
    if quality and quality != "auto":
        hints.append(f"输出图片质量为 {quality}。")
    return f"{prompt.strip()}\n\n{''.join(hints)}" if hints else prompt
