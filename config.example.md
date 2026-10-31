# config.example.json 字段说明

`config.json` 的完整示例见 [`config.example.json`](./config.example.json)，取值为程序内置默认值，可直接复制为运行配置后修改。除 `auth-key` 外所有字段均可省略（省略时使用本表「默认值」列）；网页端设置页保存后会自动写入并规范化该文件。

> 敏感字段（`auth-key`、`ai_review.api_key`、`backup.secret_access_key`、`backup.passphrase`、`image_storage.webdav_password`、`proxy_runtime.clearance.cf_cookies` 等）请填真实值后再启动；示例文件中一律为占位空值，**切勿提交真实密钥到版本库**。

## 顶层字段

| 字段 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `auth-key` | string | — | ✅ | API 访问密钥；留空启动会报错。可被环境变量 `CHATGPT2API_AUTH_KEY` 覆盖 |
| `refresh_account_interval_minute` | int | `5` | — | 账号池后台刷新轮询间隔（分钟），最小 1 |
| `image_retention_days` | int | `30` | — | 本地图片保留天数，超期自动清理 |
| `allow_remote_image_fetch` | bool | `true` | — | 是否允许服务端拉取请求中的远程 `image_url`；公网部署建议 `false`（收敛 SSRF 暴露面），关闭后仅接受 base64/data 形式图片输入 |
| `image_poll_timeout_secs` | int | `120` | — | 单次生图任务上游轮询总超时（秒） |
| `image_poll_interval_secs` | number | `10` | — | 生图任务轮询间隔（秒），仅后端调优，设置页不展示 |
| `image_poll_initial_wait_secs` | number | `10` | — | 首次轮询前的等待秒数（上游生成约需 30s，立即轮询会浪费请求并触发瞬态 429） |
| `image_account_concurrency` | int | `3` | — | 并行生图时的最大并发账号数 |
| `image_parallel_generation` | bool | `true` | — | 多图请求是否跨账号并行生成；仅后端调优，设置页不展示 |
| `image_settle_enabled` | bool | `true` | — | 图片二次确认：拿到 file_ids 后等待一段时间再次确认 |
| `image_check_before_hit_enabled` | bool | `true` | — | 先 check 再 hit：通过轮询确认 file_ids 存在后再返回，而非仅依赖 SSE 事件 |
| `image_settle_secs` | number | `2` | — | 二次确认等待时间（秒） |
| `image_timeout_retry_secs` | number | `30` | — | 前端图片任务超时后的重试等待秒数；仅网页端消费，后端不读取 |
| `image_min_free_mb` | int | `500` | — | 磁盘最低空闲空间阈值（MB），后台自动清理线程每 30 分钟检查一次，低于阈值按最旧优先清理 |
| `auto_remove_rate_limited_accounts` | bool | `false` | — | 账号触发限流后是否自动移出账号池 |
| `auto_remove_invalid_accounts` | bool | `false` | — | 账号失效后是否自动移出账号池 |
| `auto_relogin_after_refresh` | bool | `false` | — | 刷新 token 失败后是否自动尝试密码重登 |
| `log_levels` | string[] | `[]`（全部输出） | — | 启用的日志级别，可选 `debug`/`info`/`warning`/`error` |
| `base_url` | string | `""` | — | 对外服务的基础 URL；可被环境变量 `CHATGPT2API_BASE_URL` 覆盖 |
| `sensitive_words` | string[] | `[]` | — | 敏感词列表，命中后触发内容过滤 |
| `global_system_prompt` | string | `""` | — | 注入到所有会话的全局 system prompt |
| `default_upstream_model_name` | string | `"gpt-5-5"` | — | 客户端未指定模型时使用的上游模型 |
| `default_thinking_effort` | string | `"auto"` | — | 默认思考力度，可选 `auto`/`standard`/`extended`/`max` |

