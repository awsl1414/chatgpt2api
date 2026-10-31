/**
 * 图片管理页通用纯工具：图片稳定标识、大小/容量格式化、共享常量。
 * 全部为无副作用纯函数（常量除外），便于单测。
 */

import type { ManagedImage } from "@/lib/api/images";

/** 图片管理页每页条数（usePagination 以字符串持有，直接适配 Select 的 value） */
export const IMAGE_MANAGER_PAGE_SIZE = "12";

/** 图片管理页复选框统一样式：亮/暗色下的边框与选中态保持一致 */
export const IMAGE_MANAGER_CHECKBOX_CLASS =
  "border-stone-300 bg-white/80 dark:border-white/35 dark:bg-white/5 data-[state=checked]:border-stone-950 dark:data-[state=checked]:border-white";

/** 图片的稳定标识：优先使用相对路径，缺省回退 URL */
export function imageKey(item: ManagedImage): string {
  return item.rel || item.url;
}

/** 单张图片大小展示：超过 1MB 保留两位小数，否则向上取整到 KB */
export function formatSize(size: number): string {
  return size > 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(2)} MB` : `${Math.ceil(size / 1024)} KB`;
}

/** 存储容量展示（MB 入参）：超过 1024MB 折算为 GB 并保留一位小数 */
export function formatCapacity(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}
