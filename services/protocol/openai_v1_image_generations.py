"""文生图端点（/v1/images/generations）：prompt 组装、尺寸/质量参数门控与结果输出。"""
from __future__ import annotations

from typing import Any, Iterator

from services.protocol.image_stream import (
    collect_image_outputs,
    stream_image_chunks,
    stream_image_outputs_with_pool,
)
from services.protocol.message_utils import ConversationRequest, count_text_tokens
from services.protocol.prompt_plan import build_prompt_plan
from utils.image_tokens import count_image_output_items_tokens, image_usage


def handle(body: dict[str, Any]) -> dict[str, Any] | Iterator[dict[str, Any]]:
    prompt = str(body.get("prompt") or "")
    model = str(body.get("model") or "gpt-image-2")
    n = int(body.get("n") or 1)
    size = body.get("size")
    quality = str(body.get("quality") or "auto")
    response_format = str(body.get("response_format") or "b64_json")
    base_url = str(body.get("base_url") or "") or None
    progress_callback = body.get("progress_callback")
    # 提示词事实源在请求路径内构造（config 热更新即时生效）；`prompt` 字段保留
    # 调用方原始输入，供会话恢复检索使用，避免尺寸提示稀释关键词匹配。
    plan = build_prompt_plan(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        size_enabled=True,
    )
    outputs = stream_image_outputs_with_pool(ConversationRequest(
        prompt=prompt,
        model=model,
        n=n,
        size=size,
        quality=quality,
        size_enabled=True,
        response_format=response_format,
        base_url=base_url,
        message_as_error=True,
        progress_callback=progress_callback,
        plan=plan,
    ))
    if body.get("stream"):
        return stream_image_chunks(outputs)
    result = collect_image_outputs(outputs)
    result["usage"] = image_usage(
        input_text_tokens=count_text_tokens(prompt, model),
        output_tokens=count_image_output_items_tokens(result.get("data"), size, quality),
    )
    return result
