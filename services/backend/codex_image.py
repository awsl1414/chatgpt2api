"""Codex 生图链路（/backend-api/codex/responses）。

通过 urllib 直连 codex responses SSE 端点，驱动 image_generation 工具完成
生图/生图编辑，产出标准 responses 事件流；供
services.protocol.image_stream.stream_codex_image_outputs 消费。
要求账号 source_type 为 codex；需要客户端状态的函数以
`api: BackendClient` 显式声明依赖。
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from services.backend.context import BackendClient
from services.errors import CodexSourceAccountError
from services.protocol.prompt_plan import CODEX_RESPONSES_INSTRUCTIONS
from utils.helper import UpstreamHTTPError
from utils.jwt import decode_jwt_payload
from utils.log import logger

# Codex 生图请求与上游 HTTP 超时（长任务，far 大于常规请求）
CODEX_IMAGE_TIMEOUT_SECS = 1200



# 顶层模型：gpt-5.5 已被上游拒绝（400 model_not_found，2026-10-30 实测），
# gpt-6-luna 为 Codex CLI 现行值、实测 200（逆向仓库 docs/api/codex-image.md §5）
CODEX_RESPONSES_MODEL = "gpt-6-luna"



def codex_responses_headers(api: BackendClient, ) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api.access_token}",
        "Content-Type": "application/json",
    }

def ensure_codex_source_account(api: BackendClient, ) -> None:
    source_type = str((api.account or {}).get("source_type") or "web").strip().lower()
    if source_type != "codex":
        raise CodexSourceAccountError("codex responses endpoint requires a codex source account")

def codex_image_input(prompt: str, images: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for image in images:
        payload = image if image.startswith("data:image/") else f"data:image/png;base64,{image}"
        content.append({"type": "input_image", "image_url": payload})
    return [{"role": "user", "content": content}]

def codex_body_preview(body: Any, limit: int = 4000) -> str:
    if isinstance(body, (dict, list)):
        try:
            text = json.dumps(body, ensure_ascii=False)
        except Exception:
            text = repr(body)
    else:
        text = str(body or "")
    return text if len(text) <= limit else text[:limit] + "...[truncated]"

def codex_event_image_result_lengths(value: Any) -> list[int]:
    if isinstance(value, dict):
        lengths: list[int] = []
        if value.get("type") == "image_generation_call" and isinstance(value.get("result"), str):
            lengths.append(len(value["result"]))
        for item in value.values():
            lengths.extend(codex_event_image_result_lengths(item))
        return lengths
    if isinstance(value, list):
        lengths: list[int] = []
        for item in value:
            lengths.extend(codex_event_image_result_lengths(item))
        return lengths
    return []

def codex_event_summary(event: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": str(event.get("type") or ""),
        "keys": list(event.keys())[:30],
    }
    for key in ("id", "status", "sequence_number", "response_id", "item_id", "output_index", "content_index"):
        value = event.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
    for key in ("response", "item", "output"):
        value = event.get(key)
        if isinstance(value, dict):
            summary[f"{key}_type"] = value.get("type")
            summary[f"{key}_status"] = value.get("status")
            summary[f"{key}_keys"] = list(value.keys())[:30]
        elif isinstance(value, list):
            summary[f"{key}_len"] = len(value)
            summary[f"{key}_types"] = [
                item.get("type") for item in value[:10] if isinstance(item, dict)
            ]
    error = event.get("error")
    if isinstance(error, dict):
        summary["error"] = {
            key: error.get(key)
            for key in ("type", "code", "message")
            if error.get(key) is not None
        }
    delta = event.get("delta")
    if isinstance(delta, str):
        summary["delta_len"] = len(delta)
        summary["delta_preview"] = delta[:200]
    result_lengths = codex_event_image_result_lengths(event)
    if result_lengths:
        summary["image_result_lengths"] = result_lengths[:10]
    return summary

def log_codex_response_failure(
        api: BackendClient,
        path: str,
        status_code: int,
        headers: Any,
        payload: dict[str, Any],
        body: Any,
) -> None:
    request_headers = codex_responses_headers(api, )
    safe_request_headers = {
        key: value for key, value in request_headers.items() if key.lower() != "authorization"
    }
    response_headers = dict(headers.items()) if hasattr(headers, "items") else dict(headers or {})
    tool = ((payload.get("tools") or [{}])[0]) if isinstance(payload.get("tools"), list) else {}
    logger.warning({
        "event": "codex_responses_http_error",
        "path": path,
        "status_code": status_code,
        "request": {
            "model": payload.get("model"),
            "tool_model": tool.get("model"),
            "tool_action": tool.get("action"),
            "size": tool.get("size"),
            "quality": tool.get("quality"),
            "image_input_count": max(len((payload.get("input") or [{}])[0].get("content") or []) - 1, 0),
            "prompt_preview": codex_body_preview(
                (((payload.get("input") or [{}])[0].get("content") or [{}])[0].get("text") or ""),
                500,
            ),
            "headers": safe_request_headers,
        },
        "response": {
            "headers": response_headers,
            "body_preview": codex_body_preview(body),
        },
    })

def iter_codex_response_events(raw: Any) -> Iterator[dict[str, Any]]:
    content_type = str(raw.headers.get("content-type") or "").lower()
    text = raw.read().decode("utf-8", "replace")
    status_code = getattr(raw, "status", None)
    parse_errors: list[str] = []
    events: list[dict[str, Any]] = []
    if "application/json" in content_type:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                events.append(data)
        except Exception as exc:
            parse_errors.append(str(exc))
    else:
        lines: list[str] = []
        for line in text.splitlines() + [""]:
            if not line:
                if lines:
                    payload_text = "\n".join(lines).strip()
                    if payload_text and payload_text != "[DONE]":
                        try:
                            data = json.loads(payload_text)
                        except Exception as exc:
                            parse_errors.append(str(exc))
                            data = None
                        if isinstance(data, dict):
                            events.append(data)
                    lines = []
            elif line.startswith("data:"):
                lines.append(line[5:].lstrip())

    event_types: dict[str, int] = {}
    image_result_lengths: list[int] = []
    for event in events:
        event_type = str(event.get("type") or "<missing>")
        event_types[event_type] = event_types.get(event_type, 0) + 1
        image_result_lengths.extend(codex_event_image_result_lengths(event))
    logger.info({
        "event": "codex_responses_response_debug",
        "status_code": status_code,
        "content_type": content_type,
        "response_text_len": len(text),
        "event_count": len(events),
        "event_types": event_types,
        "image_result_lengths": image_result_lengths[:10],
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:5],
        "event_summaries": [codex_event_summary(event) for event in events[:30]],
        "event_previews": [
            codex_body_preview(event, 1500)
            for event in events[:10]
        ] if not image_result_lengths else [],
        "body_preview": text[:1000] if not events else "",
    })
    for event in events:
        yield event

def iter_codex_image_response_events(
        api: BackendClient,
        prompt: str,
        images: list[str] | None = None,
        size: str | None = None,
        quality: str = "auto",
        image_model: str = "gpt-image-2",
        instructions: str = CODEX_RESPONSES_INSTRUCTIONS,
) -> Iterator[dict[str, Any]]:
    """向 codex responses 端点发起一次生图请求并产出 SSE 事件。

    `instructions` 默认为固定英文常量；协议层通过
    `prompt_plan.render_codex_instructions(plan)` 传入「global system + 常量」，
    使 codex 链路也能读到管理端配置的 global_system_prompt。
    """
    if not api.access_token:
        raise RuntimeError("access_token is required for codex image endpoints")
    ensure_codex_source_account(api, )
    path = "/backend-api/codex/responses"
    payload = {
        "model": CODEX_RESPONSES_MODEL,
        "instructions": instructions or CODEX_RESPONSES_INSTRUCTIONS,
        "store": False,
        "input": codex_image_input(prompt, images or []),
        "tools": [{
            "type": "image_generation",
            "model": str(image_model or "gpt-image-2"),
            "action": "edit" if images else "generate",
            "size": str(size or "1024x1024"),
            "quality": str(quality or "auto"),
            "output_format": "png",
        }],
        "tool_choice": {"type": "image_generation"},
        "stream": True,
    }
    request = urllib.request.Request(
        api.base_url + path,
        json.dumps(payload).encode(),
        codex_responses_headers(api, ),
        method="POST",
    )
    account = api.account or {}
    token_payload = decode_jwt_payload(api.access_token)
    auth_claim = token_payload.get("https://api.openai.com/auth")
    auth_claim = auth_claim if isinstance(auth_claim, dict) else {}
    tool = payload["tools"][0]
    logger.info({
        "event": "codex_responses_request_debug",
        "url": api.base_url + path,
        "transport": "urllib.request",
        "timeout_secs": CODEX_IMAGE_TIMEOUT_SECS,
        "account_email": str(account.get("email") or "").strip(),
        "source_type": str(account.get("source_type") or "").strip(),
        "account_type": str(account.get("type") or "").strip(),
        "token_claims": {
            "jti": token_payload.get("jti"),
            "iat": token_payload.get("iat"),
            "exp": token_payload.get("exp"),
            "client_id": token_payload.get("client_id"),
            "chatgpt_account_id": auth_claim.get("chatgpt_account_id"),
            "chatgpt_plan_type": auth_claim.get("chatgpt_plan_type"),
            "localhost": auth_claim.get("localhost"),
        },
        "request": {
            "model": payload.get("model"),
            "tool_model": tool.get("model"),
            "tool_action": tool.get("action"),
            "size": tool.get("size"),
            "quality": tool.get("quality"),
            "output_format": tool.get("output_format"),
            "stream": payload.get("stream"),
            "image_input_count": max(len((payload.get("input") or [{}])[0].get("content") or []) - 1, 0),
            "prompt_preview": codex_body_preview(
                (((payload.get("input") or [{}])[0].get("content") or [{}])[0].get("text") or ""),
                500,
            ),
        },
        "headers": {
            key: value for key, value in codex_responses_headers(api, ).items()
            if key.lower() != "authorization"
        },
    })
    try:
        with urllib.request.urlopen(request, timeout=CODEX_IMAGE_TIMEOUT_SECS) as raw:
            yield from iter_codex_response_events(raw)
    except urllib.error.HTTPError as error:
        body_text = error.read().decode("utf-8", "replace")
        body: Any = body_text
        try:
            body = json.loads(body_text)
        except Exception:
            pass
        log_codex_response_failure(api, path, error.code, error.headers, payload, body)
        retry_after_header = error.headers.get("Retry-After") if error.headers else None
        retry_after = int(retry_after_header) if str(retry_after_header or "").isdigit() else None
        raise UpstreamHTTPError(path, error.code, body, retry_after=retry_after) from error
