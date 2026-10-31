"use client";

import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type DeleteConfirmDialogProps = {
  /** 非空即打开；"filtered" 表示按当前日期筛选结果删除，"selected" 表示按勾选删除 */
  mode: "selected" | "filtered" | null;
  /** 将删除的图片数量 */
  count: number;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

/** 批量删除确认弹窗：覆盖「删除所选」与「删除匹配日期」两种模式 */
export function BatchDeleteDialog({ mode, count, isDeleting, onClose, onConfirm }: DeleteConfirmDialogProps) {
  return (
    <Dialog open={mode !== null} onOpenChange={(next) => (!next ? onClose() : null)}>
      <DialogContent showCloseButton={false} className="rounded-2xl p-6">
        <DialogHeader className="gap-2">
          <DialogTitle>{mode === "filtered" ? "删除匹配日期的图片" : "删除所选图片"}</DialogTitle>
        </DialogHeader>
        <DialogDescription className="text-sm text-stone-600">
          确认删除 {count} 张图片吗？删除后无法恢复。
        </DialogDescription>
        <DialogFooter>
          <Button variant="outline" className="rounded-xl" onClick={onClose} disabled={isDeleting}>
            取消
          </Button>
          <Button
            className="rounded-xl bg-rose-600 text-white hover:bg-rose-700"
            onClick={() => void onConfirm()}
            disabled={isDeleting || count === 0}
          >
            {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
