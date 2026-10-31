"""存储后端抽象：StorageBackend 协议定义（加载/保存/健康检查/后端信息）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorageDataError(RuntimeError):
    """存储数据损坏（无法解析或不符合预期结构）时抛出。

    抛出该异常的目的是 fail-fast：阻止调用方把损坏数据当作空列表继续运行，
    否则后续的保存操作会用空数据整体覆盖真实数据（如清空账号池）。
    """

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"存储文件损坏，已拒绝加载（避免后续保存覆盖真实数据）: {file_path}: {reason}")


class StorageBackend(ABC):
    """抽象存储后端基类"""

    @abstractmethod
    def load_accounts(self) -> list[dict[str, Any]]:
        """加载所有账号数据"""
        pass

    @abstractmethod
    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        """保存所有账号数据"""
        pass

    @abstractmethod
    def load_auth_keys(self) -> list[dict[str, Any]]:
        """加载所有鉴权密钥数据"""
        pass

    @abstractmethod
    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        """保存所有鉴权密钥数据"""
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """健康检查，返回存储后端状态"""
        pass

    @abstractmethod
    def get_backend_info(self) -> dict[str, Any]:
        """获取存储后端信息"""
        pass
