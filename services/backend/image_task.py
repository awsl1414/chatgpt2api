"""生图任务轮询、图片引用解析与下载。

职责：
- 轮询 conversation 文档直到出现图片文件 ID（含指数退避、settle 二次确认、
  内容政策违规检测），见 `poll_image_results`
- `/backend-api/tasks` 查询（`query_backend_tasks`）；结构化错误判定复用
  `services.protocol.message_content.check_task_error`
- 文件/附件下载 URL 解析（`resolve_image_urls`）与图片字节下载
供 services.protocol.image_stream 与 services.image_task_service 调用；
需要客户端状态的函数以 `api: BackendClient` 显式声明依赖。
"""

import random
import re
import time
from typing import Any

from curl_cffi import requests

from services.backend.context import BackendClient
from utils.collection import add_unique
from services.config import config
from services.errors import ImageContentPolicyError, ImagePollTimeoutError
from services.protocol.message_content import check_task_error
from utils.helper import UpstreamHTTPError, ensure_ok
from utils.log import logger
from utils.limits import DEFAULT_REQUEST_TIMEOUT_SECS, QUICK_QUERY_TIMEOUT_SECS

FILE_SERVICE_ID_RE = re.compile(r"file-service://([A-Za-z0-9_-]+)")# 真正的图片文件 ID 格式：file_00000000 + 24位十六进制字符（共32字符）
REAL_IMAGE_FILE_ID_RE = re.compile(r"\bfile_00000000[a-f0-9]{24}\b")
SEDIMENT_ID_RE = re.compile(r"sediment://([A-Za-z0-9_-]+)")

# 生成结果图片下载超时
IMAGE_DOWNLOAD_TIMEOUT_SECS = 120
# 图片轮询的默认总预算（秒），与 config 的 image_poll_timeout_secs 默认值一致
IMAGE_POLL_TIMEOUT_SECS = 120.0
# /backend-api/tasks 查询的默认请求超时（秒）
TASKS_QUERY_TIMEOUT_SECS = 30.0

# 内容政策违规错误关键词（上游拒绝生成图片的各种表述）
_CONTENT_POLICY_KEYWORDS = (
    # 明确的内容政策违规
    "内容政策", "防护限制", "违反", "moderation", "policy", "blocked",
    # 拒绝生成类
    "不能生成", "无法生成", "不能帮助", "无法帮助",
    # 敏感内容类
    "裸体", "裸露", "色情", "性内容", "未成年",
    # 通用拒绝
    "抱歉，我不能",
)


def is_content_policy_error(error_msg: str) -> bool:
    """检查错误消息是否为内容政策违规。"""
    if not error_msg:
        return False
    msg_lower = error_msg.lower()
    return any(keyword in msg_lower for keyword in _CONTENT_POLICY_KEYWORDS)



def extract_image_reference_ids(payload: Any) -> tuple[list[str], list[str]]:
    file_ids: list[str] = []
    sediment_ids: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            # 只提取真正的图片文件 ID（file_00000000... 格式）和 file-service:// URI
            add_unique(file_ids, FILE_SERVICE_ID_RE.findall(value))
            add_unique(file_ids, REAL_IMAGE_FILE_ID_RE.findall(value))
            add_unique(sediment_ids, SEDIMENT_ID_RE.findall(value))
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return file_ids, sediment_ids

def has_image_asset_pointer(payload: Any) -> bool:
    if isinstance(payload, dict):
        if str(payload.get("content_type") or "") == "image_asset_pointer":
            return True
        asset_pointer = str(payload.get("asset_pointer") or "")
        if asset_pointer.startswith(("file-service://", "sediment://")):
            return True
        return any(has_image_asset_pointer(item) for item in payload.values())
    if isinstance(payload, list):
        return any(has_image_asset_pointer(item) for item in payload)
    return False

def extract_image_tool_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    """从 conversation 明细里提取图片工具输出记录。"""
    mapping = data.get("mapping") or {}
    records = []
    for message_id, node in mapping.items():
        message = (node or {}).get("message") or {}
        author = message.get("author") or {}
        metadata = message.get("metadata") or {}
        content = message.get("content") or {}
        role = str(author.get("role") or "").strip().lower()
        if role not in {"tool", "assistant"}:
            continue
        is_image_gen = metadata.get("async_task_type") == "image_gen"
        has_asset_pointer = has_image_asset_pointer(content) or has_image_asset_pointer(metadata)
        if role == "assistant" and not (is_image_gen or has_asset_pointer):
            continue
        file_ids, sediment_ids = extract_image_reference_ids({"content": content, "metadata": metadata})
        if not is_image_gen and not has_asset_pointer and not file_ids and not sediment_ids:
            continue
        records.append(
            {"message_id": message_id, "create_time": message.get("create_time") or 0, "file_ids": file_ids,
             "sediment_ids": sediment_ids})
    return sorted(records, key=lambda item: item["create_time"])

