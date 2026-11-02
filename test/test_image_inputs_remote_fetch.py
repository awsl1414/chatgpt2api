#!/usr/bin/env python3
"""`/v1/images/edits` 的 allow_remote_image_fetch 门控（SSRF 收敛）。

此前该开关只作用于对话类图片输入（`services/message_image.py`），
`api/image_inputs.py` 的远程下载完全不受控，README 的「关闭后仅接受
base64/data」承诺落空。这里固化修复后的行为：
- 开关关闭：data URL / base64 / 上传文件仍可用，远程 http(s) 直接 400；
- 开关开启：远程引用走下载路径（mock，不发真实请求）。
"""
from __future__ import annotations

import base64

import pytest
from fastapi import HTTPException

import api.image_inputs as image_inputs_module
from services.config import config

PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
REMOTE_URL = "https://example.com/pic.png"


@pytest.fixture
def remote_fetch_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "data", {**config.data, "allow_remote_image_fetch": False})


@pytest.fixture
def remote_fetch_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "data", {**config.data, "allow_remote_image_fetch": True})


def test_remote_url_rejected_when_disabled(remote_fetch_disabled: None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        image_inputs_module._download_image_url(REMOTE_URL)

    assert exc_info.value.status_code == 400
    assert "allow_remote_image_fetch" in exc_info.value.detail["error"]


def test_data_url_still_allowed_when_disabled(remote_fetch_disabled: None) -> None:
    data, filename, mime = image_inputs_module._download_image_url(PNG_DATA_URL)

    assert data == b"fake-png"
    assert mime == "image/png"
    assert filename


def test_remote_url_still_fetched_when_enabled(
    remote_fetch_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """开启时行为不变：仍然发起下载（这里只替换网络调用）。"""

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"downloaded"

    captured: dict = {}

    def fake_get(url: str, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(image_inputs_module.requests, "get", fake_get)
    data, _, mime = image_inputs_module._download_image_url(REMOTE_URL)

    assert captured["url"] == REMOTE_URL
    assert data == b"downloaded"
    assert mime == "image/png"
