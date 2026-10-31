"""ChatGPT Web 后端客户端核心链路。

`OpenAIBackendCore` 承载：
- session 构造（curl-cffi + 账号指纹/代理）与 headers 组装
- bootstrap 首页预热、sentinel chat-requirements（prepare+finalize）、
  PoW 与 turnstile 求解
- `stream_conversation()` 统一流式入口与 `list_models()`
- 图片上传与生图 SSE 流（`_upload_image` / `_stream_picture_conversation`）

领域模块（conversation_payload / search / image_task / codex_image /
editable_file）通过 `BackendClient` 协议依赖本类；对外组装层见
`services.openai_backend_api.OpenAIBackendAPI`。

说明：
- 传入 `access_token` 时，聊天和模型列表都会走已登录链路
  例如 `/backend-api/sentinel/chat-requirements`、`/backend-api/conversation`
- 不传 `access_token` 时，会走未登录链路
  例如 `/backend-anon/sentinel/chat-requirements`、`/backend-anon/conversation`
- 协议兼容转换放在 `services.protocol`
"""

import base64
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any

from curl_cffi import requests
from PIL import Image

from services.backend.context import AccountReader, ChatRequirements
from services.backend.conversation_payload import conversation_payload, image_model_settings
from services.config import config
from services.errors import (
    ImageStreamHardTimeoutError,
    InvalidAccessTokenError,
)
from services.proxy_service import proxy_settings
from utils.helper import ensure_ok, iter_sse_payloads, new_uuid
from utils.log import logger
from utils.pow import build_legacy_requirements_token, build_proof_token, parse_pow_resources
from utils.turnstile import solve_turnstile_token


DEFAULT_CLIENT_VERSION = "prod-a194cd50d4416d3c0b47c740f206b12ce60f5887"
DEFAULT_CLIENT_BUILD_NUMBER = "6708908"
DEFAULT_POW_SCRIPT = "https://chatgpt.com/backend-api/sentinel/sdk.js"


