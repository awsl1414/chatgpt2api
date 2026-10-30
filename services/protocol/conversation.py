"""对话协议域 facade / 组装入口。

历史出处：本文件原为约 1655 行、混杂 6 类职责的巨型模块（审计 B-高1），
已按职责拆分为：

- `protocol.message_utils`：消息规范化 / token 计数 / `ConversationRequest`
- `protocol.event_parse`：SSE 事件解析与会话状态（apply_text_patch /
  update_conversation_state / extract_conversation_ids 等）
- `protocol.image_stream`：生图流编排（stream_image_outputs /
  _generate_single_image / stream_image_outputs_with_pool 等；图片落盘
  经 `set_image_saver` 注入回调，本协议域不直接依赖存储服务，审计 B-中5）
- `protocol.openai_v1_chat_complete`：文本流（text_backend /
  stream_text_deltas / collect_text）

本模块仅做再导出，`services.protocol.conversation` 的对外 import 路径
与调用面 100% 保持不变（含 test/ 等既有引用）；包内模块不得反向 import
本文件。
"""
from __future__ import annotations

from services.errors import (
    ImageContentPolicyError,
    ImageGenerationError,
    ImagePollTimeoutError,
    image_stream_error_message,
    is_connection_timeout_error,
    is_token_invalid_error,
    is_tls_connection_error,
)
from services.openai_backend_api import OpenAIBackendAPI
from services.protocol.event_parse import (
    FILE_ID_RE,
    FILE_SERVICE_ID_RE,
    REAL_IMAGE_FILE_ID_RE,
    SEDIMENT_ID_RE,
    ConversationState,
    add_unique,
    apply_patch_op,
    apply_text_patch,
    assistant_message_text,
    assistant_raw_text,
    conversation_base_event,
    conversation_events,
    event_assistant_text,
    extract_conversation_ids,
    is_image_tool_event,
    is_visible_assistant_message,
    iter_conversation_payloads,
    sanitize_output_text,
    strip_history,
    update_conversation_state,
)
from services.protocol.image_stream import (
    REFERENCED_IMAGE_IDS_RE,
    TOOL_PARAMS_JSON_RE,
    ImageOutput,
    _codex_response_images,
    _generate_single_image,
    _get_detailed_error_from_tasks,
    _remove_image_conversation_later,
    collect_image_outputs,
    format_image_result,
    is_model_text_reply_instead_of_image,
    save_image_bytes,
    set_image_saver,
    stream_codex_image_outputs,
    stream_image_chunks,
    stream_image_outputs,
    stream_image_outputs_with_pool,
)
from services.protocol.message_utils import (
    ConversationRequest,
    assistant_history_messages,
    assistant_history_text,
    build_image_prompt,
    count_message_image_tokens,
    count_message_text_tokens,
    count_message_tokens,
    count_text_tokens,
    encode_images,
    encoding_for_model,
    message_text,
    normalize_messages,
    prompt_with_global_system,
)
from services.protocol.openai_v1_chat_complete import (
    collect_text,
    stream_text_deltas,
    text_backend,
)

__all__ = [
    # —— message_utils：消息与 token 工具 ——
    "ConversationRequest",
    "assistant_history_messages",
    "assistant_history_text",
    "build_image_prompt",
    "count_message_image_tokens",
    "count_message_text_tokens",
    "count_message_tokens",
    "count_text_tokens",
    "encode_images",
    "encoding_for_model",
    "message_text",
    "normalize_messages",
    "prompt_with_global_system",
    # —— event_parse：SSE 事件解析 ——
    "FILE_ID_RE",
    "FILE_SERVICE_ID_RE",
    "REAL_IMAGE_FILE_ID_RE",
    "SEDIMENT_ID_RE",
    "ConversationState",
    "add_unique",
    "apply_patch_op",
    "apply_text_patch",
    "assistant_message_text",
    "assistant_raw_text",
    "conversation_base_event",
    "conversation_events",
    "event_assistant_text",
    "extract_conversation_ids",
    "is_image_tool_event",
    "is_visible_assistant_message",
    "iter_conversation_payloads",
    "sanitize_output_text",
    "strip_history",
    "update_conversation_state",
    # —— image_stream：生图流编排 ——
    "REFERENCED_IMAGE_IDS_RE",
    "TOOL_PARAMS_JSON_RE",
    "ImageOutput",
    "collect_image_outputs",
    "format_image_result",
    "is_model_text_reply_instead_of_image",
    "save_image_bytes",
    "set_image_saver",
    "stream_codex_image_outputs",
    "stream_image_chunks",
    "stream_image_outputs",
    "stream_image_outputs_with_pool",
    # —— openai_v1_chat_complete：文本流 ——
    "collect_text",
    "stream_text_deltas",
    "text_backend",
    # —— 内部辅助（保持既有可 import 面）——
    "_codex_response_images",
    "_generate_single_image",
    "_get_detailed_error_from_tasks",
    "_remove_image_conversation_later",
    # —— 原模块级错误符号（定义已迁 services.errors，此处仅保留可 import 面）——
    "ImageContentPolicyError",
    "ImageGenerationError",
    "ImagePollTimeoutError",
    "image_stream_error_message",
    "is_connection_timeout_error",
    "is_token_invalid_error",
    "is_tls_connection_error",
    "OpenAIBackendAPI",
]
