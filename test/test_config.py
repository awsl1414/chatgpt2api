import json
import tempfile
import unittest
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.config import ALLOWED_CONFIG_KEYS, ConfigStore


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_CONFIG_FILE = ROOT_DIR / "config.json"


class ConfigLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._created_root_config = False
        if not ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.write_text(json.dumps({"auth-key": "test-auth"}), encoding="utf-8")
            cls._created_root_config = True

        from services import config as config_module

        cls.config_module = config_module

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._created_root_config and ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.unlink()

    def test_load_settings_ignores_directory_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            data_dir = base_dir / "data"
            config_dir = base_dir / "config.json"
            os_auth_key = "env-auth"

            config_dir.mkdir()

            module = self.config_module
            old_base_dir = module.BASE_DIR
            old_data_dir = module.DATA_DIR
            old_config_file = module.CONFIG_FILE
            old_env_auth_key = module.os.environ.get("CHATGPT2API_AUTH_KEY")
            try:
                module.BASE_DIR = base_dir
                module.DATA_DIR = data_dir
                module.CONFIG_FILE = config_dir
                module.os.environ["CHATGPT2API_AUTH_KEY"] = os_auth_key

                settings = module._load_settings()

                self.assertEqual(settings.auth_key, os_auth_key)
                self.assertEqual(settings.refresh_account_interval_minute, 5)
            finally:
                module.BASE_DIR = old_base_dir
                module.DATA_DIR = old_data_dir
                module.CONFIG_FILE = old_config_file
                if old_env_auth_key is None:
                    module.os.environ.pop("CHATGPT2API_AUTH_KEY", None)
                else:
                    module.os.environ["CHATGPT2API_AUTH_KEY"] = old_env_auth_key


def _make_store(tmp_path: Path, initial: dict[str, object] | None = None) -> ConfigStore:
    path = tmp_path / "config.json"
    data: dict[str, object] = {"auth-key": "test-auth"}
    if initial:
        data.update(initial)
    path.write_text(json.dumps(data), encoding="utf-8")
    return ConfigStore(path)


def test_update_rejects_unknown_top_level_keys(tmp_path: Path) -> None:
    """未知顶层键抛 ValueError（管理端映射 400），且不污染内存数据与配置文件。"""
    store = _make_store(tmp_path)

    with pytest.raises(ValueError, match="未知配置键: bogus_key"):
        store.update({"bogus_key": "x"})

    assert "bogus_key" not in store.data
    persisted = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert "bogus_key" not in persisted


def test_update_rejects_auth_key_and_backup_state(tmp_path: Path) -> None:
    """auth-key（部署侧配置）与 backup_state（独立状态文件）不在白名单内。"""
    store = _make_store(tmp_path)

    with pytest.raises(ValueError, match="未知配置键"):
        store.update({"auth-key": "new-key"})
    with pytest.raises(ValueError, match="未知配置键"):
        store.update({"backup_state": {"last_status": "running"}})


def test_update_accepts_every_whitelisted_key(tmp_path: Path) -> None:
    """白名单内全部顶层键逐一写入成功；valid_values 集合与白名单一一对应防漏。"""
    store = _make_store(tmp_path)
    valid_values: dict[str, object] = {
        "refresh_account_interval_minute": 5,
        "image_retention_days": 30,
        "image_poll_timeout_secs": 120,
        "image_poll_interval_secs": 10,
        "image_poll_initial_wait_secs": 10,
        "image_account_concurrency": 3,
        "image_min_free_mb": 500,
        "image_parallel_generation": True,
        "image_settle_enabled": True,
        "image_check_before_hit_enabled": True,
        "image_settle_secs": 2,
        "image_timeout_retry_secs": 30,
        "image_remove_conversation_after_result": True,
        "image_remove_conversation_always": False,
        "auto_remove_invalid_accounts": True,
        "auto_remove_rate_limited_accounts": False,
        "auto_relogin_after_refresh": False,
        "allow_remote_image_fetch": True,
        "log_levels": ["info", "error"],
        "sensitive_words": ["word"],
        "ai_review": {"enabled": False},
        "global_system_prompt": "p",
        "default_upstream_model_name": "gpt-6-thinking",
        "default_thinking_effort": "auto",
        "base_url": "https://example.com",
        "backup": {"enabled": False},
        "image_storage": {"enabled": False},
        "chat_completion_cache": {"enabled": True},
        "proxy_runtime": {"enabled": False},
        "third_party_apps": {"infinite_canvas": {"enabled": False}},
    }

    assert set(valid_values) == ALLOWED_CONFIG_KEYS

    for key, value in valid_values.items():
        updated = store.update({key: value})
        assert key in updated


def test_update_whitelist_is_top_level_dimension(tmp_path: Path) -> None:
    """白名单只作用于顶层键维度：已知顶层键下的嵌套字段由 normalize 收口，不做嵌套白名单。"""
    store = _make_store(tmp_path)

    updated = store.update({"ai_review": {"enabled": True, "brand_new_field": "x"}})

    assert updated["ai_review"]["enabled"] is True  # type: ignore[index]
    assert updated["ai_review"]["brand_new_field"] == "x"  # type: ignore[index]


def test_save_settings_unknown_key_returns_400(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """管理端 POST /api/settings 对未知配置键返回 400，错误信息为简体中文。"""
    import api.system as system_module

    store = _make_store(tmp_path)
    monkeypatch.setattr(system_module, "config", store)
    monkeypatch.setattr(system_module, "require_admin", lambda _authorization: {"role": "admin"})
    app = FastAPI()
    app.include_router(system_module.create_router("whitelist-test"))
    client = TestClient(app)

    response = client.post(
        "/api/settings",
        json={"bogus_key": "x"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 400
    assert "未知配置键" in response.json()["detail"]["error"]


if __name__ == "__main__":
    unittest.main()
