/**
 * 生图任务状态机（审计 §5）：任务（ImageTask）↔ 图片（StoredImage）↔ 轮次（ImageTurn）之间的状态映射，
 * 以及会话历史恢复与任务批量同步。除 IO（fetchImageTasks / saveImageConversations）外均为纯函数，可单测。
 */

import { fetchImageTasks, type ImageModel, type ImageTask } from "@/lib/api";
import { buildConversationTitle, createId } from "@/lib/image-utils";
import {
  saveImageConversations,
  type ImageConversation,
  type ImageConversationMode,
  type ImageTurn,
  type StoredImage,
  type StoredReferenceImage,
} from "@/store/image-conversations";

/** 为一个轮次生成 count 张初始 loading 占位图 */
export function createLoadingImages(turnId: string, count: number): StoredImage[] {
  return Array.from({ length: count }, (_, index) => {
    const imageId = `${turnId}-${index}`;
    return {
      id: imageId,
      taskId: imageId,
      status: "loading" as const,
    };
  });
}

/** 由 composer 参数构造一个排队中的新轮次 */
export function buildQueuedTurn(params: {
  prompt: string;
  model: ImageModel;
  mode: ImageConversationMode;
  referenceImages: StoredReferenceImage[];
  count: number;
  size: string;
  ratio: string;
  tier: string;
  quality: string;
}): ImageTurn {
  const turnId = createId();
  return {
    id: turnId,
    prompt: params.prompt,
    model: params.model,
    mode: params.mode,
    referenceImages: params.mode === "edit" ? params.referenceImages : [],
    count: params.count,
    size: params.size,
    ratio: params.ratio,
    tier: params.tier,
    quality: params.quality,
    images: createLoadingImages(turnId, params.count),
    createdAt: new Date().toISOString(),
    status: "queued",
  };
}

/** 用新提示词提交生成的目标会话：追加排队轮次并刷新 updatedAt */
export function buildSubmittedConversation(target: ImageConversation | null, turn: ImageTurn): ImageConversation {
  const now = new Date().toISOString();
  if (target) {
    return {
      ...target,
      updatedAt: now,
      turns: [...target.turns, turn],
    };
  }
  return {
    id: createId(),
    title: buildConversationTitle(turn.prompt),
    createdAt: now,
    updatedAt: now,
    turns: [turn],
  };
}

/** 复制源轮次配置构造「重新生成」轮次；源轮次无有效提示词时返回 null */
export function buildRegeneratedConversation(
  conversation: ImageConversation,
  turnId: string,
): { conversation: ImageConversation; turn: ImageTurn } | null {
  const sourceTurn = conversation.turns.find((turn) => turn.id === turnId);
  if (!sourceTurn || !sourceTurn.prompt.trim()) {
    return null;
  }

  const now = new Date().toISOString();
  const nextTurnId = createId();
  const count = Math.max(1, sourceTurn.count || sourceTurn.images.length || 1);
  const nextTurn: ImageTurn = {
    ...sourceTurn,
    id: nextTurnId,
    count,
    images: createLoadingImages(nextTurnId, count),
    createdAt: now,
    status: "queued",
    error: undefined,
    promptDeleted: false,
    resultsDeleted: false,
  };
  return {
    conversation: {
      ...conversation,
      updatedAt: now,
      turns: [...conversation.turns, nextTurn],
    },
    turn: nextTurn,
  };
}

/**
 * 删除轮次的「提示词记录」或「生成结果」：
 * prompt 置空并标记 promptDeleted，results 标记 resultsDeleted 并把图片置为「已删除」错误态；
 * 两部分都被删除（或删除后无剩余轮次）时返回 null，表示整个会话应被删除。
 */
export function buildDeletedTurnPartConversation(
  conversation: ImageConversation,
  turnId: string,
  part: "prompt" | "results",
): ImageConversation | null {
  const turns = conversation.turns
    .map((turn) => {
      if (turn.id !== turnId) {
        return turn;
      }
      const images =
        part === "results"
          ? turn.images.map((image) => ({ id: image.id, status: "error" as const, error: "生成结果已删除" }))
          : turn.images;
      const derived =
        part === "results"
          ? deriveTurnStatus({ ...turn, images })
          : { status: turn.status, error: turn.error };
      const nextTurn = {
        ...turn,
        prompt: part === "prompt" ? "" : turn.prompt,
        promptDeleted: part === "prompt" ? true : turn.promptDeleted,
        resultsDeleted: part === "results" ? true : turn.resultsDeleted,
        ...derived,
        images,
      };
      return nextTurn.promptDeleted && nextTurn.resultsDeleted ? null : nextTurn;
    })
    .filter((turn): turn is ImageTurn => Boolean(turn));

  if (turns.length === 0) {
    return null;
  }
  return {
    ...conversation,
    updatedAt: new Date().toISOString(),
    turns,
  };
}

