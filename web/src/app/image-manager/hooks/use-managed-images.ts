"use client";

import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import { fetchManagedImages, type ManagedImage } from "@/lib/api/images";
import { imageKey } from "@/lib/image-manager";
import { actionError } from "@/lib/action-result";

type UseManagedImagesOptions = {
  startDate: string;
  endDate: string;
};

type UseManagedImagesResult = {
  /** 当前筛选条件下的全量图片列表 */
  items: ManagedImage[];
  isLoading: boolean;
  /** 按日期筛选重新拉取；成功后返回新列表（失败返回 null） */
  loadImages: () => Promise<ManagedImage[] | null>;
  /** 已勾选图片的 key 集合（用于 O(1) 判断卡片选中态） */
  selectedSet: Set<string>;
  selectedPaths: string[];
  /** 批量勾选/取消勾选指定图片 */
  togglePaths: (paths: string[], checked: boolean) => void;
  clearSelection: () => void;
  /** 本地移除已删除的图片，并同步清理其选中状态 */
  removeItem: (rel: string) => void;
  /** 局部更新单张图片的标签，保持网格与后端一致 */
  updateItemTags: (rel: string, tags: string[]) => void;
  /** 移除所有图片上的某个标签（标签被全局删除时调用） */
  removeTagFromItems: (tag: string) => void;
};

/**
 * 图片管理页列表数据 hook：负责按日期拉取、勾选集合与本地增删同步。
 * 筛选（标签）与分页不在此处，由页面组合纯函数与 usePagination 完成。
 */
export function useManagedImages({ startDate, endDate }: UseManagedImagesOptions): UseManagedImagesResult {
  const [items, setItems] = useState<ManagedImage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);

  const loadImages = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchManagedImages({ start_date: startDate, end_date: endDate });
      setItems(data.items);
      // 重新加载后剔除已不存在的图片，避免批量操作命中失效路径
      setSelectedPaths((current) => current.filter((path) => data.items.some((item) => imageKey(item) === path)));
      return data.items;
    } catch (error) {
      toast.error(actionError(error, "加载图片失败"));
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate]);

  const selectedSet = useMemo(() => new Set(selectedPaths), [selectedPaths]);

  const togglePaths = useCallback((paths: string[], checked: boolean) => {
    setSelectedPaths((current) =>
      checked ? Array.from(new Set([...current, ...paths])) : current.filter((path) => !paths.includes(path)),
    );
  }, []);

  const clearSelection = useCallback(() => setSelectedPaths([]), []);

  const removeItem = useCallback((rel: string) => {
    setItems((prev) => prev.filter((item) => item.rel !== rel));
    setSelectedPaths((prev) => prev.filter((path) => path !== rel));
  }, []);

  const updateItemTags = useCallback((rel: string, tags: string[]) => {
    setItems((prev) => prev.map((item) => (item.rel === rel ? { ...item, tags } : item)));
  }, []);

  const removeTagFromItems = useCallback((tag: string) => {
    setItems((prev) =>
      prev.map((item) => ({ ...item, tags: (item.tags ?? []).filter((current) => current !== tag) })),
    );
  }, []);

  return {
    items,
    isLoading,
    loadImages,
    selectedSet,
    selectedPaths,
    togglePaths,
    clearSelection,
    removeItem,
    updateItemTags,
    removeTagFromItems,
  };
}
