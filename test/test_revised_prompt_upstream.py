#!/usr/bin/env python3
"""revised_prompt 与上游实际文本同源的回归测试（P0-1）。

验收点：`revised_prompt` 必须等于该链路**真正发往上游**的文本，而不是端点
是否有单独写一个字段。

- picture_v2：上游 prompt = `render_picture_prompt(plan)`（global + 尺寸/质量 + 提示词）；
- codex：上游 `input` = `render_codex_input_prompt(plan)`（即 `plan.prompt`），
  global 走 `instructions`。

代码链路走真实端点 `handle()`（真实 `build_prompt_plan`），仅在
`stream_image_outputs_with_pool` 边界捕获 `ConversationRequest`。
"""
from __future__ import annotations

import base64
from typing import Any
from unittest import mock

import pytest

from services.backend import codex_image
from services.config import config
from services.protocol import openai_v1_image_generations
from services.protocol.image_stream import stream_codex_image_outputs
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import (
    render_codex_input_prompt,
    render_codex_instructions,
    render_picture_prompt,
)

PNG_B64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
GLOBAL_SYS = "GLOBAL_SYS"


@pytest.fixture
def global_prompt(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": GLOBAL_SYS})
    return GLOBAL_SYS


@pytest.fixture(autouse=True)
def _fake_saver(monkeypatch: pytest.MonkeyPatch) -> None:
    """生图结果落盘替换为纯函数，避免写真实文件。"""
    import services.protocol.image_stream as image_stream_module

    monkeypatch.setattr(
        image_stream_module,
        "_image_saver",
        lambda image_data, base_url=None: "saved://test",
        raising=False,
    )


def _capture_generations_request(
    monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]
) -> ConversationRequest:
    """经真实端点 `handle()` 构造请求，在 pool 边界捕获 ConversationRequest。"""
    captured: dict[str, ConversationRequest] = {}

    def fake_pool(request: ConversationRequest):
        captured["request"] = request
        return iter([])

    monkeypatch.setattr(openai_v1_image_generations, "stream_image_outputs_with_pool", fake_pool)
    openai_v1_image_generations.handle(body)
    return captured["request"]


def test_generations_picture_upstream_text_equals_revised_prompt(
    global_prompt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """picture_v2：端点发送的 prompt 与 revised_prompt 同源（含 global 与尺寸/质量）。"""
    request = _capture_generations_request(
        monkeypatch,
        {"prompt": "a cat", "model": "gpt-image-2", "size": "1792x1024", "quality": "high"},
    )

    expected = f"{GLOBAL_SYS}\n\na cat\n\n输出图片尺寸为 1792x1024。输出图片质量为 high。"
    assert request.plan is not None
    assert render_picture_prompt(request.plan) == expected
    # 端点不再保存第二份「实际上游文本」，事实源只在 plan
    assert not hasattr(request, "final_prompt")


def test_generations_codex_upstream_input_equals_revised_prompt(
    global_prompt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codex：真实端点构造的请求，上游 input 与 revised_prompt 全等且不含 global。

    这里复用真实 `codex_image.iter_codex_image_response_events`，只替换底层
    urlopen，从而同时断言「发往上游的 payload」与「对外 revised_prompt」。
    """
    request = _capture_generations_request(
        monkeypatch,
        {"prompt": "a cat", "model": "codex-gpt-image-2", "size": "1792x1024", "quality": "high"},
    )

    captured: dict[str, Any] = {}

    def fake_urlopen(url_request: Any, timeout: float | None = None) -> Any:
        import json

        captured["payload"] = json.loads(url_request.data.decode())
        return mock.MagicMock()

    class _CodexApi:
        access_token = "token"
        account = {"source_type": "codex"}
        base_url = "https://upstream.test"

        def iter_codex_image_response_events(self, **kwargs: Any):
            yield from codex_image.iter_codex_image_response_events(self, **kwargs)

    monkeypatch.setattr(codex_image.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(codex_image, "iter_codex_response_events", lambda _raw: iter([
        {"type": "image_generation_call", "result": PNG_B64},
    ]))

    outputs = list(stream_codex_image_outputs(_CodexApi(), request))

    upstream_input = captured["payload"]["input"][0]["content"][0]["text"]
    assert upstream_input == render_codex_input_prompt(request.plan)
    assert upstream_input.startswith("a cat")
    assert "输出图片尺寸为 1792x1024，横版。" in upstream_input
    # codex 工具层忽略 size，payload 里不应再出现该字段
    assert "size" not in captured["payload"]["tools"][0]
    assert captured["payload"]["instructions"] == render_codex_instructions(request.plan)
    assert captured["payload"]["instructions"].startswith(GLOBAL_SYS)
    assert outputs[0].data[0]["revised_prompt"] == upstream_input
    assert GLOBAL_SYS not in outputs[0].data[0]["revised_prompt"]
