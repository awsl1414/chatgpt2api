"""消息 content 的协议层规范化与提示词文本压平。

职责边界：
- `normalize_message_list`：把 OpenAI/Anthropic 风格的消息列表规范化为上游对话结构
  （图片分段抽取、非 dict 元素忽略、system 原样保留）；
- `message_text`：从单条 content 中提取纯文本；
- `prompt_text_from_messages`：把消息列表中全部 user 文本压平成单一提示词；
- `image_hint_text`：把 size / quality 拼进生图提示词。

之所以落在 `services/protocol` 而非 `utils`：图片分段抽取依赖
`services.message_image`（远程拉取走代理配置与领域异常），属于业务逻辑；
`utils/__init__.py` 明确禁止 `utils` 反向依赖 `services`。
同一语义只能有一份实现——图片链路与文本链路的提示词压平都走
`prompt_text_from_messages`，它内部复用 `extract_prompt_from_message_content`。
"""
from __future__ import annotations

from typing import Any

from services.message_image import extract_image_from_message_content
from utils.helper import extract_prompt_from_message_content


def check_task_error(task: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """检查单个生图任务是否包含结构化错误（不依赖文本匹配）。

    判定字段：
    - `image_gen_message.metadata.is_error == True`
    - `image_gen_message.author.role == "assistant"`（而非 "tool"）
    - `image_gen_message.content.content_type == "text"`（而非 "multimodal_text"）

    返回 `(is_error, error_msg, metadata)`。纯结构化字段判定、无 IO，因此放在
    协议层供 `backend/image_task` 与 `protocol/image_stream` 共用，
    保持 `backend → protocol` 的单向依赖。
    """
    img_msg = task.get("image_gen_message") or {}
    if not img_msg:
        return False, "", {}

    metadata = img_msg.get("metadata") or {}
    content = img_msg.get("content") or {}
    author = img_msg.get("author") or {}

    is_error = metadata.get("is_error", False)
    is_text_only = content.get("content_type") == "text"

    # 提取错误文本
    error_msg = ""
    if is_error and is_text_only:
        parts = content.get("parts", [])
        error_msg = "".join(p for p in parts if isinstance(p, str))

    return is_error, error_msg, metadata


def message_text(content: Any) -> str:
    """从消息 content（字符串或分段列表）中提取纯文本，忽略图片等其他分段类型。

    分段直接相连、不加分隔符，与 OpenAI 兼容层的既有语义一致。
    提示词压平请用 `prompt_text_from_messages`（它在消息级别按换行连接 user 文本）。
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


def prompt_text_from_messages(messages: list[dict[str, Any]]) -> str:
    """把消息列表中全部 user 文本按换行压平成单一提示词。

    单条消息内部的分段拼接规则复用 `extract_prompt_from_message_content`
    （text / input_text 分段按换行连接、空分段跳过），消息之间同样按换行连接，
    因此与 `/v1/chat/completions` 图片链路的 `extract_chat_prompt` 语义一致。
    只有图片、没有文字的 user 消息不贡献文本。
    """
    parts: list[str] = []
    for message in messages:
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        text = extract_prompt_from_message_content(message.get("content"))
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def normalize_message_list(messages: object) -> list[dict[str, Any]]:
    """把 OpenAI 风格的消息列表规范化为上游对话结构（不含任何 system 注入）。

    规则：
    - user 消息中的图片（base64 / bytes 分段）被抽取为 `{"type": "image", ...}` 分段，
      与文本分段并存；其余消息只保留纯文本；
    - 非 list 输入与非 dict 元素被忽略；
    - system 消息原样保留（是否折进提示词由调用方决策）；
    - 既无文本也无图片的 user 消息被丢弃，避免上游收到空 user 消息；
      其他角色的空消息保留（assistant 占位、tool 结果等有协议语义）。
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
        elif text or str(role or "").strip().lower() != "user":
            normalized.append({"role": role, "content": text})
    return normalized


def image_hint_text(prompt: str, size: str | None, quality: str, orientation: str = "") -> str:
    """把 size / quality 以中文提示拼进生图提示词。

    `quality == "auto"` 时不注入质量句——旧实现是 `if quality:`，会把默认值
    「输出图片质量为 auto。」也发给上游；这是有意的行为变更（见 CHANGELOG）。

    `orientation` 非空时（`横版` / `竖版` / `方形`）追加在尺寸之后：接口 `size`
    对 codex 链路完全无效，提示词是唯一有效通道，实测「像素 + 方向」的中文措辞
    （`图片尺寸：1024x1792，竖版。`）能稳定决定宽高比（见工作区
    `docs/size-verification.md` §4.3）。picture_v2 的接口 size 本身生效，保持原措辞。
    """
    hints: list[str] = []
    if size:
        suffix = f"，{orientation}" if orientation else ""
        hints.append(f"输出图片尺寸为 {size}{suffix}。")
    if quality and quality != "auto":
        hints.append(f"输出图片质量为 {quality}。")
    return f"{prompt.strip()}\n\n{''.join(hints)}" if hints else prompt
