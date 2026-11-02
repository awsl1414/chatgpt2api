#!/usr/bin/env python3
"""生图尺寸能力表与尺寸注入的单元测试。

覆盖点（对应工作区 `docs/size-verification.md` 的实测结论）：
- 能力表：所有已测图片模型的比例通道都有效，且 codex 不发送上游 tools[0].size；
- 提示词注入：尺寸 + 方向词，picture_v2 与 codex 一致；
- **端到端提交路径**：经端点 `handle()` 构造真实请求 → 流式链路 → 上游 payload，
  验证前端提交的 size 真的变成了提示词里的比例语句（这是本次修复的核心回归点）。
"""
from __future__ import annotations

import base64
import json
from typing import Any
from unittest import mock

import pytest

from services.backend import codex_image
from services.config import config
from services.errors import ImageGenerationError
from services.protocol import openai_v1_image_generations
from services.protocol.image_stream import stream_codex_image_outputs, stream_image_outputs
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import build_prompt_plan
from utils.image_size import (
    IMAGE_SIZE_CAPABILITIES,
    image_size_capability,
    image_size_uses_prompt,
    image_size_uses_upstream_tool_field,
    orientation_label,
    parse_size_pair,
)

PNG_B64 = base64.b64encode(b"fake-png-bytes").decode("ascii")


@pytest.fixture(autouse=True)
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


class TestCapabilityTable:
    @pytest.mark.parametrize(
        "model",
        [
            "gpt-image-2",
            "codex-gpt-image-2",
            "codex-gpt-image-2.5-flare",
            "codex-gpt-image-2.5-sunburst",
        ],
    )
    def test_prompt_size_effective_for_every_model(self, model: str) -> None:
        assert image_size_uses_prompt(model) is True

    @pytest.mark.parametrize(
        "model",
        [
            "gpt-image-2",
            "codex-gpt-image-2",
            "codex-gpt-image-2.5-flare",
            "codex-gpt-image-2.5-sunburst",
        ],
    )
    def test_no_model_accepts_upstream_tool_size(self, model: str) -> None:
        """实测：picture_v2 payload 无 size 键，codex 的 tools[0].size 被忽略。"""
        assert image_size_uses_upstream_tool_field(model) is False

    @pytest.mark.parametrize("plan_type", ["plus", "team", "pro"])
    @pytest.mark.parametrize("base", ["codex-gpt-image-2", "codex-gpt-image-2.5-flare"])
    def test_plan_prefix_keeps_capability(self, plan_type: str, base: str) -> None:
        prefixed = f"{plan_type}-{base}"
        assert image_size_uses_prompt(prefixed) is True
        assert image_size_uses_upstream_tool_field(prefixed) is False

    def test_unknown_and_text_models_have_no_capability(self) -> None:
        for model in ("auto", "gpt-5-5", "", None, "not-an-image-model"):
            assert image_size_capability(model) is None
            assert image_size_uses_prompt(model) is False
            assert image_size_uses_upstream_tool_field(model) is False

    def test_table_covers_every_base_image_model(self) -> None:
        """能力表必须覆盖 `utils.helper.BASE_IMAGE_MODELS` 的每一个模型。"""
        from utils.helper import BASE_IMAGE_MODELS

        assert set(IMAGE_SIZE_CAPABILITIES) == set(BASE_IMAGE_MODELS)


class TestParseSizePair:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1792x1024", (1792, 1024)),
            ("1024X1536", (1024, 1536)),
            ("1024×1536", (1024, 1536)),
            ("1024 x 1536", (1024, 1536)),
        ],
    )
    def test_parses_common_forms(self, value: str, expected: tuple[int, int]) -> None:
        assert parse_size_pair(value) == expected

    @pytest.mark.parametrize("value", [None, "", "auto", "1024", "0x1024", "abc"])
    def test_returns_none_for_unparseable(self, value: object) -> None:
        assert parse_size_pair(value) is None

    def test_orientation_label(self) -> None:
        assert orientation_label(1792, 1024) == "横版"
        assert orientation_label(1024, 1792) == "竖版"
        assert orientation_label(1024, 1024) == "方形"


class TestPromptInjection:
    @pytest.mark.parametrize(
        "model",
        [
            "gpt-image-2",
            "codex-gpt-image-2",
            "codex-gpt-image-2.5-flare",
            "codex-gpt-image-2.5-sunburst",
        ],
    )
    def test_all_models_carry_orientation_in_prompt(self, model: str) -> None:
        """所有模型的提示词都带尺寸 + 方向——比例是唯一被证实的通道。"""
        plan = build_prompt_plan(
            model=model,
            prompt="画一只猫",
            size="1024x1792",
            quality="auto",
            size_enabled=True,
        )
        assert plan.prompt == "画一只猫\n\n输出图片尺寸为 1024x1792，竖版。"

    def test_2k_and_4k_tiers_still_carry_ratio(self) -> None:
        """2K/4K 档位提交的像素值同样转成比例语句（比例有效、像素不兑现）。"""
        plan_2k = build_prompt_plan(
            model="codex-gpt-image-2", prompt="画一只猫", size="2560x1440", size_enabled=True
        )
        assert "2560x1440，横版" in plan_2k.prompt

        plan_4k = build_prompt_plan(
            model="gpt-image-2", prompt="画一只猫", size="2160x3840", size_enabled=True
        )
        assert "2160x3840，竖版" in plan_4k.prompt

    def test_prompt_without_parseable_size_keeps_plain_size_text(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2",
            prompt="画一只猫",
            size="auto",
            quality="auto",
            size_enabled=True,
        )
        assert plan.prompt == "画一只猫\n\n输出图片尺寸为 auto。"

    def test_size_enabled_false_keeps_prompt(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2",
            prompt="画一只猫",
            size="1024x1792",
            quality="high",
            size_enabled=False,
        )
        assert plan.prompt == "画一只猫"


