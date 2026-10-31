/**
 * 统一剪贴板复制工具：成功提示文案由调用方指定，失败统一 toastError。
 * 收敛原先 6 处裸 navigator.clipboard.writeText 调用（文案/错误处理不一，
 * 且 skill-panel 的 copyText 失败时会产生 unhandled rejection，审查 R3-L4）。
 */

import { toast } from "sonner";

/** 复制文本到剪贴板；成功返回 true 并 toast 成功文案，失败/环境不支持返回 false */
export async function copyToClipboard(text: string, successMessage = "已复制到剪贴板"): Promise<boolean> {
  try {
    if (!navigator.clipboard?.writeText) {
      toast.error("当前环境不支持自动复制，请手动选择并复制");
      return false;
    }
    await navigator.clipboard.writeText(text);
    toast.success(successMessage);
    return true;
  } catch (error) {
    toast.error(error instanceof Error ? error.message : "复制失败，请手动复制");
    return false;
  }
}
