<h1 align="center">ChatGPT2API</h1>


<p align="center">ChatGPT2API 主要是对 ChatGPT 官网相关能力进行逆向整理与封装，提供面向 ChatGPT 图片生成、图片编辑、多图组图编辑场景的 OpenAI 兼容图片 API / 代理，并集成在线画图、号池管理、多种账号导入方式与 Docker 自托管部署能力。</p>

> [!WARNING]
> 免责声明：
>
> 本项目涉及对 ChatGPT 官网文本生成、图片生成与图片编辑等相关接口的逆向研究，仅供个人学习、技术研究与非商业性技术交流使用。
>
> - 严禁将本项目用于任何商业用途、盈利性使用、批量操作、自动化滥用或规模化调用。
> - 严禁将本项目用于破坏市场秩序、恶意竞争、套利倒卖、二次售卖相关服务，以及任何违反 OpenAI 服务条款或当地法律法规的行为。
> - 严禁将本项目用于生成、传播或协助生成违法、暴力、色情、未成年人相关内容，或用于诈骗、欺诈、骚扰等非法或不当用途。
> - 使用者应自行承担全部风险，包括但不限于账号被限制、临时封禁或永久封禁以及因违规使用等所导致的法律责任。
> - 使用本项目即视为你已充分理解并同意本免责声明全部内容；如因滥用、违规或违法使用造成任何后果，均由使用者自行承担。
> - 本项目基于对 ChatGPT 官网相关能力的逆向研究实现，存在账号受限、临时封禁或永久封禁的风险。请勿使用你自己的重要账号、常用账号或高价值账号进行测试。


## 赞助商

<table>
  <tr>
    <td width="190" align="center">
      <a href="https://kunrouai.com/?utm_source=chatgpt2api"><img src="assets/kunrouai.svg" width="163" alt="坤肉AI"></a>
    </td>
    <td>
      <a href="https://kunrouai.com/?utm_source=chatgpt2api">坤肉AI</a> 是一站式 AI 视觉创作平台，集 AI 生图、视频生成、多人协作画布及 Agent/MCP 连接于一体，适合个人创作与团队协作，同时面向企业提供源码出售及私有化部署服务，欢迎企业咨询合作！另有 <a href="https://api.kunrouai.com/?utm_source=chatgpt2api">API 开放平台</a>，提供丰富的 AI 模型 API 接口，支持快速接入与集成，欢迎开发者及企业对接合作！
    </td>
  </tr>
  <tr>
    <td width="190" align="center">
      <a href="https://www.ipwo.net/?ref=githubbasketikunchatgpt2api"><img src="assets/ipwo.png" width="163" alt="IPWO"></a>
    </td>
    <td>
      <a href="https://www.ipwo.net/?ref=githubbasketikunchatgpt2api">IPWO</a> 住宅代理提供动态、静态及不限量住宅代理，覆盖 195+ 个国家和地区，支持 HTTP(S) 与 SOCKS5 协议。<br>对于使用 ChatGPT2API 进行 AI 图片生成、图片编辑和 API 集成的开发者，IPWO 支持免费测试，支持地区选择与网络连接配置，满足多种开发和测试需求。优惠折扣码：<b>0200</b>。
    </td>
  </tr>
  <tr>
    <td width="190" align="center">
      <a href="https://www.atlascloud.ai/zh?utm_source=github&utm_medium=link&utm_campaign=chatgpt2api"><img src="assets/atlascloud.svg" width="163" alt="Atlas Cloud"></a>
    </td>
    <td>
      <a href="https://www.atlascloud.ai/zh?utm_source=github&utm_medium=link&utm_campaign=chatgpt2api">Atlas Cloud</a> is a full-modal AI inference platform that gives developers a single AI API to access video generation, image generation, and LLM APIs. Instead of managing multiple vendor integrations, you connect once and get unified access to 300+ curated models across all modalities. Check out <a href="https://www.atlascloud.ai/console/coding-plan">Atlas Cloud's new coding plan promotion</a> for more budget-friendly API access.
    </td>
  </tr>
