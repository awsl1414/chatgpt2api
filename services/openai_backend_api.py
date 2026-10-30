"""OpenAI 后端客户端的对外组装层。

`OpenAIBackendAPI` 组合 `services.backend` 包内各模块：
- `client.OpenAIBackendCore`：session/bootstrap、headers 组装、
  requirements+turnstile+PoW、stream_conversation、list_models 等核心链路
- `conversation_payload`：对话请求 payload 构建
- `search`：网页搜索
- `image_task`：生图任务轮询与图片 URL 解析/下载
- `codex_image`：codex responses 生图
- `editable_file`：PPT/PSD 可编辑文件导出

本文件只做组装，不承载业务逻辑；登录/匿名链路说明见 `OpenAIBackendCore`。
"""

from services.backend import codex_image, editable_file, image_task
from services.backend import search as search_domain
from services.backend.client import OpenAIBackendCore
from services.backend.editable_file import EDITABLE_FILE_MODEL
from services.backend.search import SEARCH_MODEL


class OpenAIBackendAPI(OpenAIBackendCore):
    """ChatGPT Web 后端封装（组装层）。

    通过类内方法赋值组合各领域模块的函数（第一个参数即 `self`），
    对外调用面与拆分前的 `OpenAIBackendAPI` 保持一致。
    """

    # —— 可编辑文件导出（services.backend.editable_file）——
    export_ppt_zip = editable_file.export_ppt_zip
    export_psd_zip = editable_file.export_psd_zip

    # —— codex 生图（services.backend.codex_image）——
    iter_codex_image_response_events = codex_image.iter_codex_image_response_events

    # —— 网页搜索（services.backend.search）——
    search = search_domain.search

    # —— 生图任务轮询与解析（services.backend.image_task）——
    download_image_bytes = image_task.download_image_bytes
    resolve_conversation_image_urls = image_task.resolve_conversation_image_urls
    _poll_image_results = image_task.poll_image_results
    _resolve_image_urls = image_task.resolve_image_urls
    _query_backend_tasks = image_task.query_backend_tasks
    _get_file_download_url = image_task.get_file_download_url
    _get_attachment_download_url = image_task.get_attachment_download_url
