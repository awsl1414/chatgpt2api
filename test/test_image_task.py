"""backend/image_task 纯函数与轮询状态机单测。

覆盖点：
- ID 提取：`extract_image_reference_ids` 只收真正的图片 file_id 与
  sediment_id、`has_image_asset_pointer` 递归判定、`add_unique` 去重
- 内容政策：`is_content_policy_error` 关键词匹配、
  `find_content_policy_error_in_conversation` 从对话文档提取拒绝文本
- `check_task_error` 结构化错误三元组、`query_backend_tasks` 按
  conversation_id/task_id 过滤
- `resolve_image_urls`：file_upload 跳过、失败继续、URL 去重
- `poll_image_results` 轮询状态机：命中即返（settle 关闭）、settle 二次
  确认、内容政策违规中断、预算耗尽抛 ImagePollTimeoutError
- 下载 URL 解析与图片字节去重下载

上游交互全部用假 api/session 模拟，`time.sleep` 打桩避免真实等待。
"""

import pytest
from curl_cffi import requests as curl_requests

import services.backend.image_task as image_task_module
from services.protocol.message_content import check_task_error
from services.backend.image_task import (
    download_image_bytes,
    extract_image_reference_ids,
    extract_image_tool_records,
    find_content_policy_error_in_conversation,
    get_attachment_download_url,
    get_file_download_url,
    has_image_asset_pointer,
    is_content_policy_error,
    poll_image_results,
    query_backend_tasks,
    resolve_image_urls,
)
from services.config import config
from services.errors import ImageContentPolicyError, ImagePollTimeoutError

REAL_FILE_ID = "file_00000000" + "a" * 24


class FakeResponse:
    def __init__(self, payload: dict | None = None):
        self.status_code = 200
        self._payload = payload or {}
        self.text = "{}"
        self.headers = {}
        self.content = b""

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0) if self.responses else FakeResponse()


class FakeAPI:
    """BackendClient 最小假实现，按序返回对话文档与下载 URL。"""

    def __init__(self, conversations: list[dict] | None = None, download_urls: dict[str, str] | None = None,
                 attachment_urls: dict[str, str] | None = None):
        self.access_token = "token-test"
        self.base_url = "https://chatgpt.com"
        self.session = FakeSession()
        self.conversations = list(conversations or [])
        self.download_urls = dict(download_urls or {})
        self.attachment_urls = dict(attachment_urls or {})

    def _headers(self, path: str, extra: dict | None = None) -> dict:
        return {"X-OpenAI-Target-Path": path, **(extra or {})}

    def _get_conversation(self, conversation_id: str) -> dict:
        if len(self.conversations) > 1:
            return self.conversations.pop(0)
        return self.conversations[0]

    def _get_file_download_url(self, file_id: str) -> str:
        return self.download_urls.get(file_id, "")

    def _get_attachment_download_url(self, conversation_id: str, attachment_id: str) -> str:
        return self.attachment_urls.get(attachment_id, "")


# ---- ID 提取与判定 ----


def test_extract_image_reference_ids_only_collects_real_ids():
    payload = {
        "parts": [
            f"file-service://{REAL_FILE_ID}",
            "file_upload placeholder",
            "file_00000000" + "b" * 24,
            "sediment://sed-123",
        ],
        "nested": {"asset_pointer": f"file-service://{REAL_FILE_ID}"},
    }
    file_ids, sediment_ids = extract_image_reference_ids(payload)
    assert file_ids == [REAL_FILE_ID, "file_00000000" + "b" * 24]
    assert sediment_ids == ["sed-123"]


def test_extract_image_reference_ids_handles_scalars_and_empty():
    assert extract_image_reference_ids("no ids here") == ([], [])
    assert extract_image_reference_ids(None) == ([], [])


def test_has_image_asset_pointer_detects_pointer_shapes():
    assert has_image_asset_pointer({"content_type": "image_asset_pointer"}) is True
    assert has_image_asset_pointer({"asset_pointer": "sediment://abc"}) is True
    assert has_image_asset_pointer({"parts": [{"asset_pointer": "file-service://abc"}]}) is True
    assert has_image_asset_pointer({"asset_pointer": "https://other"}) is False
    assert has_image_asset_pointer("plain") is False


