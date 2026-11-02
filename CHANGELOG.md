# Changelog

## Unreleased

+ [修复] 生图尺寸传递与实测能力对齐（依据工作区 `docs/size-verification.md` 103 条真实出图样本）：新增后端单一事实源 `utils/image_size.py`（`IMAGE_SIZE_CAPABILITIES`），按模型判定「接口 `size` 是否生效」与「提示词尺寸是否生效」。`codex-gpt-image-*` 全系列（含 plus-/team-/pro- 前缀）的接口 `size` 对上游完全无效，现已**不再向上游 payload 传 `size` 字段**，改由提示词注入尺寸+方向（如「输出图片尺寸为 1792x1024，横版。」），这是 codex 链路唯一能决定宽高比的通道；`gpt-image-2`（picture_v2）的接口 size 本身生效，提示词措辞保持不变。
+ [修复] 图片页尺寸选项按实测能力置灰（真正的视觉置灰 + 不可选，非仅 tooltip）：`codex-gpt-image-*` 忽略 `size`，整组比例档置灰（仅保留 auto），宽高比输入框一并禁用并提示「宽高比请在提示词中写明」；2K/4K 档对**所有**模型置灰（实测只兑现比例、不兑现像素，所有模型出图面积恒定约 1.57M 像素）；`gpt-image-2` 的 1K 比例档保留并标注「按比例出图，实际约 1.57M 像素」。删除错误前提 `codexExclusiveTiers`（「2K/4K 仅 Codex 支持」已被实测推翻），不做兼容保留。
+ [变更] 前端不再对 codex 系列提交无效的 `size`（`resolveRequestSize` 返回 undefined）；切换模型时的档位回退按新能力表执行（切到 codex 回退到 auto，切到 picture_v2 把 2K/4K 回退到同比例 1K），并在持久化读回后同样收敛，避免残留档位。
+ [文档] `docs/openapi.yaml` 的 `size` 字段说明、`README.md` 图片接口参数表与功能列表同步标注「仅 `gpt-image-2` 生效，codex 系列忽略」。

