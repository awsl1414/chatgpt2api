"""协议层 SSE 事件解析。

把 ChatGPT 上游 `/backend-api/conversation` 的 SSE 载荷解析为统一的
conversation.* 事件流（done / raw / event / delta），并维护会话状态
（conversation_id、file_ids、sediment_ids、blocked、tool_invoked 等）。
本模块只依赖 `message_utils` 与 `services.openai_backend_api`（类型），
不得反向依赖 protocol 包内其他模块。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from services.openai_backend_api import OpenAIBackendAPI
from services.protocol.message_utils import (
    assistant_history_messages,
    assistant_history_text,
    build_image_prompt,
    normalize_messages,
    prompt_with_global_system,
)
from utils.helper import is_supported_image_model


@dataclass
class ConversationState:
    """单次上游对话流中逐步累积的会话状态。"""

    text: str = ""
    raw_text: str = ""
    conversation_id: str = ""
    file_ids: list[str] = field(default_factory=list)
    sediment_ids: list[str] = field(default_factory=list)
    blocked: bool = False
    tool_invoked: bool | None = None
    turn_use_case: str = ""


def assistant_message_text(message: dict[str, Any]) -> str:
    """提取上游 assistant 消息的正文文本，兼容 content_type 为 code 的消息。"""
    content = message.get("content") or {}
    parts = content.get("parts") or []
    if isinstance(parts, list) and parts:
        text = "".join(part for part in parts if isinstance(part, str))
        if text:
            return text
    # Fallback: content_type "code" stores text in the "text" field instead of "parts"
    text_field = str(content.get("text") or "")
    if text_field:
        return text_field
    return ""


def is_visible_assistant_message(message: dict[str, Any]) -> bool:
    """Return whether an upstream assistant message is intended for the user."""
    author = message.get("author")
    if not isinstance(author, dict):
        return False
    role = str(author.get("role") or "").strip().lower()
    if role != "assistant":
        return False

    metadata = message.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("is_visually_hidden_from_conversation") is True:
        return False

    # Tool commands are emitted as assistant messages addressed to recipients
    # such as "web". Only messages addressed to everyone are user-visible.
    recipient = str(message.get("recipient") or "").strip().lower()
    if recipient and recipient != "all":
        return False

    # Reasoning and other internal channels must not leak into API text output.
    channel = str(message.get("channel") or "").strip().lower()
    if channel and channel != "final":
        return False

    return True


def strip_history(text: str, history_text: str = "") -> str:
    """剥掉上游回放的请求历史前缀，只保留本轮新增内容。"""
    text = str(text or "")
    history_text = str(history_text or "")
    while history_text and text.startswith(history_text):
        text = text[len(history_text):]
    return text


def sanitize_output_text(text: str) -> str:
    """清洗模型输出中的私有注解标记（引用/链接），保留可读标签、去除内部指针。"""
    text = str(text or "")

    def is_internal_annotation_part(part: str) -> bool:
        value = part.strip()
        if not value:
            return True
        lower = value.lower()
        return bool(
            re.fullmatch(r"turn\d+[a-z]*\d*", lower)
            or re.fullmatch(r"turn\d+\w*", lower)
            or lower.startswith(("turn", "source", "sources"))
        )

    def readable_annotation_part(parts: list[str]) -> str:
        for part in parts:
            value = part.strip()
            if value and not is_internal_annotation_part(value):
                return value
        return ""

    def annotation_text(payload: str) -> str:
        parts = [part.strip() for part in payload.split("")]
        kind = (parts[0] if parts else "").lower()
        data = parts[1:]
        if kind == "url":
            label = data[0] if data else ""
            url = data[1] if len(data) > 1 else ""
            if label and url.startswith(("http://", "https://")):
                return f"{label} ({url})"
            return label or url
        if kind == "cite":
            return readable_annotation_part(data)
        return readable_annotation_part(data)

    def replace_annotation(match: re.Match[str]) -> str:
        return annotation_text(match.group(1))

    def replace_annotation_before_punctuation(match: re.Match[str]) -> str:
        leading_space = match.group(1)
        replacement = annotation_text(match.group(2))
        return f"{leading_space}{replacement}" if replacement else ""

    # ChatGPT web sometimes returns rich annotation markers using private-use
    # characters. API clients cannot render those. Preserve readable labels
    # from entity/link annotations, while removing internal citation pointers.
    text = re.sub(r"(\s*)([^]*)(?=[.,;:!?])", replace_annotation_before_punctuation, text)
    text = re.sub(r"([^]*)", replace_annotation, text)
    text = re.sub(r"[^]*$", "", text)
    return text


def assistant_raw_text(event: dict[str, Any], current_text: str = "", history_text: str = "") -> str:
    """从事件中提取未清洗的 assistant 原文；消息型事件优先，否则回退到 patch 增量。"""
    for candidate in (event, event.get("v")):
        if not isinstance(candidate, dict):
            continue
        message = candidate.get("message")
        if not isinstance(message, dict) or not is_visible_assistant_message(message):
            continue
        text = assistant_message_text(message)
        if text:
            return strip_history(text, history_text)
    return apply_text_patch(event, current_text, history_text)


def event_assistant_text(event: dict[str, Any], history_text: str = "") -> str:
    """从事件中提取 assistant 文本（仅消息型事件），用于比对历史回放。"""
    for candidate in (event, event.get("v")):
        if not isinstance(candidate, dict):
            continue
        message = candidate.get("message")
        if isinstance(message, dict) and is_visible_assistant_message(message):
            return strip_history(assistant_message_text(message), history_text)
    return ""


def apply_text_patch(event: dict[str, Any], current_text: str = "", history_text: str = "") -> str:
    """把单个 SSE patch 事件应用到当前文本上，返回新文本。"""
    if event.get("p") == "/message/content/parts/0":
        return apply_patch_op(event, current_text, history_text)

    operations = event.get("v")
    if isinstance(operations, str) and current_text and not event.get("p") and not event.get("o"):
        return current_text + operations

    if event.get("o") == "patch" and isinstance(operations, list):
        text = current_text
        for item in operations:
            if isinstance(item, dict):
                text = apply_text_patch(item, text, history_text)
        return text

    if not isinstance(operations, list):
        return current_text

    text = current_text
    for item in operations:
        if isinstance(item, dict):
            text = apply_text_patch(item, text, history_text)
    return text


def apply_patch_op(operation: dict[str, Any], current_text: str, history_text: str = "") -> str:
    """应用单个 patch 操作（append / replace）到当前文本。"""
    op = operation.get("o")
    value = str(operation.get("v") or "")
    if op == "append":
        return current_text + value
    if op == "replace":
        return strip_history(value, history_text)
    return current_text


def add_unique(values: list[str], candidates: list[str]) -> None:
    """把 candidates 中非空且未出现的值追加进 values（原地修改）。"""
    for candidate in candidates:
        if candidate and candidate not in values:
            values.append(candidate)


FILE_SERVICE_ID_RE = re.compile(r"file-service://([A-Za-z0-9_-]+)")
FILE_ID_RE = re.compile(r"\b(file[-_](?!service\b)[A-Za-z0-9_-]+)\b")
# 真正的图片文件 ID 格式：file_00000000 + 24位十六进制字符（共32字符）
# 用于过滤非图片文件 ID（如 file_upload_business_upsell）
REAL_IMAGE_FILE_ID_RE = re.compile(r"\bfile_00000000[a-f0-9]{24}\b")
SEDIMENT_ID_RE = re.compile(r"sediment://([A-Za-z0-9_-]+)")


def extract_conversation_ids(payload: str) -> tuple[str, list[str], list[str]]:
    """从 SSE 载荷原文中提取 conversation_id、图片 file_ids 与 sediment_ids。"""
    conversation_match = re.search(r'"conversation_id"\s*:\s*"([^"]+)"', payload)
    conversation_id = conversation_match.group(1) if conversation_match else ""
    file_ids: list[str] = []
    # Negative lookahead excludes "file-service" (URI prefix, not a real id).
    add_unique(file_ids, FILE_SERVICE_ID_RE.findall(payload))
    # 只提取真正的图片文件 ID（file_00000000... 格式），过滤非图片文件 ID（如 file_upload_business_upsell）
    add_unique(file_ids, REAL_IMAGE_FILE_ID_RE.findall(payload))
    sediment_ids = SEDIMENT_ID_RE.findall(payload)
    return conversation_id, file_ids, sediment_ids


def is_image_tool_event(event: dict[str, Any]) -> bool:
    """判断事件是否为图片生成工具消息（async_task_type=image_gen 或含图片资产指针）。"""
    value = event.get("v")
    message = event.get("message") or (value.get("message") if isinstance(value, dict) else None)
    if not isinstance(message, dict):
        return False
    metadata = message.get("metadata") or {}
    author = message.get("author") or {}
    content = message.get("content") or {}
    if author.get("role") != "tool":
        return False
    if metadata.get("async_task_type") == "image_gen":
        return True
    if content.get("content_type") != "multimodal_text":
        return False
    return any(
        isinstance(part, dict) and (
                part.get("content_type") == "image_asset_pointer"
                or str(part.get("asset_pointer") or "").startswith(("file-service://", "sediment://"))
        )
        for part in content.get("parts") or []
    )


def _is_user_message_event(event: dict[str, Any]) -> bool:
    """检查事件是否来自 user 角色消息。"""
    value = event.get("v")
    message = event.get("message") or (value.get("message") if isinstance(value, dict) else None)
    if isinstance(message, dict):
        author = message.get("author") or {}
        if str(author.get("role") or "").strip().lower() == "user":
            return True
    return False


def update_conversation_state(state: ConversationState, payload: str, event: dict[str, Any] | None = None) -> None:
    """把单个事件（含载荷原文）累积进会话状态。

    file_id / sediment_id 只在图片生成上下文中采纳（完整图片工具消息、
    非用户消息且 tool_invoked 已置位、或引用资产指针的 patch 事件），
    避免把用户上传的输入图片误认成生成结果。
    """
    conversation_id, file_ids, sediment_ids = extract_conversation_ids(payload)
    if conversation_id and not state.conversation_id:
        state.conversation_id = conversation_id
    # Accept file_id / sediment_id when any of:
    #   1) event is a complete image_gen tool message
    #   2) prior server_ste_metadata already flipped tool_invoked True (in an image_gen turn),
    #      BUT only for non-user messages — user messages contain the uploaded input image
    #      which must NOT be treated as a generated output.
    #   3) patch event whose payload references asset_pointer / file-service://,
    #      BUT only when the event is not a user message.
    is_patch_event = isinstance(event, dict) and event.get("o") == "patch"
    is_user_msg = isinstance(event, dict) and _is_user_message_event(event)
    image_context = (
        (isinstance(event, dict) and is_image_tool_event(event))
        or (state.tool_invoked is True and not is_user_msg)
        or (is_patch_event and not is_user_msg and ("asset_pointer" in payload or "file-service://" in payload))
    )
    if image_context:
        add_unique(state.file_ids, file_ids)
        add_unique(state.sediment_ids, sediment_ids)
    if not isinstance(event, dict):
        return
    state.conversation_id = str(event.get("conversation_id") or state.conversation_id)
    value = event.get("v")
    if isinstance(value, dict):
        state.conversation_id = str(value.get("conversation_id") or state.conversation_id)
    if event.get("type") == "moderation":
        moderation = event.get("moderation_response")
        if isinstance(moderation, dict) and moderation.get("blocked") is True:
            state.blocked = True
    if event.get("type") == "server_ste_metadata":
        metadata = event.get("metadata")
        if isinstance(metadata, dict):
            if isinstance(metadata.get("tool_invoked"), bool):
                state.tool_invoked = metadata["tool_invoked"]
            state.turn_use_case = str(metadata.get("turn_use_case") or state.turn_use_case)


def conversation_base_event(event_type: str, state: ConversationState, **extra: Any) -> dict[str, Any]:
    """构造统一的 conversation.* 事件字典（携带当前会话状态快照）。"""
    return {
        "type": event_type,
        "text": state.text,
        "conversation_id": state.conversation_id,
        "file_ids": list(state.file_ids),
        "sediment_ids": list(state.sediment_ids),
        "blocked": state.blocked,
        "tool_invoked": state.tool_invoked,
        "turn_use_case": state.turn_use_case,
        **extra,
    }


def iter_conversation_payloads(payloads: Iterator[str], history_text: str = "",
                               history_messages: list[str] | None = None) -> Iterator[dict[str, Any]]:
    """把上游 SSE 载荷流解析为统一的 conversation.* 事件流。

    - `[DONE]` 产生 conversation.done；
    - JSON 解析失败的产生 conversation.raw；
    - 命中历史回放的消息被逐条跳过（不重复输出给调用方）；
    - 文本有新增时产生 conversation.delta，其余事件透传为 conversation.event。
    """
    state = ConversationState()
    history_messages = history_messages or []
    history_index = 0
    for payload in payloads:
        if not payload:
            continue
        if payload == "[DONE]":
            yield conversation_base_event("conversation.done", state, done=True)
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            update_conversation_state(state, payload)
            yield conversation_base_event("conversation.raw", state, payload=payload)
            continue
        if not isinstance(event, dict):
            yield conversation_base_event("conversation.event", state, raw=event)
            continue
        update_conversation_state(state, payload, event)
        if history_index < len(history_messages) and event_assistant_text(event, history_text) == history_messages[history_index]:
            history_index += 1
            state.raw_text = ""
            state.text = ""
            continue
        next_raw_text = assistant_raw_text(event, state.raw_text, history_text)
        next_text = sanitize_output_text(next_raw_text)
        state.raw_text = next_raw_text
        if next_text != state.text:
            delta = next_text[len(state.text):] if next_text.startswith(state.text) else next_text
            state.text = next_text
            yield conversation_base_event("conversation.delta", state, raw=event, delta=delta)
            continue
        yield conversation_base_event("conversation.event", state, raw=event)


def conversation_events(
    backend: OpenAIBackendAPI,
    messages: list[dict[str, Any]] | None = None,
    model: str = "auto",
    prompt: str = "",
    images: list[str] | None = None,
    size: str | None = None,
    quality: str = "auto",
    thinking_effort: str = "",
    size_enabled: bool = False,
) -> Iterator[dict[str, Any]]:
    """发起一次上游对话并把 SSE 流解析为 conversation.* 事件流。

    图片模型走 picture_v2 系统提示并附带图片输入；文本模型保留历史回放
    用于在事件流中剔除上游重复输出。
    """
    normalized = normalize_messages(messages or ([{"role": "user", "content": prompt}] if prompt else []))
    image_model = is_supported_image_model(model)
    history_text = "" if image_model else assistant_history_text(normalized)
    history_messages = [] if image_model else assistant_history_messages(normalized)
    if image_model:
        hinted_prompt = build_image_prompt(prompt, size, quality) if size_enabled else prompt
        final_prompt = prompt_with_global_system(hinted_prompt)
    else:
        final_prompt = prompt
    payloads = backend.stream_conversation(
        messages=normalized,
        model=model,
        prompt=final_prompt,
        images=images if image_model else None,
        system_hints=["picture_v2"] if image_model else None,
        thinking_effort=thinking_effort if not image_model else "",
    )
    yield from iter_conversation_payloads(payloads, history_text, history_messages)
