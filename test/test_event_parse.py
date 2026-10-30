"""protocol/event_parse SSE 事件解析族单测。

覆盖点：
- patch 操作：`apply_patch_op` 的 append/replace/未知操作、`strip_history`
  历史前缀剥离、`apply_text_patch` 的四种事件形态（p 路径、v 字符串追加、
  o=patch 列表、v 列表）
- 消息提取：`assistant_message_text` 的 parts 与 code text 兜底、
  `is_visible_assistant_message` 的 hidden/recipient/channel 过滤、
  `assistant_raw_text` 消息优先与 patch 回退、`event_assistant_text`
- 输出清洗：`sanitize_output_text` 对私有注解标记（U+E200..U+E202）的
  url 标签保留、cite 指针剔除、尾部未闭合标记清除
- 状态维护：`extract_conversation_ids`、`is_image_tool_event`、
  `update_conversation_state` 的图片上下文门控（用户消息不采纳 file_id）、
  moderation blocked、server_ste_metadata 的 tool_invoked / turn_use_case
- `iter_conversation_payloads`：[DONE]、非法 JSON → raw、delta 产出、
  历史回放消息跳过
"""

import json

from services.protocol.event_parse import (
    ConversationState,
    apply_patch_op,
    apply_text_patch,
    assistant_message_text,
    assistant_raw_text,
    conversation_base_event,
    event_assistant_text,
    extract_conversation_ids,
    is_visible_assistant_message,
    is_image_tool_event,
    iter_conversation_payloads,
    sanitize_output_text,
    strip_history,
    update_conversation_state,
)

REAL_FILE_ID = "file_00000000" + "a" * 24

# ChatGPT web 私有注解标记（私有区字符，源码中以字面量嵌入正则）
OPEN, CLOSE, SEP = "", "", ""


# ---- patch 操作 ----


def test_apply_patch_op_append_and_replace():
    assert apply_patch_op({"o": "append", "v": " world"}, "hello") == "hello world"
    assert apply_patch_op({"o": "replace", "v": "new"}, "old") == "new"


def test_apply_patch_op_replace_strips_history_prefix():
    assert apply_patch_op({"o": "replace", "v": "history tail"}, "", "history ") == "tail"


def test_apply_patch_op_unknown_op_keeps_current_text():
    assert apply_patch_op({"o": "delete", "v": "x"}, "keep") == "keep"


def test_strip_history_removes_repeated_prefixes():
    assert strip_history("ababab", "ab") == ""
    assert strip_history("ababx", "ab") == "x"
    assert strip_history("x", "") == "x"
    assert strip_history(None, "ab") == ""


def test_apply_text_patch_handles_direct_p_path():
    event = {"p": "/message/content/parts/0", "o": "append", "v": "world"}
    assert apply_text_patch(event, "hello ") == "hello world"


def test_apply_text_patch_appends_bare_v_string():
    assert apply_text_patch({"v": "!"}, "hello") == "hello!"


def test_apply_text_patch_bare_v_string_ignored_without_current_text():
    assert apply_text_patch({"v": "!"}, "") == ""


def test_apply_text_patch_recurses_patch_list():
    event = {"o": "patch", "v": [
        {"p": "/message/content/parts/0", "o": "append", "v": "a"},
        {"p": "/message/content/parts/0", "o": "append", "v": "b"},
    ]}
    assert apply_text_patch(event, "") == "ab"


def test_apply_text_patch_recurses_v_list_without_o():
    event = {"v": [
        {"p": "/message/content/parts/0", "o": "replace", "v": "full text"},
    ]}
    assert apply_text_patch(event, "old") == "full text"


def test_apply_text_patch_non_list_v_returns_current():
    assert apply_text_patch({"o": "patch", "v": 123}, "keep") == "keep"


# ---- 消息提取与可见性 ----


def test_assistant_message_text_from_parts():
    assert assistant_message_text({"content": {"parts": ["a", "b", 1]}}) == "ab"


def test_assistant_message_text_falls_back_to_text_field():
    assert assistant_message_text({"content": {"content_type": "code", "text": "print(1)"}}) == "print(1)"


def test_assistant_message_text_empty_message():
    assert assistant_message_text({}) == ""
    assert assistant_message_text({"content": {"parts": []}}) == ""


