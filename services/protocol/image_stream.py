"""协议层生图流编排。

承载从生图对话 SSE 流到图片结果产出的完整编排：
- `stream_image_outputs`：消费 `conversation_events` 事件流，准备对话、
  轮询图片、组装结果。主函数只保留编排骨架，四段各自下沉为模块内私有函数
  （`_progress_output_for_event` / `_resolve_stream_state` /
  `_first_poll_image_urls` / `_message_branch_outputs` / `_fallback_outputs`）；
- `_generate_single_image`：单图重试编排（取号 / 单图轮询等待 / 结果转储 /
  异常分类重试四段下沉为私有函数），`stream_image_outputs_with_pool` 负责并发编排；
- `stream_codex_image_outputs`：codex 生图流。

存储职责剥离（审计 B-中5）：本模块不直接依赖图片存储服务，
图片落盘/上传通过 `set_image_saver` 注入回调完成，由上层组装入口
（`api/app.create_app`）负责注入。
"""
from __future__ import annotations

import base64
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

from services.account_service import account_service
from services.backend.image_task import check_task_error
from services.config import config
from services.errors import (
    ImageContentPolicyError,
    ImageGenerationError,
    ImagePollTimeoutError,
    QuotaExhaustedError,
    image_stream_error_message,
    is_connection_timeout_error,
    is_token_invalid_error,
    is_tls_connection_error,
)
from services.openai_backend_api import OpenAIBackendAPI
from services.protocol.event_parse import conversation_events
from services.protocol.message_utils import ConversationRequest
from services.protocol.prompt_plan import (
    PromptPlan,
    build_prompt_plan,
    render_codex_instructions,
)
from utils.helper import (
    IMAGE_MODELS,
    codex_image_tool_model,
    is_codex_image_model,
    is_supported_image_model,
    split_image_model,
)
from utils.log import logger

REFERENCED_IMAGE_IDS_RE = re.compile(r'"referenced_image_ids"\s*:\s*\[([^\]]+)\]')
# 检测模型返回的部分工具调用 JSON（如 {"size":"1920x1088","n":1}）
# 这些 JSON 包含图片生成工具的参数，但没有实际生成图片
TOOL_PARAMS_JSON_RE = re.compile(
    r'\{\s*"size"\s*:\s*"\d+x\d+"\s*,\s*"n"\s*:\s*\d+\s*\}'
)

# 图片落盘/上传回调：`(图片字节, base_url) -> 可访问 URL`。
# 由上层组装入口通过 set_image_saver 注入，协议层不直接依赖存储实现。
ImageSaver = Callable[[bytes, str | None], str]
_image_saver: ImageSaver | None = None


def set_image_saver(saver: ImageSaver | None) -> None:
    """注入图片落盘/上传回调（审计 B-中5：protocol 层不直接依赖存储服务）。

    必须在应用组装时（`api.app.create_app`）调用；未注入时调用
    `save_image_bytes` 会抛出 RuntimeError。
    """
    global _image_saver
    _image_saver = saver


def save_image_bytes(image_data: bytes, base_url: str | None = None) -> str:
    """把图片字节落盘/上传，返回可访问 URL（动作由注入的回调执行）。"""
    if _image_saver is None:
        raise RuntimeError(
            "image saver 未注入：请在应用组装入口调用 "
            "services.protocol.image_stream.set_image_saver()"
        )
    return _image_saver(image_data, base_url)


def is_model_text_reply_instead_of_image(message: str) -> bool:
    """检测模型是否返回了文本回复（包含工具调用 JSON）而非实际生成图片。

    当上游 ChatGPT 未能触发图片生成工具时，会返回一段描述性文本，
    其中可能包含 JSON 参数（如 prompt、referenced_image_ids、size/n 等）。
    这种情况应被视为「上游未生成图片」而非「内容策略违规」。

    检测两种模式：
    1. 完整的工具调用 JSON（含 referenced_image_ids）
    2. 部分的工具参数 JSON（如 {"size":"1920x1088","n":1}）
    """
    if not message:
        return False
    if REFERENCED_IMAGE_IDS_RE.search(message):
        return True
    # 检测部分工具参数 JSON（模型返回了工具参数但未触发工具）
    if TOOL_PARAMS_JSON_RE.search(message):
        return True
    return False


def format_image_result(
    items: list[dict[str, Any]],
    prompt: str,
    response_format: str,
    base_url: str | None = None,
    created: int | None = None,
    message: str = "",
) -> dict[str, Any]:
    """把 b64 图片条目组装为图片 API 响应结构，图片字节经注入回调落盘后填入 url。"""
    data: list[dict[str, Any]] = []
    for item in items:
        b64_json = str(item.get("b64_json") or "").strip()
        if not b64_json:
            continue
        revised_prompt = str(item.get("revised_prompt") or prompt).strip() or prompt
        if response_format == "b64_json":
            data.append({
                "b64_json": b64_json,
                "url": save_image_bytes(base64.b64decode(b64_json), base_url),
                "revised_prompt": revised_prompt,
            })
        else:
            data.append({
                "url": save_image_bytes(base64.b64decode(b64_json), base_url),
                "revised_prompt": revised_prompt,
            })
    result: dict[str, Any] = {"created": created or int(time.time()), "data": data}
    if message and not data:
        result["message"] = message
    return result


