/**
 * settings-normalize.ts 配置规范化单测。
 *
 * 覆盖点：
- normalizeConfig 空配置全量默认值（数值/布尔/嵌套对象）
- default_thinking_effort 合法值保留与非法值回退 auto
- image_storage 模式映射（local/webdav/both、disabled 强制 local）
- normalizeProxyRuntime 状态码过滤与 clearance 默认
- buildSaveConfig 收口：字符串 trim、数值下限钳制、数组清洗
- normalizeConfig → buildSaveConfig 往返一致性（再次 normalize 幂等）
 */
import { describe, expect, it } from "vitest";

import {
  DEFAULT_PROXY_RUNTIME,
  DEFAULT_THIRD_PARTY_APPS,
  buildSaveConfig,
  normalizeConfig,
  normalizeProxyRuntime,
  normalizeThirdPartyApps,
} from "@/lib/settings-normalize";
import type { SettingsConfig } from "@/lib/api/settings";

describe("normalizeConfig 空配置默认值", () => {
  it("数值与布尔字段落到默认值", () => {
    const config = normalizeConfig({} as SettingsConfig);
    expect(config.refresh_account_interval_minute).toBe(5);
    expect(config.image_retention_days).toBe(30);
    expect(config.image_poll_timeout_secs).toBe(120);
    expect(config.image_account_concurrency).toBe(3);
    expect(config.allow_remote_image_fetch).toBe(true);
    expect(config.image_settle_enabled).toBe(true);
    expect(config.image_check_before_hit_enabled).toBe(true);
    expect(config.image_remove_conversation_after_result).toBe(false);
    expect(config.auto_remove_invalid_accounts).toBe(false);
    expect(config.default_upstream_model_name).toBe("gpt-6-thinking");
    expect(config.default_thinking_effort).toBe("auto");
    expect(config.base_url).toBe("");
    expect(config.log_levels).toEqual([]);
    expect(config.sensitive_words).toEqual([]);
  });

  it("嵌套对象落到默认结构", () => {
    const config = normalizeConfig({} as SettingsConfig);
    expect(config.ai_review).toEqual({
      enabled: false, base_url: "", api_key: "", model: "", prompt: "",
    });
    expect(config.image_storage).toMatchObject({ enabled: false, mode: "local", webdav_root_path: "chatgpt2api/images" });
    expect(config.proxy_runtime).toEqual(DEFAULT_PROXY_RUNTIME);
    expect(config.third_party_apps).toEqual(DEFAULT_THIRD_PARTY_APPS);
    expect(config.backup).toMatchObject({
      enabled: false, provider: "cloudflare_r2", interval_minutes: 360, rotation_keep: 10,
    });
    expect(config.backup?.include).toMatchObject({ config: true, images: false });
  });
});

describe("normalizeConfig 字段映射", () => {
  it("default_thinking_effort 合法值保留、非法值回退 auto", () => {
    expect(normalizeConfig({ default_thinking_effort: "extended" } as SettingsConfig).default_thinking_effort).toBe("extended");
    expect(normalizeConfig({ default_thinking_effort: "bogus" } as unknown as SettingsConfig).default_thinking_effort).toBe("auto");
  });

  it("image_storage 模式映射：enabled 才允许 webdav/both", () => {
    expect(normalizeConfig({
      image_storage: { enabled: true, mode: "webdav" },
    } as SettingsConfig).image_storage?.mode).toBe("webdav");
    expect(normalizeConfig({
      image_storage: { enabled: true, mode: "both" },
    } as SettingsConfig).image_storage?.mode).toBe("both");
    expect(normalizeConfig({
      image_storage: { enabled: false, mode: "webdav" },
    } as SettingsConfig).image_storage?.mode).toBe("local");
    expect(normalizeConfig({
      image_storage: { enabled: true, mode: "unknown" },
    } as unknown as SettingsConfig).image_storage?.mode).toBe("local");
  });

  it("字符串数值被强转", () => {
    const config = normalizeConfig({
      refresh_account_interval_minute: "10",
      image_settle_secs: "3",
      global_system_prompt: 123,
    } as unknown as SettingsConfig);
    expect(config.refresh_account_interval_minute).toBe(10);
    expect(config.image_settle_secs).toBe(3);
    expect(config.global_system_prompt).toBe("123");
  });
});

describe("normalizeProxyRuntime", () => {
  it("非对象输入回退默认", () => {
    expect(normalizeProxyRuntime(null)).toEqual(DEFAULT_PROXY_RUNTIME);
    expect(normalizeProxyRuntime("x")).toEqual(DEFAULT_PROXY_RUNTIME);
  });

  it("egress_mode 与 clearance.mode 白名单外回退", () => {
    const normalized = normalizeProxyRuntime({
      egress_mode: "bogus",
      clearance: { mode: "bogus" },
    });
    expect(normalized.egress_mode).toBe("direct");
    expect(normalized.clearance.mode).toBe("none");
    expect(normalizeProxyRuntime({ egress_mode: "single_proxy" }).egress_mode).toBe("single_proxy");
    expect(normalizeProxyRuntime({ clearance: { mode: "flaresolverr" } }).clearance.mode).toBe("flaresolverr");
  });

  it("reset_session_status_codes 过滤非法值并回退 [403]", () => {
    expect(normalizeProxyRuntime({ reset_session_status_codes: [403, 503, 99, 700, 403.5, "x"] }).reset_session_status_codes)
      .toEqual([403, 503]);
    expect(normalizeProxyRuntime({}).reset_session_status_codes).toEqual([403]);
    expect(normalizeProxyRuntime({ reset_session_status_codes: [429] }).reset_session_status_codes).toEqual([429]);
  });
});

