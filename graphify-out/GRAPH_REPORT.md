# Graph Report - chatgpt2api  (2026-11-01)

## Corpus Check
- 313 files · ~148,557 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: (none) 8, .lock 2, .example 1)

## Summary
- 3694 nodes · 10275 edges · 136 communities (105 shown, 31 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 462 edges (avg confidence: 0.88)
- Token cost: 201,588 input · 0 output

## Community Hubs (Navigation)
- 生图流式错误处理
- FlareSolverr 过墙服务
- 账号 OAuth/刷新路由
- 账号编辑导入弹窗
- 生图任务轮询与下载
- 账号 API 路由拆分
- 图片网格与存储统计
- 后端客户端协议与可编辑文件
- 账号表格与指标卡
- 前端布局与登录页
- 账号服务编排
- 账号池与 token 获取
- 消息图片解析与存储
- 图片存储服务
- R2 备份服务
- 备份设置前端
- 账号池单测
- AI 兼容 API 路由
- OpenAIBackendCore 核心
- 变更日志特性条目
- 图片结果格式化与重试
- token 刷新单测
- 连接管理适配器
- OpenAI 兼容协议转换
- 日志页与配置卡片
- 调试面板前端
- 搜索/PPT/PSD 面板
- 账号数据模型
- 图片编辑请求解析
- 图片任务 API 测试
- SSE 事件解析
- 对话 payload 构建
- 图片文件路由
- 号池协议与密码登录
- 后端客户端上下文与登录
- Sentinel PoW 与 Turnstile
- sub2api 集成服务
- 图片编辑器选项
- 配置存储 ConfigStore
- 消息工具与 token 计数
- Codex 生图链路
- Responses 协议与图片 token
- 后端客户端单测
- 生图脚本客户端
- 网页搜索链路
- Chat Completion 缓存测试
- 存储后端抽象
- Auth Key 服务
- 领域异常与模型服务
- 前端 lint/格式化依赖
- 图片标签编辑前端
- CPA 连接池服务
- 通用进度追踪器
- outlook 邮箱 token
- Anthropic Messages 协议
- 日志服务
- 内容风控过滤
- 图片工作台页面状态
- 生图任务服务与后端组装
- API 异常处理器
- 图片标签路由
- 模型目录服务
- 可编辑文件任务服务
- 应用工厂与路由装配
- 配置项文档
- 图片任务服务实现
- 图片 token 计数
- UTC 时间口径
- 图片会话前端存储
- 服务层测试假件
- 存储迁移脚本
- Account Pydantic 模型
- Codex SSE 解析脚本
- shadcn 组件配置
- 账号 CRUD 路由
- Chat Completion 缓存
- 图片任务 API 客户端
- TypeScript 编译配置
- 配置加载测试
- OAuth 登录服务
- 脱敏日志器
- CPA 池路由
- Git 存储后端
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
- 代理初始化脚本
- 后端客户端账号读取协议
- conversation 事件流解析
- 图片编辑 JSON API 测试
- 参考图前端 hooks
- 图片灯箱组件
- 代理初始化单测
- 设置加载与路径
- 图片任务服务单测
- PPT/PSD 脚本客户端
- 文本账号路由单测
- 文本协议路由测试
- 内存存储后端
- size_enabled 策略测试
- OAuth 刷新校验脚本
- 生图错误响应映射
- 模型列表测试
- Anthropic Messages 测试
- 滚动位置恢复
- 图片生成结果判定流程
- 上游消息结构字段
- 前端 npm 脚本
- 第三方连接管理功能
- 前端图片工作流特性
- PostCSS 配置
- Atlas Cloud 标志
- IPWO 标志
- 坤肉AI 标志
- 项目根
- GitHub 图标
- Next.js 标志
- OpenAI 图标
- Vercel 标志

## God Nodes (most connected - your core abstractions)
1. `require_admin()` - 92 edges
2. `cn()` - 92 edges
3. `AccountService` - 82 edges
4. `Button()` - 77 edges
5. `httpRequest()` - 71 edges
6. `react` - 62 edges
7. `ConfigStore` - 53 edges
8. `lucide-react` - 52 edges
9. `AccountPool` - 50 edges
10. `OpenAIBackendAPI` - 47 edges

## Surprising Connections (you probably didn't know these)
- `POST /v1/search (chatgpt2api search endpoint)` --semantically_similar_to--> `POST /v1/search (web search)`  [INFERRED] [semantically similar]
  .codex/skills/chatgpt2api-search/SKILL.md → README.md
- `build_router()` --uses--> `CpaError`  [INFERRED]
  api/accounts/cpa.py → services/errors.py
- `build_router()` --uses--> `OAuthLoginError`  [INFERRED]
  api/accounts/oauth.py → services/oauth_login_service.py
- `install_exception_handlers()` --uses--> `DomainError`  [INFERRED]
  api/errors.py → services/errors.py
- `build_test_router()` --uses--> `BackupError`  [INFERRED]
  api/system/backup.py → services/backup_service.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **ChatGPT2API Web Search Capability** — codex_skills_chatgpt2api_search_skill_search_skill, codex_skills_chatgpt2api_search_skill_search_endpoint, readme_search_endpoint, changelog_search_api [INFERRED 0.90]
- **Proxy Runtime / Egress Chain (WARP + FlareSolverr + priority)** — readme_warp_proxy_stack, readme_proxy_priority, changelog_proxy_runtime, changelog_warp_flaresolverr, changelog_account_proxy [INFERRED 0.85]
- **OpenAI-Compatible Endpoint Surface** — readme_openai_compatible_api, readme_images_generations_endpoint, readme_images_edits_endpoint, readme_chat_completions_endpoint, readme_responses_endpoint, readme_messages_endpoint, readme_models_endpoint, readme_auth_key [EXTRACTED 1.00]
- **WARP + FlareSolverr 代理链路** — docker_compose_warp_yml_warp_proxy, docker_compose_warp_yml_privoxy, docker_compose_warp_yml_flaresolverr, docker_compose_warp_yml_init_config, docker_compose_warp_yml_app_service [EXTRACTED 1.00]
- **config.json 配置分区** — config_example_md_config_json, config_example_md_proxy_runtime, config_example_md_backup_r2, config_example_md_image_storage_webdav, config_example_md_chat_completion_cache [EXTRACTED 1.00]
- **部署与升级流程** — docs_deployment_md_deployment_guide, docs_deployment_md_persistent_files, docs_deployment_md_upgrade_backup, docs_deployment_md_storage_backend [EXTRACTED 1.00]
- **图片输出判定条件组合（role=tool + image_gen + 可解析指针）** — docs_upstream_sse_conversation_md_tool_message, docs_upstream_sse_conversation_md_image_gen_async_task, docs_upstream_sse_conversation_md_file_service_pointer, docs_upstream_sse_conversation_md_sediment_pointer [EXTRACTED 1.00]
- **上游 SSE 事件类型族（启动/输入/标记/标题/元数据/moderation）** — docs_upstream_sse_conversation_md_resume_conversation_token, docs_upstream_sse_conversation_md_input_message, docs_upstream_sse_conversation_md_message_marker, docs_upstream_sse_conversation_md_title_generation, docs_upstream_sse_conversation_md_server_ste_metadata, docs_upstream_sse_conversation_md_moderation_event [EXTRACTED 1.00]
- **OpenAI 兼容接口面（images / chat / responses / models / messages）** — docs_feature_status_en_md_images_generations, docs_feature_status_en_md_images_edits, docs_feature_status_en_md_chat_completions, docs_feature_status_en_md_responses, docs_feature_status_en_md_models_endpoint, docs_feature_status_en_md_anthropic_messages [EXTRACTED 1.00]

## Communities (136 total, 31 thin omitted)

### Community 0 - "生图流式错误处理"
Cohesion: 0.05
Nodes (39): image_stream_error_message(), ImageGenerationError, is_connection_timeout_error(), is_tls_connection_error(), is_token_invalid_error(), _acquire_image_token(), _build_image_result(), collect_image_outputs() (+31 more)

### Community 1 - "FlareSolverr 过墙服务"
Cohesion: 0.06
Nodes (30): test_proxy_clearance_endpoint(), test_proxy_endpoint(), _clean(), ClearanceBundle, _coerce_timeout(), _colon_proxy_to_url(), _cookies_to_header(), _domain_matches() (+22 more)

### Community 2 - "账号 OAuth/刷新路由"
Cohesion: 0.04
Nodes (52): build_router(), finish_oauth_login(), start_oauth_login(), build_router(), get_refresh_progress(), get_relogin_progress(), re_login_accounts(), refresh_accounts() (+44 more)

### Community 3 - "账号编辑导入弹窗"
Cohesion: 0.10
Nodes (59): lucide-react, AccountEditDialog(), AccountEditDialogProps, AccountImportDialog(), AccountImportDialogProps, ImportMethod, MethodCardProps, methodMeta (+51 more)

### Community 4 - "生图任务轮询与下载"
Cohesion: 0.05
Nodes (49): check_task_error(), download_image_bytes(), extract_image_reference_ids(), walk(), extract_image_tool_records(), find_content_policy_error_in_conversation(), get_attachment_download_url(), get_file_download_url() (+41 more)

### Community 5 - "账号 API 路由拆分"
Cohesion: 0.05
Nodes (19): AccountCreateRequest, AccountDeleteRequest, AccountExportRequest, OAuthLoginFinishRequest, OAuthLoginStartRequest, AccountRefreshRequest, Sub2APIImportRequest, Sub2APIServerCreateRequest (+11 more)

### Community 6 - "图片网格与存储统计"
Cohesion: 0.08
Nodes (53): react, sonner, ImageGridCard(), ImageGridCardProps, ImageGrid(), ImageGridProps, freeSpaceClass(), StorageStatsPanel() (+45 more)

### Community 7 - "后端客户端协议与可编辑文件"
Cohesion: 0.09
Nodes (55): BackendClient, clean_editable_mime_type(), decode_editable_base64_image(), download_editable_artifact(), download_url_from_response(), editable_artifact_from_dict(), editable_browser_headers(), editable_conversation_document_headers() (+47 more)

### Community 8 - "账号表格与指标卡"
Cohesion: 0.08
Nodes (51): MethodCard(), AccountsMetricCards(), AccountsMetricCardsProps, metricCards, MetricKey, AccountsPaginationProps, AccountsTable(), AccountsTableProps (+43 more)

### Community 9 - "前端布局与登录页"
Cohesion: 0.07
Nodes (49): localforage, next, react-dom, metadata, RootLayout(), viewport, LoginPage(), HomePage() (+41 more)

### Community 10 - "账号服务编排"
Cohesion: 0.06
Nodes (6): AccountService, InvalidAccessTokenError, fetch_remote_info(), AccountExportTests, make_jwt(), AccountCapabilityTests

### Community 11 - "账号池与 token 获取"
Cohesion: 0.06
Nodes (6): parse_account(), AccountPool, _apply_relogin_update(), QuotaExhaustedError, TokenLogTests, anonymize_token()

### Community 12 - "消息图片解析与存储"
Cohesion: 0.07
Nodes (24): _decode_json_image_string(), _decode_message_image_object(), _decode_message_image_url(), extract_chat_image(), extract_image_from_message_content(), _image_extension(), _message_image_url(), AccountModel (+16 more)

### Community 13 - "图片存储服务"
Cohesion: 0.09
Nodes (15): ImageStorageError, NotFoundError, _clean(), _image_dimensions(), ImageStorageService, _is_image_rel(), _local_image_path(), _read_json_object() (+7 more)

### Community 14 - "R2 备份服务"
Cohesion: 0.10
Nodes (14): BackupError, BackupService, _clean(), CloudflareR2Client, _count_items(), _guess_content_type(), _hmac_sha256(), _is_backup_object() (+6 more)

### Community 15 - "备份设置前端"
Cohesion: 0.09
Nodes (48): BackupSettingsCard(), formatBytes(), formatDateTime(), getFilenameFromContentDisposition(), includeLabels, ActionResult, BackupDetail, BackupInclude (+40 more)

### Community 16 - "账号池单测"
Cohesion: 0.09
Nodes (38): _isolated(), make_account(), make_pool(), MemoryStorage, test_acquire_next_candidate_token_blocks_until_release(), test_acquire_next_candidate_token_raises_without_candidates(), test_acquire_next_candidate_token_respects_exclusions(), test_acquire_next_candidate_token_rotates_across_accounts() (+30 more)

### Community 17 - "AI 兼容 API 路由"
Cohesion: 0.10
Nodes (35): AnthropicMessageRequest, ChatCompletionRequest, create_router(), create_chat_completion(), create_message(), create_ppt_task(), create_psd_task(), create_response() (+27 more)

### Community 18 - "OpenAIBackendCore 核心"
Cohesion: 0.09
Nodes (6): OpenAIBackendCore, ChatRequirements, ImageStreamHardTimeoutError, test_extract_quota_and_restore_at_reads_image_gen_entry(), ensure_ok(), new_uuid()

### Community 19 - "变更日志特性条目"
Cohesion: 0.06
Nodes (50): Account-level Proxy, Async Account Refresh / Re-login, allow_remote_image_fetch Deployment Switch, Backend Package Split (services/backend, services/account), ChatGPT2API Changelog, Chat Completion Cache and Request Coalescing, Codex Image Models (codex-gpt-image-2.5-flare / sunburst), ALLOWED_CONFIG_KEYS Config Key Whitelist (+42 more)

### Community 20 - "图片结果格式化与重试"
Cohesion: 0.07
Nodes (27): public_image_error_message(), _codex_response_images(), format_image_result(), is_model_text_reply_instead_of_image(), _poll_image_results_with_retry(), save_image_bytes(), _fake_saver(), FakeBackend (+19 more)

### Community 21 - "token 刷新单测"
Cohesion: 0.08
Nodes (24): expired_token(), FakePool, FakeProgress, fresh_token(), make_jwt(), make_service(), _no_auto_relogin(), test_app_session_terminated_triggers_relogin_callback() (+16 more)

### Community 22 - "连接管理适配器"
Cohesion: 0.08
Nodes (38): axios, cpaConnectionAdapter, CpaEditFields(), CpaPoolForm, Sub2APIEditFieldsProps, Sub2APIForm, ConnectionAdapter, ConnectionFormContext (+30 more)

### Community 23 - "OpenAI 兼容协议转换"
Cohesion: 0.12
Nodes (35): InvalidRequestError, parse_image_count(), encode_images(), chat_completion_annotations(), chat_image_args(), chat_messages_from_body(), collect_chat_content(), collect_text() (+27 more)

### Community 24 - "日志页与配置卡片"
Cohesion: 0.13
Nodes (38): radix-ui, AccountsPagination(), ImageComposer(), formatDuration(), getDetailText(), getStatus(), getUrls(), LogsContent() (+30 more)

### Community 25 - "调试面板前端"
Cohesion: 0.09
Nodes (38): CodexAuthPanel(), CodexAuthPanelProps, SessionPanel(), SessionPanelProps, ChatPanel(), messageImages(), messageText(), readImage() (+30 more)

### Community 26 - "搜索/PPT/PSD 面板"
Cohesion: 0.09
Nodes (35): react-markdown, remark-gfm, PptPanel(), PsdPanel(), cleanUrl(), MarkdownResult(), normalizeMarkdown(), SearchPanel() (+27 more)

### Community 27 - "账号数据模型"
Cohesion: 0.07
Nodes (13): account_matches_any_plan_type(), account_matches_plan_type(), account_matches_source_type(), account_payload_token(), is_image_account_available(), normalize_account_type(), normalize_source_type(), now_str() (+5 more)

### Community 28 - "图片编辑请求解析"
Cohesion: 0.08
Nodes (18): _clean(), _decode_base64_image(), _decode_data_url(), _download_image_url(), _extension_from_mime(), _filename_from_url(), _is_upload(), _json_image_sources() (+10 more)

### Community 29 - "图片任务 API 测试"
Cohesion: 0.06
Nodes (12): FakeImageTaskService, ImageTasksApiTests, client(), _compact(), _raise_quota_like_image_stream(), test_image_error_response_accepts_wrapped_quota_error(), test_images_generations_quota_429_contract(), test_images_generations_stream_quota_429_contract_before_first_byte() (+4 more)

### Community 30 - "SSE 事件解析"
Cohesion: 0.09
Nodes (30): apply_patch_op(), apply_text_patch(), assistant_message_text(), assistant_raw_text(), conversation_base_event(), event_assistant_text(), is_image_tool_event(), _is_user_message_event() (+22 more)

### Community 31 - "对话 payload 构建"
Cohesion: 0.09
Nodes (22): api_messages_to_conversation_messages(), conversation_payload(), image_model_settings(), FakeAPI, test_both_protocol_endpoints_share_single_implementation(), test_conversation_payload_falls_back_to_config_effort_and_drops_empty(), test_conversation_payload_skeleton_and_thinking_effort(), test_image_message_uploads_and_builds_multimodal_parts() (+14 more)

### Community 32 - "图片文件路由"
Cohesion: 0.09
Nodes (26): build_router(), delete_images_endpoint(), download_images_endpoint(), download_single_image_endpoint(), get_image(), get_image_thumbnail(), get_images(), DomainError (+18 more)

### Community 33 - "号池协议与密码登录"
Cohesion: 0.07
Nodes (6): AccountPoolProtocol, PasswordLoginService, _build_refresh_initial(), _build_relogin_initial(), _safe_response_text(), TokenRefreshService

### Community 34 - "后端客户端上下文与登录"
Cohesion: 0.08
Nodes (9): _legacy_admin_identity(), generate_pkce(), build_legacy_requirements_token(), build_pow_config(), build_proof_token(), _legacy_parse_time(), parse_pow_resources(), _pow_generate() (+1 more)

### Community 35 - "Sentinel PoW 与 Turnstile"
Cohesion: 0.07
Nodes (11): build_sentinel_token(), SentinelTokenGenerator, OrderedMap, solve_turnstile_token(), func_1(), func_17(), func_18(), func_19() (+3 more)

### Community 36 - "sub2api 集成服务"
Cohesion: 0.11
Nodes (15): Sub2apiError, _auth_headers(), _clean(), _extract_access_token(), _extract_paged_items(), _fetch_access_tokens_for_accounts(), list_remote_accounts(), list_remote_groups() (+7 more)

### Community 37 - "图片编辑器选项"
Cohesion: 0.10
Nodes (32): aspectIcons, countOptions, getDraggedImageFiles(), hasDraggedImages(), ImageComposerProps, isImageFile(), qualityOptions, ImageComposerOptions (+24 more)

### Community 39 - "消息工具与 token 计数"
Cohesion: 0.09
Nodes (12): conversation_events(), assistant_history_messages(), assistant_history_text(), build_image_prompt(), count_message_text_tokens(), count_message_tokens(), encoding_for_model(), message_text() (+4 more)

### Community 40 - "Codex 生图链路"
Cohesion: 0.11
Nodes (18): codex_body_preview(), codex_event_image_result_lengths(), codex_event_summary(), codex_image_input(), codex_responses_headers(), ensure_codex_source_account(), iter_codex_image_response_events(), iter_codex_response_events() (+10 more)

### Community 41 - "Responses 协议与图片 token"
Cohesion: 0.18
Nodes (28): normalize_text_messages(), count_message_image_tokens(), count_text_tokens(), _append_response_message(), collect_response(), extract_response_image(), has_unsupported_response_tools(), image_output_items() (+20 more)

### Community 42 - "后端客户端单测"
Cohesion: 0.13
Nodes (19): FakeResponse, FakeSession, make_core(), test_chat_target_switches_between_auth_and_anon(), test_conversation_headers_conditional_sentinel_tokens(), test_decode_image_base64_supports_data_url_raw_base64_and_local_file(), test_get_chat_requirements_prepare_then_finalize_with_pow_and_turnstile(), test_get_chat_requirements_raises_when_finalize_token_missing() (+11 more)

### Community 43 - "生图脚本客户端"
Cohesion: 0.12
Nodes (13): main(), main(), main(), main(), detect_ext(), load_auth_key(), post_json(), save_image() (+5 more)

### Community 44 - "网页搜索链路"
Cohesion: 0.14
Nodes (24): clean_search_url(), extract_search_result(), extract_search_sources(), find_search_value(), get_search_conversation(), prepare_search_conversation(), run_search_conversation(), search() (+16 more)

### Community 45 - "Chat Completion 缓存测试"
Cohesion: 0.08
Nodes (4): handle(), ChatCompletionCacheTests, fake_collect_text(), fake_stream_text_deltas()

### Community 46 - "存储后端抽象"
Cohesion: 0.12
Nodes (3): StorageBackend, StorageDataError, JSONStorageBackend

### Community 47 - "Auth Key 服务"
Cohesion: 0.20
Nodes (3): AuthService, _hash_key(), AuthServiceTests

### Community 48 - "领域异常与模型服务"
Cohesion: 0.10
Nodes (4): ChatCompletionsTests, extract_chat_prompt(), extract_prompt_from_message_content(), save_images_from_text()

### Community 49 - "前端 lint/格式化依赖"
Cohesion: 0.07
Nodes (26): class-variance-authority, clsx, eslint, eslint-config-next, eslint-config-prettier, prettier, prettier-plugin-organize-imports, prettier-plugin-tailwindcss (+18 more)

### Community 50 - "图片标签编辑前端"
Cohesion: 0.13
Nodes (21): date-fns, react-day-picker, ImageTagEditor(), ImageTagEditorProps, TagFilterBar(), TagFilterBarProps, TagFilterChip(), LongPressHandlers (+13 more)

### Community 51 - "CPA 连接池服务"
Cohesion: 0.12
Nodes (10): cpa_pool_files(), CPAConfig, CPAImportService, fetch_remote_access_token(), list_remote_files(), _management_headers(), _new_id(), _normalize_import_job() (+2 more)

### Community 52 - "通用进度追踪器"
Cohesion: 0.11
Nodes (14): ProgressTracker, _apply_refresh_update(), make_tracker(), test_apply_update_without_callback_only_counts(), test_auto_complete_marks_done_when_processed_reaches_total(), test_clean_removes_record(), test_concurrent_updates_keep_processed_consistent(), test_finish_with_error_records_error_field() (+6 more)

### Community 53 - "outlook 邮箱 token"
Cohesion: 0.13
Nodes (17): build_parser(), _clean(), _decode_header(), exchange_refresh_token(), _graph_sender(), _http_request(), HttpResponse, main() (+9 more)

### Community 54 - "Anthropic Messages 协议"
Cohesion: 0.16
Nodes (23): build_tool_prompt(), _compact_message_text(), compact_system(), _compact_system_text(), content_blocks(), handle(), _has_claude_code_system(), merge_system() (+15 more)

### Community 55 - "日志服务"
Cohesion: 0.14
Nodes (10): _collect_account_emails(), _collect_conversation_ids(), _collect_urls(), LogService, _next_item(), _request_excerpt(), _strip_internal_response_fields(), test_log_service_day_filter_accepts_utc_format() (+2 more)

### Community 56 - "内容风控过滤"
Cohesion: 0.11
Nodes (13): check_request(), _on_failure(), _extract_review_decision(), _is_allow_decision(), _is_reject_decision(), _resolve_fail_open(), _sanitize_for_review(), _text() (+5 more)

### Community 57 - "图片工作台页面状态"
Cohesion: 0.18
Nodes (22): ImageDeleteConfirmTarget, ImageLightboxItem, ImageResultsHandlers, ImagePage(), ImagePageContent(), fetchAccounts(), buildDeletedTurnPartConversation(), buildQueuedTurn() (+14 more)

### Community 58 - "生图任务服务与后端组装"
Cohesion: 0.11
Nodes (6): main(), OpenAIBackendAPI, handle(), _conversation(), FakeBackend, MultiImageResultTests

### Community 59 - "API 异常处理器"
Cohesion: 0.14
Nodes (14): _compatible_error_response(), install_exception_handlers(), domain_error_handler(), http_exception_handler(), validation_exception_handler(), _is_anthropic_messages_path(), _is_openai_compatible_path(), anthropic_error_response() (+6 more)

### Community 60 - "图片标签路由"
Cohesion: 0.14
Nodes (17): build_router(), cleanup_to_target(), compress_all_images(), delete_image_tag(), get_image_storage(), list_image_tags(), update_image_tags(), ImageTagsRequest (+9 more)

### Community 61 - "模型目录服务"
Cohesion: 0.14
Nodes (4): ModelCatalogService, FakeBackend, model_list(), ModelCatalogServiceTests

### Community 62 - "可编辑文件任务服务"
Cohesion: 0.20
Nodes (9): _clean(), _editable_access_token(), EditableFileTaskService, _elapsed_seconds(), _file_url(), _owner_id(), _public_task(), _task_key() (+1 more)

### Community 63 - "应用工厂与路由装配"
Cohesion: 0.10
Nodes (7): create_router(), create_app(), __call__(), lifespan(), serve_web(), resolve_web_asset(), start_limited_account_watcher()

### Community 64 - "配置项文档"
Cohesion: 0.11
Nodes (25): ai_review（AI 内容审查）, auth-key（API 访问密钥）, backup（Cloudflare R2 自动备份）, chat_completion_cache（会话缓存）, Cloudflare clearance 过墙, config.json 主配置文件, 生图轮询与二次确认参数, image_storage（WebDAV 图片存储） (+17 more)

### Community 65 - "图片任务服务实现"
Cohesion: 0.22
Nodes (7): _clean(), _collect_image_urls(), ImageTaskService, progress_callback(), _owner_id(), _public_task(), _task_key()

### Community 66 - "图片 token 计数"
Cohesion: 0.18
Nodes (16): ImageTokenTests, count_generated_image_tokens(), count_image_input_tokens(), count_image_inputs_tokens(), count_image_output_items_tokens(), count_image_output_tokens(), decode_data_url_bytes(), image_size_from_bytes() (+8 more)

### Community 67 - "UTC 时间口径"
Cohesion: 0.12
Nodes (10): _timestamp(), test_account_parse_time_accepts_new_utc_format(), test_parse_timestamp_accepts_both_legacy_forms(), test_parse_timestamp_forms(), test_parse_timestamp_round_trip(), test_task_timestamp_legacy_and_new_forms(), test_utc_iso_from_epoch_fixed_value(), test_utc_now_iso_format_and_clock() (+2 more)

### Community 68 - "图片会话前端存储"
Cohesion: 0.20
Nodes (23): pickFallbackConversationId(), sortImageConversations(), clearImageConversations(), dataUrlMimeType(), deleteImageConversation(), getLegacyReferenceImages(), getTimestamp(), ImageConversationsState (+15 more)

### Community 69 - "服务层测试假件"
Cohesion: 0.10
Nodes (5): FakeAccountService, FakeConfig, FakeProxySettings, FakeStorage, ProxyRuntimeApiTests

### Community 70 - "存储迁移脚本"
Cohesion: 0.18
Nodes (8): export_to_json(), import_from_json(), main(), migrate_data(), test_storage(), create_storage_backend(), _mask_password(), _mask_token()

### Community 72 - "Codex SSE 解析脚本"
Cohesion: 0.17
Nodes (13): find_images(), main(), parse_events(), ConversationState, extract_conversation_ids(), update_conversation_state(), test_extract_conversation_ids_from_payload(), test_update_conversation_state_accepts_patch_event_with_asset_pointer() (+5 more)

### Community 73 - "shadcn 组件配置"
Cohesion: 0.10
Nodes (19): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+11 more)