## `proxy_runtime` — 稳定代理运行时

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用稳定代理出站 |
| `egress_mode` | string | `"direct"` | 出站模式，可选 `direct`/`single_proxy` |
| `proxy_url` | string | `""` | 主链路代理地址（如 `http://privoxy:8118`） |
| `resource_proxy_url` | string | `""` | 资源类请求（图片等）专用代理，留空跟随 `proxy_url` |
| `skip_ssl_verify` | bool | `false` | 是否跳过上游 SSL 证书校验 |
| `reset_session_status_codes` | int[] | `[403]` | 命中这些状态码时重置会话（取值 100–599） |
| `clearance.enabled` | bool | `false` | 是否启用 Cloudflare 过墙 |
| `clearance.mode` | string | `"none"` | 过墙方式，可选 `none`/`manual`/`flaresolverr` |
| `clearance.cf_cookies` | string | `""` | 手动模式下注入的 CF cookies |
| `clearance.cf_clearance` | string | `""` | 手动模式下注入的 `cf_clearance` cookie |
| `clearance.user_agent` | string | Chrome 145 UA | 过墙请求使用的 UA |
| `clearance.browser` | string | `"chrome"` | 过墙浏览器指纹标识 |
| `clearance.flaresolverr_url` | string | `""` | FlareSolverr 服务地址（如 `http://flaresolverr:8191`） |
| `clearance.timeout_sec` | int | `60` | FlareSolverr 单次求解超时（秒），最小 1 |
| `clearance.refresh_interval` | int | `3600` | clearance 凭证刷新间隔（秒），最小 60 |
| `clearance.warm_up_on_start` | bool | `false` | 启动时是否预热一次 clearance |

## `ai_review` — AI 内容审查

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用 AI 审查（对请求内容做二次校验） |
| `base_url` | string | `""` | 审查服务的 OpenAI 兼容 base URL |
| `api_key` | string | `""` | 审查服务密钥 |
| `model` | string | `""` | 审查用模型名 |
| `prompt` | string | `""` | 审查用提示词 |

## `backup` — 自动备份（Cloudflare R2）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用定时备份 |
| `provider` | string | `"cloudflare_r2"` | 备份目标，当前仅支持 Cloudflare R2 |
| `account_id` | string | `""` | R2 账户 ID |
| `access_key_id` | string | `""` | R2 访问密钥 ID |
| `secret_access_key` | string | `""` | R2 秘密访问密钥 |
| `bucket` | string | `""` | R2 桶名 |
| `prefix` | string | `"backups"` | 备份对象键前缀 |
| `interval_minutes` | int | `360` | 备份间隔（分钟），最小 1 |
| `rotation_keep` | int | `10` | 保留的历史备份数量，`0` 表示不清理 |
| `encrypt` | bool | `false` | 是否启用备份包加密 |
| `passphrase` | string | `""` | 加密口令（`encrypt` 为 `true` 时必填） |
| `include.*` | bool | 见示例 | 备份内容开关：`config`/`cpa`/`sub2api`/`logs`/`image_tasks`/`accounts_snapshot`/`auth_keys_snapshot`（默认 `true`）、`images`（默认 `false`） |

## `image_storage` — 图片存储

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用 WebDAV 图片存储（关闭时仅存本地） |
| `mode` | string | `"local"` | 存储模式，可选 `local`/`webdav`/`both`（`enabled=false` 时强制 `local`） |
| `webdav_url` | string | `""` | WebDAV 服务地址（启用后必填） |
| `webdav_username` | string | `""` | WebDAV 用户名 |
| `webdav_password` | string | `""` | WebDAV 密码（启用后必填） |
| `webdav_root_path` | string | `"chatgpt2api/images"` | WebDAV 上的根目录 |
| `public_base_url` | string | `""` | 对外访问图片的公共基础 URL（如 CDN 地址） |

## `chat_completion_cache` — 会话缓存

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用 chat completion 响应缓存 |
| `ttl_seconds` | int | `60` | 缓存条目 TTL（秒） |
| `max_entries` | int | `256` | 缓存最大条目数 |
| `dedupe_inflight` | bool | `true` | 相同请求在途去重（并发命中同一上游任务） |
| `stream_cache` | bool | `true` | 流式响应是否也走缓存 |
| `normalize_messages` | bool | `true` | 计算缓存键前是否规范化 messages |
| `drop_adjacent_duplicates` | bool | `true` | 规范化时是否丢弃相邻重复消息 |
| `drop_assistant_history` | bool | `false` | 规范化时是否丢弃历史 assistant 消息 |

## `third_party_apps` — 第三方应用入口

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `infinite_canvas.enabled` | bool | `false` | 是否在顶部导航展示画布（Infinite Canvas）入口 |
| `infinite_canvas.url` | string | `"https://canvas.best"` | 画布应用地址 |