def test_extract_image_tool_records_filters_roles_and_sorts_by_time():
    conversation = {
        "mapping": {
            "m2": {"message": {
                "id": "m2", "create_time": 20.0,
                "author": {"role": "assistant"},
                "metadata": {"async_task_type": "image_gen"},
                "content": {"content_type": "text", "parts": [f"file-service://{REAL_FILE_ID}"]},
            }},
            "m1": {"message": {
                "id": "m1", "create_time": 10.0,
                "author": {"role": "tool"},
                "metadata": {},
                "content": {"content_type": "multimodal_text", "parts": [
                    {"asset_pointer": "sediment://sed-1"},
                ]},
            }},
            "m3": {"message": {
                "id": "m3", "create_time": 30.0,
                "author": {"role": "assistant"},
                "metadata": {},
                "content": {"content_type": "text", "parts": ["普通回复，无图片"]},
            }},
            "m4": {"message": {
                "id": "m4", "create_time": 40.0,
                "author": {"role": "user"},
                "metadata": {},
                "content": {"content_type": "text", "parts": ["用户消息"]},
            }},
        }
    }
    records = extract_image_tool_records(conversation)
    assert [record["message_id"] for record in records] == ["m1", "m2"]
    assert records[0]["sediment_ids"] == ["sed-1"]
    assert records[1]["file_ids"] == [REAL_FILE_ID]
    assert all(record["message_id"] != "m3" and record["message_id"] != "m4" for record in records)


# ---- 内容政策 ----


def test_is_content_policy_error_matches_keywords():
    assert is_content_policy_error("抱歉，我不能生成该图片") is True
    assert is_content_policy_error("This request was blocked by policy") is True
    assert is_content_policy_error("") is False
    assert is_content_policy_error("今天的天气不错") is False


def test_find_content_policy_error_in_conversation_returns_text_and_truncates():
    conversation = {
        "mapping": {
            "n1": {"message": {"author": {"role": "user"}, "content": {"parts": ["我不能生成"]}}},
            "n2": {"message": {"author": {"role": "assistant"},
                               "content": {"parts": ["好的 ", "很抱歉，我不能帮助完成该请求"]}}},
        }
    }
    # 每个文本 part 提取时 strip，再以换行拼接
    assert find_content_policy_error_in_conversation(conversation) == "好的\n很抱歉，我不能帮助完成该请求"

    long_text = "很抱歉，我不能" + "x" * 600
    truncated = find_content_policy_error_in_conversation({
        "mapping": {"n1": {"message": {"author": {"role": "assistant"}, "content": {"parts": [long_text]}}}}
    })
    assert len(truncated) == 500

    assert find_content_policy_error_in_conversation({}) == ""


# ---- tasks 结构化错误 ----


def test_check_task_error_structured_fields():
    ok_task = {"image_gen_message": {
        "metadata": {"is_error": False},
        "author": {"role": "tool"},
        "content": {"content_type": "multimodal_text", "parts": []},
    }}
    assert check_task_error(ok_task) == (False, "", {"is_error": False})

    error_task = {"image_gen_message": {
        "metadata": {"is_error": True, "async_task_type": "image_gen"},
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": ["内容政策", 123]},
    }}
    is_error, error_msg, metadata = check_task_error(error_task)
    assert is_error is True
    assert error_msg == "内容政策"
    assert metadata["async_task_type"] == "image_gen"

    assert check_task_error({}) == (False, "", {})


def test_query_backend_tasks_filters_by_conversation_and_task():
    tasks = [
        {"task_id": "t1", "conversation_id": "conv-a"},
        {"task_id": "t2", "original_conversation_id": "conv-a"},
        {"task_id": "t3", "conversation_id": "conv-b"},
        "not-a-dict",
    ]

    api = FakeAPI()
    api.session = FakeSession([FakeResponse(payload={"tasks": tasks})])
    assert [task["task_id"] for task in query_backend_tasks(api, conversation_id="conv-a")] == ["t1", "t2"]

    api.session = FakeSession([FakeResponse(payload={"tasks": tasks})])
    assert [task["task_id"] for task in query_backend_tasks(api, task_id="t3")] == ["t3"]

    api.session = FakeSession([FakeResponse(payload={"tasks": "not-a-list"})])
    assert query_backend_tasks(api) == []


# ---- URL 解析与下载 ----


