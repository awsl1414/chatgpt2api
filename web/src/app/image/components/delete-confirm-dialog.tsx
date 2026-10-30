"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/** 删除确认目标：单个会话 / 提示词记录 / 生成结果 / 全部历史 */
export type ImageDeleteConfirmTarget =
  | { type: "one"; id: string }
  | { type: "prompt"; conversationId: string; turnId: string }
  | { type: "results"; conversationId: string; turnId: string }
  | { type: "all" };

type DeleteConfirmDialogProps = {
  target: ImageDeleteConfirmTarget;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
};

const confirmTitles: Record<ImageDeleteConfirmTarget["type"], string> = {
  all: "清空历史记录",
  prompt: "删除提示词记录",
  results: "删除生成结果",
  one: "删除对话",
};

const confirmDescriptions: Record<ImageDeleteConfirmTarget["type"], string> = {
  all: "确认删除全部图片历史记录吗？删除后无法恢复。",
  prompt: "确认删除这条提示词记录吗？对应生成结果会保留。",
  results: "确认删除这条生成结果吗？对应提示词记录会保留。",
  one: "确认删除这条图片对话吗？删除后无法恢复。",
};

/** 图片页统一的删除确认弹窗，按 target 类型展示对应文案 */
export function DeleteConfirmDialog({ target, onCancel, onConfirm }: DeleteConfirmDialogProps) {
  return (
    <Dialog open onOpenChange={(open) => (!open ? onCancel() : null)}>
      <DialogContent showCloseButton={false} className="rounded-2xl p-6">
        <DialogHeader className="gap-2">
          <DialogTitle>{confirmTitles[target.type]}</DialogTitle>
          <DialogDescription className="text-sm leading-6">{confirmDescriptions[target.type]}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            取消
          </Button>
          <Button className="bg-rose-600 text-white hover:bg-rose-700" onClick={() => void onConfirm()}>
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