@dataclass
class ImageOutput:
    """生图流产出的统一输出事件（progress / message / result）。"""

    kind: str
    model: str
    index: int
    total: int
    created: int = field(default_factory=lambda: int(time.time()))
    text: str = ""
    upstream_event_type: str = ""
    data: list[dict[str, Any]] = field(default_factory=list)
    account_email: str = ""
    conversation_id: str = ""

    def to_chunk(self) -> dict[str, Any]:
        """转换为流式响应 chunk 字典（image.generation.* 对象）。"""
        chunk: dict[str, Any] = {
            "object": "image.generation.chunk",
            "created": self.created,
            "model": self.model,
            "index": self.index,
            "total": self.total,
            "progress_text": self.text,
            "upstream_event_type": self.upstream_event_type,
            "data": [],
        }
        if self.account_email:
            chunk["_account_email"] = self.account_email
        if self.conversation_id:
            chunk["_conversation_id"] = self.conversation_id
        if self.kind == "message":
            chunk.update({
                "object": "image.generation.message",
                "message": self.text,
            })
            chunk.pop("progress_text", None)
            chunk.pop("upstream_event_type", None)
        elif self.kind == "result":
            chunk.update({
                "object": "image.generation.result",
                "data": self.data,
            })
            chunk.pop("progress_text", None)
            chunk.pop("upstream_event_type", None)
        return chunk


def _get_detailed_error_from_tasks(
    backend: OpenAIBackendAPI,
    conversation_id: str,
    timeout_secs: float = 10.0,
    wait_secs: float = 2.0,
) -> str:
    """从 /backend-api/tasks/ 接口获取结构化错误信息。

    当 SSE 流检测到 moderation 拦截时，轮询 tasks 接口获取详细错误文本。
    使用结构化字段（metadata.is_error, author.role, content.content_type）判断，
    而非依赖易变的文本匹配。

    参数：
    - `backend`：OpenAIBackendAPI 实例。
    - `conversation_id`：会话 ID。
    - `timeout_secs`：请求超时秒数。
    - `wait_secs`：等待任务创建的秒数。设为 0 可跳过等待。

    返回：
    - 详细错误信息文本，如果未找到则返回空字符串。
    """
    try:
        if wait_secs > 0:
            time.sleep(wait_secs)
        tasks = backend._query_backend_tasks(conversation_id=conversation_id, timeout_secs=timeout_secs)
        if not tasks:
            return ""

        for task in tasks:
            is_error, error_msg, metadata = check_task_error(task)
            if is_error and error_msg:
                logger.info({
                    "event": "image_task_structured_error",
                    "conversation_id": conversation_id,
                    "error_msg": error_msg,
                    "metadata": metadata,
                })
                return error_msg
        return ""
    except Exception as exc:
        logger.warning({
            "event": "image_task_error_query_failed",
            "conversation_id": conversation_id,
            "error": str(exc),
        })
        return ""


def _remove_image_conversation_later(
        backend: OpenAIBackendAPI,
        conversation_id: str,
        *,
        success: bool,
) -> None:
    """按配置在后台线程删除图片会话，失败只记日志不影响主流程。"""
    if not conversation_id:
        return
    if not (config.image_remove_conversation_always or (success and config.image_remove_conversation_after_result)):
        return

    def _run() -> None:
        try:
            backend.delete_conversation(conversation_id)
            logger.info({"event": "image_conversation_removed", "conversation_id": conversation_id})
        except Exception as exc:
            logger.warning({
                "event": "image_conversation_remove_failed",
                "conversation_id": conversation_id,
                "error": str(exc),
            })

    threading.Thread(target=_run, name=f"remove-image-conversation-{conversation_id}", daemon=True).start()


def _recover_conversation_id(
    backend: OpenAIBackendAPI,
    prompt: str,
    *,
    recovered_event: str,
    failed_event: str,
    message_preview: str = "",
) -> str:
    """conversation_id 丢失时，按 prompt 从最近对话列表恢复；失败返回空串。

    SSE 流太短时（模型返回文本而非触发图片工具）会话 ID 可能未被捕获，
    但图片已在上游异步生成，此时通过列出最近对话恢复。
    """
    try:
        recovered_id = backend.find_conversation_by_prompt(prompt, time.time(), timeout_secs=5.0)
    except Exception as exc:
        logger.warning({
            "event": failed_event,
            "error": repr(exc)[:300],
        })
        return ""
    if not recovered_id:
        return ""
    payload: dict[str, Any] = {"event": recovered_event, "conversation_id": recovered_id}
    if message_preview:
        payload["message_preview"] = message_preview
    logger.info(payload)
    return recovered_id


def _poll_image_results_with_retry(
    backend: OpenAIBackendAPI,
    conversation_id: str,
    file_ids: list[str],
    sediment_ids: list[str],
    *,
    retry_poll_timeout: int,
    max_retries: int,
    log_prefix: str,
    wait_before_attempt: Callable[[int], float] | None = None,
) -> None:
    """轮询上游图片结果，失败按递增退避重试（原地扩充 file_ids / sediment_ids）。

    - `wait_before_attempt`：每轮尝试前的等待秒数工厂；返回值 > 0 时以
      `{log_prefix}_after_wait` 记录等待日志并 sleep。
    - 失败时记录 `{log_prefix}_poll_failed`；若仍有剩余次数且不是超时/
      内容违规错误，记录 `{log_prefix}_poll_retry` 并按 30s*次数 退避后
      重试，否则终止（结果通过 file_ids / sediment_ids 是否扩充体现）。
    """
    for poll_attempt in range(1, max_retries + 1):
        wait_secs = wait_before_attempt(poll_attempt) if wait_before_attempt else 0.0
        if wait_secs > 0:
            logger.info({
                "event": f"{log_prefix}_after_wait",
                "conversation_id": conversation_id,
                "retry_wait_secs": wait_secs,
                "poll_attempt": poll_attempt,
            })
            time.sleep(wait_secs)
        try:
            polled_file_ids, polled_sediment_ids = backend._poll_image_results(
                conversation_id,
                retry_poll_timeout,
                file_ids,
                sediment_ids,
            )
            file_ids.extend(item for item in polled_file_ids if item and item not in file_ids)
            sediment_ids.extend(item for item in polled_sediment_ids if item and item not in sediment_ids)
            return  # 轮询成功，退出重试循环
        except Exception as exc:
            error_str = str(exc)
            is_transient = (
                isinstance(exc, ImagePollTimeoutError)
                or is_tls_connection_error(error_str)
                or "upstream" in error_str.lower()
                or "connection" in error_str.lower()
                or "timeout" in error_str.lower()
            )
            logger.warning({
                "event": f"{log_prefix}_poll_failed",
                "conversation_id": conversation_id,
                "poll_attempt": poll_attempt,
                "error": repr(exc)[:300],
                "is_transient": is_transient,
            })
            # 如果还有重试次数且不是超时/内容违规错误，继续重试（递增退避：30s, 60s, 90s）
            if poll_attempt < max_retries and not isinstance(exc, (ImagePollTimeoutError, ImageContentPolicyError)):
                backoff = 30.0 * poll_attempt
                logger.info({
                    "event": f"{log_prefix}_poll_retry",
                    "conversation_id": conversation_id,
                    "poll_attempt": poll_attempt,
                    "backoff_secs": backoff,
                })
                time.sleep(backoff)
                continue
            # 超时错误或重试次数用尽，停止重试
            return