def test_is_visible_assistant_message_filters_internal_messages():
    visible = {"author": {"role": "assistant"}, "recipient": "all", "channel": "final"}
    assert is_visible_assistant_message(visible) is True

    hidden = {**visible, "metadata": {"is_visually_hidden_from_conversation": True}}
    assert is_visible_assistant_message(hidden) is False

    tool_recipient = {**visible, "recipient": "web"}
    assert is_visible_assistant_message(tool_recipient) is False

    reasoning = {**visible, "channel": "commentary"}
    assert is_visible_assistant_message(reasoning) is False

    assert is_visible_assistant_message({"author": {"role": "user"}}) is False
    assert is_visible_assistant_message({}) is False


def test_assistant_raw_text_prefers_message_event():
    event = {"v": {"message": {
        "author": {"role": "assistant"}, "recipient": "all",
        "content": {"parts": ["final answer"]},
    }}}
    assert assistant_raw_text(event) == "final answer"


def test_assistant_raw_text_falls_back_to_patch_delta():
    event = {"p": "/message/content/parts/0", "o": "append", "v": " tail"}
    assert assistant_raw_text(event, "head") == "head tail"


def test_assistant_raw_text_strips_history_from_message():
    event = {"v": {"message": {
        "author": {"role": "assistant"}, "recipient": "all",
        "content": {"parts": ["history tail"]},
    }}}
    assert assistant_raw_text(event, history_text="history ") == "tail"


def test_event_assistant_text_only_reads_message_events():
    message_event = {"v": {"message": {
        "author": {"role": "assistant"}, "recipient": "all",
        "content": {"parts": ["answer"]},
    }}}
    assert event_assistant_text(message_event) == "answer"
    assert event_assistant_text({"p": "/message/content/parts/0", "o": "append", "v": "x"}) == ""


# ---- 输出清洗 ----


def test_sanitize_output_text_keeps_url_annotation_label():
    text = f"see {OPEN}url{SEP}文档{SEP}https://example.com/doc{CLOSE} page"
    assert sanitize_output_text(text) == "see 文档 (https://example.com/doc) page"


def test_sanitize_output_text_removes_internal_cite_pointer():
    text = f"text {OPEN}cite{SEP}turn5view0{CLOSE} more"
    assert sanitize_output_text(text) == "text  more"


def test_sanitize_output_text_truncates_unclosed_trailing_marker():
    assert sanitize_output_text(f"answer {OPEN}source_x") == "answer "
    assert sanitize_output_text("clean text") == "clean text"


# ---- 状态维护 ----


def test_extract_conversation_ids_from_payload():
    payload = json.dumps({
        "conversation_id": "conv-1",
        "v": {"message": {"content": {"parts": [
            {"asset_pointer": f"file-service://{REAL_FILE_ID}"},
            "sediment://sed-9",
        ]}}},
    })
    conversation_id, file_ids, sediment_ids = extract_conversation_ids(payload)
    assert conversation_id == "conv-1"
    assert file_ids == [REAL_FILE_ID]
    assert sediment_ids == ["sed-9"]


def test_is_image_tool_event_detects_async_task_and_asset_pointer():
    task_event = {"v": {"message": {
        "author": {"role": "tool"},
        "metadata": {"async_task_type": "image_gen"},
    }}}
    assert is_image_tool_event(task_event) is True

    pointer_event = {"v": {"message": {
        "author": {"role": "tool"},
        "content": {"content_type": "multimodal_text", "parts": [
            {"asset_pointer": f"file-service://{REAL_FILE_ID}"},
        ]},
    }}}
    assert is_image_tool_event(pointer_event) is True

    assert is_image_tool_event({"v": {"message": {"author": {"role": "assistant"}}}}) is False
    assert is_image_tool_event({}) is False


def test_update_conversation_state_accumulates_ids_and_text_context():
    state = ConversationState()
    update_conversation_state(state, '{"conversation_id": "conv-1"}', {"conversation_id": "conv-1"})
    assert state.conversation_id == "conv-1"
    assert state.file_ids == []


def test_update_conversation_state_adopts_ids_in_image_tool_context():
    state = ConversationState()
    event = {"v": {"message": {
        "author": {"role": "tool"},
        "metadata": {"async_task_type": "image_gen"},
    }}}
    payload = json.dumps({
        "conversation_id": "conv-1",
        "file_id": REAL_FILE_ID,
        "pointer": "sediment://sed-1",
    })
    update_conversation_state(state, payload, event)
    assert state.file_ids == [REAL_FILE_ID]
    assert state.sediment_ids == ["sed-1"]


