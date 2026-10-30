"""ChatGPT 网页搜索链路。

基于 `/backend-api/f/conversation` 的 search 会话发起一次网页搜索，
轮询对话文档直到答案稳定（或超时），并从 assistant 消息中提取答案与引用来源。
供 services.protocol.openai_search 调用；`walk_dicts` / `add_unique` 为
包内共享的纯工具函数。需要客户端状态的函数以 `api: BackendClient` 显式声明依赖。
"""

import json
import re
import time
from typing import Any

from services.backend.context import BackendClient
from utils.helper import ensure_ok, iter_sse_payloads, new_uuid

SEARCH_MODEL = "gpt-5-5"
SEARCH_TIMEOUT_SECS = 300.0
SEARCH_POLL_INTERVAL_SECS = 3.0
SEARCH_DONE_STATUS = {"finished_successfully", "finished_partial_completion"}
SEARCH_CONVERSATION_ID_RE = re.compile(r'"conversation_id"\s*:\s*"([^"]+)"')
SEARCH_URL_RE = re.compile(r"https?://[^\s\"'<>）)\]}]+")



def search(api: BackendClient, prompt: str, model: str = SEARCH_MODEL, timeout_secs: float = SEARCH_TIMEOUT_SECS,
           poll_interval_secs: float = SEARCH_POLL_INTERVAL_SECS) -> dict[str, Any]:
    if not api.access_token:
        raise RuntimeError("access_token is required for search")
    conduit_token = prepare_search_conversation(api, prompt, model)
    api._bootstrap()
    conversation_id = run_search_conversation(api, prompt, conduit_token, model)
    return wait_search_result(api, conversation_id, timeout_secs, poll_interval_secs)

def prepare_search_conversation(api: BackendClient, prompt: str, model: str) -> str:
    path = "/backend-api/f/conversation/prepare"
    response = api.session.post(
        api.base_url + path,
        headers=api._headers(path, {"Accept": "*/*", "Content-Type": "application/json", "X-Conduit-Token": "no-token"}),
        json={
            "action": "next",
            "fork_from_shared_post": False,
            "parent_message_id": "client-created-root",
            "model": model,
            "client_prepare_state": "success",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": ["search"],
            "partial_query": {"id": new_uuid(), "author": {"role": "user"}, "content": {"content_type": "text", "parts": [prompt]}},
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
        },
        timeout=60,
    )
    ensure_ok(response, path)
    token = str(response.json().get("conduit_token") or "")
    if not token:
        raise RuntimeError("missing conduit_token")
    return token