### Community 74 - "账号 CRUD 路由"
Cohesion: 0.13
Nodes (9): build_router(), create_accounts(), delete_accounts(), get_accounts(), download_timestamp(), spawn_background_task(), unique_tokens(), build_router() (+1 more)

### Community 75 - "Chat Completion 缓存"
Cohesion: 0.23
Nodes (7): cache_key(), CacheEntry, canonical_body(), ChatCompletionCache, InflightCall, _json_safe(), _message_signature()

### Community 76 - "图片任务 API 客户端"
Cohesion: 0.18
Nodes (16): createImageEditTask(), createImageGenerationTask(), fetchImageTasks(), ImageTask, ImageTaskListResponse, resumeImagePoll(), abortableSleep(), abortAllConversationQueues() (+8 more)

### Community 77 - "TypeScript 编译配置"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 78 - "配置加载测试"
Cohesion: 0.18
Nodes (7): ConfigLoadingTests, _make_store(), test_save_settings_unknown_key_returns_400(), test_update_accepts_every_whitelisted_key(), test_update_rejects_auth_key_and_backup_state(), test_update_rejects_unknown_top_level_keys(), test_update_whitelist_is_top_level_dimension()

### Community 81 - "CPA 池路由"
Cohesion: 0.20
Nodes (12): build_router(), cpa_pool_import(), cpa_pool_import_progress(), create_cpa_pool(), delete_cpa_pool(), list_cpa_pools(), update_cpa_pool(), CPAImportRequest (+4 more)

