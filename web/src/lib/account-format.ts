import type { Account } from "@/lib/api/accounts";

// 账号页展示用的纯格式化函数：无副作用、无 DOM 依赖，便于单测与复用

/** 数值紧凑展示：≥1000 显示为 x.xk，否则原样 */
export function formatCompact(value: number) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return String(value);
}

/** 额度展示：负数按 0 处理 */
export function formatQuota(account: Account) {
  return String(Math.max(0, account.quota));
}

/** 恢复时间展示：返回绝对时间（YYYY-MM-DD HH:mm:ss）与相对剩余时间的组合 */
export function formatRestoreAt(value?: string | null) {
  if (!value) {
    return { absolute: "—", relative: "" };
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { absolute: value, relative: "" };
  }

  const diffMs = Math.max(0, date.getTime() - Date.now());
  const totalHours = Math.ceil(diffMs / (1000 * 60 * 60));
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  const relative = diffMs > 0 ? `剩余 ${days}d ${hours}h` : "已到恢复时间";

  const pad = (num: number) => String(num).padStart(2, "0");
  const absolute = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;

  return { absolute, relative };
}

/** 额度汇总：仅统计「正常」账号的非负额度之和（与统计卡片口径一致） */
export function formatQuotaSummary(accounts: Account[]) {
  const availableAccounts = accounts.filter((account) => account.status === "正常");
  return formatCompact(availableAccounts.reduce((sum, account) => sum + Math.max(0, account.quota), 0));
}

/** Token 脱敏展示：保留前 16 位与后 8 位 */
export function maskToken(token?: string) {
  if (!token) return "—";
  if (token.length <= 18) return token;
  return `${token.slice(0, 16)}...${token.slice(-8)}`;
}

/** 账号类型展示：空值回退为 Free */
export function displayAccountType(account: Account) {
  return account.type || "Free";
}

/** 账号来源展示：空值回退为 web */
export function displayAccountSource(account: Account) {
  const source = String(account.source_type || "").trim().toLowerCase();
  if (!source) {
    return "web";
  }
  if (source === "web") {
    return "web";
  }
  return source;
}
