"""protocol/image_stream 生图流编排单测（mock saver 与轮询，不发真实请求）。

覆盖点：
- `is_model_text_reply_instead_of_image`：referenced_image_ids 与部分工具
  参数 JSON 两种「文本回复代替生图」的判定
- `ImageOutput.to_chunk`：progress / message / result 三种 chunk 形态
- `format_image_result`：b64_json / url 两种 response_format，图片字节经
  注入的 saver 落盘后填入 url；空结果附 message
- `stream_image_chunks` / `collect_image_outputs`：流到 chunk、流归并为
  非流式响应（合并 result/message/progress、附账号邮箱）
- `stream_image_outputs` 四段衔接（mock conversation_events 与 backend）：
  - blocked + 文本 → 产出 message 事件且不轮询
  - SSE 已带 file_ids → 轮询解析 URL → 下载字节 → result 事件
  - 纯文本回复（无图片上下文）→ 文本透传为 message
  - 无 message 无 URL 但 turn_use_case=image gen → 兜底重试轮询后出结果
- `_poll_image_results_with_retry`：成功扩充 ids、内容政策错误立即终止、
  普通异常按退避重试
- codex 生图流：`_codex_response_images` 递归抽取、
  `stream_codex_image_outputs` 成功与无图错误的分支
"""

import base64

import pytest

import services.protocol.image_stream as image_stream_module
from services.errors import (
    CodexSourceAccountError,
    ImageContentPolicyError,
    ImageGenerationError,
    public_image_error_message,
)
from services.backend.codex_image import iter_codex_image_response_events
from services.protocol.image_stream import (
    ImageOutput,
    _codex_response_images,
    _poll_image_results_with_retry,
    collect_image_outputs,
    format_image_result,
    is_model_text_reply_instead_of_image,
    save_image_bytes,
    set_image_saver,
    stream_image_chunks,
    stream_image_outputs,
    stream_codex_image_outputs,
)
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import build_prompt_plan, render_picture_prompt

REAL_FILE_ID = "file_00000000" + "a" * 24
PNG_B64 = base64.b64encode(b"fake-png-bytes").decode("ascii")


@pytest.fixture(autouse=True)
def _fake_saver(monkeypatch):
    """注入假的图片落盘回调；不打真实睡眠。"""
    monkeypatch.setattr(image_stream_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        image_stream_module, "_image_saver",
        lambda image_data, base_url=None: f"saved://{base64.b64encode(image_data).decode('ascii')[:8]}",
        raising=False,
    )
    yield


def make_request(**overrides) -> ConversationRequest:
    fields = {
        "model": "gpt-image-2",
        "prompt": "a cat",
        "response_format": "b64_json",
        "base_url": None,
    }
    fields.update(overrides)
    return ConversationRequest(**fields)


class FakeBackend:
    """生图流依赖的最小 backend 假实现。"""

    def __init__(self, urls: list[str] | None = None, image_bytes: bytes = b"fake-png-bytes"):
        self.urls = list(urls or [])
        self.image_bytes = image_bytes
        self.resolve_calls: list[tuple] = []
        self.poll_calls: list[tuple] = []

    def resolve_conversation_image_urls(self, conversation_id, file_ids, sediment_ids, poll=True, poll_timeout_secs=None):
        self.resolve_calls.append((conversation_id, list(file_ids), list(sediment_ids), poll))
        return list(self.urls)

    def download_image_bytes(self, urls: list[str]) -> list[bytes]:
        return [self.image_bytes for _ in urls]

    def _poll_image_results(self, conversation_id, timeout, file_ids, sediment_ids):
        self.poll_calls.append((conversation_id, list(file_ids), list(sediment_ids)))
        return [], []

    def close(self) -> None:
        """`_generate_single_image` 在 finally 中关闭 backend。"""


# ---- 文本回复判定 ----


def test_is_model_text_reply_instead_of_image_patterns():
    assert is_model_text_reply_instead_of_image(
        'I will generate {"referenced_image_ids": ["file_x"], "prompt": "cat"}'
    ) is True
    assert is_model_text_reply_instead_of_image('{"size": "1920x1088", "n": 1}') is True
    assert is_model_text_reply_instead_of_image("just a text answer") is False
    assert is_model_text_reply_instead_of_image("") is False