### Community 83 - "前端运行时依赖"
Cohesion: 0.12
Nodes (17): dependencies, axios, class-variance-authority, clsx, date-fns, localforage, lucide-react, next (+9 more)

### Community 84 - "图片结果渲染"
Cohesion: 0.19
Nodes (16): b64BlobUrlCache, base64SizeCache, downloadStoredImage(), formatBase64ImageSize(), formatDuration(), formatElapsed(), formatImageDimensions(), getProgressLabel() (+8 more)

### Community 85 - "功能状态清单"
Cohesion: 0.14
Nodes (16): 功能状态（Feature Status）, Anthropic 协议支持 POST /v1/messages, 文本补全缓存与重复请求合并（chat_completion_cache）, 面向图片工作流的 POST /v1/chat/completions, Codex 画图接口逆向链路, POST /v1/complete 文本补全与流式输出, Docker 自托管部署（多架构镜像）, 图片并行生成（image_parallel_generation） (+8 more)

### Community 86 - "配置归一化"
Cohesion: 0.25
Nodes (11): load_backup_state(), _normalize_backup_include(), _normalize_backup_settings(), _normalize_backup_state(), _normalize_bool(), _normalize_chat_completion_cache_settings(), _normalize_image_storage_settings(), _normalize_positive_int() (+3 more)

