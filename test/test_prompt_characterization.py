#!/usr/bin/env python3
"""提示词组装的现有行为特征测试（characterization test）。

这三处当前**零测试覆盖**，重构前先把「现在真实是什么样」固化下来：

- `message_utils.normalize_messages`：global system 前置、以及**非幂等**（调用两次会
  注入两次）这一已知缺陷；
- `message_utils.prompt_with_global_system`：`f"{global}\\n\\n{prompt}"` 的拼接格式；
- `anthropic_v1_messages.build_tool_prompt` / `merge_system` / `XML_TOOL_RULE`。

本文件的断言描述的是**当前行为**，不是理想行为。若重构后这里的用例失败，
说明行为发生漂移，必须先判断漂移是否符合预期再更新断言——**不要**为了让测试变绿
而改写它们（尤其 `test_normalize_messages_is_not_idempotent`）。
"""
from __future__ import annotations

import pytest

from services.config import config
from services.protocol.anthropic_v1_messages import (
    XML_TOOL_RULE,
    build_tool_prompt,
    merge_system,
)
from services.protocol.message_utils import normalize_messages, prompt_with_global_system

GLOBAL_PROMPT = "全局系统提示：始终用中文回答。"


@pytest.fixture
def global_prompt(monkeypatch: pytest.MonkeyPatch) -> str:
    """把 `global_system_prompt` 注入进程内 config 单例，测试结束后由 monkeypatch 还原。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": GLOBAL_PROMPT})
    return GLOBAL_PROMPT


@pytest.fixture
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """清空 `global_system_prompt`。"""
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


# --------------------------------------------------------------------------- #
# normalize_messages
# --------------------------------------------------------------------------- #

def test_normalize_messages_prepends_global_system(global_prompt: str) -> None:
    """配置了 global_system_prompt 时，首条是 global system 消息。"""
    normalized = normalize_messages([{"role": "user", "content": "你好"}])

    assert normalized[0] == {"role": "system", "content": global_prompt}
    assert normalized[1] == {"role": "user", "content": "你好"}


def test_normalize_messages_puts_request_system_after_global(global_prompt: str) -> None:
    """请求级 system 作为第二条 system 消息，排在 global 之后（两条并存，不合并）。"""
    normalized = normalize_messages([{"role": "user", "content": "你好"}], "请求级系统提示")

    assert normalized[0] == {"role": "system", "content": global_prompt}
    assert normalized[1] == {"role": "system", "content": "请求级系统提示"}
    assert normalized[2] == {"role": "user", "content": "你好"}


def test_normalize_messages_without_global_keeps_messages_unchanged(no_global_prompt: None) -> None:
    """没有 global system 且没传 system 时，只做消息结构规范化，不加任何 system。"""
    normalized = normalize_messages([{"role": "user", "content": "你好"}])

    assert normalized == [{"role": "user", "content": "你好"}]


def test_normalize_messages_accepts_segmented_system(no_global_prompt: None) -> None:
    """分段形式的请求级 system 会被压成纯文本后作为 system 消息。"""
    normalized = normalize_messages(
        [{"role": "user", "content": "你好"}],
        [{"type": "text", "text": "第一段"}, {"type": "text", "text": "第二段"}],
    )

    assert normalized[0] == {"role": "system", "content": "第一段第二段"}


def test_normalize_messages_extracts_image_parts(no_global_prompt: None) -> None:
    """user 消息里的 base64 图片分段被抽成 `{"type": "image", ...}`，与文本分段并存。"""
    normalized = normalize_messages([
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这是什么"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}},
            ],
        },
    ])

    content = normalized[0]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "这是什么"}
    assert content[1]["type"] == "image"
    assert content[1]["data"] == b"hello"
    assert content[1]["mime"] == "image/png"


def test_normalize_messages_is_not_idempotent(global_prompt: str) -> None:
    """已知缺陷（阶段 1 如实固化）：重复调用会把 global system 注入多次。

    端点层与 `event_parse.conversation_events` 各调一次 `normalize_messages`，
    于是文本链路每次请求实际注入 2 次。阶段 2 修复后本用例应改为断言幂等。
    """
    once = normalize_messages([{"role": "user", "content": "你好"}])
    twice = normalize_messages(once)

    system_messages = [message for message in twice if message["role"] == "system"]
    assert len(system_messages) == 2
    assert system_messages == [{"role": "system", "content": global_prompt}] * 2


def test_normalize_messages_ignores_non_list_input(global_prompt: str) -> None:
    """非 list 输入被忽略，只剩 global system 一条。"""
    assert normalize_messages(None) == [{"role": "system", "content": global_prompt}]
    assert normalize_messages("not-a-list") == [{"role": "system", "content": global_prompt}]


def test_normalize_messages_skips_non_dict_items(no_global_prompt: None) -> None:
    """列表里的非 dict 元素被跳过。"""
    assert normalize_messages(["oops", {"role": "user", "content": "hi"}]) == [
        {"role": "user", "content": "hi"},
    ]


# --------------------------------------------------------------------------- #
# prompt_with_global_system
# --------------------------------------------------------------------------- #

def test_prompt_with_global_system_joins_with_blank_line(global_prompt: str) -> None:
    """拼接格式固定为 `f"{global}\\n\\n{prompt}"`。"""
    assert prompt_with_global_system("画一只猫") == f"{global_prompt}\n\n画一只猫"


def test_prompt_with_global_system_returns_prompt_when_global_empty(no_global_prompt: None) -> None:
    """global 为空时原样返回，不加任何前缀。"""
    assert prompt_with_global_system("画一只猫") == "画一只猫"


def test_prompt_with_global_system_does_not_strip_prompt(global_prompt: str) -> None:
    """prompt 前后空白被保留（当前实现不做 strip）。"""
    assert prompt_with_global_system("  画一只猫  ") == f"{global_prompt}\n\n  画一只猫  "


def test_prompt_with_global_system_empty_prompt(global_prompt: str) -> None:
    """空 prompt 时仍会拼出 `global + "\\n\\n"`，产生尾随空行。"""
    assert prompt_with_global_system("") == f"{global_prompt}\n\n"


# --------------------------------------------------------------------------- #
# anthropic 三件套：build_tool_prompt / merge_system / XML_TOOL_RULE
# --------------------------------------------------------------------------- #

def test_xml_tool_rule_constant() -> None:
    """XML_TOOL_RULE 是固定英文文案，且只声明 tool_calls XML 形状。"""
    assert XML_TOOL_RULE.startswith("Tool output adapter: when calling tools, output ONLY this XML")
    assert "<tool_calls><tool_call><tool_name>TOOL_NAME</tool_name>" in XML_TOOL_RULE
    assert "<parameters><PARAM><![CDATA[value]]></PARAM></parameters>" in XML_TOOL_RULE
    # 首行声明 + 换行 + 一行 XML 形状，没有尾随换行
    assert XML_TOOL_RULE.endswith("</tool_call></tool_calls>")


def test_build_tool_prompt_returns_empty_for_non_list() -> None:
    """tools 不是 list 时返回空串。"""
    assert build_tool_prompt(None) == ""
    assert build_tool_prompt({"name": "x"}) == ""


def test_build_tool_prompt_returns_empty_for_empty_list() -> None:
    assert build_tool_prompt([]) == ""


def test_build_tool_prompt_returns_empty_when_no_tool_has_name() -> None:
    """所有工具都取不到名字时，不产出任何内容。"""
    assert build_tool_prompt([{"description": "无名字"}]) == ""


def test_build_tool_prompt_renders_tool_block_and_rules() -> None:
    """单个工具渲染成 `Tool/Description/Parameters` 三段，尾部追加固定规则。

    注意当前实现把规则字面量整体 `.strip()` 后才拼接，因此工具块与
    `Tool use rules:` 之间**没有分隔换行**（已知的格式瑕疵，如实固化）。
    """
    prompt = build_tool_prompt([{
        "name": "read_file",
        "description": "读取文件",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    }])

    assert prompt.startswith("Available tools:\nTool: read_file\nDescription: 读取文件\nParameters: ")
    assert '{"type": "object", "properties": {"path": {"type": "string"}}}' in prompt
    assert "}Tool use rules:\n" in prompt
    assert prompt.endswith("using the exact schema names.")


def test_build_tool_prompt_supports_openai_function_shape() -> None:
    """OpenAI 的 `{"type":"function","function":{...}}` 形状同样可解析。"""
    prompt = build_tool_prompt([{
        "type": "function",
        "function": {"name": "shell", "description": "跑命令", "parameters": {"type": "object"}},
    }])

    assert "Tool: shell\nDescription: 跑命令\nParameters: " in prompt


def test_build_tool_prompt_joins_multiple_tools_with_newline() -> None:
    """多个工具块之间用单个换行连接。"""
    prompt = build_tool_prompt([
        {"name": "a", "description": "da", "input_schema": {}},
        {"name": "b", "description": "db", "input_schema": {}},
    ])

    assert "Tool: a\nDescription: da\nParameters: {}\nTool: b\nDescription: db\nParameters: {}" in prompt


def test_merge_system_returns_none_when_both_empty() -> None:
    """system 与 extra 都为空时返回 None（不是空串）。"""
    assert merge_system(None, "") is None


def test_merge_system_appends_extra_to_string_system() -> None:
    """字符串 system 与 extra 之间用空行分隔。"""
    assert merge_system("S", "E") == "S\n\nE"


def test_merge_system_strips_string_system() -> None:
    """字符串 system 会被 strip 后再拼接。"""
    assert merge_system("  S  ", "E") == "S\n\nE"


def test_merge_system_returns_extra_when_system_missing() -> None:
    assert merge_system(None, "E") == "E"
    assert merge_system("   ", "E") == "E"


def test_merge_system_appends_text_block_to_list_system() -> None:
    """list 形式的 system 追加一个 text 分段，不合并进原分段。"""
    system = [{"type": "text", "text": "S"}]

    assert merge_system(system, "E") == [{"type": "text", "text": "S"}, {"type": "text", "text": "E"}]


def test_merge_system_replaces_extra_with_xml_rule_for_claude_code() -> None:
    """检测到 Claude Code 的 system 时，extra 被整体替换为 XML_TOOL_RULE。"""
    assert merge_system("You are Claude Code, Anthropic's official CLI.", "原始 extra") == (
        f"You are Claude Code, Anthropic's official CLI.\n\n{XML_TOOL_RULE}"
    )


def test_merge_system_claude_code_without_extra_still_injects_xml_rule() -> None:
    """Claude Code 场景下即使 extra 为空也会注入 XML_TOOL_RULE（当前行为）。

    注意：`merge_system` 先做 strip/合并再判断 `if not extra`，因此此时 extra 已被
    替换成 XML_TOOL_RULE，会与 system 一起拼接（而不是只返回 XML_TOOL_RULE）。
    """
    assert merge_system("You are Claude Code", "") == f"You are Claude Code\n\n{XML_TOOL_RULE}"
    # 非 Claude Code 场景下 extra 为空就直接返回 system，不注入任何规则
    assert merge_system(None, "") is None


def test_merge_system_detects_claude_code_in_list_system() -> None:
    """list 形式的 system 也能识别 Claude Code 标记。"""
    system = [{"type": "text", "text": "You are Claude Code"}]

    assert merge_system(system, "E") == [*system, {"type": "text", "text": XML_TOOL_RULE}]


def test_merge_system_keeps_non_text_blocks_in_list_system() -> None:
    """list 里的非 text 分段原样保留。"""
    system = [{"type": "image", "data": "x"}, {"type": "text", "text": " S "}]

    assert merge_system(system, "E") == [
        {"type": "image", "data": "x"},
        {"type": "text", "text": " S "},
        {"type": "text", "text": "E"},
    ]