# ---- chunk 与归并 ----


def test_image_output_to_chunk_three_kinds():
    progress = ImageOutput(kind="progress", model="m", index=1, total=2, text="working",
                           upstream_event_type="conversation.delta", conversation_id="c1").to_chunk()
    assert progress["object"] == "image.generation.chunk"
    assert progress["progress_text"] == "working"
    assert progress["upstream_event_type"] == "conversation.delta"
    assert progress["data"] == []

    message = ImageOutput(kind="message", model="m", index=1, total=2, text="rejected",
                          account_email="a@b.c", conversation_id="c1").to_chunk()
    assert message["object"] == "image.generation.message"
    assert message["message"] == "rejected"
    assert "progress_text" not in message and "upstream_event_type" not in message
    assert message["_account_email"] == "a@b.c"
    assert message["_conversation_id"] == "c1"

    result = ImageOutput(kind="result", model="m", index=1, total=2, data=[{"url": "u"}]).to_chunk()
    assert result["object"] == "image.generation.result"
    assert result["data"] == [{"url": "u"}]
    assert "progress_text" not in result


def test_format_image_result_b64_and_url_formats():
    items = [{"b64_json": PNG_B64, "revised_prompt": "a better cat"}]
    result = format_image_result(items, "a cat", "b64_json", base_url="http://x")
    assert result["data"] == [{
        "b64_json": PNG_B64,
        "url": f"saved://{base64.b64encode(b'fake-png-bytes').decode('ascii')[:8]}",
        "revised_prompt": "a better cat",
    }]

    url_only = format_image_result(items, "a cat", "url")
    assert set(url_only["data"][0]) == {"url", "revised_prompt"}
    assert "created" in url_only


def test_format_image_result_skips_empty_items_and_keeps_message():
    result = format_image_result([{"b64_json": ""}], "p", "b64_json", message="no image")
    assert result["data"] == []
    assert result["message"] == "no image"


def test_stream_image_chunks_and_collect_outputs():
    outputs = [
        ImageOutput(kind="progress", model="m", index=1, total=1, text="step1"),
        ImageOutput(kind="result", model="m", index=1, total=1, data=[{"url": "u"}], account_email="a@b.c"),
        ImageOutput(kind="message", model="m", index=1, total=1, text="note"),
    ]
    chunks = list(stream_image_chunks(iter(outputs)))
    assert [chunk["object"] for chunk in chunks] == [
        "image.generation.chunk", "image.generation.result", "image.generation.message",
    ]

    collected = collect_image_outputs(iter(outputs))
    assert collected["data"] == [{"url": "u"}]
    assert collected["_account_email"] == "a@b.c"
    assert "message" not in collected  # 有结果时不携带消息

    empty = collect_image_outputs(iter([ImageOutput(kind="progress", model="m", index=1, total=1, text="p1")]))
    assert empty["data"] == []
    assert empty["message"] == "p1"


# ---- stream_image_outputs 四段衔接 ----


def run_stream_image_outputs(monkeypatch, backend: FakeBackend, events: list[dict],
                             detailed_error: str = "") -> list:
    """替换 conversation_events 与 tasks 错误查询后驱动完整编排。"""
    monkeypatch.setattr(image_stream_module, "conversation_events", lambda backend_arg, **kwargs: iter(events))
    monkeypatch.setattr(image_stream_module, "_get_detailed_error_from_tasks",
                        lambda *args, **kwargs: detailed_error)
    return list(stream_image_outputs(backend, make_request()))


def test_stream_image_outputs_blocked_message_short_circuits(monkeypatch):
    backend = FakeBackend()
    events = [
        {"type": "conversation.delta", "delta": "thinking...", "conversation_id": "conv-1"},
        {"type": "conversation.event", "conversation_id": "conv-1", "text": "已被政策拦截",
         "blocked": True, "file_ids": [], "sediment_ids": []},
    ]
    outputs = run_stream_image_outputs(
        monkeypatch, backend, events, detailed_error="详细：内容政策违规",
    )

    # delta 与 conversation.event 各透传一个 progress，随后被 blocked message 短路
    assert [output.kind for output in outputs] == ["progress", "progress", "message"]
    assert outputs[-1].text == "详细：内容政策违规"
    assert outputs[-1].conversation_id == "conv-1"
    # blocked 短路：未发生任何轮询
    assert backend.resolve_calls == []


