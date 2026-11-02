#!/usr/bin/env python3
"""/v1/messages 对图片模型的对外契约（P0-2）。

该端点只实现文本对话，图片模型此前被当作文本会话发起、图片工具事件被丢弃，
客户端拿到空 `content`。现在的契约是入口直接 400（Anthropic 错误体），
并在消息里指明可用的图片端点。
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from services.config import config

AUTH_HEADERS = {"x-api-key": "chatgpt2api", "anthropic-version": "2023-06-01"}


@pytest.fixture()
def client() -> TestClient:
    # 用真实应用：DomainError → Anthropic/OpenAI 兼容错误体的映射在 api/errors.py
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def no_global_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "data", {**config.data, "global_system_prompt": ""})


@pytest.mark.parametrize(
    "model",
    ["gpt-image-2", "codex-gpt-image-2", "team-codex-gpt-image-2.5-sunburst"],
)
def test_messages_rejects_image_model_with_400(client: TestClient, model: str) -> None:
    response = client.post(
        "/v1/messages",
        headers=AUTH_HEADERS,
        json={"model": model, "messages": [{"role": "user", "content": "画一只猫"}]},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == "invalid_request_error"
    assert "not supported on /v1/messages" in body["error"]["message"]
    assert model in body["error"]["message"]


def test_messages_rejects_image_model_in_stream_mode(client: TestClient) -> None:
    response = client.post(
        "/v1/messages",
        headers=AUTH_HEADERS,
        json={"model": "gpt-image-2", "stream": True, "messages": [{"role": "user", "content": "画一只猫"}]},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.content)["type"] == "error"