def _build_image_result(
    backend: OpenAIBackendAPI,
    request: ConversationRequest,
    image_urls: list[str],
    conversation_id: str,
    index: int,
    total: int,
) -> ImageOutput | None:
    """结果组装段：下载图片字节并组装为 result 类型 ImageOutput，无有效数据返回 None。"""
    if request.progress_callback:
        request.progress_callback("receiving_image")
    image_items = [
        {"b64_json": base64.b64encode(image_data).decode("ascii")}
        for image_data in backend.download_image_bytes(image_urls)
    ]
    data = format_image_result(
        image_items,
        request.prompt,
        request.response_format,
        request.base_url,
        int(time.time()),
    )["data"]
    if data:
        return ImageOutput(kind="result", model=request.model, index=index, total=total, data=data, conversation_id=conversation_id)
    return None


@dataclass
class _StreamState:
    """`stream_image_outputs` 轮询前置判定段的产物，供后续轮询与结果组装复用。"""

    conversation_id: str
    file_ids: list[str]
    sediment_ids: list[str]
    message: str
    should_poll_for_image: bool
    is_text_reply: bool
    poll_timeout: int


def _progress_output_for_event(
    event: dict[str, Any],
    request: ConversationRequest,
    index: int,
    total: int,
) -> ImageOutput | None:
    """把单条 SSE 事件映射为进度 ImageOutput；非进度事件返回 None。

    仅做映射，不消费事件流——进度事件的产出时序由调用方逐条 yield 决定。
    """
    if event.get("type") == "conversation.delta":
        return ImageOutput(
            kind="progress",
            model=request.model,
            index=index,
            total=total,
            text=str(event.get("delta") or ""),
            upstream_event_type="conversation.delta",
            conversation_id=str(event.get("conversation_id") or ""),
        )
    if event.get("type") == "conversation.event":
        raw = event.get("raw")
        raw_type = str(raw.get("type") or "") if isinstance(raw, dict) else ""
        return ImageOutput(
            kind="progress",
            model=request.model,
            index=index,
            total=total,
            upstream_event_type=raw_type,
            conversation_id=str(event.get("conversation_id") or ""),
        )
    return None


def _resolve_stream_state(
    backend: OpenAIBackendAPI,
    request: ConversationRequest,
    last: dict[str, Any],
    index: int,
    total: int,
) -> tuple[_StreamState | None, ImageOutput | None]:
    """轮询前置判定段：解析会话状态、识别文本回复、恢复会话 ID 并做 tasks 预检。

    返回 `(state, short_circuit)`：
    - `short_circuit` 非 None 时表示应直接产出该 message 事件并结束，`state` 为 None；
    - 否则 `state` 给出后续轮询所需的会话 ID、文件 ID 与超时配置。
    """
    conversation_id = str(last.get("conversation_id") or "")
    file_ids = [str(item) for item in last.get("file_ids") or []]
    sediment_ids = [str(item) for item in last.get("sediment_ids") or []]
    message = str(last.get("text") or "").strip()
    logger.info({
        "event": "image_stream_resolve_start",
        "conversation_id": conversation_id,
        "file_ids": file_ids,
        "sediment_ids": sediment_ids,
        "tool_invoked": last.get("tool_invoked"),
        "turn_use_case": last.get("turn_use_case"),
    })
    if request.progress_callback:
        request.progress_callback("image_stream_resolve_start")
    if message and not file_ids and not sediment_ids and last.get("blocked"):
        # 尝试从 /backend-api/tasks/ 获取详细错误信息
        detailed_error = _get_detailed_error_from_tasks(backend, conversation_id)
        error_text = detailed_error or message or "Image generation was rejected by upstream policy."
        return None, ImageOutput(kind="message", model=request.model, index=index, total=total, text=error_text, conversation_id=conversation_id)
    should_poll_for_image = bool(request.images) or last.get("turn_use_case") == "image gen"
    if message and not file_ids and not sediment_ids and not should_poll_for_image:
        return None, ImageOutput(kind="message", model=request.model, index=index, total=total, text=message, conversation_id=conversation_id)

    # 检测模型是否返回了文本描述（含 referenced_image_ids）而非实际生成图片
    # 这说明模型已发起图片生成工具调用，但 SSE 在工具完成前断开，
    # 图片可能正在异步生成中。需要使用更积极的轮询策略来获取结果。
    is_text_reply = bool(message and is_model_text_reply_instead_of_image(message))
    if is_text_reply:
        logger.info({
            "event": "image_detected_text_reply_with_ids",
            "conversation_id": conversation_id,
            "message_preview": message[:200],
        })

    # 当检测到文本回复但 conversation_id 丢失时，尝试从最近对话列表中恢复
    if is_text_reply and not conversation_id:
        conversation_id = _recover_conversation_id(
            backend, request.prompt,
            recovered_event="image_conversation_id_recovered",
            failed_event="image_conversation_id_recovery_failed",
            message_preview=message[:200],
        ) or conversation_id

    # 在轮询图片之前，先检查 /backend-api/tasks/ 是否有 moderation 拦截
    # 这样可以避免不必要的长时间轮询超时
    # 注意：当 should_poll_for_image 为 True 或检测到文本回复时，
    # 即使 tasks 报告了"错误"，也不能直接返回——因为上游可能将工具调用的 JSON 参数
    # （如 {"size":"1792x1024","n":1}）标记为 is_error，而实际上图片正在异步生成中。
    # 此时应继续轮询图片。
    detailed_error = ""
    if not file_ids and not sediment_ids and conversation_id:
        detailed_error = _get_detailed_error_from_tasks(backend, conversation_id, timeout_secs=5.0, wait_secs=1.0)
        if detailed_error and not should_poll_for_image and not is_text_reply:
            logger.info({
                "event": "image_task_error_before_poll",
                "conversation_id": conversation_id,
                "error": detailed_error,
            })
            return None, ImageOutput(kind="message", model=request.model, index=index, total=total, text=detailed_error, conversation_id=conversation_id)
        if detailed_error and (should_poll_for_image or is_text_reply):
            logger.info({
                "event": "image_task_error_skipped_for_poll",
                "conversation_id": conversation_id,
                "error": detailed_error,
            })

    # 当检测到文本回复（含 referenced_image_ids）时，使用更长的超时来轮询图片结果。
    # 因为上游可能将图片生成作为异步任务执行，SSE 流在工具完成前就断开了，
    # 导致对话文档中尚未写入图片工具的响应记录。
    poll_timeout = config.image_poll_timeout_secs
    if is_text_reply and conversation_id:
        # 文本回复场景下图片可能仍在异步生成，使用更长超时（默认 120s → 额外 180s = 300s）
        poll_timeout = max(poll_timeout, 300)
        logger.info({
            "event": "image_text_reply_extended_poll",
            "conversation_id": conversation_id,
            "poll_timeout_secs": poll_timeout,
        })

    return _StreamState(
        conversation_id=conversation_id,
        file_ids=file_ids,
        sediment_ids=sediment_ids,
        message=message,
        should_poll_for_image=should_poll_for_image,
        is_text_reply=is_text_reply,
        poll_timeout=poll_timeout,
    ), None