</table>

## 快速开始

### Docker 运行

```bash
git clone git@github.com:basketikun/chatgpt2api.git
cd chatgpt2api
docker compose up -d
```

启动前请先在 `config.json` 中设置 `auth-key`，也可以在 `docker-compose.yml` 中通过 `CHATGPT2API_AUTH_KEY` 覆盖。完整配置模板见 [`config.example.json`](./config.example.json)（内置默认值，可直接复制后修改），逐字段说明见 [`config.example.md`](./config.example.md)。

- Web 面板：`http://localhost:3000`
- API 地址：`http://localhost:3000/v1`
- 数据目录：`./data`

### WARP / FlareSolverr 稳定代理部署

如果图片链路经常遇到 Cloudflare 拦截，可以启用附带的 WARP + Privoxy + FlareSolverr 方案：

```bash
cp .env.example .env
docker compose -f docker-compose.warp.yml up -d --build
```

该 compose 会启动：

- `warp-proxy`：提供 WARP SOCKS5 出口。
- `privoxy`：把 WARP SOCKS5 转成 HTTP 代理。
- `flaresolverr`：刷新 Cloudflare clearance。
- `init-config`：幂等写入 `proxy_runtime` 默认配置。
- `app`：启动 ChatGPT2API 主服务。

默认只让上游 OpenAI / ChatGPT 请求走稳定代理，账号邮箱、CPA 等辅助链路不会被强制接管。账号自身配置的代理优先级最高，其次是稳定代理运行时，再其次是显式代理。（旧版 `config.json` 全局 `proxy` 配置已移除，请改用稳定代理运行时。）

可在 `.env` 中调整端口和代理运行时参数，也可在后台设置页的「稳定代理运行时」面板手动保存、测试代理和测试 clearance。

### 本地开发

启动后端：

```bash
git clone git@github.com:basketikun/chatgpt2api.git
cd chatgpt2api
uv sync
uv run main.py
```

启动前端：

```bash
cd chatgpt2api/web
bun install
bun run dev
```

后续更新新版本：

```bash
docker pull ghcr.io/basketikun/chatgpt2api:latest
docker-compose down
docker-compose up -d

```

### 存储后端配置

支持通过环境变量 `STORAGE_BACKEND` 切换存储方式：

- `json` - 本地 JSON 文件（默认）
- `sqlite` - 本地 SQLite 数据库
- `postgres` - 外部 PostgreSQL（需配置 `DATABASE_URL`）
- `git` - Git 私有仓库（需配置 `GIT_REPO_URL` 和 `GIT_TOKEN`）

示例：使用 PostgreSQL