/** 将指定失败图片重置为新的排队任务；轮次无有效提示词时返回 null（原会话不变） */
export function buildRetryImageConversation(
  conversation: ImageConversation,
  turnId: string,
  imageId: string,
): ImageConversation | null {
  const now = new Date().toISOString();
  let changed = false;
  const turns = conversation.turns.map((turn) => {
    if (turn.id !== turnId || !turn.prompt.trim()) {
      return turn;
    }

    const retryImageId = `${turnId}-${createId()}`;
    const images = turn.images.map((image) =>
      image.id === imageId
        ? {
            id: retryImageId,
            taskId: retryImageId,
            status: "loading" as const,
          }
        : image,
    );
    changed = true;
    const derived = deriveTurnStatus({ ...turn, status: "queued", images });
    return {
      ...turn,
      ...derived,
      images,
    };
  });
  if (!changed) {
    return null;
  }
  return {
    ...conversation,
    updatedAt: now,
    turns,
  };
}

/**
 * 把后端任务状态映射到单张图片的存储状态：
 * success / error 直接落终态；queued / running 保持 loading 并推进进度与计时。
 */
export function taskDataToStoredImage(image: StoredImage, task: ImageTask): StoredImage {
  if (task.status === "success") {
    const first = task.data?.[0];
    if (!first?.b64_json && !first?.url) {
      return {
        ...image,
        taskId: task.id,
        status: "error",
        taskStatus: undefined,
        progress: undefined,
        error: "未返回图片数据",
      };
    }
    return {
      ...image,
      taskId: task.id,
      status: "success",
      taskStatus: undefined,
      progress: undefined,
      b64_json: first.b64_json,
      url: first.url,
      revised_prompt: first.revised_prompt,
      error: undefined,
      durationMs: task.duration_ms,
    };
  }

  if (task.status === "error") {
    return {
      ...image,
      taskId: task.id,
      status: "error",
      taskStatus: undefined,
      progress: undefined,
      error: task.error || "生成失败",
      durationMs: task.duration_ms,
    };
  }

  const newTaskStatus = task.status === "queued" ? "queued" : task.status === "running" ? "running" : image.taskStatus;
  const shouldSetStartTime = newTaskStatus === "running" && !image.startTime;
  const startTime = shouldSetStartTime ? Date.now() : image.startTime;
  // elapsedSecs 仅使用后端返回的值，确保计时从 image_stream_resolve_start 开始
  const elapsedSecs =
    newTaskStatus === "running" && typeof task.elapsed_secs === "number"
      ? task.elapsed_secs
      : undefined;

  return {
    ...image,
    taskId: task.id,
    status: "loading",
    taskStatus: newTaskStatus,
    progress: task.progress || image.progress,
    error: undefined,
    startTime,
    elapsedSecs,
    elapsedUpdatedAt: elapsedSecs != null ? Date.now() : undefined,
  };
}

/** 由轮次内各图片状态推导轮次整体状态与错误信息 */
export function deriveTurnStatus(turn: ImageTurn): Pick<ImageTurn, "status" | "error"> {
  const loadingCount = turn.images.filter((image) => image.status === "loading").length;
  const failedCount = turn.images.filter((image) => image.status === "error").length;
  const successCount = turn.images.filter((image) => image.status === "success").length;
  if (loadingCount > 0) {
    // 如果任何图片的 taskStatus 为 running，则状态为 generating
    const hasRunning = turn.images.some((image) => image.taskStatus === "running");
    if (hasRunning) {
      return { status: "generating", error: undefined };
    }
    return { status: turn.status === "queued" ? "queued" : "generating", error: undefined };
  }
  if (failedCount > 0) {
    return { status: "error", error: `其中 ${failedCount} 张未成功生成` };
  }
  if (successCount > 0) {
    return { status: "success", error: undefined };
  }
  // 所有图片都被忽略（images 为空），视为完成
  return { status: "success", error: undefined };
}

