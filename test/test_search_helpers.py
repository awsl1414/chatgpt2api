"""backend/search 纯工具函数与结果提取单测。

覆盖点：
- `find_search_value`：原始 SSE 载荷正则、嵌套 dict/list 递归、非法 JSON 回退
- `walk_dicts` / `add_unique` / `clean_search_url` 基础纯函数
- `search_message_text`：content.text、parts 字符串与 dict 摘要的拼装
- `extract_search_sources`：url/link/source_url 多形态提取与去重
- `extract_search_result`：assistant 消息选取（按 create_time 最新）、状态
  提取（finish_details → metadata）、正文 URL 补充进 sources
"""

from services.backend.search import (
    add_unique,
    clean_search_url,
    extract_search_result,
    extract_search_sources,
    find_search_value,
    search_message_text,
    walk_dicts,
)


def test_find_search_value_from_raw_payload_regex():
    payload = 'data: {"v": {"message": {"conversation_id": "conv-abc"}}}'
    assert find_search_value(payload, "conversation_id") == "conv-abc"


def test_find_search_value_recurses_dicts_and_lists():
    payload = {"a": [{"b": {"conversation_id": "conv-1"}}]}
    assert find_search_value(payload, "conversation_id") == "conv-1"


def test_find_search_value_invalid_json_returns_empty():
    assert find_search_value("not json {", "conversation_id") == ""
    assert find_search_value({"other": 1}, "conversation_id") == ""


def test_find_search_value_ignores_non_string_values():
    payload = {"conversation_id": 123, "nested": {"conversation_id": "conv-real"}}
    assert find_search_value(payload, "conversation_id") == "conv-real"


def test_walk_dicts_flattens_nested_structures():
    payload = {"a": 1, "b": [{"c": {"d": 2}}], "e": "str"}
    dicts = walk_dicts(payload)
    assert payload in dicts
    assert {"d": 2} in dicts
    assert walk_dicts("plain") == []


def test_clean_search_url_strips_trailing_punctuation():
    assert clean_search_url("https://example.com/a,") == "https://example.com/a"
    assert clean_search_url(" https://example.com/a。") == "https://example.com/a"
    assert clean_search_url(None) == ""
    assert clean_search_url("") == ""


def test_add_unique_appends_only_new_non_empty_values():
    values = ["a"]
    add_unique(values, ["a", "", "b", "b"])
    assert values == ["a", "b"]


def test_search_message_text_joins_text_and_part_fields():
    message = {"content": {
        "text": "summary-line",
        "parts": ["first", {"text": "inner-text"}, {"summary": "inner-summary"}, {"other": 1}, 42],
    }}
    assert search_message_text(message) == "summary-line\nfirst\ninner-text\ninner-summary"


def test_search_message_text_handles_plain_string_content_and_non_dict():
    assert search_message_text({"content": "plain"}) == "plain"
    assert search_message_text("not-a-dict") == ""
    assert search_message_text({}) == ""


def test_extract_search_sources_collects_multiple_shapes_without_duplicates():
    payload = {
        "metadata": {"url": "https://one.example/a"},
        "items": [
            {"url": "https://one.example/a", "title": "dup"},
            {"link": "https://two.example/b", "name": "Two", "snippet": "s", "type": "webpage"},
            {"source_url": "https://three.example/c", "source": "Three"},
        ],
    }
    sources = extract_search_sources(payload)
    assert [source["url"] for source in sources] == [
        "https://one.example/a", "https://two.example/b", "https://three.example/c",
    ]
    assert sources[1] == {"title": "Two", "url": "https://two.example/b", "snippet": "s", "source_type": "webpage"}
    assert sources[2]["title"] == "Three"


def test_extract_search_result_prefers_latest_assistant_message():
    conversation = {
        "mapping": {
            "n1": {"message": {
                "id": "old", "create_time": 1.0, "author": {"role": "assistant"},
                "metadata": {"finish_details": {"type": "finished_successfully"}},
                "content": {"parts": ["old answer"]},
            }},
            "n2": {"message": {
                "id": "new", "create_time": 2.0, "author": {"role": "assistant"},
                "metadata": {"finish_details": {"type": "finished_partial_completion"}},
                "content": {"parts": ["new answer https://src.example/x."]},
            }},
            "n3": {"message": {"id": "u", "create_time": 3.0, "author": {"role": "user"},
                               "content": {"parts": ["question"]}}},
        }
    }
    result = extract_search_result("conv-1", conversation)
    assert result["conversation_id"] == "conv-1"
    assert result["assistant_message_id"] == "new"
    assert result["status"] == "finished_partial_completion"
    assert result["answer"] == "new answer https://src.example/x."
    # 正文中的 URL（清洗尾部句点后）被补充进 sources
    assert any(source["url"] == "https://src.example/x" for source in result["sources"])
    assert result["create_time"] == 2.0


def test_extract_search_result_without_assistant_message():
    result = extract_search_result("conv-1", {"mapping": {}})
    assert result["answer"] == ""
    assert result["assistant_message_id"] == ""
    assert result["status"] == ""
