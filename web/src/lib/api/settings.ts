import { httpRequest } from "@/lib/api/client";
import type { BackupSettings, BackupState } from "@/lib/api/backups";

export type ImageStorageMode = "local" | "webdav" | "both";

export type ImageStorageSettings = {
  enabled: boolean;
  mode: ImageStorageMode;
  webdav_url: string;
  webdav_username: string;
  webdav_password: string;
  webdav_root_path: string;
  public_base_url: string;
};

export type ThirdPartyAppsSettings = {
  infinite_canvas: {
    enabled: boolean;
    url: string;
  };
};

// 会话补全缓存配置（后端 services/config.py get_chat_completion_cache_settings）
export type ChatCompletionCacheSettings = {
  enabled: boolean;
  ttl_seconds: number;
  max_entries: number;
  dedupe_inflight: boolean;
  stream_cache: boolean;
  normalize_messages: boolean;
  drop_adjacent_duplicates: boolean;
  drop_assistant_history: boolean;
};

export type ProxyRuntimeEgressMode = "direct" | "single_proxy";
export type ProxyRuntimeClearanceMode = "none" | "manual" | "flaresolverr";

export type ProxyRuntimeClearanceSettings = {
  enabled: boolean;
  mode: ProxyRuntimeClearanceMode;
  cf_cookies: string;
  cf_clearance: string;
  user_agent: string;
  browser: string;
  flaresolverr_url: string;
  timeout_sec: number | string;
  refresh_interval: number | string;
  warm_up_on_start: boolean;
  has_cf_cookies?: boolean;
  has_cf_clearance?: boolean;
};

export type ProxyRuntimeSettings = {
  enabled: boolean;
  egress_mode: ProxyRuntimeEgressMode;
  proxy_url: string;
  resource_proxy_url: string;
  skip_ssl_verify: boolean;
  reset_session_status_codes: number[];
  clearance: ProxyRuntimeClearanceSettings;
};

export type ProxyRuntimeStatus = {
  enabled: boolean;
  egress_mode: ProxyRuntimeEgressMode | string;
  proxy_source: string;
  has_proxy: boolean;
  clearance_enabled: boolean;
  clearance_mode: ProxyRuntimeClearanceMode | string;
  has_clearance_bundle: boolean;
  cached_clearance_hosts: string[];
};

export type ProxyRuntimeResponse = {
  runtime: ProxyRuntimeSettings;
  status: ProxyRuntimeStatus;
};

// 字段与后端 ConfigStore.get()（services/config.py）逐一对应，均为显式声明；
// 后端新增字段时需同步补充，不允许再放回 [key: string]: unknown 索引签名
export type SettingsConfig = {
  base_url?: string;
  global_system_prompt?: string;
  default_upstream_model_name?: string;
  default_thinking_effort?: "auto" | "standard" | "extended" | "max";
  sensitive_words?: string[];
  ai_review?: {
    enabled?: boolean;
    base_url?: string;
    api_key?: string;
    model?: string;
    prompt?: string;
  };
  refresh_account_interval_minute?: number | string;
  image_retention_days?: number | string;
  image_poll_timeout_secs?: number | string;
  image_poll_interval_secs?: number | string;
  image_poll_initial_wait_secs?: number | string;
  image_account_concurrency?: number | string;
  image_parallel_generation?: boolean;
  allow_remote_image_fetch?: boolean;
  image_settle_enabled?: boolean;
  image_check_before_hit_enabled?: boolean;
  image_remove_conversation_after_result?: boolean;
  image_remove_conversation_always?: boolean;
  image_settle_secs?: number | string;
  image_timeout_retry_secs?: number | string;
  auto_remove_invalid_accounts?: boolean;
  auto_remove_rate_limited_accounts?: boolean;
  auto_relogin_after_refresh?: boolean;
  log_levels?: string[];
  image_storage?: ImageStorageSettings;
  proxy_runtime?: ProxyRuntimeSettings;
  third_party_apps?: ThirdPartyAppsSettings;
  backup?: BackupSettings;
  backup_state?: BackupState;
  chat_completion_cache?: ChatCompletionCacheSettings;
};

export async function fetchSettingsConfig() {
  return httpRequest<{ config: SettingsConfig }>("/api/settings");
}

// 上游模型目录：来自系统缓存的 ChatGPT /backend-api/models slug 列表，用于设置页下拉选项
export async function fetchUpstreamModels() {
  return httpRequest<{ models: string[] }>("/api/upstream-models");
}

export async function updateSettingsConfig(settings: SettingsConfig) {
  return httpRequest<{ config: SettingsConfig }>("/api/settings", {
    method: "POST",
    body: settings,
  });
}

export async function fetchThirdPartyApps() {
  return httpRequest<{ third_party_apps: ThirdPartyAppsSettings }>("/api/third-party-apps");
}

// ── 上游代理连通性测试（proxy_runtime 子域） ─────────────────────────

export type ProxyTestResult = {
  ok: boolean;
  status: number;
  latency_ms: number;
  error: string | null;
  proxy_source?: string;
  has_proxy?: boolean;
};

export type ClearanceTestResult = {
  ok: boolean;
  status: string;
  latency_ms: number;
  has_cookies: boolean;
  user_agent: string;
  error: string | null;
  runtime: ProxyRuntimeStatus;
};

export async function testProxy(url?: string) {
  return httpRequest<{ result: ProxyTestResult }>("/api/proxy/test", {
    method: "POST",
    body: { url: url ?? "" },
  });
}

export async function testProxyClearance(targetUrl?: string) {
  return httpRequest<{ result: ClearanceTestResult }>("/api/proxy/clearance/test", {
    method: "POST",
    body: { target_url: targetUrl ?? "https://chatgpt.com" },
  });
}
