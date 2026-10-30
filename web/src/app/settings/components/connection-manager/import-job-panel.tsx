"use client";

import { Badge } from "@/components/ui/badge";
import type { CPAImportJob } from "@/lib/api";

/** 连接卡内的导入任务进度面板，CPA 与 Sub2API 共用 */
export function ImportJobPanel({ job }: { job: CPAImportJob }) {
  const progress = job.total > 0 ? Math.round((job.completed / job.total) * 100) : 0;

  return (
    <div className="space-y-2 rounded-xl bg-stone-50 px-3 py-3">
      <div className="text-xs font-medium tracking-[0.16em] text-stone-400 uppercase">导入任务</div>
      <div className="rounded-lg border border-stone-200 bg-white px-3 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-stone-700">
              状态 {job.status}，已处理 {job.completed}/{job.total}
            </div>
            <div className="truncate text-xs text-stone-400">
              任务 {job.job_id.slice(0, 8)} · {job.created_at}
            </div>
          </div>
          <Badge
            variant={job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "info"}
            className="rounded-md"
          >
            {progress}%
          </Badge>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-200">
          <div className="h-full rounded-full bg-stone-900 transition-all" style={{ width: `${progress}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-500">
          <span>新增 {job.added}</span>
          <span>跳过 {job.skipped}</span>
          <span>刷新 {job.refreshed}</span>
          <span>失败 {job.failed}</span>
        </div>
      </div>
    </div>
  );
}
