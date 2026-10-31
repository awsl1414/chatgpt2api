"""统一时间口径（R3-L7，UTC ISO8601 单一口径）单测。

覆盖点：
- utc_now_iso / utc_iso_from_epoch：Z 后缀、秒级、与 UTC 时钟一致
- parse_timestamp 宽松解析：Z / +00:00 后缀、naive ISO（T 或空格分隔）、
  date-only、前端 toISOString 毫秒形态、非法输入返回 None；
  naive 缺省按本地时区解释（存量本地时间形态）、可切换按 UTC 解释
- 写入端抽查：image_task_service._timestamp 两种存量/新形态均得正确 epoch；
  log_service 日期过滤对新口径字符串的 day 切片兼容
- account.models.parse_time 对新口径 Z 后缀字符串保持兼容
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from services.image_task_service import _timestamp as task_timestamp
from services.log_service import LogService
from utils.clock import parse_timestamp, utc_iso_from_epoch, utc_now_iso

UTC_ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_utc_now_iso_format_and_clock():
    """新口径：秒级 ISO8601、Z 后缀、与 UTC 当前时间误差 < 5 秒。"""
    value = utc_now_iso()
    assert UTC_ISO_Z_RE.match(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is timezone.utc
    assert abs((datetime.now(timezone.utc) - parsed).total_seconds()) < 5


def test_utc_iso_from_epoch_fixed_value():
    """固定 epoch 转换结果稳定可预期（不随本机时区变化）。"""
    # 2026-10-31T05:14:09Z
    assert utc_iso_from_epoch(1793423649) == "2026-10-31T05:14:09Z"


def test_parse_timestamp_accepts_both_legacy_forms():
    """宽松解析兼容两种既有形态：naive 本地时间与 UTC 形态。"""
    local_form = "2026-10-31 14:30:00"
    expected_local = datetime.strptime(local_form, "%Y-%m-%d %H:%M:%S").astimezone()
    assert parse_timestamp(local_form) == expected_local.astimezone(timezone.utc)

    utc_naive_form = "2026-10-31 14:30:00"
    assert parse_timestamp(utc_naive_form, naive_as_local=False) == datetime(
        2026, 10, 31, 14, 30, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-31T05:14:09Z", datetime(2026, 10, 31, 5, 14, 9, tzinfo=timezone.utc)),
        ("2026-10-31T05:14:09+00:00", datetime(2026, 10, 31, 5, 14, 9, tzinfo=timezone.utc)),
        ("2026-10-31T05:14:09.123+08:00", datetime(2026, 10, 30, 21, 14, 9, 123000, tzinfo=timezone.utc)),
        ("2026-10-31T05:14:09.123456+08:00", datetime(2026, 10, 30, 21, 14, 9, 123456, tzinfo=timezone.utc)),
        ("2026-10-31T05:14:09", None),  # naive T 分隔：按本地解释，仅校验可解析性
        ("2026-10-31", None),  # date-only：按本地解释，仅校验可解析性
        ("2026-10-31T05:14:09.123Z", datetime(2026, 10, 31, 5, 14, 9, 123000, tzinfo=timezone.utc)),
        ("", None),
        ("not-a-time", None),
        (None, None),
        (12345, None),
    ],
)
def test_parse_timestamp_forms(raw, expected):
    parsed = parse_timestamp(raw)
    if raw in {"2026-10-31T05:14:09", "2026-10-31"}:
        # naive 无后缀：按本地时区解释，等值于本地时间转 UTC
        raw_text = str(raw)
        naive = datetime.fromisoformat(raw_text) if "T" in raw_text else datetime.strptime(raw_text, "%Y-%m-%d")
        assert parsed == naive.astimezone(timezone.utc)
    else:
        assert parsed == expected


def test_parse_timestamp_round_trip():
    """生成 → 解析往返保持同一时刻。"""
    first = utc_now_iso()
    parsed = parse_timestamp(first)
    assert parsed is not None
    assert utc_iso_from_epoch(parsed.timestamp()) == first


def test_task_timestamp_legacy_and_new_forms():
    """image_task_service._timestamp：存量本地 naive 与新 UTC Z 形态均得正确 epoch。"""
    legacy_local = "2026-10-31 14:30:00"
    expected = datetime.strptime(legacy_local, "%Y-%m-%d %H:%M:%S").astimezone().timestamp()
    assert task_timestamp(legacy_local) == expected
    assert task_timestamp("2026-10-31T05:14:09Z") == 1793423649.0
    assert task_timestamp("") == 0.0
    assert task_timestamp("garbage") == 0.0
    assert task_timestamp(None) == 0.0


def test_log_service_day_filter_accepts_utc_format():
    """logs 日期过滤（t[:10] day 切片）对新口径 Z 字符串兼容。"""
    item = {"time": "2026-10-31T05:14:09Z", "type": "调用完成"}
    assert LogService._matches_filters(item, start_date="2026-10-31", end_date="2026-10-31")
    assert not LogService._matches_filters(item, start_date="2026-11-01")
    assert not LogService._matches_filters(item, end_date="2026-10-30")


def test_account_parse_time_accepts_new_utc_format():
    """account.models.parse_time（naive 按 UTC）对新口径 Z 字符串保持兼容。"""
    from services.account.models import parse_time

    parsed = parse_time("2026-10-31T05:14:09Z")
    assert parsed == datetime(2026, 10, 31, 5, 14, 9, tzinfo=timezone.utc)
