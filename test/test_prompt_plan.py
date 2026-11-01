#!/usr/bin/env python3
"""`services.protocol.prompt_plan` 的单元测试。

覆盖 `build_prompt_plan` 的策略决策（system 合并去重、空 prompt 派生、尺寸/质量
注入、hints 默认值、auto 短路）与三个 renderer 的形态转换。阶段 1 尚无调用点，
这些用例即该模块的行为契约。
"""
from __future__ import annotations

import pytest

from services.backend.codex_image import CODEX_RESPONSES_INSTRUCTIONS as CODEX_INSTRUCTIONS_IN_BACKEND
from services.config import config
from services.protocol.prompt_plan import (
    CODEX_RESPONSES_INSTRUCTIONS,
    PICTURE_V2_HINT,
    TOOL_UNAVAILABLE_SYSTEM_MESSAGE,
    build_prompt_plan,
    render_codex_instructions,
    render_conversation_messages,
    render_picture_prompt,
)

GLOBAL_PROMPT = "全局系统提示：始终用中文回答。"


@pytest.fixture
def global_prompt(monkeypatch: pytest.MonkeyPatch) -> str:
    """注入 global_system_prompt，测试结束由 monkeypatch 还原。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": GLOBAL_PROMPT})
    return GLOBAL_PROMPT


@pytest.fixture
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """清空 global_system_prompt。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


# --------------------------------------------------------------------------- #
# 常量守卫
# --------------------------------------------------------------------------- #

def test_codex_instructions_constant_matches_backend() -> None:
    """本模块的 codex 指令常量必须与 backend 侧保持一致（阶段 2 会收敛为单一来源）。"""
    assert CODEX_RESPONSES_INSTRUCTIONS == CODEX_INSTRUCTIONS_IN_BACKEND


def test_tool_unavailable_message_is_static_text() -> None:
    """兜底文案是静态英文常量，不含任何配置求值结果。"""
    assert TOOL_UNAVAILABLE_SYSTEM_MESSAGE.startswith("This compatibility backend cannot execute local tools")
    assert "{global" not in TOOL_UNAVAILABLE_SYSTEM_MESSAGE


def test_tool_unavailable_message_single_source() -> None:
    """阶段 2：端点文件里的逐字副本已删除，`prompt_plan` 是唯一来源。

    端点模块不再定义同名常量（避免两处并存导致再次漂移）。
    """
    from services.protocol import openai_v1_chat_complete, openai_v1_response

    assert not hasattr(openai_v1_chat_complete, "TOOL_UNAVAILABLE_SYSTEM_MESSAGE")
    assert not hasattr(openai_v1_response, "TOOL_UNAVAILABLE_SYSTEM_MESSAGE")


def test_prompt_plan_module_has_no_protocol_package_imports() -> None:
    """依赖纪律：`prompt_plan.py` 不得反向依赖 protocol 包内其他模块。

    与 `message_utils.py` 的约定一致，避免与 `event_parse` / `image_stream` 形成环。
    """
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "services" / "protocol" / "prompt_plan.py"
    code = source.read_text(encoding="utf-8")

    assert "from services.protocol" not in code
    assert "import services.protocol" not in code


def test_prompt_plan_is_frozen() -> None:
    """PromptPlan 是不可变值对象。"""
    plan = build_prompt_plan(model="gpt-5-5", prompt="hi")

    with pytest.raises(Exception):
        plan.prompt = "changed"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# system 合并与顺序
# --------------------------------------------------------------------------- #

def test_system_order_is_global_then_request_then_tool_unavailable(global_prompt: str) -> None:
    """system 合并顺序固定为 [global, 请求级 system, tool_unavailable]。"""
    plan = build_prompt_plan(
        model="gpt-5-5",
        messages=[{"role": "user", "content": "你好"}],
        system="请求级系统提示",
        tool_unavailable=True,
    )

    assert plan.system == f"{global_prompt}\n\n请求级系统提示\n\n{TOOL_UNAVAILABLE_SYSTEM_MESSAGE}"


def test_system_skips_duplicate_parts(global_prompt: str) -> None:
    """同一段文本重复出现时只保留首次。"""
    plan = build_prompt_plan(model="gpt-5-5", prompt="hi", system=global_prompt)

    assert plan.system == global_prompt


def test_system_empty_when_nothing_configured(no_global_prompt: None) -> None:
    plan = build_prompt_plan(model="gpt-5-5", messages=[{"role": "user", "content": "你好"}])

    assert plan.system == ""


def test_leading_system_messages_fold_into_plan_system(global_prompt: str) -> None:
    """消息列表里已有的前置 system 被折进 plan.system，不再留在 messages 中。"""
    plan = build_prompt_plan(
        model="gpt-5-5",
        messages=[
            {"role": "system", "content": global_prompt},
            {"role": "user", "content": "你好"},
        ],
    )

    assert plan.system == global_prompt
    assert plan.messages == [{"role": "user", "content": "你好"}]


