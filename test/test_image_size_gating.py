#!/usr/bin/env python3
"""图片尺寸/质量提示注入的门控测试。

契约里明确有 size 参数的接口（/v1/images/*、/v1/responses 图片工具）才把
尺寸/质量拼进提示词；没有 size 参数的接口（/v1/chat/completions）保持提示词原样。
"""
from __future__ import annotations

import unittest
from unittest import mock

from services.protocol import (
    openai_v1_chat_complete,
    openai_v1_image_edit,
    openai_v1_image_generations,
    openai_v1_response,
)
from services.protocol.event_parse import conversation_events
from services.protocol.image_stream import ImageOutput
from services.protocol.message_utils import ConversationRequest, build_image_prompt


def result_image_output(model: str) -> ImageOutput:
    return ImageOutput(
        kind="result",
        model=model,
        index=1,
        total=1,
        data=[{"b64_json": "aGVsbG8="}],
    )


class BuildImagePromptTests(unittest.TestCase):
    def test_appends_size_and_quality_hints(self) -> None:
        prompt = build_image_prompt("画一只猫", "1792x1024", "high")
        self.assertIn("画一只猫", prompt)
        self.assertIn("输出图片尺寸为 1792x1024。", prompt)
        self.assertIn("输出图片质量为 high。", prompt)

    def test_keeps_prompt_without_size(self) -> None:
        prompt = build_image_prompt("画一只猫", None, "auto")
        self.assertNotIn("输出图片尺寸", prompt)


class ConversationEventsSizeGatingTests(unittest.TestCase):
    def _captured_prompt(self, *, model: str, size: str | None, quality: str, size_enabled: bool) -> str:
        captured: dict[str, object] = {}
        backend = mock.MagicMock()
        backend.stream_conversation.side_effect = lambda **kwargs: captured.update(kwargs) or iter([])
        list(conversation_events(
            backend,
            model=model,
            prompt="画一只猫",
            size=size,
            quality=quality,
            size_enabled=size_enabled,
        ))
        return str(captured.get("prompt") or "")

    def test_image_model_injects_hints_when_size_enabled(self) -> None:
        prompt = self._captured_prompt(
            model="gpt-image-2",
            size="1792x1024",
            quality="high",
            size_enabled=True,
        )
        self.assertIn("输出图片尺寸为 1792x1024。", prompt)
        self.assertIn("输出图片质量为 high。", prompt)

    def test_image_model_keeps_prompt_without_size_enabled(self) -> None:
        prompt = self._captured_prompt(
            model="gpt-image-2",
            size="1792x1024",
            quality="high",
            size_enabled=False,
        )
        self.assertNotIn("输出图片尺寸", prompt)
        self.assertNotIn("输出图片质量", prompt)

    def test_text_model_keeps_prompt(self) -> None:
        prompt = self._captured_prompt(
            model="auto",
            size="1792x1024",
            quality="high",
            size_enabled=True,
        )
        self.assertNotIn("输出图片尺寸", prompt)
        self.assertNotIn("输出图片质量", prompt)


class HandlerSizeEnabledTests(unittest.TestCase):
    """各接口构造 ConversationRequest 时的 size_enabled 取值。"""

    def _request_from_pool(self, module, handler, body) -> ConversationRequest:
        captured: dict[str, ConversationRequest] = {}

        def fake_pool(request: ConversationRequest):
            captured["request"] = request
            return iter([result_image_output(request.model)])

        with mock.patch.object(module, "stream_image_outputs_with_pool", side_effect=fake_pool):
            list(handler(body))
        return captured["request"]

    def test_images_generations_enables_size(self) -> None:
        request = self._request_from_pool(
            openai_v1_image_generations,
            openai_v1_image_generations.handle,
            {"prompt": "画一只猫", "model": "gpt-image-2", "size": "1792x1024", "quality": "high"},
        )
        self.assertTrue(request.size_enabled)
        self.assertEqual(request.size, "1792x1024")

    def test_images_edits_enables_size(self) -> None:
        request = self._request_from_pool(
            openai_v1_image_edit,
            openai_v1_image_edit.handle,
            {
                "prompt": "把背景换成海边",
                "model": "gpt-image-2",
                "images": [(b"image", "a.png", "image/png")],
                "size": "1024x1536",
                "quality": "high",
            },
        )
        self.assertTrue(request.size_enabled)

    def test_responses_image_tool_enables_size(self) -> None:
        body = {
            "model": "gpt-image-2",
            "input": "画一只猫",
            "tools": [{"type": "image_generation", "size": "1024x1024", "quality": "high"}],
        }
        request = self._request_from_pool(
            openai_v1_response,
            openai_v1_response.response_events,
            body,
        )
        self.assertTrue(request.size_enabled)

    def test_chat_completions_disables_size(self) -> None:
        request = self._request_from_pool(
            openai_v1_chat_complete,
            openai_v1_chat_complete.handle,
            {"model": "gpt-image-2", "prompt": "画一只猫"},
        )
        self.assertFalse(request.size_enabled)
        self.assertIsNone(request.size)


if __name__ == "__main__":
    unittest.main()