def find_content_policy_error_in_conversation(data: dict[str, Any]) -> str:
    """从对话文档中查找内容政策违规错误消息。

    上游拒绝生成图片时，错误消息会出现在 assistant 消息的文本中。
    本方法遍历所有 assistant/tool 消息，检查是否包含内容政策违规关键词，
    如果匹配则返回该消息文本（截断至 500 字符），否则返回空字符串。
    """
    mapping = data.get("mapping") or {}
    for node in mapping.values():
        message = (node or {}).get("message") or {}
        author = message.get("author") or {}
        role = str(author.get("role") or "").strip().lower()
        if role not in {"assistant", "tool"}:
            continue
        content = message.get("content") or {}
        # 提取消息文本
        text_parts: list[str] = []
        if isinstance(content, dict):
            msg_parts = content.get("parts") or []
            if isinstance(msg_parts, list):
                for part in msg_parts:
                    if isinstance(part, str) and part.strip():
                        text_parts.append(part.strip())
            text_field = str(content.get("text") or "")
            if text_field.strip():
                text_parts.append(text_field.strip())
        elif isinstance(content, str) and content.strip():
            text_parts.append(content.strip())
        msg_text = "\n".join(text_parts)
        if msg_text and is_content_policy_error(msg_text):
            return msg_text[:500]
    return ""

