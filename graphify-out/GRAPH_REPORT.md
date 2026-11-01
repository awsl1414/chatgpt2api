# Graph Report - chatgpt2api-orchestrator  (2026-11-01)

## Corpus Check
- 194 files · ~125,711 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: (none) 8, .lock 2, .example 1)

## Summary
- 2550 nodes · 7231 edges · 111 communities (80 shown, 31 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 271 edges (avg confidence: 0.86)
- Token cost: 115,199 input · 20,330 output

## Community Hubs (Navigation)
- Proxy Clearance & FlareSolverr
- Accounts Admin UI
- Storage Migration & Tests
- Image Results UI
- Config Store Settings
- Image Errors & Conversation
- Settings Cards UI
- Backup Service
- Image Storage Service
- Image Input Decoding
- Annotation Sanitization
- Protocol Test Scripts
- Admin Backup & Theme UI
- Navigation & Filters UI
- Image Generation Orchestration
- Admin CRUD Routers
- sub2api Service
- Python Import Surface
- Account Service
- Image Task Service
- OpenAI API Routers
- Logs Page UI
- Docs & Release History
- Responses API Backend
- Import & Sub2API UI
- Storage Backends
- Frontend Lint & Format Deps
- Account Import Dialog
- Debug & Skill Panels
- Upstream Chat Client
- Account API Schemas
- Outlook Mail Token Flow
- Auth Service
- Chat & Search Panels
- Error Handlers
- System Admin Endpoints
- Anthropic Messages Adapter
- Account Token Lifecycle
- Editable File Panel
- Web Runtime Dependencies
- FastAPI App Bootstrap
- Model Catalog Service
- Image File Endpoints
- Login & Auth Guard
- OpenAI Backend Client
- Chat Completions Tests
- Editable File Tasks
- Test Fakes & Config
- Turnstile PoW Solver
- Image Token Accounting
- CPA Pool Config
- Chat Completion Cache
- shadcn Component Config
- Image Result Extraction
- TypeScript Compiler Config
- CPA & Sentinel Integration
- Log Service
- OAuth Login Service
- Request Models
- Account Refresh Progress
- Account Export Tests
- Multi-Image Result Tests
- Web Search Tool
- Image & SSE Concepts
- PoW Token Building
- Version Check & Next Config
- Content Filter Review
- Responses API Tests
- Frontend Dev Dependencies
- Editable File Artifacts
- Masked Logger
- Image Tags Service
- Docker Deployment Stack
- Conversation Cleanup Tests
- System Request Schemas
- Proxy Config Init
- JSON Storage Backend
- Image Task API Tests
- Text 3D Flip Component
- Editable File Export
- Image Edits JSON Tests
- Text Account Routing
- Config Persistence
- Text Reveal Animation
- Model List Tests
- Proxy Config Tests
- Text Protocol Routing Tests
- Images Edits API Tests
- Root Layout & Theme
- WebDAV Fake Client
- Anthropic Messages Tests
- Morphing Text Component
- Upstream HTTP Errors
- Sponsor & Brand Logos
- ESLint Config
- Package Scripts
- Upgrade Backup & Rollback
- Account Pool Connections
- Type Overrides
- Framework Logos
- PostCSS Config
- Completion Cache Concept
- Project Root Package

## God Nodes (most connected - your core abstractions)
1. `OpenAIBackendAPI` - 139 edges
2. `AccountService` - 107 edges
3. `cn()` - 94 edges
4. `httpRequest()` - 68 edges
5. `require_admin()` - 63 edges
6. `Button()` - 58 edges
7. `create_router()` - 52 edges
8. `react` - 50 edges
9. `ConfigStore` - 47 edges
10. `ImagePageContent()` - 45 edges

## Surprising Connections (you probably didn't know these)
- `POST /v1/search Endpoint` --semantically_similar_to--> `POST /v1/chat/completions`  [INFERRED] [semantically similar]
  .codex/skills/chatgpt2api-search/SKILL.md → README.md
- `GitHub Octocat Icon (monochrome UI icon)` --semantically_similar_to--> `Atlas Cloud Wordmark Logo (SVG)`  [INFERRED] [semantically similar]
  web/public/github.svg → assets/atlascloud.svg
- `create_router()` --uses--> `OAuthLoginError`  [INFERRED]
  api/accounts.py → services/oauth_login_service.py
- `cpa_pool_files()` --indirect_call--> `list_remote_files()`  [INFERRED]
  api/accounts.py → services/cpa_service.py
- `filter_or_log()` --indirect_call--> `check_request()`  [INFERRED]
  api/ai.py → services/content_filter.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **OpenAI-Compatible API Surface** — readme_models_endpoint, readme_images_generations_endpoint, readme_images_edits_endpoint, readme_chat_completions_endpoint, readme_responses_endpoint [EXTRACTED 1.00]
- **Self-Hosted Deployment Stack** — docker_compose_local_app_service, docker_compose_local_sqlite_storage, docker_compose_local_data_volume, _github_workflows_docker_publish_publish_docker_image, _github_workflows_docker_publish_ghcr_registry, readme_storage_backend [INFERRED 0.85]
- **Release Timeline** — changelog_v1_2_0, changelog_v1_3_0, changelog_v1_4_1, changelog_v1_5_0, changelog_v1_8_0 [EXTRACTED 1.00]
- **WARP Egress Pipeline (init-config → privoxy → warp-proxy, with flaresolverr clearance)** — docker_compose_warp_init_config, docker_compose_warp_privoxy, docker_compose_warp_warp_proxy, docker_compose_warp_flaresolverr, docker_compose_warp_app [EXTRACTED 1.00]
- **SSE Image Result Resolution Flow** — docs_upstream_sse_conversation_image_tool_output, docs_upstream_sse_conversation_asset_pointer, docs_upstream_sse_conversation_server_ste_metadata, docs_upstream_sse_conversation_policy_refusal, docs_upstream_sse_conversation_result_resolution [EXTRACTED 1.00]
- **Project Brand and Sponsor Logo Asset Set** — assets_atlascloud_atlascloudlogo, assets_ipwo_ipwologo, assets_kunrouai_kunrouailogo, web_public_github_githubicon [INFERRED 0.75]

## Communities (111 total, 31 thin omitted)

### Community 0 - "Proxy Clearance & FlareSolverr"
Cohesion: 0.05
Nodes (29): test_proxy_clearance_endpoint(), test_proxy_endpoint(), _clean(), ClearanceBundle, _coerce_timeout(), _colon_proxy_to_url(), _cookies_to_header(), _domain_matches() (+21 more)

### Community 1 - "Accounts Admin UI"
Cohesion: 0.05
Nodes (78): AccountsPage(), AccountsPageContent(), accountStatusOptions, displayAccountSource(), displayAccountType(), downloadTokens(), formatCompact(), formatQuota() (+70 more)

### Community 2 - "Storage Migration & Tests"
Cohesion: 0.05
Nodes (24): export_to_json(), import_from_json(), main(), migrate_data(), test_storage(), diagnose(), _fmt_remaining(), force_refresh() (+16 more)

### Community 3 - "Image Results UI"
Cohesion: 0.06
Nodes (76): b64BlobUrlCache, base64SizeCache, downloadStoredImage(), formatBase64ImageSize(), formatDuration(), formatElapsed(), formatImageDimensions(), getProgressLabel() (+68 more)

### Community 4 - "Config Store Settings"
Cohesion: 0.06
Nodes (12): ConfigStore, _normalize_backup_include(), _normalize_backup_settings(), _normalize_bool(), _normalize_chat_completion_cache_settings(), _normalize_image_storage_settings(), _normalize_positive_int(), _normalize_proxy_runtime_settings() (+4 more)

### Community 5 - "Image Errors & Conversation"
Cohesion: 0.08
Nodes (46): ImageContentPolicyError, ImagePollTimeoutError, ImageTaskError, add_unique(), apply_patch_op(), apply_text_patch(), assistant_history_messages(), assistant_history_text() (+38 more)

### Community 6 - "Settings Cards UI"
Cohesion: 0.12
Nodes (44): lucide-react, sonner, BaseUrlCard(), ConfigCard(), CPAPoolsCard(), ProxyRuntimeCard(), ProxySettingsCard(), ProxySettingsCard() (+36 more)

### Community 7 - "Backup Service"
Cohesion: 0.10
Nodes (14): BackupError, BackupService, _clean(), CloudflareR2Client, _count_items(), _guess_content_type(), _hmac_sha256(), _is_backup_object() (+6 more)

### Community 8 - "Image Storage Service"
Cohesion: 0.11
Nodes (14): _clean(), _image_dimensions(), ImageStorageError, ImageStorageService, _is_image_rel(), _local_image_path(), _now_iso(), _read_json_object() (+6 more)

### Community 9 - "Image Input Decoding"
Cohesion: 0.08
Nodes (19): _clean(), _decode_base64_image(), _decode_data_url(), _download_image_url(), _extension_from_mime(), _filename_from_url(), _is_upload(), _json_image_sources() (+11 more)

### Community 10 - "Annotation Sanitization"
Cohesion: 0.07
Nodes (12): sanitize_output_text(), annotation_text(), is_internal_annotation_part(), readable_annotation_part(), replace_annotation(), replace_annotation_before_punctuation(), handle(), handle() (+4 more)

### Community 11 - "Protocol Test Scripts"
Cohesion: 0.10
Nodes (20): find_images(), main(), parse_events(), main(), main(), main(), request_json(), main() (+12 more)

### Community 12 - "Admin Backup & Theme UI"
Cohesion: 0.11
Nodes (31): class-variance-authority, react-dom, BackupSettingsCard(), formatBytes(), formatDateTime(), getFilenameFromContentDisposition(), includeLabels, CPAPoolDialog() (+23 more)

### Community 13 - "Navigation & Filters UI"
Cohesion: 0.12
Nodes (31): react, DateRangeFilter(), DateRangeFilterProps, adminNavItems, buildThirdPartyHref(), TopNav(), userNavItems, Calendar() (+23 more)

### Community 14 - "Image Generation Orchestration"
Cohesion: 0.15
Nodes (30): collect_image_outputs(), ConversationRequest, count_text_tokens(), encode_images(), stream_image_chunks(), stream_image_outputs_with_pool(), chat_completion_annotations(), chat_image_args() (+22 more)

### Community 15 - "Admin CRUD Routers"
Cohesion: 0.11
Nodes (35): create_router(), cpa_pool_files(), cpa_pool_import(), cpa_pool_import_progress(), create_accounts(), create_cpa_pool(), create_sub2api_server(), create_user_key() (+27 more)

### Community 16 - "sub2api Service"
Cohesion: 0.11
Nodes (15): _auth_headers(), _clean(), _extract_access_token(), _extract_paged_items(), _fetch_access_tokens_for_accounts(), list_remote_accounts(), list_remote_groups(), _login() (+7 more)

### Community 19 - "Image Task Service"
Cohesion: 0.14
Nodes (11): _clean(), _collect_image_urls(), ImageTaskService, progress_callback(), _now_iso(), _owner_id(), _public_task(), _task_key() (+3 more)

### Community 20 - "OpenAI API Routers"
Cohesion: 0.14
Nodes (26): create_router(), create_chat_completion(), create_message(), create_ppt_task(), create_psd_task(), create_response(), edit_images(), generate_images() (+18 more)

### Community 21 - "Logs Page UI"
Cohesion: 0.11
Nodes (31): @radix-ui/react-dialog, formatDuration(), getDetailText(), getStatus(), getUrls(), LogsContent(), LogsPage(), LogType (+23 more)

### Community 22 - "Docs & Release History"
Cohesion: 0.07
Nodes (34): chatgpt2api-search Skill, POST /v1/search Endpoint, GHCR Image Publishing, Multi-Architecture Build (QEMU + Buildx), Publish Docker Image Workflow, Default Upstream Model & Thinking Effort Config, Parallel Image Generation, Incremental Database Sync (+26 more)

### Community 23 - "Responses API Backend"
Cohesion: 0.19
Nodes (29): count_message_image_tokens(), text_backend(), _append_response_message(), collect_response(), extract_response_image(), has_unsupported_response_tools(), image_output_items(), _input_image_parts() (+21 more)

### Community 24 - "Import & Sub2API UI"
Cohesion: 0.14
Nodes (27): ImportBrowserDialog(), AuthMode, normalizeAccounts(), PAGE_SIZE_OPTIONS, Sub2APIConnections(), PAGE_SIZE_OPTIONS, Checkbox(), DialogFooter() (+19 more)

### Community 26 - "Frontend Lint & Format Deps"
Cohesion: 0.06
Nodes (30): clsx, date-fns, eslint, @eslint/eslintrc, immer, localforage, prettier-plugin-organize-imports, prettier-plugin-tailwindcss (+22 more)

### Community 27 - "Account Import Dialog"
Cohesion: 0.11
Nodes (27): AccountImportDialog(), AccountImportDialogProps, getAccountJsonAccount(), getAccountJsonAccounts(), getCodexAuthAccount(), getSessionAccessToken(), ImportMethod, MethodCard() (+19 more)

### Community 28 - "Debug & Skill Panels"
Cohesion: 0.14
Nodes (23): PsdPanel(), SkillPanel(), DebugPage(), tabs, ApiDoc, ApiDocsCard(), docs, ParamRow (+15 more)

### Community 29 - "Upstream Chat Client"
Cohesion: 0.14
Nodes (4): ChatRequirements, ensure_ok(), iter_sse_payloads(), new_uuid()

### Community 30 - "Account API Schemas"
Cohesion: 0.12
Nodes (21): _account_payload_token(), _account_zip_bytes(), AccountCreateRequest, AccountDeleteRequest, AccountExportRequest, AccountRefreshRequest, AccountUpdateRequest, CPAImportRequest (+13 more)

### Community 31 - "Outlook Mail Token Flow"
Cohesion: 0.13
Nodes (17): build_parser(), _clean(), _decode_header(), exchange_refresh_token(), _graph_sender(), _http_request(), HttpResponse, main() (+9 more)

### Community 32 - "Auth Service"
Cohesion: 0.22
Nodes (4): AuthService, _hash_key(), _now_iso(), AuthServiceTests

### Community 33 - "Chat & Search Panels"
Cohesion: 0.11
Nodes (24): axios, react-markdown, remark-gfm, ChatPanel(), messageImages(), messageText(), readImage(), SelectedImage (+16 more)

### Community 34 - "Error Handlers"
Cohesion: 0.13
Nodes (15): _compatible_error_response(), install_exception_handlers(), http_exception_handler(), validation_exception_handler(), _is_anthropic_messages_path(), _is_openai_compatible_path(), _image_error_response(), _protocol_error_response() (+7 more)

### Community 35 - "System Admin Endpoints"
Cohesion: 0.09
Nodes (24): create_router(), delete_backup_endpoint(), delete_logs(), download_backup_endpoint(), download_images_endpoint(), get_backup_detail(), get_backups(), get_image_storage() (+16 more)

### Community 36 - "Anthropic Messages Adapter"
Cohesion: 0.15
Nodes (24): build_tool_prompt(), _compact_message_text(), compact_system(), _compact_system_text(), content_blocks(), handle(), _has_claude_code_system(), merge_system() (+16 more)

### Community 38 - "Editable File Panel"
Cohesion: 0.16
Nodes (23): createClientTaskId(), EditableFilePanel(), fileNameOf(), formatElapsed(), isRunning(), mergeTasks(), Props, readFile() (+15 more)

### Community 39 - "Web Runtime Dependencies"
Cohesion: 0.08
Nodes (26): dependencies, axios, class-variance-authority, clsx, date-fns, immer, localforage, lucide-react (+18 more)

### Community 40 - "FastAPI App Bootstrap"
Cohesion: 0.12
Nodes (8): create_app(), lifespan(), serve_web(), raise_image_quota_error(), resolve_web_asset(), start_limited_account_watcher(), _auto_cleanup_worker(), start_image_cleanup_scheduler()

### Community 41 - "Model Catalog Service"
Cohesion: 0.15
Nodes (4): ModelCatalogService, FakeBackend, model_list(), ModelCatalogServiceTests

### Community 42 - "Image File Endpoints"
Cohesion: 0.12
Nodes (20): cleanup_to_target(), delete_images_endpoint(), download_single_image_endpoint(), get_image(), get_image_thumbnail(), get_images(), _cleanup_empty_dirs(), cleanup_image_thumbnails() (+12 more)

### Community 43 - "Login & Auth Guard"
Cohesion: 0.22
Nodes (19): next, LoginPage(), HomePage(), login(), getValidatedAuthSession(), UseAuthGuardResult, useRedirectIfAuthenticated(), AUTH_KEY_STORAGE_KEY (+11 more)

### Community 45 - "Chat Completions Tests"
Cohesion: 0.14
Nodes (14): ChatCompletionsTests, anthropic_sse_stream(), _decode_json_image_string(), _decode_message_image_object(), _decode_message_image_url(), extract_image_from_message_content(), _extract_json_image_value(), _image_extension() (+6 more)

### Community 46 - "Editable File Tasks"
Cohesion: 0.21
Nodes (9): _clean(), _editable_access_token(), EditableFileTaskService, _elapsed_seconds(), _file_url(), _now_iso(), _owner_id(), _public_task() (+1 more)

### Community 48 - "Test Fakes & Config"
Cohesion: 0.09
Nodes (5): FakeAccountService, FakeConfig, FakeProxySettings, FakeStorage, ProxyRuntimeApiTests

### Community 49 - "Turnstile PoW Solver"
Cohesion: 0.11
Nodes (9): OrderedMap, solve_turnstile_token(), func_1(), func_17(), func_18(), func_19(), func_5(), _turnstile_to_str() (+1 more)

### Community 50 - "Image Token Accounting"
Cohesion: 0.19
Nodes (16): ImageTokenTests, count_generated_image_tokens(), count_image_input_tokens(), count_image_output_tokens(), _decode_data_url(), image_size_from_bytes(), image_size_from_data_url(), _model_name() (+8 more)

### Community 51 - "CPA Pool Config"
Cohesion: 0.15
Nodes (6): CPAConfig, CPAImportService, _new_id(), _normalize_import_job(), _normalize_pool(), _now_iso()

### Community 52 - "Chat Completion Cache"
Cohesion: 0.23
Nodes (8): cache_key(), CacheEntry, canonical_body(), ChatCompletionCache, InflightCall, _json_safe(), _message_signature(), normalize_text_messages()

### Community 53 - "shadcn Component Config"
Cohesion: 0.10
Nodes (19): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+11 more)

