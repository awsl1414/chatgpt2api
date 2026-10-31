/**
 * 图片标签纯逻辑：按标签筛选、标签增删的不可变更新、候选标签计算。
 * 与 UI 解耦，便于单测；API 调用在 hooks/use-managed-images 中完成。
 */

import type { ManagedImage } from "@/lib/api/images";

/** 多标签筛选：图片需同时包含全部选中标签（AND 语义）；未选标签时原样返回 */
export function filterImagesByTags(items: ManagedImage[], selectedTags: string[]): ManagedImage[] {
  if (selectedTags.length === 0) {
    return items;
  }
  return items.filter((item) => selectedTags.every((tag) => (item.tags ?? []).includes(tag)));
}

/**
 * 追加标签（自动去除首尾空白）。
 * 标签为空或已存在时返回 null，表示无需更新。
 */
export function appendTag(tags: string[] | undefined, tag: string): string[] | null {
  const normalized = tag.trim();
  if (!normalized) {
    return null;
  }
  const current = tags ?? [];
  if (current.includes(normalized)) {
    return null;
  }
  return [...current, normalized];
}

/** 图片尚未拥有的标签：标签编辑弹层中的快捷候选 */
export function unusedTags(tags: string[] | undefined, allTags: string[]): string[] {
  return allTags.filter((tag) => !(tags ?? []).includes(tag));
}
