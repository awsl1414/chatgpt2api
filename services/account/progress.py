"""泛型进度追踪器（审计 B-高3）。

合并原 account_service 中两套几乎重复的进度追踪（refresh 6 方法 + relogin
6 方法，共 12 个方法）为一个可配置的 ``ProgressTracker``：

- 差异点全部参数化：初始状态由 ``build_initial(total)`` 构造；单条进度如何
  写入由 ``apply_update(progress, payload)`` 决定；relogin 侧「处理数达到
  总数即自动完成」由 ``auto_complete`` 开关表达。
- 线程语义与原实现一致：每条进度一个互斥锁；``get`` 返回浅拷贝。

具体实例（refresh 的状态计数/额度累加、relogin 的结果列表与 token 匿名化）
由组装层 services/account_service.py 以闭包配置。
"""
from __future__ import annotations

from threading import Lock
from typing import Any, Callable

# 初始状态构造：build_initial(total) -> dict
BuildInitial = Callable[[int], dict]
# 单条进度写入：apply_update(progress, payload) -> None（processed 计数由本类统一维护）
ApplyUpdate = Callable[[dict, Any], None]


class ProgressTracker:
    """按 progress_id 追踪一批任务的处理进度（线程安全）。"""

    def __init__(
        self,
        *,
        build_initial: BuildInitial,
        apply_update: ApplyUpdate | None = None,
        auto_complete: bool = False,
    ):
        self._build_initial = build_initial
        self._apply_update = apply_update
        self._auto_complete = auto_complete
        self._lock = Lock()
        self._items: dict[str, dict] = {}

    def start(self, progress_id: str, total: int) -> None:
        """初始化一条进度记录。"""
        with self._lock:
            self._items[progress_id] = self._build_initial(total)

    def update(self, progress_id: str, payload: Any) -> None:
        """记录单个任务处理完成；``processed`` 计数自动累加。"""
        with self._lock:
            progress = self._items.get(progress_id)
            if progress is None:
                return
            progress["processed"] += 1
            if self._apply_update is not None:
                self._apply_update(progress, payload)
            if self._auto_complete and progress["processed"] >= progress["total"]:
                progress["done"] = True

    def finish(self, progress_id: str, result: dict | None = None, error: str | None = None) -> None:
        """标记整批任务完成（可附带汇总结果或错误）。"""
        with self._lock:
            progress = self._items.get(progress_id)
            if progress is None:
                return
            progress["done"] = True
            progress["result"] = result
            if error:
                progress["error"] = error

    def get(self, progress_id: str) -> dict | None:
        """查询进度副本；不存在时返回 None。"""
        with self._lock:
            progress = self._items.get(progress_id)
            return dict(progress) if progress else None

    def clean(self, progress_id: str) -> None:
        """清理进度记录。"""
        with self._lock:
            self._items.pop(progress_id, None)
