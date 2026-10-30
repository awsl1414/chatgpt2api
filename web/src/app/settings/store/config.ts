"use client";

import { create } from "zustand";

import {
  fetchSettingsConfig,
  fetchUpstreamModels,
  syncImageStorage,
  testImageStorageConnection,
  updateSettingsConfig,
  type BackupSettings,
  type ImageStorageSettings,
  type ProxyRuntimeSettings,
  type SettingsConfig,
  type ThirdPartyAppsSettings,
} from "@/lib/api";
import { actionError, type ActionResult } from "@/lib/action-result";
import { buildSaveConfig, normalizeConfig, normalizeProxyRuntime, normalizeThirdPartyApps } from "@/lib/settings-normalize";

/**
 * config 域 store：系统配置（SettingsConfig）与其加载/保存/字段编辑。
 *
 * 只承载真正跨页面共享的服务端配置状态；备份列表、CPA/Sub2API 连接等
 * 服务端数据快照由各自组件内部请求（审计 F-高3），不进入全局 store。
 * 所有动作只返回 ActionResult，toast 由调用组件负责（审计 F-低2）。
 */

export const useConfigStore = create<ConfigStore>((set, get) => ({
  config: null,
  isLoadingConfig: true,
  isSavingConfig: false,
  upstreamModels: [],
  isLoadingUpstreamModels: false,
  isTestingImageStorage: false,
  isSyncingImageStorage: false,

  loadConfig: async () => {
    set({ isLoadingConfig: true });
    try {
      const data = await fetchSettingsConfig();
      set({ config: normalizeConfig(data.config) });
      return { ok: true };
    } catch (error) {
      return { ok: false, error: actionError(error, "加载系统配置失败") };
    } finally {
      set({ isLoadingConfig: false });
    }
  },

  loadUpstreamModels: async () => {
    set({ isLoadingUpstreamModels: true });
    try {
      const data = await fetchUpstreamModels();
      set({ upstreamModels: (data.models || []).filter(Boolean) });
    } catch {
      // 拉取失败时保持空列表，下拉框会回退展示当前配置值
    } finally {
      set({ isLoadingUpstreamModels: false });
    }
  },

  saveConfig: async () => {
    const { config } = get();
    if (!config) {
      return { ok: false, error: "配置尚未加载" };
    }

    set({ isSavingConfig: true });
    try {
      const data = await updateSettingsConfig(buildSaveConfig(config));
      set({ config: normalizeConfig(data.config) });
      // 画布入口卡片的启用状态影响顶部导航，通知其重新拉取
      window.dispatchEvent(new Event("third-party-apps-updated"));
      return { ok: true };
    } catch (error) {
      return { ok: false, error: actionError(error, "保存系统配置失败") };
    } finally {
      set({ isSavingConfig: false });
    }
  },

  setRefreshAccountIntervalMinute: (value) => {
    set((state) => state.config ? { config: { ...state.config, refresh_account_interval_minute: value } } : {});
  },

  setImageRetentionDays: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_retention_days: value } } : {});
  },

  setImagePollTimeoutSecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_poll_timeout_secs: value } } : {});
  },

  setImageAccountConcurrency: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_account_concurrency: value } } : {});
  },

  setImageSettleEnabled: (value) => {
    set((state) => state.config
      ? { config: { ...state.config, image_settle_enabled: value, image_check_before_hit_enabled: value } }
      : {});
  },

  setImageCheckBeforeHitEnabled: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_check_before_hit_enabled: value } } : {});
  },

  setImageRemoveConversationAfterResult: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_remove_conversation_after_result: value } } : {});
  },

  setImageRemoveConversationAlways: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_remove_conversation_always: value } } : {});
  },

  setImageSettleSecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_settle_secs: value } } : {});
  },

  setImageTimeoutRetrySecs: (value) => {
    set((state) => state.config ? { config: { ...state.config, image_timeout_retry_secs: value } } : {});
  },

  setAutoRemoveInvalidAccounts: (value) => {
    set((state) => state.config ? { config: { ...state.config, auto_remove_invalid_accounts: value } } : {});
  },

  setAutoRemoveRateLimitedAccounts: (value) => {
    set((state) => state.config ? { config: { ...state.config, auto_remove_rate_limited_accounts: value } } : {});
  },

  setAutoReloginAfterRefresh: (value) => {
    set((state) => state.config ? { config: { ...state.config, auto_relogin_after_refresh: value } } : {});
  },

  setLogLevel: (level, enabled) => {
    set((state) => {
      if (!state.config) return {};
      const levels = new Set(state.config.log_levels || []);
      if (enabled) levels.add(level);
      else levels.delete(level);
      return { config: { ...state.config, log_levels: Array.from(levels) } };
    });
  },

  setBaseUrl: (value) => {
    set((state) => state.config ? { config: { ...state.config, base_url: value } } : {});
  },

  setGlobalSystemPrompt: (value) => {
    set((state) => state.config ? { config: { ...state.config, global_system_prompt: value } } : {});
  },

  setDefaultUpstreamModelName: (value) => {
    set((state) => state.config ? { config: { ...state.config, default_upstream_model_name: value } } : {});
  },

  setDefaultThinkingEffort: (value) => {
    set((state) => state.config ? { config: { ...state.config, default_thinking_effort: value } } : {});
  },

  setSensitiveWordsText: (value) => {
    set((state) => state.config ? { config: { ...state.config, sensitive_words: value.split("\n") } } : {});
  },

  setAIReviewField: (key, value) => {
    set((state) => state.config
      ? { config: { ...state.config, ai_review: { ...(state.config.ai_review || {}), [key]: value } } }
      : {});
  },

  setImageStorageField: (key, value) => {
    set((state) => {
      if (!state.config?.image_storage) {
        return {};
      }
      const next = {
        ...state.config.image_storage,
        [key]: value,
      };
      if (key === "enabled" && !value) {
        next.mode = "local";
      }
      if (key === "enabled" && value && next.mode === "local") {
        next.mode = "webdav";
      }
      return {
        config: {
          ...state.config,
          image_storage: next,
        },
      };
    });
  },

  setProxyRuntimeField: (key, value) => {
    set((state) => {
      if (!state.config) {
        return {};
      }
      const runtime = normalizeProxyRuntime(state.config.proxy_runtime);
      const nextRuntime = normalizeProxyRuntime({
        ...runtime,
        [key]: value,
      });
      return {
        config: {
          ...state.config,
          proxy_runtime: nextRuntime,
        },
      };
    });
  },

  setProxyRuntimeClearanceField: (key, value) => {
    set((state) => {
      if (!state.config) {
        return {};
      }
      const runtime = normalizeProxyRuntime(state.config.proxy_runtime);
      const nextRuntime = normalizeProxyRuntime({
        ...runtime,
        clearance: {
          ...runtime.clearance,
          [key]: value,
        },
      });
      return {
        config: {
          ...state.config,
          proxy_runtime: nextRuntime,
        },
      };
    });
  },

  setProxyRuntimeStatusCodesText: (value) => {
    const codes = value
      .split(/[,\s]+/)
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isInteger(item) && item >= 100 && item <= 599);
    set((state) => {
      if (!state.config) {
        return {};
      }
      const runtime = normalizeProxyRuntime(state.config.proxy_runtime);
      return {
        config: {
          ...state.config,
          proxy_runtime: normalizeProxyRuntime({
            ...runtime,
            reset_session_status_codes: codes.length > 0 ? codes : [403],
          }),
        },
      };
    });
  },

  setInfiniteCanvasField: (key, value) => {
    set((state) => {
      if (!state.config) {
        return {};
      }
      const apps = normalizeThirdPartyApps(state.config.third_party_apps);
      return {
        config: {
          ...state.config,
          third_party_apps: {
            ...apps,
            infinite_canvas: {
              ...apps.infinite_canvas,
              [key]: value,
            },
          },
        },
      };
    });
  },

  setBackupField: (key, value) => {
    set((state) => {
      if (!state.config?.backup) {
        return {};
      }
      return {
        config: {
          ...state.config,
          backup: {
            ...state.config.backup,
            [key]: value,
          },
        },
      };
    });
  },

  setBackupInclude: (key, value) => {
    set((state) => {
      if (!state.config?.backup) {
        return {};
      }
      return {
        config: {
          ...state.config,
          backup: {
            ...state.config.backup,
            include: {
              ...state.config.backup.include,
              [key]: value,
            },
          },
        },
      };
    });
  },

  testImageStorage: async () => {
    set({ isTestingImageStorage: true });
    try {
      const saved = await get().saveConfig();
      if (!saved.ok) {
        return { ok: false, error: saved.error ?? "保存配置失败" };
      }
      const data = await testImageStorageConnection();
      if (data.result.ok) {
        return { ok: true, message: `WebDAV 连接可用：HTTP ${data.result.status}` };
      }
      return { ok: false, error: `WebDAV 连接失败：${data.result.error ?? `HTTP ${data.result.status}`}` };
    } catch (error) {
      return { ok: false, error: actionError(error, "测试 WebDAV 失败") };
    } finally {
      set({ isTestingImageStorage: false });
    }
  },

  syncImagesToWebDAV: async () => {
    set({ isSyncingImageStorage: true });
    try {
      const saved = await get().saveConfig();
      if (!saved.ok) {
        return { ok: false, error: saved.error ?? "保存配置失败" };
      }
      const data = await syncImageStorage();
      return { ok: true, message: `同步完成：上传 ${data.result.uploaded}，跳过 ${data.result.skipped}，失败 ${data.result.failed}` };
    } catch (error) {
      return { ok: false, error: actionError(error, "同步图片失败") };
    } finally {
      set({ isSyncingImageStorage: false });
    }
  },
}));

