"""allow_remote_image_fetch 部署开关（SSRF 防护）单测。

覆盖点：
- ConfigStore.allow_remote_image_fetch：缺省默认 true（与历史行为一致）、
  显式 false / 字符串形态归一化、update 持久化
- 远程 image_url 拉取路径：开关关闭时在发起任何网络请求前拒绝
  （InvalidRequestError，400 语义），开关开启时行为不变（mock 拉取，不发真实请求）
"""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from services.config import ConfigStore
from services.errors import InvalidRequestError
import services.message_image as message_image_module
from services.message_image import _decode_message_image_url

REMOTE_URL = "https://example.com/pic.png"


@contextmanager
def _config_store(initial: dict[str, object] | None = None):
    """在临时目录构造 ConfigStore，测试结束自动清理。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "config.json"
        data: dict[str, object] = {"auth-key": "test-auth"}
        if initial:
            data.update(initial)
        path.write_text(json.dumps(data), encoding="utf-8")
        yield ConfigStore(path)


class AllowRemoteImageFetchConfigTests(unittest.TestCase):
    def test_defaults_to_true_when_missing(self) -> None:
        with _config_store() as store:
            self.assertTrue(store.allow_remote_image_fetch)
            self.assertTrue(store.get()["allow_remote_image_fetch"])

    def test_normalizes_false_and_string_values(self) -> None:
        with _config_store({"allow_remote_image_fetch": False}) as store:
            self.assertFalse(store.allow_remote_image_fetch)
        with _config_store({"allow_remote_image_fetch": "false"}) as store:
            self.assertFalse(store.allow_remote_image_fetch)
        with _config_store({"allow_remote_image_fetch": "yes"}) as store:
            self.assertTrue(store.allow_remote_image_fetch)

    def test_update_persists_value(self) -> None:
        with _config_store({"allow_remote_image_fetch": True}) as store:
            store.update({"allow_remote_image_fetch": False})
            self.assertFalse(store.allow_remote_image_fetch)
            on_disk = json.loads(store.path.read_text(encoding="utf-8"))
            self.assertIs(on_disk["allow_remote_image_fetch"], False)


@pytest.fixture()
def patch_config():
    """把 message_image 模块引用的 config 单例替换为可注入的临时 ConfigStore。"""

    def _patch(store: ConfigStore):
        return mock.patch.object(message_image_module, "config", store)

    return _patch


def test_remote_fetch_rejected_when_disabled(patch_config):
    """开关关闭：远程 image_url 在发请求前即拒绝，且不发起任何网络请求。"""
    with _config_store({"allow_remote_image_fetch": False}) as store:
        with patch_config(store), mock.patch.object(message_image_module.requests, "get") as mock_get:
            with pytest.raises(InvalidRequestError) as exc_info:
                _decode_message_image_url(REMOTE_URL)

    mock_get.assert_not_called()
    assert "allow_remote_image_fetch" in str(exc_info.value)
    assert exc_info.value.status_code == 400


def test_remote_fetch_still_works_when_enabled(patch_config):
    """开关开启（默认）：行为不变，按既有流程拉取远程图片。"""
    with _config_store({"allow_remote_image_fetch": True}) as store:
        fake_response = mock.Mock()
        fake_response.status_code = 200
        fake_response.headers = {"content-length": "4", "content-type": "image/png"}
        fake_response.content = b"gold"
        with patch_config(store), mock.patch.object(
            message_image_module.requests, "get", return_value=fake_response
        ) as mock_get:
            result = _decode_message_image_url(REMOTE_URL)

    assert mock_get.call_count == 1
    assert result == (b"gold", "image/png")


def test_data_url_unaffected_when_disabled(patch_config):
    """开关关闭仅限制远程 URL，data:/base64 图片输入不受影响。"""
    with _config_store({"allow_remote_image_fetch": False}) as store:
        data_url = "data:image/png;base64," + "aGVsbG8="
        with patch_config(store), mock.patch.object(message_image_module.requests, "get") as mock_get:
            result = _decode_message_image_url(data_url)

    mock_get.assert_not_called()
    assert result == (b"hello", "image/png")


if __name__ == "__main__":
    unittest.main()
