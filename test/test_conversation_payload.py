"""conversation_payload 纯函数单测。

覆盖点：
- `normalize_thinking_effort` 各取值的归一化表
- `api_messages_to_conversation_messages`：纯文本消息、多段文本、图片输入
  上传（mock `api._upload_image`）、无 token 携带图片、非法 content 类型
- `conversation_payload`：固定骨架字段与 thinking_effort 的注入规则
- `image_model_settings`：非图片模型回退 auto、默认上游模型、codex 公开
  模型直通、以及 "-standard/-extended/-max" 后缀拆解

config 单例通过 `config.data` 注入测试值，上游不发任何请求。
"""

from typing import Any

import pytest

from services.backend.conversation_payload import (
    api_messages_to_conversation_messages,
    conversation_payload,
    image_model_settings,
    normalize_thinking_effort,
)
from services.config import config


class FakeAPI:
    """BackendClient 最小假实现：只提供图片上传与 access_token 状态。"""

    def __init__(self, access_token: str = "token-test", upload_results: list[dict[str, Any]] | None = None):
        self.access_token = access_token
        self.upload_results = list(upload_results or [])
        self.upload_calls: list[tuple[str, str]] = []

    def _upload_image(self, image: str, file_name: str = "image.png") -> dict[str, Any]:
        self.upload_calls.append((image, file_name))
        return self.upload_results.pop(0)


def test_normalize_thinking_effort_value_table():
    assert normalize_thinking_effort("") == ""
    assert normalize_thinking_effort(None) == ""
    assert normalize_thinking_effort("auto") == ""
    assert normalize_thinking_effort("none") == ""
    assert normalize_thinking_effort("HIGH") == "high"
    assert normalize_thinking_effort(" low ") == "low"
    assert normalize_thinking_effort("medium") == "medium"
    assert normalize_thinking_effort("standard") == "standard"
    assert normalize_thinking_effort("max") == "max"
    assert normalize_thinking_effort("xhigh") == "extended"
    assert normalize_thinking_effort("extended") == "extended"
    assert normalize_thinking_effort("bogus") == ""


def test_string_message_maps_to_text_parts():
    api = FakeAPI()
    result = api_messages_to_conversation_messages(api, [
        {"role": "system", "content": "you are helpful"},
        {"content": "hello"},
    ])
    assert len(result) == 2
    system_message, user_message = result
    assert system_message["author"] == {"role": "system"}
    assert system_message["content"] == {"content_type": "text", "parts": ["you are helpful"]}
    assert user_message["author"] == {"role": "user"}
    assert user_message["content"] == {"content_type": "text", "parts": ["hello"]}
    # 每条消息都分配了唯一 id
    assert system_message["id"] != user_message["id"]
    assert api.upload_calls == []


def test_multi_part_text_message_joins_text_parts():
    api = FakeAPI()
    result = api_messages_to_conversation_messages(api, [
        {"role": "user", "content": [
            {"type": "text", "text": "look "},
            {"type": "text", "text": "here"},
            {"type": "other", "text": "ignored"},
            "not-a-dict-part",
        ]},
    ])
    assert result[0]["content"] == {"content_type": "text", "parts": ["look here"]}


def test_image_message_uploads_and_builds_multimodal_parts():
    uploaded = {
        "file_id": "file_00000000" + "a" * 24,
        "file_name": "image_1.png",
        "file_size": 128,
        "mime_type": "image/png",
        "width": 4,
        "height": 2,
    }
    api = FakeAPI(upload_results=[uploaded])
    png_b64 = "aGVsbG8="  # 任意 base64，mock 不校验内容
    result = api_messages_to_conversation_messages(api, [
        {"role": "user", "content": [
            {"type": "text", "text": "edit this"},
            {"type": "image", "data": b"hello", "mime": "image/png"},
        ]},
    ])

    assert api.upload_calls == [(f"data:image/png;base64,{png_b64}", "image_1.png")]
    message = result[0]
    assert message["content"]["content_type"] == "multimodal_text"
    parts = message["content"]["parts"]
    assert parts[0] == {
        "content_type": "image_asset_pointer",
        "asset_pointer": f"file-service://{uploaded['file_id']}",
        "width": 4,
        "height": 2,
        "size_bytes": 128,
    }
    assert parts[1] == "edit this"
    assert message["metadata"]["attachments"] == [{
        "id": uploaded["file_id"],
        "mimeType": "image/png",
        "name": "image_1.png",
        "size": 128,
        "width": 4,
        "height": 2,
    }]


