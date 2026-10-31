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
import { Input } from "@/components/ui/input";

type DeleteByDateDialogProps = {
  open: boolean;
  /** 删除该日期之前的图片（yyyy-MM-dd） */
  startDate: string;
  isDeleting: boolean;
  onStartDateChange: (value: string) => void;
  onClose: () => void;
  onConfirm: (startDate: string) => Promise<void>;
};

/** 按日期删除弹窗：删除指定日期之前的所有图片 */
export function DeleteByDateDialog({
  open,
  startDate,
  isDeleting,
  onStartDateChange,
  onClose,
  onConfirm,
}: DeleteByDateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onClose() : null)}>
      <DialogContent className="rounded-2xl sm:max-w-md">
        <DialogHeader>
          <DialogTitle>按日期删除图片</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <label className="shrink-0 text-sm text-stone-600">删除</label>
            <Input
              className="h-9 text-sm"
              type="date"
              value={startDate}
              onChange={(event) => onStartDateChange(event.target.value)}
            />
            <span className="text-sm text-stone-400">之前的图片</span>
          </div>
          <DialogDescription className="text-xs text-stone-500">
            此操作不可撤销，将永久删除所有匹配日期的图片及其缩略图。
          </DialogDescription>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={!startDate || isDeleting}
            onClick={() => void onConfirm(startDate)}
          >
            {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