def _first_poll_image_urls(backend: OpenAIBackendAPI, state: _StreamState) -> list[str]:
    """首次轮询解析图片 URL；文本回复场景下的内容策略/网络错误降级为空列表。"""
    try:
        return backend.resolve_conversation_image_urls(
            state.conversation_id, state.file_ids, state.sediment_ids, poll_timeout_secs=state.poll_timeout,
        )
    except (ImageContentPolicyError, ImagePollTimeoutError) as exc:
        # 当检测到文本回复时，task error 不应直接判定为内容策略违规，
        # 因为图片可能仍在后台异步生成中
        if state.is_text_reply and isinstance(exc, ImageContentPolicyError):
            logger.warning({
                "event": "image_text_reply_task_error_ignored",
                "conversation_id": state.conversation_id,
                "error": str(exc),
            })
            return []
        raise
    except Exception as exc:
        # 当检测到文本回复时，首次轮询的临时网络错误不应直接中断，
        # 因为图片可能仍在后台异步生成中，后续 retry poll 会继续尝试。
        if state.is_text_reply and state.conversation_id:
            logger.warning({
                "event": "image_text_reply_first_poll_error_ignored",
                "conversation_id": state.conversation_id,
                "error": repr(exc)[:300],
            })
            return []
        raise


def _message_branch_outputs(
    backend: OpenAIBackendAPI,
    request: ConversationRequest,
    state: _StreamState,
    index: int,
    total: int,
) -> Iterator[ImageOutput]:
    """结果组装段（有 message 时）：文本回复场景再尝试轮询，最终产出 message 或 result。

    产出顺序与拆分前完全一致：先尝试拿到 result，拿不到再产出 message。
    """
    conversation_id = state.conversation_id
    message = state.message
    file_ids = state.file_ids
    sediment_ids = state.sediment_ids
    is_text_reply = state.is_text_reply
    # 检测模型是否返回了文本描述（含 referenced_image_ids）而非实际生成图片
    # 这说明模型已发起图片生成工具调用，但 SSE 在工具完成前断开。
    # 此时应再尝试轮询图片结果，而不是直接把文本当作最终输出。
    # 当 is_text_reply 但 conversation_id 丢失时，尝试从最近对话列表恢复
    if is_text_reply and not conversation_id:
        conversation_id = _recover_conversation_id(
            backend, request.prompt,
            recovered_event="image_text_reply_conversation_id_recovered",
            failed_event="image_text_reply_conversation_id_recovery_failed",
            message_preview=message[:200],
        ) or conversation_id
    if is_text_reply and conversation_id:
        logger.info({
            "event": "image_model_text_reply_retry_poll",
            "conversation_id": conversation_id,
            "message_preview": message[:200],
        })
        # 文本回复场景下，图片可能需要 4-5 分钟才能异步生成完成。
        # 使用 300s 超时并允许多次重试，避免因临时网络问题提前退出。
        _poll_image_results_with_retry(
            backend, conversation_id, file_ids, sediment_ids,
            retry_poll_timeout=max(config.image_poll_timeout_secs, 300),
            max_retries=3,
            log_prefix="image_model_text_reply",
        )

        if file_ids or sediment_ids:
            image_urls = backend.resolve_conversation_image_urls(
                conversation_id, file_ids, sediment_ids, poll=False,
            )
            if image_urls:
                output = _build_image_result(backend, request, image_urls, conversation_id, index, total)
                if output:
                    yield output
                    return
    elif is_text_reply:
        logger.warning({
            "event": "image_model_text_reply_no_image",
            "conversation_id": conversation_id,
            "message_preview": message[:200],
        })
    yield ImageOutput(kind="message", model=request.model, index=index, total=total, text=message, conversation_id=conversation_id)