def poll_image_results(
        api: BackendClient,
        conversation_id: str,
        timeout_secs: float = IMAGE_POLL_TIMEOUT_SECS,
        initial_file_ids: list[str] | None = None,
        initial_sediment_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Poll the conversation document until image file ids appear or budget runs out.

    - Sleeps image_poll_initial_wait_secs first (default 10s, +jitter). ChatGPT
      image generation takes ~30s; polling immediately wastes requests and trips
      a transient 429 the upstream returns within ~200ms of the SSE stream
      closing (the conversation document is not yet committed).
    - Subsequent polls are image_poll_interval_secs apart (default 10s).
    - On upstream 429 / 5xx or network errors, backs off exponentially
      (capped at 16s, +jitter) honoring Retry-After when present.
    - All sleeps stay within timeout_secs; on exhaustion raises ImagePollTimeoutError.
    """
    start = time.time()
    attempt = 0
    interval = float(config.image_poll_interval_secs)
    initial_wait = float(config.image_poll_initial_wait_secs)
    file_ids: list[str] = []
    sediment_ids: list[str] = []
    add_unique(file_ids, initial_file_ids or [])
    add_unique(sediment_ids, initial_sediment_ids or [])
    has_initial_ids = bool(file_ids or sediment_ids)
    last_hit_key: tuple[tuple[str, ...], tuple[str, ...]] | None = (
        (tuple(file_ids), tuple(sediment_ids)) if has_initial_ids else None
    )
    logger.info({
        "event": "image_poll_start",
        "conversation_id": conversation_id,
        "timeout_secs": timeout_secs,
        "initial_wait_secs": initial_wait,
        "interval_secs": interval,
        "initial_file_ids": file_ids,
        "initial_sediment_ids": sediment_ids,
    })

    def _remaining() -> float:
        return timeout_secs - (time.time() - start)

    if has_initial_ids and config.image_settle_enabled:
        settle_for = min(config.image_settle_secs, max(0.0, _remaining()))
        if settle_for > 0:
            time.sleep(settle_for)
    elif initial_wait > 0:
        jitter = random.uniform(0, min(2.0, initial_wait * 0.2))
        sleep_for = min(initial_wait + jitter, max(0.0, _remaining()))
        if sleep_for > 0:
            time.sleep(sleep_for)

    def _retry_sleep(reason: str, status_code: int | None, error: str | None, retry_after: int | None) -> bool:
        # retry_after=0 means "retry immediately" — must not be coerced via falsy check.
        # 指数退避：2^attempt 秒、指数封顶 4（即最长等待 16s）；有 Retry-After 时优先采用
        base = retry_after if retry_after is not None else min(2 ** min(attempt, 4), 16)
        backoff = base + random.uniform(0, 0.5)
        remaining = _remaining()
        if remaining <= 0:
            return False
        sleep_for = min(backoff, remaining)
        log_payload: dict[str, Any] = {
            "event": "image_poll_retry",
            "conversation_id": conversation_id,
            "attempt": attempt,
            "reason": reason,
            "sleep_secs": round(sleep_for, 2),
        }
        if status_code is not None:
            log_payload["status_code"] = status_code
        if error is not None:
            log_payload["error"] = error
        logger.warning(log_payload)
        time.sleep(sleep_for)
        return True

    last_task_error = ""
    while _remaining() > 0:
        attempt += 1
        # 在每次轮询时，检查 /backend-api/tasks/ 是否有错误（仅记录，不中断）
        # 内容政策违规检测通过对话文本进行（在 find_content_policy_error_in_conversation 中）
        last_task_error = ""
        try:
            tasks = query_backend_tasks(api, conversation_id=conversation_id, timeout_secs=QUICK_QUERY_TIMEOUT_SECS)
            for task in tasks:
                is_error, error_msg, metadata = check_task_error(task)
                if is_error and error_msg:
                    last_task_error = error_msg
                    logger.info({
                        "event": "image_poll_task_error_not_blocking",
                        "conversation_id": conversation_id,
                        "attempt": attempt,
                        "error_msg": error_msg,
                        "metadata": metadata,
                    })
        except Exception as exc:
            # tasks 查询失败不影响正常轮询流程
            logger.debug({
                "event": "image_poll_task_check_failed",
                "conversation_id": conversation_id,
                "attempt": attempt,
                "error": str(exc),
            })

        try:
            conversation = api._get_conversation(conversation_id)
        except UpstreamHTTPError as exc:
            if exc.status_code in (429, 500, 502, 503, 504):
                if _retry_sleep("upstream_status", exc.status_code, None, exc.retry_after):
                    continue
                break
            raise
        except requests.exceptions.RequestException as exc:
            if _retry_sleep("network", None, str(exc), None):
                continue
            break

        for record in extract_image_tool_records(conversation):
            for file_id in record["file_ids"]:
                if file_id not in file_ids:
                    file_ids.append(file_id)
            for sediment_id in record["sediment_ids"]:
                if sediment_id not in sediment_ids:
                    sediment_ids.append(sediment_id)

        # 检查对话文本中是否包含内容政策违规错误
        # 当上游拒绝生成图片时，错误消息会出现在对话文档的 assistant 消息中，
        # 而非 /backend-api/tasks/ 的 task error 结构中。
        # 如果在没有找到图片文件 ID 的同时检测到内容政策违规，立即中断轮询。
        if not file_ids and not sediment_ids:
            policy_msg = find_content_policy_error_in_conversation(conversation)
            if policy_msg:
                logger.warning({
                    "event": "image_poll_conversation_text_policy_violation",
                    "conversation_id": conversation_id,
                    "attempt": attempt,
                    "error_msg": policy_msg[:200],
                })
                raise ImageContentPolicyError(policy_msg, conversation_id or "")

        logger.debug({"event": "image_poll_check", "conversation_id": conversation_id, "attempt": attempt,
                      "file_ids": file_ids, "sediment_ids": sediment_ids})
        if file_ids or sediment_ids:
            if not config.image_check_before_hit_enabled:
                # 先check再hit 机制关闭：直接返回首次发现的 file_ids
                logger.info({"event": "image_poll_hit_no_settle", "conversation_id": conversation_id,
                             "file_ids": file_ids, "sediment_ids": sediment_ids})
                return file_ids, sediment_ids
            hit_key = (tuple(file_ids), tuple(sediment_ids))
            if last_hit_key == hit_key:
                logger.info({"event": "image_poll_hit", "conversation_id": conversation_id, "file_ids": file_ids,
                             "sediment_ids": sediment_ids})
                return file_ids, sediment_ids
            last_hit_key = hit_key
            if not config.image_settle_enabled:
                # 二次确认机制关闭：直接返回首次发现的 file_ids
                logger.info({"event": "image_poll_hit_settle_disabled", "conversation_id": conversation_id,
                             "file_ids": file_ids, "sediment_ids": sediment_ids})
                return file_ids, sediment_ids
            logger.info({"event": "image_poll_hit_pending_settle", "conversation_id": conversation_id,
                         "file_ids": file_ids, "sediment_ids": sediment_ids,
                         "settle_secs": config.image_settle_secs})
            wait = min(config.image_settle_secs, max(0.0, _remaining()))
            if wait > 0:
                time.sleep(wait)
                continue
            return file_ids, sediment_ids
        logger.debug({"event": "image_poll_wait", "conversation_id": conversation_id,
                      "elapsed_secs": round(time.time() - start, 1)})
        wait = min(interval, max(0.0, _remaining()))
        if wait > 0:
            time.sleep(wait)
    logger.info({
        "event": "image_poll_timeout",
        "conversation_id": conversation_id,
        "timeout_secs": timeout_secs,
        "attempts_made": attempt,
        # attempts_made == 0 means the initial_wait consumed the entire budget — no HTTP attempted.
        "initial_wait_exhausted_budget": attempt == 0,
        "last_task_error": last_task_error if last_task_error else None,
    })
    exc = ImagePollTimeoutError(
        f"ChatGPT 生图超时（已等待 {timeout_secs} 秒）。"
        f"当前超时阈值可在 config.json 中调大 image_poll_timeout_secs，"
        f"也可能是账号被限流或生图队列拥堵导致。",
        conversation_id or "",
    )
    if last_task_error:
        setattr(exc, "task_error", last_task_error)
    raise exc

def get_file_download_url(api: BackendClient, file_id: str) -> str:
    """获取文件下载地址。"""
    path = f"/backend-api/files/{file_id}/download"
    response = api.session.get(api.base_url + path, headers=api._headers(path, {"Accept": "application/json"}),
                                timeout=DEFAULT_REQUEST_TIMEOUT_SECS)
    ensure_ok(response, path)
    data = response.json()
    return data.get("download_url") or data.get("url") or ""

def get_attachment_download_url(api: BackendClient, conversation_id: str, attachment_id: str) -> str:
    """通过 conversation 附件接口获取下载地址。"""
    path = f"/backend-api/conversation/{conversation_id}/attachment/{attachment_id}/download"
    response = api.session.get(api.base_url + path, headers=api._headers(path, {"Accept": "application/json"}),
                                timeout=DEFAULT_REQUEST_TIMEOUT_SECS)
    ensure_ok(response, path)
    data = response.json()
    return data.get("download_url") or data.get("url") or ""

def query_backend_tasks(
    api: BackendClient,
    conversation_id: str = "",
    task_id: str = "",
    timeout_secs: float = TASKS_QUERY_TIMEOUT_SECS,
) -> list[dict[str, Any]]:
    """查询 /backend-api/tasks/ 接口获取异步任务状态和错误信息。

    参数：
    - `conversation_id`：可选。按 conversation_id 过滤任务。
    - `task_id`：可选。按 task_id 过滤任务。
    - `timeout_secs`：请求超时秒数。

    返回：
    - 任务列表，每个任务包含 image_gen_message 等字段。
    """
    path = "/backend-api/tasks"
    response = api.session.get(
        api.base_url + path,
        headers=api._headers(path, {"Accept": "application/json"}),
        timeout=timeout_secs,
    )
    ensure_ok(response, path)
    data = response.json()
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return []

    # 按 conversation_id 或 task_id 过滤
    if conversation_id:
        tasks = [
            t for t in tasks
            if isinstance(t, dict) and (
                t.get("conversation_id") == conversation_id
                or t.get("original_conversation_id") == conversation_id
            )
        ]
    if task_id:
        tasks = [t for t in tasks if isinstance(t, dict) and t.get("task_id") == task_id]
    return tasks

def resolve_image_urls(api: BackendClient, conversation_id: str, file_ids: list[str], sediment_ids: list[str]) -> list[str]:
    """把图片结果 id 解析成可下载 URL。"""
    urls = []
    skip_patterns = {"file_upload"}
    for file_id in file_ids:
        if file_id in skip_patterns:
            logger.debug({
                "event": "image_file_id_skipped",
                "source": "file",
                "conversation_id": conversation_id,
                "id": file_id,
            })
            continue
        try:
            url = api._get_file_download_url(file_id)
        except Exception as exc:
            logger.debug({
                "event": "image_download_url_failed",
                "source": "file",
                "conversation_id": conversation_id,
                "id": file_id,
                "error": repr(exc),
            })
            continue
        if url:
            if url not in urls:
                urls.append(url)
        else:
            logger.debug({
                "event": "image_download_url_empty",
                "source": "file",
                "conversation_id": conversation_id,
                "id": file_id,
            })
    if not conversation_id or not sediment_ids:
        logger.debug({
            "event": "image_urls_resolved",
            "conversation_id": conversation_id,
            "file_ids": file_ids,
            "sediment_ids": sediment_ids,
            "urls": urls,
        })
        return urls
    for sediment_id in sediment_ids:
        try:
            url = api._get_attachment_download_url(conversation_id, sediment_id)
        except Exception as exc:
            logger.debug({
                "event": "image_download_url_failed",
                "source": "sediment",
                "conversation_id": conversation_id,
                "id": sediment_id,
                "error": repr(exc),
            })
            continue
        if url:
            if url not in urls:
                urls.append(url)
        else:
            logger.debug({
                "event": "image_download_url_empty",
                "source": "sediment",
                "conversation_id": conversation_id,
                "id": sediment_id,
            })
    logger.debug({
        "event": "image_urls_resolved",
        "conversation_id": conversation_id,
        "file_ids": file_ids,
        "sediment_ids": sediment_ids,
        "urls": urls,
    })
    return urls

def resolve_conversation_image_urls(
        api: BackendClient,
        conversation_id: str,
        file_ids: list[str],
        sediment_ids: list[str],
        poll: bool = True,
        poll_timeout_secs: float | None = None,
) -> list[str]:
    file_ids = [item for item in file_ids if item != "file_upload"]
    sediment_ids = list(sediment_ids)
    timeout = poll_timeout_secs if poll_timeout_secs is not None else config.image_poll_timeout_secs
    # 当 check-before-hit 和 settle 均已关闭，且 SSE 已给出 file_ids 时，
    # 跳过轮询直接解析 URL，省去 initial_wait + 轮询耗时。
    if poll and conversation_id and (file_ids or sediment_ids):
        if not config.image_check_before_hit_enabled and not config.image_settle_enabled:
            logger.info({
                "event": "image_resolve_skip_poll_direct_resolve",
                "conversation_id": conversation_id,
                "file_ids": file_ids,
                "sediment_ids": sediment_ids,
            })
            return resolve_image_urls(api, conversation_id, file_ids, sediment_ids)
    if poll and conversation_id:
        logger.info({
            "event": "image_resolve_poll_needed",
            "conversation_id": conversation_id,
            "initial_file_ids": file_ids,
            "initial_sediment_ids": sediment_ids,
            "poll_timeout_secs": timeout,
        })
        try:
            polled_file_ids, polled_sediment_ids = poll_image_results(api, 
                conversation_id,
                timeout,
                file_ids,
                sediment_ids,
            )
        except ImagePollTimeoutError as exc:
            # 如果轮询超时且有 task error（如 moderation 拦截），抛出 ImageContentPolicyError
            # 而非 ImagePollTimeoutError，让调用方能区分真正的超时和上游拒绝
            task_error = getattr(exc, "task_error", "")
            if not file_ids and not sediment_ids:
                if task_error:
                    raise ImageContentPolicyError(task_error, conversation_id or "") from exc
                raise
            logger.warning({
                "event": "image_resolve_poll_partial_timeout",
                "conversation_id": conversation_id,
                "file_ids": file_ids,
                "sediment_ids": sediment_ids,
            })
        except Exception as exc:
            if not file_ids and not sediment_ids:
                raise
            logger.warning({
                "event": "image_resolve_poll_partial_error",
                "conversation_id": conversation_id,
                "file_ids": file_ids,
                "sediment_ids": sediment_ids,
                "error": repr(exc),
            })
        else:
            file_ids.extend(item for item in polled_file_ids if item and item not in file_ids)
            sediment_ids.extend(item for item in polled_sediment_ids if item and item not in sediment_ids)
    return resolve_image_urls(api, conversation_id, file_ids, sediment_ids)

def download_image_bytes(api: BackendClient, urls: list[str]) -> list[bytes]:
    images = []
    for url in urls:
        response = api.session.get(url, timeout=IMAGE_DOWNLOAD_TIMEOUT_SECS)
        ensure_ok(response, "image_download")
        if response.content not in images:
            images.append(response.content)
    return images
