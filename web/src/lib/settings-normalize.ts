import type { BackupSettings } from "@/lib/api/backups";
import type {
  ImageStorageMode,
  ImageStorageSettings,
  ProxyRuntimeClearanceMode,
  ProxyRuntimeEgressMode,
  ProxyRuntimeSettings,
  SettingsConfig,
  ThirdPartyAppsSettings,
} from "@/lib/api/settings";

/**
 * 系统配置的规范化单一份实现。
 *
 * 加载侧（normalizeConfig）与保存侧（buildSaveConfig）共用同一份默认值与字段清单，
 * 替代旧 settings/store.ts 中两份手工同步的字段映射（审计 F-中1）。
 * 后端字段见 services/config.py 的 ConfigStore.get()。
 */

export const DEFAULT_PROXY_RUNTIME: ProxyRuntimeSettings = {
  enabled: false,
  egress_mode: "direct",
  proxy_url: "",
  resource_proxy_url: "",
  skip_ssl_verify: false,
  reset_session_status_codes: [403],
  clearance: {
    enabled: false,
    mode: "none",
    cf_cookies: "",
    cf_clearance: "",
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    browser: "chrome",
    flaresolverr_url: "",
    timeout_sec: 60,
    refresh_interval: 3600,
    warm_up_on_start: false,
    has_cf_cookies: false,
    has_cf_clearance: false,
  },
};

export const DEFAULT_THIRD_PARTY_APPS: ThirdPartyAppsSettings = {
  infinite_canvas: {
    enabled: false,
    url: "https://canvas.best",
  },
};

const DEFAULT_IMAGE_STORAGE: ImageStorageSettings = {
  enabled: false,
  mode: "local",
  webdav_url: "",
  webdav_username: "",
  webdav_password: "",
  webdav_root_path: "chatgpt2api/images",
  public_base_url: "",
};

const DEFAULT_BACKUP: BackupSettings = {
  enabled: false,
  provider: "cloudflare_r2",
  account_id: "",
  access_key_id: "",
  secret_access_key: "",
  bucket: "",
  prefix: "backups",
  interval_minutes: 360,
  rotation_keep: 10,
  encrypt: false,
  passphrase: "",
  include: {
    config: true,
    cpa: true,
    sub2api: true,
    logs: true,
    image_tasks: true,
    accounts_snapshot: true,
    auth_keys_snapshot: true,
    images: false,
  },
};

const THINKING_EFFORTS = ["standard", "extended", "max"] as const;

export function normalizeProxyRuntime(value: unknown): ProxyRuntimeSettings {
  const source = typeof value === "object" && value !== null ? value as Partial<ProxyRuntimeSettings> : {};
  const clearanceSource = typeof source.clearance === "object" && source.clearance !== null
    ? source.clearance as Partial<ProxyRuntimeSettings["clearance"]>
    : {};
  const egressMode = source.egress_mode === "single_proxy" ? "single_proxy" : "direct";
  const clearanceMode: ProxyRuntimeClearanceMode = clearanceSource.mode === "manual" || clearanceSource.mode === "flaresolverr"
    ? clearanceSource.mode
    : "none";
  const statusCodes = Array.isArray(source.reset_session_status_codes)
    ? source.reset_session_status_codes
      .map((item) => Number(item))
      .filter((item) => Number.isInteger(item) && item >= 100 && item <= 599)
    : [];
  return {
    ...DEFAULT_PROXY_RUNTIME,
    ...source,
    enabled: Boolean(source.enabled),
    egress_mode: egressMode as ProxyRuntimeEgressMode,
    proxy_url: String(source.proxy_url || ""),
    resource_proxy_url: String(source.resource_proxy_url || ""),
    skip_ssl_verify: Boolean(source.skip_ssl_verify),
    reset_session_status_codes: statusCodes.length > 0 ? statusCodes : [403],
    clearance: {
      ...DEFAULT_PROXY_RUNTIME.clearance,
      ...clearanceSource,
      enabled: Boolean(clearanceSource.enabled),
      mode: clearanceMode,
      cf_cookies: String(clearanceSource.cf_cookies || ""),
      cf_clearance: String(clearanceSource.cf_clearance || ""),
      user_agent: String(clearanceSource.user_agent || DEFAULT_PROXY_RUNTIME.clearance.user_agent),
      browser: String(clearanceSource.browser || "chrome"),
      flaresolverr_url: String(clearanceSource.flaresolverr_url || ""),
      timeout_sec: Number(clearanceSource.timeout_sec || 60),
      refresh_interval: Number(clearanceSource.refresh_interval || 3600),
      warm_up_on_start: Boolean(clearanceSource.warm_up_on_start),
      has_cf_cookies: Boolean(clearanceSource.has_cf_cookies),
      has_cf_clearance: Boolean(clearanceSource.has_cf_clearance),
    },
  };
}

