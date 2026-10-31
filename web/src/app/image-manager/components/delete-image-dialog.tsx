"use client";

import { LoaderCircle, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ManagedImage } from "@/lib/api/images";
import { formatSize } from "@/lib/image-manager";

type DeleteImageDialogProps = {
  open: boolean;
  target: ManagedImage | null;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

/** 单张图片删除确认弹窗：展示缩略图与元信息，确认后调用删除 */
export function DeleteImageDialog({ open, target, isDeleting, onClose, onConfirm }: DeleteImageDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onClose() : null)}>
      <DialogContent className="max-w-sm overflow-hidden rounded-2xl">
        <DialogHeader>
          <DialogTitle className="pr-8">确认删除</DialogTitle>
        </DialogHeader>
        <DialogDescription className="text-sm text-stone-600">
          确定要删除这张图片吗？此操作不可恢复。
        </DialogDescription>
        {target ? (
          <div className="flex items-center gap-3 overflow-hidden rounded-xl border border-stone-200 bg-stone-50 p-3">
            <img
              src={target.thumbnail_url || target.url}
              alt=""
              className="size-16 shrink-0 rounded-lg object-cover"
              onError={(event) => {
                if (event.currentTarget.src !== target.url) {
                  event.currentTarget.src = target.url;
                }
              }}
            />
            <div className="min-w-0 overflow-hidden text-xs text-stone-500">
              <div className="truncate font-medium text-stone-700">{target.name}</div>
              <div className="truncate">{target.created_at}</div>
              <div>{formatSize(target.size)}</div>
            </div>
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="rounded-xl">
            取消
          </Button>
          <Button variant="destructive" onClick={() => void onConfirm()} disabled={isDeleting} className="rounded-xl">
            {isDeleting ? <LoaderCircle className="mr-1 size-4 animate-spin" /> : <Trash2 className="mr-1 size-4" />}
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
