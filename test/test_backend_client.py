"""OpenAIBackendCore 关键链路单测。

覆盖点：
- headers 组装：`_headers` 的 target path/route 注入、`_conversation_headers`
  与 `_image_headers` 对 requirements 各 token 的条件携带、已登录/匿名链路的
  Authorization 与 `/backend-api` vs `/backend-anon` 目标路径
- `_get_chat_requirements` 时序：prepare（p token）→ PoW / turnstile 求解 →
  finalize，以及 arkose 拒绝、finalize 缺 token 等失败分支
- `stream_conversation` 事件转发：普通文本链路的 bootstrap → requirements →
  post → SSE 载荷转发，picture_v2 提示时的图片链路分流
- 纯辅助函数：`_extract_quota_and_restore_at`、`_decode_image_base64`

上游交互（session、PoW/turnstile 求解、SSE 迭代）全部 mock，不发真实请求。
"""

import base64
import json
from io import BytesIO

import pytest
from PIL import Image

from services.backend.client import OpenAIBackendCore
from services.backend.context import ChatRequirements
from services.errors import InvalidAccessTokenError


class FakeResponse:
    """模拟 curl_cffi 响应的最小接口（status/json/text/headers/close）。"""

    def __init__(self, status_code: int = 200, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._payload)
        self.closed = False

    def json(self) -> dict:
        return self._payload

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """记录请求并按序返回预设响应的假 session。"""

    def __init__(self, responses: list[FakeResponse] | None = None):
        self.headers: dict[str, str] = {}
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def _record(self, method: str, url: str, kwargs: dict) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        response = self.responses.pop(0) if self.responses else FakeResponse()
        return response

    def get(self, url: str, **kwargs) -> FakeResponse:
        return self._record("GET", url, kwargs)

    def post(self, url: str, **kwargs) -> FakeResponse:
        return self._record("POST", url, kwargs)

    def put(self, url: str, **kwargs) -> FakeResponse:
        return self._record("PUT", url, kwargs)


def make_core(access_token: str = "token-test") -> OpenAIBackendCore:
    return OpenAIBackendCore(access_token=access_token)


# ---- headers 组装 ----


def test_headers_injects_target_path_and_route_and_keeps_session_headers():
    core = make_core()
    headers = core._headers("/backend-api/conversation", {"Accept": "application/json"})
    assert headers["X-OpenAI-Target-Path"] == "/backend-api/conversation"
    assert headers["X-OpenAI-Target-Route"] == "/backend-api/conversation"
    assert headers["Accept"] == "application/json"
    # curl_cffi Headers 转 dict 后键可能变为小写，做大小写不敏感比较
    assert (headers.get("User-Agent") or headers.get("user-agent")) == core.user_agent
    assert (headers.get("OAI-Client-Version") or headers.get("oai-client-version")) == core.client_version


def test_headers_extra_can_override_defaults():
    core = make_core()
    headers = core._headers("/x", {"Accept": "text/event-stream"})
    assert headers["Accept"] == "text/event-stream"


def test_session_headers_carry_authorization_only_for_auth_chain():
    auth_core = make_core("token-test")
    assert auth_core.session.headers["Authorization"] == "Bearer token-test"

    anon_core = make_core("")
    assert "Authorization" not in anon_core.session.headers


def test_conversation_headers_conditional_sentinel_tokens():
    core = make_core()
    full = core._conversation_headers(
        "/backend-api/conversation",
        ChatRequirements(token="req-token", proof_token="proof", turnstile_token="ts", so_token="so"),
    )
    assert full["OpenAI-Sentinel-Chat-Requirements-Token"] == "req-token"
    assert full["OpenAI-Sentinel-Proof-Token"] == "proof"
    assert full["OpenAI-Sentinel-Turnstile-Token"] == "ts"
    assert full["OpenAI-Sentinel-SO-Token"] == "so"
    assert full["Accept"] == "text/event-stream"
    assert full["X-OpenAI-Target-Path"] == "/backend-api/conversation"

    minimal = core._conversation_headers(
        "/backend-api/conversation", ChatRequirements(token="req-token")
    )
    assert "OpenAI-Sentinel-Proof-Token" not in minimal
    assert "OpenAI-Sentinel-Turnstile-Token" not in minimal
    assert "OpenAI-Sentinel-SO-Token" not in minimal


def test_image_headers_conduit_token_and_sse_trace_id():
    core = make_core()
    requirements = ChatRequirements(token="req-token")
    headers = core._image_headers("/backend-api/f/conversation", requirements, "conduit-1", "text/event-stream")
    assert headers["X-Conduit-Token"] == "conduit-1"
    assert headers["Accept"] == "text/event-stream"
    assert len(headers["X-Oai-Turn-Trace-Id"]) == 36  # uuid4

    plain = core._image_headers("/backend-api/f/conversation/prepare", requirements)
    assert "X-Conduit-Token" not in plain
    assert "X-Oai-Turn-Trace-Id" not in plain
    assert plain["Accept"] == "*/*"


