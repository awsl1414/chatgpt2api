"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, History, LoaderCircle, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { DeleteConfirmDialog, type ImageDeleteConfirmTarget } from "@/app/image/components/delete-confirm-dialog";
import { HistoryDialog } from "@/app/image/components/history-dialog";
import { ImageComposer } from "@/app/image/components/image-composer";
import { ImageResults, type ImageLightboxItem } from "@/app/image/components/image-results";
import { ImageSidebar } from "@/app/image/components/image-sidebar";
import { ImageLightbox } from "@/components/image-lightbox";
import { Button } from "@/components/ui/button";
import { usePersistedComposerOptions } from "@/hooks/use-persisted-composer-options";
import { useReferenceImages } from "@/hooks/use-reference-images";
import { useScrollRestore } from "@/hooks/use-scroll-restore";
import { fetchAccounts } from "@/lib/api/accounts";
import { resumeImagePoll } from "@/lib/api/image-tasks";
import { ACTIVE_CONVERSATION_STORAGE_KEY } from "@/lib/image-storage-keys";
import { abortAllConversationQueues, isConversationQueueActive, runConversationQueue } from "@/lib/image-task-poller";
import {
  buildDeletedTurnPartConversation,
  buildQueuedTurn,
  buildRegeneratedConversation,
  buildRetryImageConversation,
  buildSubmittedConversation,
  deriveTurnStatus,
  recoverConversationHistory,
} from "@/lib/image-task-state";
import { formatAvailableQuota, parseImageSize, pickFallbackConversationId } from "@/lib/image-utils";
import { useAuthGuard } from "@/lib/use-auth-guard";
import { useConfigStore } from "@/app/settings/store/config";
import {
  getImageConversationStats,
  listImageConversations,
  useImageConversationsStore,
  type ImageConversationMode,
} from "@/store/image-conversations";