def test_stream_image_outputs_success_with_sse_file_ids(monkeypatch):
    backend = FakeBackend(urls=["https://cdn/a.png"])
    progress_steps: list[str] = []
    events = [
        {"type": "conversation.event", "conversation_id": "conv-1",
         "file_ids": [REAL_FILE_ID], "sediment_ids": [], "text": ""},
    ]
    monkeypatch.setattr(image_stream_module, "conversation_events", lambda backend_arg, **kwargs: iter(events))
    monkeypatch.setattr(image_stream_module, "_get_detailed_error_from_tasks", lambda *args, **kwargs: "")
    outputs = list(stream_image_outputs(backend, make_request(progress_callback=progress_steps.append)))

    assert [output.kind for output in outputs] == ["progress", "result"]
    data = outputs[-1].data[0]
    assert data["b64_json"] == PNG_B64
    assert data["url"].startswith("saved://")
    assert data["revised_prompt"] == "a cat"
    assert backend.resolve_calls == [("conv-1", [REAL_FILE_ID], [], True)]
    assert "receiving_image" in progress_steps


def test_stream_image_outputs_revised_prompt_matches_upstream_text(monkeypatch):
    """`revised_prompt` 反映实际发往上游的文本（含尺寸/质量与 global），而非原始输入。"""
    backend = FakeBackend(urls=["https://cdn/a.png"])
    events = [
        {"type": "conversation.event", "conversation_id": "conv-1",
         "file_ids": [REAL_FILE_ID], "sediment_ids": [], "text": ""},
    ]
    monkeypatch.setattr(image_stream_module, "conversation_events", lambda backend_arg, **kwargs: iter(events))
    monkeypatch.setattr(image_stream_module, "_get_detailed_error_from_tasks", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        image_stream_module.config, "data",
        {**image_stream_module.config.data, "global_system_prompt": "GLOBAL"},
    )

    plan = build_prompt_plan(
        model="gpt-image-2", prompt="a cat", size="1792x1024", quality="high", size_enabled=True,
    )
    request = make_request(size="1792x1024", quality="high", size_enabled=True, plan=plan)
    outputs = list(stream_image_outputs(backend, request))

    revised = outputs[-1].data[0]["revised_prompt"]
    assert revised == render_picture_prompt(plan)
    assert "GLOBAL" in revised
    assert "输出图片尺寸为 1792x1024。" in revised
    assert "输出图片质量为 high。" in revised
    # 会话恢复检索仍用原始 prompt（不含尺寸句与 global）
    assert request.prompt == "a cat"


def test_stream_codex_image_outputs_revised_prompt_matches_upstream_input(monkeypatch):
    """codex 链路的 `revised_prompt` 必须等于上游实际收到的 `input` 文本。

    codex 的 global system 走 `instructions`，`input` 只承载 `plan.prompt`；
    这里断言 `revised_prompt` 与真正发往上游的 input 全等，且不含 global。
    """
    monkeypatch.setattr(
        image_stream_module.config, "data",
        {**image_stream_module.config.data, "global_system_prompt": "GLOBAL_SYS"},
    )
    captured: dict = {}

    class CodexBackend:
        def iter_codex_image_response_events(self, **kwargs):
            captured.update(kwargs)
            yield {"type": "image_generation_call", "result": PNG_B64}

    plan = build_prompt_plan(model="codex-gpt-image-2", prompt="a cat")
    request = make_request(model="codex-gpt-image-2", plan=plan)
    outputs = list(stream_codex_image_outputs(CodexBackend(), request))

    assert captured["instructions"].startswith("GLOBAL_SYS")
    assert captured["prompt"] == "a cat"
    assert outputs[0].data[0]["revised_prompt"] == captured["prompt"] == "a cat"
    assert "GLOBAL_SYS" not in outputs[0].data[0]["revised_prompt"]
    assert request.prompt == "a cat"