```yaml
environment:
  - STORAGE_BACKEND=postgres
  - DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## 功能

### API 兼容能力

- 兼容 `POST /v1/images/generations` 图片生成接口
- 兼容 `POST /v1/images/edits` 图片编辑接口
- 图片输入默认支持远程 `image_url` 拉取；面向公网部署时可在 `config.json` 设 `"allow_remote_image_fetch": false` 关闭（收敛 SSRF 暴露面），关闭后仅接受 base64/data/上传文件形式的图片输入（对话类图片输入与 `/v1/images/edits` 的远程引用同一开关控制）
- 兼容面向图片场景的 `POST /v1/chat/completions`
- 兼容面向图片场景的 `POST /v1/responses`
- 兼容 Anthropic Messages 协议 `POST /v1/messages`
- 兼容网页搜索 `POST /v1/search`
- 支持 `POST /v1/ppt/generations`、`POST /v1/psd/generations` 异步生成可编辑文件，`GET /v1/editable-file-tasks` 查询任务状态，产物经 `GET /files/{file_path}` 下载
- `GET /v1/models` 返回上游模型目录的并集：有网页生图账号时追加 `gpt-image-2`，有 Codex Plus/Team/Pro 账号时追加
  `codex-gpt-image-2`、`codex-gpt-image-2.5-flare`、`codex-gpt-image-2.5-sunburst` 及 plus-/team-/pro- 前缀变体；
  文本模型（`auto`、`gpt-5*` 等）是否出现取决于上游目录与账号类型
- 支持通过 `n` 返回多张生成结果
- 支持生成可编辑 PPT 文件
- 支持生成可编辑 PSD 文件
- 支持 Codex 中的画图接口逆向，仅 `Plus` / `Team` / `Pro` 订阅可用，模型别名为 `codex-gpt-image-2`、`codex-gpt-image-2.5-flare`、`codex-gpt-image-2.5-sunburst`，如有需要可自行在其他场景映射回
  `gpt-image-2`，用于和官网画图区分；也就意味着同一账号会同时有官网和 Codex 两份生图额度

### 在线画图功能

- 内置在线画图工作台，支持生成、图片编辑与多图组图编辑
- 图片页模型选择器展示 `GET /v1/models` 中 id 含 image 的项：`gpt-image-2`、`codex-gpt-image-*` 及其 plus-/team-/pro- 前缀变体（文本模型不会出现在图片页）
- 编辑模式支持参考图上传
- 前端支持多图生成交互
- 本地保存图片会话历史，支持回看、删除和清空
- 支持服务端缓存图片URL
- 图片生成进度追踪，超时后可继续等待
- 图片懒加载与滚动位置记忆，优化大量图片场景性能

### 号池管理功能

- 自动刷新账号邮箱、类型、额度和恢复时间（异步进度追踪）
- 轮询可用账号执行图片生成与图片编辑
- 遇到 Token 失效类错误时自动剔除无效 Token
- 定时检查限流账号并自动刷新
- 支持密码重新登录恢复异常账号，刷新后可自动重登
- 支持网页端配置 `proxy_runtime` 出站代理（WARP / FlareSolverr / Cloudflare 过墙方案）
- 支持搜索、筛选、批量刷新、导出、手动编辑和清理账号
- 支持四种导入方式：本地 CPA JSON 文件导入、远程 CPA 服务器导入、`sub2api` 服务器导入、`access_token` 导入
- 支持在设置页配置 `sub2api` 服务器，筛选并批量导入其中的 OpenAI OAuth 账号

### 实验性 / 规划中

- 详细状态说明见：[功能清单](./docs/feature-status.en.md)

## 效果展示

<table width="100%">
  <tr>
    <td width="50%"><img src="https://i.ibb.co/Jj8nfwwP/image.png" alt="image" border="0"></td>
    <td width="50%"><img src="https://i.ibb.co/pqf235v/image-edit.png" alt="image edit" border="0"></td>
  </tr>
  <tr>
    <td width="50%"><img src="https://i.ibb.co/tPcqtVfd/chery-studio.png" alt="chery studio" border="0"></td>
    <td width="50%"><img src="https://i.ibb.co/PsT9YHBV/account-pool.png" alt="account pool" border="0"></td>
  </tr>
  <tr>
    <td width="50%"><img src="https://i.ibb.co/rRWLG08q/new-api.png" alt="new api" border="0"></td>
  </tr>
</table>

## API

所有 AI 接口都需要请求头：

```http
Authorization: Bearer <auth-key>
```

完整的 OpenAPI 3.1 规范（含管理面板 API、鉴权级别与错误体形态）见 [`docs/openapi.yaml`](./docs/openapi.yaml)，可直接导入 Apifox / Postman / Swagger UI 等工具。

<details>
<summary><code>GET /v1/models</code></summary>
<br>

返回当前暴露的图片模型列表。

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer <auth-key>"
```

<details>
<summary>说明</summary>
<br>