+ [重构] 提示词组装收敛到单一事实源 `services/protocol/prompt_plan.py`（`PromptPlan`）：文本（`/v1/chat/completions`、`/v1/responses`、`/v1/messages`）、picture_v2 与 codex 三条链路统一在请求路径内构造一次提示词，各链路只做形态转换。由此修复三个缺陷：①配置 `global_system_prompt` 时文本链路每次请求注入 **2 次**（含调用方自带 system 的请求，不会再逐轮累积）；②`/v1/responses` 用图片模型但无 `image_generation` 工具时上游收到空 `prompt`（纯图片请求现回退到「按参考图生成图片。」，并从 messages 提取输入图片，图生图不再丢图）；③`codex-*` 模型完全不读 `global_system_prompt`，现拼进 responses 的 `instructions` 字段。
+ [变更] 承接上条，以下对外可观测行为随之调整：`global_system_prompt` 与「不支持工具」兜底文案合并为**一条** system 消息（旧实现为多条独立 system，`prompt_tokens` 相应减少）；兜底文案位置由首位改为合并 system 的末尾；`quality` 为 `auto`（默认值）时不再向上游注入「输出图片质量为 auto。」这类无信息量句子，因此未显式传 `quality` 的生图请求提示词文本与旧版不同。
+ [修复] `/v1/messages` 传图片模型名时不再静默返回空文本：该端点只实现文本对话，入口直接返回 400（Anthropic 错误体），消息指明改用 `/v1/images/generations` 或 `/v1/images/edits`。
+ [修复] `revised_prompt` 与上游实际收到的文本同源：picture_v2 用 `render_picture_prompt(plan)`，codex 用 `render_codex_input_prompt(plan)`（即上游 `input`，global 走 `instructions`）。删除 `ConversationRequest.final_prompt`，消除「端点写了但某条链路用不到」的错位。
+ [修复] 图片 SSE 流硬上限超时（`ImageStreamHardTimeoutError`）不再被泛化异常吞掉并透出中文内部文案：直接映射为 502 `upstream_stream_timeout`（英文稳定文案），不再按传输层错误重试。
+ [重构] 提示词链路收尾清理：删除已无调用方的 `message_utils.normalize_messages` / `prompt_with_global_system` / `build_image_prompt` 及其私有辅助函数；`CODEX_RESPONSES_INSTRUCTIONS` 收敛为 `prompt_plan.py` 单一事实源，`backend/codex_image.py` 改为 import；删除 `PromptPlan` 中无人消费的 `size` / `quality` 字段（运行时透传仍读 `ConversationRequest`）；设置页「全局附加指令」说明文案与 `config.example.md` 同步为三条链路的实际注入方式。
+ [重构] 消息规范化与提示词压平下沉到 `services/protocol/message_content.py`（原 `utils/message_content.py` 反向依赖 `services`，违反 `utils` 依赖纪律）；提示词提取只保留一份实现（`extract_prompt_from_message_content` 语义），删除 `prompt_plan._prompt_from_messages`；`check_task_error` 从 `backend/image_task.py` 下沉到协议层，保持 `backend → protocol` 单向。
+ [重构] `ConversationRequest.plan` 改为真实类型 `PromptPlan | None`（`TYPE_CHECKING` 解环），删除 `__post_init__` 的 `getattr` 鸭子类型兜底；`images` 只保留 `PromptPlan.images` 一处来源，`ConversationRequest.images` 与 `final_prompt` 一并删除。
+ [变更] `/v1/images/generations` 删除从未实现的 `history_disabled` 字段（此前接受但无效果）。
+ [加固] `allow_remote_image_fetch=false` 现在同样约束 `/v1/images/edits` 的远程图片引用：关闭后远程 http(s) 一律 400，仅接受 data URL / base64 / 上传文件（此前该端点不受控，README 承诺落空）。
+ [文档] `docs/openapi.yaml`：图片 SSE 由「OpenAI chunk」更正为实际的 `image.generation.*` 对象（新增 `ImageGenerationChunk` schema）；拆分 `ImageGenerationRequest` 与 `ImageEditFormRequest`（JSON 布尔 `stream` vs multipart 字符串枚举）；补充 `/v1/messages` 图片模型 400 契约、`/api/images` 的 `groups`、`/api/accounts` 响应 required、`/health` format 宽松匹配等实测差异。
+ [文档] `docs/feature-status.en.md` 删除全仓不存在的 `/v1/complete` 条目；`/v1/chat/completions` 与 `/v1/responses` 的 `stream` 去掉「仍在测试」；模型清单改为「上游目录并集 + 按账号类型动态追加」，图片页不再声称支持文本模型。
+ [文档] `README.md`、`config.example.md`、`docs/deployment.md` 与设置页文案同步：`log_levels` 为空时不含 debug、`default_thinking_effort` 后缀优先仅适用图片请求、源码运行默认监听 `127.0.0.1:8000`、首部署必须写 `auth-key`、异常账号处理是密码重登而非「移除异常状态」、代理优先级去掉已移除的全局代理。
+ [文档] CHANGELOG 补记请求超时等魔术数字收敛到 `utils/limits.py`（行为零变化）。