def test_image_upload_extension_derives_from_mime_type():
    uploaded = {"file_id": "f1", "mime_type": "image/jpeg", "file_name": "", "file_size": 1, "width": 1, "height": 1}
    api = FakeAPI(upload_results=[uploaded])
    api_messages_to_conversation_messages(api, [
        {"role": "user", "content": [{"type": "image", "data": b"x", "mime": "image/jpeg"}]},
    ])
    assert api.upload_calls[0][1] == "image_1.jpg"


def test_image_message_without_access_token_raises():
    api = FakeAPI(access_token="")
    with pytest.raises(RuntimeError, match="authenticated upstream account"):
        api_messages_to_conversation_messages(api, [
            {"role": "user", "content": [{"type": "image", "data": b"x"}]},
        ])


def test_unsupported_content_type_raises():
    api = FakeAPI()
    with pytest.raises(RuntimeError, match="only string or list"):
        api_messages_to_conversation_messages(api, [{"role": "user", "content": 12345}])


def test_conversation_payload_skeleton_and_thinking_effort(monkeypatch):
    monkeypatch.setattr(config, "data", {**config.data, "default_thinking_effort": "high"})
    api = FakeAPI()
    payload = conversation_payload(api, [{"role": "user", "content": "hi"}], "gpt-5-5", "Asia/Shanghai", "extended")

    assert payload["action"] == "next"
    assert payload["model"] == "gpt-5-5"
    assert payload["timezone"] == "Asia/Shanghai"
    assert payload["thinking_effort"] == "extended"
    assert payload["history_and_training_disabled"] is True
    assert payload["force_use_sse"] is True
    assert payload["conversation_mode"] == {"kind": "primary_assistant"}
    assert payload["messages"][0]["content"]["parts"] == ["hi"]
    assert len(payload["parent_message_id"]) == 36
    assert len(payload["websocket_request_id"]) == 36


def test_conversation_payload_falls_back_to_config_effort_and_drops_empty(monkeypatch):
    monkeypatch.setattr(config, "data", {**config.data, "default_thinking_effort": "max"})
    api = FakeAPI()
    payload = conversation_payload(api, [{"role": "user", "content": "hi"}], "gpt-5-5", "UTC")
    assert payload["thinking_effort"] == "max"

    monkeypatch.setattr(config, "data", {**config.data, "default_thinking_effort": "auto"})
    payload_no_effort = conversation_payload(api, [{"role": "user", "content": "hi"}], "gpt-5-5", "UTC", "bogus")
    assert "thinking_effort" not in payload_no_effort


def test_image_model_settings_non_image_model_falls_back_to_auto():
    assert image_model_settings("gpt-5-5") == ("auto", "")
    assert image_model_settings("") == ("auto", "")


def test_image_model_settings_default_upstream_model(monkeypatch):
    monkeypatch.setattr(config, "data", {
        **config.data,
        "default_upstream_model_name": "gpt-5-5",
        "default_thinking_effort": "extended",
    })
    assert image_model_settings("gpt-image-2") == ("gpt-5-5", "extended")


def test_image_model_settings_codex_public_model_passthrough():
    assert image_model_settings("codex-gpt-image-2") == ("codex-gpt-image-2", "")
    assert image_model_settings("plus-codex-gpt-image-2.5-flare") == ("codex-gpt-image-2.5-flare", "")


def test_image_model_settings_split_effort_suffix(monkeypatch):
    monkeypatch.setattr(config, "data", {
        **config.data,
        "default_upstream_model_name": "gpt-5-5-thinking-max",
        "default_thinking_effort": "auto",
    })
    assert image_model_settings("gpt-image-2") == ("gpt-5-5-thinking", "max")
    # codex 公开模型直通，不做后缀拆解
    assert image_model_settings("codex-gpt-image-2") == ("codex-gpt-image-2", "")