type ConfigStore = {
  config: SettingsConfig | null;
  isLoadingConfig: boolean;
  isSavingConfig: boolean;
  upstreamModels: string[];
  isLoadingUpstreamModels: boolean;
  isTestingImageStorage: boolean;
  isSyncingImageStorage: boolean;

  loadConfig: () => Promise<ActionResult>;
  loadUpstreamModels: () => Promise<void>;
  saveConfig: () => Promise<ActionResult>;

  setRefreshAccountIntervalMinute: (value: string) => void;
  setImageRetentionDays: (value: string) => void;
  setImagePollTimeoutSecs: (value: string) => void;
  setImageAccountConcurrency: (value: string) => void;
  setImageSettleEnabled: (value: boolean) => void;
  setImageCheckBeforeHitEnabled: (value: boolean) => void;
  setImageRemoveConversationAfterResult: (value: boolean) => void;
  setImageRemoveConversationAlways: (value: boolean) => void;
  setImageSettleSecs: (value: string) => void;
  setImageTimeoutRetrySecs: (value: string) => void;
  setAutoRemoveInvalidAccounts: (value: boolean) => void;
  setAutoRemoveRateLimitedAccounts: (value: boolean) => void;
  setAutoReloginAfterRefresh: (value: boolean) => void;
  setLogLevel: (level: string, enabled: boolean) => void;
  setBaseUrl: (value: string) => void;
  setGlobalSystemPrompt: (value: string) => void;
  setDefaultUpstreamModelName: (value: string) => void;
  setDefaultThinkingEffort: (value: "auto" | "standard" | "extended" | "max") => void;
  setSensitiveWordsText: (value: string) => void;
  setAIReviewField: (key: "enabled" | "base_url" | "api_key" | "model" | "prompt", value: string | boolean) => void;
  setImageStorageField: (key: keyof ImageStorageSettings, value: string | boolean) => void;
  setProxyRuntimeField: <K extends keyof ProxyRuntimeSettings>(key: K, value: ProxyRuntimeSettings[K]) => void;
  setProxyRuntimeClearanceField: <K extends keyof ProxyRuntimeSettings["clearance"]>(key: K, value: ProxyRuntimeSettings["clearance"][K]) => void;
  setProxyRuntimeStatusCodesText: (value: string) => void;
  setInfiniteCanvasField: <K extends keyof ThirdPartyAppsSettings["infinite_canvas"]>(key: K, value: ThirdPartyAppsSettings["infinite_canvas"][K]) => void;
  setBackupField: (key: keyof BackupSettings, value: string | boolean) => void;
  setBackupInclude: (key: keyof BackupSettings["include"], value: boolean) => void;

  testImageStorage: () => Promise<ActionResult>;
  syncImagesToWebDAV: () => Promise<ActionResult>;
};
