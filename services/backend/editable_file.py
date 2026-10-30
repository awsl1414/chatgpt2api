"""ChatGPT 可编辑文件导出（PPT / PSD）链路。

接受 base64 图片与用户补充需求，驱动一次上游对话（gpt-5-5-thinking）生成
PPTX/PSD 主文件与素材 zip 压缩包，解析并下载产物后落盘。
供 services.editable_file_task_service 调用；所有需要客户端状态的函数以
`api: BackendClient` 作为第一个参数显式声明依赖。
"""

import base64
import json
import mimetypes
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from PIL import Image

from services.backend.context import BackendClient
from services.backend.search import SEARCH_CONVERSATION_ID_RE, walk_dicts
from utils.helper import ensure_ok, iter_sse_payloads, new_uuid


EDITABLE_FILE_MODEL = "gpt-5-5-thinking"
EDITABLE_FILE_THINKING_EFFORT = "extended"
EDITABLE_FILE_TIMEOUT_SECS = 1200.0
EDITABLE_FILE_POLL_INTERVAL_SECS = 5.0
EDITABLE_FILE_CLIENT_VERSION = "prod-bede35f9dcd856d080e012478f0c1031faa2588e"
EDITABLE_FILE_CLIENT_BUILD_NUMBER = "6631702"
EDITABLE_FILE_PSD_OUTPUT_DIR = "data/files/psd"
EDITABLE_FILE_PPT_OUTPUT_DIR = "data/files/ppt"
EDITABLE_FILE_PPT_PROMPT = """我需要你根据用户的需求，来制作一个可以编辑的PPT，你可以使用Agent来做，你不要再继续询问用户问题，内容风格、版式、配色、内容结构和页面信息你可以自行补充并直接执行。整体的流程如下：
1. 用生图的方式，帮我生成一个精美的产品介绍ppt，5-6个页面
2. 帮我把以上涉及到的所有图像和形状素材拆分成单独png，每个素材单独一张图片，不要有遗漏，让我可以直接在ppt里拼接素材还原，不要文字
3. 利用以上所有图片和形状素材，帮我还原你第一次生成的展示ppt，我需要是可编辑的ppt格式，主要部分需要你单独还原插入，文字需要可以编辑
最后只需要给我生成一个PPT文件，以及生成中遇到的各种素材压缩包zip文件就行。"""
EDITABLE_FILE_PSD_PROMPT = "帮我生成这个图像，把这张海报分成若干图像，包括背景图，每个元素不要改位置，这样子我可以直接在 平时里无需拖动，底色为白色，不要伪透明底。再帮我将以上拆分的图像拼合成一个psd文件，去除白色底，不要改变每个图层的相应位置，保留每个元素所在图层的相应位置，保留每个元素的图层，最后只需要给我输出psd文件，以及每个图层的zip文件"
EDITABLE_ASSET_POINTER_RE = re.compile(r"(?:file-service|sediment)://([A-Za-z0-9_-]+)")
EDITABLE_ZIP_MIME_TYPES = {"application/zip", "application/x-zip-compressed"}
EDITABLE_PSD_MIME_TYPES = {"image/vnd.adobe.photoshop", "application/vnd.adobe.photoshop"}
EDITABLE_PPT_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}
EDITABLE_PSD_EXPORT_FILE_RE = re.compile(r"(?:sandbox:)?(/mnt/data/[^\s\"'\)\]]+\.(?:psd|zip))", re.IGNORECASE)
EDITABLE_PPT_EXPORT_FILE_RE = re.compile(r"(?:sandbox:)?(/mnt/data/[^\s\"'\)\]]+\.(?:pptx?|zip))", re.IGNORECASE)

FILE_ID_RE = re.compile(r"\b(file[-_](?!service\b)[A-Za-z0-9_-]+)\b")


# —— 导出结果数据结构 ——


@dataclass
class EditableFileArtifact:
    attachment_id: str = ""
    file_id: str = ""
    name: str = ""
    mime_type: str = ""
    create_time: float = 0.0
    author_role: str = ""
    sandbox_path: str = ""
    message_id: str = ""