def run_search_conversation(api: BackendClient, prompt: str, conduit_token: str, model: str) -> str:
    requirements = api._get_chat_requirements()
    path = "/backend-api/f/conversation"
    response = api.session.post(
        api.base_url + path,
        headers=api._image_headers(path, requirements, conduit_token, "text/event-stream"),
        json={
            "action": "next",
            "messages": [{
                "id": new_uuid(),
                "author": {"role": "user"},
                "create_time": time.time(),
                "content": {"content_type": "text", "parts": [prompt]},
                "metadata": {
                    "developer_mode_connector_ids": [],
                    "selected_github_repos": [],
                    "selected_all_github_repos": False,
                    "system_hints": ["search"],
                    "serialization_metadata": {"custom_symbol_offsets": []},
                },
            }],
            "parent_message_id": "client-created-root",
            "model": model,
            "client_prepare_state": "success",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": True,
            "system_hints": [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "force_use_search": True,
            "client_reported_search_source": "conversation_composer_web_icon",
            "client_contextual_info": {"is_dark_mode": False, "time_since_loaded": 36, "page_height": 925, "page_width": 886, "pixel_ratio": 2, "screen_height": 1440, "screen_width": 2560, "app_name": "chatgpt.com"},
            "paragen_cot_summary_display_override": "allow",
            "force_parallel_switch": "auto",
        },
        timeout=300,
        stream=True,
    )
    ensure_ok(response, path)
    conversation_id = ""
    try:
        for payload in iter_sse_payloads(response):
            conversation_id = conversation_id or find_search_value(payload, "conversation_id")
            if payload == "[DONE]":
                break
    finally:
        response.close()
    if not conversation_id:
        raise RuntimeError("conversation_id not found in stream")
    return conversation_id

def wait_search_result(api: BackendClient, conversation_id: str, timeout_secs: float, poll_interval_secs: float) -> dict[str, Any]:
    deadline = time.time() + timeout_secs
    last_result: dict[str, Any] | None = None
    last_answer = ""
    stable_hits = 0
    while time.time() < deadline:
        try:
            last_result = extract_search_result(conversation_id, get_search_conversation(api, conversation_id))
        except UpstreamHTTPError as exc:
            if exc.status_code not in {404, 409, 423, 429, 500, 502, 503, 504}:
                raise
        if last_result and last_result.get("answer"):
            if last_result.get("status") in SEARCH_DONE_STATUS:
                return last_result
            answer = str(last_result.get("answer") or "")
            stable_hits = stable_hits + 1 if answer == last_answer else 0
            last_answer = answer
            if stable_hits >= 2:
                return last_result
        time.sleep(poll_interval_secs)
    if last_result:
        return last_result
    raise RuntimeError(f"timed out waiting for search result: {conversation_id}")

def get_search_conversation(api: BackendClient, conversation_id: str) -> dict[str, Any]:
    path = f"/backend-api/conversation/{conversation_id}"
    headers = api._headers(path, {"Accept": "*/*"})
    headers["Referer"] = f"{api.base_url}/c/{conversation_id}"
    headers["X-OpenAI-Target-Route"] = "/backend-api/conversation/{conversation_id}"
    response = api.session.get(api.base_url + path, headers=headers, timeout=60)
    ensure_ok(response, path)
    return response.json()

def extract_search_result(conversation_id: str, conversation: dict[str, Any]) -> dict[str, Any]:
    messages = []
    for node in (conversation.get("mapping") or {}).values():
        message = (node or {}).get("message") or {}
        if ((message.get("author") or {}).get("role") or "") == "assistant":
            messages.append(message)
    message = max(messages, key=lambda item: float(item.get("create_time") or 0.0)) if messages else {}
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    finish_details = metadata.get("finish_details") if isinstance(metadata.get("finish_details"), dict) else {}
    answer = search_message_text(message)
    sources = extract_search_sources(message)
    for url in SEARCH_URL_RE.findall(answer):
        url = clean_search_url(url)
        if url and all(item["url"] != url for item in sources):
            sources.append({"title": "", "url": url, "snippet": "", "source_type": ""})
    return {
        "conversation_id": conversation_id,
        "status": str(finish_details.get("type") or metadata.get("status") or find_search_value(message, "status") or "").strip(),
        "answer": answer,
        "sources": sources,
        "assistant_message_id": str(message.get("id") or ""),
        "create_time": float(message.get("create_time") or 0.0),
    }

def extract_search_sources(payload: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for obj in walk_dicts(payload):
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        url = clean_search_url(obj.get("url") or obj.get("link") or obj.get("source_url") or metadata.get("url"))
        if url and all(item["url"] != url for item in sources):
            sources.append({
                "title": str(obj.get("title") or obj.get("name") or obj.get("source") or "").strip(),
                "url": url,
                "snippet": str(obj.get("snippet") or obj.get("text") or obj.get("description") or "").strip(),
                "source_type": str(obj.get("type") or obj.get("source_type") or "").strip(),
            })
    return sources

def search_message_text(message: Any) -> str:
    content = message.get("content") if isinstance(message, dict) else {}
    parts = []
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            parts.append(content["text"])
        for part in content.get("parts") or []:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.extend(str(part.get(key) or "") for key in ("text", "summary", "content") if part.get(key))
    elif isinstance(content, str):
        parts.append(content)
    return "\n".join(part.strip() for part in parts if str(part).strip()).strip()

def find_search_value(payload: Any, key: str) -> str:
    if isinstance(payload, str):
        match = SEARCH_CONVERSATION_ID_RE.search(payload) if key == "conversation_id" else None
        if match:
            return match.group(1)
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return ""
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        return next((found for item in payload.values() if (found := find_search_value(item, key))), "")
    if isinstance(payload, list):
        return next((found for item in payload if (found := find_search_value(item, key))), "")
    return ""

def walk_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload, *(item for value in payload.values() for item in walk_dicts(value))]
    if isinstance(payload, list):
        return [item for value in payload for item in walk_dicts(value)]
    return []

def clean_search_url(value: Any) -> str:
    return str(value or "").strip().rstrip(".,;，。；")

def add_unique(values: list[str], candidates: list[str]) -> None:
    for candidate in candidates:
        if candidate and candidate not in values:
            values.append(candidate)
