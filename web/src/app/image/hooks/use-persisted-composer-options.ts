"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchModels } from "@/lib/api/models";
import type { ImageModel } from "@/lib/api/types";
import { aspectFallbackForModel } from "@/lib/image-composer-options";
import { clampImageCount, filterImageModels, normalizeStoredImageModel } from "@/lib/image-utils";
import {
  IMAGE_COUNT_STORAGE_KEY,
  IMAGE_MODEL_STORAGE_KEY,
  IMAGE_QUALITY_STORAGE_KEY,
  IMAGE_RATIO_STORAGE_KEY,
  IMAGE_TIER_STORAGE_KEY,
} from "@/lib/image-storage-keys";

/**
 * 图片生成参数（不含提示词与参考图）。
 * 作为 ImageComposer 的单一受控值对象传递，新增参数只需在类型与默认值处各改一次。
 */
export type ImageComposerOptions = {
  imageCount: string;
  imageRatio: string;
  imageTier: string;
  imageWidth: string;
  imageHeight: string;
  imageQuality: string;
  imageModel: ImageModel;
  imageModels: ImageModel[];
};

type UsePersistedComposerOptionsResult = ImageComposerOptions & {
  /** 收敛后的生成参数对象，直接作为 ImageComposer 的 options prop */
  options: ImageComposerOptions;
  /** 合并式更新生成参数：只传要改的字段，其余保持当前值 */
  patchOptions: (patch: Partial<ImageComposerOptions>) => void;
  /** imageCount 的合法整数值（[1, 100]） */
  parsedCount: number;
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

  const options = useMemo<ImageComposerOptions>(
    () => ({ imageCount, imageRatio, imageTier, imageWidth, imageHeight, imageQuality, imageModel, imageModels }),
    [imageCount, imageRatio, imageTier, imageWidth, imageHeight, imageQuality, imageModel, imageModels],
  );

  /**
   * 合并式更新生成参数：只覆盖 patch 中出现的字段。
   * imageCount 仍走 clamp 收敛，其余字段原样写入，与逐个 setter 的行为一致。
   */
  const patchOptions = useCallback((patch: Partial<ImageComposerOptions>) => {
    if (patch.imageCount !== undefined) {
      setImageCount(patch.imageCount);
    }
    if (patch.imageRatio !== undefined) {
      setImageRatio(patch.imageRatio);
    }
    if (patch.imageTier !== undefined) {
      setImageTier(patch.imageTier);
    }
    if (patch.imageWidth !== undefined) {
      setImageWidth(patch.imageWidth);
    }
    if (patch.imageHeight !== undefined) {
      setImageHeight(patch.imageHeight);
    }
    if (patch.imageQuality !== undefined) {
      setImageQuality(patch.imageQuality);
    }
    if (patch.imageModel !== undefined) {
      setImageModel(patch.imageModel);
    }
    if (patch.imageModels !== undefined) {
      setImageModels(patch.imageModels);
    }
  }, [setImageCount]);

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

  // 持久化读回或异步加载模型后，收敛到该模型可用的档位：
  // 用户上次可能停在 2K 档，或上次模型是 codex 而当前已是 picture_v2（反之亦然）。
  useEffect(() => {
    const fallback = aspectFallbackForModel(imageModel, imageRatio, imageTier);
    if (!fallback) {
      return;
    }
    setImageRatio(fallback.ratio);
    setImageTier(fallback.tier);
    setImageWidth(fallback.width);
    setImageHeight(fallback.height);
  }, [imageModel, imageRatio, imageTier]);

  // 切换模型时同步校验尺寸：新模型不接受 size（codex 系列）时回退到 auto，
  // 否则把 2K/4K 档回退到同比例 1K 档（见 lib/image-composer-options）
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
    options,
    patchOptions,
    parsedCount,
    handleImageModelChange,
    loadPersistedOptions,
  };
}