# --------------------------------------------------------------------------- #
# 端到端提交路径：端点 handle() → 流式链路 → 上游实际收到的文本
# --------------------------------------------------------------------------- #

def _capture_generations_request(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> ConversationRequest:
    """经真实端点 `handle()` 构造请求，在 pool 边界捕获 ConversationRequest。"""
    captured: dict[str, ConversationRequest] = {}

    def fake_pool(request: ConversationRequest):
        captured["request"] = request
        return iter([])

    monkeypatch.setattr(openai_v1_image_generations, "stream_image_outputs_with_pool", fake_pool)
    openai_v1_image_generations.handle(body)
    return captured["request"]


def _codex_upstream_payload(request: ConversationRequest) -> dict[str, Any]:
    """驱动 codex 流式链路，返回真正发往上游的 payload。"""
    captured: dict[str, Any] = {}

    def fake_urlopen(url_request: Any, timeout: float | None = None) -> mock.MagicMock:
        captured["payload"] = json.loads(url_request.data.decode())
        return mock.MagicMock()

    class _CodexApi:
        access_token = "token"
        account = {"source_type": "codex"}
        base_url = "https://upstream.test"

        def iter_codex_image_response_events(self, **kwargs: Any):
            yield from codex_image.iter_codex_image_response_events(self, **kwargs)

    with mock.patch.object(codex_image.urllib.request, "urlopen", fake_urlopen), mock.patch.object(
        codex_image, "iter_codex_response_events", lambda _raw: iter([])
    ):
        with pytest.raises(ImageGenerationError):
            list(stream_codex_image_outputs(_CodexApi(), request))
    return captured["payload"]


class TestEndToEndSubmitPath:
    """回归：前端提交的 size 必须真的变成上游提示词里的比例语句。

    修复前 `resolveRequestSize` 对 codex 返回 undefined → size 为空 →
    `image_hint_text` 的 `if size:` 不成立 → 零注入，用户彻底失去比例控制。
    这里从端点入口构造请求，覆盖整条真实路径。
    """

    @pytest.mark.parametrize(
        ("size", "expected_fragment"),
        [
            ("1920x1088", "输出图片尺寸为 1920x1088，横版。"),
            ("1088x1920", "输出图片尺寸为 1088x1920，竖版。"),
            ("1024x1024", "输出图片尺寸为 1024x1024，方形。"),
            ("3840x2160", "输出图片尺寸为 3840x2160，横版。"),
        ],
    )
    def test_codex_upstream_prompt_carries_ratio(
        self, monkeypatch: pytest.MonkeyPatch, size: str, expected_fragment: str
    ) -> None:
        request = _capture_generations_request(
            monkeypatch,
            {"prompt": "画一只猫", "model": "codex-gpt-image-2", "size": size},
        )
        payload = _codex_upstream_payload(request)

        upstream_text = payload["input"][0]["content"][0]["text"]
        assert expected_fragment in upstream_text
        # codex 上游工具层不再收到 size 字段（收到也会被忽略）
        assert "size" not in payload["tools"][0]

    def test_picture_v2_upstream_prompt_carries_ratio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        request = _capture_generations_request(
            monkeypatch,
            {"prompt": "画一只猫", "model": "gpt-image-2", "size": "1920x1088"},
        )
        captured: dict[str, Any] = {}

        backend = mock.MagicMock()
        backend.stream_conversation.side_effect = lambda **kwargs: captured.update(kwargs) or iter([])
        monkeypatch.setattr(
            "services.protocol.image_stream._get_detailed_error_from_tasks", lambda *a, **k: ""
        )
        list(stream_image_outputs(backend, request))

        # conversation_events 把 plan 渲染成 picture_v2 的单段 prompt 后才发上游
        assert "输出图片尺寸为 1920x1088，横版。" in captured["prompt"]

    def test_empty_size_yields_no_ratio_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """没有 size 时确实无从注入——这是前端必须提交 size 的原因。

        前端 `resolveRequestSize` 对**所有模型**都返回非空字符串
        （见 `web/src/lib/image-composer-options.test.ts`），因此真实路径不会走到这里；
        本用例把这条隐式契约显式钉住，防止再次出现「前端不传 → 后端零注入」的回退。
        """
        request = _capture_generations_request(
            monkeypatch,
            {"prompt": "画一只猫", "model": "codex-gpt-image-2"},
        )
        payload = _codex_upstream_payload(request)
        assert payload["input"][0]["content"][0]["text"] == "画一只猫"

    def test_frontend_default_size_from_composer_round_trip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """完整链路：前端默认 W/H（1024×1024）→ size → 后端 → 上游提示词。

        前端 `resolveRequestSize(model, "", "")` 的回退值即 `1024x1024`
        （对应 image-composer-options.test.ts 的断言），这里验证它确实被注入。
        """
        request = _capture_generations_request(
            monkeypatch,
            {"prompt": "画一只猫", "model": "codex-gpt-image-2", "size": "1024x1024"},
        )
        payload = _codex_upstream_payload(request)
        assert "输出图片尺寸为 1024x1024，方形。" in payload["input"][0]["content"][0]["text"]