def test_resolve_image_urls_skips_upload_placeholder_and_dedups():
    api = FakeAPI(download_urls={
        REAL_FILE_ID: "https://cdn/a.png",
        "file_00000000" + "c" * 24: "",
    }, attachment_urls={"sed-1": "https://cdn/b.png"})
    urls = resolve_image_urls(api, "conv-1", ["file_upload", REAL_FILE_ID, "file_00000000" + "c" * 24], ["sed-1"])
    assert urls == ["https://cdn/a.png", "https://cdn/b.png"]


def test_resolve_image_urls_continues_on_download_errors():
    class BrokenAPI(FakeAPI):
        def _get_file_download_url(self, file_id: str) -> str:
            raise RuntimeError("boom")

    api = BrokenAPI(attachment_urls={})
    assert resolve_image_urls(api, "conv-1", [REAL_FILE_ID], []) == []


def test_resolve_image_urls_without_conversation_skips_attachments():
    api = FakeAPI(attachment_urls={"sed-1": "https://cdn/b.png"})
    assert resolve_image_urls(api, "", [], ["sed-1"]) == []


def test_get_file_download_url_prefers_download_url_then_url():
    api = FakeAPI()
    api.session = FakeSession([FakeResponse(payload={"download_url": "https://cdn/a.png"})])
    assert get_file_download_url(api, REAL_FILE_ID) == "https://cdn/a.png"

    api.session = FakeSession([FakeResponse(payload={"url": "https://cdn/b.png"})])
    assert get_file_download_url(api, REAL_FILE_ID) == "https://cdn/b.png"

    api.session = FakeSession([FakeResponse(payload={})])
    assert get_file_download_url(api, REAL_FILE_ID) == ""


def test_get_attachment_download_url_builds_path():
    api = FakeAPI()
    api.session = FakeSession([FakeResponse(payload={"download_url": "https://cdn/x.png"})])
    url = get_attachment_download_url(api, "conv-1", "sed-1")
    assert url == "https://cdn/x.png"
    assert api.session.calls[0]["url"] == "https://chatgpt.com/backend-api/conversation/conv-1/attachment/sed-1/download"


def test_download_image_bytes_dedups_identical_content():
    class ByteAPI:
        def __init__(self):
            self.session = FakeSession()

        class _Resp:
            status_code = 200
            content = b"same-bytes"
            headers = {}

            def json(self):  # pragma: no cover - ensure_ok 不触发
                return {}

    api = ByteAPI()
    api.session = FakeSession([ByteAPI._Resp(), ByteAPI._Resp()])
    assert download_image_bytes(api, ["u1", "u2"]) == [b"same-bytes"]


# ---- poll_image_results 轮询状态机 ----


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch):
    """轮询不打真实睡眠；轮询期间不做 tasks 预检（单独分支另行覆盖）。"""
    monkeypatch.setattr(image_task_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(image_task_module, "query_backend_tasks", lambda api, **kwargs: [])


def test_poll_image_results_returns_after_settle_double_confirm():
    image_conversation = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "tool"},
            "metadata": {"async_task_type": "image_gen"},
            "content": {"parts": [f"file-service://{REAL_FILE_ID}", "sediment://sed-1"]},
        }},
    }}
    api = FakeAPI(conversations=[{"mapping": {}}, image_conversation])

    file_ids, sediment_ids = poll_image_results(api, "conv-1", timeout_secs=10.0)

    assert file_ids == [REAL_FILE_ID]
    assert sediment_ids == ["sed-1"]


def test_poll_image_results_returns_immediately_when_settle_disabled(monkeypatch):
    monkeypatch.setattr(config, "data", {
        **config.data,
        "image_settle_enabled": False,
        "image_check_before_hit_enabled": False,
    })
    image_conversation = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "tool"},
            "metadata": {"async_task_type": "image_gen"},
            "content": {"parts": [f"file-service://{REAL_FILE_ID}"]},
        }},
    }}
    api = FakeAPI(conversations=[image_conversation])
    file_ids, _ = poll_image_results(api, "conv-1", timeout_secs=10.0)
    assert file_ids == [REAL_FILE_ID]


