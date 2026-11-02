#!/usr/bin/env python3
"""阶段 2 端点迁移的缺陷回归测试。

用 mock 驱动端点 `handle()`，断言最终传给上游的 `prompt` / `messages` /
`instructions`，固化三个高危缺陷已修复：

1. **重复注入**：文本链路配置 global system 后，上游 messages 中只出现 1 次；
2. **codex 静默失效**：`codex-*` 模型把 global system 拼进 `instructions`。

`/v1/messages` 对图片模型的 400 契约见 `test_v1_messages_image_contract.py`。

手法沿用 `test_image_size_gating.py` 的 `_captured_prompt` 模式：替换 backend
并捕获 `stream_conversation` 的 kwargs。
"""
from __future__ import annotations

import json
from typing import Any
from unittest import mock

import pytest

from services.backend import codex_image
from services.account_service import account_service
from services.config import config
from services.errors import ImageGenerationError
from services.protocol import anthropic_v1_messages, openai_v1_chat_complete, openai_v1_response
from services.protocol import image_stream as image_stream_module
from services.protocol.image_stream import stream_codex_image_outputs
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import build_prompt_plan, render_picture_prompt

GLOBAL_PROMPT = "GLOBAL"


@pytest.fixture
def global_prompt(monkeypatch: pytest.MonkeyPatch) -> str:
    """注入 global_system_prompt，测试结束由 monkeypatch 还原。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": GLOBAL_PROMPT})
    return GLOBAL_PROMPT


@pytest.fixture
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """清空 global_system_prompt。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


class _CapturedBackend:
    """替换 `OpenAIBackendAPI`：记录 `stream_conversation` 收到的上游参数。"""

    def __init__(self) -> None:
        self.captured: dict[str, Any] = {}
        self.access_token = "test-token"

    def stream_conversation(self, **kwargs: Any):
        self.captured.update(kwargs)
        return iter([])

    def close(self) -> None:
        """`stream_text_deltas` 在 finally 里关闭 backend。"""