# --------------------------------------------------------------------------- #
# 幂等性
# --------------------------------------------------------------------------- #

def test_build_prompt_plan_is_idempotent_for_system(global_prompt: str) -> None:
    """把已渲染的 messages 再次送入构造，不会重复注入 global system。"""
    first = build_prompt_plan(model="gpt-5-5", messages=[{"role": "user", "content": "你好"}])
    second = build_prompt_plan(model="gpt-5-5", messages=render_conversation_messages(first))

    assert second.system == first.system == global_prompt
    assert second.messages == first.messages
    assert len([m for m in render_conversation_messages(second) if m["role"] == "system"]) == 1


def test_build_prompt_plan_is_idempotent_with_multi_part_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """global 自身含空行、且带请求级 system 与兜底文案时，仍不重复注入。

    不能按空行拆分比较已注入的 system——global 自己就可能有多段。
    """
    multi_part_global = "第一段\n\n第二段"
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": multi_part_global})

    first = build_prompt_plan(
        model="gpt-5-5",
        messages=[{"role": "user", "content": "你好"}],
        system="请求级",
        tool_unavailable=True,
    )
    second = build_prompt_plan(
        model="gpt-5-5",
        messages=render_conversation_messages(first),
        system="请求级",
        tool_unavailable=True,
    )

    assert second.system == first.system
    assert second.system.count(multi_part_global) == 1


def test_caller_supplied_system_message_is_preserved(global_prompt: str) -> None:
    """调用方自带的 system 消息不被当成重复注入丢弃。"""
    plan = build_prompt_plan(
        model="gpt-5-5",
        messages=[{"role": "system", "content": "调用方自带"}, {"role": "user", "content": "你好"}],
    )

    assert plan.system == f"{global_prompt}\n\n调用方自带"
    assert plan.messages == [{"role": "user", "content": "你好"}]


def test_render_conversation_messages_puts_system_first_once(global_prompt: str) -> None:
    """渲染结果里 system 只有首条一条。"""
    plan = build_prompt_plan(
        model="gpt-5-5",
        messages=[{"role": "user", "content": "你好"}, {"role": "assistant", "content": "在"}],
    )
    messages = render_conversation_messages(plan)

    assert messages[0] == {"role": "system", "content": global_prompt}
    assert [m["role"] for m in messages] == ["system", "user", "assistant"]


def test_render_conversation_messages_without_system(no_global_prompt: None) -> None:
    """没有 system 时直接返回消息列表，不插入空 system。"""
    plan = build_prompt_plan(model="gpt-5-5", messages=[{"role": "user", "content": "你好"}])

    assert render_conversation_messages(plan) == [{"role": "user", "content": "你好"}]


# --------------------------------------------------------------------------- #
# 空 prompt 派生
# --------------------------------------------------------------------------- #

def test_empty_prompt_derived_from_user_messages(no_global_prompt: None) -> None:
    """图片模型 + 空 prompt + messages → plan.prompt 非空。"""
    plan = build_prompt_plan(
        model="gpt-image-2",
        messages=[
            {"role": "system", "content": "忽略我"},
            {"role": "user", "content": "画一只猫"},
            {"role": "assistant", "content": "好的"},
            {"role": "user", "content": "再加一顶帽子"},
        ],
    )

    assert plan.prompt == "画一只猫\n再加一顶帽子"


def test_empty_prompt_without_messages_stays_empty(no_global_prompt: None) -> None:
    """既没 prompt 也没 messages 时保持空串（由调用方决定报错）。"""
    plan = build_prompt_plan(model="gpt-image-2")

    assert plan.prompt == ""


def test_explicit_prompt_wins_over_messages(no_global_prompt: None) -> None:
    """显式 prompt 优先，不从 messages 派生。"""
    plan = build_prompt_plan(
        model="gpt-image-2",
        messages=[{"role": "user", "content": "画一只猫"}],
        prompt="画一只狗",
    )

    assert plan.prompt == "画一只狗"


def test_segmented_content_text_is_flattened(no_global_prompt: None) -> None:
    """分段 content 里的 text 分段参与压平。"""
    plan = build_prompt_plan(
        model="gpt-image-2",
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": "画一只猫"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}}],
        }],
    )

    assert plan.prompt == "画一只猫"
    assert plan.messages[0]["content"][0] == {"type": "text", "text": "画一只猫"}
    assert plan.messages[0]["content"][1]["type"] == "image"


# --------------------------------------------------------------------------- #
# 尺寸 / 质量注入与 auto 短路
# --------------------------------------------------------------------------- #

def test_size_and_quality_hints_injected_when_size_enabled(no_global_prompt: None) -> None:
    plan = build_prompt_plan(
        model="gpt-image-2",
        prompt="画一只猫",
        size="1792x1024",
        quality="high",
        size_enabled=True,
    )

    assert plan.prompt == "画一只猫\n\n输出图片尺寸为 1792x1024。输出图片质量为 high。"


