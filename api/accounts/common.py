"""账号管理路由的公共支撑：后台任务调度与入参归一化工具。

拆分后各域子路由共用这两个能力（审计 B-中7）：
- ``spawn_background_task``：调度后台协程并持有强引用，避免任务被回收；
- ``unique_tokens`` / ``download_timestamp``：token 去重与导出文件名时间戳。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Coroutine

# 后台任务强引用集：asyncio.create_task 的返回值若不持有引用，
# 任务可能在完成前被垃圾回收（Python 官方文档明确警告），完成回调负责移除
_background_tasks: set[asyncio.Task[None]] = set()


def spawn_background_task(coro: Coroutine[Any, Any, None]) -> None:
    """调度后台协程并持有强引用直到其完成。"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def unique_tokens(tokens: list[str]) -> list[str]:
    """按原顺序去重并剔除空 token（保持拆分前的 dict.fromkeys 语义）。"""
    return list(dict.fromkeys(str(token or "").strip() for token in tokens if str(token or "").strip()))


def download_timestamp() -> str:
    """导出文件名时间戳（UTC，格式 YYYYMMDD-HHMMSS）。"""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
