"""统一时间口径工具（R3-L7）：UTC ISO8601 单一格式生成与宽松解析。

历史背景：存量数据存在两种时间形态——services 各域曾以**本地时间**写
``%Y-%m-%d %H:%M:%S``（logs/tasks/images/cpa/sub2api），account 域以
**UTC** 写同形字符串（``account.models.now_str``）。本模块统一新数据
口径为 UTC ISO8601（秒级、``Z`` 后缀），读取端一律经 :func:`parse_timestamp`
宽松解析兼容全部既有形态，不做存量数据回写迁移。

后缀选择 ``Z`` 的理由：JS ``new Date()`` 原生支持（前端任务列表/图片列表
直接吃该字符串）；Python 3.11+ ``fromisoformat`` 原生支持；与
``backup_service._iso_now`` 既有形态一致；项目内既有宽松读取端
（``account.models.parse_time``、``backup_service``）均已做 Z→+00:00 归一。
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """当前 UTC 时间的 ISO8601 字符串（秒级、``Z`` 后缀），如 ``2026-10-31T05:14:09Z``。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_iso_from_epoch(epoch_seconds: float) -> str:
    """把 Unix 时间戳转为与 :func:`utc_now_iso` 同格式的 UTC ISO8601 字符串。"""
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_timestamp(value: object, *, naive_as_local: bool = True) -> datetime | None:
    """宽松解析时间戳为带时区的 UTC datetime，无法解析时返回 ``None``。

    兼容形态：
    - 带 ``Z`` / ``+00:00`` 后缀的 ISO8601（新口径）
    - 无时区 naive ISO8601（``T`` 或空格分隔，含微秒）
    - ``%Y-%m-%d %H:%M:%S`` 与 date-only ``%Y-%m-%d``（存量）
    - 前端 ``new Date().toISOString()`` 产生的毫秒 ISO 形态

    naive 输入缺省按**本地时区**解释（对应存量本地时间写入）；account 域
    的 UTC naive 形态请继续使用 ``account.models.parse_time``（按 UTC 解释）。
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw[:len("2000-01-01 00:00:00")], fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        if naive_as_local:
            parsed = parsed.astimezone()
        else:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
