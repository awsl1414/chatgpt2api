import axios, { AxiosError, AxiosHeaders, type AxiosRequestConfig } from "axios";

import webConfig from "@/constants/common-env";
import { clearStoredAuthSession, getStoredAuthKey } from "@/store/auth";

type RequestConfig = AxiosRequestConfig & {
  redirectOnUnauthorized?: boolean;
};

type ErrorPayload = {
  detail?: string | { error?: string | { message?: string } };
  error?: string | { message?: string };
  message?: string;
};

function errorMessageFromValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (!value || typeof value !== "object") {
    return "";
  }

  const item = value as { error?: unknown; message?: unknown };
  if (typeof item.message === "string") {
    return item.message;
  }
  return errorMessageFromValue(item.error);
}

export const request = axios.create({
  baseURL: webConfig.apiUrl.replace(/\/$/, ""),
});

request.interceptors.request.use(async (config) => {
  // 统一经 AxiosHeaders 构造，避免绕过 axios 类型对 headers 做断言赋值（审查 R2-M7）
  const headers = AxiosHeaders.from(config.headers ?? {});
  const authKey = await getStoredAuthKey();
  if (authKey && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authKey}`);
  }
  config.headers = headers;
  return config;
});

request.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ErrorPayload>) => {
    const status = error.response?.status;
    const shouldRedirect =
      (error.config as RequestConfig | undefined)?.redirectOnUnauthorized !== false;
    if (status === 401 && shouldRedirect && typeof window !== "undefined") {
      // Avoid redirect loop — only redirect if not already on /login
      if (!window.location.pathname.startsWith("/login")) {
        await clearStoredAuthSession();
        window.location.replace("/login");
        // Return a never-resolving promise to prevent further error handling
        // while the browser navigates away
        return new Promise(() => {});
      }
    }

    const payload = error.response?.data;
    const message =
      errorMessageFromValue(payload?.detail) ||
      errorMessageFromValue(payload?.error) ||
      payload?.message ||
      error.message ||
      `请求失败 (${status || 500})`;
    return Promise.reject(new Error(message));
  },
);

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  redirectOnUnauthorized?: boolean;
};

export async function httpRequest<T>(path: string, options: RequestOptions = {}) {
  const { method = "GET", body, headers, redirectOnUnauthorized = true } = options;
  const config: RequestConfig = {
    url: path,
    method,
    data: body,
    headers,
    redirectOnUnauthorized,
  };
  const response = await request.request<T>(config);
  return response.data;
}