### Community 88 - "健康监控页与身份路由"
Cohesion: 0.15
Nodes (6): render_health_dashboard(), build_router(), get_version(), login(), build_router(), health_dashboard()

### Community 89 - "上游 Conversation SSE 协议"
Cohesion: 0.15
Nodes (15): 上游 Conversation SSE 协议说明, conversation_id 字段, Conversation SSE 流式返回协议, [DONE] 流结束标记, c（消息序号/游标字段）, message_marker 事件（user_visible_token / last_token）, moderation 事件（moderation_response.blocked）, o（patch 操作字段：add / append / replace / patch） (+7 more)

### Community 90 - "生图会话清理"
Cohesion: 0.20
Nodes (3): _remove_image_conversation_later(), FakeBackend, RemoveImageConversationGateTests

### Community 91 - "前端开发依赖"
Cohesion: 0.13
Nodes (15): devDependencies, eslint, eslint-config-next, eslint-config-prettier, prettier, prettier-plugin-organize-imports, prettier-plugin-tailwindcss, tailwindcss (+7 more)

### Community 92 - "Next 配置与版本检查"
Cohesion: 0.22
Nodes (8): nextConfig, projectRoot, isNewerVersion(), readLocalReleases(), toVersionParts(), useVersionCheck(), parseChangelog(), ReleaseInfo

