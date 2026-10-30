"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { aspectFallbackForModel } from "@/app/image/components/image-composer";
import { fetchModels } from "@/lib/api/models";
import type { ImageModel } from "@/lib/api/types";
import { clampImageCount, filterImageModels, normalizeStoredImageModel } from "@/lib/image-utils";
import {
  IMAGE_COUNT_STORAGE_KEY,
  IMAGE_MODEL_STORAGE_KEY,
  IMAGE_QUALITY_STORAGE_KEY,
  IMAGE_RATIO_STORAGE_KEY,
  IMAGE_TIER_STORAGE_KEY,
} from "@/lib/image-storage-keys";

type UsePersistedComposerOptionsResult = {
  imageCount: string;
  imageRatio: string;
  imageTier: string;
  imageWidth: string;
  imageHeight: string;
  imageQuality: string;
  imageModel: ImageModel;
  imageModels: ImageModel[];
  /** imageCount 的合法整数值（[1, 100]） */
  parsedCount: number;
  setImageCount: (value: string) => void;
  setImageRatio: (value: string) => void;
  setImageTier: (value: string) => void;
  setImageWidth: (value: string) => void;
  setImageHeight: (value: string) => void;
  setImageQuality: (value: string) => void;
  setImageModel: (value: ImageModel) => void;
  /** 切换模型时同步校验档位：非 Codex 模型自动回退同比例 1K 档 */
  handleImageModelChange: (model: ImageModel) => void;
  /** 挂载/bfcache 恢复时从 localStorage 读回持久化的 composer 选项（由页面 loadHistory 调用） */
  loadPersistedOptions: () => void;
};

/**
 * 图片 composer 选项的持久化 hook（审计 §5）：
 * 宽高比/档位/质量/模型/数量在变更时写入 localStorage，挂载时读回；
 * 可用模型列表从 /api/models 异步加载并收敛当前选择。
 * 生成尺寸（宽/高）不持久化，每次加载重置为 1024。
 */
export function usePersistedComposerOptions(): UsePersistedComposerOptionsResult {
  const [imageCount, setImageCountRaw] = useState("3");
  const [imageRatio, setImageRatio] = useState("auto");
  const [imageTier, setImageTier] = useState("1k");
  const [imageWidth, setImageWidth] = useState("1024");
  const [imageHeight, setImageHeight] = useState("1024");
  const [imageQuality, setImageQuality] = useState("auto");
  const [imageModel, setImageModel] = useState<ImageModel>("gpt-image-2");
  const [imageModels, setImageModels] = useState<ImageModel[]>(["gpt-image-2"]);

  const parsedCount = useMemo(() => Number(clampImageCount(imageCount)), [imageCount]);

  /** 数量输入统一收敛为 [1, 100] 整数字符串 */
  const setImageCount = useCallback((value: string) => {
    setImageCountRaw(value ? clampImageCount(value) : "");
  }, []);

  const loadPersistedOptions = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    setImageRatio(window.localStorage.getItem(IMAGE_RATIO_STORAGE_KEY) || "1:1");
    setImageTier(window.localStorage.getItem(IMAGE_TIER_STORAGE_KEY) || "1k");
    setImageWidth("1024");
    setImageHeight("1024");
    setImageQuality(window.localStorage.getItem(IMAGE_QUALITY_STORAGE_KEY) || "auto");
    setImageCountRaw(window.localStorage.getItem(IMAGE_COUNT_STORAGE_KEY) || "1");
  }, []);

  // 加载可用图片模型列表，并把当前选择收敛到可用集合
  useEffect(() => {
    let cancelled = false;

    const loadImageModels = async () => {
      try {
        const data = await fetchModels();
        const available = filterImageModels(Array.isArray(data.data) ? data.data : []);
        if (cancelled || available.length === 0) {
          return;
        }
        setImageModels(available);
        const storedModel =
          typeof window !== "undefined" ? window.localStorage.getItem(IMAGE_MODEL_STORAGE_KEY) : null;
        setImageModel((current) => {
          if (available.includes(current)) {
            return current;
          }
          return normalizeStoredImageModel(storedModel, available);
        });
      } catch {
        if (!cancelled) {
          setImageModels(["gpt-image-2"]);
        }
      }
    };

    void loadImageModels();
    return () => {
      cancelled = true;
    };
  }, []);

  // 选项变更时写入 localStorage
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(IMAGE_RATIO_STORAGE_KEY, imageRatio);
    window.localStorage.setItem(IMAGE_TIER_STORAGE_KEY, imageTier);
    window.localStorage.setItem(IMAGE_QUALITY_STORAGE_KEY, imageQuality);
    window.localStorage.setItem(IMAGE_MODEL_STORAGE_KEY, imageModel);
  }, [imageRatio, imageTier, imageQuality, imageModel]);

  useEffect(() => {
    if (typeof window !== "undefined" && parsedCount > 0) {
      window.localStorage.setItem(IMAGE_COUNT_STORAGE_KEY, String(parsedCount));
    }
  }, [parsedCount]);

  // 切换模型时同步校验尺寸：非 Codex 模型不支持 2K/4K 档，自动回退到同比例 1K 档
  const handleImageModelChange = useCallback(
    (model: ImageModel) => {
      setImageModel(model);
      const fallback = aspectFallbackForModel(model, imageRatio, imageTier);
      if (fallback) {
        setImageRatio(fallback.ratio);
        setImageTier(fallback.tier);
        setImageWidth(fallback.width);
        setImageHeight(fallback.height);
      }
    },
    [imageRatio, imageTier],
  );

  return {
    imageCount,
    imageRatio,
    imageTier,
    imageWidth,
    imageHeight,
    imageQuality,
    imageModel,
    imageModels,
    parsedCount,
    setImageCount,
    setImageRatio,
    setImageTier,
    setImageWidth,
    setImageHeight,
    setImageQuality,
    setImageModel,
    handleImageModelChange,
    loadPersistedOptions,
  };
}
