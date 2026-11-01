"""提示词事实源：一次上游请求的提示词构造与按链路渲染。

本模块是提示词组装的单一事实源：`build_prompt_plan` 在**请求路径内**构造一次
`PromptPlan`，各链路（文本 / picture_v2 / codex）只通过 renderer 做形态转换，
不再各自判断「要不要注入 global system」「要不要拼尺寸/质量文本」。

依赖纪律：只依赖 `services.config` / `services.message_image` / `utils`，
**不得** import protocol 包内其他模块（与 `message_utils.py` 的约定一致），
避免与 `event_parse` / `image_stream` 形成环。

热更新红线：`config` 是进程内单例，`global_system_prompt` 每次访问都实时读
`config.data`，管理端改配置后同一进程的下一个请求立即生效。因此本模块所有
模块级常量都必须是**静态文本**，绝不能把 config 求值进模块级常量；
`PromptPlan` 只能在请求路径内构造。

与相邻实现的边界：
- `message_utils.normalize_messages`：把请求消息规范化为上游结构（含图片分段）；
- `conversation_payload.api_messages_to_conversation_messages`：渲染 web 端 wire format。

本模块复用前者的语义，只负责「system 合并去重 + 提示词压平 + 尺寸/质量文本」这类
策略决策。阶段 1 新旧路径并存（本模块尚无调用点），阶段 2 才逐端点迁移。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.config import config
from services.message_image import extract_image_from_message_content
from utils.helper import is_supported_image_model

# 请求带不受支持的工具（非搜索类）时注入的兜底 system 文案。
# 阶段 1 下沉至此作为唯一副本；阶段 2 删除 `openai_v1_chat_complete.py`
# 与 `openai_v1_response.py` 中的逐字重复定义。
TOOL_UNAVAILABLE_SYSTEM_MESSAGE = (
    "This compatibility backend cannot execute local tools, shell commands, non-search tools, "
    "or file operations. Do not claim to have run tools or inspected external resources. "
    "If a user asks you to use a tool, say that tool execution is unavailable through this backend."
)

# codex 链路的固定英文指令。阶段 1 与 `services/backend/codex_image.py` 的常量
# 保持一致（有测试守卫），阶段 2 由本模块作为唯一来源。
CODEX_RESPONSES_INSTRUCTIONS = (
    "Use the image_generation tool to create exactly one image for the user's request. "
    "Return the generated image result."
)

# 图片模型走 ChatGPT 网页端生图通道时携带的 system hint。
PICTURE_V2_HINT = "picture_v2"


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
    - `size` / `quality`：请求级生图参数（未做 `size_enabled` 门控，供 codex 工具层等直接使用）；
    - `images`：base64 编码的输入图片。
    """

    system: str
    messages: list[dict[str, Any]]
    prompt: str
    hints: list[str]
    size: str | None
    quality: str
    images: list[str]


def _text_of(content: Any) -> str:
    """从消息 content（字符串或分段列表）中提取纯文本，忽略图片等其他分段类型。

    与 `message_utils.message_text` 语义一致（分段直接相连，不加分隔符）。
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


def _normalize_messages(messages: object) -> list[dict[str, Any]]:
    """把 OpenAI 风格的 messages 规范化为上游对话请求所需的结构（不含 system 注入）。

    处理规则与 `message_utils.normalize_messages` 的消息部分一致：user 消息中的图片
    （base64 / bytes 分段）被抽取为 `{"type": "image", ...}` 分段，与文本分段并存；
    其余消息只保留纯文本。global system 的注入改由 `build_prompt_plan` 统一决策。
    """
    normalized: list[dict[str, Any]] = []
    if not isinstance(messages, list):
        return normalized
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "user")
        content = message.get("content", "")
        text = _text_of(content)
        images: list[tuple[bytes, str]] = []
        if role == "user":
            images.extend(extract_image_from_message_content(content))
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict) or part.get("type") != "image":
                        continue
                    data = part.get("data")
                    if isinstance(data, (bytes, bytearray)) and all(existing[0] != bytes(data) for existing in images):
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


def _prompt_from_messages(messages: list[dict[str, Any]]) -> str:
    """把对话历史里的全部 user 文本压平成单一 prompt（与 `extract_chat_prompt` 的拼接规则一致）。

    用于图片模型收到空 `prompt` 时兜底，避免上游拿到空串。多轮 user 文本以 `\\n` 连接。
    """
    parts: list[str] = []
    for message in messages:
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        text = _text_of(message.get("content")).strip()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _apply_image_hints(prompt: str, size: str | None, quality: str) -> str:
    """把 size / quality 以中文提示拼进生图提示词；`quality == "auto"` 时不注入质量句。"""
    hints: list[str] = []
    if size:
        hints.append(f"输出图片尺寸为 {size}。")
    if quality and quality != "auto":
        hints.append(f"输出图片质量为 {quality}。")
    return f"{prompt.strip()}\n\n{''.join(hints)}" if hints else prompt


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
    - `prompt`：调用方原始提示词；为空时从 `messages` 的 user 文本压平派生（保证非空）；
    - `images`：base64 输入图片；
    - `size` / `quality`：生图参数；
    - `size_enabled`：接口契约里明确有 size 参数时才为 True，此时才把尺寸/质量拼进 `prompt`；
    - `hints`：显式 system hint；为 None 时图片模型默认 `["picture_v2"]`，其余为空；
    - `system`：请求级 system（字符串或 Anthropic 分段列表），与 global system 合并去重；
    - `tool_unavailable`：是否在 system 末尾追加 `TOOL_UNAVAILABLE_SYSTEM_MESSAGE`。

    system 合并顺序固定为 `[global, 请求级 system, tool_unavailable]`，重复文本只保留首次出现。
    消息列表里已有的前置 system 消息同样折进 `system`，因此对「已注入过的消息」重复调用
    本函数不会二次注入（幂等）。

    副作用：读取 `config.global_system_prompt`（实时，支持热更新）；
    派生 prompt 时可能触发 `image_url` 远程拉取（受 `allow_remote_image_fetch` 开关约束）。
    """
    global_system = config.global_system_prompt
    raw_messages = messages if isinstance(messages, list) and messages else None
    if raw_messages is None and str(prompt or "").strip():
        raw_messages = [{"role": "user", "content": prompt}]
    normalized = _normalize_messages(raw_messages)

    leading_system: list[str] = []
    while normalized and normalized[0].get("role") == "system":
        text = normalized.pop(0).get("content")
        if isinstance(text, str) and text:
            leading_system.append(text)

    system_parts: list[str] = []
    for part in (global_system, *leading_system, _text_of(system), TOOL_UNAVAILABLE_SYSTEM_MESSAGE if tool_unavailable else ""):
        if part and part not in system_parts:
            system_parts.append(part)

    final_prompt = str(prompt or "")
    if not final_prompt.strip():
        final_prompt = _prompt_from_messages(normalized)
    if size_enabled:
        final_prompt = _apply_image_hints(final_prompt, size, quality)

    if hints is None:
        hints = [PICTURE_V2_HINT] if is_supported_image_model(model) else []

    return PromptPlan(
        system="\n\n".join(system_parts),
        messages=normalized,
        prompt=final_prompt,
        hints=list(hints),
        size=size,
        quality=quality,
        images=list(images or []),
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


def render_codex_instructions(plan: PromptPlan, instructions: str = CODEX_RESPONSES_INSTRUCTIONS) -> str:
    """codex 链路：把 system 拼进 responses 的 `instructions` 字段。"""
    return f"{plan.system}\n\n{instructions}" if plan.system else instructions
