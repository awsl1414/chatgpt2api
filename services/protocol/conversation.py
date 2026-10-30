from __future__ import annotations

from typing import Iterator

from services.account_service import account_service
from services.errors import is_token_invalid_error
from services.openai_backend_api import OpenAIBackendAPI
from services.protocol.event_parse import (
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


def text_backend(model: str = "auto") -> OpenAIBackendAPI:
    return OpenAIBackendAPI(
        access_token=account_service.get_text_access_token(model=model),
        account_reader=account_service,
    )


def stream_text_deltas(backend: OpenAIBackendAPI, request: ConversationRequest) -> Iterator[str]:
    attempted_tokens: set[str] = set()
    token = getattr(backend, "access_token", "")
    emitted = False
    while True:
        if token and token in attempted_tokens:
            raise RuntimeError("no available text account")
        if token:
            attempted_tokens.add(token)
        active_backend = None
        try:
            active_backend = OpenAIBackendAPI(access_token=token, account_reader=account_service)
            for event in conversation_events(
                active_backend,
                messages=request.messages,
                model=request.model,
                prompt=request.prompt,
                thinking_effort=request.thinking_effort,
            ):
                if event.get("type") != "conversation.delta":
                    continue
                delta = str(event.get("delta") or "")
                if delta:
                    emitted = True
                    yield delta
            account_service.mark_text_used(token)
            return
        except Exception as exc:
            error_message = str(exc)
            if token and not emitted and is_token_invalid_error(error_message):
                refreshed_token = account_service.refresh_access_token(token, force=True, event="text_stream")
                if refreshed_token and refreshed_token != token and refreshed_token not in attempted_tokens:
                    token = refreshed_token
                else:
                    account_service.remove_invalid_token(token, "text_stream")
                    token = account_service.get_text_access_token(
                        excluded_tokens=set(attempted_tokens),
                        model=request.model,
                    )
                if token:
                    continue
            raise
        finally:
            if active_backend is not None:
                active_backend.close()


def collect_text(backend: OpenAIBackendAPI, request: ConversationRequest) -> str:
    return "".join(stream_text_deltas(backend, request))