| 字段   | 说明                                                                                                         |
|:-----|:-----------------------------------------------------------------------------------------------------------|
| 返回模型 | `gpt-image-2`、`codex-gpt-image-2`、`codex-gpt-image-2.5-flare`、`codex-gpt-image-2.5-sunburst`、`auto`、`gpt-5`、`gpt-5-1`、`gpt-5-2`、`gpt-5-3`、`gpt-5-3-mini`、`gpt-5-mini` |
| 接入场景 | 可接入 Cherry Studio、New API 等上游或客户端                                                                          |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/generations</code></summary>
<br>

OpenAI 兼容图片生成接口，用于文生图。

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只漂浮在太空里的猫",
    "n": 1,
    "response_format": "b64_json"
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段                | 说明                                                 |
|:------------------|:---------------------------------------------------|
| `model`           | 图片模型，当前可用值以 `/v1/models` 返回结果为准，推荐使用 `gpt-image-2` |
| `prompt`          | 图片生成提示词                                            |
| `n`               | 生成数量，当前后端限制为 `1-4`                                 |
| `response_format` | 当前请求模型中包含该字段，默认值为 `b64_json`                       |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/edits</code></summary>
<br>

OpenAI 兼容图片编辑接口，可上传图片文件，也可按官方 JSON 格式传入图片链接并生成编辑结果。

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer <auth-key>" \
  -F "model=gpt-image-2" \
  -F "prompt=把这张图改成赛博朋克夜景风格" \
  -F "n=1" \
  -F "image=@./input.png"
```

也可以直接传图片 URL：

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer <auth-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "把这张图改成赛博朋克夜景风格",
    "images": [
      {"image_url": "https://example.com/input.png"}
    ]
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段          | 说明                                            |
|:------------|:----------------------------------------------|
| `model`     | 图片模型， `gpt-image-2`                           |
| `prompt`    | 图片编辑提示词                                       |
| `n`         | 生成数量，当前后端限制为 `1-4`                            |
| `image`     | 需要编辑的图片文件，使用 multipart/form-data 上传           |
| `images`    | JSON 图片引用数组，支持 `{"image_url": "https://..."}` |
| `image_url` | 表单模式下也可直接传图片链接，支持重复字段传多张图                     |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/chat/completions</code></summary>
<br>

面向文本、网页搜索与图片场景的 Chat Completions 兼容接口，不是完整通用聊天代理。

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "messages": [
      {
        "role": "user",
        "content": "生成一张雨夜东京街头的赛博朋克猫"
      }
    ],
    "n": 1
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段                   | 说明                                                                           |
|:---------------------|:-----------------------------------------------------------------------------|
| `model`              | 文本、搜索或图片模型；搜索模型会触发网页搜索兼容逻辑                                                   |
| `messages`           | 消息数组，支持文本、搜索和图片请求内容                                                          |
| `n`                  | 图片生成数量，按当前实现解析为图片数量                                                          |
| `stream`             | 文本、搜索和图片场景均支持；`stream=true` 返回 SSE 流                                                       |
| `tools`              | 文本场景支持 `web_search` / `web_search_preview` / `web_search_preview_2025_03_11` |
| `web_search_options` | 传入时会触发网页搜索兼容逻辑                                                               |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/responses</code></summary>
<br>

面向文本、网页搜索和图片生成工具调用的 Responses API 兼容接口，不是完整通用 Responses API 代理。

```bash
curl http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-5",
    "input": "生成一张未来感城市天际线图片",
    "tools": [
      {
        "type": "image_generation"
      }
    ]
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段       | 说明                                                                                      |
|:---------|:----------------------------------------------------------------------------------------|
| `model`  | 响应中会回显该模型字段，搜索和图片生成会走对应兼容逻辑                                                             |
| `input`  | 输入内容；搜索使用最后一条用户文本，图片生成需能解析出提示词                                                          |
| `tools`  | 支持 `image_generation`、`web_search`、`web_search_preview`、`web_search_preview_2025_03_11` |
| `stream` | 已实现：`stream=true` 返回 Responses 事件格式的 SSE 流                                            |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/messages</code></summary>
<br>

