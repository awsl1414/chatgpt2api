"""提示词事实源：一次上游请求的提示词构造与按链路渲染。

本模块是提示词组装的单一事实源：`build_prompt_plan` 在**请求路径内**构造一次
`PromptPlan`，各链路（文本 / picture_v2 / codex）只通过 renderer 做形态转换，
不再各自判断「要不要注入 global system」「要不要拼尺寸/质量文本」。

依赖纪律：只依赖 `services.config` / `services.protocol.message_content` / `utils`；
`message_content` 是纯规范化工具（不含业务决策），不反向依赖本模块，因此不构成环。
**不得** import protocol 包内其他模块（`message_utils` / `event_parse` / `image_stream`），
避免形成环。

热更新红线：`config` 是进程内单例，`global_system_prompt` 每次访问都实时读
`config.data`，管理端改配置后同一进程的下一个请求立即生效。因此本模块所有
模块级常量都必须是**静态文本**，绝不能把 config 求值进模块级常量；
`PromptPlan` 只能在请求路径内构造。

注入与幂等：端点从调用方原始 messages 构造一次 plan，渲染结果只发往上游，
**不会回灌** `build_prompt_plan`，因此不存在「每轮累积 global」的问题。
`build_prompt_plan` 额外识别本模块渲染出的前置 system（全等匹配），使
「调用方回放已渲染请求」路径同样幂等。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from services.config import config
from services.protocol.message_content import (
    image_hint_text,
    message_text,
    normalize_message_list,
    prompt_text_from_messages,
)
from utils.helper import is_supported_image_model

# 请求带不受支持的工具（非搜索类）时注入的兜底 system 文案（唯一副本）。
TOOL_UNAVAILABLE_SYSTEM_MESSAGE = (
    "This compatibility backend cannot execute local tools, shell commands, non-search tools, "
    "or file operations. Do not claim to have run tools or inspected external resources. "
    "If a user asks you to use a tool, say that tool execution is unavailable through this backend."
)

# codex 链路的固定英文指令（唯一事实源）。`services/backend/codex_image.py`
# 从这里 import 后用作 `iter_codex_image_response_events` 的默认参数值。
CODEX_RESPONSES_INSTRUCTIONS = (
    "Use the image_generation tool to create exactly one image for the user's request. "
    "Return the generated image result."
)

# 图片模型走 ChatGPT 网页端生图通道时携带的 system hint。
PICTURE_V2_HINT = "picture_v2"

# 纯图片、无文字请求（图生图）的兜底指令：上游必须收到非空 prompt。
IMAGE_ONLY_PROMPT = "按参考图生成图片。"


@dataclass(frozen=True)
class PromptPlan:
    """一次上游请求的提示词事实源。

    构造一次，各链路按需渲染。所有注入决策（system 合并、hints、
    尺寸文本）在此确定，renderer 只做形态转换，不再做策略判断。

    字段语义：
    - `system`：global system 与请求级 system 已合并去重的单个字符串；
    - `messages`：规范化后的完整对话历史，**不含**前置 system 消息（已折进 `system`）；
      图片链路不使用该字段（picture_v2 只认压平后的 `prompt`）；
    - `prompt`：实际发往上游的单一文本，图片链路已拼接尺寸/质量提示，保证非空；
    - `hints`：随请求发送的 system hint（图片链路为 `picture_v2`）；
    - `images`：base64 编码的输入图片，是图片输入的**唯一**事实源。

    生图参数 `size` / `quality` 不作为 plan 字段保存：它们只影响 `prompt` 文本
    （`size_enabled` 时已拼入），运行时透传给上游工具层时一律读
    `ConversationRequest.size` / `.quality`，避免同一事实存两处。
    """

    system: str
    messages: list[dict[str, Any]]
    prompt: str
    hints: list[str]
    images: list[str]


def _has_image_parts(messages: list[dict[str, Any]]) -> bool:
    """判断规范化后的消息里是否含图片分段（`{"type": "image", ...}`）。"""
    for message in messages:
        content = message.get("content")
        if isinstance(content, list) and any(
            isinstance(part, dict) and part.get("type") == "image" for part in content
        ):
            return True
    return False


def _images_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    """从规范化消息的图片分段中提取 base64 编码的图片，供 picture_v2 作为图片输入。"""
    encoded: list[str] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image":
                continue
            data = part.get("data")
            if isinstance(data, (bytes, bytearray)) and data:
                encoded.append(base64.b64encode(bytes(data)).decode("ascii"))
    return encoded


def build_prompt_plan(
    *,
    model: str,
    messages: list[dict[str, Any]] | None = None,
    prompt: str = "",
    images: list[str] | None = None,
    size: str | None = None,
    quality: str = "auto",
    size_enabled: bool = False,
    hints: list[str] | None = None,
    system: Any = None,
    tool_unavailable: bool = False,
) -> PromptPlan:
    """构造一次上游请求的 `PromptPlan`（必须在请求路径内调用）。

    参数：
    - `model`：请求模型名，用于推导默认 `hints`；
    - `messages`：OpenAI 风格的消息列表；为空且给了 `prompt` 时按单条 user 消息处理；
    - `prompt`：调用方原始提示词；为空时从 messages 的 user 文本压平派生（保证非空）；
    - `images`：base64 输入图片；为空时从 messages 的图片分段派生；
    - `size` / `quality`：生图参数；
    - `size_enabled`：接口契约里明确有 size 参数时才为 True，此时才把尺寸/质量拼进 `prompt`；
    - `hints`：显式 system hint；为 None 时图片模型默认 `["picture_v2"]`，其余为空；
    - `system`：请求级 system（字符串或 Anthropic 分段列表），与 global system 合并去重；
    - `tool_unavailable`：是否在 system 末尾追加 `TOOL_UNAVAILABLE_SYSTEM_MESSAGE`。

    system 合并顺序固定为 `[global, 请求级 system, 调用方前置 system, tool_unavailable]`，
    重复文本只保留首次出现（与旧实现保持一致）。消息列表里的前置 system 消息
    同样折进 `system`。

    幂等：调用方把本模块**渲染后**的上游 messages 原样回放时，首条 system 会被
    识别为已注入（全等，或「合并结果 + 调用方自带 system」的前缀形态）并剥离，
    不会重复累积 global；调用方在 messages 里自带的 system 同样被计数一次。

    副作用：读取 `config.global_system_prompt`（实时，支持热更新）；
    派生 prompt 时可能触发 `image_url` 远程拉取（受 `allow_remote_image_fetch` 开关约束）。
    """
    global_system = config.global_system_prompt
    raw_messages = messages if isinstance(messages, list) and messages else None
    if raw_messages is None and str(prompt or "").strip():
        raw_messages = [{"role": "user", "content": prompt}]
    normalized = normalize_message_list(raw_messages)

    leading_system: list[str] = []
    while normalized and normalized[0].get("role") == "system":
        text = normalized.pop(0).get("content")
        if isinstance(text, str) and text:
            leading_system.append(text)

    request_system = message_text(system)
    tool_system = TOOL_UNAVAILABLE_SYSTEM_MESSAGE if tool_unavailable else ""
    merged = "\n\n".join(
        part for part in dict.fromkeys((global_system, request_system, tool_system)) if part
    )
    # 幂等：调用方回放了本模块渲染出的 system 时丢弃已注入部分，避免二次累积。
    # 两种形态都要覆盖：
    # ① 首条 system 恰好等于本次合并结果（纯注入，无调用方自带 system）；
    # ② 首条 system 是「本次合并结果 + 调用方自带 system」——剥离已注入的前缀，
    #    保留调用方剩余文本。只在前缀精确匹配 `merge + 两个换行` 时剥离，
    #    不做子串替换，因此调用方自身文本的顺序不会被改写。
    if merged and leading_system:
        if leading_system[0] == merged:
            leading_system.pop(0)
        elif leading_system[0].startswith(f"{merged}\n\n"):
            remainder = leading_system[0][len(merged) + 2:]
            if remainder.strip():
                leading_system[0] = remainder
            else:
                leading_system.pop(0)

    system_parts: list[str] = []
    for part in (global_system, request_system, *leading_system, tool_system):
        if part and part not in system_parts:
            system_parts.append(part)

    image_model = is_supported_image_model(model)
    final_prompt = str(prompt or "")
    if not final_prompt.strip():
        final_prompt = prompt_text_from_messages(normalized)
    # 纯图片、无文字的请求（典型：图生图）必须给上游一个非空指令，否则等于空 prompt。
    if not final_prompt.strip() and image_model and _has_image_parts(normalized):
        final_prompt = IMAGE_ONLY_PROMPT
    # 尺寸/质量提示只对图片模型有意义：文本模型即使调用方传了 size_enabled 也保持原样。
    if size_enabled and image_model:
        final_prompt = image_hint_text(final_prompt, size, quality)

    if hints is None:
        hints = [PICTURE_V2_HINT] if image_model else []

    # 调用方未显式给图片时，从 messages 的图片分段派生，避免图生图请求丢图。
    resolved_images = list(images) if images else _images_from_messages(normalized)

    return PromptPlan(
        system="\n\n".join(system_parts),
        messages=normalized,
        prompt=final_prompt,
        hints=list(hints),
        images=resolved_images,
    )


def render_conversation_messages(plan: PromptPlan) -> list[dict[str, Any]]:
    """文本链路：渲染成上游 messages 数组，system 作为首条且只出现一次。"""
    messages: list[dict[str, Any]] = []
    if plan.system:
        messages.append({"role": "system", "content": plan.system})
    messages.extend(dict(message) for message in plan.messages)
    return messages


def render_picture_prompt(plan: PromptPlan) -> str:
    """picture_v2 链路：把 system 与已压平的 prompt 拼成单一字符串（上游只认单段文本）。"""
    return f"{plan.system}\n\n{plan.prompt}" if plan.system else plan.prompt


def render_codex_input_prompt(plan: PromptPlan) -> str:
    """codex 链路：上游 `input` 文本。

    codex 的 system 走 responses 的 `instructions`（见 `render_codex_instructions`），
    `input` 只承载调用方提示词本身，因此这里等于 `plan.prompt`。显式提供 renderer
    是为了让「上游实际收到的文本」与 `revised_prompt` 同源，而不是散落在调用点。
    """
    return plan.prompt


def render_codex_instructions(plan: PromptPlan, instructions: str = CODEX_RESPONSES_INSTRUCTIONS) -> str:
    """codex 链路：把 system 拼进 responses 的 `instructions` 字段。"""
    return f"{plan.system}\n\n{instructions}" if plan.system else instructions
