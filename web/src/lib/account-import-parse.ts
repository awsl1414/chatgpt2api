import type { AccountImportPayload } from "@/lib/api/accounts";

// 账号导入的纯解析函数：只做文本/JSON → 导入 payload 的转换，不触达网络与 UI

export function splitTokens(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function getSessionAccessToken(value: unknown) {
  const token = (value as { accessToken?: unknown })?.accessToken;
  return typeof token === "string" ? token.trim() : "";
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function getCodexTokenRecord(raw: Record<string, unknown>) {
  // Codex CLI 的 auth.json 会把 token 放在嵌套的 tokens 对象里，需要兼容两种形状
  const nested = isRecord(raw.tokens) ? raw.tokens : {};
  const tokenValue = raw.access_token ?? raw.accessToken ?? nested.access_token ?? nested.accessToken;
  const token = typeof tokenValue === "string" ? tokenValue.trim() : "";
  return { nested, token };
}

export function getAccountJsonAccount(value: unknown): AccountImportPayload | null {
  if (!isRecord(value)) {
    return null;
  }
  const raw = value;
  const { nested, token } = getCodexTokenRecord(raw);
  if (!token) {
    return null;
  }

  const payload: AccountImportPayload = {
    ...nested,
    ...raw,
    access_token: token,
    source_type: "codex",
  };
  delete payload.accessToken;
  delete payload.tokens;
  if (payload.type === "codex") {
    payload.export_type = "codex";
    delete payload.type;
  }
  return payload;
}

export function getAccountJsonAccounts(value: unknown): AccountImportPayload[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => getAccountJsonAccount(item))
      .filter((item): item is AccountImportPayload => Boolean(item));
  }

  const singleAccount = getAccountJsonAccount(value);
  if (singleAccount) {
    return [singleAccount];
  }

  if (value && typeof value === "object") {
    const raw = value as Record<string, unknown>;
    const nested = raw.accounts ?? raw.items;
    if (Array.isArray(nested)) {
      return nested
        .map((item) => getAccountJsonAccount(item))
        .filter((item): item is AccountImportPayload => Boolean(item));
    }
  }

  return [];
}

export function getCodexAuthAccount(value: unknown): AccountImportPayload | null {
  if (!isRecord(value)) {
    return null;
  }
  const raw = value;
  const { nested, token } = getCodexTokenRecord(raw);
  if (!token) {
    return null;
  }

  const payload: AccountImportPayload = {
    ...nested,
    ...raw,
    access_token: token,
    export_type: "codex",
    source_type: "codex",
  };
  delete payload.accessToken;
  delete payload.tokens;
  if (payload.type === "codex") {
    delete payload.type;
  }
  return payload;
}

export function readFileAsText(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error ?? new Error(`读取文件失败: ${file.name}`));
    reader.readAsText(file);
  });
}
