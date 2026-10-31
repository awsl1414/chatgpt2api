"use client";

import { useCallback, useEffect, useState } from "react";
import { LoaderCircle, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { BatchDeleteDialog } from "@/app/image-manager/components/batch-delete-dialog";
import { DeleteByDateDialog } from "@/app/image-manager/components/delete-by-date-dialog";
import { DeleteImageDialog } from "@/app/image-manager/components/delete-image-dialog";
import { DeleteTagDialog } from "@/app/image-manager/components/delete-tag-dialog";
import { ImageGrid } from "@/app/image-manager/components/image-grid";
import { StorageStatsPanel } from "@/app/image-manager/components/storage-stats-panel";
import { TagFilterBar } from "@/app/image-manager/components/tag-filter-bar";
import { AuthGuard } from "@/components/auth-guard";
import { DateRangeFilter } from "@/components/date-range-filter";
import { ImageLightbox } from "@/components/image-lightbox";
import { Button } from "@/components/ui/button";
import { useImageStorage } from "@/app/image-manager/hooks/use-image-storage";
import { useImageTags } from "@/app/image-manager/hooks/use-image-tags";
import { useManagedImages } from "@/app/image-manager/hooks/use-managed-images";
import { usePagination } from "@/hooks/use-pagination";
import { actionError } from "@/lib/action-result";
import {
  deleteManagedImages,
  downloadImages,
  downloadSingleImage,
  type ManagedImage,
} from "@/lib/api/images";
import { IMAGE_MANAGER_PAGE_SIZE, formatSize, imageKey } from "@/lib/image-manager";
import { filterImagesByTags } from "@/lib/image-tags";

type DeleteMode = "selected" | "filtered";

/**
 * 图片管理页内容：按日期/标签筛选图片，批量下载与删除，维护标签与存储统计。
 * 数据与动作下沉到 hooks 与 components，本组件只负责状态编排与弹窗开关。
 */
function ImageManagerContent() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [deleteMode, setDeleteMode] = useState<DeleteMode | null>(null);
  const [deleteByDateOpen, setDeleteByDateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ManagedImage | null>(null);
  const [dialogVisible, setDialogVisible] = useState(false);
  const [deleteStartDate, setDeleteStartDate] = useState("");
  const [tagDeleteTarget, setTagDeleteTarget] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const images = useManagedImages({ startDate, endDate });
  const { loadImages } = images;
  const storage = useImageStorage();
  const tags = useImageTags({
    onTagsApplied: images.updateItemTags,
    onTagRemoved: images.removeTagFromItems,
  });

  const filteredItems = filterImagesByTags(images.items, tags.selectedTags);
  const { page, pageCount, pageItems, setPage, resetPage } = usePagination(
    filteredItems,
    IMAGE_MANAGER_PAGE_SIZE,
  );

  const selectedSet = images.selectedSet;
  const currentPageSelected = pageItems.length > 0 && pageItems.every((item) => selectedSet.has(imageKey(item)));
  const allSelected = filteredItems.length > 0 && filteredItems.every((item) => selectedSet.has(imageKey(item)));
  const batchDeleteCount = deleteMode === "filtered" ? images.items.length : images.selectedPaths.length;

  const lightboxImages = filteredItems.map((item) => ({
    id: item.name,
    src: item.url,
    sizeLabel: formatSize(item.size),
    dimensions: item.width && item.height ? `${item.width} x ${item.height}` : undefined,
  }));

  const reload = useCallback(async () => {
    await loadImages();
    resetPage();
  }, [loadImages, resetPage]);

  // 日期范围变化即重新拉取（首次挂载同样走这里）
  useEffect(() => {
    void reload();
  }, [reload]);

  const closeDialog = useCallback(() => {
    setDialogVisible(false);
    setTimeout(() => setDeleteTarget(null), 200);
  }, []);

  const handleDelete = async () => {
    if (!deleteTarget) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteManagedImages({ paths: [deleteTarget.rel] });
      images.removeItem(deleteTarget.rel);
      toast.success("图片已删除");
    } catch (error) {
      toast.error(actionError(error, "删除失败"));
    } finally {
      setIsDeleting(false);
      closeDialog();
    }
  };

  const handleBatchDownload = async () => {
    const paths = images.selectedPaths;
    if (paths.length === 0) {
      return;
    }
    setIsDownloading(true);
    try {
      await downloadImages(paths);
      toast.success(`已下载 ${paths.length} 张图片`);
    } catch (error) {
      toast.error(actionError(error, "下载失败"));
    } finally {
      setIsDownloading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (!deleteMode || batchDeleteCount === 0) {
      return;
    }
    setIsDeleting(true);
    try {
      const data = await deleteManagedImages(
        deleteMode === "filtered"
          ? { start_date: startDate, end_date: endDate, all_matching: true }
          : { paths: images.selectedPaths },
      );
      toast.success(`已删除 ${data.removed} 张图片`);
      setDeleteMode(null);
      images.clearSelection();
      await reload();
    } catch (error) {
      toast.error(actionError(error, "删除图片失败"));
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteByDate = async (date: string) => {
    setIsDeleting(true);
    try {
      const result = await deleteManagedImages({ end_date: date, all_matching: true });
      toast.success(`已删除 ${result.removed} 张图片`);
      setDeleteByDateOpen(false);
      await Promise.all([storage.reload(), reload()]);
    } catch {
      toast.error("删除失败");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteTag = async (tag: string) => {
    await tags.deleteTag(tag);
  };

  const clearFilters = () => {
    setStartDate("");
    setEndDate("");
    tags.clearFilterTags();
  };

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Images</div>
          <h1 className="text-2xl font-semibold tracking-tight">图片管理</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <DateRangeFilter
            startDate={startDate}
            endDate={endDate}
            onChange={(start, end) => {
              setStartDate(start);
              setEndDate(end);
            }}
          />
          <Button
            variant="outline"
            onClick={clearFilters}
            className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
          >
            清除筛选条件
          </Button>
          <Button
            onClick={() => void reload()}
            disabled={images.isLoading}
            className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
          >
            {images.isLoading ? <LoaderCircle className="size-4 animate-spin" /> : <Search className="size-4" />}
            查询
          </Button>
          <Button
            variant="outline"
            onClick={() => setDeleteMode("filtered")}
            disabled={isDeleting || images.items.length === 0 || (!startDate && !endDate)}
            className="h-10 rounded-xl border-rose-200 bg-white px-4 text-rose-600 hover:bg-rose-50"
          >
            <Trash2 className="size-4" />
            删除匹配日期
          </Button>
        </div>
      </div>

      <TagFilterBar
        allTags={tags.allTags}
        selectedTags={tags.selectedTags}
        onToggle={(tag) => {
          tags.toggleFilterTag(tag);
          resetPage();
        }}
        onClear={() => {
          tags.clearFilterTags();
          resetPage();
        }}
        onRequestDelete={setTagDeleteTarget}
      />

      <StorageStatsPanel
        storage={storage.storage}
        isLoading={storage.isLoading}
        onRefresh={storage.reload}
        onCompress={storage.compress}
        onCleanupToTarget={storage.cleanupToTarget}
        onRequestDeleteByDate={() => setDeleteByDateOpen(true)}
      />

      <ImageGrid
        pageItems={pageItems}
        allItems={filteredItems}
        totalCount={images.items.length}
        filteredCount={filteredItems.length}
        tagsFiltering={tags.selectedTags.length > 0}
        page={page}
        pageCount={pageCount}
        selectedSet={selectedSet}
        selectedCount={images.selectedPaths.length}
        allSelected={allSelected}
        currentPageSelected={currentPageSelected}
        isLoading={images.isLoading}
        isDownloading={isDownloading}
        isDeleting={isDeleting}
        allTags={tags.allTags}
        onTogglePaths={images.togglePaths}
        onClearSelection={images.clearSelection}
        onRefresh={() => void reload()}
        onBatchDownload={() => void handleBatchDownload()}
        onRequestDeleteSelected={() => setDeleteMode("selected")}
        onPageChange={setPage}
        onOpenLightbox={(index) => {
          setLightboxIndex(index);
          setLightboxOpen(true);
        }}
        onDeleteImage={(item) => {
          setDeleteTarget(item);
          setDialogVisible(true);
        }}
        onDownloadImage={(item) => void downloadSingleImage(item.rel)}
        onAddTag={(item, rawTag) => tags.addTag(item, rawTag)}
        onRemoveTag={(item, tag) => tags.removeTag(item, tag)}
        onPickTag={(item, tag) => void tags.applyTags(item, [...(item.tags ?? []), tag])}
      />

      <ImageLightbox
        images={lightboxImages}
        currentIndex={lightboxIndex}
        open={lightboxOpen}
        onOpenChange={setLightboxOpen}
        onIndexChange={setLightboxIndex}
      />

      <DeleteImageDialog
        open={dialogVisible}
        target={deleteTarget}
        isDeleting={isDeleting}
        onClose={closeDialog}
        onConfirm={handleDelete}
      />

      <BatchDeleteDialog
        mode={deleteMode}
        count={batchDeleteCount}
        isDeleting={isDeleting}
        onClose={() => setDeleteMode(null)}
        onConfirm={handleBatchDelete}
      />

      <DeleteByDateDialog
        open={deleteByDateOpen}
        startDate={deleteStartDate}
        isDeleting={isDeleting}
        onStartDateChange={setDeleteStartDate}
        onClose={() => setDeleteByDateOpen(false)}
        onConfirm={handleDeleteByDate}
      />

      <DeleteTagDialog
        tag={tagDeleteTarget}
        onClose={() => setTagDeleteTarget(null)}
        onConfirm={handleDeleteTag}
      />
    </section>
  );
}

export default function ImageManagerPage() {
  return (
    <AuthGuard roles={["admin"]}>
      {() => <ImageManagerContent />}
    </AuthGuard>
  );
}