@dataclass
class EditableFileExportResult:
    conversation_id: str
    primary_path: Path
    zip_path: Path


def editable_prompt(fixed_prompt: str, user_prompt_text: str) -> str:
    extra = str(user_prompt_text or "").strip()
    return fixed_prompt if not extra else fixed_prompt + "\n\n以下是用户补充需求，请直接结合执行：\n" + extra

def export_ppt_zip(
        api: BackendClient,
        base64_images: list[str] | None,
        prompt: str,
        output_dir: str | Path = EDITABLE_FILE_PPT_OUTPUT_DIR,
        timeout_secs: float = EDITABLE_FILE_TIMEOUT_SECS,
        poll_interval_secs: float = EDITABLE_FILE_POLL_INTERVAL_SECS,
) -> EditableFileExportResult:
    return export_editable_file_zip(api, 
        base64_images or [],
        editable_prompt(EDITABLE_FILE_PPT_PROMPT, prompt),
        output_dir,
        primary_label="ppt",
        primary_suffixes=(".ppt", ".pptx"),
        primary_mime_types=EDITABLE_PPT_MIME_TYPES,
        primary_mime_keywords=("presentationml.presentation", "ms-powerpoint"),
        primary_default_extension=".pptx",
        export_file_re=EDITABLE_PPT_EXPORT_FILE_RE,
        timeout_secs=timeout_secs,
        poll_interval_secs=poll_interval_secs,
    )

def export_psd_zip(
        api: BackendClient,
        base64_images: list[str],
        prompt: str,
        output_dir: str | Path = EDITABLE_FILE_PSD_OUTPUT_DIR,
        timeout_secs: float = EDITABLE_FILE_TIMEOUT_SECS,
        poll_interval_secs: float = EDITABLE_FILE_POLL_INTERVAL_SECS,
) -> EditableFileExportResult:
    if not base64_images:
        raise ValueError("base64_images is empty")
    return export_editable_file_zip(api, 
        base64_images,
        editable_prompt(EDITABLE_FILE_PSD_PROMPT, prompt),
        output_dir,
        primary_label="psd",
        primary_suffixes=(".psd",),
        primary_mime_types=EDITABLE_PSD_MIME_TYPES,
        primary_mime_keywords=("photoshop",),
        primary_default_extension=".psd",
        export_file_re=EDITABLE_PSD_EXPORT_FILE_RE,
        timeout_secs=timeout_secs,
        poll_interval_secs=poll_interval_secs,
    )

def export_editable_file_zip(
        api: BackendClient,
        base64_images: list[str],
        prompt: str,
        output_dir: str | Path,
        *,
        primary_label: str,
        primary_suffixes: tuple[str, ...],
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
        primary_default_extension: str,
        export_file_re: re.Pattern[str],
        timeout_secs: float,
        poll_interval_secs: float,
) -> EditableFileExportResult:
    if not api.access_token:
        raise RuntimeError("access_token is required for editable file export")
    api.client_version = EDITABLE_FILE_CLIENT_VERSION
    api.client_build_number = EDITABLE_FILE_CLIENT_BUILD_NUMBER
    api.session.headers["OAI-Client-Version"] = EDITABLE_FILE_CLIENT_VERSION
    api.session.headers["OAI-Client-Build-Number"] = EDITABLE_FILE_CLIENT_BUILD_NUMBER
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    uploaded = [upload_editable_base64_image(api, item, index) for index, item in enumerate(base64_images, start=1)]
    conduit_token = prepare_editable_conversation(api, prompt, [item["mime_type"] for item in uploaded])
    conversation_id = run_editable_conversation(api, prompt, uploaded, conduit_token)
    artifacts = wait_editable_output_artifacts(api, 
        conversation_id,
        primary_label,
        primary_suffixes,
        primary_mime_types,
        primary_mime_keywords,
        export_file_re,
        timeout_secs,
        poll_interval_secs,
    )
    downloaded = [download_editable_artifact(api, 
        conversation_id,
        item,
        output_path,
        primary_mime_types,
        primary_mime_keywords,
        primary_default_extension,
    ) for item in artifacts]
    primary_path = next((item for item in downloaded if item.suffix.lower() in primary_suffixes), None)
    zip_path = next((item for item in downloaded if item.suffix.lower() == ".zip"), None)
    if not primary_path or not zip_path:
        raise RuntimeError(f"download finished but did not get both {primary_label} and zip files: {downloaded}")
    return EditableFileExportResult(conversation_id=conversation_id, primary_path=primary_path, zip_path=zip_path)

