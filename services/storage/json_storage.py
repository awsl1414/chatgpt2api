from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.storage.base import StorageBackend, StorageDataError
from utils.log import logger


class JSONStorageBackend(StorageBackend):
    """本地 JSON 文件存储后端"""

    def __init__(self, file_path: Path, auth_keys_path: Path | None = None):
        self.file_path = file_path
        self.auth_keys_path = auth_keys_path or file_path.with_name("auth_keys.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_keys_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_json_list(file_path: Path) -> list[dict[str, Any]]:
        if not file_path.exists():
            return []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.error(f"存储文件损坏，无法解析: {file_path}: {type(exc).__name__}: {exc}")
            raise StorageDataError(str(file_path), f"{type(exc).__name__}: {exc}") from exc
        if not isinstance(data, list):
            logger.error(f"存储文件结构异常，期望 list 实际为 {type(data).__name__}: {file_path}")
            raise StorageDataError(str(file_path), f"期望 list，实际为 {type(data).__name__}")
        return data

    @staticmethod
    def _save_json_list(file_path: Path, items: list[dict[str, Any]]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def load_accounts(self) -> list[dict[str, Any]]:
        """从 JSON 文件加载账号数据"""
        return self._load_json_list(self.file_path)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        """保存账号数据到 JSON 文件"""
        self._save_json_list(self.file_path, accounts)

    def load_auth_keys(self) -> list[dict[str, Any]]:
        """从 JSON 文件加载鉴权密钥数据"""
        if not self.auth_keys_path.exists():
            return []
        try:
            data = json.loads(self.auth_keys_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.error(f"鉴权密钥文件损坏，无法解析: {self.auth_keys_path}: {type(exc).__name__}: {exc}")
            raise StorageDataError(str(self.auth_keys_path), f"{type(exc).__name__}: {exc}") from exc
        if isinstance(data, dict):
            data = data.get("items")
        if not isinstance(data, list):
            logger.error(f"鉴权密钥文件结构异常，期望 list: {self.auth_keys_path}")
            raise StorageDataError(str(self.auth_keys_path), "期望 list（或包含 items 的 dict）")
        return data

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        """保存鉴权密钥数据到 JSON 文件"""
        self.auth_keys_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_keys_path.write_text(
            json.dumps({"items": auth_keys}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def health_check(self) -> dict[str, Any]:
        """健康检查"""
        try:
            # 检查文件是否可读写
            if self.file_path.exists():
                self.file_path.read_text(encoding="utf-8")
            return {
                "status": "healthy",
                "backend": "json",
                "file_exists": self.file_path.exists(),
                "file_path": str(self.file_path),
                "auth_keys_file_exists": self.auth_keys_path.exists(),
                "auth_keys_file_path": str(self.auth_keys_path),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "json",
                "error": str(e),
            }

    def get_backend_info(self) -> dict[str, Any]:
        """获取存储后端信息"""
        return {
            "type": "json",
            "description": "本地 JSON 文件存储",
            "file_path": str(self.file_path),
            "file_exists": self.file_path.exists(),
            "auth_keys_file_path": str(self.auth_keys_path),
            "auth_keys_file_exists": self.auth_keys_path.exists(),
        }
