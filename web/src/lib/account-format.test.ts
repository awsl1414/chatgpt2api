/**
 * account-format.ts 格式化纯函数单测。
 *
 * 覆盖点：formatCompact 紧凑数值、formatQuota 负数回退、formatRestoreAt
 * 绝对/相对时间与非法值回退、formatQuotaSummary 仅统计正常账号、
 * maskToken 脱敏规则、displayAccountType / displayAccountSource 空值回退。
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  displayAccountSource,
  displayAccountType,
  formatCompact,
  formatQuota,
  formatQuotaSummary,
  formatRestoreAt,
  maskToken,
} from "@/lib/account-format";
import type { Account } from "@/lib/api/accounts";

function makeAccount(overrides: Partial<Account>): Account {
  return {
    access_token: "token",
    type: "free",
    status: "正常",
    quota: 0,
    success: 0,
    fail: 0,
    ...overrides,
  };
}

describe("formatCompact", () => {
  it("小于 1000 时原样输出", () => {
    expect(formatCompact(0)).toBe("0");
    expect(formatCompact(999)).toBe("999");
  });

  it("大于等于 1000 时显示 x.xk", () => {
    expect(formatCompact(1000)).toBe("1.0k");
    expect(formatCompact(1533)).toBe("1.5k");
    expect(formatCompact(12345)).toBe("12.3k");
  });
});

describe("formatQuota", () => {
  it("负数按 0 处理", () => {
    expect(formatQuota(makeAccount({ quota: -5 }))).toBe("0");
    expect(formatQuota(makeAccount({ quota: 42 }))).toBe("42");
  });
});

describe("formatRestoreAt", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-31T12:00:00"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("空值返回占位符", () => {
    expect(formatRestoreAt(null)).toEqual({ absolute: "—", relative: "" });
    expect(formatRestoreAt(undefined)).toEqual({ absolute: "—", relative: "" });
  });

  it("非法日期原样返回", () => {
    expect(formatRestoreAt("not-a-date")).toEqual({ absolute: "not-a-date", relative: "" });
  });

  it("未来时间返回绝对时间与剩余天数小时", () => {
    const result = formatRestoreAt("2026-11-01T13:30:00");
    expect(result.absolute).toBe("2026-11-01 13:30:00");
    expect(result.relative).toBe("剩余 1d 2h");
  });

  it("已过期时间显示已到恢复时间", () => {
    const result = formatRestoreAt("2026-10-30T00:00:00");
    expect(result.relative).toBe("已到恢复时间");
  });
});

describe("formatQuotaSummary", () => {
  it("仅统计正常账号的非负额度", () => {
    const accounts = [
      makeAccount({ status: "正常", quota: 100 }),
      makeAccount({ status: "限流", quota: 50 }),
      makeAccount({ status: "异常", quota: 30 }),
      makeAccount({ status: "正常", quota: -10 }),
    ];
    expect(formatQuotaSummary(accounts)).toBe("100");
  });

  it("汇总达到 1000 时紧凑显示", () => {
    const accounts = [
      makeAccount({ status: "正常", quota: 600 }),
      makeAccount({ status: "正常", quota: 600 }),
    ];
    expect(formatQuotaSummary(accounts)).toBe("1.2k");
  });
});

describe("maskToken", () => {
  it("空值返回占位符", () => {
    expect(maskToken(undefined)).toBe("—");
    expect(maskToken("")).toBe("—");
  });

  it("短 token 原样展示", () => {
    expect(maskToken("short-token-12")).toBe("short-token-12");
  });

  it("长 token 保留前 16 位与后 8 位", () => {
    const token = "a".repeat(16) + "b".repeat(8) + "c".repeat(4);
    expect(maskToken(token)).toBe(`${"a".repeat(16)}...${"b".repeat(4)}${"c".repeat(4)}`);
  });
});

describe("displayAccountType / displayAccountSource", () => {
  it("类型空值回退 Free", () => {
    expect(displayAccountType(makeAccount({ type: "" }))).toBe("Free");
    expect(displayAccountType(makeAccount({ type: "plus" }))).toBe("plus");
  });

  it("来源空值回退 web 且统一小写", () => {
    expect(displayAccountSource(makeAccount({ source_type: null }))).toBe("web");
    expect(displayAccountSource(makeAccount({ source_type: "  " }))).toBe("web");
    expect(displayAccountSource(makeAccount({ source_type: "WEB" }))).toBe("web");
    expect(displayAccountSource(makeAccount({ source_type: "Codex" }))).toBe("codex");
  });
});