def upload_editable_base64_image(api: BackendClient, base64_image: str, index: int) -> dict[str, Any]:
    data, file_name, mime_type, width, height = decode_editable_base64_image(base64_image, index)
    path = "/backend-api/files"
    response = api.session.post(
        api.base_url + path,
        headers=api._headers(path, {"Accept": "*/*", "Content-Type": "application/json"}),
        json={
            "file_name": file_name,
            "file_size": len(data),
            "use_case": "multimodal",
            "timezone_offset_min": -480,
            "reset_rate_limits": False,
            "store_in_library": True,
            "library_persistence_mode": "opportunistic",
        },
        timeout=60,
    )
    ensure_ok(response, path)
    payload = response.json()
    upload_url = str(payload.get("upload_url") or "")
    file_id = str(payload.get("file_id") or "")
    if not upload_url or not file_id:
        raise RuntimeError(f"invalid upload response: {payload}")
    response = api.session.put(
        upload_url,
        headers={
            "Content-Type": mime_type,
            "x-ms-blob-type": "BlockBlob",
            "x-ms-version": "2020-04-08",
            "Origin": api.base_url,
            "Referer": api.base_url + "/",
            "User-Agent": api.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.8",
        },
        data=data,
        timeout=120,
    )
    ensure_ok(response, "image_upload")
    path = f"/backend-api/files/{file_id}/uploaded"
    response = api.session.post(
        api.base_url + path,
        headers=api._headers(path, {"Accept": "*/*", "Content-Type": "application/json"}),
        data="{}",
        timeout=60,
    )
    ensure_ok(response, path)
    return {
        "file_id": file_id,
        "library_file_id": str(payload.get("library_file_id") or ""),
        "file_name": file_name,
        "file_size": len(data),
        "mime_type": mime_type,
        "width": width,
        "height": height,
    }

def decode_editable_base64_image(base64_image: str, index: int) -> tuple[bytes, str, str, int, int]:
    raw = str(base64_image or "").strip()
    if not raw:
        raise ValueError("base64 image is empty")
    mime_type = ""
    payload = raw
    match = re.match(r"^data:([^;]+);base64,(.*)$", raw, re.IGNORECASE | re.DOTALL)
    if match:
        mime_type = str(match.group(1) or "").strip().lower()
        payload = str(match.group(2) or "").strip()
    data = base64.b64decode(payload)
    image = Image.open(BytesIO(data))
    image.load()
    width, height = image.size
    mime_type = Image.MIME.get(image.format, mime_type or "image/png")
    extension = mimetypes.guess_extension(mime_type) or ".png"
    return data, f"image_{index}{extension}", mime_type, width, height

def prepare_editable_conversation(api: BackendClient, prompt: str, attachment_mime_types: list[str]) -> str:
    path = "/backend-api/f/conversation/prepare"
    payload: dict[str, Any] = {
        "action": "next",
        "fork_from_shared_post": False,
        "parent_message_id": "client-created-root",
        "model": EDITABLE_FILE_MODEL,
        "client_prepare_state": "success",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": {"kind": "primary_assistant"},
        "system_hints": [],
        "partial_query": {"id": new_uuid(), "author": {"role": "user"}, "content": {"content_type": "text", "parts": [prompt]}},
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {"app_name": "chatgpt.com"},
        "thinking_effort": EDITABLE_FILE_THINKING_EFFORT,
    }
    if attachment_mime_types:
        payload["attachment_mime_types"] = attachment_mime_types
    response = api.session.post(
        api.base_url + path,
        headers=api._headers(path, {"Accept": "*/*", "Content-Type": "application/json", "X-Conduit-Token": "no-token"}),
        json=payload,
        timeout=60,
    )
    ensure_ok(response, path)
    conduit_token = str(response.json().get("conduit_token") or "")
    if not conduit_token:
        raise RuntimeError(f"missing conduit_token: {response.text}")
    return conduit_token

