"""存储后端包：JSON 文件 / 数据库 / Git 三后端的统一 StorageBackend 接口实现。"""
from __future__ import annotations

from services.storage.factory import create_storage_backend

__all__ = ["create_storage_backend"]