### Community 54 - "Image Result Extraction"
Cohesion: 0.12
Nodes (4): _is_content_policy_error(), walk(), _remaining(), _retry_sleep()

### Community 55 - "TypeScript Compiler Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 56 - "CPA & Sentinel Integration"
Cohesion: 0.18
Nodes (5): fetch_remote_access_token(), list_remote_files(), _management_headers(), build_sentinel_token(), SentinelTokenGenerator

### Community 57 - "Log Service"
Cohesion: 0.22
Nodes (6): _collect_account_emails(), _collect_conversation_ids(), _collect_urls(), LogService, _request_excerpt(), _strip_internal_response_fields()

### Community 59 - "Request Models"
Cohesion: 0.18
Nodes (10): AnthropicMessageRequest, ChatCompletionRequest, EditableFileTaskRequest, ImageGenerationRequest, ResponseCreateRequest, SearchRequest, list_image_tasks(), ImageGenerationTaskRequest (+2 more)

### Community 60 - "Account Refresh Progress"
Cohesion: 0.21
Nodes (3): ImageStreamHardTimeoutError, InvalidAccessTokenError, AccountCapabilityTests

### Community 61 - "Account Export Tests"
Cohesion: 0.21
Nodes (3): AccountExportTests, make_jwt(), MemoryStorage