def test_update_conversation_state_ignores_user_message_file_ids():
    state = ConversationState()
    state.tool_invoked = True
    event = {"v": {"message": {"author": {"role": "user"}}}}
    payload = json.dumps({"attachments": [{"id": REAL_FILE_ID}]})
    update_conversation_state(state, payload, event)
    # 用户上传的输入图片不应被当成生成结果
    assert state.file_ids == []


def test_update_conversation_state_accepts_patch_event_with_asset_pointer():
    state = ConversationState()
    event = {"o": "patch", "v": []}
    payload = json.dumps({"parts": [{"asset_pointer": f"sediment://sed-{1}"}], "file_id": REAL_FILE_ID})
    update_conversation_state(state, payload, event)
    assert state.sediment_ids == ["sed-1"]
    assert state.file_ids == [REAL_FILE_ID]


def test_update_conversation_state_tracks_moderation_and_metadata():
    state = ConversationState()
    update_conversation_state(
        state,
        json.dumps({"type": "moderation", "moderation_response": {"blocked": True}}),
        {"type": "moderation", "moderation_response": {"blocked": True}},
    )
    assert state.blocked is True

    metadata_event = {
        "type": "server_ste_metadata",
        "metadata": {"tool_invoked": True, "turn_use_case": "image gen"},
    }
    update_conversation_state(state, "{}", metadata_event)
    assert state.tool_invoked is True
    assert state.turn_use_case == "image gen"


def test_conversation_base_event_carries_state_snapshot():
    state = ConversationState(conversation_id="conv-1", text="t", tool_invoked=True)
    state.file_ids.append(REAL_FILE_ID)
    event = conversation_base_event("conversation.done", state, done=True)
    assert event["type"] == "conversation.done"
    assert event["conversation_id"] == "conv-1"
    assert event["file_ids"] == [REAL_FILE_ID]
    assert event["tool_invoked"] is True
    assert event["done"] is True
    # 快照为拷贝，修改事件不影响内部状态
    event["file_ids"].append("x")
    assert state.file_ids == [REAL_FILE_ID]


# ---- iter_conversation_payloads ----


def message_event_payload(text: str, conversation_id: str = "conv-1") -> str:
    return json.dumps({"v": {"message": {
        "author": {"role": "assistant"}, "recipient": "all", "channel": "final",
        "conversation_id": conversation_id,
        "content": {"parts": [text]},
    }}})


def test_iter_conversation_payloads_done_and_raw_events():
    payloads = ['{"p": "/message/content/parts/0", "o": "append", "v": "hi"}', "not-json", "[DONE]", "after-done"]
    events = list(iter_conversation_payloads(iter(payloads)))
    types = [event["type"] for event in events]
    assert types == ["conversation.delta", "conversation.raw", "conversation.done"]


def test_iter_conversation_payloads_accumulates_deltas():
    payloads = [
        '{"p": "/message/content/parts/0", "o": "append", "v": "你好"}',
        '{"p": "/message/content/parts/0", "o": "append", "v": "世界"}',
        "[DONE]",
    ]
    events = list(iter_conversation_payloads(iter(payloads)))
    deltas = [event["delta"] for event in events if event["type"] == "conversation.delta"]
    assert deltas == ["你好", "世界"]
    # delta 事件携带截至当前的累积文本
    assert [event["text"] for event in events if event["type"] == "conversation.delta"] == ["你好", "你好世界"]


def test_iter_conversation_payloads_skips_history_replay():
    payloads = [
        message_event_payload("历史消息"),
        message_event_payload("新消息"),
        "[DONE]",
    ]
    events = list(iter_conversation_payloads(iter(payloads), history_messages=["历史消息"]))
    # 历史回放消息被跳过，不产出 delta
    assert [event["type"] for event in events] == ["conversation.delta", "conversation.done"]
    assert events[0]["delta"] == "新消息"


def test_iter_conversation_payloads_non_dict_json_becomes_event():
    events = list(iter_conversation_payloads(iter(["123", "[DONE]"])))
    assert events[0]["type"] == "conversation.event"
    assert events[0]["raw"] == 123


def test_iter_conversation_payloads_empty_payloads_skipped():
    events = list(iter_conversation_payloads(iter(["", "[DONE]"])))
    assert [event["type"] for event in events] == ["conversation.done"]