Anthropic Messages 协议兼容接口，支持文本对话、网页搜索工具与图片生成，流式响应为 Anthropic SSE 事件格式。

```bash
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <auth-key>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "auto",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "你好，请简单介绍一下你自己。"
      }
    ]
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段                | 说明                                                         |
|:------------------|:-----------------------------------------------------------|
| `model`           | 文本、搜索或图片模型                                                 |
| `messages`        | Anthropic 消息数组                                             |
| `system`          | 可选系统提示                                                     |
| `stream`          | 可选，`true` 时返回 Anthropic SSE 事件流（`message_start` … `message_stop`） |
| `tools`           | 支持 `web_search` 系列工具定义                                      |

认证兼容 `x-api-key` 请求头或 `Authorization: Bearer` 请求头。

<br>
</details>
</details>

<details>
<summary><code>POST /v1/search</code></summary>
<br>

网页搜索接口：使用账号内置搜索能力返回带引用来源的搜索结果。

```bash
curl http://localhost:8000/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "prompt": "2026 年 AI 行业最新动态"
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段       | 说明                    |
|:---------|:----------------------|
| `prompt` | 搜索关键词或问题（必填）          |

响应中附带 `_account_email` 字段标识实际执行搜索的账号。

<br>
</details>
</details>

<details>
<summary><code>POST /v1/ppt/generations</code> / <code>POST /v1/psd/generations</code></summary>
<br>

异步生成可编辑 PPT / PSD 文件：提交任务后立即返回任务对象，后台生成完成后通过 `GET /v1/editable-file-tasks` 查询结果。

```bash
curl http://localhost:8000/v1/ppt/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "prompt": "生成一份 2026 年 Q2 电商运营复盘 PPT，商务科技风",
    "base64_images": [],
    "client_task_id": "my-task-1"
  }'
```

<details>
<summary>字段说明</summary>
<br>

| 字段                | 说明                                              |
|:------------------|:------------------------------------------------|
| `prompt`          | 生成要求                                            |
| `base64_images`   | 参考图片 base64 数组；PSD 任务必须至少提供一张                   |
| `client_task_id`  | 可选幂等 ID，重复提交返回既有任务                              |

任务状态：`queued` → `running` → `success` / `failed`；成功后 `result` 中携带可下载文件地址。

<br>
</details>
</details>

<details>
<summary><code>GET /v1/editable-file-tasks</code></summary>
<br>

查询可编辑文件任务状态。

```bash
curl "http://localhost:8000/v1/editable-file-tasks?ids=my-task-1" \
  -H "Authorization: Bearer <auth-key>"
```

<details>
<summary>字段说明</summary>
<br>

| 参数    | 说明                                         |
|:------|:-------------------------------------------|
| `ids` | 可选逗号分隔任务 ID；缺省返回当前身份的全部任务 |

返回 `{"items": [...], "missing_ids": [...]}`；`items` 内含 `id`、`status`、`kind`、`created_at`、`updated_at`、`elapsed_seconds`，以及完成后的 `result` 或失败时的 `error`。

<br>
</details>
</details>

## 社区支持

学 AI , 上 L 站：[LinuxDO](https://linux.do)

## Contributors

感谢所有为本项目做出贡献的开发者：

<a href="https://github.com/basketikun/chatgpt2api/graphs/contributors">
  <img alt="Contributors" src="https://contrib.rocks/image?repo=basketikun/chatgpt2api" />
</a>

## Star History

[![Star History Chart](https://api.star-history.com/chart?repos=basketikun/chatgpt2api&type=date&legend=top-left)](https://www.star-history.com/?repos=basketikun%2Fchatgpt2api&type=date&legend=top-left)