### Community 93 - "输出注解清洗"
Cohesion: 0.19
Nodes (9): sanitize_output_text(), annotation_text(), is_internal_annotation_part(), readable_annotation_part(), replace_annotation(), replace_annotation_before_punctuation(), test_sanitize_output_text_keeps_url_annotation_label(), test_sanitize_output_text_removes_internal_cite_pointer() (+1 more)

### Community 94 - "代理运行时配置测试"
Cohesion: 0.24
Nodes (3): _normalize_proxy_runtime_settings(), _normalize_status_codes(), ProxyRuntimeConfigTests

### Community 95 - "代理初始化脚本"
Cohesion: 0.42
Nodes (7): _deep_fill_missing(), _env_bool(), _env_int(), _looks_like_repository_default(), main(), _mask_url(), _warp_runtime_defaults()

### Community 97 - "conversation 事件流解析"
Cohesion: 0.17
Nodes (7): iter_conversation_payloads(), message_event_payload(), test_iter_conversation_payloads_accumulates_deltas(), test_iter_conversation_payloads_done_and_raw_events(), test_iter_conversation_payloads_empty_payloads_skipped(), test_iter_conversation_payloads_non_dict_json_becomes_event(), test_iter_conversation_payloads_skips_history_replay()

### Community 99 - "参考图前端 hooks"
Cohesion: 0.35
Nodes (10): useReferenceImages(), UseReferenceImagesOptions, UseReferenceImagesResult, buildReferenceImageFromResult(), buildReferenceImageFromStoredImage(), dataUrlToFile(), fetchImageAsFile(), readFileAsDataUrl() (+2 more)