def test_chat_target_switches_between_auth_and_anon():
    assert make_core("token-test")._chat_target() == ("/backend-api/conversation", "Asia/Shanghai")
    assert make_core("")._chat_target() == ("/backend-anon/conversation", "America/Los_Angeles")


# ---- sentinel chat-requirements 时序 ----


def test_get_chat_requirements_prepare_then_finalize_with_pow_and_turnstile(monkeypatch):
    core = make_core()
    fake_session = FakeSession([
        FakeResponse(payload={
            "prepare_token": "prepare-1",
            "proofofwork": {"required": True, "seed": "seed-1", "difficulty": "0327"},
            "turnstile": {"required": True, "dx": "dx-payload"},
        }),
        FakeResponse(payload={"token": "final-token", "so_token": "so-1"}),
    ])
    core.session = fake_session

    calls: list[str] = []
    monkeypatch.setattr(
        "services.backend.client.build_legacy_requirements_token",
        lambda ua, sources, build: (calls.append("p_token"), "p-token")[1],
    )
    monkeypatch.setattr(
        "services.backend.client.build_proof_token",
        lambda seed, difficulty, ua, script_sources, data_build: (
            calls.append(f"proof:{seed}:{difficulty}"), "proof-token")[1],
    )
    monkeypatch.setattr(
        "services.backend.client.solve_turnstile_token",
        lambda dx, p: (calls.append(f"turnstile:{p}:{dx}"), "ts-token")[1],
    )
    core.pow_script_sources = ["https://chatgpt.com/backend-api/sentinel/sdk.js"]
    core.pow_data_build = "build-1"

    requirements = core._get_chat_requirements()

    assert calls == ["p_token", "proof:seed-1:0327", "turnstile:p-token:dx-payload"]
    assert [call["url"] for call in fake_session.calls] == [
        "https://chatgpt.com/backend-api/sentinel/chat-requirements/prepare",
        "https://chatgpt.com/backend-api/sentinel/chat-requirements/finalize",
    ]
    assert fake_session.calls[0]["json"] == {"p": "p-token"}
    assert fake_session.calls[1]["json"] == {
        "prepare_token": "prepare-1",
        "proof_token": "proof-token",
        "turnstile_token": "ts-token",
    }
    assert requirements.token == "final-token"
    assert requirements.proof_token == "proof-token"
    assert requirements.turnstile_token == "ts-token"
    assert requirements.so_token == "so-1"
    assert requirements.raw_finalize == {"token": "final-token", "so_token": "so-1"}


def test_get_chat_requirements_skips_pow_and_turnstile_when_not_required(monkeypatch):
    core = make_core()
    core.session = FakeSession([
        FakeResponse(payload={"prepare_token": "prepare-1", "proofofwork": {"required": False}}),
        FakeResponse(payload={"token": "final-token"}),
    ])

    def _fail(*args, **kwargs):
        raise AssertionError("不应在未要求时求解 PoW/turnstile")

    monkeypatch.setattr("services.backend.client.build_legacy_requirements_token", lambda *a, **k: "p-token")
    monkeypatch.setattr("services.backend.client.build_proof_token", _fail)
    monkeypatch.setattr("services.backend.client.solve_turnstile_token", _fail)

    requirements = core._get_chat_requirements()

    assert requirements.token == "final-token"
    assert requirements.proof_token == ""
    assert requirements.turnstile_token == ""
    assert core.session.calls[1]["json"]["proof_token"] == ""
    assert core.session.calls[1]["json"]["turnstile_token"] == ""


def test_get_chat_requirements_rejects_arkose(monkeypatch):
    core = make_core()
    core.session = FakeSession([
        FakeResponse(payload={"arkose": {"required": True}}),
    ])
    monkeypatch.setattr("services.backend.client.build_legacy_requirements_token", lambda *a, **k: "p-token")

    with pytest.raises(RuntimeError, match="arkose"):
        core._get_chat_requirements()


def test_get_chat_requirements_raises_when_finalize_token_missing(monkeypatch):
    core = make_core()
    core.session = FakeSession([
        FakeResponse(payload={"prepare_token": "prepare-1"}),
        FakeResponse(payload={}),
    ])
    monkeypatch.setattr("services.backend.client.build_legacy_requirements_token", lambda *a, **k: "p-token")

    with pytest.raises(RuntimeError, match="missing auth chat requirements token"):
        core._get_chat_requirements()


# ---- stream_conversation ----


