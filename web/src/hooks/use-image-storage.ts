"use client";

import { useCallback, useState } from "react";

import {
  compressAllImages,
  deleteToTarget,
  fetchImageStorage,
  type ImageStorageStats,
} from "@/lib/api/images";
import { useInitialLoad } from "@/hooks/use-initial-load";

type UseImageStorageResult = {
  storage: ImageStorageStats | null;
  isLoading: boolean;
  /** 重新拉取存储统计（刷新 / 压缩 / 清理后调用） */
  reload: () => Promise<void>;
  /** 压缩全部图片，返回释放的 MB 数 */
  compress: () => Promise<number>;
  /** 清理图片直到剩余空间达到目标值，返回删除张数与释放 MB 数 */
  cleanupToTarget: (targetFreeMb: number) => Promise<{ removed: number; freedMb: number }>;
};

/**
 * 图片存储统计 hook：磁盘/图片占用数据与压缩、按目标清理两个动作。
 * 拉取失败保持 `storage === null`，由面板展示失败占位。
 */
export function useImageStorage(): UseImageStorageResult {
  const [storage, setStorage] = useState<ImageStorageStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const reload = useCallback(async () => {
    setIsLoading(true);
    try {
      setStorage(await fetchImageStorage());
    } catch {
      // 存储统计属于辅助信息，失败时不打断页面，保持面板失败占位
    } finally {
      setIsLoading(false);
    }
  }, []);

  useInitialLoad(() => void reload());

  const compress = useCallback(async () => {
    const result = await compressAllImages();
    await reload();
    return result.saved_mb;
  }, [reload]);

  const cleanupToTarget = useCallback(
    async (targetFreeMb: number) => {
      const result = await deleteToTarget(targetFreeMb);
      await reload();
      return { removed: result.removed, freedMb: result.freed_mb ?? 0 };
    },
    [reload],
  );

  return { storage, isLoading, reload, compress, cleanupToTarget };
}