def _patch_text_backend(monkeypatch: pytest.MonkeyPatch, module: Any) -> _CapturedBackend:
    """把文本链路的上游 backend 替换为假实现，并捕获 `stream_conversation` 参数。

    三处都要替换：`openai_v1_chat_complete`（`stream_text_deltas` 会重新构造
    `OpenAIBackendAPI`）、端点模块自身的构造点（`/v1/messages` 自己取号建 client）、
    以及 `/v1/responses` 的 `text_backend`。`account_service` 是进程内单例，
    patch 一次对所有模块生效。
    """
    backend = _CapturedBackend()
    monkeypatch.setattr(account_service, "get_text_access_token", lambda **_kwargs: backend.access_token)
    monkeypatch.setattr(account_service, "mark_text_used", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(openai_v1_chat_complete, "OpenAIBackendAPI", lambda **_kwargs: backend)
    monkeypatch.setattr(anthropic_v1_messages, "OpenAIBackendAPI", lambda **_kwargs: backend)
    if hasattr(module, "OpenAIBackendAPI"):
        monkeypatch.setattr(module, "OpenAIBackendAPI", lambda **_kwargs: backend)
    if hasattr(module, "text_backend"):
        monkeypatch.setattr(module, "text_backend", lambda _model="auto": backend)
    return backend


# --------------------------------------------------------------------------- #
# 文本链路不回显图片 hint（图片模型请求已由 /v1/messages 入口 400 拒绝）
# --------------------------------------------------------------------------- #

def test_anthropic_text_model_keeps_user_prompt(no_global_prompt: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """文本模型不注入 picture_v2。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_chat_complete)

    anthropic_v1_messages.handle({
        "model": "gpt-5-5",
        "messages": [{"role": "user", "content": "你好"}],
    })

    assert backend.captured["system_hints"] is None
    assert backend.captured["messages"][-1] == {"role": "user", "content": "你好"}


def test_responses_image_model_without_tool_derives_prompt(
    no_global_prompt: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """图片模型但没带 image_generation 工具 → 走文本分支，picture_v2 仍拿到非空 prompt。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_response)

    openai_v1_response.handle({"model": "gpt-image-2", "input": "画一只猫"})

    assert backend.captured["system_hints"] == ["picture_v2"]
    assert backend.captured["prompt"] == "画一只猫"


def test_responses_text_model_keeps_user_prompt(no_global_prompt: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """文本模型不注入 picture_v2。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_response)

    openai_v1_response.handle({"model": "gpt-5-5", "input": "你好"})

    assert backend.captured["system_hints"] is None
    assert backend.captured["messages"][-1] == {"role": "user", "content": "你好"}


# --------------------------------------------------------------------------- #
# 缺陷 2：文本链路 global system 只注入一次
# --------------------------------------------------------------------------- #

def test_chat_completions_injects_global_once(global_prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """端点层与事件层各调一次 normalize_messages 的历史缺陷已消除。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_chat_complete)

    openai_v1_chat_complete.handle({
        "model": "gpt-5-5",
        "messages": [{"role": "user", "content": "你好"}],
    })

    messages = backend.captured["messages"]
    system_messages = [message for message in messages if message["role"] == "system"]
    assert system_messages == [{"role": "system", "content": GLOBAL_PROMPT}]
    assert sum(str(message.get("content") or "").count(GLOBAL_PROMPT) for message in messages) == 1


def test_responses_injects_global_once_and_merges_instructions(
    global_prompt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`instructions` 作为请求级 system 与 global 合并为同一条 system 消息。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_response)

    openai_v1_response.handle({
        "model": "gpt-5-5",
        "input": "你好",
        "instructions": "请求级指令",
    })

    messages = backend.captured["messages"]
    system_messages = [message for message in messages if message["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"] == f"{GLOBAL_PROMPT}\n\n请求级指令"


def test_anthropic_injects_global_once(global_prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Anthropic 请求级 system 与 global 合并，且只出现一次。"""
    backend = _patch_text_backend(monkeypatch, openai_v1_chat_complete)

    anthropic_v1_messages.handle({
        "model": "gpt-5-5",
        "system": "请求级系统提示",
        "messages": [{"role": "user", "content": "你好"}],
    })

    messages = backend.captured["messages"]
    system_messages = [message for message in messages if message["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"] == f"{GLOBAL_PROMPT}\n\n请求级系统提示"


def test_unsupported_tool_message_sits_at_system_tail(global_prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """不支持的本地工具兜底文案位于合并 system 的末尾（global 在前）。

    旧实现把它 insert(0) 放在首位；合并后固定顺序为
    `[global, 请求级 system, tool_unavailable]`，这里守卫该顺序不再被调换。
    """
    backend = _patch_text_backend(monkeypatch, openai_v1_chat_complete)

    openai_v1_chat_complete.handle({
        "model": "gpt-5-5",
        "messages": [{"role": "user", "content": "run echo hi"}],
        "tools": [{"type": "function", "name": "shell"}],
    })

    system_messages = [m for m in backend.captured["messages"] if m["role"] == "system"]
    assert len(system_messages) == 1
    content = system_messages[0]["content"]
    assert content.startswith(GLOBAL_PROMPT)
    assert content.endswith("tool execution is unavailable through this backend.")


def test_repeated_rendering_does_not_accumulate_global(global_prompt: str) -> None:
    """把已渲染的 messages 再次送入端点（模拟调用方回放），global 仍然只有 1 份。"""
    body = {"model": "gpt-5-5", "messages": [{"role": "user", "content": "你好"}]}

    _model, first_messages = openai_v1_chat_complete.text_chat_parts(body)
    _model, second_messages = openai_v1_chat_complete.text_chat_parts({**body, "messages": first_messages})

    assert [message for message in second_messages if message["role"] == "system"] == [
        {"role": "system", "content": GLOBAL_PROMPT}
    ]
    assert second_messages == first_messages


def test_adjacent_duplicate_dedupe_runs_after_flattening(no_global_prompt: None) -> None:
    """字符串与分段两种 content 语义相同，仍按相邻重复去重（旧顺序保持）。

    裁剪必须作用在已拍平的消息上；否则两者签名不同，`drop_adjacent_duplicates` 失效。
    """
    _model, messages = openai_v1_chat_complete.text_chat_parts({
        "model": "gpt-5-5",
        "messages": [
            {"role": "user", "content": "继续"},
            {"role": "user", "content": [{"type": "text", "text": "继续"}]},
        ],
    })

    assert messages == [{"role": "user", "content": "继续"}]


def test_recover_conversation_id_uses_raw_prompt(global_prompt: str) -> None:
    """硬约束：会话恢复检索必须用调用方原始 prompt，而非带 global 前缀的最终 prompt。

    `_recover_conversation_id` 按 `common / len(prompt_words)` 打分，global 前缀会
    稀释分母、降低命中率，因此这里守卫「传进去的是原始 prompt」。
    """
    backend = mock.MagicMock()
    backend.find_conversation_by_prompt.return_value = ""

    plan = build_prompt_plan(model="gpt-image-2", prompt="画一只猫", size="1024x1024", size_enabled=True)
    # plan.prompt 才是实际发往上游的文本（含 global 与尺寸句），两者必须不同
    assert plan.prompt != "画一只猫"

    image_stream_module._recover_conversation_id(
        backend,
        "画一只猫",
        recovered_event="r",
        failed_event="f",
    )

    backend.find_conversation_by_prompt.assert_called_once()
    assert backend.find_conversation_by_prompt.call_args[0][0] == "画一只猫"


def test_generations_revised_prompt_contains_hints_and_global(
    global_prompt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """端到端：`/v1/images/generations` 的 revised_prompt 含尺寸句与 global。

    第四缺陷的验收点——调用方能看到真正发给上游的内容，而不是未改写的原始输入。
    """
    from services.protocol import openai_v1_image_generations

    captured: dict[str, Any] = {}

    def fake_pool(request: ConversationRequest):
        captured["request"] = request
        return iter([])

    monkeypatch.setattr(openai_v1_image_generations, "stream_image_outputs_with_pool", fake_pool)
    openai_v1_image_generations.handle({
        "prompt": "画一只猫",
        "model": "gpt-image-2",
        "size": "1792x1024",
        "quality": "high",
    })

    request = captured["request"]
    assert request.prompt == "画一只猫"
    # 实际上游文本由链路渲染器决定：picture_v2 用 render_picture_prompt(plan)
    upstream = render_picture_prompt(request.plan)
    assert upstream.startswith(f"{global_prompt}\n\n")
    assert "输出图片尺寸为 1792x1024。" in upstream
    assert "输出图片质量为 high。" in upstream
    # 端点不再单独保存一份「实际上游文本」，事实源唯一
    assert not hasattr(request, "final_prompt")


def test_chat_global_prompt_read_at_request_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """热更新红线：同一进程内改 `config.data`，下一个文本请求立即生效。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第一次"})
    _model, first = openai_v1_chat_complete.text_chat_parts(
        {"model": "gpt-5-5", "messages": [{"role": "user", "content": "你好"}]}
    )

    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第二次"})
    _model, second = openai_v1_chat_complete.text_chat_parts(
        {"model": "gpt-5-5", "messages": [{"role": "user", "content": "你好"}]}
    )

    assert first[0]["content"] == "第一次"
    assert second[0]["content"] == "第二次"


# --------------------------------------------------------------------------- #
# 缺陷 3：codex 模型把 global system 拼进 instructions
# --------------------------------------------------------------------------- #

def _run_codex_stream(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """驱动 codex 生图流并捕获上游 payload（无图片结果，故以异常收尾）。

    `stream_codex_image_outputs` 只依赖 backend 的
    `iter_codex_image_response_events`；这里把它绑定到真实的
    `codex_image.iter_codex_image_response_events`，只替换底层 urlopen，
    从而捕获真正发往上游的 `instructions`。
    """
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float | None = None) -> mock.MagicMock:
        captured["payload"] = json.loads(request.data.decode())
        return mock.MagicMock()

    monkeypatch.setattr(codex_image.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(codex_image, "iter_codex_response_events", lambda _raw: iter([]))

    class _CodexApi:
        """绑定真实 codex 生图实现的最小 backend 假体。"""

        access_token = "token"
        account = {"source_type": "codex"}
        base_url = "https://upstream.test"

        def iter_codex_image_response_events(self, **kwargs: Any):
            yield from codex_image.iter_codex_image_response_events(self, **kwargs)

    request = ConversationRequest(model="codex-gpt-image-2", prompt="画一只猫")
    with pytest.raises(ImageGenerationError):
        list(stream_codex_image_outputs(_CodexApi(), request))
    return captured["payload"]


def test_codex_instructions_include_global(global_prompt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """配置 global 后，codex 请求的 `instructions` 含 global 且保留固定英文指令。"""
    payload = _run_codex_stream(monkeypatch)

    assert payload["instructions"].startswith(GLOBAL_PROMPT)
    assert "Use the image_generation tool" in payload["instructions"]


def test_codex_instructions_without_global_use_constant(no_global_prompt: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置 global 时保持原常量，行为不变。"""
    payload = _run_codex_stream(monkeypatch)

    assert payload["instructions"] == codex_image.CODEX_RESPONSES_INSTRUCTIONS


def test_codex_instructions_read_at_request_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """热更新红线：改配置后下一个请求立即生效，不在 import 期求值。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第一次"})
    assert _run_codex_stream(monkeypatch)["instructions"].startswith("第一次")

    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第二次"})
    assert _run_codex_stream(monkeypatch)["instructions"].startswith("第二次")
