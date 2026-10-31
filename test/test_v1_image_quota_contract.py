"""对外 429 insufficient_quota 契约回归测试。

固化账号池生图额度耗尽时的对外错误响应体：改动 QuotaExhaustedError
映射链路（pool → image_stream → log_service._image_error_response）前后，
必须保证 /v1/images/generations 的 429 响应体逐字节不变。

覆盖三条链路：
- 非流式端点（LoggedCall.run 同步 handler 路径）→ HTTP 429 固定 JSON 体
- 流式端点首字节前（LoggedCall.run 首个 item 拉取路径）→ HTTP 429 固定 JSON 体
- 流式首字节后中断（LoggedCall.stream 中段路径）→ SSE data 错误事件，
  维持 ImageGenerationError.to_openai_error 形态（server_error/upstream_error）

不发任何网络请求：handler 层 mock 抛出与 image_stream 一致的包装异常。
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.ai as ai_module
from services.errors import QuotaExhaustedError
from services.log_service import _image_error_response

AUTH_HEADERS = {"Authorization": "Bearer chatgpt2api"}

# 对外 429 契约固定响应体（message 为常量，不带 tried N tokens 后缀）
QUOTA_429_BODY = {
    "error": {
        "message": "no available image quota",
        "type": "insufficient_quota",
        "param": None,
        "code": "insufficient_quota",
    }
}


def _compact(body: dict) -> bytes:
    """与服务端 openai_error_response 一致的紧凑 JSON 序列化。"""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _raise_quota_like_image_stream(plan_type: str = "") -> None:
    """模拟 image_stream.py 对池额度耗尽异常的既有包装路径（from 保留 __cause__）。"""
    quota_error = QuotaExhaustedError(
        f"no available {plan_type} image quota (tried 3 tokens)".replace("  ", " ").strip()
        if plan_type else "no available image quota (tried 3 tokens)"
    )
    from services.errors import ImageGenerationError

    raise ImageGenerationError(str(quota_error), account_email="user@example.com") from quota_error


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(ai_module.create_router())
    return TestClient(app, raise_server_exceptions=False)


def test_image_error_response_accepts_raw_quota_error():
    """_image_error_response 对直接抛出的 QuotaExhaustedError 映射固定 429 体。"""
    response = _image_error_response(QuotaExhaustedError("no available image quota"))
    assert response.status_code == 429
    assert json.loads(response.body) == QUOTA_429_BODY


def test_image_error_response_accepts_wrapped_quota_error():
    """经 image_stream 包装（__cause__ 链）后仍映射固定 429 体，不依赖消息子串。"""
    with pytest.raises(Exception) as exc_info:
        _raise_quota_like_image_stream()
    response = _image_error_response(exc_info.value)
    assert response.status_code == 429
    assert json.loads(response.body) == QUOTA_429_BODY


def test_images_generations_quota_429_contract(client):
    """非流式：额度耗尽时 /v1/images/generations 返回 429 与逐字节固定响应体。"""
    with mock.patch.object(ai_module.openai_v1_image_generations, "handle", _raise_quota_like_image_stream):
        response = client.post(
            "/v1/images/generations",
            headers=AUTH_HEADERS,
            json={"model": "gpt-image-2", "prompt": "p", "n": 1, "response_format": "b64_json"},
        )

    assert response.status_code == 429
    assert response.content == _compact(QUOTA_429_BODY)


def test_images_generations_stream_quota_429_contract_before_first_byte(client):
    """流式：首字节前额度耗尽同样返回 HTTP 429 与逐字节固定响应体。"""
    with mock.patch.object(ai_module.openai_v1_image_generations, "handle", _raise_quota_like_image_stream):
        response = client.post(
            "/v1/images/generations",
            headers=AUTH_HEADERS,
            json={
                "model": "gpt-image-2",
                "prompt": "p",
                "n": 1,
                "response_format": "b64_json",
                "stream": True,
            },
        )

    assert response.status_code == 429
    assert response.content == _compact(QUOTA_429_BODY)


def test_images_generations_stream_quota_error_event_mid_stream(client):
    """流式中段：额度耗尽维持既有 SSE 错误事件形态（server_error/upstream_error）。"""
    def stream_then_fail(body):
        def items():
            yield {"type": "progress", "progress": 1}
            _raise_quota_like_image_stream()
        return items()

    with mock.patch.object(ai_module.openai_v1_image_generations, "handle", stream_then_fail):
        response = client.post(
            "/v1/images/generations",
            headers=AUTH_HEADERS,
            json={
                "model": "gpt-image-2",
                "prompt": "p",
                "n": 1,
                "response_format": "b64_json",
                "stream": True,
            },
        )

    assert response.status_code == 200
    events = [
        line[6:].strip()
        for line in response.text.splitlines()
        if line.startswith("data: ") and line[6:].strip() != "[DONE]"
    ]
    error_event = json.loads(events[-1])
    assert error_event["error"]["message"] == "no available image quota (tried 3 tokens)"
    assert error_event["error"]["type"] == "server_error"
    assert error_event["error"]["code"] == "upstream_error"
    assert error_event["error"]["account_email"] == "user@example.com"