### Community 63 - "Multi-Image Result Tests"
Cohesion: 0.18
Nodes (4): ImageOutput, _conversation(), FakeBackend, MultiImageResultTests

### Community 64 - "Web Search Tool"
Cohesion: 0.27
Nodes (14): stream_web_search_chat_completion(), web_search_chat_response(), clean_search_text(), replace_annotation(), has_unsupported_tools(), has_web_search_tool(), is_web_search_chat_request(), message_text() (+6 more)

### Community 65 - "Image & SSE Concepts"
Cohesion: 0.20
Nodes (15): Codex Image Reverse-Engineered Path (codex-gpt-image-2), Parallel Image Generation (image_parallel_generation), Image Generation Progress Tracking, OpenAI-Compatible Image API (/v1/images/*), Pending Features (image sizes, rt_token refresh, Anthropic protocol), Asset Pointer Types (file-service://, sediment://, file_upload), Image Tool Output Message (role=tool, async_task_type=image_gen), input_message Event (+7 more)

### Community 66 - "PoW Token Building"
Cohesion: 0.22
Nodes (7): build_legacy_requirements_token(), build_pow_config(), build_proof_token(), _legacy_parse_time(), parse_pow_resources(), _pow_generate(), ScriptSrcParser

### Community 67 - "Version Check & Next Config"
Cohesion: 0.20
Nodes (8): nextConfig, projectRoot, isNewerVersion(), readLocalReleases(), toVersionParts(), useVersionCheck(), parseChangelog(), ReleaseInfo

### Community 68 - "Content Filter Review"
Cohesion: 0.18
Nodes (9): check_request(), _extract_review_decision(), _is_allow_decision(), _is_reject_decision(), request_shape(), walk(), _resolve_fail_open(), _sanitize_for_review() (+1 more)

### Community 70 - "Frontend Dev Dependencies"
Cohesion: 0.13
Nodes (15): devDependencies, eslint, eslint-config-next, eslint-config-prettier, @eslint/eslintrc, prettier-plugin-organize-imports, prettier-plugin-tailwindcss, tailwindcss (+7 more)

### Community 73 - "Image Tags Service"
Cohesion: 0.28
Nodes (11): delete_image_tag(), list_image_tags(), update_image_tags(), delete_tag(), _ensure_file(), get_all_tags(), get_tags(), load_tags() (+3 more)

### Community 74 - "Docker Deployment Stack"
Cohesion: 0.26
Nodes (13): app Service (default compose), STORAGE_BACKEND Environment (json/sqlite/postgres/git), app Service (WARP variant), flaresolverr Service, init-config Service, privoxy Service (SOCKS5 to HTTP bridge), CHATGPT2API_PROXY_RUNTIME_* Environment Contract, warp-proxy Service (Cloudflare WARP SOCKS5) (+5 more)

### Community 76 - "Conversation Cleanup Tests"
Cohesion: 0.22
Nodes (3): _remove_image_conversation_later(), FakeBackend, RemoveImageConversationGateTests

### Community 77 - "System Request Schemas"
Cohesion: 0.27
Nodes (10): BackupDeleteRequest, ClearanceTestRequest, compress_all_images(), ImageDeleteRequest, ImageDownloadRequest, ImageTagsRequest, LogDeleteRequest, ProxyTestRequest (+2 more)

### Community 78 - "Proxy Config Init"
Cohesion: 0.42
Nodes (7): _deep_fill_missing(), _env_bool(), _env_int(), _looks_like_repository_default(), main(), _mask_url(), _warp_runtime_defaults()

### Community 81 - "Text 3D Flip Component"
Cohesion: 0.21
Nodes (11): CharBox, CharBoxProps, CONTAINER_TRANSFORMS, DEFAULT_TRANSITION, extractTextFromChildren(), FRONT_FACE_TRANSFORMS, ROTATION_MAP, SECOND_FACE_TRANSFORMS (+3 more)

### Community 86 - "Text Account Routing"
Cohesion: 0.36
Nodes (3): ModelRoute, ModelUnavailableError, TextAccountRoutingTests

### Community 87 - "Config Persistence"
Cohesion: 0.38
Nodes (8): _is_invalid_auth_key(), load_backup_state(), _load_settings(), LoadedSettings, _normalize_auth_key(), _normalize_backup_state(), _read_json_object(), save_backup_state()

### Community 88 - "Text Reveal Animation"
Cohesion: 0.36
Nodes (7): motion, buildGradient(), DEFAULT_COLORS, DiaTextReveal(), DiaTextRevealProps, measureWidths(), sweepEase()

### Community 93 - "Root Layout & Theme"
Cohesion: 0.38
Nodes (4): metadata, RootLayout(), viewport, ThemeScript()

### Community 96 - "Morphing Text Component"
Cohesion: 0.53
Nodes (5): MorphingText(), MorphingTextProps, SvgFilters(), Texts(), useMorphingText()

### Community 98 - "Sponsor & Brand Logos"
Cohesion: 0.67
Nodes (4): Atlas Cloud Wordmark Logo (SVG), IPWO Logo (blue W monogram with dot, raster PNG), Kunrou AI (坤肉AI) Horizontal Logo with Gradient Orbit Mark, GitHub Octocat Icon (monochrome UI icon)

### Community 99 - "ESLint Config"
Cohesion: 0.50
Nodes (3): eslint-config-next, eslint-config-prettier, eslintConfig

### Community 100 - "Package Scripts"
Cohesion: 0.50
Nodes (4): scripts, build, dev, start

### Community 101 - "Upgrade Backup & Rollback"
Cohesion: 0.67
Nodes (3): Backup Before Upgrade, Core Persistent Files (config.json / .env / data/), Rollback Procedure

### Community 102 - "Account Pool Connections"
Cohesion: 0.67
Nodes (3): Account Pool Management, CPA Connection Management and Import, sub2api Connection and OpenAI OAuth Import

### Community 103 - "Type Overrides"
Cohesion: 0.67
Nodes (3): overrides, @types/react, @types/react-dom

### Community 104 - "Framework Logos"
Cohesion: 0.67
Nodes (3): Next.js Wordmark Logo (next.svg), OpenAI Logo Icon (openai.svg), Vercel Triangle Logo (vercel.svg)

## Knowledge Gaps
- **44 isolated node(s):** `chatgpt2api`, `immer`, `react-hook-form`, `react-medium-image-zoom`, `@eslint/eslintrc` (+39 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 542 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OpenAIBackendAPI` connect `OpenAI Backend Client` to `Image Errors & Conversation`, `Protocol Test Scripts`, `Python Import Surface`, `Account Service`, `Image Task Service`, `Responses API Backend`, `Upstream Chat Client`, `Anthropic Messages Adapter`, `Account Token Lifecycle`, `Model Catalog Service`, `Editable File Tasks`, `Codex & Search Backend`, `Image Result Extraction`, `Upstream Conversation Client`, `Multi-Image Result Tests`, `Web Search Tool`, `Editable File Artifacts`, `Conversation Cleanup Tests`, `Editable File Export`, `Chat Message Conversion`, `Upstream HTTP Errors`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `OpenAIBackendAPI` (e.g. with `AccountService` and `EditableFileTaskService`) actually correct?**
  _`OpenAIBackendAPI` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `chatgpt2api`, `immer`, `react-hook-form` to the rest of the system?**
  _44 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Proxy Clearance & FlareSolverr` be split into smaller, more focused modules?**
  _Cohesion score 0.05337078651685393 - nodes in this community are weakly interconnected._
- **Why does `AccountService` connect `Account Service` to `Storage Migration & Tests`, `Account Token Lifecycle`, `Model Catalog Service`, `Token Pool Selection`, `OpenAI Backend Client`, `Python Import Surface`, `Refresh Token Keepalive`, `Text Account Routing`, `Storage Backends`, `Account Refresh Progress`, `Account Export Tests`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `AccountService` (e.g. with `ModelUnavailableError` and `InvalidAccessTokenError`) actually correct?**
  _`AccountService` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `Accounts Admin UI` be split into smaller, more focused modules?**
  _Cohesion score 0.050837496326770495 - nodes in this community are weakly interconnected._