def _fallback_outputs(
    backend: OpenAIBackendAPI,
    request: ConversationRequest,
    state: _StreamState,
    index: int,
    total: int,
) -> Iterator[ImageOutput]:
    """结果组装段（message 为空时）：短延迟重试轮询后产出 result 或明确的 message。

    兜底路径保证调用方不会得到 "upstream completed without generating images" 这类模糊报错。
    """
    conversation_id = state.conversation_id
    file_ids = state.file_ids
    sediment_ids = state.sediment_ids
    logger.warning({
        "event": "image_stream_no_result_fallback",
        "conversation_id": conversation_id,
        "file_ids": file_ids,
        "sediment_ids": sediment_ids,
        "should_poll_for_image": state.should_poll_for_image,
    })
    # 当 should_poll_for_image 为 True 但 conversation_id 丢失时，尝试恢复
    if state.should_poll_for_image and not conversation_id:
        conversation_id = _recover_conversation_id(
            backend, request.prompt,
            recovered_event="image_fallback_conversation_id_recovered",
            failed_event="image_fallback_conversation_id_recovery_failed",
        ) or conversation_id
    if state.should_poll_for_image and conversation_id:
        # 图片可能仍在异步处理中（上游 SSE 流在图片生成完成前就结束了）。
        # 使用 300s 超时并允许多次重试，避免因临时网络问题或图片尚未提交而提前退出。
        _poll_image_results_with_retry(
            backend, conversation_id, file_ids, sediment_ids,
            retry_poll_timeout=max(config.image_poll_timeout_secs, 300),
            max_retries=3,
            log_prefix="image_stream_retry_poll",
            wait_before_attempt=lambda attempt: min(30.0 * attempt, config.image_poll_initial_wait_secs * attempt),
        )

        if file_ids or sediment_ids:
            image_urls = backend.resolve_conversation_image_urls(
                conversation_id, file_ids, sediment_ids, poll=False,
            )
            if image_urls:
                output = _build_image_result(backend, request, image_urls, conversation_id, index, total)
                if output:
                    yield output
                    return

        # 重试后仍然失败，yield 错误消息
        yield ImageOutput(kind="message", model=request.model, index=index, total=total,
                          text="Image generation completed upstream but the result could not be retrieved. "
                               "The image may still be processing. Please try again in a moment.",
                          conversation_id=conversation_id)
    else:
        # conversation_id 也为空时（SSE 流极短、未捕获到会话 ID），
        # 仍然 yield 一条消息，避免 stream_image_outputs_with_pool 产生
        # "upstream completed without generating images" 模糊报错
        yield ImageOutput(kind="message", model=request.model, index=index, total=total,
                          text="Image generation started upstream but the response was incomplete. "
                               "Please try again.",
                          conversation_id=conversation_id)


def _request_plan(request: ConversationRequest) -> PromptPlan:
    """取请求携带的提示词事实源；端点未构造时就地补建一次（幂等，不重复注入）。

    图片链路的 `request.prompt` 是调用方原始输入，尺寸/质量文本由 `plan.prompt`
    承载，因此这里把 `size_enabled` 一并传下去；`request.messages` 若已是渲染后的
    上游数组，`build_prompt_plan` 会折叠其前置 system，不会二次注入。
    """
    if request.plan is not None:
        return request.plan
    return build_prompt_plan(
        model=request.model,
        messages=request.messages,
        prompt=request.prompt,
        images=request.images,
        size=request.size,
        quality=request.quality,
        size_enabled=request.size_enabled,
    )


def stream_image_outputs(
        backend: OpenAIBackendAPI,
        request: ConversationRequest,
        index: int = 1,
        total: int = 1,
) -> Iterator[ImageOutput]:
    """消费生图对话 SSE 流，产出 progress / message / result 事件。

    按四段组织（行为与事件产出顺序与拆分前完全一致），每段实现下沉到模块内
    私有函数，本函数只保留编排骨架：
    1. 准备对话：消费 conversation_events，逐条映射并透传进度事件；
    2. 轮询前置判定：blocked / 纯文本回复判定、conversation_id 恢复、tasks 预检；
    3. 轮询：首次解析图片 URL，文本回复与兜底场景按退避重试轮询；
    4. 结果组装：下载字节并组装 result 事件，失败时产出明确的 message 事件。
    """
    # —— 段 1：准备对话 ——
    last: dict[str, Any] = {}
    for event in conversation_events(
            backend,
            plan=_request_plan(request),
            prompt=request.prompt,
            model=request.model,
            images=request.images or [],
            size=request.size,
            quality=request.quality,
            size_enabled=request.size_enabled,
    ):
        last = event
        progress = _progress_output_for_event(event, request, index, total)
        if progress is not None:
            yield progress

    # —— 段 2：轮询前置判定 ——
    state, short_circuit = _resolve_stream_state(backend, request, last, index, total)
    if short_circuit is not None:
        yield short_circuit
        return
    assert state is not None

    # —— 段 3：轮询 ——
    image_urls = _first_poll_image_urls(backend, state)

    # —— 段 4：结果组装 ——
    if image_urls:
        output = _build_image_result(backend, request, image_urls, state.conversation_id, index, total)
        if output:
            yield output
        return

    if state.message:
        yield from _message_branch_outputs(backend, request, state, index, total)
        return

    yield from _fallback_outputs(backend, request, state, index, total)



def _codex_response_images(value: Any) -> list[str]:
    """从 codex 响应事件树中递归抽取 image_generation_call 的 base64 图片。"""
    if isinstance(value, dict):
        if value.get("type") == "image_generation_call" and isinstance(value.get("result"), str):
            result = value["result"].strip()
            if result:
                return [result.split(",", 1)[1] if result.startswith("data:image/") else result]
        images: list[str] = []
        for item in value.values():
            images.extend(_codex_response_images(item))
        return images
    if isinstance(value, list):
        images: list[str] = []
        for item in value:
            images.extend(_codex_response_images(item))
        return images
    return []


