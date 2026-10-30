"""图片模型公开名与上游工具层模型 ID 映射的单元测试。

codex-gpt-image-2.5-flare / codex-gpt-image-2.5-sunburst 为 codex/responses
工具层模型（2026-10-30 实测有效），公开名 = "codex-" + 工具层模型 ID。
"""
from __future__ import annotations

import unittest

from utils.helper import (
    IMAGE_MODELS,
    PUBLIC_IMAGE_MODELS,
    codex_image_tool_model,
    is_codex_image_model,
    is_supported_image_model,
    split_image_model,
)


class ImageModelNameTests(unittest.TestCase):
    def test_codex_25_models_are_supported_codex_models(self) -> None:
        for model in ("codex-gpt-image-2.5-flare", "codex-gpt-image-2.5-sunburst"):
            self.assertTrue(is_supported_image_model(model), model)
            self.assertTrue(is_codex_image_model(model), model)

    def test_split_keeps_plan_prefix(self) -> None:
        self.assertEqual(
            split_image_model("plus-codex-gpt-image-2.5-flare"),
            ("plus", "codex-gpt-image-2.5-flare"),
        )
        self.assertEqual(split_image_model("gpt-image-2"), (None, "gpt-image-2"))
        self.assertEqual(
            split_image_model("free-codex-gpt-image-2.5-flare"),
            (None, None),
        )

    def test_tool_model_mapping(self) -> None:
        self.assertEqual(codex_image_tool_model("codex-gpt-image-2"), "gpt-image-2")
        self.assertEqual(codex_image_tool_model("codex-gpt-image-2.5-flare"), "gpt-image-2.5-flare")
        self.assertEqual(
            codex_image_tool_model("pro-codex-gpt-image-2.5-sunburst"),
            "gpt-image-2.5-sunburst",
        )
        # 非 codex 模型回退默认工具模型
        self.assertEqual(codex_image_tool_model("gpt-image-2"), "gpt-image-2")
        self.assertEqual(codex_image_tool_model("unknown"), "gpt-image-2")

    def test_prefixed_variants_are_advertised(self) -> None:
        for model in (
            "plus-codex-gpt-image-2.5-flare",
            "team-codex-gpt-image-2.5-sunburst",
            "pro-codex-gpt-image-2.5-flare",
        ):
            self.assertIn(model, IMAGE_MODELS, model)
            self.assertIn(model, PUBLIC_IMAGE_MODELS, model)

    def test_legacy_models_still_resolve(self) -> None:
        self.assertTrue(is_supported_image_model("codex-gpt-image-2"))
        self.assertTrue(is_codex_image_model("codex-gpt-image-2"))
        self.assertTrue(is_supported_image_model("gpt-image-2"))
        self.assertFalse(is_codex_image_model("gpt-image-2"))


if __name__ == "__main__":
    unittest.main()
