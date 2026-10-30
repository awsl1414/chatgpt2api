/**
 * 图片页通用纯工具函数：ID 生成、参数解析、会话标题/排序、额度与时间格式化。
 * 全部为无副作用的纯函数（除 createId 使用随机数），便于单测。
 */

import type { Account } from "@/lib/api/accounts";
import type { ImageModel } from "@/lib/api/types";
import type { ImageConversation } from "@/store/image-conversations";

/** 生成带时间戳前缀的短随机 ID，用于会话与轮次 */
export function createId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** 将生成数量输入收敛为 [1, 100] 内的整数字符串 */
export function clampImageCount(value: string): string {
  return String(Math.min(100, Math.max(1, Math.floor(Number(value) || 1))));
}

/** 解析 "宽x高" 尺寸字符串，非法时回退 1024x1024 */
export function parseImageSize(size: string): { width: string; height: string } {
  const match = size.match(/^(\d+)x(\d+)$/);
  return match ? { width: match[1], height: match[2] } : { width: "1024", height: "1024" };
}

/** 用提示词前 12 个字符生成会话标题 */
export function buildConversationTitle(prompt: string): string {
  const trimmed = prompt.trim();
  if (trimmed.length <= 12) {
    return trimmed;
  }
  return `${trimmed.slice(0, 12)}...`;
}

/** 按 updatedAt 倒序排列会话（新会话在前） */
export function sortImageConversations(conversations: ImageConversation[]): ImageConversation[] {
  return [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

/**
 * 挑选删除/清空后的兜底选中会话：
 * 优先选仍有排队或生成中任务的会话，否则选最近更新的一个。
 */
export function pickFallbackConversationId(conversations: ImageConversation[]): string | null {
  const activeConversation = conversations.find((conversation) =>
    conversation.turns.some((turn) => turn.status === "queued" || turn.status === "generating"),
  );
  return activeConversation?.id ?? conversations[0]?.id ?? null;
}

/** 从模型列表中筛出图片生成模型并去重 */
export function filterImageModels(items: { id?: string | null }[]): ImageModel[] {
  return items
    .map((item) => String(item.id || "").trim())
    .filter((id, index, list) => id.toLowerCase().includes("image") && list.indexOf(id) === index);
}

/** 将持久化的模型选择收敛到当前可用模型，不可用时回退列表第一个 */
export function normalizeStoredImageModel(value: string | null, availableModels: ImageModel[]): ImageModel {
  const normalized = String(value || "").trim();
  if (normalized && availableModels.includes(normalized)) {
    return normalized;
  }
  return availableModels[0] || "gpt-image-2";
}

/** 管理员可用额度：非「禁用」账号额度求和（仅管理员页面使用） */
export function formatAvailableQuota(accounts: Account[]): string {
  const availableAccounts = accounts.filter((account) => account.status !== "禁用");
  return String(availableAccounts.reduce((sum, account) => sum + Math.max(0, account.quota), 0));
}

/** 会话/轮次时间展示：MM-DD HH:mm，非法时间返回空串 */
export function formatConversationTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