def stream_codex_image_outputs(
        backend: OpenAIBackendAPI,
        request: ConversationRequest,
        index: int = 1,
        total: int = 1,
) -> Iterator[ImageOutput]:
    """codex 生图流：直接消费 codex 响应事件并组装结果，无中间进度事件。

    codex 链路绕开 `conversation_events`，`global_system_prompt` 无处注入；
    因此这里通过 `render_codex_instructions(plan)` 把它拼进 responses 的
    `instructions` 字段，与文本/picture_v2 链路保持同一份提示词事实源。
    """
    plan = _request_plan(request)
    images = _codex_response_images(list(backend.iter_codex_image_response_events(
        prompt=request.prompt,
        images=request.images or [],
        size=request.size,
        quality=request.quality,
        image_model=codex_image_tool_model(request.model),
        instructions=render_codex_instructions(plan),
    )))
    if not images:
        raise ImageGenerationError("No image result found in response")
    data = format_image_result(
        [{"b64_json": item, "revised_prompt": request.prompt} for item in images],
        request.prompt,
        request.response_format,
        request.base_url,
        int(time.time()),
    )["data"]
    if data:
        yield ImageOutput(kind="result", model=request.model, index=index, total=total, data=data)
        return
    raise ImageGenerationError("No image result found in response")


# 单图生成的重试预算（原 _generate_single_image 内局部常量，提取后按模块级私有常量维护）
# 模型返回文本而非图片的最大重试次数
_MAX_TEXT_REPLY_RETRIES = 3
# TLS 连接错误最大重试次数
_MAX_TLS_RETRIES = 3
# 连接超时错误最大重试次数（同账号短等待重试）
_MAX_CONN_TIMEOUT_RETRIES = 3
# 轮询超时错误最大重试次数（换账号重试）
_MAX_POLL_TIMEOUT_RETRIES = 4


@dataclass
class _RetryBudget:
    """单张图片生成循环内的重试计数（每张图独立实例，跨账号轮换累计）。"""

    text_reply: int = 0
    tls: int = 0
    conn_timeout: int = 0
    poll_timeout: int = 0


def _acquire_image_token(request: ConversationRequest, account_email: str) -> str:
    """取号段：回调进度、解析模型计划类型并取出可用 access_token。

    取号失败（额度耗尽或号池无可用账号）统一包装为 ImageGenerationError，
    原异常经 ``__cause__`` 保留，供 log_service 映射 429 insufficient_quota。
    """
    try:
        if request.progress_callback:
            request.progress_callback("getting_account")
        plan_type, _ = split_image_model(request.model)
        codex_model = is_codex_image_model(request.model)
        return account_service.get_available_access_token(
            plan_type=plan_type,
            source_type="codex" if codex_model else None,
            plan_types=("plus", "team", "pro") if codex_model and not plan_type else None,
        )
    except (RuntimeError, QuotaExhaustedError) as exc:
        # 额度耗尽（QuotaExhaustedError）沿用旧 RuntimeError 的包装路径：
        # 原异常经 __cause__ 保留，log_service._image_error_response 据此
        # 映射 429 insufficient_quota，对外响应体保持逐字节不变
        raise ImageGenerationError(str(exc) or "image generation failed", account_email=account_email) from exc


def _lookup_account_email(token: str, index: int) -> str:
    """账号元信息段：按 token 查账号邮箱并记录 debug 日志（查不到返回空串）。"""
    account = account_service.get_account(token) or {}
    account_email = str(account.get("email") or "").strip()
    logger.debug({
        "event": "image_account_lookup",
        "token_prefix": token[:12] + "..." if len(token) > 12 else token,
        "account_email": account_email,
        "account_found": bool(account),
        "index": index,
    })
    return account_email


def _run_image_stream(
    backend: OpenAIBackendAPI,
    request: ConversationRequest,
    index: int,
    total: int,
    account_email: str,
) -> tuple[list[ImageOutput], bool, bool, bool]:
    """单图轮询等待段：消费一次生图流并归集输出事件。

    返回 `(outputs, emitted_for_token, returned_message, returned_result)`；
    无论正常结束还是异常退出，都会按配置在后台删除本次图片会话。
    `message_as_error` 模式下首条 message 事件直接抛 400 内容政策错误。
    """
    stream_fn = stream_codex_image_outputs if is_codex_image_model(request.model) else stream_image_outputs
    outputs: list[ImageOutput] = []
    emitted_for_token = False
    returned_message = False
    returned_result = False
    last_conversation_id = ""
    try:
        for output in stream_fn(backend, request, index, total):
            last_conversation_id = output.conversation_id or last_conversation_id
            if account_email and not output.account_email:
                output.account_email = account_email
            if output.kind == "message" and request.message_as_error:
                raise ImageGenerationError(
                    output.text or "Image generation was rejected by upstream policy.",
                    status_code=400,
                    error_type="invalid_request_error",
                    code="content_policy_violation",
                    account_email=account_email,
                    conversation_id=output.conversation_id,
                )
            emitted_for_token = True
            returned_message = output.kind == "message"
            returned_result = returned_result or output.kind == "result"
            outputs.append(output)
    except Exception as exc:
        # 异常路径（内容政策拒绝、轮询超时等）会话 ID 只挂在异常上
        last_conversation_id = last_conversation_id or str(getattr(exc, "conversation_id", "") or "")
        raise
    finally:
        _remove_image_conversation_later(backend, last_conversation_id, success=returned_result)
    return outputs, emitted_for_token, returned_message, returned_result