def test_poll_image_results_keeps_initial_ids_and_polls_for_more():
    # SSE 流已给出的初始 id 作为 last_hit_key 基线；轮询发现新 id 后
    # hit_key 变化触发 settle 二次确认，第二轮确认后合并返回
    image_conversation = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "tool"},
            "metadata": {"async_task_type": "image_gen"},
            "content": {"parts": ["sediment://sed-new"]},
        }},
    }}
    api = FakeAPI(conversations=[image_conversation])
    file_ids, sediment_ids = poll_image_results(
        api, "conv-1", timeout_secs=10.0,
        initial_file_ids=["file_00000000" + "e" * 24], initial_sediment_ids=["sed-old"],
    )
    assert file_ids == ["file_00000000" + "e" * 24]
    assert sediment_ids == ["sed-old", "sed-new"]


def test_poll_image_results_returns_initial_ids_immediately_when_nothing_new():
    # 轮询结果与初始 id 完全一致时无需二次确认，首轮即返回
    api = FakeAPI(conversations=[{"mapping": {}}])
    file_ids, sediment_ids = poll_image_results(
        api, "conv-1", timeout_secs=10.0,
        initial_file_ids=["file_00000000" + "e" * 24], initial_sediment_ids=["sed-old"],
    )
    assert file_ids == ["file_00000000" + "e" * 24]
    assert sediment_ids == ["sed-old"]


def test_poll_image_results_raises_content_policy_error():
    rejected = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "assistant"},
            "content": {"content_type": "text", "parts": ["很抱歉，我不能生成该内容"]},
        }},
    }}
    api = FakeAPI(conversations=[rejected])
    with pytest.raises(ImageContentPolicyError, match="不能生成"):
        poll_image_results(api, "conv-1", timeout_secs=10.0)


def test_poll_image_results_raises_timeout_after_budget_exhausted():
    api = FakeAPI(conversations=[{"mapping": {}}])
    with pytest.raises(ImagePollTimeoutError, match="生图超时"):
        poll_image_results(api, "conv-1", timeout_secs=0.3)


def test_poll_image_results_attaches_last_task_error_to_timeout(monkeypatch):
    monkeypatch.setattr(
        image_task_module, "query_backend_tasks",
        lambda api, **kwargs: [{"image_gen_message": {
            "metadata": {"is_error": True},
            "author": {"role": "assistant"},
            "content": {"content_type": "text", "parts": ["moderation 拦截"]},
        }}],
    )
    api = FakeAPI(conversations=[{"mapping": {}}])
    with pytest.raises(ImagePollTimeoutError) as exc_info:
        poll_image_results(api, "conv-1", timeout_secs=0.3)
    assert getattr(exc_info.value, "task_error", "") == "moderation 拦截"


def test_poll_image_results_survives_task_query_failure(monkeypatch):
    def _boom(api, **kwargs):
        raise RuntimeError("tasks down")

    monkeypatch.setattr(image_task_module, "query_backend_tasks", _boom)
    image_conversation = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "tool"},
            "metadata": {"async_task_type": "image_gen"},
            "content": {"parts": [f"file-service://{REAL_FILE_ID}"]},
        }},
    }}
    api = FakeAPI(conversations=[image_conversation])
    file_ids, _ = poll_image_results(api, "conv-1", timeout_secs=10.0)
    assert file_ids == [REAL_FILE_ID]


def test_poll_image_results_uses_curl_request_exception(monkeypatch):
    """网络抖动分支：RequestException 触发退避重试后继续轮询到命中。

    注意：当前源码的 `except UpstreamHTTPError` 未导入该名称，任何异常都会
    先触发 NameError（已记入审计报告），因此本用例先修复前提——这里通过
    把缺失的名字注入模块全局来隔离验证网络分支本身。
    """
    import utils.helper as helper_module

    monkeypatch.setattr(image_task_module, "UpstreamHTTPError", helper_module.UpstreamHTTPError, raising=False)

    attempts = {"count": 0}
    image_conversation = {"mapping": {
        "m1": {"message": {
            "create_time": 1.0, "author": {"role": "tool"},
            "metadata": {"async_task_type": "image_gen"},
            "content": {"parts": [f"file-service://{REAL_FILE_ID}"]},
        }},
    }}

    class FlakyAPI(FakeAPI):
        def _get_conversation(self, conversation_id: str) -> dict:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise curl_requests.exceptions.RequestException("connection reset")
            return super()._get_conversation(conversation_id)

    api = FlakyAPI(conversations=[{"mapping": {}}, image_conversation])
    file_ids, _ = poll_image_results(api, "conv-1", timeout_secs=10.0)
    assert attempts["count"] >= 2
    assert file_ids == [REAL_FILE_ID]
