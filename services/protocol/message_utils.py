"""协议层消息与 token 工具。

承载 OpenAI 兼容协议域共享的消息规范化、图片编码与 token 计数工具，
以及图片/文本生成共用的请求模型 `ConversationRequest`。
本模块只依赖 `services.config` / `services.message_image` / `utils`，
不得反向依赖 protocol 包内其他模块。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Iterable

import tiktoken

from services.config import config
from utils.image_tokens import count_image_content_tokens
from utils.message_content import image_hint_text, message_text, normalize_message_list


def encode_images(images: Iterable[tuple[bytes, str, str]]) -> list[str]:
    """把 `(图片字节, 文件名, mime)` 元组序列编码为 base64 字符串列表，跳过空图片。"""
    return [base64.b64encode(data).decode("ascii") for data, _, _ in images if data]


def _leading_system_texts(messages: object) -> list[str]:
    """收集消息列表开头连续 system 消息的文本，用于 `normalize_messages` 的幂等判断。"""
    texts: list[str] = []
    if not isinstance(messages, list):
        return texts
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "system":
            break
        text = message_text(message.get("content"))
        if text:
            texts.append(text)
    return texts


def _already_prefixed(leading_system: list[str], text: str) -> bool:
    """判断 `text` 是否已作为首条 system 的内容或其前缀出现（幂等判断）。

    不能只做全等比较：合并后的 system 形如 `global\\n\\n请求级`，首条 system 全等于
    global 的情形之外还要覆盖「以 global 开头」的情形，否则会二次注入。
    """
    if not text:
        return False
    return any(item == text or item.startswith(f"{text}\n\n") for item in leading_system)


def normalize_messages(messages: object, system: Any = None) -> list[dict[str, Any]]:
    """把 OpenAI 风格的 messages 规范化为上游对话请求所需的结构。

    处理规则：
    - 全局 system prompt 与请求级 `system` 参数分别作为独立 system 消息前置；
    - user 消息中的图片（base64 / bytes 分段）被抽取为 `{"type": "image", ...}` 分段，
      与文本分段并存；其余消息只保留纯文本。

    幂等保护：若消息列表开头已经存在 global system（全等或以它开头），则跳过注入，
    避免把上一次本函数的输出再次送入时重复注入。
    新链路的注入决策统一由 `prompt_plan.build_prompt_plan` 承担，本函数保留给
    尚未迁移的调用点使用（阶段 3 清理）。
    """
    leading_system = _leading_system_texts(messages)
    normalized = []
    if config.global_system_prompt and not _already_prefixed(leading_system, config.global_system_prompt):
        normalized.append({"role": "system", "content": config.global_system_prompt})
    system_text = message_text(system)
    if system_text and not _already_prefixed(leading_system, system_text):
        normalized.append({"role": "system", "content": system_text})
    normalized.extend(normalize_message_list(messages))
    return normalized


def prompt_with_global_system(prompt: str) -> str:
    """给生图提示词拼接全局 system prompt（仅在配置了全局 prompt 时生效）。"""
    return f"{config.global_system_prompt}\n\n{prompt}" if config.global_system_prompt else prompt


def assistant_history_text(messages: list[dict[str, Any]]) -> str:
    """拼接规范化消息里全部 assistant 文本，用于剔除上游回放的历史回复。"""
    return "".join(str(item.get("content") or "") for item in messages if item.get("role") == "assistant")


def assistant_history_messages(messages: list[dict[str, Any]]) -> list[str]:
    """返回规范化消息里全部非空 assistant 文本列表，用于逐条比对上游历史回放。"""
    return [str(item.get("content") or "") for item in messages if item.get("role") == "assistant" and item.get("content")]


def build_image_prompt(prompt: str, size: str | None, quality: str = "auto") -> str:
    """把接口契约中的 size / quality 参数以中文提示的形式拼进生图提示词。

    `quality == "auto"` 时短路，不注入「输出图片质量为 auto。」这类无信息量的句子。
    实现见 `utils.message_content.image_hint_text`；新链路请直接用
    `prompt_plan.build_prompt_plan`，本函数保留给尚未迁移的调用点。
    """
    return image_hint_text(prompt, size, quality)


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
