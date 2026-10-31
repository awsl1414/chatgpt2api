"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type DeleteTagDialogProps = {
  /** 非空即打开：待删除的标签名 */
  tag: string | null;
  onClose: () => void;
  onConfirm: (tag: string) => Promise<void>;
};

/** 标签删除确认弹窗：删除会从所有图片上移除该标签 */
export function DeleteTagDialog({ tag, onClose, onConfirm }: DeleteTagDialogProps) {
  return (
    <Dialog open={tag !== null} onOpenChange={(next) => (!next ? onClose() : null)}>
      <DialogContent className="max-w-sm rounded-2xl">
        <DialogHeader>
          <DialogTitle>删除标签</DialogTitle>
        </DialogHeader>
        <DialogDescription className="text-sm text-stone-600">
          确定要删除标签 <span className="font-semibold">&quot;{tag}&quot;</span> 吗？将从所有图片中移除该标签。
        </DialogDescription>
        <DialogFooter>
          <Button variant="outline" className="rounded-xl" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="destructive"
            className="rounded-xl"
            onClick={() => {
              if (tag !== null) {
                void onConfirm(tag);
              }
              onClose();
            }}
          >
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
