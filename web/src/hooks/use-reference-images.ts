"use client";

import { useCallback, useState, type RefObject } from "react";
import { toast } from "sonner";

import { buildReferenceImageFromStoredImage, dataUrlToFile, readFileAsDataUrl } from "@/lib/image-reference";
import type { StoredImage, StoredReferenceImage } from "@/store/image-conversations";

type UseReferenceImagesOptions = {
  /** composer 内隐藏的文件选择 input */
  fileInputRef: RefObject<HTMLInputElement | null>;
  /** composer 提示词输入框，继续编辑/复用配置后聚焦 */
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  setSelectedConversationId: (id: string | null) => void;
};

type UseReferenceImagesResult = {
  /** 待提交的参考图 File 列表（决定 generate / edit 模式） */
  referenceImageFiles: File[];
  /** 参考图预览（dataUrl）列表，与 referenceImageFiles 一一对应 */
  referenceImages: StoredReferenceImage[];
  /** 追加参考图文件并生成预览 */
  append: (files: File[]) => Promise<void>;
  /** 移除指定位置的参考图 */
  remove: (index: number) => void;
  /** 清空参考图并重置文件选择 input */
  clear: () => void;
  /** 「继续编辑」：把历史结果图/参考图加入当前参考图列表并聚焦输入框 */
  continueEdit: (conversationId: string, image: StoredImage | StoredReferenceImage) => Promise<void>;
  /** 「复用提示词配置」：从历史轮次恢复参考图列表 */
  reuseFromTurn: (turn: StoredReferenceImage[]) => void;
};

/**
 * 图片 composer 参考图管理 hook（审计 §5）：
 * 统一维护「预览 dataUrl 列表 + 提交 File 列表」这对平行状态，
 * 以及继续编辑 / 复用配置两条从历史图片恢复参考图的链路。
 */
export function useReferenceImages({
  fileInputRef,
  textareaRef,
  setSelectedConversationId,
}: UseReferenceImagesOptions): UseReferenceImagesResult {
  const [referenceImageFiles, setReferenceImageFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<StoredReferenceImage[]>([]);

  const resetFileInput = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [fileInputRef]);

  const append = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }

      try {
        const previews = await Promise.all(
          files.map(async (file) => ({
            name: file.name,
            type: file.type || "image/png",
            dataUrl: await readFileAsDataUrl(file),
          })),
        );

        setReferenceImageFiles((prev) => [...prev, ...files]);
        setReferenceImages((prev) => [...prev, ...previews]);
        resetFileInput();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "读取参考图失败");
      }
    },
    [resetFileInput],
  );

  const remove = useCallback(
    (index: number) => {
      setReferenceImageFiles((prev) => {
        const next = prev.filter((_, currentIndex) => currentIndex !== index);
        if (next.length === 0) {
          resetFileInput();
        }
        return next;
      });
      setReferenceImages((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
    },
    [resetFileInput],
  );

  const clear = useCallback(() => {
    setReferenceImageFiles([]);
    setReferenceImages([]);
    resetFileInput();
  }, [resetFileInput]);

  const continueEdit = useCallback(
    async (conversationId: string, image: StoredImage | StoredReferenceImage) => {
      try {
        const nextReference =
          "dataUrl" in image
            ? {
                referenceImage: image,
                file: dataUrlToFile(image.dataUrl, image.name, image.type),
              }
            : await buildReferenceImageFromStoredImage(image, `conversation-${conversationId}-${Date.now()}.png`);
        if (!nextReference) {
          return;
        }

        setSelectedConversationId(conversationId);

        setReferenceImages((prev) => [...prev, nextReference.referenceImage]);
        setReferenceImageFiles((prev) => [...prev, nextReference.file]);
        textareaRef.current?.focus();
        toast.success("已加入当前参考图，继续输入描述即可编辑");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "读取结果图失败");
      }
    },
    [setSelectedConversationId, textareaRef],
  );

  const reuseFromTurn = useCallback(
    (turnReferences: StoredReferenceImage[]) => {
      setReferenceImages(turnReferences);
      setReferenceImageFiles(
        turnReferences.map((image) => dataUrlToFile(image.dataUrl, image.name, image.type)),
      );
      resetFileInput();
    },
    [resetFileInput],
  );

  return {
    referenceImageFiles,
    referenceImages,
    append,
    remove,
    clear,
    continueEdit,
    reuseFromTurn,
  };
}