def _finalize_stream_outputs(
    token: str,
    outputs: list[ImageOutput],
    *,
    emitted_for_token: bool,
    returned_message: bool,
    returned_result: bool,
    account_email: str,
) -> list[ImageOutput]:
    """结果转储段：按本次产出形态回写账号结果并返回输出列表。

    - 产出 message：计失败并原样返回（文本透传给调用方）；
    - 无 result：计失败；若已有事件产出则抛 400 no_image_generated，否则返回空输出；
    - 有 result：计成功并返回。
    """
    if returned_message:
        account_service.mark_image_result(token, False)
        return outputs
    if not returned_result:
        account_service.mark_image_result(token, False)
        if emitted_for_token:
            conv_id = outputs[-1].conversation_id if outputs else ""
            raise ImageGenerationError(
                "upstream completed without generating images",
                status_code=400,
                error_type="invalid_request_error",
                code="no_image_generated",
                account_email=account_email,
                conversation_id=conv_id,
            )
        return outputs
    account_service.mark_image_result(token, True)
    return outputs


def _decide_poll_timeout_retry(
    budget: _RetryBudget,
    exc: ImagePollTimeoutError,
    token: str,
    account_email: str,
    index: int,
    emitted_for_token: bool,
) -> bool:
    """轮询超时分类：已产出事件则不再重试；否则换账号重试直至预算耗尽。"""
    if emitted_for_token:
        return False
    budget.poll_timeout += 1
    if budget.poll_timeout <= _MAX_POLL_TIMEOUT_RETRIES:
        logger.warning({
            "event": "image_poll_timeout_retry",
            "request_token": token,
            "account_email": account_email,
            "retry_count": budget.poll_timeout,
            "index": index,
            "error": str(exc)[:200],
        })
        return True
    logger.warning({
        "event": "image_poll_timeout_exhausted_retries",
        "request_token": token,
        "account_email": account_email,
        "retry_count": budget.poll_timeout,
        "index": index,
    })
    return False


def _decide_text_reply_retry(
    budget: _RetryBudget,
    exc: ImageGenerationError,
    error_text: str,
    token: str,
    account_email: str,
    index: int,
    emitted_for_token: bool,
) -> bool:
    """文本回复分类：模型返回文本而非图片时换账号重试，预算耗尽抛 502。"""
    if not (is_model_text_reply_instead_of_image(error_text) and not emitted_for_token):
        logger.warning({
            "event": "image_stream_generation_error",
            "request_token": token,
            "account_email": account_email,
            "error": error_text,
            "index": index,
        })
        return False
    budget.text_reply += 1
    if budget.text_reply <= _MAX_TEXT_REPLY_RETRIES:
        logger.warning({
            "event": "image_model_text_reply_retry",
            "request_token": token,
            "account_email": account_email,
            "retry_count": budget.text_reply,
            "index": index,
            "error": error_text[:200],
        })
        return True
    logger.warning({
        "event": "image_model_text_reply_exhausted_retries",
        "request_token": token,
        "account_email": account_email,
        "retry_count": budget.text_reply,
        "index": index,
    })
    raise ImageGenerationError(
        "Image generation failed: the upstream model returned a text description "
        "instead of generating an image. Please try again later.",
        status_code=502,
        error_type="server_error",
        code="upstream_text_reply",
        account_email=account_email,
        conversation_id=getattr(exc, "conversation_id", ""),
    ) from exc


def _decide_transport_retry(
    budget: _RetryBudget,
    exc: Exception,
    token: str,
    account_email: str,
    index: int,
    emitted_for_token: bool,
) -> tuple[bool, str, str]:
    """传输层异常分类：token 失效换 token、TLS/连接超时退避重试。

    返回 `(should_retry, token, error_text)`；`token` 在换 token 分支被更新，
    调用方据此更新循环内 token。重试前按原逻辑 sleep 退避。
    """
    last_error = str(exc)
    logger.warning({
        "event": "image_stream_fail",
        "request_token": token,
        "account_email": account_email,
        "error": last_error,
        "index": index,
    })
    if not emitted_for_token and is_token_invalid_error(last_error):
        refreshed_token = account_service.refresh_access_token(token, force=True, event="image_stream")
        if refreshed_token and refreshed_token != token:
            return True, refreshed_token, last_error
        account_service.remove_invalid_token(token, "image_stream")
        return True, token, last_error
    # TLS/SSL 连接错误：自动重试
    if not emitted_for_token and is_tls_connection_error(last_error):
        budget.tls += 1
        if budget.tls <= _MAX_TLS_RETRIES:
            logger.warning({
                "event": "image_stream_tls_retry",
                "request_token": token,
                "account_email": account_email,
                "retry_count": budget.tls,
                "index": index,
                "error": last_error[:200],
            })
            time.sleep(min(2.0 * budget.tls, 10.0))
            return True, token, last_error
    # 连接超时错误（curl 28）：同账号短等待重试，不切换账号
    if not emitted_for_token and is_connection_timeout_error(last_error):
        budget.conn_timeout += 1
        if budget.conn_timeout <= _MAX_CONN_TIMEOUT_RETRIES:
            wait_secs = min(3.0 * budget.conn_timeout, 9.0)
            logger.warning({
                "event": "image_stream_conn_timeout_retry",
                "request_token": token,
                "account_email": account_email,
                "retry_count": budget.conn_timeout,
                "index": index,
                "wait_secs": wait_secs,
                "error": last_error[:200],
            })
            time.sleep(wait_secs)
            return True, token, last_error
    return False, token, last_error