### Community 100 - "图片灯箱组件"
Cohesion: 0.24
Nodes (11): clamp(), defaultTransform, getTouchCenter(), getTouchDistance(), ImageLightbox(), ImageLightboxProps, ImageTransform, LightboxImage (+3 more)

### Community 102 - "设置加载与路径"
Cohesion: 0.25
Nodes (5): _is_invalid_auth_key(), _load_settings(), LoadedSettings, _normalize_auth_key(), _read_json_object()

### Community 104 - "PPT/PSD 脚本客户端"
Cohesion: 0.33
Nodes (4): main(), request_json(), main(), request_json()

### Community 105 - "文本账号路由单测"
Cohesion: 0.42
Nodes (3): ModelUnavailableError, ModelRoute, TextAccountRoutingTests

### Community 108 - "size_enabled 策略测试"
Cohesion: 0.33
Nodes (3): HandlerSizeEnabledTests, fake_pool(), result_image_output()

### Community 109 - "OAuth 刷新校验脚本"
Cohesion: 0.36
Nodes (4): diagnose(), _fmt_remaining(), force_refresh(), main()

### Community 110 - "生图错误响应映射"
Cohesion: 0.32
Nodes (4): _image_error_response(), _is_quota_exhausted_error(), _protocol_error_response(), test_image_error_response_accepts_raw_quota_error()