def run_editable_conversation(api: BackendClient, prompt: str, uploaded: list[dict[str, Any]], conduit_token: str) -> str:
    api._bootstrap()
    requirements = api._get_chat_requirements()
    message: dict[str, Any] = {"id": new_uuid(), "author": {"role": "user"}, "create_time": time.time()}
    if uploaded:
        parts = [{
            "content_type": "image_asset_pointer",
            "asset_pointer": f"sediment://{item['file_id']}",
            "size_bytes": item["file_size"],
            "width": item["width"],
            "height": item["height"],
        } for item in uploaded]
        parts.append(prompt)
        message["content"] = {"content_type": "multimodal_text", "parts": parts}
        message["metadata"] = {
            "attachments": [{
                "id": item["file_id"],
                "size": item["file_size"],
                "name": item["file_name"],
                "mime_type": item["mime_type"],
                "width": item["width"],
                "height": item["height"],
                "source": "library",
                "library_file_id": item["library_file_id"],
                "is_big_paste": False,
            } for item in uploaded],
            "developer_mode_connector_ids": [],
            "selected_sources": [],
            "selected_github_repos": [],
            "selected_all_github_repos": False,
            "serialization_metadata": {"custom_symbol_offsets": []},
        }
    else:
        message["content"] = {"content_type": "text", "parts": [prompt]}
    path = "/backend-api/f/conversation"
    response = api.session.post(
        api.base_url + path,
        headers=api._image_headers(path, requirements, conduit_token, "text/event-stream"),
        json={
            "action": "next",
            "messages": [message],
            "parent_message_id": "client-created-root",
            "model": EDITABLE_FILE_MODEL,
            "client_prepare_state": "sent",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": True,
            "system_hints": [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {
                "is_dark_mode": False,
                "time_since_loaded": 401,
                "page_height": 1138,
                "page_width": 803,
                "pixel_ratio": 2,
                "screen_height": 1440,
                "screen_width": 2560,
                "app_name": "chatgpt.com",
            },
            "paragen_cot_summary_display_override": "allow",
            "force_parallel_switch": "auto",
            "thinking_effort": EDITABLE_FILE_THINKING_EFFORT,
        },
        timeout=300,
        stream=True,
    )
    ensure_ok(response, path)
    conversation_id = ""
    try:
        for payload in iter_sse_payloads(response):
            if payload == "[DONE]":
                break
            conversation_id = conversation_id or find_editable_value(payload, "conversation_id")
    finally:
        response.close()
    if not conversation_id:
        raise RuntimeError("conversation_id not found in stream")
    return conversation_id

def wait_editable_output_artifacts(
        api: BackendClient,
        conversation_id: str,
        primary_label: str,
        primary_suffixes: tuple[str, ...],
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
        export_file_re: re.Pattern[str],
        timeout_secs: float,
        poll_interval_secs: float,
) -> list[EditableFileArtifact]:
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        try:
            conversation = get_editable_conversation_detail(api, conversation_id)
        except UpstreamHTTPError as exc:
            if exc.status_code in {404, 409, 423, 429, 500, 502, 503, 504}:
                time.sleep(poll_interval_secs)
                continue
            raise
        targeted = pick_editable_target_artifacts(
            extract_editable_artifacts(conversation, export_file_re),
            primary_suffixes,
            primary_mime_types,
            primary_mime_keywords,
        )
        if targeted:
            return targeted
        time.sleep(poll_interval_secs)
    raise RuntimeError(f"timed out waiting for {primary_label}/zip outputs")

def get_editable_conversation_detail(api: BackendClient, conversation_id: str) -> dict[str, Any]:
    path = f"/backend-api/conversation/{conversation_id}"
    response = api.session.get(api.base_url + path, headers=editable_conversation_document_headers(api, path, conversation_id), timeout=60)
    ensure_ok(response, path)
    return response.json()

def editable_browser_headers(api: BackendClient, path: str, conversation_id: str) -> dict[str, str]:
    headers = api._headers(path, {"Accept": "*/*"})
    headers["Referer"] = f"{api.base_url}/c/{conversation_id}"
    return headers

def editable_conversation_document_headers(api: BackendClient, path: str, conversation_id: str) -> dict[str, str]:
    headers = editable_browser_headers(api, path, conversation_id)
    headers["X-OpenAI-Target-Route"] = "/backend-api/conversation/{conversation_id}"
    return headers

def extract_editable_artifacts(conversation: dict[str, Any], export_file_re: re.Pattern[str]) -> list[EditableFileArtifact]:
    artifacts: dict[str, EditableFileArtifact] = {}
    for node in sorted((conversation.get("mapping") or {}).values(), key=lambda item: float(((item or {}).get("message") or {}).get("create_time") or 0.0)):
        message = (node or {}).get("message") or {}
        message_id = str(message.get("id") or "")
        author_role = str(((message.get("author") or {}).get("role") or "")).strip()
        if author_role not in {"assistant", "tool"}:
            continue
        create_time = float(message.get("create_time") or 0.0)
        message_text = editable_message_text(message)
        for artifact in extract_editable_message_artifacts(message, message_id, author_role, create_time, export_file_re):
            key = artifact.attachment_id or artifact.file_id or artifact.name or artifact.sandbox_path
            if key:
                artifacts[key] = merge_editable_artifact(artifacts.get(key), artifact)
        for export_path in extract_editable_export_paths(message_text, export_file_re):
            inferred = EditableFileArtifact(name=Path(export_path).name, create_time=create_time, author_role=author_role, sandbox_path=export_path, message_id=message_id)
            artifacts[export_path] = merge_editable_artifact(artifacts.get(export_path), inferred)
    return sorted(artifacts.values(), key=lambda item: item.create_time)

def extract_editable_message_artifacts(
        message: dict[str, Any],
        message_id: str,
        author_role: str,
        create_time: float,
        export_file_re: re.Pattern[str],
) -> list[EditableFileArtifact]:
    artifacts: list[EditableFileArtifact] = []
    for item in (message.get("metadata") or {}).get("attachments") or []:
        artifact = editable_artifact_from_dict(item, message_id, author_role, create_time, export_file_re)
        if artifact:
            artifacts.append(artifact)
    for obj in api._walk_search_dicts(message):
        artifact = editable_artifact_from_dict(obj, message_id, author_role, create_time, export_file_re)
        if artifact:
            artifacts.append(artifact)
    return artifacts

def editable_artifact_from_dict(
        payload: dict[str, Any],
        message_id: str,
        author_role: str,
        create_time: float,
        export_file_re: re.Pattern[str],
) -> EditableFileArtifact | None:
    if not ({"id", "file_id", "asset_pointer", "name", "file_name", "filename", "mime_type", "mimeType"} & set(payload.keys())):
        return None
    attachment_id = match_editable_file_id(str(payload.get("id") or ""))
    file_id = match_editable_file_id(str(payload.get("file_id") or ""))
    name = sanitize_editable_filename(str(payload.get("name") or payload.get("file_name") or payload.get("filename") or payload.get("title") or "").strip())
    mime_type = clean_editable_mime_type(payload.get("mime_type") or payload.get("mimeType") or "")
    for asset_id in EDITABLE_ASSET_POINTER_RE.findall(str(payload.get("asset_pointer") or "")):
        attachment_id = attachment_id or asset_id
        file_id = file_id or asset_id
    if not attachment_id or not file_id:
        ids = extract_editable_file_ids(json.dumps(payload, ensure_ascii=False))
        attachment_id = attachment_id or (ids[0] if ids else "")
        file_id = file_id or (ids[0] if ids else "")
    if not attachment_id and not file_id:
        return None
    return EditableFileArtifact(
        attachment_id=attachment_id,
        file_id=file_id,
        name=name,
        mime_type=mime_type,
        create_time=create_time,
        author_role=author_role,
        sandbox_path=(extract_editable_export_paths(payload, export_file_re) or [""])[0],
        message_id=message_id,
    )

def pick_editable_target_artifacts(
        artifacts: list[EditableFileArtifact],
        primary_suffixes: tuple[str, ...],
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
) -> list[EditableFileArtifact]:
    primary = next((item for item in reversed(artifacts) if looks_like_editable_primary(item, primary_suffixes, primary_mime_types, primary_mime_keywords)), None)
    zip_item = next((item for item in reversed(artifacts) if looks_like_editable_zip(item)), None)
    return [primary, zip_item] if primary and zip_item else []

def download_editable_artifact(
        api: BackendClient,
        conversation_id: str,
        artifact: EditableFileArtifact,
        output_dir: Path,
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
        primary_default_extension: str,
) -> Path:
    download_url = resolve_editable_download_url(api, conversation_id, artifact)
    if not download_url:
        raise RuntimeError(f"download url not found for artifact: {artifact}")
    response = api.session.get(download_url, timeout=300)
    ensure_ok(response, "artifact_download")
    content_type = clean_editable_mime_type(response.headers.get("Content-Type") or artifact.mime_type)
    file_name = resolve_editable_output_name(artifact, response.url, response.headers.get("Content-Disposition"), content_type, primary_mime_types, primary_mime_keywords, primary_default_extension)
    target_path = unique_editable_path(output_dir / file_name)
    target_path.write_bytes(response.content)
    return target_path

def resolve_editable_download_url(api: BackendClient, conversation_id: str, artifact: EditableFileArtifact) -> str:
    ids: list[str] = []
    for item in (artifact.attachment_id, artifact.file_id):
        if item and item not in ids:
            ids.append(item)
    if artifact.sandbox_path and artifact.message_id:
        path = f"/backend-api/conversation/{conversation_id}/interpreter/download"
        response = api.session.get(
            api.base_url + path,
            headers=editable_download_headers(api, path, conversation_id, "/backend-api/conversation/{conversation_id}/interpreter/download"),
            params={"message_id": artifact.message_id, "sandbox_path": artifact.sandbox_path},
            timeout=60,
        )
        if 200 <= response.status_code < 300:
            url = download_url_from_response(response)
            if url:
                return url
    for attachment_id in ids:
        path = f"/backend-api/conversation/{conversation_id}/attachment/{attachment_id}/download"
        response = api.session.get(
            api.base_url + path,
            headers=editable_download_headers(api, path, conversation_id, "/backend-api/conversation/{conversation_id}/attachment/{attachment_id}/download"),
            timeout=60,
        )
        if 200 <= response.status_code < 300:
            url = download_url_from_response(response)
            if url:
                return url
    for file_id in ids:
        path = f"/backend-api/files/download/{file_id}"
        response = api.session.get(
            api.base_url + path,
            headers=editable_download_headers(api, path, conversation_id, "/backend-api/files/download/{file_id}"),
            params={"post_id": "", "inline": "false"},
            timeout=60,
        )
        if 200 <= response.status_code < 300:
            url = download_url_from_response(response)
            if url:
                return url
    for file_id in ids:
        path = f"/backend-api/files/{file_id}/download"
        response = api.session.get(
            api.base_url + path,
            headers=editable_download_headers(api, path, conversation_id, "/backend-api/files/download/{file_id}"),
            timeout=60,
        )
        if 200 <= response.status_code < 300:
            url = download_url_from_response(response)
            if url:
                return url
    return ""

def editable_download_headers(api: BackendClient, path: str, conversation_id: str, route: str) -> dict[str, str]:
    headers = editable_browser_headers(api, path, conversation_id)
    headers["X-OpenAI-Target-Route"] = route
    return headers

def download_url_from_response(response: Any) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return str(payload.get("download_url") or payload.get("url") or "")

def resolve_editable_output_name(
        artifact: EditableFileArtifact,
        final_url: str,
        content_disposition: str | None,
        content_type: str,
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
        primary_default_extension: str,
) -> str:
    file_name = sanitize_editable_filename(artifact.name)
    if not file_name and artifact.sandbox_path:
        file_name = sanitize_editable_filename(Path(artifact.sandbox_path).name)
    if not file_name:
        file_name = sanitize_editable_filename(editable_filename_from_content_disposition(content_disposition or ""))
    if not file_name:
        file_name = sanitize_editable_filename(Path(urlparse(final_url).path).name)
    extension = editable_extension_from_mime_type(content_type, primary_mime_types, primary_mime_keywords, primary_default_extension)
    return f"artifact{extension}" if not file_name else (file_name if Path(file_name).suffix else file_name + extension)

def find_editable_value(payload: Any, key: str) -> str:
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
        return next((found for item in payload.values() if (found := find_editable_value(item, key))), "")
    if isinstance(payload, list):
        return next((found for item in payload if (found := find_editable_value(item, key))), "")
    return ""

def extract_editable_file_ids(text: str) -> list[str]:
    values: list[str] = []
    for item in EDITABLE_ASSET_POINTER_RE.findall(text):
        if item not in values:
            values.append(item)
    for item in FILE_ID_RE.findall(text):
        if item not in values:
            values.append(item)
    return values

def match_editable_file_id(value: str) -> str:
    match = FILE_ID_RE.search(value)
    return match.group(1) if match else ""

def clean_editable_mime_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text.split(";", 1)[0] if "/" in text else ""

def looks_like_editable_primary(
        artifact: EditableFileArtifact,
        primary_suffixes: tuple[str, ...],
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
) -> bool:
    path, name, mime = artifact.sandbox_path.lower(), artifact.name.lower(), artifact.mime_type
    return name.endswith(primary_suffixes) or path.endswith(primary_suffixes) or mime in primary_mime_types or any(keyword in mime for keyword in primary_mime_keywords)

def looks_like_editable_zip(artifact: EditableFileArtifact) -> bool:
    path, name, mime = artifact.sandbox_path.lower(), artifact.name.lower(), artifact.mime_type
    return name.endswith(".zip") or path.endswith(".zip") or mime in EDITABLE_ZIP_MIME_TYPES or mime.endswith("/zip")

def editable_extension_from_mime_type(
        mime_type: str,
        primary_mime_types: set[str],
        primary_mime_keywords: tuple[str, ...],
        primary_default_extension: str,
) -> str:
    if mime_type in primary_mime_types or any(keyword in mime_type for keyword in primary_mime_keywords):
        return primary_default_extension
    if mime_type in EDITABLE_ZIP_MIME_TYPES or mime_type.endswith("/zip"):
        return ".zip"
    return mimetypes.guess_extension(mime_type) or ""

def editable_filename_from_content_disposition(content_disposition: str) -> str:
    extended_match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
    if extended_match:
        return unquote(extended_match.group(1)).strip()
    plain_match = re.search(r'filename="([^"]+)"', content_disposition, re.IGNORECASE)
    return plain_match.group(1).strip() if plain_match else ""

def sanitize_editable_filename(value: str) -> str:
    return Path(str(value or "").strip()).name.replace("\x00", "").strip()

def unique_editable_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"failed to allocate output path for {path}")

