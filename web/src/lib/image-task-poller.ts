/**
 * 生图会话队列轮询器（审计 §5 / F-高5）：runConversationQueue 移出组件，
 * 提交 + 轮询状态机在模块层运行，读取与写入统一走 useImageConversationsStore。
 *
 * 取消通道：每个会话队列持有一个 AbortController，组件卸载时调用
 * abortAllConversationQueues() 即刻终止所有 while 轮询（含 sleep 等待），
 * 终止路径不修改会话状态——残留 loading 图片会在下次加载时由
 * recoverConversationHistory / syncConversationImageTasks 按后端任务状态恢复。
 */

import { toast } from "sonner";

import { createImageEditTask, createImageGenerationTask, fetchImageTasks, type ImageTask } from "@/lib/api";
import { dataUrlToFile } from "@/lib/image-reference";
import { deriveTurnStatus, taskDataToStoredImage } from "@/lib/image-task-state";
import { useImageConversationsStore } from "@/store/image-conversations";

const POLL_INTERVAL_MS = 2000;
const MAX_CONSECUTIVE_POLL_ERRORS = 10;

/** 正在运行的会话队列：conversationId → 取消控制器 */
const activeQueueControllers = new Map<string, AbortController>();

/** 可被 AbortSignal 提前打断的 sleep；被打断后立即返回 */
function abortableSleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise<void>((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      resolve();
    }
    signal.addEventListener("abort", onAbort);
  });
}

/** 某会话队列是否已在运行（用于页面跳过重复启动） */
export function isConversationQueueActive(conversationId: string): boolean {
  return activeQueueControllers.has(conversationId);
}

/** 终止全部会话队列（组件卸载时调用，修复离开页面后轮询继续跑的泄漏） */
export function abortAllConversationQueues(): void {
  for (const controller of activeQueueControllers.values()) {
    controller.abort();
  }
  activeQueueControllers.clear();
}

type ConversationQueueOptions = {
  /** 队列处理完毕（未被取消）后的回调，页面用它刷新剩余额度 */
  onQueueDrained?: () => void;
};

/**
 * 启动指定会话的队列处理；同一会话重复调用直接忽略。
 * 内部异步执行，出错时把错误落回对应轮次的图片状态并 toast。
 */
export function runConversationQueue(conversationId: string, options: ConversationQueueOptions = {}): void {
  if (activeQueueControllers.has(conversationId)) {
    return;
  }
  const controller = new AbortController();
  activeQueueControllers.set(conversationId, controller);
  void runQueue(conversationId, controller.signal, options).finally(() => {
    activeQueueControllers.delete(conversationId);
  });
}