class OpenAIBackendCore:
    """ChatGPT Web 后端封装。

    说明：
    - 传入 `access_token` 时，聊天和模型列表都会走已登录链路
      例如 `/backend-api/sentinel/chat-requirements`、`/backend-api/conversation`
    - 不传 `access_token` 时，会走未登录链路
      例如 `/backend-anon/sentinel/chat-requirements`、`/backend-anon/conversation`
    - `stream_conversation()` 是底层统一流式入口
    - 协议兼容转换放在 `services.protocol`
    """

    def __init__(self, access_token: str = "", *, account_reader: AccountReader | None = None) -> None:
        """初始化后端客户端。

        参数：
        - `access_token`：可选。传入后表示使用已登录链路；不传则使用未登录链路。
        - `account_reader`：可选。token → 账号元数据的读取接口，由组装层注入；
          不传则视作匿名链路（无账号元数据，代理走全局配置）。
        """
        self.base_url = "https://chatgpt.com"
        self.client_version = DEFAULT_CLIENT_VERSION
        self.client_build_number = DEFAULT_CLIENT_BUILD_NUMBER
        self.access_token = access_token
        account = account_reader.get_account(self.access_token) if account_reader and self.access_token else {}
        self.account = account if isinstance(account, dict) else {}
        self.fp = self._build_fp()
        self.user_agent = self.fp["user-agent"]
        self.device_id = self.fp["oai-device-id"]
        self.session_id = self.fp["oai-session-id"]
        self.pow_script_sources: list[str] = []
        self.pow_data_build = ""
        self.progress_callback: Callable[[str], None] | None = None
        self.session = requests.Session(**proxy_settings.build_session_kwargs(
            account=self.account,
            impersonate=self.fp["impersonate"],
            verify=True,
        ))
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Sec-Ch-Ua": self.fp["sec-ch-ua"],
            "Sec-Ch-Ua-Arch": '"x86"',
            "Sec-Ch-Ua-Bitness": '"64"',
            "Sec-Ch-Ua-Full-Version": '"143.0.3650.96"',
            "Sec-Ch-Ua-Full-Version-List": '"Microsoft Edge";v="143.0.3650.96", "Chromium";v="143.0.7499.147", "Not A(Brand";v="24.0.0.0"',
            "Sec-Ch-Ua-Mobile": self.fp["sec-ch-ua-mobile"],
            "Sec-Ch-Ua-Model": '""',
            "Sec-Ch-Ua-Platform": self.fp["sec-ch-ua-platform"],
            "Sec-Ch-Ua-Platform-Version": '"19.0.0"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "OAI-Device-Id": self.device_id,
            "OAI-Session-Id": self.session_id,
            "OAI-Language": "zh-CN",
            "OAI-Client-Version": self.client_version,
            "OAI-Client-Build-Number": self.client_build_number,
        })
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._closed = True
        session = getattr(self, "session", None)
        if session:
            try:
                session.close()
            except Exception:
                pass

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def _build_fp(self) -> dict[str, str]:
        account = self.account
        raw_fp = account.get("fp")
        fp = {str(k).lower(): str(v) for k, v in raw_fp.items()} if isinstance(raw_fp, dict) else {}
        for key in (
                "user-agent",
                "impersonate",
                "oai-device-id",
                "oai-session-id",
                "sec-ch-ua",
                "sec-ch-ua-mobile",
                "sec-ch-ua-platform",
        ):
            value = str(account.get(key) or "").strip()
            if value:
                fp[key] = value
        fp.setdefault(
            "user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        )
        fp.setdefault("impersonate", "chrome110")
        fp.setdefault("oai-device-id", new_uuid())
        fp.setdefault("oai-session-id", new_uuid())
        fp.setdefault("sec-ch-ua", '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"')
        fp.setdefault("sec-ch-ua-mobile", "?0")
        fp.setdefault("sec-ch-ua-platform", '"Windows"')
        return fp

    def _headers(self, path: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        """构造请求头，并补上 web 端要求的 target path/route。"""
        headers = dict(self.session.headers)
        headers["X-OpenAI-Target-Path"] = path
        headers["X-OpenAI-Target-Route"] = path
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _extract_quota_and_restore_at(limits_progress: list[Any]) -> tuple[int, str | None]:
        for item in limits_progress:
            if isinstance(item, dict) and item.get("feature_name") == "image_gen":
                return int(item.get("remaining") or 0), str(item.get("reset_after") or "") or None
        return 0, None

    def _raise_on_error(self, response: Any, path: str) -> None:
        if response.status_code == 401:
            raise InvalidAccessTokenError(f"token invalidated ({path})")
        raise RuntimeError(f"{path} failed: HTTP {response.status_code}")

    def _get_me(self) -> dict[str, Any]:
        path = "/backend-api/me"
        response = self.session.get(self.base_url + path, headers=self._headers(path), timeout=20)
        if response.status_code != 200:
            self._raise_on_error(response, path)
        return response.json()

    def _get_conversation_init(self) -> dict[str, Any]:
        path = "/backend-api/conversation/init"
        response = self.session.post(
            self.base_url + path,
            headers=self._headers(path, {"Content-Type": "application/json"}),
            json={
                "gizmo_id": None,
                "requested_default_model": None,
                "conversation_id": None,
                "timezone_offset_min": -480,
            },
            timeout=20,
        )
        if response.status_code != 200:
            self._raise_on_error(response, path)
        return response.json()

    def _get_default_account(self) -> dict[str, Any]:
        path = "/backend-api/accounts/check/v4-2023-04-27"
        response = self.session.get(self.base_url + path + "?timezone_offset_min=-480", headers=self._headers(path),
                                    timeout=20)
        if response.status_code != 200:
            self._raise_on_error(response, path)
        payload = response.json()
        default_account = ((payload.get("accounts") or {}).get("default") or {}).get("account") or {}
        logger.debug({
            "event": "backend_user_info_account_payload",
            "plan_type": default_account.get("plan_type"),
            "account_user_role": default_account.get("account_user_role"),
            "account_id": default_account.get("account_id"),
            "is_deactivated": default_account.get("is_deactivated"),
            "has_active_subscription": (payload.get("accounts") or {}).get("default", {}).get("entitlement", {}).get("has_active_subscription"),
            "subscription_plan": (payload.get("accounts") or {}).get("default", {}).get("entitlement", {}).get("subscription_plan"),
        })
        return default_account

    def get_user_info(self) -> dict[str, Any]:
        """获取当前 token 的账号信息。"""
        if not self.access_token:
            raise RuntimeError("access_token is required")
        executor = ThreadPoolExecutor(max_workers=3)
        try:
            me_future = executor.submit(self._get_me)
            init_future = executor.submit(self._get_conversation_init)
            account_future = executor.submit(self._get_default_account)
            me_payload, init_payload, default_account = me_future.result(), init_future.result(), account_future.result()
        except (KeyboardInterrupt, SystemExit):
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True, cancel_futures=True)

        plan_type = str(default_account.get("plan_type") or "free")

        limits_progress = init_payload.get("limits_progress")
        limits_progress = limits_progress if isinstance(limits_progress, list) else []
        quota, restore_at = self._extract_quota_and_restore_at(limits_progress)
        result = {
            "email": me_payload.get("email"),
            "user_id": me_payload.get("id"),
            "type": plan_type,
            "quota": quota,
            "limits_progress": limits_progress,
            "default_model_slug": init_payload.get("default_model_slug"),
            "restore_at": restore_at,
            "status": "限流" if quota == 0 else "正常",
        }
        logger.debug({
            "event": "backend_user_info_result",
            "email": result.get("email"),
            "user_id": result.get("user_id"),
            "type": result.get("type"),
            "quota": result.get("quota"),
            "default_model_slug": result.get("default_model_slug"),
            "restore_at": result.get("restore_at"),
            "status": result.get("status"),
        })
        return result

    def _bootstrap_headers(self) -> dict[str, str]:
        """构造首页预热请求头。"""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": self.session.headers["Sec-Ch-Ua"],
            "Sec-Ch-Ua-Mobile": self.session.headers["Sec-Ch-Ua-Mobile"],
            "Sec-Ch-Ua-Platform": self.session.headers["Sec-Ch-Ua-Platform"],
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    def _conversation_headers(self, path: str, requirements: ChatRequirements) -> dict[str, str]:
        """根据当前 requirements 构造对话 SSE 请求头。"""
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "OpenAI-Sentinel-Chat-Requirements-Token": requirements.token,
        }
        if requirements.proof_token:
            headers["OpenAI-Sentinel-Proof-Token"] = requirements.proof_token
        if requirements.turnstile_token:
            headers["OpenAI-Sentinel-Turnstile-Token"] = requirements.turnstile_token
        if requirements.so_token:
            headers["OpenAI-Sentinel-SO-Token"] = requirements.so_token
        return self._headers(path, headers)

    def _image_headers(self, path: str, requirements: ChatRequirements, conduit_token: str = "", accept: str = "*/*") -> \
            dict[str, str]:
        """构造图片链路请求头。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": accept,
            "OpenAI-Sentinel-Chat-Requirements-Token": requirements.token,
        }
        if requirements.proof_token:
            headers["OpenAI-Sentinel-Proof-Token"] = requirements.proof_token
        if conduit_token:
            headers["X-Conduit-Token"] = conduit_token
        if accept == "text/event-stream":
            headers["X-Oai-Turn-Trace-Id"] = new_uuid()
        return self._headers(path, headers)

    def _prepare_image_conversation(self, prompt: str, requirements: ChatRequirements, model: str) -> str:
        """为图片生成准备 conduit token。"""
        path = "/backend-api/f/conversation/prepare"
        upstream_model, thinking_effort = image_model_settings(model)
        payload = {
            "action": "next",
            "fork_from_shared_post": False,
            "parent_message_id": new_uuid(),
            "model": upstream_model,
            "client_prepare_state": "success",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": ["picture_v2"],
            "partial_query": {
                "id": new_uuid(),
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": [prompt]},
            },
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
        }
        if thinking_effort:
            payload["thinking_effort"] = thinking_effort
        response = self.session.post(
            self.base_url + path,
            headers=self._image_headers(path, requirements),
            json=payload,
            timeout=60,
        )
        ensure_ok(response, path)
        return response.json().get("conduit_token", "")

    def _decode_image_base64(self, image: str) -> bytes:
        """把 base64 图片字符串或本地路径解码成二进制。"""
        if (
                image
                and len(image) < 512
                and not image.startswith("data:")
                and "\n" not in image
                and "\r" not in image
        ):
            file_path = Path(image).expanduser()
            if file_path.exists() and file_path.is_file():
                return file_path.read_bytes()
        payload = image.split(",", 1)[1] if image.startswith("data:") and "," in image else image
        return base64.b64decode(payload)

    def _upload_image(self, image: str, file_name: str = "image.png") -> dict[str, Any]:
        """上传一张 base64 图片，返回底层文件元数据。"""
        data = self._decode_image_base64(image)
        if (
                image
                and len(image) < 512
                and not image.startswith("data:")
                and "\n" not in image
                and "\r" not in image
        ):
            candidate_path = Path(image).expanduser()
            if candidate_path.exists() and candidate_path.is_file():
                file_name = candidate_path.name
        image = Image.open(BytesIO(data))
        width, height = image.size
        mime_type = Image.MIME.get(image.format, "image/png")
        path = "/backend-api/files"
        response = self.session.post(
            self.base_url + path,
            headers=self._headers(path, {"Content-Type": "application/json", "Accept": "application/json"}),
            json={"file_name": file_name, "file_size": len(data), "use_case": "multimodal", "width": width,
                  "height": height},
            timeout=60,
        )
        ensure_ok(response, path)
        upload_meta = response.json()
        response = self.session.put(
            upload_meta["upload_url"],
            headers={
                "Content-Type": mime_type,
                "x-ms-blob-type": "BlockBlob",
                "x-ms-version": "2020-04-08",
                "Origin": self.base_url,
                "Referer": self.base_url + "/",
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.8",
            },
            data=data,
            timeout=120,
        )
        ensure_ok(response, "image_upload")
        path = f"/backend-api/files/{upload_meta['file_id']}/uploaded"
        response = self.session.post(
            self.base_url + path,
            headers=self._headers(path, {"Content-Type": "application/json", "Accept": "application/json"}),
            data="{}",
            timeout=60,
        )
        ensure_ok(response, path)
        return {
            "file_id": upload_meta["file_id"],
            "file_name": file_name,
            "file_size": len(data),
            "mime_type": mime_type,
            "width": width,
            "height": height,
        }

    def _start_image_generation(self, prompt: str, requirements: ChatRequirements, conduit_token: str, model: str,
                                references: list[dict[str, Any]] | None = None) -> requests.Response:
        """启动图片生成或编辑的 SSE 请求。"""
        upstream_model, thinking_effort = image_model_settings(model)
        references = references or []
        parts = [{
            "content_type": "image_asset_pointer",
            "asset_pointer": f"file-service://{item['file_id']}",
            "width": item["width"],
            "height": item["height"],
            "size_bytes": item["file_size"],
        } for item in references]
        parts.append(prompt)
        content = {"content_type": "multimodal_text", "parts": parts} if references else {"content_type": "text",
                                                                                          "parts": [prompt]}
        metadata = {
            "developer_mode_connector_ids": [],
            "selected_github_repos": [],
            "selected_all_github_repos": False,
            "system_hints": ["picture_v2"],
            "serialization_metadata": {"custom_symbol_offsets": []},
        }
        if references:
            metadata["attachments"] = [{
                "id": item["file_id"],
                "mimeType": item["mime_type"],
                "name": item["file_name"],
                "size": item["file_size"],
                "width": item["width"],
                "height": item["height"],
            } for item in references]
        payload = {
            "action": "next",
            "messages": [{
                "id": new_uuid(),
                "author": {"role": "user"},
                "create_time": time.time(),
                "content": content,
                "metadata": metadata,
            }],
            "parent_message_id": new_uuid(),
            "model": upstream_model,
            "client_prepare_state": "sent",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": True,
            "system_hints": ["picture_v2"],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {
                "is_dark_mode": False,
                "time_since_loaded": 1200,
                "page_height": 1072,
                "page_width": 1724,
                "pixel_ratio": 1.2,
                "screen_height": 1440,
                "screen_width": 2560,
                "app_name": "chatgpt.com",
            },
            "paragen_cot_summary_display_override": "allow",
            "force_parallel_switch": "auto",
        }
        if thinking_effort:
            payload["thinking_effort"] = thinking_effort
        path = "/backend-api/f/conversation"
        response = self.session.post(
            self.base_url + path,
            headers=self._image_headers(path, requirements, conduit_token, "text/event-stream"),
            json=payload,
            timeout=300,
            stream=True,
        )
        ensure_ok(response, path)
        return response

    def _get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """获取完整 conversation 详情。"""
        path = f"/backend-api/conversation/{conversation_id}"
        response = self.session.get(self.base_url + path, headers=self._headers(path, {"Accept": "application/json"}),
                                    timeout=60)
        ensure_ok(response, path)
        return response.json()

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        """删除本地对话记录。"""
        path = f"/backend-api/conversation/{conversation_id}"
        headers = self._headers(path, {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Referer": f"{self.base_url}/c/{conversation_id}",
            "X-OpenAI-Target-Route": "/backend-api/conversation/{conversation_id}",
        })
        response = self.session.patch(
            self.base_url + path,
            headers=headers,
            json={"is_visible": False},
            timeout=60,
        )
        ensure_ok(response, path)
        return response.json()

    def _list_recent_conversations(self, limit: int = 5, timeout_secs: float = 10.0) -> list[dict[str, Any]]:
        """列出最近的对话列表，按更新时间倒序。

        当 SSE 流太短导致 conversation_id 丢失时，可以通过此方法
        查找最近创建的对话来恢复 conversation_id。
        """
        path = f"/backend-api/conversations?offset=0&limit={limit}&order=updated&conversation_filter=all"
        try:
            response = self.session.get(
                self.base_url + path,
                headers=self._headers(path, {"Accept": "application/json"}),
                timeout=timeout_secs,
            )
            ensure_ok(response, path)
            data = response.json()
            return data.get("items") or data.get("conversations") or []
        except Exception as exc:
            logger.debug({"event": "list_conversations_failed", "error": str(exc)})
            return []

    def find_conversation_by_prompt(self, prompt: str, started_at: float, timeout_secs: float = 10.0) -> str:
        """根据 prompt 和开始时间，从最近对话列表中查找匹配的 conversation_id。

        当 SSE 流太短导致 conversation_id 丢失时，使用此方法恢复。
        通过对比 prompt 关键词和时间戳来匹配最可能的对话。

        参数：
            prompt: 用户输入的 prompt 文本
            started_at: 请求开始的时间戳（epoch seconds）
            timeout_secs: 请求超时秒数

        返回：
            匹配的 conversation_id，如果未找到返回空字符串
        """
        items = self._list_recent_conversations(limit=10, timeout_secs=timeout_secs)
        if not items:
            return ""
        # 筛选在 started_at 之前或附近创建的对话（最多往前 5 分钟）
        # ChatGPT 的 updated_at 通常晚于实际请求时间
        prompt_lower = str(prompt or "").lower().strip()
        best_match = ""
        best_score = 0.0
        for item in items:
            # item 可能是完整的 conversation 对象或摘要
            conv_id = str(item.get("id") or item.get("conversation_id") or "")
            if not conv_id:
                continue
            # 检查时间范围：对话的 updated_at 应该在请求开始时间之后（或附近）
            updated_at = float(item.get("update_time") or item.get("updated_at") or 0)
            if updated_at and started_at and (updated_at < started_at - 30 or updated_at > started_at + 600):
                continue
            # 匹配 prompt 关键词
            title = str(item.get("title") or "").lower()
            # 计算匹配分数
            score = 0.0
            if prompt_lower and title:
                # 简单的关键词匹配
                prompt_words = set(prompt_lower.split())
                title_words = set(title.split())
                common = prompt_words & title_words
                if common:
                    score = len(common) / max(len(prompt_words), 1)
            # 图生图通常标题为 "Image" 开头
            if title.startswith("image"):
                score += 0.3
            if score > best_score:
                best_score = score
                best_match = conv_id
        if best_match and best_score > 0.1:
            logger.info({
                "event": "conversation_prompt_match_found",
                "conversation_id": best_match,
                "match_score": round(best_score, 2),
            })
            return best_match
        # 如果没有标题匹配，返回最新的对话（时间最近的）
        for item in items:
            conv_id = str(item.get("id") or item.get("conversation_id") or "")
            updated_at = float(item.get("update_time") or item.get("updated_at") or 0)
            if conv_id and updated_at and started_at and updated_at >= started_at - 30:
                logger.info({
                    "event": "conversation_latest_match",
                    "conversation_id": conv_id,
                    "updated_at": updated_at,
                })
                return conv_id
        return ""

    def stream_conversation(
            self,
            messages: list[dict[str, Any]] | None = None,
            model: str = "auto",
            prompt: str = "",
            images: list[str] | None = None,
            system_hints: list[str] | None = None,
            thinking_effort: str = "",
    ) -> Iterator[str]:
        system_hints = system_hints or []
        if "picture_v2" in system_hints:
            yield from self._stream_picture_conversation(prompt, model, images or [])
            return

        normalized = messages or [{"role": "user", "content": prompt}]
        self._bootstrap()
        requirements = self._get_chat_requirements()
        path, timezone = self._chat_target()
        payload = conversation_payload(self, normalized, model, timezone, thinking_effort=thinking_effort)
        response = self.session.post(
            self.base_url + path,
            headers=self._conversation_headers(path, requirements),
            json=payload,
            timeout=300,
            stream=True,
        )
        ensure_ok(response, path)
        try:
            yield from iter_sse_payloads(response)
        finally:
            response.close()

    def _report_progress(self, step: str) -> None:
        """Report progress step to the callback if set."""
        if self.progress_callback:
            try:
                self.progress_callback(step)
            except Exception:
                pass

    def _stream_picture_conversation(
            self,
            prompt: str,
            model: str,
            images: list[str],
    ) -> Iterator[str]:
        if not self.access_token:
            raise RuntimeError("access_token is required for image endpoints")
        self._report_progress("uploading")
        references = [self._upload_image(image, f"image_{idx}.png") for idx, image in enumerate(images, start=1)]
        self._report_progress("bootstrapping")
        self._bootstrap()
        self._report_progress("getting_token")
        requirements = self._get_chat_requirements()
        self._report_progress("preparing_conversation")
        conduit_token = self._prepare_image_conversation(prompt, requirements, model)
        self._report_progress("starting_generation")
        response = self._start_image_generation(prompt, requirements, conduit_token, model, references)
        self._report_progress("generating")
        yield from self._iter_sse_payloads_capped(response, float(config.image_poll_timeout_secs))

    def _iter_sse_payloads_capped(self, response: Any, hard_cap_secs: float) -> Iterator[str]:
        """按墙钟硬上限消费图片 SSE 流，避免上游异常时长连接被无限挂起。

        curl_cffi 在 stream=True + 标量 timeout 下不限制流式 body 的总读取时长，
        上游未生成图片却保持连接时，读取会一直阻塞直到边缘重置（曾观测到单条流
        挂起约 29.5 分钟才失败）。这里复用「图片轮询超时」作为硬上限：到点后关闭
        底层连接以解除阻塞，并抛出明确错误，让任务快速失败而非长时间挂起。
        """
        deadline = time.monotonic() + hard_cap_secs
        # 看门狗：SSE 读取可能阻塞在底层 curl 调用中，超时后关闭连接以强制解除阻塞
        watchdog = threading.Timer(hard_cap_secs, response.close)
        watchdog.daemon = True
        watchdog.start()
        timeout_message = f"图片生成流已超过硬上限 {int(hard_cap_secs)} 秒，已强制中断（上游可能未生成图片）"
        try:
            for payload in iter_sse_payloads(response):
                yield payload
                if time.monotonic() >= deadline:
                    raise ImageStreamHardTimeoutError(timeout_message)
        except ImageStreamHardTimeoutError:
            raise
        except Exception as exc:
            # 看门狗关闭连接后，底层读取会抛出 curl 错误，这里统一转成明确的硬上限错误
            if time.monotonic() >= deadline:
                raise ImageStreamHardTimeoutError(timeout_message) from exc
            raise
        finally:
            watchdog.cancel()
            try:
                response.close()
            except Exception:
                pass

    def _bootstrap(self) -> None:
        """预热首页，并提取 PoW 相关脚本引用。"""
        response = self.session.get(
            self.base_url + "/",
            headers=self._bootstrap_headers(),
            timeout=30,
        )
        ensure_ok(response, "bootstrap")
        self.pow_script_sources, self.pow_data_build = parse_pow_resources(response.text)
        if not self.pow_script_sources:
            self.pow_script_sources = [DEFAULT_POW_SCRIPT]

    def _get_chat_requirements(self) -> ChatRequirements:
        """获取当前模式对话所需的 sentinel token（prepare + finalize 两步流程）。"""
        base = "/backend-api/sentinel/chat-requirements" if self.access_token else "/backend-anon/sentinel/chat-requirements"
        p_token = build_legacy_requirements_token(self.user_agent, self.pow_script_sources, self.pow_data_build)

        prepare_path = base + "/prepare"
        response = self.session.post(
            self.base_url + prepare_path,
            headers=self._headers(prepare_path, {"Content-Type": "application/json"}),
            json={"p": p_token},
            timeout=30,
        )
        ensure_ok(response, "chat_requirements_prepare")
        prepare_data = response.json()

        if (prepare_data.get("arkose") or {}).get("required"):
            raise RuntimeError("chat requirements requires arkose token, which is not implemented")

        proof_token = ""
        proof_info = prepare_data.get("proofofwork") or {}
        if proof_info.get("required"):
            proof_token = build_proof_token(
                proof_info.get("seed", ""),
                proof_info.get("difficulty", ""),
                self.user_agent,
                script_sources=self.pow_script_sources,
                data_build=self.pow_data_build,
            )

        turnstile_token = ""
        turnstile_info = prepare_data.get("turnstile") or {}
        if turnstile_info.get("required") and turnstile_info.get("dx"):
            turnstile_token = solve_turnstile_token(turnstile_info["dx"], p_token) or ""

        finalize_path = base + "/finalize"
        response = self.session.post(
            self.base_url + finalize_path,
            headers=self._headers(finalize_path, {"Content-Type": "application/json"}),
            json={
                "prepare_token": prepare_data.get("prepare_token", ""),
                "proof_token": proof_token,
                "turnstile_token": turnstile_token,
            },
            timeout=30,
        )
        ensure_ok(response, "chat_requirements_finalize")
        data = response.json()

        token = data.get("token", "")
        if not token:
            message = "missing auth chat requirements token" if self.access_token else "missing chat requirements token"
            raise RuntimeError(f"{message}: {data}")

        return ChatRequirements(
            token=token,
            proof_token=proof_token,
            turnstile_token=turnstile_token,
            so_token=data.get("so_token", ""),
            raw_finalize=data,
        )

    def _chat_target(self) -> tuple[str, str]:
        if self.access_token:
            return "/backend-api/conversation", "Asia/Shanghai"
        return "/backend-anon/conversation", "America/Los_Angeles"

    def list_models(self) -> dict[str, Any]:
        """返回当前模式下可用模型，格式对齐 OpenAI `/v1/models`。"""
        self._bootstrap()
        path = "/backend-api/models?history_and_training_disabled=false" if self.access_token else (
            "/backend-anon/models?iim=false&is_gizmo=false"
        )
        route = "/backend-api/models" if self.access_token else "/backend-anon/models"
        context = "auth_models" if self.access_token else "anon_models"
        response = self.session.get(
            self.base_url + path,
            headers=self._headers(route),
            timeout=30,
        )
        ensure_ok(response, context)
        data = []
        seen = set()
        for item in response.json().get("models", []):
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug", "")).strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            data.append({
                "id": slug,
                "object": "model",
                "created": int(item.get("created") or 0),
                "owned_by": str(item.get("owned_by") or "chatgpt"),
                "permission": [],
                "root": slug,
                "parent": None,
            })
        data.sort(key=lambda item: item["id"])
        return {"object": "list", "data": data}