/** 排队/生成中的轮次若已无 loading 图片，收敛为推导出的终态 */
export function finalizeIdleQueuedTurn(turn: ImageTurn): ImageTurn {
  if (
    (turn.status !== "queued" && turn.status !== "generating") ||
    turn.images.some((image) => image.status === "loading")
  ) {
    return turn;
  }
  const derived = deriveTurnStatus(turn);
  if (derived.status === turn.status && derived.error === turn.error) {
    return turn;
  }
  return {
    ...turn,
    ...derived,
  };
}

/**
 * 批量同步会话内仍在 loading / 可重试 error 状态图片的后端任务状态，
 * 有变化时落盘并返回新数组（无变化时原样返回）。
 */
export async function syncConversationImageTasks(items: ImageConversation[]) {
  const taskIds = Array.from(
    new Set(
      items.flatMap((conversation) =>
        conversation.turns.flatMap((turn) =>
          turn.resultsDeleted
            ? []
            : turn.images.flatMap((image) =>
                (image.status === "loading" || (image.status === "error" && image.taskId))
                  ? [image.taskId!]
                  : [],
              ),
        ),
      ),
    ),
  );
  if (taskIds.length === 0) {
    return items;
  }

  let taskList: Awaited<ReturnType<typeof fetchImageTasks>>;
  try {
    taskList = await fetchImageTasks(taskIds);
  } catch {
    return items;
  }
  const taskMap = new Map(taskList.items.map((task) => [task.id, task]));
  let changed = false;
  const normalized = items.map((conversation) => {
    const turns = conversation.turns.map((turn) => {
      let turnChanged = false;
      const images = turn.images.map((image) => {
        if (!image.taskId) {
          return image;
        }
        if (image.status !== "loading" && image.status !== "error") {
          return image;
        }
        const task = taskMap.get(image.taskId);
        if (!task) {
          return image;
        }
        const nextImage = taskDataToStoredImage(image, task);
        if (nextImage !== image) {
          turnChanged = true;
        }
        return nextImage;
      });
      if (!turnChanged) {
        return turn;
      }
      changed = true;
      const derived = deriveTurnStatus({ ...turn, images });
      return {
        ...turn,
        ...derived,
        images,
      };
    });
    if (turns === conversation.turns || !turns.some((turn, index) => turn !== conversation.turns[index])) {
      return conversation;
    }
    return {
      ...conversation,
      turns,
      updatedAt: new Date().toISOString(),
    };
  });

  if (changed) {
    await saveImageConversations(normalized);
  }
  return normalized;
}

/**
 * 恢复页面刷新前的会话历史：
 * 无 taskId 的残留 loading 图片标记为中断错误，空闲排队轮次收敛终态，
 * 最后再对仍需跟踪的任务做一轮同步。
 */
export async function recoverConversationHistory(items: ImageConversation[]) {
  let changed = false;
  const normalized = items.map((conversation) => {
    const turns = conversation.turns.map((turn) => {
      if (turn.status !== "queued" && turn.status !== "generating" && turn.status !== "error") {
        return turn;
      }

      let turnChanged = false;
      const images = turn.images.map((image) => {
        if (image.status !== "loading" || image.taskId) {
          return image;
        }
        turnChanged = true;
        return {
          ...image,
          status: "error" as const,
          error: "页面刷新或任务中断，未找到可恢复的任务 ID",
        };
      });
      const candidateTurn = turnChanged ? { ...turn, images } : turn;
      const nextTurn = finalizeIdleQueuedTurn(candidateTurn);
      const derived = turnChanged ? deriveTurnStatus(nextTurn) : { status: nextTurn.status, error: nextTurn.error };
      if (!turnChanged && nextTurn === turn && derived.status === turn.status && derived.error === turn.error) {
        return turn;
      }
      changed = true;
      return {
        ...nextTurn,
        ...derived,
      };
    });

    if (!turns.some((turn, index) => turn !== conversation.turns[index])) {
      return conversation;
    }

    return {
      ...conversation,
      turns,
      updatedAt: new Date().toISOString(),
    };
  });

  if (changed) {
    await saveImageConversations(normalized);
  }

  return syncConversationImageTasks(normalized);
}