### Community 113 - "滚动位置恢复"
Cohesion: 0.36
Nodes (7): getResultsDistanceFromBottom(), loadScrollPositions(), saveScrollPositions(), useScrollRestore(), UseScrollRestoreResult, SCROLL_POSITIONS_STORAGE_KEY, ImageConversation

### Community 114 - "图片生成结果判定流程"
Cohesion: 0.33
Nodes (7): POST /v1/images/generations（OpenAI 兼容图片生成）, 完整会话明细查询（补找图片工具输出）, file-service:// 指针, async_task_type = image_gen, SSE 结束后的结果判断流程, server_ste_metadata 调度与工具状态事件, role=tool 图片工具消息

### Community 115 - "上游消息结构字段"
Cohesion: 0.29
Nodes (7): asset_pointer 图片指针, message.content.parts 内容片段, message.content.content_type（text / multimodal_text / model_editable_context）, file_upload 上传占位指针, input_message 用户输入事件, message 对象（author/content/status/end_turn/metadata）, sediment:// 指针

### Community 116 - "前端 npm 脚本"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, start, test, typecheck

### Community 118 - "第三方连接管理功能"
Cohesion: 0.67
Nodes (4): 账号池管理（号池）, 账号刷新异步进度追踪与重新登录, CPA 连接管理与按需导入, sub2api 连接管理与账号导入