def test_stream_conversation_forwards_sse_payloads(monkeypatch):
    core = make_core()
    sse_response = FakeResponse()
    fake_session = FakeSession([sse_response])
    core.session = fake_session

    bootstrap_calls: list[str] = []
    monkeypatch.setattr(core, "_bootstrap", lambda: bootstrap_calls.append("bootstrap"))
    monkeypatch.setattr(
        core, "_get_chat_requirements",
        lambda: ChatRequirements(token="req-token"),
    )
    forwarded: list[list[str]] = []
    monkeypatch.setattr(
        "services.backend.client.iter_sse_payloads",
        lambda response: forwarded.append(response) or iter(["hello", "[DONE]"]),
    )

    payloads = list(core.stream_conversation(prompt="hi", model="auto"))

    assert payloads == ["hello", "[DONE]"]
    assert forwarded == [sse_response]
    assert sse_response.closed
    assert bootstrap_calls == ["bootstrap"]
    call = fake_session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://chatgpt.com/backend-api/conversation"
    assert call["stream"] is True
    assert call["headers"]["OpenAI-Sentinel-Chat-Requirements-Token"] == "req-token"
    message = call["json"]["messages"][0]
    assert message["author"] == {"role": "user"}
    assert message["content"] == {"content_type": "text", "parts": ["hi"]}
    assert call["json"]["model"] == "auto"


def test_stream_conversation_routes_picture_v2_to_image_chain(monkeypatch):
    core = make_core()

    def _fail(*args, **kwargs):
        raise AssertionError("picture_v2 提示不应走普通文本链路")

    monkeypatch.setattr(core, "_bootstrap", _fail)

    def fake_picture(prompt, model, images):
        yield f"picture:{prompt}:{model}:{len(images)}"

    monkeypatch.setattr(core, "_stream_picture_conversation", fake_picture)

    payloads = list(core.stream_conversation(
        prompt="a cat", model="gpt-image-2", images=["aaaa"], system_hints=["picture_v2"],
    ))
    assert payloads == ["picture:a cat:gpt-image-2:1"]


# ---- 纯辅助函数 ----


def test_extract_quota_and_restore_at_reads_image_gen_entry():
    limits = [
        {"feature_name": "other", "remaining": 9},
        {"feature_name": "image_gen", "remaining": 7, "reset_after": "2026-10-31T00:00:00Z"},
    ]
    assert OpenAIBackendCore._extract_quota_and_restore_at(limits) == (7, "2026-10-31T00:00:00Z")
    assert OpenAIBackendCore._extract_quota_and_restore_at([]) == (0, None)
    assert OpenAIBackendCore._extract_quota_and_restore_at([{"feature_name": "image_gen"}]) == (0, None)


def test_decode_image_base64_supports_data_url_raw_base64_and_local_file(tmp_path):
    core = make_core()
    raw = b"\x89PNG fake bytes"

    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    assert core._decode_image_base64(data_url) == raw

    assert core._decode_image_base64(base64.b64encode(raw).decode("ascii")) == raw

    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    assert core._decode_image_base64(str(file_path)) == raw


def test_upload_image_uploads_blob_and_confirms_file():
    core = make_core()
    image = Image.new("RGB", (2, 1), color=(255, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    fake_session = FakeSession([
        FakeResponse(payload={"file_id": "file_00000000" + "a" * 24, "upload_url": "https://blob.example/put"}),
        FakeResponse(),
        FakeResponse(),
    ])
    core.session = fake_session

    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    meta = core._upload_image(data_url, "image_1.png")

    assert meta["file_id"] == "file_00000000" + "a" * 24
    assert meta["file_name"] == "image_1.png"
    assert meta["file_size"] == len(png_bytes)
    assert meta["mime_type"] == "image/png"
    assert meta["width"] == 2
    assert meta["height"] == 1

    file_post, blob_put, confirm_post = fake_session.calls
    assert file_post["url"] == "https://chatgpt.com/backend-api/files"
    assert file_post["json"]["file_size"] == len(png_bytes)
    assert file_post["json"]["width"] == 2
    assert blob_put["url"] == "https://blob.example/put"
    assert blob_put["data"] == png_bytes
    assert blob_put["headers"]["x-ms-blob-type"] == "BlockBlob"
    assert confirm_post["url"] == f"https://chatgpt.com/backend-api/files/{meta['file_id']}/uploaded"


def test_raise_on_error_distinguishes_invalid_token():
    core = make_core()
    with pytest.raises(InvalidAccessTokenError):
        core._raise_on_error(FakeResponse(status_code=401), "/backend-api/me")
    with pytest.raises(RuntimeError, match="HTTP 500"):
        core._raise_on_error(FakeResponse(status_code=500), "/backend-api/me")
