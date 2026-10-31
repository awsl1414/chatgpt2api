# Changelog

## Unreleased

+ [新增] 新增部署开关 `allow_remote_image_fetch`（默认开启，行为不变）：控制服务端是否拉取用户请求中的远程 `image_url`（http/https）；面向公网部署时建议设为 `false` 以收敛 SSRF 暴露面，关闭后仅接受 base64/data 形式的图片输入。
+ [重构] 账号池生图额度耗尽改抛领域异常 `QuotaExhaustedError`（`services/errors.py`），替换 `services/account/pool.py` 的 `RuntimeError` 并消除 `log_service` 的消息子串匹配；对外 429 `insufficient_quota` 错误响应格式不变。
+ [破坏性变更] 移除旧版全局代理：`config.json` 的 `proxy` 键不再生效，设置页全局代理输入框已删除，代理请改用「稳定代理运行时」（`proxy_runtime`）或账号级代理。优先级为 账号代理 > 稳定代理运行时（仅上游请求）> 显式代理 > 直连。
+ [重构] 后端大文件拆分：`services/openai_backend_api.py` 拆为 `services/backend/` 包（client / image_task / codex_image / search / editable_file / conversation_payload），`services/account_service.py` 拆为 `services/account/` 包（pool / token_refresh / password_login / progress / models），`services/protocol/conversation.py` 拆出 `message_utils`、`event_parse`、`image_stream` 等模块；异常体系统一到 `services/errors.py`，backend 与 account 的循环依赖改为构造注入解除。
+ [重构] 前端三大拆分：图片页 `page.tsx` 拆出 `lib/image-task-state`、`lib/image-task-poller` 等纯逻辑模块与 hooks，账号页拆出组件与轮询 hook，设置页 `store.ts` 按域拆分，CPA 与 `sub2api` 导入界面统一为 connection-manager 公共组件。
+ [修复] 测试体系：`pyproject.toml` 补声明 pytest 与 requests 开发依赖，live 用例统一以 `CHATGPT2API_LIVE=1` 环境变量门控，离线 `uv run pytest` 与 `uv run python -m unittest discover` 全绿。
+ [优化] 设置页「默认请求上游模型名称」由手填改为下拉选择，选项来自系统缓存的上游模型目录（新增 `GET /api/upstream-models` 接口）；目录拉取失败或当前配置值不在目录中时自动回退保留原值。
+ [新增] 新增 Codex 通道图像模型 `codex-gpt-image-2.5-flare`、`codex-gpt-image-2.5-sunburst`（含 plus-/team-/pro- 前缀变体）：工具层模型 ID 按公开名映射传给上游 `/backend-api/codex/responses`，`/v1/models` 按账号类型广播；图片页模型选择器展示友好名称。
+ [修复] Codex 生图顶层模型 `gpt-5.5` 已被上游拒绝（400 `model_not_found`），改为实测可用的 `gpt-6-luna`。
+ [修复] 尺寸/质量提示仅注入契约里明确有 `size` 参数的接口（`/v1/images/generations`、`/v1/images/edits`、`/v1/responses` 图片工具）；`/v1/chat/completions` 等没有 `size` 参数的接口不再拼接该上下文。
+ [优化] 图片页 2K/4K 尺寸档位仅 Codex 模型可选：置灰选项增加提示说明，切换到非 Codex 模型时自动回退到同比例 1K 档。

## 1.8.0 - 2026-07-28

+ [新增] 新增默认请求上游模型名称和默认思考强度配置，支持在设置页面修改，并可通过模型名的 `-standard`、`-extended`、`-max` 后缀覆盖思考强度。
+ [修复] 新增没出图也移除本地对话的配置，支持在图片生成失败、超时或仅返回文本时异步隐藏对应对话记录。
+ [修复] `/v1/models` 汇总各账号类型的官方模型列表，文本请求按模型权限选择账号。
+ [修复] 过滤隐藏、非最终频道及发往内部工具的助手消息，避免搜索指令和推理内容泄漏到 API 输出。
+ [修复] 修复输出清洗误删代码和命令中标点前空格的问题。
+ [修复] 为图片生成 SSE 流增加可配置的硬超时上限，避免上游长连接长时间挂起。
+ [优化] 数据库存储改为增量同步，仅新增、更新或删除发生变化的记录，保留未变记录的 ID。

## 1.7.0 - 2026-07-05

+ [移除] 移除注册功能、防滥用机制导致封禁GitHub账号。

## 1.6.0 - 2026-07-04

+ [修复] 修复sub2api导入问题。
+ [修复] 修复前端404、405问题。
+ [新增] 新增出图后删除对话记录功能。
+ [调整] Pro号不再按无限额度处理、约每天1000张。

## 1.5.0 - 2026-06-13

+ [新增] 新增 WARP / Privoxy / FlareSolverr 清障方案，注册遇到 Cloudflare 拦截后可刷新 clearance 并重试。
+ [新增] 新增 `outlook_token` 邮箱池，支持 Outlook/Hotmail 注册验证码读取。
+ [新增] 新增网页搜索兼容接口、图片编辑 mask 和图片任务相关能力。
+ [优化] 更新 sentinel/PoW 获取方式，提高上游请求兼容性。
+ [优化] 调整代理优先级和注册请求重试逻辑。

## 1.4.1 - 2026-06-03

+ [新增] 账号刷新改为异步模式，支持前端轮询刷新/重新登录进度。
+ [新增] 号池管理页面新增重新登录功能，支持密码登录恢复异常账号。
+ [新增] 刷新后自动重新登录异常账号（可在设置页开启）。
+ [新增] 图片生成支持并行模式，多张图片使用独立线程和账号同时生成。
+ [新增] 图片轮询超时自动换账号重试（最多4次），连接超时同账号递增等待重试。
+ [新增] 图片二次确认机制与先check再hit可配置化，关闭后可跳过等待直接返回结果。
+ [新增] 图片任务进度追踪，显示当前生成步骤（上传/预热/获取token/生成中等）。
+ [新增] 图片超时后续轮询功能，前端显示"继续等待"按钮。
+ [新增] 设置页新增图片二次确认、超时等待时间、自动重新登录等配置项。
+ [优化] 优化生图页面滚动加载性能，图片懒加载、会话切换滚动位置保存与恢复。

## 1.4.0 - 2026-05-31

+ [新增] 新增AI生成可编辑PSD文件逆向。
+ [新增] 新增AI生成可编辑PPT文件逆向。

## 1.3.1 - 2026-05-30

+ [新增] 新增ChatGPT搜索调试、Skills。

## 1.3.0 - 2026-05-30

+ [新增] 新增ChatGPT搜索接口逆向。

## 1.2.4 - 2026-05-30

+ [新增] 添加聊天补全缓存与重复请求合并。
+ [新增] 新增无限画布一键跳转功能

## 1.2.3 - 2026-05-29

+ [新增] 新增账号级代理。
+ [修复] 修复503异常信息、前端邮箱换行问题。

## 1.2.2 - 2026-05-29

+ [新增] 新增Codex链路生图、支持2k,4k。
+ [新增] 支持RT刷新账号信息。

## 1.2.0 - 2026-05-28

+ [新增] 当前版本基线，包含 Web 面板、画图、号池管理、注册机、图片管理、日志管理和设置能力。
+ [新增] 前端版本号支持点击查看版本更新弹窗，展示当前版本、最新版本和更新日志。
+ [优化] 优化注册机效率，成功率大幅提高。
+ [优化] 优化生图页面配置选项。
