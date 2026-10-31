"use client";

import { CalendarDays, Copy, Download, Maximize2, Trash2 } from "lucide-react";

import { ImageTagEditor } from "@/app/image-manager/components/image-tag-editor";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { ManagedImage } from "@/lib/api/images";
import { copyToClipboard } from "@/lib/clipboard";
import { IMAGE_MANAGER_CHECKBOX_CLASS, formatSize } from "@/lib/image-manager";

type ImageGridCardProps = {
  image: ManagedImage;
  allTags: string[];
  /** 是否处于勾选状态 */
  selected: boolean;
  /** 点击图片打开灯箱（索引由网格统一换算） */
  onOpen: () => void;
  onToggleSelected: (checked: boolean) => void;
  onDelete: () => void;
  onDownload: () => void;
  onAddTag: (rawTag: string) => boolean;
  onRemoveTag: (tag: string) => void;
  onPickTag: (tag: string) => void;
};

/** 图片网格中的单张卡片：缩略图、元信息、下载/复制/勾选与标签编辑 */
export function ImageGridCard({
  image,
  allTags,
  selected,
  onOpen,
  onToggleSelected,
  onDelete,
  onDownload,
  onAddTag,
  onRemoveTag,
  onPickTag,
}: ImageGridCardProps) {
  return (
    <div className="group border-r border-b border-stone-100 p-4 transition hover:bg-stone-50 dark:hover:bg-white/5">
      <div className="relative">
        <button
          type="button"
          className="relative block aspect-square w-full cursor-zoom-in overflow-hidden rounded-lg bg-stone-100 text-left"
          onClick={onOpen}
        >
          <img
            src={image.thumbnail_url || image.url}
            alt={image.name}
            className="h-full w-full object-cover transition group-hover:scale-[1.02]"
            onError={(event) => {
              if (event.currentTarget.src !== image.url) {
                event.currentTarget.src = image.url;
              }
            }}
          />
          <span className="absolute right-2 bottom-2 rounded-full bg-black/50 p-2 text-white opacity-100 transition sm:opacity-0 sm:group-hover:opacity-100">
            <Maximize2 className="size-4" />
          </span>
        </button>
        <button
          type="button"
          className="absolute top-2 right-2 z-10 inline-flex size-7 items-center justify-center rounded-full bg-black/50 text-white opacity-100 transition hover:bg-red-600 sm:opacity-0 sm:group-hover:opacity-100"
          title="删除图片"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>
      <div className="mt-3 space-y-2 text-xs text-stone-500">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1 font-medium text-stone-700">
            <CalendarDays className="size-3.5" />
            {image.created_at}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8 rounded-lg text-stone-400 hover:bg-stone-100 hover:text-stone-700"
              onClick={onDownload}
              title="下载图片"
            >
              <Download className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 rounded-lg text-stone-400 hover:bg-stone-100 hover:text-stone-700"
              onClick={() => void copyToClipboard(image.url, "图片地址已复制")}
            >
              <Copy className="size-4" />
            </Button>
            <Checkbox
              className={IMAGE_MANAGER_CHECKBOX_CLASS}
              checked={selected}
              onCheckedChange={(checked) => onToggleSelected(Boolean(checked))}
            />
          </div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span>{formatSize(image.size)}</span>
          <span>{image.width && image.height ? `${image.width} x ${image.height}` : "-"}</span>
        </div>
        <ImageTagEditor
          image={image}
          allTags={allTags}
          onAdd={onAddTag}
          onRemove={onRemoveTag}
          onPick={onPickTag}
        />
      </div>
    </div>
  );
}