export function normalizeThirdPartyApps(value: unknown): ThirdPartyAppsSettings {
  const source = typeof value === "object" && value !== null ? value as Partial<ThirdPartyAppsSettings> : {};
  const canvas: Partial<ThirdPartyAppsSettings["infinite_canvas"]> = typeof source.infinite_canvas === "object" && source.infinite_canvas
    ? source.infinite_canvas
    : {};
  return {
    infinite_canvas: {
      enabled: Boolean(canvas.enabled),
      url: String(canvas.url || DEFAULT_THIRD_PARTY_APPS.infinite_canvas.url),
    },
  };
}

/** 加载侧：把后端返回的原始 config 规范化为前端可安全渲染的形态 */
export function normalizeConfig(config: SettingsConfig): SettingsConfig {
  const defaultThinkingEffort = THINKING_EFFORTS.includes(config.default_thinking_effort as (typeof THINKING_EFFORTS)[number])
    ? config.default_thinking_effort as (typeof THINKING_EFFORTS)[number]
    : "auto";
  const imageStorage = typeof config.image_storage === "object" && config.image_storage
    ? config.image_storage as ImageStorageSettings
    : DEFAULT_IMAGE_STORAGE;
  const imageStorageMode: ImageStorageMode = imageStorage.enabled && imageStorage.mode === "both"
    ? "both"
    : imageStorage.enabled && imageStorage.mode === "webdav"
      ? "webdav"
      : "local";
  const backup = typeof config.backup === "object" && config.backup
    ? config.backup as BackupSettings
    : DEFAULT_BACKUP;
  return {
    ...config,
    refresh_account_interval_minute: Number(config.refresh_account_interval_minute || 5),
    image_retention_days: Number(config.image_retention_days || 30),
    image_poll_timeout_secs: Number(config.image_poll_timeout_secs || 120),
    image_account_concurrency: Number(config.image_account_concurrency || 3),
    allow_remote_image_fetch: config.allow_remote_image_fetch !== false,
    image_settle_enabled: Boolean(config.image_settle_enabled !== false),
    image_check_before_hit_enabled: Boolean(config.image_check_before_hit_enabled !== false),
    image_remove_conversation_after_result: Boolean(config.image_remove_conversation_after_result),
    image_remove_conversation_always: Boolean(config.image_remove_conversation_always),
    image_settle_secs: Number(config.image_settle_secs || 2.0),
    image_timeout_retry_secs: Number(config.image_timeout_retry_secs || 30),
    auto_remove_invalid_accounts: Boolean(config.auto_remove_invalid_accounts),
    auto_remove_rate_limited_accounts: Boolean(config.auto_remove_rate_limited_accounts),
    auto_relogin_after_refresh: Boolean(config.auto_relogin_after_refresh),
    log_levels: Array.isArray(config.log_levels) ? config.log_levels : [],
    base_url: typeof config.base_url === "string" ? config.base_url : "",
    global_system_prompt: String(config.global_system_prompt || ""),
    default_upstream_model_name: String(config.default_upstream_model_name || "gpt-6-thinking"),
    default_thinking_effort: defaultThinkingEffort,
    sensitive_words: Array.isArray(config.sensitive_words) ? config.sensitive_words : [],
    ai_review: {
      enabled: Boolean(config.ai_review?.enabled),
      base_url: String(config.ai_review?.base_url || ""),
      api_key: String(config.ai_review?.api_key || ""),
      model: String(config.ai_review?.model || ""),
      prompt: String(config.ai_review?.prompt || ""),
    },
    image_storage: {
      enabled: Boolean(imageStorage.enabled),
      mode: imageStorageMode,
      webdav_url: String(imageStorage.webdav_url || ""),
      webdav_username: String(imageStorage.webdav_username || ""),
      webdav_password: String(imageStorage.webdav_password || ""),
      webdav_root_path: String(imageStorage.webdav_root_path || "chatgpt2api/images"),
      public_base_url: String(imageStorage.public_base_url || ""),
    },
    proxy_runtime: normalizeProxyRuntime(config.proxy_runtime),
    third_party_apps: normalizeThirdPartyApps(config.third_party_apps),
    backup: {
      ...backup,
      enabled: Boolean(backup.enabled),
      account_id: String(backup.account_id || ""),
      access_key_id: String(backup.access_key_id || ""),
      secret_access_key: String(backup.secret_access_key || ""),
      bucket: String(backup.bucket || ""),
      prefix: String(backup.prefix || "backups"),
      interval_minutes: Number(backup.interval_minutes || 360),
      rotation_keep: Number(backup.rotation_keep ?? 10),
      encrypt: Boolean(backup.encrypt),
      passphrase: String(backup.passphrase || ""),
      include: {
        config: Boolean(backup.include?.config ?? true),
        cpa: Boolean(backup.include?.cpa ?? true),
        sub2api: Boolean(backup.include?.sub2api ?? true),
        logs: Boolean(backup.include?.logs ?? true),
        image_tasks: Boolean(backup.include?.image_tasks ?? true),
        accounts_snapshot: Boolean(backup.include?.accounts_snapshot ?? true),
        auth_keys_snapshot: Boolean(backup.include?.auth_keys_snapshot ?? true),
        images: Boolean(backup.include?.images ?? false),
      },
    },
  };
}

