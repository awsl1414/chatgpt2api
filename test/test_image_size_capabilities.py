#!/usr/bin/env python3
"""生图尺寸能力表与尺寸文本注入的单元测试。

覆盖点（对应工作区 `docs/size-verification.md` 的实测结论）：
- 能力表按模型给出「接口 size 是否生效」「提示词尺寸是否生效」；
- plus-/team-/pro- 前缀与基础模型能力一致；
- codex 系列提示词注入带方向（横版/竖版/方形），picture_v2 保持原措辞；
- codex 上游 payload 不含 `size` 字段；
- 非图片模型不注入任何尺寸文本。
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
from services.protocol.image_stream import stream_codex_image_outputs
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import build_prompt_plan
from utils.image_size import (
    IMAGE_SIZE_CAPABILITIES,
    image_size_capability,
    image_size_uses_api_field,
    image_size_uses_prompt,
    orientation_label,
    parse_size_pair,
)

PNG_B64 = base64.b64encode(b"fake-png-bytes").decode("ascii")


@pytest.fixture(autouse=True)
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


class TestCapabilityTable:
    def test_picture_v2_uses_api_size(self) -> None:
        assert image_size_uses_api_field("gpt-image-2") is True
        assert image_size_uses_prompt("gpt-image-2") is True

    @pytest.mark.parametrize(
        "model",
        [
            "codex-gpt-image-2",
            "codex-gpt-image-2.5-flare",
            "codex-gpt-image-2.5-sunburst",
        ],
    )
    def test_codex_ignores_api_size_but_honors_prompt(self, model: str) -> None:
        assert image_size_uses_api_field(model) is False
        assert image_size_uses_prompt(model) is True

    @pytest.mark.parametrize("plan_type", ["plus", "team", "pro"])
    @pytest.mark.parametrize("base", ["codex-gpt-image-2", "codex-gpt-image-2.5-flare"])
    def test_plan_prefix_keeps_capability(self, plan_type: str, base: str) -> None:
        prefixed = f"{plan_type}-{base}"
        assert image_size_uses_api_field(prefixed) is False
        assert image_size_uses_prompt(prefixed) is True

    def test_unknown_and_text_models_have_no_capability(self) -> None:
        for model in ("auto", "gpt-5-5", "", None, "not-an-image-model"):
            assert image_size_capability(model) is None
            assert image_size_uses_api_field(model) is False
            assert image_size_uses_prompt(model) is False

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
    def test_codex_prompt_carries_orientation(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2",
            prompt="画一只猫",
            size="1024x1792",
            quality="auto",
            size_enabled=True,
        )
        assert plan.prompt == "画一只猫\n\n输出图片尺寸为 1024x1792，竖版。"

    def test_picture_v2_prompt_keeps_original_wording(self) -> None:
        """picture_v2 的接口 size 本身生效，提示词措辞保持不变（行为零变化）。"""
        plan = build_prompt_plan(
            model="gpt-image-2",
            prompt="画一只猫",
            size="1024x1792",
            quality="auto",
            size_enabled=True,
        )
        assert plan.prompt == "画一只猫\n\n输出图片尺寸为 1024x1792。"

    def test_codex_prompt_without_parseable_size_stays_plain(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2",
            prompt="画一只猫",
            size="auto",
            quality="auto",
            size_enabled=True,
        )
        assert plan.prompt == "画一只猫\n\n输出图片尺寸为 auto。"

    def test_codex_size_enabled_false_keeps_prompt(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2",
            prompt="画一只猫",
            size="1024x1792",
            quality="high",
            size_enabled=False,
        )
        assert plan.prompt == "画一只猫"


def _run_codex_stream(payload_body: dict[str, Any]) -> dict[str, Any]:
    """驱动 codex 生图流并返回真正发往上游的 payload。"""
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float | None = None) -> mock.MagicMock:
        captured["payload"] = json.loads(request.data.decode())
        return mock.MagicMock()

    with mock.patch.object(codex_image.urllib.request, "urlopen", fake_urlopen), mock.patch.object(
        codex_image, "iter_codex_response_events", lambda _raw: iter([])
    ):
        class _CodexApi:
            access_token = "token"
            account = {"source_type": "codex"}
            base_url = "https://upstream.test"

            def iter_codex_image_response_events(self, **kwargs: Any):
                yield from codex_image.iter_codex_image_response_events(self, **kwargs)

        request = ConversationRequest(**payload_body)
        with pytest.raises(ImageGenerationError):
            list(stream_codex_image_outputs(_CodexApi(), request))
    return captured["payload"]


class TestCodexUpstreamPayload:
    def test_codex_payload_omits_size(self) -> None:
        plan = build_prompt_plan(
            model="codex-gpt-image-2", prompt="a cat", size="1792x1024", size_enabled=True
        )
        payload = _run_codex_stream(
            {"model": "codex-gpt-image-2", "prompt": "a cat", "size": "1792x1024", "plan": plan}
        )
        tool = payload["tools"][0]
        assert "size" not in tool
        assert tool["model"] == "gpt-image-2"
        assert tool["quality"] == "auto"
        assert payload["input"][0]["content"][0]["text"] == "a cat\n\n输出图片尺寸为 1792x1024，横版。"
