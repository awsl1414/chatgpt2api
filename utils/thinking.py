"""思考强度（thinking effort）参数归一化。

`/v1/chat/completions`、`/v1/responses` 与 backend 请求体构造共用同一实现，
避免多处并行拷贝产生口径漂移（审查 R2-M3 / R3-M1 / R3-M2）。
"""

from __future__ import annotations

from typing import Any


def normalize_thinking_effort(value: object, *, passthrough_standard_max: bool = False) -> str:
    """把任意输入归一化为上游可接受的思考强度值。

    Args:
        value: 请求或配置中的原始值（可为 None / 任意类型）。
        passthrough_standard_max: 是否放行 `standard` / `max` 原样透传。
            backend payload 层（含 config.default_thinking_effort 消费点）
            传 True；对外 API 层保持缺省 False——未知值（含 standard/max）
            归一化为 ""，由调用方回退到 config 默认值。

    Returns:
        "" / "low" / "medium" / "high" / "extended"（或透传的 "standard" / "max"）。
    """
    normalized = str(value or "").strip().lower()
    if normalized in {"", "none", "auto"}:
        return ""
    if normalized in {"low", "medium", "high"}:
        return normalized
    if normalized in {"xhigh", "extended"}:
        return "extended"
    if passthrough_standard_max and normalized in {"standard", "max"}:
        return normalized
    return ""


def thinking_effort_from_body(body: dict[str, Any]) -> str:
    """从请求体提取思考强度，统一解析优先级：reasoning.effort > thinking_effort > reasoning_effort。

    `reasoning.effort` 是 OpenAI Responses 规范字段，优先级最高；
    `thinking_effort` 为本项目自定义扩展，`reasoning_effort` 为 chat
    completions 常见别名，仅作兜底。
    """
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict):
        return normalize_thinking_effort(reasoning.get("effort"))
    if "thinking_effort" in body:
        return normalize_thinking_effort(body.get("thinking_effort"))
    if "reasoning_effort" in body:
        return normalize_thinking_effort(body.get("reasoning_effort"))
    return ""