/** 保存侧：把编辑中的 config 收敛为提交给 POST /api/settings 的 payload（trim 与边界值在此收口） */
export function buildSaveConfig(config: SettingsConfig): SettingsConfig {
  return {
    ...config,
    refresh_account_interval_minute: Math.max(1, Number(config.refresh_account_interval_minute) || 1),
    image_retention_days: Math.max(1, Number(config.image_retention_days) || 30),
    image_poll_timeout_secs: Math.max(1, Number(config.image_poll_timeout_secs) || 120),
    image_account_concurrency: Math.max(1, Number(config.image_account_concurrency) || 3),
    allow_remote_image_fetch: config.allow_remote_image_fetch !== false,
    image_settle_enabled: Boolean(config.image_settle_enabled !== false),
    image_check_before_hit_enabled: Boolean(config.image_check_before_hit_enabled !== false),
    image_remove_conversation_after_result: Boolean(config.image_remove_conversation_after_result),
    image_remove_conversation_always: Boolean(config.image_remove_conversation_always),
    image_settle_secs: Math.max(0.5, Number(config.image_settle_secs) || 2.0),
    image_timeout_retry_secs: Math.max(1, Number(config.image_timeout_retry_secs) || 30),
    auto_remove_invalid_accounts: Boolean(config.auto_remove_invalid_accounts),
    auto_remove_rate_limited_accounts: Boolean(config.auto_remove_rate_limited_accounts),
    auto_relogin_after_refresh: Boolean(config.auto_relogin_after_refresh),
    base_url: String(config.base_url || "").trim(),
    global_system_prompt: String(config.global_system_prompt || "").trim(),
    default_upstream_model_name: String(config.default_upstream_model_name || "gpt-6-thinking").trim() || "gpt-6-thinking",
    default_thinking_effort: THINKING_EFFORTS.includes(config.default_thinking_effort as (typeof THINKING_EFFORTS)[number])
      ? config.default_thinking_effort
      : "auto",
    sensitive_words: (config.sensitive_words || []).map((item) => String(item).trim()).filter(Boolean),
    ai_review: {
      enabled: Boolean(config.ai_review?.enabled),
      base_url: String(config.ai_review?.base_url || "").trim(),
      api_key: String(config.ai_review?.api_key || "").trim(),
      model: String(config.ai_review?.model || "").trim(),
      prompt: String(config.ai_review?.prompt || "").trim(),
    },
    image_storage: {
      enabled: Boolean(config.image_storage?.enabled),
      mode: config.image_storage?.enabled && ["webdav", "both"].includes(String(config.image_storage?.mode)) ? config.image_storage.mode : "local",
      webdav_url: String(config.image_storage?.webdav_url || "").trim(),
      webdav_username: String(config.image_storage?.webdav_username || "").trim(),
      webdav_password: String(config.image_storage?.webdav_password || "").trim(),
      webdav_root_path: String(config.image_storage?.webdav_root_path || "chatgpt2api/images").trim(),
      public_base_url: String(config.image_storage?.public_base_url || "").trim(),
    },
    proxy_runtime: {
      ...normalizeProxyRuntime(config.proxy_runtime),
      proxy_url: String(config.proxy_runtime?.proxy_url || "").trim(),
      resource_proxy_url: String(config.proxy_runtime?.resource_proxy_url || "").trim(),
      reset_session_status_codes: normalizeProxyRuntime({
        reset_session_status_codes: (config.proxy_runtime?.reset_session_status_codes || [403])
          .map((item) => Number(item))
          .filter((item) => Number.isInteger(item) && item >= 100 && item <= 599),
      }).reset_session_status_codes,
      clearance: {
        ...normalizeProxyRuntime(config.proxy_runtime).clearance,
        cf_cookies: String(config.proxy_runtime?.clearance?.cf_cookies || "").trim(),
        cf_clearance: String(config.proxy_runtime?.clearance?.cf_clearance || "").trim(),
        user_agent: String(config.proxy_runtime?.clearance?.user_agent || DEFAULT_PROXY_RUNTIME.clearance.user_agent).trim(),
        browser: String(config.proxy_runtime?.clearance?.browser || "chrome").trim(),
        flaresolverr_url: String(config.proxy_runtime?.clearance?.flaresolverr_url || "").trim(),
        timeout_sec: Math.max(1, Number(config.proxy_runtime?.clearance?.timeout_sec) || 60),
        refresh_interval: Math.max(60, Number(config.proxy_runtime?.clearance?.refresh_interval) || 3600),
      },
    },
    third_party_apps: {
      infinite_canvas: {
        enabled: Boolean(config.third_party_apps?.infinite_canvas?.enabled),
        url: String(config.third_party_apps?.infinite_canvas?.url || DEFAULT_THIRD_PARTY_APPS.infinite_canvas.url).trim(),
      },
    },
    backup: {
      ...(config.backup as BackupSettings),
      account_id: String(config.backup?.account_id || "").trim(),
      access_key_id: String(config.backup?.access_key_id || "").trim(),
      secret_access_key: String(config.backup?.secret_access_key || "").trim(),
      bucket: String(config.backup?.bucket || "").trim(),
      prefix: String(config.backup?.prefix || "backups").trim(),
      interval_minutes: Math.max(1, Number(config.backup?.interval_minutes) || 360),
      rotation_keep: Math.max(0, Number(config.backup?.rotation_keep) || 0),
      passphrase: String(config.backup?.passphrase || "").trim(),
    },
  };
}
