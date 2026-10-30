"use client";

import { History } from "lucide-react";

import { ImageSidebar } from "@/app/image/components/image-sidebar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useImageConversationsStore } from "@/store/image-conversations";

type HistoryDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateDraft: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void | Promise<void>;
  onRenameConversation: (id: string, title: string) => void | Promise<void>;
  onClearHistory: () => void | Promise<void>;
};

/** 移动端历史记录弹窗：会话列表数据直接订阅图片会话 store */
export function HistoryDialog({
  open,
  onOpenChange,
  onCreateDraft,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  onClearHistory,
}: HistoryDialogProps) {
  const conversations = useImageConversationsStore((state) => state.conversations);
  const isLoadingHistory = useImageConversationsStore((state) => state.isLoadingHistory);
  const selectedConversationId = useImageConversationsStore((state) => state.selectedConversationId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(82dvh,760px)] w-[92vw] max-w-[460px] flex-col overflow-hidden rounded-[32px] border-white/80 bg-white p-0 shadow-[0_32px_110px_-38px_rgba(15,23,42,0.45)] sm:rounded-[36px]">
        <DialogHeader className="px-6 pt-7 pb-4 sm:px-8">
          <DialogTitle className="flex items-center gap-2 text-xl font-bold tracking-tight">
            <History className="size-5" />
            历史记录
          </DialogTitle>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-8 sm:px-8">
          <ImageSidebar
            conversations={conversations}
            isLoadingHistory={isLoadingHistory}
            selectedConversationId={selectedConversationId}
            onCreateDraft={() => {
              onCreateDraft();
              onOpenChange(false);
            }}
            onClearHistory={onClearHistory}
            onSelectConversation={(id) => {
              onSelectConversation(id);
              onOpenChange(false);
            }}
            onDeleteConversation={onDeleteConversation}
            onRenameConversation={onRenameConversation}
            hideActionButtons
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
