"use client";

import { ChevronLeft, ChevronRight, Download, ImageIcon, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";

import { ImageGridCard } from "@/app/image-manager/components/image-grid-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import type { ManagedImage } from "@/lib/api/images";
import { IMAGE_MANAGER_CHECKBOX_CLASS, imageKey } from "@/lib/image-manager";

type ImageGridProps = {
  /** 当前页图片 */
  pageItems: ManagedImage[];
  /** 全量图片（「全选结果」与灯箱索引都基于筛选结果，此处传筛选结果） */
  allItems: ManagedImage[];
  /** 未筛选的图片总数，用于展示「筛选自 N 张」 */
  totalCount: number;
  /** 按标签筛选后的结果总数 */
  filteredCount: number;
  /** 标签筛选是否生效（展示「筛选自 N 张」） */
  tagsFiltering: boolean;
  page: number;
  pageCount: number;
  selectedSet: Set<string>;
  selectedCount: number;
  allSelected: boolean;
  currentPageSelected: boolean;
  isLoading: boolean;
  isDownloading: boolean;
  isDeleting: boolean;
  allTags: string[];
  onTogglePaths: (paths: string[], checked: boolean) => void;
  onClearSelection: () => void;
  onRefresh: () => void;
  onBatchDownload: () => void;
  onRequestDeleteSelected: () => void;
  onPageChange: (page: number) => void;
  /** 打开灯箱，index 为图片在全量筛选结果中的下标 */
  onOpenLightbox: (index: number) => void;
  onDeleteImage: (item: ManagedImage) => void;
  onDownloadImage: (item: ManagedImage) => void;
  onAddTag: (item: ManagedImage, rawTag: string) => boolean;
  onRemoveTag: (item: ManagedImage, tag: string) => void;
  onPickTag: (item: ManagedImage, tag: string) => void;
};

/**
 * 图片网格卡片区：工具栏（统计/全选/批量操作）、卡片网格、分页与空态。
 * 纯展示组件，所有数据与动作由页面注入。
 */
export function ImageGrid({
  pageItems,
  allItems,
  totalCount,
  filteredCount,
  tagsFiltering,
  page,
  pageCount,
  selectedSet,
  selectedCount,
  allSelected,
  currentPageSelected,
  isLoading,
  isDownloading,
  isDeleting,
  allTags,
  onTogglePaths,
  onClearSelection,
  onRefresh,
  onBatchDownload,
  onRequestDeleteSelected,
  onPageChange,
  onOpenLightbox,
  onDeleteImage,
  onDownloadImage,
  onAddTag,
  onRemoveTag,
  onPickTag,
}: ImageGridProps) {
  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3 text-sm text-stone-600">
            <ImageIcon className="size-4" />
            共 {filteredCount} 张
            {tagsFiltering ? <span className="text-stone-400">（筛选自 {totalCount} 张）</span> : null}
            <label className="flex items-center gap-2">
              <Checkbox
                className={IMAGE_MANAGER_CHECKBOX_CLASS}
                checked={currentPageSelected}
                onCheckedChange={(checked) => onTogglePaths(pageItems.map(imageKey), Boolean(checked))}
              />
              本页全选
            </label>
            <label className="flex items-center gap-2">
              <Checkbox
                className={IMAGE_MANAGER_CHECKBOX_CLASS}
                checked={allSelected}
                onCheckedChange={(checked) => onTogglePaths(allItems.map(imageKey), Boolean(checked))}
              />
              全选结果
            </label>
            {selectedCount > 0 ? <span>已选 {selectedCount} 张</span> : null}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" className="h-8 rounded-lg px-3 text-stone-500" onClick={onRefresh} disabled={isLoading}>
              <RefreshCw className={`size-4 ${isLoading ? "animate-spin" : ""}`} />
              刷新
            </Button>
            <button
              type="button"
              className="text-sm text-stone-500 hover:text-stone-900 disabled:text-stone-300"
              onClick={onClearSelection}
              disabled={selectedCount === 0 || isDeleting}
            >
              取消选择
            </button>
            <Button
              variant="outline"
              className="h-8 rounded-lg border-stone-200 bg-white px-3 text-stone-600 hover:bg-stone-50"
              onClick={onBatchDownload}
              disabled={selectedCount === 0 || isDownloading || isDeleting}
            >
              {isDownloading ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
              下载所选
            </Button>
            <Button
              variant="outline"
              className="h-8 rounded-lg border-rose-200 bg-white px-3 text-rose-600 hover:bg-rose-50"
              onClick={onRequestDeleteSelected}
              disabled={selectedCount === 0 || isDeleting}
            >
              <Trash2 className="size-4" />
              删除所选
            </Button>
          </div>
        </div>
        <div className="grid gap-0 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {pageItems.map((item) => (
            <ImageGridCard
              key={item.rel}
              image={item}
              allTags={allTags}
              selected={selectedSet.has(imageKey(item))}
              onOpen={() => onOpenLightbox(allItems.findIndex((row) => imageKey(row) === imageKey(item)))}
              onToggleSelected={(checked) => onTogglePaths([imageKey(item)], checked)}
              onDelete={() => onDeleteImage(item)}
              onDownload={() => onDownloadImage(item)}
              onAddTag={(rawTag) => onAddTag(item, rawTag)}
              onRemoveTag={(tag) => onRemoveTag(item, tag)}
              onPickTag={(tag) => onPickTag(item, tag)}
            />
          ))}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-stone-100 px-4 py-3 text-sm text-stone-500">
          <span>
            第 {page} / {pageCount} 页，共 {filteredCount} 张
          </span>
          <Button
            variant="outline"
            size="icon"
            className="size-9 rounded-lg border-stone-200 bg-white"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-9 rounded-lg border-stone-200 bg-white"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
        {!isLoading && filteredCount === 0 ? (
          <div className="px-6 py-14 text-center text-sm text-stone-500">没有找到图片</div>
        ) : null}
      </CardContent>
    </Card>
  );
}
