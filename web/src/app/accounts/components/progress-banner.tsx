"use client";

// 刷新 / 重新登录任务的进度横幅：数据一律来自后端进度接口或真实完成状态，不做本地模拟
export type ProgressState = {
  visible: boolean;
  current: number;
  total: number;
  message: string;
  email: string;
};

export const initialProgressState: ProgressState = {
  visible: false,
  current: 0,
  total: 0,
  message: "",
  email: "",
};

export function ProgressBanner({ progress }: { progress: ProgressState }) {
  if (!progress.visible) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white/90 shadow-sm">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-stone-600">
            {progress.message}
            {progress.email && <span className="ml-1 font-medium text-stone-700">{progress.email}</span>}
          </span>
          <span className="font-medium text-stone-700">
            {progress.current}/{progress.total}
          </span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-stone-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all duration-300 ease-out"
            style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
          />
        </div>
      </div>
    </div>
  );
}