def test_auto_quality_is_short_circuited(no_global_prompt: None) -> None:
    """quality == "auto" 时不注入「输出图片质量为 auto。」。"""
    plan = build_prompt_plan(
        model="gpt-image-2",
        prompt="画一只猫",
        size="1792x1024",
        quality="auto",
        size_enabled=True,
    )

    assert "输出图片质量为" not in plan.prompt
    assert plan.prompt == "画一只猫\n\n输出图片尺寸为 1792x1024。"


def test_size_hints_not_injected_when_size_disabled(no_global_prompt: None) -> None:
    """size_enabled=False（如 /v1/chat/completions）时提示词保持原样。"""
    plan = build_prompt_plan(
        model="gpt-image-2",
        prompt="画一只猫",
        size="1792x1024",
        quality="high",
        size_enabled=False,
    )

    assert plan.prompt == "画一只猫"
    # 参数本身仍透传，供 codex 工具层等直接消费
    assert plan.size == "1792x1024"
    assert plan.quality == "high"


def test_no_hints_when_size_and_auto_quality(no_global_prompt: None) -> None:
    """无 size 且 quality=auto 时不产生任何提示后缀。"""
    plan = build_prompt_plan(model="gpt-image-2", prompt="画一只猫", size_enabled=True)

    assert plan.prompt == "画一只猫"


# --------------------------------------------------------------------------- #
# hints 默认值
# --------------------------------------------------------------------------- #

def test_picture_v2_hint_defaults_for_image_model(no_global_prompt: None) -> None:
    assert build_prompt_plan(model="gpt-image-2", prompt="画一只猫").hints == [PICTURE_V2_HINT]
    assert build_prompt_plan(model="pro-codex-gpt-image-2", prompt="画一只猫").hints == [PICTURE_V2_HINT]


def test_no_hint_for_text_model(no_global_prompt: None) -> None:
    assert build_prompt_plan(model="gpt-5-5", messages=[{"role": "user", "content": "hi"}]).hints == []


def test_explicit_hints_override_default(no_global_prompt: None) -> None:
    plan = build_prompt_plan(model="gpt-image-2", prompt="画一只猫", hints=[])

    assert plan.hints == []


# --------------------------------------------------------------------------- #
# renderer：picture_v2 与 codex
# --------------------------------------------------------------------------- #

def test_render_picture_prompt_prepends_system(global_prompt: str) -> None:
    plan = build_prompt_plan(
        model="gpt-image-2",
        prompt="画一只猫",
        size="1024x1024",
        size_enabled=True,
    )

    assert render_picture_prompt(plan) == f"{global_prompt}\n\n画一只猫\n\n输出图片尺寸为 1024x1024。"


def test_render_picture_prompt_without_system(no_global_prompt: None) -> None:
    plan = build_prompt_plan(model="gpt-image-2", prompt="画一只猫")

    assert render_picture_prompt(plan) == "画一只猫"


def test_render_codex_instructions_includes_global(global_prompt: str) -> None:
    """配了 global → codex instructions 含 global 且拼在固定常量前。"""
    plan = build_prompt_plan(model="codex-gpt-image-2", prompt="画一只猫")

    assert render_codex_instructions(plan) == f"{global_prompt}\n\n{CODEX_RESPONSES_INSTRUCTIONS}"


def test_render_codex_instructions_without_global(no_global_prompt: None) -> None:
    """未配 global 时原样返回固定常量。"""
    plan = build_prompt_plan(model="codex-gpt-image-2", prompt="画一只猫")

    assert render_codex_instructions(plan) == CODEX_RESPONSES_INSTRUCTIONS


def test_render_codex_instructions_accepts_custom_instructions(global_prompt: str) -> None:
    plan = build_prompt_plan(model="codex-gpt-image-2", prompt="画一只猫")

    assert render_codex_instructions(plan, "CUSTOM") == f"{global_prompt}\n\nCUSTOM"


# --------------------------------------------------------------------------- #
# 热更新红线
# --------------------------------------------------------------------------- #

def test_global_prompt_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """PromptPlan 在调用时实时读 config，改配置后同一进程下一个请求立即生效。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第一次"})
    first = build_prompt_plan(model="gpt-5-5", prompt="hi")

    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": "第二次"})
    second = build_prompt_plan(model="gpt-5-5", prompt="hi")

    assert first.system == "第一次"
    assert second.system == "第二次"


def test_images_default_to_empty_list(no_global_prompt: None) -> None:
    assert build_prompt_plan(model="gpt-image-2", prompt="画一只猫").images == []
    assert build_prompt_plan(model="gpt-image-2", prompt="画一只猫", images=["abc"]).images == ["abc"]