def _generate_single_image(
        request: ConversationRequest,
        index: int,
        total: int,
) -> list[ImageOutput]:
    """为单张图片执行生成逻辑（含重试），返回结果列表。

    该函数在独立线程中运行，每个线程使用不同的账号，
    实现并行生图，避免串行超时阻塞。

    按四段组织，重试判定下沉到模块内私有函数，本函数保留循环与
    ``continue`` / ``raise`` 控制流：
    1. 取号：``_acquire_image_token`` + ``_lookup_account_email``；
    2. 单图轮询等待：``_run_image_stream`` 消费生图流并归集事件；
    3. 结果转储：``_finalize_stream_outputs`` 回写账号结果；
    4. 异常分类与重试：轮询超时 / 内容政策 / 文本回复 / 传输层错误。
    """
    budget = _RetryBudget()
    account_email = ""

    while True:
        token = _acquire_image_token(request, account_email)
        emitted_for_token = False
        returned_message = False
        returned_result = False
        account_email = _lookup_account_email(token, index)
        backend = None
        try:
            backend = OpenAIBackendAPI(access_token=token, account_reader=account_service)
            if request.progress_callback:
                backend.progress_callback = request.progress_callback
            outputs, emitted_for_token, returned_message, returned_result = _run_image_stream(
                backend, request, index, total, account_email,
            )
            return _finalize_stream_outputs(
                token,
                outputs,
                emitted_for_token=emitted_for_token,
                returned_message=returned_message,
                returned_result=returned_result,
                account_email=account_email,
            )
        except ImagePollTimeoutError as exc:
            account_service.mark_image_result(token, False)
            if account_email:
                setattr(exc, "account_email", account_email)
            # 轮询超时：换账号重试
            if _decide_poll_timeout_retry(budget, exc, token, account_email, index, emitted_for_token):
                continue
            raise
        except ImageContentPolicyError as exc:
            account_service.mark_image_result(token, False)
            logger.warning({
                "event": "image_stream_content_policy_error",
                "request_token": token,
                "account_email": account_email,
                "error": str(exc),
                "index": index,
            })
            raise ImageGenerationError(
                str(exc) or "Image generation was rejected by upstream policy.",
                status_code=400,
                error_type="invalid_request_error",
                code="content_policy_violation",
                account_email=account_email,
                conversation_id=getattr(exc, "conversation_id", ""),
            ) from exc
        except ImageGenerationError as exc:
            account_service.mark_image_result(token, False)
            if account_email and not getattr(exc, "account_email", ""):
                exc.account_email = account_email
            # 如果是模型返回文本而非图片，尝试换账号重试
            if _decide_text_reply_retry(
                budget, exc, str(exc), token, account_email, index, emitted_for_token,
            ):
                continue
            raise
        except Exception as exc:
            account_service.mark_image_result(token, False)
            should_retry, token, last_error = _decide_transport_retry(
                budget, exc, token, account_email, index, emitted_for_token,
            )
            if should_retry:
                continue
            raise ImageGenerationError(image_stream_error_message(last_error), account_email=account_email, conversation_id="") from exc
        finally:
            if backend is not None:
                backend.close()


def stream_image_outputs_with_pool(request: ConversationRequest) -> Iterator[ImageOutput]:
    """并行生成多张图片，每张图片使用独立线程和账号，互不阻塞。"""
    if not is_supported_image_model(request.model):
        raise ImageGenerationError("unsupported image model,supported models: " + ", ".join(sorted(IMAGE_MODELS)))

    if request.n <= 1:
        # 单张图片，直接执行（无需线程池开销）
        outputs = _generate_single_image(request, 1, 1)
        for output in outputs:
            yield output
        return

    # 多张图片：根据配置选择并行或串行执行
    if not config.image_parallel_generation:
        logger.info({
            "event": "image_serial_generation_start",
            "n": request.n,
            "model": request.model,
        })
        for index in range(1, request.n + 1):
            outputs = _generate_single_image(request, index, request.n)
            for output in outputs:
                yield output
        return

    logger.info({
        "event": "image_parallel_generation_start",
        "n": request.n,
        "model": request.model,
    })
    # 每张图片一个线程，同时启动
    futures = {}
    results: dict[int, list[ImageOutput]] = {}
    errors: dict[int, Exception] = {}
    with ThreadPoolExecutor(max_workers=request.n) as executor:
        for index in range(1, request.n + 1):
            future = executor.submit(_generate_single_image, request, index, request.n)
            futures[future] = index

        # 按完成顺序收集结果
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                errors[index] = exc
                logger.warning({
                    "event": "image_parallel_generation_error",
                    "index": index,
                    "error": str(exc)[:300],
                })

    # yield 结果：跳过索引顺序限制，不再让低索引失败阻塞高索引成功结果
    emitted = False
    last_error = ""
    # 先 yield 所有成功的结果
    for index in range(1, request.n + 1):
        if index in results:
            for output in results[index]:
                emitted = True
                yield output
        elif index in errors:
            last_error = str(errors[index])
            if not emitted:
                logger.warning({
                    "event": "image_parallel_failure_before_success",
                    "failed_index": index,
                    "error": last_error[:200],
                })

    # 如果有失败但也有成功，记录警告
    if emitted:
        for index in range(1, request.n + 1):
            if index in errors:
                logger.warning({
                    "event": "image_parallel_partial_failure",
                    "failed_index": index,
                    "error": str(errors[index])[:200],
                })

    if not emitted:
        if not last_error:
            last_error = "no account in the pool could generate images — check account quota and rate-limit status"
        raise ImageGenerationError(image_stream_error_message(last_error), conversation_id="")


def stream_image_chunks(outputs: Iterable[ImageOutput]) -> Iterator[dict[str, Any]]:
    """把 ImageOutput 流转换为流式响应 chunk 字典流。"""
    for output in outputs:
        yield output.to_chunk()


def collect_image_outputs(outputs: Iterable[ImageOutput]) -> dict[str, Any]:
    """把 ImageOutput 流归并为非流式响应字典（合并结果、消息与进度文本）。"""
    created = None
    data: list[dict[str, Any]] = []
    message = ""
    progress_parts: list[str] = []
    account_email = ""
    for output in outputs:
        created = created or output.created
        if output.account_email and not account_email:
            account_email = output.account_email
        if output.kind == "progress" and output.text:
            progress_parts.append(output.text)
        elif output.kind == "message":
            message = output.text
        elif output.kind == "result":
            data.extend(output.data)

    result: dict[str, Any] = {"created": created or int(time.time()), "data": data}
    if not data:
        text = message or "".join(progress_parts).strip()
        if text:
            result["message"] = text
    if account_email:
        result["_account_email"] = account_email
    return result