function ImagePageContent({ isAdmin }: { isAdmin: boolean }) {
  const didLoadQuotaRef = useRef(false);
  const loadCancelledRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const config = useConfigStore((state) => state.config);
  const imageTimeoutRetrySecs = Number(config?.image_timeout_retry_secs || 30);

  const conversations = useImageConversationsStore((state) => state.conversations);
  const isLoadingHistory = useImageConversationsStore((state) => state.isLoadingHistory);
  const selectedConversationId = useImageConversationsStore((state) => state.selectedConversationId);
  const setConversations = useImageConversationsStore((state) => state.setConversations);
  const setLoadingHistory = useImageConversationsStore((state) => state.setLoadingHistory);
  const setSelectedConversationId = useImageConversationsStore((state) => state.setSelectedConversationId);
  const upsertConversation = useImageConversationsStore((state) => state.upsertConversation);
  const updateConversation = useImageConversationsStore((state) => state.updateConversation);
  const deleteConversationAction = useImageConversationsStore((state) => state.deleteConversation);
  const clearConversationsAction = useImageConversationsStore((state) => state.clearConversations);
  const renameConversationAction = useImageConversationsStore((state) => state.renameConversation);

  const {
    imageCount,
    imageRatio,
    imageTier,
    imageWidth,
    imageHeight,
    imageQuality,
    imageModel,
    imageModels,
    parsedCount,
    setImageCount,
    setImageRatio,
    setImageTier,
    setImageWidth,
    setImageHeight,
    setImageQuality,
    setImageModel,
    handleImageModelChange,
    loadPersistedOptions,
  } = usePersistedComposerOptions();

  const [imagePrompt, setImagePrompt] = useState("");
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [availableQuota, setAvailableQuota] = useState("加载中...");
  const [lightboxImages, setLightboxImages] = useState<ImageLightboxItem[]>([]);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  const [deleteConfirm, setDeleteConfirm] = useState<ImageDeleteConfirmTarget | null>(null);

  const reference = useReferenceImages({ fileInputRef, textareaRef, setSelectedConversationId });

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  );
  const activeTaskCount = useMemo(
    () =>
      conversations.reduce((sum, conversation) => {
        const stats = getImageConversationStats(conversation);
        return sum + stats.queued + stats.running;
      }, 0),
    [conversations],
  );

  const { resultsViewportRef, scrollToLatestBtnRef, handleResultsScroll, scrollResultsToLatest, stickToBottom } =
    useScrollRestore(selectedConversation);

  const loadHistory = useCallback(async () => {
    loadPersistedOptions();
    try {
      const items = await listImageConversations();
      const normalizedItems = await recoverConversationHistory(items);
      if (loadCancelledRef.current) {
        return;
      }

      setConversations(normalizedItems);
      const storedConversationId =
        typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY) : null;
      const nextSelectedConversationId =
        (storedConversationId && normalizedItems.some((conversation) => conversation.id === storedConversationId)
          ? storedConversationId
          : null) ?? pickFallbackConversationId(normalizedItems);
      setSelectedConversationId(nextSelectedConversationId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "读取会话记录失败");
    } finally {
      if (!loadCancelledRef.current) {
        setLoadingHistory(false);
      }
    }
  }, [loadPersistedOptions, setConversations, setLoadingHistory, setSelectedConversationId]);

  // Handle bfcache (back/forward cache) — re-sync task status on page restore
  useEffect(() => {
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        void loadHistory();
      }
    };
    window.addEventListener("pageshow", handlePageShow);
    return () => window.removeEventListener("pageshow", handlePageShow);
  }, [loadHistory]);

  useEffect(() => {
    loadCancelledRef.current = false;
    void loadHistory();
    return () => {
      loadCancelledRef.current = true;
      // 组件卸载时终止全部会话轮询（修复离开页面后 while(true) 继续轮询的泄漏）
      abortAllConversationQueues();
    };
  }, [loadHistory]);

  const loadQuota = useCallback(async () => {
    if (!isAdmin) {
      setAvailableQuota("--");
      return;
    }
    try {
      const data = await fetchAccounts();
      setAvailableQuota(formatAvailableQuota(data.items));
    } catch {
      setAvailableQuota((prev) => (prev === "加载中..." ? "--" : prev));
    }
  }, [isAdmin]);

  useEffect(() => {
    if (didLoadQuotaRef.current) {
      return;
    }
    didLoadQuotaRef.current = true;

    const handleFocus = () => {
      void loadQuota();
    };

    void loadQuota();
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
    };
  }, [isAdmin, loadQuota]);

  // 选中会话持久化到 localStorage，刷新后恢复
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (selectedConversationId) {
      window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, selectedConversationId);
    } else {
      window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
    }
  }, [selectedConversationId]);

  // 选中的会话被删除后回退到兜底会话
  useEffect(() => {
    if (selectedConversationId && !conversations.some((conversation) => conversation.id === selectedConversationId)) {
      setSelectedConversationId(pickFallbackConversationId(conversations));
    }
  }, [conversations, selectedConversationId, setSelectedConversationId]);

  // 有待处理任务的会话自动启动队列轮询（同一会话由 runConversationQueue 内部去重）
  useEffect(() => {
    for (const conversation of conversations) {
      if (isConversationQueueActive(conversation.id)) {
        continue;
      }
      if (
        conversation.turns.some(
          (turn) =>
            !turn.resultsDeleted &&
            (turn.status === "queued" || turn.status === "generating") &&
            turn.images.some((image) => image.status === "loading"),
        )
      ) {
        runConversationQueue(conversation.id, { onQueueDrained: () => void loadQuota() });
      }
    }
  }, [conversations, loadQuota]);

  const resetComposer = useCallback(() => {
    setImagePrompt("");
    reference.clear();
  }, [reference]);

  const handleCreateDraft = () => {
    stickToBottom();
    setSelectedConversationId(null);
    resetComposer();
    textareaRef.current?.focus();
  };

  const handleDeleteConversation = async (id: string) => {
    const wasSelected = useImageConversationsStore.getState().selectedConversationId === id;
    try {
      await deleteConversationAction(id);
      if (wasSelected) {
        resetComposer();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除会话失败");
      setConversations(await listImageConversations());
    }
  };

  const handleDeleteTurnPart = async (conversationId: string, turnId: string, part: "prompt" | "results") => {
    const conversation = useImageConversationsStore.getState().conversations.find((item) => item.id === conversationId);
    if (!conversation) {
      return;
    }
    const nextConversation = buildDeletedTurnPartConversation(conversation, turnId, part);
    if (!nextConversation) {
      // 提示词与结果都被删除，整个会话一并删除
      await handleDeleteConversation(conversationId);
      return;
    }
    await upsertConversation(nextConversation);
  };

  const handleClearHistory = async () => {
    try {
      await clearConversationsAction();
      resetComposer();
      toast.success("已清空历史记录");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "清空历史记录失败");
    }
  };

  const handleRenameConversation = async (id: string, title: string) => {
    try {
      await renameConversationAction(id, title);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重命名失败");
    }
  };

  const openDeleteConversationConfirm = (id: string) => {
    setIsHistoryOpen(false);
    setDeleteConfirm({ type: "one", id });
  };

  const openDeletePromptConfirm = (conversationId: string, turnId: string) => {
    setDeleteConfirm({ type: "prompt", conversationId, turnId });
  };

  const openDeleteResultsConfirm = (conversationId: string, turnId: string) => {
    setDeleteConfirm({ type: "results", conversationId, turnId });
  };

  const openClearHistoryConfirm = () => {
    setIsHistoryOpen(false);
    setDeleteConfirm({ type: "all" });
  };

  const handleConfirmDelete = async () => {
    const target = deleteConfirm;
    setDeleteConfirm(null);
    if (!target) {
      return;
    }
    if (target.type === "all") {
      await handleClearHistory();
      return;
    }
    if (target.type === "prompt" || target.type === "results") {
      await handleDeleteTurnPart(target.conversationId, target.turnId, target.type);
      return;
    }
    await handleDeleteConversation(target.id);
  };

  const handleReuseTurnConfig = useCallback(
    async (conversationId: string, turnId: string) => {
      const conversation = useImageConversationsStore
        .getState()
        .conversations.find((item) => item.id === conversationId);
      const turn = conversation?.turns.find((item) => item.id === turnId);
      if (!turn || !turn.prompt.trim()) {
        return;
      }

      setSelectedConversationId(conversationId);
      setImagePrompt(turn.prompt);
      setImageCount(String(Math.max(1, turn.count || turn.images.length || 1)));
      setImageRatio(turn.ratio);
      setImageTier(turn.tier);
      const parsedSize = parseImageSize(turn.size);
      setImageWidth(parsedSize.width);
      setImageHeight(parsedSize.height);
      setImageQuality(turn.quality);
      setImageModel(turn.model);
      reference.reuseFromTurn(turn.referenceImages);
      textareaRef.current?.focus();
      toast.success("已复用这条提示词配置");
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reference 各方法与 composer setter 均为稳定引用
    [setSelectedConversationId],
  );

  const openLightbox = useCallback((images: ImageLightboxItem[], index: number) => {
    if (images.length === 0) {
      return;
    }
    setLightboxImages(images);
    setLightboxIndex(Math.max(0, Math.min(index, images.length - 1)));
    setLightboxOpen(true);
  }, []);

  const startQueue = useCallback(
    (conversationId: string) => {
      runConversationQueue(conversationId, { onQueueDrained: () => void loadQuota() });
    },
    [loadQuota],
  );

  const handleRegenerateTurn = useCallback(
    async (conversationId: string, turnId: string) => {
      const conversation = useImageConversationsStore
        .getState()
        .conversations.find((item) => item.id === conversationId);
      if (!conversation) {
        return;
      }
      const built = buildRegeneratedConversation(conversation, turnId);
      if (!built) {
        return;
      }

      setSelectedConversationId(conversationId);
      await upsertConversation(built.conversation);
      startQueue(conversationId);
      toast.success("已加入重新生成队列");
    },
    [setSelectedConversationId, startQueue, upsertConversation],
  );

  const handleRetryImage = useCallback(
    async (conversationId: string, turnId: string, imageId: string) => {
      const conversation = useImageConversationsStore
        .getState()
        .conversations.find((item) => item.id === conversationId);
      if (!conversation) {
        return;
      }
      const nextConversation = buildRetryImageConversation(conversation, turnId, imageId);
      if (!nextConversation) {
        return;
      }

      setSelectedConversationId(conversationId);
      await upsertConversation(nextConversation);
      startQueue(conversationId);
    },
    [setSelectedConversationId, startQueue, upsertConversation],
  );

  // 超时任务「继续等待」：向后端申请延长轮询窗口，并把对应图片重置为 loading
  const handleTimeoutRetryContinue = useCallback(
    async (taskId: string) => {
      const conversationId = useImageConversationsStore
        .getState()
        .conversations.find((conversation) =>
          conversation.turns.some((turn) => turn.images.some((image) => image.taskId === taskId)),
        )?.id;
      if (!conversationId) {
        return;
      }
      try {
        await resumeImagePoll(taskId, imageTimeoutRetrySecs);
        void updateConversation(conversationId, (current) => ({
          ...current,
          updatedAt: new Date().toISOString(),
          turns: current.turns.map((turn) => {
            const hasLoading = turn.images.some((image) => image.taskId === taskId);
            if (!hasLoading) return turn;
            return {
              ...turn,
              status: "generating" as const,
              error: undefined,
              images: turn.images.map((image) =>
                image.taskId === taskId
                  ? {
                      ...image,
                      status: "loading" as const,
                      error: undefined,
                      taskStatus: "running" as const,
                      startTime: image.startTime || Date.now(),
                    }
                  : image,
              ),
            };
          }),
        }));
        toast.info(`已继续等待 ${imageTimeoutRetrySecs} 秒`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "续轮询失败");
      }
    },
    [imageTimeoutRetrySecs, updateConversation],
  );

  const handleDismissErrors = useCallback(
    async (conversationId: string, turnId: string) => {
      await updateConversation(conversationId, (current) => ({
        ...current,
        updatedAt: new Date().toISOString(),
        turns: current.turns.map((turn) => {
          if (turn.id !== turnId) return turn;
          const successImages = turn.images.filter((image) => image.status !== "error");
          const derived = deriveTurnStatus({ ...turn, images: successImages });
          return {
            ...turn,
            ...derived,
            count: successImages.length,
            images: successImages,
          };
        }),
      }));
    },
    [updateConversation],
  );

  const handleSubmit = async () => {
    const prompt = imagePrompt.trim();
    if (!prompt) {
      toast.error("请输入提示词");
      return;
    }

    const effectiveImageMode: ImageConversationMode = reference.referenceImageFiles.length > 0 ? "edit" : "generate";
    const targetConversation = selectedConversationId
      ? useImageConversationsStore
          .getState()
          .conversations.find((conversation) => conversation.id === selectedConversationId) ?? null
      : null;
    const turn = buildQueuedTurn({
      prompt,
      model: imageModel,
      mode: effectiveImageMode,
      referenceImages: reference.referenceImages,
      count: parsedCount,
      size: `${imageWidth || 1024}x${imageHeight || 1024}`,
      ratio: imageRatio,
      tier: imageTier,
      quality: imageQuality,
    });
    const baseConversation = buildSubmittedConversation(targetConversation, turn);

    stickToBottom();
    setSelectedConversationId(baseConversation.id);
    setImagePrompt("");
    reference.clear();

    await upsertConversation(baseConversation);
    startQueue(baseConversation.id);

    const targetStats = getImageConversationStats(baseConversation);
    if (targetStats.running > 0 || targetStats.queued > 1) {
      toast.success("已加入当前对话队列");
    } else if (!targetConversation) {
      toast.success("已创建新对话并开始处理");
    } else {
      toast.success("已发送到当前对话");
    }
  };

  return (
    <>
      <section className="mx-auto grid h-[calc(100dvh-6.5rem)] min-h-0 w-full max-w-[1380px] grid-cols-1 gap-2 overflow-hidden px-0 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] sm:h-[calc(100dvh-5.25rem)] sm:gap-3 sm:px-3 sm:pb-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <div className="hidden h-full min-h-0 border-r border-stone-200/70 pr-3 lg:block">
          <ImageSidebar
            conversations={conversations}
            isLoadingHistory={isLoadingHistory}
            selectedConversationId={selectedConversationId}
            onCreateDraft={handleCreateDraft}
            onClearHistory={openClearHistoryConfirm}
            onSelectConversation={setSelectedConversationId}
            onDeleteConversation={openDeleteConversationConfirm}
            onRenameConversation={handleRenameConversation}
          />
        </div>

        <HistoryDialog
          open={isHistoryOpen}
          onOpenChange={setIsHistoryOpen}
          onCreateDraft={handleCreateDraft}
          onSelectConversation={setSelectedConversationId}
          onDeleteConversation={openDeleteConversationConfirm}
          onRenameConversation={handleRenameConversation}
          onClearHistory={openClearHistoryConfirm}
        />

        <div className="flex min-h-0 flex-col gap-2 sm:gap-4">
          <div className="flex items-center justify-between gap-2 px-1 lg:hidden">
            <Button
              variant="outline"
              className="h-10 flex-1 rounded-2xl border-stone-200 bg-white/90 text-stone-700 shadow-sm"
              onClick={() => setIsHistoryOpen(true)}
            >
              <History className="mr-2 size-4" />
              历史记录 ({conversations.length})
            </Button>
            <Button className="h-10 rounded-2xl bg-stone-950 text-white shadow-sm" onClick={handleCreateDraft}>
              <Plus className="size-4" />
              新建
            </Button>
            <Button
              variant="outline"
              className="h-10 rounded-2xl border-stone-200 bg-white/85 px-3 text-stone-600 shadow-sm"
              onClick={openClearHistoryConfirm}
              disabled={conversations.length === 0}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>

          <div className="relative min-h-0 flex-1">
            <div
              ref={resultsViewportRef}
              onScroll={handleResultsScroll}
              className="hide-scrollbar h-full overscroll-contain overflow-y-auto px-1 py-2 sm:px-4 sm:py-4"
              style={{ contain: "layout style paint" }}
            >
              <ImageResults
                selectedConversation={selectedConversation}
                onOpenLightbox={openLightbox}
                onContinueEdit={reference.continueEdit}
                onDeletePrompt={openDeletePromptConfirm}
                onDeleteResults={openDeleteResultsConfirm}
                onReuseTurnConfig={handleReuseTurnConfig}
                onRegenerateTurn={handleRegenerateTurn}
                onRetryImage={handleRetryImage}
                onTimeoutRetryContinue={handleTimeoutRetryContinue}
                onDismissErrors={handleDismissErrors}
              />
            </div>

            <button
              ref={scrollToLatestBtnRef}
              type="button"
              aria-label="滚动到最新消息"
              title="滚动到最新消息"
              onClick={() => scrollResultsToLatest("smooth")}
              className="absolute bottom-4 left-1/2 z-20 inline-flex size-11 -translate-x-1/2 items-center justify-center rounded-full border border-stone-200 bg-white/95 text-stone-700 shadow-lg shadow-stone-200/60 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 dark:border-white/10 dark:bg-stone-800/95 dark:text-stone-100 dark:shadow-black/40 dark:hover:bg-stone-700"
              style={{ display: "none" }}
            >
              <ArrowDown className="size-5" />
            </button>
          </div>

          <ImageComposer
            prompt={imagePrompt}
            imageCount={imageCount}
            imageRatio={imageRatio}
            imageTier={imageTier}
            imageWidth={imageWidth}
            imageHeight={imageHeight}
            imageQuality={imageQuality}
            imageModel={imageModel}
            imageModels={imageModels}
            availableQuota={availableQuota}
            activeTaskCount={activeTaskCount}
            referenceImages={reference.referenceImages}
            textareaRef={textareaRef}
            fileInputRef={fileInputRef}
            onPromptChange={setImagePrompt}
            onImageCountChange={setImageCount}
            onImageRatioChange={setImageRatio}
            onImageTierChange={setImageTier}
            onImageWidthChange={setImageWidth}
            onImageHeightChange={setImageHeight}
            onImageQualityChange={setImageQuality}
            onImageModelChange={handleImageModelChange}
            onSubmit={handleSubmit}
            onPickReferenceImage={() => fileInputRef.current?.click()}
            onReferenceImageChange={reference.append}
            onRemoveReferenceImage={reference.remove}
          />
        </div>
      </section>

      <ImageLightbox
        images={lightboxImages}
        currentIndex={lightboxIndex}
        open={lightboxOpen}
        onOpenChange={setLightboxOpen}
        onIndexChange={setLightboxIndex}
      />

      {deleteConfirm ? (
        <DeleteConfirmDialog
          target={deleteConfirm}
          onCancel={() => setDeleteConfirm(null)}
          onConfirm={handleConfirmDelete}
        />
      ) : null}
    </>
  );
}

export default function ImagePage() {
  const { isCheckingAuth, session } = useAuthGuard();

  if (isCheckingAuth || !session) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <ImagePageContent isAdmin={session.role === "admin"} />;
}
