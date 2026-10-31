"""列表去重追加等纯集合工具（无业务依赖，backend / protocol 共用）。

来源：services/protocol/event_parse.py 与 services/backend/search.py 曾各持
一份逐行相同的 `add_unique`（审查 R3-L1），现下沉为本模块统一实现。
"""

from __future__ import annotations


def add_unique(values: list[str], candidates: list[str]) -> None:
    """把 candidates 中非空且未出现的值追加进 values（原地修改）。"""
    for candidate in candidates:
        if candidate and candidate not in values:
            values.append(candidate)
