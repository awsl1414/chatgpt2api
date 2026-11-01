"""协议层消息与 token 工具。

承载 OpenAI 兼容协议域共享的图片编码、assistant 历史提取与 token 计数工具，
以及图片/文本生成共用的请求模型 `ConversationRequest`。
提示词组装的策略决策（system 合并、尺寸/质量文本注入）统一在
`services.protocol.prompt_plan` 中完成，本模块不再提供。
本模块只依赖 `services.message_image` / `utils`，不得反向依赖 protocol 包内其他模块。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Iterable

import tiktoken

from utils.image_tokens import count_image_content_tokens
from utils.message_content import message_text


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
    """

    model: str = "auto"
    prompt: str = ""
    # 实际发往上游的文本（已拼入 global system 与尺寸/质量提示），由端点从
    # `plan.prompt` 写入。`revised_prompt` 用它反映真实发送内容；会话恢复检索
    # （`_recover_conversation_id`）仍用原始 `prompt`，避免 global 前缀稀释关键词匹配。
    final_prompt: str = ""
    messages: list[dict[str, Any]] | None = None
    thinking_effort: str = ""
    images: list[str] | None = None
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
    # 端点在请求路径内构造好的提示词事实源；下游直接渲染，不再重复拼装，
    # 避免尺寸/质量提示被二次注入。为 None 时下游按字段自行构造（幂等）。
    # 类型为 `services.protocol.prompt_plan.PromptPlan`；此处用字符串注解是为了
    # 不引入运行时循环导入（`prompt_plan` 不依赖本模块，方向单向）。
    plan: "Any" = None

    def __post_init__(self) -> None:
        """端点只传 `plan` 时，把 `plan.prompt` 回填为 `final_prompt` 的兜底值。

        图片链路的实际上游文本是 `render_picture_prompt(plan)`（含 global），
        由端点显式写入 `final_prompt`；这里只做「未显式写入时不至于为空」的兜底，
        避免在 `message_utils` 复制 renderer 的拼接逻辑（依赖纪律不允许）。
        """
        if not self.final_prompt and self.plan is not None:
            self.final_prompt = str(getattr(self.plan, "prompt", "") or "")