+ [文档] 新增 `docs/openapi.yaml`：对外 HTTP 接口的 OpenAPI 3.1 规范（66 path / 32 schema），覆盖 OpenAI/Anthropic 兼容层、图片异步任务、可编辑文件任务、管理面板 API 与无鉴权直链；除 `include_in_schema=False` 的两个直链端点（`/images/*`、`/image-thumbnails/*`，手工补录）外，与运行时 `create_app().openapi()` 逐操作比对，错误体两套形态、鉴权级别、时间口径均已实测对齐，`openapi-spec-validator` 通过。
+ [加固] 管理端配置保存（`POST /api/settings`）对未知顶层键返回 400（错误信息「未知配置键: xxx」，简体中文）：`ConfigStore.update()` 新增顶层键白名单 `ALLOWED_CONFIG_KEYS`（与 `config.get()` 输出、`config.example.json` 键集合一致），防止前端注入任意键污染 config.json；白名单只作用于顶层键维度，嵌套字段仍由各域 normalize 收口；`auth-key` 与 `backup_state` 不在白名单内（前者为部署侧配置，后者为独立状态文件）。
+ [变更] `default_upstream_model_name` 默认值（fallback）由 `gpt-5-5` 改为 `gpt-6-thinking`：后端 `services/config.py`、前端 `settings-normalize` 回退值、`config.example.json`/`config.example.md` 示例与设置页说明文案同步更新；已显式配置该键的用户不受影响。
+ [重构] 时间口径统一为 UTC ISO8601 单一口径（R3-L7）：调用日志、图片/文件任务、CPA/sub2api 导入任务、图片存储、鉴权 key 的时间戳生成端统一输出 UTC 秒级 ISO8601（`Z` 后缀），并收敛原先 7 处重复的 `_now_iso` 到 `utils/clock.py`；账号 `last_used_at` 顺带修复「本地时间写入、按 UTC 读取」的口径错位。读取端宽松解析兼容存量「本地时间」与「UTC」两种既有形态，存量数据不做回写迁移；账号域（`now_str`）既有 UTC 时间戳格式不变。
+ [新增] 新增部署开关 `allow_remote_image_fetch`（默认开启，行为不变）：控制服务端是否拉取用户请求中的远程 `image_url`（http/https）；面向公网部署时建议设为 `false` 以收敛 SSRF 暴露面，关闭后仅接受 base64 / data URL / 上传文件形式的图片输入。
+ [重构] 账号池生图额度耗尽改抛领域异常 `QuotaExhaustedError`（`services/errors.py`），替换 `services/account/pool.py` 的 `RuntimeError` 并消除 `log_service` 的消息子串匹配；对外 429 `insufficient_quota` 错误响应格式不变。
+ [破坏性变更] 移除旧版全局代理：`config.json` 的 `proxy` 键不再生效，设置页全局代理输入框已删除，代理请改用「稳定代理运行时」（`proxy_runtime`）或账号级代理。优先级为 账号代理 > 稳定代理运行时（仅上游请求）> 显式代理 > 直连。
+ [重构] 后端大文件拆分：`services/openai_backend_api.py` 拆为 `services/backend/` 包（client / image_task / codex_image / search / editable_file / conversation_payload），`services/account_service.py` 拆为 `services/account/` 包（pool / token_refresh / password_login / progress / models），`services/protocol/conversation.py` 拆出 `message_utils`、`event_parse`、`image_stream` 等模块；异常体系统一到 `services/errors.py`，backend 与 account 的循环依赖改为构造注入解除。
+ [重构] 前端三大拆分：图片页 `page.tsx` 拆出 `lib/image-task-state`、`lib/image-task-poller` 等纯逻辑模块与 hooks，账号页拆出组件与轮询 hook，设置页 `store.ts` 按域拆分，CPA 与 `sub2api` 导入界面统一为 connection-manager 公共组件。
+ [修复] 测试体系：`pyproject.toml` 补声明 pytest 与 requests 开发依赖，live 用例统一以 `CHATGPT2API_LIVE=1` 环境变量门控，离线 `uv run pytest` 与 `uv run python -m unittest discover` 全绿。
+ [优化] 设置页「默认请求上游模型名称」由手填改为下拉选择，选项来自系统缓存的上游模型目录（新增 `GET /api/upstream-models` 接口）；目录拉取失败或当前配置值不在目录中时自动回退保留原值。
+ [新增] 新增 Codex 通道图像模型 `codex-gpt-image-2.5-flare`、`codex-gpt-image-2.5-sunburst`（含 plus-/team-/pro- 前缀变体）：工具层模型 ID 按公开名映射传给上游 `/backend-api/codex/responses`，`/v1/models` 按账号类型广播；图片页模型选择器展示友好名称。
+ [修复] Codex 生图顶层模型 `gpt-5.5` 已被上游拒绝（400 `model_not_found`），改为实测可用的 `gpt-6-luna`。
+ [修复] 尺寸/质量提示仅注入契约里明确有 `size` 参数的接口（`/v1/images/generations`、`/v1/images/edits`、`/v1/responses` 图片工具）；`/v1/chat/completions` 等没有 `size` 参数的接口不再拼接该上下文。
+ [优化] 图片页尺寸档位增加提示说明，切换模型时自动收敛档位（初始假设「2K/4K 仅 Codex 支持」，已被本节上方的实测结论推翻并重做：现按模型真实能力置灰）。

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
