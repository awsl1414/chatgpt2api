"""后端客户端的共享协议与数据结构。

本模块只定义跨模块共享的类型契约，不包含业务逻辑：
- `AccountReader`：账号池的「token → 账号元数据」最小读取接口（审计 B-高2，
  由组装层注入，避免 backend 依赖 account_service）
- `ChatRequirements`：一次对话请求所需的 sentinel token 集合
- `BackendClient`：backend 各领域模块对客户端核心的显式依赖面（结构化协议），
  领域模块只允许依赖本协议，不允许反向依赖 `client`
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from curl_cffi import requests


class AccountReader(Protocol):
    """「token → 账号元数据」的最小读取接口。

    由组装层（protocol/、各 service 调用点）注入，使本模块不依赖账号池
    实现（审计 B-高2：openai_backend_api 不再 import account_service）。
    """

    def get_account(self, access_token: str) -> dict[str, Any]:
        ...


@dataclass
class ChatRequirements:
    """保存一次对话请求所需的 sentinel token。"""

    token: str
    proof_token: str = ""
    turnstile_token: str = ""
    so_token: str = ""
    raw_finalize: dict[str, Any] | None = None


class BackendClient(Protocol):
    """backend 领域模块对客户端核心的最小依赖面。

    `services.backend.client.OpenAIBackendCore` 结构化实现本协议；
    领域模块的函数以 `api: BackendClient` 作为第一个参数显式接收依赖。
    """

    access_token: str
    account: dict[str, Any]
    base_url: str
    user_agent: str
    client_version: str
    client_build_number: str
    session: requests.Session
    pow_script_sources: list[str]
    pow_data_build: str
    progress_callback: Callable[[str], None] | None

    def _headers(self, path: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        """构造请求头，并补上 web 端要求的 target path/route。"""
        ...

    def _image_headers(
        self,
        path: str,
        requirements: ChatRequirements,
        conduit_token: str = "",
        accept: str = "*/*",
    ) -> dict[str, str]:
        """构造图片链路请求头。"""
        ...

    def _bootstrap(self) -> None:
        """预热首页，并提取 PoW 相关脚本引用。"""
        ...

    def _get_chat_requirements(self) -> ChatRequirements:
        """获取当前模式对话所需的 sentinel token。"""
        ...

    def _get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """获取完整 conversation 详情。"""
        ...

    def _upload_image(self, image: str, file_name: str = "image.png") -> dict[str, Any]:
        """上传一张 base64 图片，返回底层文件元数据。"""
        ...