def merge_editable_artifact(current: EditableFileArtifact | None, latest: EditableFileArtifact) -> EditableFileArtifact:
    if current is None:
        return latest
    return EditableFileArtifact(
        attachment_id=latest.attachment_id or current.attachment_id,
        file_id=latest.file_id or current.file_id,
        name=latest.name or current.name,
        mime_type=latest.mime_type or current.mime_type,
        create_time=max(current.create_time, latest.create_time),
        author_role=latest.author_role or current.author_role,
        sandbox_path=latest.sandbox_path or current.sandbox_path,
        message_id=latest.message_id or current.message_id,
    )

def editable_message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content") or {}
    parts: list[str] = []
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            parts.append(content["text"])
        for part in content.get("parts") or []:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.extend(str(part.get(key) or "") for key in ("text", "asset_pointer", "model_set_context") if part.get(key))
    if isinstance(message.get("content"), str):
        parts.append(str(message["content"]))
    return "\n".join(part for part in parts if part).strip()

def extract_editable_export_paths(payload: Any, export_file_re: re.Pattern[str]) -> list[str]:
    if isinstance(payload, str):
        text = payload
    else:
        try:
            text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            text = str(payload)
    values: list[str] = []
    for item in export_file_re.findall(text):
        path = str(item or "").strip()
        if path and path not in values:
            values.append(path)
    return values