describe("normalizeThirdPartyApps", () => {
  it("canvas url 空值回退默认", () => {
    expect(normalizeThirdPartyApps({})).toEqual(DEFAULT_THIRD_PARTY_APPS);
    expect(normalizeThirdPartyApps({ infinite_canvas: { enabled: true, url: "" } })).toEqual({
      infinite_canvas: { enabled: true, url: DEFAULT_THIRD_PARTY_APPS.infinite_canvas.url },
    });
  });
});

describe("buildSaveConfig 收口", () => {
  it("字符串字段 trim", () => {
    const saved = buildSaveConfig({
      base_url: "  http://x  ",
      global_system_prompt: " prompt ",
      default_upstream_model_name: "  ",
      sensitive_words: [" a ", "", "b\t"],
      ai_review: { base_url: " url " },
    } as SettingsConfig);
    expect(saved.base_url).toBe("http://x");
    expect(saved.global_system_prompt).toBe("prompt");
    expect(saved.default_upstream_model_name).toBe("gpt-6-thinking");
    expect(saved.sensitive_words).toEqual(["a", "b"]);
    expect(saved.ai_review?.base_url).toBe("url");
  });

  it("数值下限钳制", () => {
    const saved = buildSaveConfig({
      refresh_account_interval_minute: 0,       // falsy → 默认 3? 否：默认 3 是 concurrency；interval 默认 1
      image_account_concurrency: -1,            // 负数 → 钳到 1
      image_settle_secs: 0,                     // falsy → 默认 2.0
      image_timeout_retry_secs: -5,
      backup: { rotation_keep: -1 },
    } as SettingsConfig);
    expect(saved.refresh_account_interval_minute).toBe(1);
    expect(saved.image_account_concurrency).toBe(1);
    expect(saved.image_settle_secs).toBe(2.0);
    expect(saved.image_timeout_retry_secs).toBe(1);
    expect(saved.backup?.rotation_keep).toBe(0);
  });

  it("allow_remote_image_fetch 默认 true，显式 false 保留", () => {
    // 后端默认开启（SSRF 防护开关），缺省/undefined 归一化为 true
    expect(normalizeConfig({} as SettingsConfig).allow_remote_image_fetch).toBe(true);
    expect(normalizeConfig({ allow_remote_image_fetch: false } as SettingsConfig).allow_remote_image_fetch).toBe(false);
    expect(buildSaveConfig({ allow_remote_image_fetch: false } as SettingsConfig).allow_remote_image_fetch).toBe(false);
    expect(buildSaveConfig({} as SettingsConfig).allow_remote_image_fetch).toBe(true);
  });

  it("image_storage 关闭时强制 local，开启时保留 webdav/both", () => {
    expect(buildSaveConfig({
      image_storage: { enabled: false, mode: "webdav" },
    } as SettingsConfig).image_storage?.mode).toBe("local");
    expect(buildSaveConfig({
      image_storage: { enabled: true, mode: "both" },
    } as SettingsConfig).image_storage?.mode).toBe("both");
  });

  it("proxy_runtime clearance 数值下限", () => {
    const saved = buildSaveConfig({
      proxy_runtime: {
        ...DEFAULT_PROXY_RUNTIME,
        clearance: { ...DEFAULT_PROXY_RUNTIME.clearance, timeout_sec: 0, refresh_interval: 10 },
      },
    } as SettingsConfig);
    expect(saved.proxy_runtime?.clearance?.timeout_sec).toBe(60);
    // 刷新间隔最小 60 秒
    expect(saved.proxy_runtime?.clearance?.refresh_interval).toBe(60);
  });
});

describe("normalizeConfig → buildSaveConfig 往返一致性", () => {
  it("规范化后再保存再规范化保持稳定", () => {
    const raw = {
      refresh_account_interval_minute: 15,
      image_poll_timeout_secs: 200,
      default_thinking_effort: "extended",
      base_url: "http://x",
      sensitive_words: ["a", "b"],
      image_storage: { enabled: true, mode: "webdav", webdav_url: "https://dav" },
      proxy_runtime: {
        ...DEFAULT_PROXY_RUNTIME,
        enabled: true,
        egress_mode: "single_proxy",
        reset_session_status_codes: [403, 429],
      },
      third_party_apps: { infinite_canvas: { enabled: true, url: "https://c" } },
      backup: {
        enabled: true,
        provider: "cloudflare_r2",
        account_id: "acct",
        access_key_id: "key",
        secret_access_key: "secret",
        bucket: "bucket",
        prefix: "prefix",
        interval_minutes: 60,
        rotation_keep: 5,
        encrypt: true,
        passphrase: "pw",
        include: {
          config: true, cpa: true, sub2api: true, logs: true,
          image_tasks: true, accounts_snapshot: true, auth_keys_snapshot: true, images: false,
        },
      },
    } as unknown as SettingsConfig;

    const normalized = normalizeConfig(raw);
    const saved = buildSaveConfig(normalized);
    const renormalized = normalizeConfig(saved);
    const resaved = buildSaveConfig(renormalized);

    expect(renormalized).toEqual(normalized);
    expect(resaved).toEqual(saved);
    // 关键字段在往返后保持
    expect(saved.refresh_account_interval_minute).toBe(15);
    expect(saved.image_poll_timeout_secs).toBe(200);
    expect(saved.default_thinking_effort).toBe("extended");
    expect(renormalized.base_url).toBe("http://x");
    expect(saved.image_storage?.mode).toBe("webdav");
    expect(saved.proxy_runtime?.egress_mode).toBe("single_proxy");
    expect(saved.proxy_runtime?.reset_session_status_codes).toEqual([403, 429]);
  });
});
