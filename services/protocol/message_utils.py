"""协议层消息与 token 工具。

承载 OpenAI 兼容协议域共享的图片编码、assistant 历史提取与 token 计数工具，
以及图片/文本生成共用的请求模型 `ConversationRequest`。
提示词组装的策略决策（system 合并、尺寸/质量文本注入）统一在
`services.protocol.prompt_plan` 中完成，本模块不再提供。
本模块只依赖 `services.message_image` / `services.protocol.message_content` / `utils`，
不得反向依赖 protocol 包内其他模块（`prompt_plan` 仅在 `TYPE_CHECKING` 下引入类型）。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

import tiktoken

from services.protocol.message_content import message_text
from utils.image_tokens import count_image_content_tokens

if TYPE_CHECKING:
    from services.protocol.prompt_plan import PromptPlan


def encode_images(images: Iterable[tuple[bytes, str, str]]) -> list[str]:
    """把 `(图片字节, 文件名, mime)` 元组序列编码为 base64 字符串列表，跳过空图片。"""
    return [base64.b64encode(data).decode("ascii") for data, _, _ in images if data]


def assistant_history_text(messages: list[dict[str, Any]]) -> str:
    """拼接规范化消息里全部 assistant 文本，用于剔除上游回放的历史回复。"""
    return "".join(str(item.get("content") or "") for item in messages if item.get("role") == "assistant")


def assistant_history_messages(messages: list[dict[str, Any]]) -> list[str]:
    """返回规范化消息里全部非空 assistant 文本列表，用于逐条比对上游历史回放。"""
    return [str(item.get("content") or "") for item in messages if item.get("role") == "assistant" and item.get("content")]


def encoding_for_model(model: str) -> tiktoken.Encoding:
    """返回模型对应的 tiktoken 编码，未知模型回退到 o200k_base / cl100k_base。"""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            return tiktoken.get_encoding("o200k_base")
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")


def count_message_image_tokens(messages: list[dict[str, Any]], model: str) -> int:
    """统计消息列表中图片内容占用的 token 数。"""
    return sum(count_image_content_tokens(message.get("content"), model) for message in messages)


def count_message_text_tokens(messages: list[dict[str, Any]], model: str) -> int:
    """按 OpenAI 计数惯例（每条消息 +3、name 字段 +1、末尾 +3）统计文本 token 数。"""
    encoding = encoding_for_model(model)
    total = 0
    for message in messages:
        total += 3
        for key, value in message.items():
            if key == "content" and isinstance(value, list):
                total += len(encoding.encode(message_text(value)))
            elif isinstance(value, str):
                total += len(encoding.encode(value))
            else:
                continue
            if key == "name":
                total += 1
    return total + 3


def count_message_tokens(messages: list[dict[str, Any]], model: str) -> int:
    """统计消息列表的总 token 数（文本 + 图片）。"""
    return count_message_text_tokens(messages, model) + count_message_image_tokens(messages, model)


def count_text_tokens(text: str, model: str) -> int:
    """统计单段文本的 token 数。"""
    return len(encoding_for_model(model).encode(text))


@dataclass
class ConversationRequest:
    """图片/文本生成协议层的统一请求模型。

    由 `api/` 各端点构造，贯穿 `protocol/` 内的文本流与生图流编排。
    提示词与图片输入的**唯一事实源**是 `plan`：端点在请求路径内构造一次，
    下游只渲染，不再按字段各自拼装。
    """

    model: str = "auto"
    # 调用方原始提示词：图片链路用于会话恢复检索（`_recover_conversation_id`）
    # 与 codex 链路的 `input`，不承载任何注入结果。
    prompt: str = ""
    messages: list[dict[str, Any]] | None = None
    thinking_effort: str = ""
    n: int = 1
    size: str | None = None
    quality: str = "auto"
    # 接口契约里明确有 size 参数时才为 True，此时才把尺寸/质量拼进提示词；
    # 没有 size 参数的接口（如 /v1/chat/completions）保持提示词原样
    size_enabled: bool = False
    response_format: str = "b64_json"
    base_url: str | None = None
    message_as_error: bool = False
    progress_callback: Any = None  # Callable[[str], None] | None
    # 提示词与图片输入的事实源；端点必须显式传入，未传时由下游就地构造
    # （`_request_plan`），二者共用同一个 `build_prompt_plan`。
    plan: PromptPlan | None = None
