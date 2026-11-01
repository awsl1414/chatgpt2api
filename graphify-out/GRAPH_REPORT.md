# Graph Report - chatgpt2api  (2026-11-02)

## Corpus Check
- 306 files · ~159,638 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: (none) 8, .lock 2, .example 1)

## Summary
- 3917 nodes · 10780 edges · 171 communities (121 shown, 50 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 476 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74098b50`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- split_image_model
- FlareSolverr 过墙服务
- 账号 OAuth/刷新路由
- 账号编辑导入弹窗
- poll_image_results
- 账号 API 路由拆分
- 图片网格与存储统计
- 后端客户端协议与可编辑文件
- 账号表格与指标卡
- 前端布局与登录页
- 账号服务编排
- 账号池与 token 获取
- DatabaseStorageBackend
- 图片存储服务
- R2 备份服务
- 备份设置前端
- 账号池单测
- AI 兼容 API 路由
- OpenAIBackendCore 核心
- ChatGPT2API Changelog
- image_stream.py
- token 刷新单测
- 连接管理适配器
- openai_v1_chat_complete.py
- 日志页与配置卡片
- 调试面板前端
- 搜索/PPT/PSD 面板
- 账号数据模型
- 图片编辑请求解析
- test_v1_image_quota_contract.py
- SSE 事件解析
- 对话 payload 构建
- 图片文件路由
- account_service.py
- chat_completion_cache.py
- Sentinel PoW 与 Turnstile
- sub2api 集成服务
- 图片编辑器选项
- 配置存储 ConfigStore
- event_parse.py
- Codex 生图链路
- test_prompt_migration.py
- 后端客户端单测
- json
- 网页搜索链路
- Chat Completion 缓存测试
- 存储后端抽象
- Auth Key 服务
- InvalidRequestError
- 前端 lint/格式化依赖
- image-composer.tsx
- CPA 连接池服务
- 通用进度追踪器
- outlook 邮箱 token
- Anthropic Messages 协议
- 日志服务
- 内容风控过滤
- 图片工作台页面状态
- FakeBackend
- API 异常处理器
- 图片标签路由
- 模型目录服务
- 可编辑文件任务服务
- 应用工厂与路由装配
- 配置项文档
- 图片任务服务实现
- image_tokens.py
- UTC 时间口径
- 图片会话前端存储
- 服务层测试假件
- build_prompt_plan
- Account Pydantic 模型
- update_conversation_state
- shadcn 组件配置
- 账号 CRUD 路由
- Chat Completion 缓存
- 图片任务 API 客户端
- TypeScript 编译配置
- 配置加载测试
- OAuth 登录服务
- 脱敏日志器
- CPA 池路由
- test_prompt_characterization.py
- 前端运行时依赖
- 图片结果渲染
- 功能状态清单
- 配置归一化
- Responses 接口测试
- 健康监控页与身份路由
- 上游 Conversation SSE 协议
- 生图会话清理
- 前端开发依赖
- Next 配置与版本检查
- 输出注解清洗
- 代理运行时配置测试
- auth.ts
- 后端客户端账号读取协议
- conversation 事件流解析
- 图片编辑 JSON API 测试
- 参考图前端 hooks
- account-import-dialog.tsx
- 代理初始化单测
- 设置加载与路径
- 图片任务服务单测
- editable_file.py
- 文本账号路由单测
- lucide-react
- 内存存储后端
- size_enabled 策略测试
- OAuth 刷新校验脚本
- TokenRefreshService
- 模型列表测试
- Anthropic Messages 测试
- 滚动位置恢复
- 图片生成结果判定流程
- 上游消息结构字段
- 前端 npm 脚本
- test_image_task.py
- 第三方连接管理功能
- 前端图片工作流特性
- query_backend_tasks
- PostCSS 配置
- Atlas Cloud 标志
- IPWO 标志
- 坤肉AI 标志
- 项目根
- GitHub 图标
- Next.js 标志
- OpenAI 图标
- Vercel 标志
- _render_text_messages
- image/page.tsx
- image_task.py
- StorageBackend
- build_router
- FakeImageTaskService
- OpenAI-Compatible Image API Surface
- ChatGPT2API Project
- test_build_prompt_plan_is_idempotent_with_multi_part_system
- SentinelTokenGenerator
- ai.py
- Account Pool Management
- next.config.ts
- WARP 部署 app 服务（chatgpt2api-warp）
- test_picture_prompt_empty_prompt_falls_back_to_image_only
- ImageBaseUrlApiTests
- ImagesEditsApiTests
- .build_export_zip
- FakeWebDAVClient
- global_prompt
- OAuthLoginFinishRequest
- ConversationEventsSizeGatingTests
- Codex Image Generation Reverse Engineering
- Docker Self-Hosted Deployment
- eslint.config.mjs
- extract_conversation_ids
- BuildImagePromptTests
- test_poll_image_results_uses_curl_request_exception
- ImageGenerationTaskRequest
- _fast_poll
- overrides
- test_codex_instructions_have_single_source
- test_tool_unavailable_message_is_static_text
- test_prompt_plan_module_has_no_protocol_package_imports

## God Nodes (most connected - your core abstractions)
1. `require_admin()` - 92 edges
2. `cn()` - 92 edges
3. `AccountService` - 82 edges
4. `Button()` - 77 edges
5. `build_prompt_plan()` - 72 edges
6. `httpRequest()` - 71 edges
7. `react` - 62 edges
8. `ConfigStore` - 53 edges
9. `lucide-react` - 52 edges
10. `AccountPool` - 50 edges

## Surprising Connections (you probably didn't know these)
- `POST /v1/search (chatgpt2api search endpoint)` --semantically_similar_to--> `POST /v1/search (web search)`  [INFERRED] [semantically similar]
  .codex/skills/chatgpt2api-search/SKILL.md → README.md
- `build_router()` --uses--> `OAuthLoginError`  [INFERRED]
  api/accounts/oauth.py → services/oauth_login_service.py
- `install_exception_handlers()` --uses--> `DomainError`  [INFERRED]
  api/errors.py → services/errors.py
- `build_test_router()` --uses--> `BackupError`  [INFERRED]
  api/system/backup.py → services/backup_service.py
- `build_router()` --uses--> `BackupError`  [INFERRED]
  api/system/backup.py → services/backup_service.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **config.json 配置分区** — config_example_md_config_json, config_example_md_proxy_runtime, config_example_md_backup_r2, config_example_md_image_storage_webdav, config_example_md_chat_completion_cache [EXTRACTED 1.00]
- **部署与升级流程** — docs_deployment_md_deployment_guide, docs_deployment_md_persistent_files, docs_deployment_md_upgrade_backup, docs_deployment_md_storage_backend [EXTRACTED 1.00]
- **OpenAI 兼容接口面（images / chat / responses / models / messages）** — docs_feature_status_en_md_images_generations, docs_feature_status_en_md_images_edits, docs_feature_status_en_md_chat_completions, docs_feature_status_en_md_responses, docs_feature_status_en_md_models_endpoint, docs_feature_status_en_md_anthropic_messages [EXTRACTED 1.00]
- **OpenAI-Compatible Endpoint Surface** — readme_openai_compatible_api, readme_images_generations_endpoint, readme_images_edits_endpoint, readme_chat_completions_endpoint, readme_responses_endpoint, readme_messages_endpoint, readme_models_endpoint, readme_auth_key [EXTRACTED 1.00]
- **图片输出判定条件组合（role=tool + image_gen + 可解析指针）** — docs_upstream_sse_conversation_md_tool_message, docs_upstream_sse_conversation_md_image_gen_async_task, docs_upstream_sse_conversation_md_file_service_pointer, docs_upstream_sse_conversation_md_sediment_pointer [EXTRACTED 1.00]
- **上游 SSE 事件类型族（启动/输入/标记/标题/元数据/moderation）** — docs_upstream_sse_conversation_md_resume_conversation_token, docs_upstream_sse_conversation_md_input_message, docs_upstream_sse_conversation_md_message_marker, docs_upstream_sse_conversation_md_title_generation, docs_upstream_sse_conversation_md_server_ste_metadata, docs_upstream_sse_conversation_md_moderation_event [EXTRACTED 1.00]
- **WARP + FlareSolverr 代理链路** — docker_compose_warp_yml_warp_proxy, docker_compose_warp_yml_privoxy, docker_compose_warp_yml_flaresolverr, docker_compose_warp_yml_init_config, docker_compose_warp_yml_app_service [EXTRACTED 1.00]
- **Proxy Runtime / Egress Chain (WARP + FlareSolverr + priority)** — readme_warp_proxy_stack, readme_proxy_priority, changelog_proxy_runtime, changelog_warp_flaresolverr, changelog_account_proxy [INFERRED 0.85]
- **ChatGPT2API Web Search Capability** — codex_skills_chatgpt2api_search_skill_search_skill, codex_skills_chatgpt2api_search_skill_search_endpoint, readme_search_endpoint, changelog_search_api [INFERRED 0.90]

## Communities (171 total, 50 thin omitted)

### Community 0 - "split_image_model"
Cohesion: 0.22
Nodes (5): _acquire_image_token(), ImageModelNameTests, codex_image_tool_model(), is_codex_image_model(), split_image_model()

### Community 1 - "FlareSolverr 过墙服务"
Cohesion: 0.06
Nodes (28): _clean(), ClearanceBundle, _coerce_timeout(), _colon_proxy_to_url(), _cookies_to_header(), _domain_matches(), _filter_flaresolverr_cookies(), _find_header_key() (+20 more)

### Community 2 - "账号 OAuth/刷新路由"
Cohesion: 0.04
Nodes (52): build_router(), finish_oauth_login(), start_oauth_login(), build_router(), create_sub2api_server(), delete_sub2api_server(), list_sub2api_servers(), sub2api_server_accounts() (+44 more)

### Community 3 - "账号编辑导入弹窗"
Cohesion: 0.13
Nodes (43): AccountEditDialog(), AccountEditDialogProps, AccountImportDialog(), AccountJsonPanel(), confirmDescriptions, confirmTitles, DeleteConfirmDialog(), DeleteConfirmDialogProps (+35 more)

### Community 4 - "poll_image_results"
Cohesion: 0.15
Nodes (14): poll_image_results(), _remaining(), _retry_sleep(), ImagePollTimeoutError, FakeAPI, test_poll_image_results_attaches_last_task_error_to_timeout(), test_poll_image_results_keeps_initial_ids_and_polls_for_more(), test_poll_image_results_raises_content_policy_error() (+6 more)

### Community 5 - "账号 API 路由拆分"
Cohesion: 0.07
Nodes (11): AccountRefreshRequest, AccountUpdateRequest, UserKeyCreateRequest, UserKeyUpdateRequest, BackupDeleteRequest, ImageDeleteRequest, ImageDownloadRequest, LogDeleteRequest (+3 more)

### Community 6 - "图片网格与存储统计"
Cohesion: 0.11
Nodes (37): freeSpaceClass(), StorageStatsPanel(), StorageStatsPanelProps, useImageStorage(), UseImageStorageResult, useImageTags(), UseImageTagsOptions, UseImageTagsResult (+29 more)

### Community 7 - "后端客户端协议与可编辑文件"
Cohesion: 0.12
Nodes (36): clean_editable_mime_type(), editable_artifact_from_dict(), editable_extension_from_mime_type(), editable_filename_from_content_disposition(), editable_message_text(), EditableFileArtifact, extract_editable_artifacts(), extract_editable_export_paths() (+28 more)

### Community 8 - "账号表格与指标卡"
Cohesion: 0.07
Nodes (56): class-variance-authority, AccountsMetricCards(), AccountsMetricCardsProps, metricCards, MetricKey, AccountsPaginationProps, AccountsTable(), AccountsTableProps (+48 more)

### Community 9 - "前端布局与登录页"
Cohesion: 0.08
Nodes (43): radix-ui, react, react-day-picker, ImageTagEditor(), ImageTagEditorProps, metadata, RootLayout(), viewport (+35 more)

### Community 10 - "账号服务编排"
Cohesion: 0.05
Nodes (6): AccountService, InvalidAccessTokenError, fetch_remote_info(), AccountCapabilityTests, FakeBackend, model_list()

### Community 11 - "账号池与 token 获取"
Cohesion: 0.08
Nodes (6): is_image_account_available(), now_str(), parse_account(), AccountPool, TokenLogTests, anonymize_token()

### Community 12 - "DatabaseStorageBackend"
Cohesion: 0.06
Nodes (27): _deep_fill_missing(), _env_bool(), _env_int(), _looks_like_repository_default(), main(), _mask_url(), _warp_runtime_defaults(), export_to_json() (+19 more)

### Community 13 - "图片存储服务"
Cohesion: 0.12
Nodes (13): ImageStorageError, _clean(), _image_dimensions(), ImageStorageService, _is_image_rel(), _local_image_path(), _read_json_object(), _safe_relative_path() (+5 more)

### Community 14 - "R2 备份服务"
Cohesion: 0.10
Nodes (14): BackupError, BackupService, _clean(), CloudflareR2Client, _count_items(), _guess_content_type(), _hmac_sha256(), _is_backup_object() (+6 more)

### Community 15 - "备份设置前端"
Cohesion: 0.09
Nodes (45): BackupSettingsCard(), formatBytes(), formatDateTime(), getFilenameFromContentDisposition(), includeLabels, BackupDetail, BackupInclude, BackupItem (+37 more)

### Community 16 - "账号池单测"
Cohesion: 0.09
Nodes (38): _isolated(), make_account(), make_pool(), MemoryStorage, test_acquire_next_candidate_token_blocks_until_release(), test_acquire_next_candidate_token_raises_without_candidates(), test_acquire_next_candidate_token_respects_exclusions(), test_acquire_next_candidate_token_rotates_across_accounts() (+30 more)

### Community 17 - "AI 兼容 API 路由"
Cohesion: 0.14
Nodes (28): create_router(), create_chat_completion(), create_message(), create_ppt_task(), create_psd_task(), create_response(), edit_images(), generate_images() (+20 more)

### Community 18 - "OpenAIBackendCore 核心"
Cohesion: 0.09
Nodes (3): OpenAIBackendCore, test_extract_quota_and_restore_at_reads_image_gen_entry(), ensure_ok()

### Community 19 - "ChatGPT2API Changelog"
Cohesion: 0.22
Nodes (13): Account-level Proxy, ChatGPT2API Changelog, ALLOWED_CONFIG_KEYS Config Key Whitelist, default_upstream_model_name Setting, Frontend Module Split (image task state/poller, settings store), Image Generation SSE Hard Timeout, Parallel Image Generation, Stable Proxy Runtime (proxy_runtime) (+5 more)

### Community 20 - "image_stream.py"
Cohesion: 0.03
Nodes (65): main(), image_stream_error_message(), ImageContentPolicyError, ImageGenerationError, ImageStreamHardTimeoutError, ImageTaskError, is_connection_timeout_error(), is_tls_connection_error() (+57 more)

### Community 21 - "token 刷新单测"
Cohesion: 0.08
Nodes (24): expired_token(), FakePool, FakeProgress, fresh_token(), make_jwt(), make_service(), _no_auto_relogin(), test_app_session_terminated_triggers_relogin_callback() (+16 more)

### Community 22 - "连接管理适配器"
Cohesion: 0.08
Nodes (38): axios, cpaConnectionAdapter, CpaEditFields(), CpaPoolForm, Sub2APIEditFieldsProps, Sub2APIForm, ConnectionAdapter, ConnectionFormContext (+30 more)

### Community 23 - "openai_v1_chat_complete.py"
Cohesion: 0.07
Nodes (59): chat_completion_annotations(), chat_messages_from_body(), collect_chat_content(), collect_text(), completion_chunk(), completion_response(), handle(), image_chat_events() (+51 more)

### Community 24 - "日志页与配置卡片"
Cohesion: 0.11
Nodes (31): formatDuration(), getDetailText(), getStatus(), getUrls(), LogsContent(), LogsPage(), LogType, typeLabels (+23 more)

### Community 25 - "调试面板前端"
Cohesion: 0.17
Nodes (23): createClientTaskId(), EditableFilePanel(), fileNameOf(), formatElapsed(), isRunning(), mergeTasks(), Props, readFile() (+15 more)

### Community 26 - "搜索/PPT/PSD 面板"
Cohesion: 0.14
Nodes (23): react-markdown, remark-gfm, PptPanel(), PsdPanel(), cleanUrl(), MarkdownResult(), normalizeMarkdown(), SearchPanel() (+15 more)

### Community 27 - "账号数据模型"
Cohesion: 0.07
Nodes (15): account_matches_any_plan_type(), account_matches_plan_type(), account_matches_source_type(), account_payload_token(), normalize_account_type(), normalize_source_type(), parse_time(), prepare_account_payload() (+7 more)

### Community 28 - "图片编辑请求解析"
Cohesion: 0.08
Nodes (18): _clean(), _decode_base64_image(), _decode_data_url(), _download_image_url(), _extension_from_mime(), _filename_from_url(), _is_upload(), _json_image_sources() (+10 more)

### Community 29 - "test_v1_image_quota_contract.py"
Cohesion: 0.10
Nodes (12): QuotaExhaustedError, _image_error_response(), _is_quota_exhausted_error(), _compact(), _raise_quota_like_image_stream(), test_image_error_response_accepts_raw_quota_error(), test_image_error_response_accepts_wrapped_quota_error(), test_images_generations_quota_429_contract() (+4 more)

### Community 30 - "SSE 事件解析"
Cohesion: 0.11
Nodes (25): apply_patch_op(), apply_text_patch(), assistant_message_text(), assistant_raw_text(), event_assistant_text(), is_visible_assistant_message(), strip_history(), test_apply_patch_op_append_and_replace() (+17 more)

### Community 31 - "对话 payload 构建"
Cohesion: 0.10
Nodes (21): api_messages_to_conversation_messages(), conversation_payload(), image_model_settings(), FakeAPI, test_both_protocol_endpoints_share_single_implementation(), test_conversation_payload_falls_back_to_config_effort_and_drops_empty(), test_conversation_payload_skeleton_and_thinking_effort(), test_image_message_uploads_and_builds_multimodal_parts() (+13 more)

### Community 32 - "图片文件路由"
Cohesion: 0.10
Nodes (26): build_router(), delete_images_endpoint(), download_images_endpoint(), download_single_image_endpoint(), get_image(), get_image_thumbnail(), get_images(), DomainError (+18 more)

### Community 33 - "account_service.py"
Cohesion: 0.05
Nodes (8): AccountPoolProtocol, ModelRouteProvider, PasswordLoginService, ProgressTracker, _apply_relogin_update(), _build_refresh_initial(), _build_relogin_initial(), generate_pkce()

### Community 34 - "chat_completion_cache.py"
Cohesion: 0.13
Nodes (12): cache_key(), canonical_body(), _json_safe(), _message_signature(), normalize_text_messages(), build_legacy_requirements_token(), build_pow_config(), build_proof_token() (+4 more)

### Community 35 - "Sentinel PoW 与 Turnstile"
Cohesion: 0.11
Nodes (9): OrderedMap, solve_turnstile_token(), func_1(), func_17(), func_18(), func_19(), func_5(), _turnstile_to_str() (+1 more)

### Community 36 - "sub2api 集成服务"
Cohesion: 0.11
Nodes (15): Sub2apiError, _auth_headers(), _clean(), _extract_access_token(), _extract_paged_items(), _fetch_access_tokens_for_accounts(), list_remote_accounts(), list_remote_groups() (+7 more)

### Community 37 - "图片编辑器选项"
Cohesion: 0.15
Nodes (18): ImageComposerOptions, usePersistedComposerOptions(), UsePersistedComposerOptionsResult, AuthRole, ImageModel, aspectFallbackForModel(), AspectOption, aspectOptions (+10 more)

### Community 39 - "event_parse.py"
Cohesion: 0.08
Nodes (15): conversation_events(), assistant_history_messages(), assistant_history_text(), count_message_image_tokens(), count_message_text_tokens(), count_message_tokens(), encoding_for_model(), _has_image_parts() (+7 more)

### Community 40 - "Codex 生图链路"
Cohesion: 0.18
Nodes (13): codex_body_preview(), codex_event_image_result_lengths(), codex_event_summary(), codex_image_input(), codex_responses_headers(), ensure_codex_source_account(), iter_codex_image_response_events(), iter_codex_response_events() (+5 more)

### Community 41 - "test_prompt_migration.py"
Cohesion: 0.05
Nodes (26): handle(), _CapturedBackend, global_prompt(), no_global_prompt(), _patch_text_backend(), _run_codex_stream(), iter_codex_image_response_events(), test_adjacent_duplicate_dedupe_runs_after_flattening() (+18 more)

### Community 42 - "后端客户端单测"
Cohesion: 0.12
Nodes (20): ChatRequirements, FakeResponse, FakeSession, make_core(), test_chat_target_switches_between_auth_and_anon(), test_conversation_headers_conditional_sentinel_tokens(), test_decode_image_base64_supports_data_url_raw_base64_and_local_file(), test_get_chat_requirements_prepare_then_finalize_with_pow_and_turnstile() (+12 more)

### Community 43 - "json"
Cohesion: 0.04
Nodes (24): find_images(), main(), parse_events(), main(), main(), main(), request_json(), main() (+16 more)

### Community 44 - "网页搜索链路"
Cohesion: 0.16
Nodes (24): clean_search_url(), extract_search_result(), extract_search_sources(), find_search_value(), get_search_conversation(), prepare_search_conversation(), run_search_conversation(), search() (+16 more)

### Community 45 - "Chat Completion 缓存测试"
Cohesion: 0.08
Nodes (4): handle(), ChatCompletionCacheTests, fake_collect_text(), fake_stream_text_deltas()

### Community 47 - "Auth Key 服务"
Cohesion: 0.21
Nodes (3): AuthService, _hash_key(), AuthServiceTests

### Community 48 - "InvalidRequestError"
Cohesion: 0.10
Nodes (18): InvalidRequestError, _decode_json_image_string(), _decode_message_image_object(), _decode_message_image_url(), extract_chat_image(), extract_image_from_message_content(), _image_extension(), _message_image_url() (+10 more)

### Community 49 - "前端 lint/格式化依赖"
Cohesion: 0.09
Nodes (21): clsx, date-fns, eslint, localforage, prettier, prettier-plugin-organize-imports, prettier-plugin-tailwindcss, react-dom (+13 more)

### Community 50 - "image-composer.tsx"
Cohesion: 0.10
Nodes (45): AccountsPagination(), CodexAuthPanel(), CodexAuthPanelProps, SessionPanel(), SessionPanelProps, ChatPanel(), messageImages(), messageText() (+37 more)

### Community 51 - "CPA 连接池服务"
Cohesion: 0.12
Nodes (7): CPAConfig, CPAImportService, fetch_remote_access_token(), _management_headers(), _new_id(), _normalize_import_job(), _normalize_pool()

### Community 52 - "通用进度追踪器"
Cohesion: 0.20
Nodes (13): _apply_refresh_update(), make_tracker(), test_apply_update_without_callback_only_counts(), test_auto_complete_marks_done_when_processed_reaches_total(), test_clean_removes_record(), test_concurrent_updates_keep_processed_consistent(), test_finish_with_error_records_error_field(), test_finish_without_result_keeps_result_none() (+5 more)

### Community 53 - "outlook 邮箱 token"
Cohesion: 0.13
Nodes (17): build_parser(), _clean(), _decode_header(), exchange_refresh_token(), _graph_sender(), _http_request(), HttpResponse, main() (+9 more)

### Community 54 - "Anthropic Messages 协议"
Cohesion: 0.12
Nodes (19): _compact_message_text(), compact_system(), _compact_system_text(), content_blocks(), message_request(), message_response(), MessageRequest, parse_tool_calls() (+11 more)

### Community 55 - "日志服务"
Cohesion: 0.18
Nodes (8): _collect_account_emails(), _collect_conversation_ids(), _collect_urls(), LogService, _next_item(), _request_excerpt(), _strip_internal_response_fields(), test_log_service_day_filter_accepts_utc_format()

### Community 56 - "内容风控过滤"
Cohesion: 0.11
Nodes (13): check_request(), _on_failure(), _extract_review_decision(), _is_allow_decision(), _is_reject_decision(), _resolve_fail_open(), _sanitize_for_review(), _text() (+5 more)

### Community 57 - "图片工作台页面状态"
Cohesion: 0.23
Nodes (16): buildDeletedTurnPartConversation(), buildQueuedTurn(), buildRegeneratedConversation(), buildRetryImageConversation(), buildSubmittedConversation(), createLoadingImages(), deriveTurnStatus(), finalizeIdleQueuedTurn() (+8 more)

### Community 58 - "FakeBackend"
Cohesion: 0.24
Nodes (3): _conversation(), FakeBackend, MultiImageResultTests

### Community 59 - "API 异常处理器"
Cohesion: 0.13
Nodes (15): _compatible_error_response(), install_exception_handlers(), domain_error_handler(), http_exception_handler(), validation_exception_handler(), _is_anthropic_messages_path(), _is_openai_compatible_path(), _protocol_error_response() (+7 more)

### Community 60 - "图片标签路由"
Cohesion: 0.14
Nodes (17): build_router(), cleanup_to_target(), compress_all_images(), delete_image_tag(), get_image_storage(), list_image_tags(), update_image_tags(), ImageTagsRequest (+9 more)

### Community 62 - "可编辑文件任务服务"
Cohesion: 0.20
Nodes (9): _clean(), _editable_access_token(), EditableFileTaskService, _elapsed_seconds(), _file_url(), _owner_id(), _public_task(), _task_key() (+1 more)

### Community 63 - "应用工厂与路由装配"
Cohesion: 0.09
Nodes (8): create_router(), create_app(), __call__(), lifespan(), serve_web(), resolve_web_asset(), start_limited_account_watcher(), start_image_cleanup_scheduler()

### Community 64 - "配置项文档"
Cohesion: 0.14
Nodes (17): ai_review（AI 内容审查）, auth-key（API 访问密钥）, backup（Cloudflare R2 自动备份）, chat_completion_cache（会话缓存）, config.json 主配置文件, 生图轮询与二次确认参数, image_storage（WebDAV 图片存储）, third_party_apps（第三方应用入口） (+9 more)

### Community 65 - "图片任务服务实现"
Cohesion: 0.22
Nodes (7): _clean(), _collect_image_urls(), ImageTaskService, progress_callback(), _owner_id(), _public_task(), _task_key()

### Community 66 - "image_tokens.py"
Cohesion: 0.09
Nodes (30): collect_image_outputs(), stream_image_chunks(), stream_image_outputs_with_pool(), count_text_tokens(), encode_images(), image_chat_response(), _composite_mask(), handle() (+22 more)

### Community 67 - "UTC 时间口径"
Cohesion: 0.11
Nodes (10): _timestamp(), test_account_parse_time_accepts_new_utc_format(), test_parse_timestamp_accepts_both_legacy_forms(), test_parse_timestamp_forms(), test_parse_timestamp_round_trip(), test_task_timestamp_legacy_and_new_forms(), test_utc_iso_from_epoch_fixed_value(), test_utc_now_iso_format_and_clock() (+2 more)

### Community 68 - "图片会话前端存储"
Cohesion: 0.21
Nodes (22): sortImageConversations(), clearImageConversations(), dataUrlMimeType(), deleteImageConversation(), getLegacyReferenceImages(), getTimestamp(), ImageConversationsState, ImageConversationStats (+14 more)

### Community 69 - "服务层测试假件"
Cohesion: 0.10
Nodes (5): FakeAccountService, FakeConfig, FakeProxySettings, FakeStorage, ProxyRuntimeApiTests

### Community 70 - "build_prompt_plan"
Cohesion: 0.07
Nodes (30): build_prompt_plan(), render_codex_instructions(), test_auto_quality_is_short_circuited(), test_build_prompt_plan_is_idempotent_for_system(), test_caller_supplied_system_message_is_preserved(), test_caller_system_containing_global_is_not_rewritten(), test_empty_prompt_derived_from_user_messages(), test_empty_prompt_without_messages_stays_empty() (+22 more)

### Community 72 - "update_conversation_state"
Cohesion: 0.20
Nodes (12): conversation_base_event(), ConversationState, is_image_tool_event(), _is_user_message_event(), update_conversation_state(), test_conversation_base_event_carries_state_snapshot(), test_is_image_tool_event_detects_async_task_and_asset_pointer(), test_update_conversation_state_accepts_patch_event_with_asset_pointer() (+4 more)

### Community 73 - "shadcn 组件配置"
Cohesion: 0.10
Nodes (19): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+11 more)

### Community 74 - "账号 CRUD 路由"
Cohesion: 0.11
Nodes (11): AccountCreateRequest, AccountDeleteRequest, build_router(), create_accounts(), delete_accounts(), get_accounts(), download_timestamp(), unique_tokens() (+3 more)

### Community 75 - "Chat Completion 缓存"
Cohesion: 0.38
Nodes (3): CacheEntry, ChatCompletionCache, InflightCall

### Community 76 - "图片任务 API 客户端"
Cohesion: 0.26
Nodes (11): createImageEditTask(), createImageGenerationTask(), fetchImageTasks(), ImageTask, ImageTaskListResponse, abortableSleep(), activeQueueControllers, ConversationQueueOptions (+3 more)

### Community 77 - "TypeScript 编译配置"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 78 - "配置加载测试"
Cohesion: 0.18
Nodes (7): ConfigLoadingTests, _make_store(), test_save_settings_unknown_key_returns_400(), test_update_accepts_every_whitelisted_key(), test_update_rejects_auth_key_and_backup_state(), test_update_rejects_unknown_top_level_keys(), test_update_whitelist_is_top_level_dimension()

### Community 81 - "CPA 池路由"
Cohesion: 0.17
Nodes (15): build_router(), cpa_pool_files(), cpa_pool_import(), cpa_pool_import_progress(), create_cpa_pool(), delete_cpa_pool(), list_cpa_pools(), update_cpa_pool() (+7 more)

### Community 82 - "test_prompt_characterization.py"
Cohesion: 0.08
Nodes (21): build_tool_prompt(), _has_claude_code_system(), merge_system(), _tool_meta(), test_build_tool_prompt_joins_multiple_tools_with_newline(), test_build_tool_prompt_renders_tool_block_and_rules(), test_build_tool_prompt_returns_empty_for_empty_list(), test_build_tool_prompt_returns_empty_for_non_list() (+13 more)

### Community 83 - "前端运行时依赖"
Cohesion: 0.12
Nodes (17): dependencies, axios, class-variance-authority, clsx, date-fns, localforage, lucide-react, next (+9 more)

### Community 84 - "图片结果渲染"
Cohesion: 0.16
Nodes (18): b64BlobUrlCache, base64SizeCache, downloadStoredImage(), formatBase64ImageSize(), formatDuration(), formatElapsed(), formatImageDimensions(), getProgressLabel() (+10 more)

### Community 85 - "功能状态清单"
Cohesion: 0.14
Nodes (16): 功能状态（Feature Status）, Anthropic 协议支持 POST /v1/messages, 文本补全缓存与重复请求合并（chat_completion_cache）, 面向图片工作流的 POST /v1/chat/completions, Codex 画图接口逆向链路, POST /v1/complete 文本补全与流式输出, Docker 自托管部署（多架构镜像）, 图片并行生成（image_parallel_generation） (+8 more)

### Community 86 - "配置归一化"
Cohesion: 0.19
Nodes (8): _normalize_backup_include(), _normalize_backup_settings(), _normalize_bool(), _normalize_chat_completion_cache_settings(), _normalize_image_storage_settings(), _normalize_positive_int(), _normalize_third_party_apps_settings(), _validate_image_storage_settings()

### Community 88 - "健康监控页与身份路由"
Cohesion: 0.15
Nodes (6): render_health_dashboard(), build_router(), get_version(), login(), build_router(), health_dashboard()

### Community 89 - "上游 Conversation SSE 协议"
Cohesion: 0.15
Nodes (15): 上游 Conversation SSE 协议说明, conversation_id 字段, Conversation SSE 流式返回协议, [DONE] 流结束标记, c（消息序号/游标字段）, message_marker 事件（user_visible_token / last_token）, moderation 事件（moderation_response.blocked）, o（patch 操作字段：add / append / replace / patch） (+7 more)

### Community 91 - "前端开发依赖"
Cohesion: 0.13
Nodes (15): devDependencies, eslint, eslint-config-next, eslint-config-prettier, prettier, prettier-plugin-organize-imports, prettier-plugin-tailwindcss, tailwindcss (+7 more)

### Community 92 - "Next 配置与版本检查"
Cohesion: 0.46
Nodes (6): isNewerVersion(), readLocalReleases(), toVersionParts(), useVersionCheck(), parseChangelog(), ReleaseInfo

### Community 93 - "输出注解清洗"
Cohesion: 0.19
Nodes (9): sanitize_output_text(), annotation_text(), is_internal_annotation_part(), readable_annotation_part(), replace_annotation(), replace_annotation_before_punctuation(), test_sanitize_output_text_keeps_url_annotation_label(), test_sanitize_output_text_removes_internal_cite_pointer() (+1 more)

### Community 94 - "代理运行时配置测试"
Cohesion: 0.26
Nodes (3): _normalize_proxy_runtime_settings(), _normalize_status_codes(), ProxyRuntimeConfigTests

### Community 95 - "auth.ts"
Cohesion: 0.14
Nodes (26): next, SkillPanel(), subscribeNoop(), LoginPage(), HomePage(), AuthGuardProps, webConfig, useAuthGuard() (+18 more)

### Community 97 - "conversation 事件流解析"
Cohesion: 0.17
Nodes (7): iter_conversation_payloads(), message_event_payload(), test_iter_conversation_payloads_accumulates_deltas(), test_iter_conversation_payloads_done_and_raw_events(), test_iter_conversation_payloads_empty_payloads_skipped(), test_iter_conversation_payloads_non_dict_json_becomes_event(), test_iter_conversation_payloads_skips_history_replay()

### Community 99 - "参考图前端 hooks"
Cohesion: 0.35
Nodes (10): useReferenceImages(), UseReferenceImagesOptions, UseReferenceImagesResult, buildReferenceImageFromResult(), buildReferenceImageFromStoredImage(), dataUrlToFile(), fetchImageAsFile(), readFileAsDataUrl() (+2 more)

### Community 100 - "account-import-dialog.tsx"
Cohesion: 0.15
Nodes (22): sonner, AccountImportDialogProps, ImportMethod, MethodCardProps, methodMeta, AccountJsonPanelProps, AccountJsonParseResult, OAuthPanel() (+14 more)

### Community 102 - "设置加载与路径"
Cohesion: 0.22
Nodes (8): _is_invalid_auth_key(), load_backup_state(), _load_settings(), LoadedSettings, _normalize_auth_key(), _normalize_backup_state(), _read_json_object(), save_backup_state()

### Community 104 - "editable_file.py"
Cohesion: 0.17
Nodes (19): BackendClient, decode_editable_base64_image(), download_editable_artifact(), download_url_from_response(), editable_browser_headers(), editable_conversation_document_headers(), editable_download_headers(), editable_prompt() (+11 more)

### Community 105 - "文本账号路由单测"
Cohesion: 0.42
Nodes (3): ModelUnavailableError, ModelRoute, TextAccountRoutingTests

### Community 106 - "lucide-react"
Cohesion: 0.17
Nodes (20): lucide-react, MethodCard(), ImageGridCard(), ImageGridCardProps, ImageGrid(), ImageGridProps, ApiDoc, ApiDocsCard() (+12 more)

### Community 107 - "内存存储后端"
Cohesion: 0.23
Nodes (3): AccountExportTests, make_jwt(), MemoryStorage

### Community 109 - "OAuth 刷新校验脚本"
Cohesion: 0.36
Nodes (4): diagnose(), _fmt_remaining(), force_refresh(), main()

### Community 113 - "滚动位置恢复"
Cohesion: 0.43
Nodes (6): getResultsDistanceFromBottom(), loadScrollPositions(), saveScrollPositions(), useScrollRestore(), UseScrollRestoreResult, SCROLL_POSITIONS_STORAGE_KEY

### Community 114 - "图片生成结果判定流程"
Cohesion: 0.33
Nodes (7): POST /v1/images/generations（OpenAI 兼容图片生成）, 完整会话明细查询（补找图片工具输出）, file-service:// 指针, async_task_type = image_gen, SSE 结束后的结果判断流程, server_ste_metadata 调度与工具状态事件, role=tool 图片工具消息

### Community 115 - "上游消息结构字段"
Cohesion: 0.29
Nodes (7): asset_pointer 图片指针, message.content.parts 内容片段, message.content.content_type（text / multimodal_text / model_editable_context）, file_upload 上传占位指针, input_message 用户输入事件, message 对象（author/content/status/end_turn/metadata）, sediment:// 指针

### Community 116 - "前端 npm 脚本"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, start, test, typecheck

### Community 117 - "test_image_task.py"
Cohesion: 0.19
Nodes (13): check_task_error(), extract_image_reference_ids(), extract_image_tool_records(), find_content_policy_error_in_conversation(), has_image_asset_pointer(), is_content_policy_error(), test_check_task_error_structured_fields(), test_extract_image_reference_ids_handles_scalars_and_empty() (+5 more)

### Community 118 - "第三方连接管理功能"
Cohesion: 0.67
Nodes (4): 账号池管理（号池）, 账号刷新异步进度追踪与重新登录, CPA 连接管理与按需导入, sub2api 连接管理与账号导入

### Community 119 - "前端图片工作流特性"
Cohesion: 0.67
Nodes (3): 前端图片工作台, 图片生成进度追踪（上传/预热/获取 token/生成中）, 前端图片懒加载与滚动位置恢复（LazyImage / bfcache）

### Community 120 - "query_backend_tasks"
Cohesion: 0.13
Nodes (11): download_image_bytes(), get_attachment_download_url(), get_file_download_url(), query_backend_tasks(), FakeResponse, FakeSession, test_download_image_bytes_dedups_identical_content(), __init__() (+3 more)

### Community 136 - "_render_text_messages"
Cohesion: 0.12
Nodes (8): _render_text_messages(), test_text_messages_accept_segmented_system(), test_text_messages_are_idempotent(), test_text_messages_ignore_non_list_input(), test_text_messages_merge_request_system_after_global(), test_text_messages_prepend_global_system(), test_text_messages_skip_non_dict_items(), test_text_messages_without_global_keep_messages_unchanged()

### Community 137 - "image/page.tsx"
Cohesion: 0.29
Nodes (12): ImageDeleteConfirmTarget, ImageSidebar(), ImagePage(), ImagePageContent(), resumeImagePoll(), abortAllConversationQueues(), isConversationQueueActive(), formatAvailableQuota() (+4 more)

### Community 138 - "image_task.py"
Cohesion: 0.18
Nodes (7): walk(), resolve_conversation_image_urls(), resolve_image_urls(), test_resolve_image_urls_continues_on_download_errors(), test_resolve_image_urls_without_conversation_skips_attachments(), test_add_unique_appends_only_new_non_empty_values(), add_unique()

### Community 140 - "build_router"
Cohesion: 0.20
Nodes (6): spawn_background_task(), build_router(), get_refresh_progress(), get_relogin_progress(), re_login_accounts(), refresh_accounts()

### Community 142 - "OpenAI-Compatible Image API Surface"
Cohesion: 0.20
Nodes (10): allow_remote_image_fetch Deployment Switch, Chat Completion Cache and Request Coalescing, Editable PSD/PPT File Generation, POST /v1/chat/completions, Editable File Generation (PPT/PSD), GET /v1/editable-file-tasks, POST /v1/images/edits, POST /v1/messages (Anthropic Messages) (+2 more)

### Community 143 - "ChatGPT2API Project"
Cohesion: 0.20
Nodes (10): Backend Package Split (services/backend, services/account), Incremental Database Sync, ChatGPT Search API Reverse Engineering, POST /v1/search (chatgpt2api search endpoint), chatgpt2api-search Skill, auth-key Bearer Authentication, ChatGPT2API Project, Reverse-Engineering Non-Commercial Disclaimer (+2 more)

### Community 144 - "test_build_prompt_plan_is_idempotent_with_multi_part_system"
Cohesion: 0.22
Nodes (4): global_prompt(), no_global_prompt(), test_build_prompt_plan_is_idempotent_with_multi_part_system(), test_global_prompt_is_read_at_call_time()

### Community 146 - "ai.py"
Cohesion: 0.36
Nodes (6): AnthropicMessageRequest, ChatCompletionRequest, EditableFileTaskRequest, ImageGenerationRequest, ResponseCreateRequest, SearchRequest

### Community 147 - "Account Pool Management"
Cohesion: 0.22
Nodes (9): Async Account Refresh / Re-login, Image Task Progress Tracking, outlook_token Email Pool, QuotaExhaustedError Domain Exception, sub2api Account Import, Account Import Methods (CPA / sub2api / access_token), Account Pool Management, POST /v1/images/generations (+1 more)

### Community 148 - "next.config.ts"
Cohesion: 0.22
Nodes (3): vitest, nextConfig, projectRoot

### Community 150 - "WARP 部署 app 服务（chatgpt2api-warp）"
Cohesion: 0.36
Nodes (8): Cloudflare clearance 过墙, proxy_runtime（稳定代理运行时）, WARP 部署 app 服务（chatgpt2api-warp）, flaresolverr（Cloudflare 挑战求解服务）, init-config 一次性配置生成容器, privoxy（HTTP 转 SOCKS 代理）, warp-proxy（Cloudflare WARP 出站）, WARP / FlareSolverr 部署方式

### Community 151 - "test_picture_prompt_empty_prompt_falls_back_to_image_only"
Cohesion: 0.14
Nodes (4): test_picture_prompt_empty_prompt_falls_back_to_image_only(), test_picture_prompt_joins_with_blank_line(), test_picture_prompt_preserves_prompt_whitespace(), test_picture_prompt_returns_prompt_when_global_empty()

### Community 159 - "Codex Image Generation Reverse Engineering"
Cohesion: 0.50
Nodes (4): Codex Image Models (codex-gpt-image-2.5-flare / sunburst), GET /api/upstream-models, Codex Image Generation Reverse Engineering, GET /v1/models

### Community 160 - "Docker Self-Hosted Deployment"
Cohesion: 0.67
Nodes (4): GHCR Image ghcr.io/{owner}/chatgpt2api, Multi-arch Build (amd64/arm64 via QEMU + Buildx), Publish Docker Image Workflow, Docker Self-Hosted Deployment

### Community 161 - "eslint.config.mjs"
Cohesion: 0.50
Nodes (3): eslint-config-next, eslint-config-prettier, eslintConfig

### Community 167 - "overrides"
Cohesion: 0.67
Nodes (3): overrides, @types/react, @types/react-dom

## Knowledge Gaps
- **59 isolated node(s):** `chatgpt2api`, `@tailwindcss/postcss`, `@types/node`, `@types/react`, `@types/react-dom` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1085 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **50 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_admin()` connect `账号 OAuth/刷新路由` to `图片文件路由`, `账号 API 路由拆分`, `账号 CRUD 路由`, `build_router`, `CPA 池路由`, `AI 兼容 API 路由`, `图片标签路由`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `AccountService` (e.g. with `ModelRouteProvider` and `PasswordLoginService`) actually correct?**
  _`AccountService` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `chatgpt2api`, `@tailwindcss/postcss`, `@types/node` to the rest of the system?**
  _59 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FlareSolverr 过墙服务` be split into smaller, more focused modules?**
  _Cohesion score 0.057203956161454156 - nodes in this community are weakly interconnected._
- **Why does `ConfigStore` connect `配置存储 ConfigStore` to `设置加载与路径`, `StorageBackend`, `json`, `配置加载测试`, `InvalidRequestError`, `配置归一化`, `健康监控页与身份路由`, `先 check 再 hit 机制`, `图片二次确认机制`, `代理运行时配置测试`, `应用工厂与路由装配`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `账号 OAuth/刷新路由` be split into smaller, more focused modules?**
  _Cohesion score 0.04408749145591251 - nodes in this community are weakly interconnected._
- **Why does `build_prompt_plan()` connect `build_prompt_plan` to `image_tokens.py`, `BuildImagePromptTests`, `event_parse.py`, `_render_text_messages`, `test_prompt_migration.py`, `test_build_prompt_plan_is_idempotent_with_multi_part_system`, `test_prompt_characterization.py`, `image_stream.py`, `Anthropic Messages 协议`, `openai_v1_chat_complete.py`, `test_picture_prompt_empty_prompt_falls_back_to_image_only`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._