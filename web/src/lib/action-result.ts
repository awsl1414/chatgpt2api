import { toast } from "sonner";

/**
 * Store 层动作的统一返回形态：store 不直接弹 toast（审计 F-低2），
 * 把结果交还给调用组件，由组件决定成功/失败的提示文案。
 */
export type ActionResult = {
  ok: boolean;
  /** 失败时的具体错误描述；组件侧以此作为 toast 文案，缺省时用 fallback */
  error?: string;
  /** 成功时带数据量的提示文案；组件侧优先使用，缺省时用成功 fallback */
  message?: string;
};

/** 把 ActionResult 转成 toast；message 优先于成功 fallback，error 优先于失败 fallback */
export function toastActionResult(result: ActionResult, successFallback: string, errorFallback: string): void {
  if (result.ok) {
    toast.success(result.message ?? successFallback);
  } else {
    toast.error(result.error ?? errorFallback);
  }
}

/** 把 catch 到的未知错误规范化为用户可读文案 */
export function actionError(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