def test_stream_image_outputs_plain_text_message_passthrough(monkeypatch):
    backend = FakeBackend()
    events = [
        {"type": "conversation.event", "conversation_id": "conv-2",
         "file_ids": [], "sediment_ids": [], "text": "普通回答"},
    ]
    outputs = run_stream_image_outputs(monkeypatch, backend, events)
    # conversation.event 透传一个空 progress，随后文本作为 message 输出
    assert [output.kind for output in outputs] == ["progress", "message"]
    assert outputs[-1].text == "普通回答"
    assert backend.resolve_calls == []  # 无图片上下文不轮询


def test_stream_image_outputs_fallback_retry_poll_recovers_result(monkeypatch):
    """无 message 无 URL 但 should_poll_for_image：兜底重试轮询后产出结果。"""
    backend = FakeBackend(urls=[])  # 首次解析拿不到 URL，图片「稍后」才可用
    poll_results = iter([(["file_00000000" + "f" * 24], ["sed-1"])])

    def fake_poll(conversation_id, timeout, file_ids, sediment_ids):
        backend.poll_calls.append((conversation_id, list(file_ids), list(sediment_ids)))
        backend.urls = ["https://cdn/late.png"]  # 重试轮询后结果才可解析
        return next(poll_results)

    monkeypatch.setattr(backend, "_poll_image_results", fake_poll)
    events = [
        {"type": "conversation.event", "conversation_id": "conv-3",
         "file_ids": [], "sediment_ids": [], "text": "", "turn_use_case": "image gen"},
    ]
    monkeypatch.setattr(image_stream_module, "conversation_events", lambda backend_arg, **kwargs: iter(events))
    monkeypatch.setattr(image_stream_module, "_get_detailed_error_from_tasks", lambda *args, **kwargs: "")

    outputs = list(stream_image_outputs(backend, make_request()))

    # 兜底重试轮询发生在首次解析失败之后，且后续以 poll=False 直接解析
    assert len(backend.poll_calls) == 1
    assert backend.resolve_calls[-1][3] is False
    assert [output.kind for output in outputs] == ["progress", "result"]


# ---- _poll_image_results_with_retry ----


def test_poll_with_retry_success_extends_ids_in_place(monkeypatch):
    monkeypatch.setattr(image_stream_module.time, "sleep", lambda *_: None)
    backend = FakeBackend()
    monkeypatch.setattr(backend, "_poll_image_results",
                        lambda cid, timeout, fids, sids: ([REAL_FILE_ID], ["sed-1"]))
    file_ids: list[str] = []
    sediment_ids: list[str] = []
    _poll_image_results_with_retry(
        backend, "conv-1", file_ids, sediment_ids,
        retry_poll_timeout=10, max_retries=3, log_prefix="test",
    )
    assert file_ids == [REAL_FILE_ID]
    assert sediment_ids == ["sed-1"]


def test_poll_with_retry_stops_immediately_on_content_policy_error(monkeypatch):
    monkeypatch.setattr(image_stream_module.time, "sleep", lambda *_: None)
    backend = FakeBackend()
    calls: list[int] = []

    def fake_poll(cid, timeout, fids, sids):
        calls.append(1)
        raise ImageContentPolicyError("policy", "conv-1")

    monkeypatch.setattr(backend, "_poll_image_results", fake_poll)
    _poll_image_results_with_retry(
        backend, "conv-1", [], [],
        retry_poll_timeout=10, max_retries=3, log_prefix="test",
    )
    assert len(calls) == 1  # 内容政策错误不重试


def test_poll_with_retry_backs_off_on_transient_error(monkeypatch):
    monkeypatch.setattr(image_stream_module.time, "sleep", lambda *_: None)
    backend = FakeBackend()
    attempts: list[int] = []

    def fake_poll(cid, timeout, fids, sids):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("upstream connection reset")
        return [REAL_FILE_ID], []

    monkeypatch.setattr(backend, "_poll_image_results", fake_poll)
    file_ids: list[str] = []
    _poll_image_results_with_retry(
        backend, "conv-1", file_ids, [],
        retry_poll_timeout=10, max_retries=3, log_prefix="test",
    )
    assert len(attempts) == 3
    assert file_ids == [REAL_FILE_ID]


