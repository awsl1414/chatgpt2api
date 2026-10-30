"""services.backend 包：ChatGPT 后端客户端按领域拆分后的实现模块。

- `context`：跨模块共享协议与数据结构（AccountReader / ChatRequirements / BackendClient）
- `client`：OpenAIBackendCore 核心链路（session/bootstrap、headers、requirements+turnstile+PoW、流式对话）
- `conversation_payload`：对话请求 payload 构建
- `search`：网页搜索
- `image_task`：生图任务轮询与图片解析下载
- `codex_image`：codex responses 生图
- `editable_file`：PPT/PSD 可编辑文件导出

依赖方向：各领域模块只依赖 `context`（不允许反向依赖 `client`）；
`services.openai_backend_api.OpenAIBackendAPI` 作为对外组装层组合全部模块。
"""