### Community 119 - "前端图片工作流特性"
Cohesion: 0.67
Nodes (3): 前端图片工作台, 图片生成进度追踪（上传/预热/获取 token/生成中）, 前端图片懒加载与滚动位置恢复（LazyImage / bfcache）

## Knowledge Gaps
- **59 isolated node(s):** `chatgpt2api`, `@tailwindcss/postcss`, `@types/node`, `@types/react`, `@types/react-dom` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 983 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ConfigStore` connect `配置存储 ConfigStore` to `设置加载与路径`, `消息图片解析与存储`, `存储后端抽象`, `配置加载测试`, `配置归一化`, `健康监控页与身份路由`, `先 check 再 hit 机制`, `图片二次确认机制`, `代理运行时配置测试`, `应用工厂与路由装配`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `AccountService` (e.g. with `ModelRouteProvider` and `PasswordLoginService`) actually correct?**
  _`AccountService` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `chatgpt2api`, `@tailwindcss/postcss`, `@types/node` to the rest of the system?**
  _59 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `生图流式错误处理` be split into smaller, more focused modules?**
  _Cohesion score 0.04943820224719101 - nodes in this community are weakly interconnected._
- **Why does `require_admin()` connect `账号 OAuth/刷新路由` to `图片文件路由`, `FlareSolverr 过墙服务`, `账号 API 路由拆分`, `账号 CRUD 路由`, `CPA 池路由`, `AI 兼容 API 路由`, `CPA 连接池服务`, `图片标签路由`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Should `FlareSolverr 过墙服务` be split into smaller, more focused modules?**
  _Cohesion score 0.05515832482124617 - nodes in this community are weakly interconnected._
- **Why does `AccountService` connect `账号服务编排` to `号池协议与密码登录`, `Account Pydantic 模型`, `Codex 生图链路`, `文本账号路由单测`, `账号池与 token 获取`, `存储后端抽象`, `Auth Key 服务`, `领域异常与模型服务`, `通用进度追踪器`, `账号数据模型`, `模型目录服务`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._