# ---- codex 生图流 ----


def test_codex_response_images_recurses_event_tree():
    events = [
        {"type": "response.output_item", "content": [
            {"type": "image_generation_call", "result": f"data:image/png;base64,{PNG_B64}"},
        ]},
        {"other": [{"type": "image_generation_call", "result": f"{PNG_B64}"}]},
        {"type": "image_generation_call", "result": "  "},
    ]
    images = _codex_response_images(events)
    assert images == [PNG_B64, PNG_B64]


def test_stream_codex_image_outputs_yields_result():
    class CodexBackend:
        def iter_codex_image_response_events(self, **kwargs):
            yield {"type": "image_generation_call", "result": PNG_B64}

    outputs = list(stream_codex_image_outputs(CodexBackend(), make_request(model="codex-gpt-image-2")))
    assert len(outputs) == 1
    assert outputs[0].kind == "result"
    assert outputs[0].data[0]["b64_json"] == PNG_B64


def test_stream_codex_image_outputs_raises_without_images():
    class EmptyBackend:
        def iter_codex_image_response_events(self, **kwargs):
            yield {"type": "response.output_text", "text": "no image"}

    with pytest.raises(ImageGenerationError, match="No image result"):
        list(stream_codex_image_outputs(EmptyBackend(), make_request(model="codex-gpt-image-2")))


def test_codex_stream_rejects_web_source_account():
    """web 账号请求 codex 生图应抛 CodexSourceAccountError（R1-1：补 import 前为 NameError）。"""
    class WebAccountBackend:
        access_token = "test-token"
        account = {"source_type": "web"}

    with pytest.raises(
        CodexSourceAccountError,
        match="codex responses endpoint requires a codex source account",
    ):
        list(iter_codex_image_response_events(WebAccountBackend(), prompt="画一张图"))


def test_codex_source_account_error_message_passes_public_filter():
    """CodexSourceAccountError 文案经 public_image_error_message 清洗后原样对外（502 兼容）。"""
    exc = CodexSourceAccountError("codex responses endpoint requires a codex source account")
    assert exc.status_code == 502
    assert public_image_error_message(str(exc)) == "codex responses endpoint requires a codex source account"


def test_save_image_bytes_requires_injected_saver():
    saved = save_image_bytes(b"abc", None)
    assert saved.startswith("saved://")

    original = image_stream_module._image_saver
    image_stream_module._image_saver = None
    try:
        with pytest.raises(RuntimeError, match="image saver"):
            save_image_bytes(b"abc", None)
    finally:
        image_stream_module._image_saver = original


# ---- 硬上限超时映射 ----


def test_hard_timeout_is_mapped_to_stable_upstream_error(monkeypatch):
    """`ImageStreamHardTimeoutError` 不被泛化分支吞掉，映射为 502 upstream_stream_timeout。"""
    from services.errors import ImageStreamHardTimeoutError

    monkeypatch.setattr(image_stream_module, "_acquire_image_token", lambda request, account_email: "token")
    monkeypatch.setattr(image_stream_module, "_lookup_account_email", lambda token, index: "")
    monkeypatch.setattr(image_stream_module.account_service, "mark_image_result", lambda *a, **k: None)
    monkeypatch.setattr(image_stream_module, "OpenAIBackendAPI", lambda **kwargs: FakeBackend())

    def boom(*_args, **_kwargs):
        raise ImageStreamHardTimeoutError("upstream image stream exceeded the hard cap")

    monkeypatch.setattr(image_stream_module, "_run_image_stream", boom)
    retried: list = []
    monkeypatch.setattr(
        image_stream_module, "_decide_transport_retry",
        lambda *a, **k: retried.append(a) or (True, "token", "err"),
    )

    with pytest.raises(ImageGenerationError) as exc_info:
        list(image_stream_module._generate_single_image(make_request(), 1, 1))

    error = exc_info.value
    assert error.status_code == 502
    assert error.code == "upstream_stream_timeout"
    assert "硬上限" not in str(error)
    # 确定性超时不走传输层重试
    assert retried == []
