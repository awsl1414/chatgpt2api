"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";

import { deleteImageTag, fetchImageTags, setImageTags, type ManagedImage } from "@/lib/api/images";
import { appendTag } from "@/lib/image-tags";
import { actionError } from "@/lib/action-result";
import { useInitialLoad } from "@/hooks/use-initial-load";

type UseImageTagsOptions = {
  /** 单张图片标签更新成功后，同步网格中的该图片 */
  onTagsApplied: (rel: string, tags: string[]) => void;
  /** 标签被全局删除后，从所有图片上移除该标签 */
  onTagRemoved: (tag: string) => void;
};

type UseImageTagsResult = {
  /** 全部已存在的标签（用于筛选条与快捷添加候选） */
  allTags: string[];
  /** 当前生效的筛选标签（AND 语义） */
  selectedTags: string[];
  toggleFilterTag: (tag: string) => void;
  clearFilterTags: () => void;
  /** 覆盖设置某张图片的标签 */
  applyTags: (item: ManagedImage, tags: string[]) => Promise<void>;
  /** 追加一个标签；输入为空或已存在时提示并返回 false */
  addTag: (item: ManagedImage, rawTag: string) => boolean;
  removeTag: (item: ManagedImage, tag: string) => void;
  /** 全局删除标签，并从筛选条件/本地图片中同步移除 */
  deleteTag: (tag: string) => Promise<void>;
};

/**
 * 图片标签 hook：标签列表、筛选条件与增删改的后端同步。
 * 标签编辑弹层的开关与输入框状态由卡片组件本地持有，不进入页面状态。
 */
export function useImageTags({ onTagsApplied, onTagRemoved }: UseImageTagsOptions): UseImageTagsResult {
  const [allTags, setAllTags] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const reloadTags = useCallback(async () => {
    try {
      const data = await fetchImageTags();
      setAllTags(data.tags);
    } catch (error) {
      toast.error(actionError(error, "加载标签失败"));
    }
  }, []);

  useInitialLoad(() => void reloadTags());

  const toggleFilterTag = useCallback((tag: string) => {
    setSelectedTags((prev) => (prev.includes(tag) ? prev.filter((current) => current !== tag) : [...prev, tag]));
  }, []);

  const clearFilterTags = useCallback(() => setSelectedTags([]), []);

  const applyTags = useCallback(
    async (item: ManagedImage, tags: string[]) => {
      try {
        const result = await setImageTags(item.rel, tags);
        onTagsApplied(item.rel, result.tags);
        await reloadTags();
      } catch (error) {
        toast.error(actionError(error, "设置标签失败"));
      }
    },
    [onTagsApplied, reloadTags],
  );

  const addTag = useCallback(
    (item: ManagedImage, rawTag: string) => {
      const nextTags = appendTag(item.tags, rawTag);
      if (nextTags === null) {
        if (rawTag.trim()) {
          toast.error("标签已存在");
        }
        return false;
      }
      void applyTags(item, nextTags);
      return true;
    },
    [applyTags],
  );

  const removeTag = useCallback(
    (item: ManagedImage, tag: string) => {
      void applyTags(
        item,
        (item.tags ?? []).filter((current) => current !== tag),
      );
    },
    [applyTags],
  );

  const deleteTag = useCallback(
    async (tag: string) => {
      try {
        const result = await deleteImageTag(tag);
        setAllTags((prev) => prev.filter((current) => current !== tag));
        setSelectedTags((prev) => prev.filter((current) => current !== tag));
        onTagRemoved(tag);
        toast.success(`标签"${tag}"已删除，影响 ${result.removed_from} 张图片`);
      } catch (error) {
        toast.error(actionError(error, "删除标签失败"));
      }
    },
    [onTagRemoved],
  );

  return {
    allTags,
    selectedTags,
    toggleFilterTag,
    clearFilterTags,
    applyTags,
    addTag,
    removeTag,
    deleteTag,
  };
}
