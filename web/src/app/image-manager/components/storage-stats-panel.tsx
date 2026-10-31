"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ImageStorageStats } from "@/lib/api/images";
import { formatCapacity } from "@/lib/image-manager";

type StorageStatsPanelProps = {
  storage: ImageStorageStats | null;
  isLoading: boolean;
  /** 重新拉取统计 */
  onRefresh: () => Promise<void>;
  /** 压缩全部图片，返回释放 MB 数 */
  onCompress: () => Promise<number>;
  /** 清理图片直到剩余空间达到目标 MB，返回删除张数与释放 MB */
  onCleanupToTarget: (targetFreeMb: number) => Promise<{ removed: number; freedMb: number }>;
  /** 打开「按日期删除」弹窗 */
  onRequestDeleteByDate: () => void;
};

const STAT_CARD_CLASS = "rounded-xl border border-stone-200 bg-white/80 p-3";

/** 磁盘剩余空间按阈值着色：<200MB 红、<500MB 黄、否则绿 */
function freeSpaceClass(freeMb: number): string {
  if (freeMb < 200) {
    return "text-red-500";
  }
  return freeMb < 500 ? "text-yellow-500" : "text-green-600";
}

/** 存储统计面板：磁盘/图片占用指标 + 刷新、压缩、按日期删除、清理至目标空间 */
export function StorageStatsPanel({
  storage,
  isLoading,
  onRefresh,
  onCompress,
  onCleanupToTarget,
  onRequestDeleteByDate,
}: StorageStatsPanelProps) {
  const [compressResult, setCompressResult] = useState("");
  const [targetFreeMb, setTargetFreeMb] = useState(500);

  const handleCompress = async () => {
    try {
      setCompressResult(`已压缩${await onCompress()}MB`);
    } catch {
      setCompressResult("压缩失败");
    }
  };

  const handleCleanup = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const result = await onCleanupToTarget(targetFreeMb);
      toast.success(`已删除 ${result.removed} 张图片，释放 ${result.freedMb}MB`);
    } catch {
      toast.error("清理失败");
    }
  };

  return (
    <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
      {storage ? (
        <>
          <div className={STAT_CARD_CLASS}>
            <div className="text-xs text-stone-500">磁盘总量</div>
            <div className="text-lg font-bold text-stone-800">{formatCapacity(storage.disk_total_mb)}</div>
          </div>
          <div className={STAT_CARD_CLASS}>
            <div className="text-xs text-stone-500">剩余空间</div>
            <div className={`text-lg font-bold ${freeSpaceClass(storage.disk_free_mb)}`}>
              {formatCapacity(storage.disk_free_mb)}
            </div>
          </div>
          <div className={STAT_CARD_CLASS}>
            <div className="text-xs text-stone-500">图片数量</div>
            <div className="text-lg font-bold text-stone-800">{storage.image_count}</div>
          </div>
          <div className={STAT_CARD_CLASS}>
            <div className="text-xs text-stone-500">图片占用</div>
            <div className="text-lg font-bold text-stone-800">{formatCapacity(storage.image_size_mb)}</div>
          </div>
          <div className={`${STAT_CARD_CLASS} col-span-2 flex flex-wrap items-center gap-2`}>
            <span className="w-full text-xs text-stone-500">快捷操作</span>
            <Button size="sm" variant="outline" className="h-7 text-xs" disabled={isLoading} onClick={() => void onRefresh()}>
              <RefreshCw className={`mr-1 size-3 ${isLoading ? "animate-spin" : ""}`} />刷新
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void handleCompress()}>
              🗜️ 压缩优化
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 border-rose-200 text-xs text-rose-600"
              onClick={onRequestDeleteByDate}
            >
              🗑️ 按日期删除
            </Button>
            <form onSubmit={(event) => void handleCleanup(event)} className="flex items-center gap-1">
              <Button size="sm" variant="outline" className="h-7 border-amber-200 text-xs text-amber-700" type="submit">
                🧹 清理至
              </Button>
              <Input
                className="h-7 w-14 px-1 text-center text-xs"
                type="number"
                min={50}
                value={targetFreeMb}
                onChange={(event) => setTargetFreeMb(Number(event.target.value) || 500)}
              />
              <span className="text-xs text-stone-400">MB 剩余</span>
            </form>
            {compressResult ? <span className="ml-1 text-xs text-green-600">{compressResult}</span> : null}
          </div>
        </>
      ) : (
        <div className={`${STAT_CARD_CLASS} col-span-full text-center text-sm text-stone-400`}>
          {isLoading ? "加载存储信息..." : "存储信息加载失败"}
        </div>
      )}
    </div>
  );
}
