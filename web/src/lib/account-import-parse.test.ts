/**
 * account-import-parse.ts 导入解析单测。
 *
 * 覆盖点：splitTokens 换行切分（含 CRLF 与空行）、getSessionAccessToken
 * 类型收窄、isRecord 判定、getAccountJsonAccount 对 Codex CLI auth.json
 * 平铺/嵌套两种 token 形态的兼容、getAccountJsonAccounts 的数组/单对象/
 * accounts|items 包裹三种格式、getCodexAuthAccount 的 export_type 标记。
 */
import { describe, expect, it } from "vitest";

import {
  getAccountJsonAccount,
  getAccountJsonAccounts,
  getCodexAuthAccount,
  getSessionAccessToken,
  isRecord,
  splitTokens,
} from "@/lib/account-import-parse";

describe("splitTokens", () => {
  it("按行切分并去除空行与首尾空白", () => {
    expect(splitTokens("a\n b \n\n c\r\nd")).toEqual(["a", "b", "c", "d"]);
  });

  it("空文本返回空数组", () => {
    expect(splitTokens("")).toEqual([]);
    expect(splitTokens("\n \n")).toEqual([]);
  });
});

describe("getSessionAccessToken", () => {
  it("仅接受字符串 accessToken 并 trim", () => {
    expect(getSessionAccessToken({ accessToken: " tok " })).toBe("tok");
    expect(getSessionAccessToken({ accessToken: 123 })).toBe("");
    expect(getSessionAccessToken({})).toBe("");
    expect(getSessionAccessToken(null)).toBe("");
    expect(getSessionAccessToken("str")).toBe("");
  });
});

describe("isRecord", () => {
  it("对象为 true，数组/原始值为 false", () => {
    expect(isRecord({ a: 1 })).toBe(true);
    expect(isRecord([1, 2])).toBe(false);
    expect(isRecord("x")).toBe(false);
    expect(isRecord(null)).toBe(false);
    expect(isRecord(undefined)).toBe(false);
  });
});

describe("getAccountJsonAccount", () => {
  it("解析平铺 access_token 形态并标记 codex 来源", () => {
    const payload = getAccountJsonAccount({
      access_token: "tok-a",
      refresh_token: "rt",
      email: "a@b.c",
    });
    expect(payload).toMatchObject({
      access_token: "tok-a",
      refresh_token: "rt",
      source_type: "codex",
    });
  });

  it("兼容 Codex CLI auth.json 嵌套 tokens 形态并展平", () => {
    const payload = getAccountJsonAccount({
      tokens: { access_token: "tok-nested", refresh_token: "rt-nested" },
      OPENAI_API_KEY: null,
    });
    expect(payload).toMatchObject({
      access_token: "tok-nested",
      refresh_token: "rt-nested",
      source_type: "codex",
    });
    expect(payload).not.toHaveProperty("tokens");
  });

  it("兼容 accessToken 别名", () => {
    expect(getAccountJsonAccount({ accessToken: "tok-camel" })?.access_token).toBe("tok-camel");
  });

  it("type=codex 转换为 export_type 标记", () => {
    const payload = getAccountJsonAccount({ access_token: "tok", type: "codex" });
    expect(payload?.export_type).toBe("codex");
    expect(payload).not.toHaveProperty("type");
  });

  it("缺 token 时返回 null", () => {
    expect(getAccountJsonAccount({ refresh_token: "rt" })).toBeNull();
    expect(getAccountJsonAccount("str")).toBeNull();
    expect(getAccountJsonAccount(null)).toBeNull();
  });
});

describe("getAccountJsonAccounts", () => {
  it("解析数组并跳过无效条目", () => {
    const accounts = getAccountJsonAccounts([
      { access_token: "tok-1" },
      { no_token: true },
      "invalid",
    ]);
    expect(accounts).toHaveLength(1);
    expect(accounts[0].access_token).toBe("tok-1");
  });

  it("解析单对象与 accounts/items 包裹两种格式", () => {
    expect(getAccountJsonAccounts({ access_token: "tok-single" })).toHaveLength(1);
    expect(getAccountJsonAccounts({ accounts: [{ access_token: "tok-1" }] })[0].access_token).toBe("tok-1");
    expect(getAccountJsonAccounts({ items: [{ access_token: "tok-2" }] })[0].access_token).toBe("tok-2");
  });

  it("无法识别的形状返回空数组", () => {
    expect(getAccountJsonAccounts(null)).toEqual([]);
    expect(getAccountJsonAccounts({ other: [] })).toEqual([]);
    expect(getAccountJsonAccounts({ accounts: "not-array" })).toEqual([]);
  });
});

describe("getCodexAuthAccount", () => {
  it("始终携带 export_type=codex 并展平嵌套 tokens", () => {
    const payload = getCodexAuthAccount({
      tokens: { access_token: "tok-nested", refresh_token: "rt" },
    });
    expect(payload).toMatchObject({
      access_token: "tok-nested",
      export_type: "codex",
      source_type: "codex",
    });
    expect(payload).not.toHaveProperty("tokens");
  });

  it("type=codex 被删除且不转成 export_type（已显式设置）", () => {
    const payload = getCodexAuthAccount({ access_token: "tok", type: "codex" });
    expect(payload?.export_type).toBe("codex");
    expect(payload).not.toHaveProperty("type");
  });

  it("缺 token 时返回 null", () => {
    expect(getCodexAuthAccount({})).toBeNull();
  });
});