async function runQueue(
  conversationId: string,
  signal: AbortSignal,
  options: ConversationQueueOptions,
): Promise<void> {
  const store = useImageConversationsStore.getState();
  const snapshot = store.conversations.find((conversation) => conversation.id === conversationId);
  const activeTurn = snapshot?.turns.find(
    (turn) =>
      (turn.status === "queued" || turn.status === "generating") &&
      turn.images.some((image) => image.status === "loading"),
  );
  if (!snapshot || !activeTurn) {
    return;
  }

  const applyTasks = async (tasks: ImageTask[]) => {
    const taskMap = new Map(tasks.map((task) => [task.id, task]));
    await useImageConversationsStore.getState().updateConversation(conversationId, (conversation) => {
      const turns = conversation.turns.map((turn) => {
        if (turn.id !== activeTurn.id) {
          return turn;
        }
        const images = turn.images.map((image) => {
          const taskId = image.taskId || image.id;
          const task = taskMap.get(taskId);
          return task ? taskDataToStoredImage({ ...image, taskId }, task) : image;
        });
        const derived = deriveTurnStatus({ ...turn, images });
        return {
          ...turn,
          ...derived,
          images,
        };
      });
      return {
        ...conversation,
        updatedAt: new Date().toISOString(),
        turns,
      };
    });
  };

  try {
    const referenceFiles = activeTurn.referenceImages.map((image, index) =>
      dataUrlToFile(image.dataUrl, image.name || `${activeTurn.id}-${index + 1}.png`, image.type),
    );
    if (activeTurn.mode === "edit" && referenceFiles.length === 0) {
      throw new Error("未找到可用于继续编辑的参考图");
    }

    const pendingImages = activeTurn.images.filter((image) => image.status === "loading");
    const submitted = await Promise.all(
      pendingImages.map((image) => {
        const taskId = image.taskId || image.id;
        return activeTurn.mode === "edit"
          ? createImageEditTask(taskId, referenceFiles, activeTurn.prompt, activeTurn.model, activeTurn.size, activeTurn.quality)
          : createImageGenerationTask(taskId, activeTurn.prompt, activeTurn.model, activeTurn.size, activeTurn.quality);
      }),
    );
    await applyTasks(submitted);

    let consecutiveErrors = 0;
    const retryingTaskIds = new Set<string>();
    while (!signal.aborted) {
      const latestConversation = useImageConversationsStore
        .getState()
        .conversations.find((conversation) => conversation.id === conversationId);
      const latestTurn = latestConversation?.turns.find((turn) => turn.id === activeTurn.id);
      const loadingTaskIds =
        latestTurn?.images.flatMap((image) =>
          image.status === "loading" && image.taskId ? [image.taskId] : [],
        ) || [];
      if (loadingTaskIds.length === 0) {
        break;
      }

      await abortableSleep(POLL_INTERVAL_MS, signal);
      if (signal.aborted) {
        return;
      }
      try {
        const taskList = await fetchImageTasks(loadingTaskIds);
        consecutiveErrors = 0;
        if (taskList.items.length > 0) {
          // 检测是否有超时错误且需要显示重试按钮
          const timeoutTask = taskList.items.find(
            (task) =>
              task.status === "error" &&
              task.error?.includes("超时") &&
              task.conversation_id &&
              !retryingTaskIds.has(task.id),
          );
          if (timeoutTask && timeoutTask.conversation_id) {
            retryingTaskIds.add(timeoutTask.id);
            // 应用超时错误到对应图片，UI 上显示「继续等待」按钮（由页面处理续轮询）
            await applyTasks([timeoutTask]);
          } else {
            await applyTasks(taskList.items);
          }
        }
        if (taskList.missing_ids.length > 0 && latestTurn) {
          // missing_ids：后端已丢失的任务，自动重新提交
          const missingImages = latestTurn.images.filter(
            (image) => image.status === "loading" && image.taskId && taskList.missing_ids.includes(image.taskId),
          );
          const resubmitted = await Promise.all(
            missingImages.map((image) =>
              activeTurn.mode === "edit"
                ? createImageEditTask(image.taskId || image.id, referenceFiles, activeTurn.prompt, activeTurn.model, activeTurn.size, activeTurn.quality)
                : createImageGenerationTask(image.taskId || image.id, activeTurn.prompt, activeTurn.model, activeTurn.size, activeTurn.quality),
            ),
          );
          if (resubmitted.length > 0) {
            await applyTasks(resubmitted);
          }
        }
      } catch (pollError) {
        consecutiveErrors += 1;
        if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
          throw pollError;
        }
      }
    }

    if (!signal.aborted) {
      options.onQueueDrained?.();
    }
  } catch (error) {
    if (signal.aborted) {
      // 组件已卸载导致的取消不算失败，状态恢复交给下次加载时的历史恢复逻辑
      return;
    }
    const message = error instanceof Error ? error.message : "生成图片失败";
    await useImageConversationsStore.getState().updateConversation(conversationId, (conversation) => {
      return {
        ...conversation,
        updatedAt: new Date().toISOString(),
        turns: conversation.turns.map((turn) =>
          turn.id === activeTurn.id
            ? {
                ...turn,
                status: "error",
                error: message,
                images: turn.images.map((image) =>
                  image.status === "loading" ? { ...image, status: "error", error: message } : image,
                ),
              }
            : turn,
        ),
      };
    });
    toast.error(message);
  } finally {
    if (!signal.aborted) {
      kickPendingConversationQueues(options);
    }
  }
}

/** 扫描仍有排队/生成中图片且尚未运行的会话，逐个启动队列 */
function kickPendingConversationQueues(options: ConversationQueueOptions = {}): void {
  const conversations = useImageConversationsStore.getState().conversations;
  for (const conversation of conversations) {
    if (activeQueueControllers.has(conversation.id)) {
      continue;
    }
    if (
      conversation.turns.some(
        (turn) =>
          (turn.status === "queued" || turn.status === "generating") &&
          turn.images.some((image) => image.status === "loading"),
      )
    ) {
      runConversationQueue(conversation.id, options);
    }
  }
}
