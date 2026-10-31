/**
 * image-task-state.ts 任务↔图片状态机单测。
 *
 * 覆盖点：
 * - createLoadingImages / buildQueuedTurn / buildSubmittedConversation
 *   的占位图与轮次构造（edit 模式保留参考图，generate 清空）
 * - buildRegeneratedConversation / buildRetryImageConversation 的重建
 *   与无有效提示词时返回 null 的异常分支
 * - buildDeletedTurnPartConversation：删提示词、删结果、双删清空
 * - taskDataToStoredImage：success/error 终态、缺数据异常分支、
 *   queued/running 的 loading 推进与计时
 * - deriveTurnStatus / finalizeIdleQueuedTurn 的轮次状态推导与收敛
 * - syncConversationImageTasks / recoverConversationHistory 的批量同步
 *   （mock fetchImageTasks / saveImageConversations）
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImageTask } from "@/lib/api/image-tasks";
import type { ImageConversation, ImageTurn, StoredImage } from "@/store/image-conversations";
import {
  buildDeletedTurnPartConversation,
  buildQueuedTurn,
  buildRegeneratedConversation,
  buildRetryImageConversation,
  buildSubmittedConversation,
  createLoadingImages,
  deriveTurnStatus,
  finalizeIdleQueuedTurn,
  recoverConversationHistory,
  syncConversationImageTasks,
  taskDataToStoredImage,
} from "@/lib/image-task-state";

const { fetchImageTasksMock, saveImageConversationsMock } = vi.hoisted(() => ({
  fetchImageTasksMock: vi.fn(),
  saveImageConversationsMock: vi.fn(async () => {}),
}));

vi.mock("@/lib/api/image-tasks", () => ({
  fetchImageTasks: fetchImageTasksMock,
}));

vi.mock("@/store/image-conversations", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/store/image-conversations")>();
  return { ...original, saveImageConversations: saveImageConversationsMock };
});

beforeEach(() => {
  fetchImageTasksMock.mockReset();
  saveImageConversationsMock.mockClear();
});

// ---- 构造工具 ----

function makeTurn(overrides: Partial<ImageTurn> = {}): ImageTurn {
  return {
    id: "turn-1",
    prompt: "a cat",
    model: "gpt-image-2",
    mode: "generate",
    referenceImages: [],
    count: 2,
    size: "1024x1024",
    ratio: "1:1",
    tier: "standard",
    quality: "auto",
    images: [
      { id: "turn-1-0", taskId: "task-0", status: "loading" },
      { id: "turn-1-1", taskId: "task-1", status: "loading" },
    ],
    createdAt: new Date(Date.now() - 60_000).toISOString(),
    status: "generating",
    ...overrides,
  };
}

function makeConversation(turns: ImageTurn[]): ImageConversation {
  return {
    id: "conv-1",
    title: "a cat",
    createdAt: new Date(Date.now() - 60_000).toISOString(),
    updatedAt: new Date(Date.now() - 60_000).toISOString(),
    turns,
  };
}

function makeTask(overrides: Partial<ImageTask> & { id: string }): ImageTask {
  return {
    status: "running",
    mode: "generate",
    created_at: "2026-10-31T00:00:00",
    updated_at: "2026-10-31T00:00:00",
    ...overrides,
  };
}

// ---- 占位图与轮次构造 ----

describe("createLoadingImages", () => {
  it("按数量生成带序号 id 的 loading 占位图", () => {
    const images = createLoadingImages("t1", 3);
    expect(images).toHaveLength(3);
    expect(images.map((image) => image.id)).toEqual(["t1-0", "t1-1", "t1-2"]);
    expect(images.every((image) => image.status === "loading" && image.taskId === image.id)).toBe(true);
  });

  it("数量为 0 时返回空数组", () => {
    expect(createLoadingImages("t1", 0)).toEqual([]);
  });
});

describe("buildQueuedTurn", () => {
  it("edit 模式保留参考图，generate 模式清空参考图", () => {
    const referenceImages = [{ name: "ref.png", type: "image/png", dataUrl: "data:..." }];
    const editTurn = buildQueuedTurn({
      prompt: "edit it", model: "gpt-image-2", mode: "edit", referenceImages,
      count: 1, size: "1024x1024", ratio: "1:1", tier: "standard", quality: "auto",
    });
    expect(editTurn.mode).toBe("edit");
    expect(editTurn.referenceImages).toEqual(referenceImages);
    expect(editTurn.status).toBe("queued");
    expect(editTurn.images).toHaveLength(1);
    expect(editTurn.images[0].status).toBe("loading");

    const generateTurn = buildQueuedTurn({
      prompt: "gen", model: "gpt-image-2", mode: "generate", referenceImages,
      count: 2, size: "1024x1024", ratio: "1:1", tier: "standard", quality: "auto",
    });
    expect(generateTurn.referenceImages).toEqual([]);
    expect(generateTurn.images).toHaveLength(2);
  });
});

describe("buildSubmittedConversation", () => {
  it("已有会话追加轮次并刷新 updatedAt", () => {
    const existing = makeConversation([makeTurn()]);
    const turn = makeTurn({ id: "turn-2" });
    const result = buildSubmittedConversation(existing, turn);
    expect(result.turns).toEqual([existing.turns[0], turn]);
    expect(result.updatedAt >= existing.updatedAt).toBe(true);
    expect(result.id).toBe("conv-1");
  });

  it("无会话时新建并按提示词生成标题", () => {
    const turn = makeTurn({ prompt: "一只橘猫在晒太阳" });
    const result = buildSubmittedConversation(null, turn);
    expect(result.turns).toEqual([turn]);
    expect(result.title).toBe("一只橘猫在晒太阳");
    expect(result.id).toBeTruthy();
  });
});

// ---- 重建与删除 ----

describe("buildRegeneratedConversation", () => {
  it("复制源轮次配置并追加排队轮次", () => {
    const conversation = makeConversation([
      makeTurn({ id: "turn-1", count: 0, images: [] }),
    ]);
    const result = buildRegeneratedConversation(conversation, "turn-1");
    expect(result).not.toBeNull();
    const { conversation: next, turn } = result!;
    expect(next.turns).toHaveLength(2);
    expect(turn.id).not.toBe("turn-1");
    expect(turn.status).toBe("queued");
    expect(turn.prompt).toBe("a cat");
    // count 非法时回退图片数或 1
    expect(turn.count).toBe(1);
    expect(turn.images).toHaveLength(1);
    expect(turn.error).toBeUndefined();
  });

  it("源轮次提示词为空或不存在时返回 null", () => {
    const conversation = makeConversation([
      makeTurn({ id: "turn-1", prompt: "   " }),
    ]);
    expect(buildRegeneratedConversation(conversation, "turn-1")).toBeNull();
    expect(buildRegeneratedConversation(conversation, "missing")).toBeNull();
  });
});

describe("buildRetryImageConversation", () => {
  it("把指定失败图片重置为新的排队任务", () => {
    const conversation = makeConversation([
      makeTurn({
        id: "turn-1",
        status: "error",
        images: [
          { id: "img-1", taskId: "task-1", status: "error", error: "boom" },
          { id: "img-2", taskId: "task-2", status: "success" },
        ],
      }),
    ]);
    const result = buildRetryImageConversation(conversation, "turn-1", "img-1");
    expect(result).not.toBeNull();
    const retried = result!.turns[0].images[0];
    expect(retried.status).toBe("loading");
    expect(retried.id).not.toBe("img-1");
    expect(retried.taskId).toBe(retried.id);
    expect(result!.turns[0].images[1].id).toBe("img-2");
  });

  it("轮次无有效提示词或轮次不存在时返回 null", () => {
    const emptyPrompt = makeConversation([makeTurn({ prompt: "" })]);
    expect(buildRetryImageConversation(emptyPrompt, "turn-1", "img-1")).toBeNull();

    const conversation = makeConversation([makeTurn()]);
    expect(buildRetryImageConversation(conversation, "missing-turn", "img-1")).toBeNull();
  });

  it("目标图片不存在时返回 null，不改动会话（R1-2：changed 守卫须以图片实际替换为准）", () => {
    // 图片 id 匹配不到（双击重试后旧 id 已被替换、跨 tab 竞态同步）时
    // 不应返回非 null 会话，避免 handleRetryImage 误写 store 并重复提交任务
    const conversation = makeConversation([makeTurn()]);
    expect(buildRetryImageConversation(conversation, "turn-1", "missing-img")).toBeNull();
  });
});

describe("buildDeletedTurnPartConversation", () => {
  it("删除提示词：prompt 清空并标记 promptDeleted", () => {
    const conversation = makeConversation([
      makeTurn(),
      makeTurn({ id: "turn-2" }),
    ]);
    const result = buildDeletedTurnPartConversation(conversation, "turn-1", "prompt");
    expect(result).not.toBeNull();
    const turn = result!.turns[0];
    expect(turn.prompt).toBe("");
    expect(turn.promptDeleted).toBe(true);
    expect(turn.images).toEqual(conversation.turns[0].images);
  });

  it("删除结果：图片置为已删除错误态并标记 resultsDeleted", () => {
    const conversation = makeConversation([makeTurn()]);
    const result = buildDeletedTurnPartConversation(conversation, "turn-1", "results");
    const turn = result!.turns[0];
    expect(turn.resultsDeleted).toBe(true);
    expect(turn.images.every((image: StoredImage) => image.status === "error" && image.error === "生成结果已删除")).toBe(true);
  });

  it("两部分都已删除（或删除后无剩余轮次）时返回 null", () => {
    const bothDeleted = makeConversation([
      makeTurn({ promptDeleted: true, resultsDeleted: true }),
    ]);
    expect(buildDeletedTurnPartConversation(bothDeleted, "turn-1", "prompt")).toBeNull();
    expect(buildDeletedTurnPartConversation(bothDeleted, "turn-1", "results")).toBeNull();
    expect(buildDeletedTurnPartConversation(makeConversation([makeTurn()]), "turn-1", "prompt")).not.toBeNull();
  });
});

// ---- 任务 ↔ 图片状态映射 ----

describe("taskDataToStoredImage", () => {
  it("success 且有数据：落入 success 终态并携带时长", () => {
    const image: StoredImage = { id: "i1", status: "loading" };
    const task = makeTask({
      id: "task-1", status: "success", duration_ms: 1234,
      data: [{ b64_json: "b64", url: "https://x/img.png", revised_prompt: "better" }],
    });
    const next = taskDataToStoredImage(image, task);
    expect(next.status).toBe("success");
    expect(next.b64_json).toBe("b64");
    expect(next.url).toBe("https://x/img.png");
    expect(next.revised_prompt).toBe("better");
    expect(next.durationMs).toBe(1234);
    expect(next.error).toBeUndefined();
    expect(next.progress).toBeUndefined();
  });

  it("success 但缺图片数据：转入错误态", () => {
    const next = taskDataToStoredImage({ id: "i1", status: "loading" }, makeTask({ id: "t", status: "success", data: [{}] }));
    expect(next.status).toBe("error");
    expect(next.error).toBe("未返回图片数据");
  });

  it("error：携带错误消息与时长，缺省消息兜底", () => {
    const next = taskDataToStoredImage({ id: "i1", status: "loading" },
      makeTask({ id: "t", status: "error", error: "上游拒绝", duration_ms: 10 }));
    expect(next.status).toBe("error");
    expect(next.error).toBe("上游拒绝");
    expect(next.durationMs).toBe(10);

    const fallback = taskDataToStoredImage({ id: "i1", status: "loading" }, makeTask({ id: "t", status: "error" }));
    expect(fallback.error).toBe("生成失败");
  });

  it("queued：保持 loading 并记录 taskStatus", () => {
    const previous: StoredImage = { id: "i1", status: "loading", progress: "10%" };
    const next = taskDataToStoredImage(previous, makeTask({ id: "t", status: "queued", progress: "20%" }));
    expect(next.status).toBe("loading");
    expect(next.taskStatus).toBe("queued");
    expect(next.progress).toBe("20%");
    expect(next.startTime).toBeUndefined();
  });

  it("running：首次进入时记录 startTime 并采用后端 elapsed_secs", () => {
    const next = taskDataToStoredImage(
      { id: "i1", status: "loading" },
      makeTask({ id: "t", status: "running", elapsed_secs: 5.5 }),
    );
    expect(next.taskStatus).toBe("running");
    expect(next.startTime).toBeTypeOf("number");
    expect(next.elapsedSecs).toBe(5.5);
    expect(next.elapsedUpdatedAt).toBeTypeOf("number");

    // 已有 startTime 不被覆盖
    const again = taskDataToStoredImage(next, makeTask({ id: "t", status: "running", elapsed_secs: 6.5 }));
    expect(again.startTime).toBe(next.startTime);
    expect(again.elapsedSecs).toBe(6.5);
  });

  it("未知状态保留原 taskStatus 且 progress 无新值时沿用旧值", () => {
    const previous: StoredImage = { id: "i1", status: "loading", taskStatus: "running", progress: "30%" };
    const next = taskDataToStoredImage(previous, makeTask({ id: "t", status: "queued" }));
    expect(next.taskStatus).toBe("queued");
    expect(next.progress).toBe("30%");
  });
});

// ---- 轮次状态推导 ----

describe("deriveTurnStatus", () => {
  it("存在 loading 且有 running → generating", () => {
    const turn = makeTurn({
      images: [
        { id: "a", taskId: "t", status: "loading", taskStatus: "running" },
        { id: "b", status: "error" },
      ],
    });
    expect(deriveTurnStatus(turn)).toEqual({ status: "generating", error: undefined });
  });

  it("存在 loading 无 running → 保持 queued", () => {
    const turn = makeTurn({ status: "queued", images: [{ id: "a", taskId: "t", status: "loading" }] });
    expect(deriveTurnStatus(turn)).toEqual({ status: "queued", error: undefined });
  });

  it("无 loading 有失败 → error 并带失败数量", () => {
    const turn = makeTurn({
      images: [{ id: "a", status: "error" }, { id: "b", status: "error" }, { id: "c", status: "success" }],
    });
    expect(deriveTurnStatus(turn)).toEqual({ status: "error", error: "其中 2 张未成功生成" });
  });

  it("全部成功或空图片 → success", () => {
    expect(deriveTurnStatus(makeTurn({ images: [{ id: "a", status: "success" }] })).status).toBe("success");
    expect(deriveTurnStatus(makeTurn({ images: [] }))).toEqual({ status: "success", error: undefined });
  });
});

describe("finalizeIdleQueuedTurn", () => {
  it("排队/生成中轮次无 loading 图片时收敛为推导终态", () => {
    const turn = makeTurn({
      status: "queued",
      images: [{ id: "a", status: "error" }],
    });
    const finalized = finalizeIdleQueuedTurn(turn);
    expect(finalized.status).toBe("error");
    expect(finalized.error).toBe("其中 1 张未成功生成");
  });

  it("仍有 loading 图片或已收敛的轮次原样返回", () => {
    const loading = makeTurn();
    expect(finalizeIdleQueuedTurn(loading)).toBe(loading);

    const done = makeTurn({ status: "success", images: [{ id: "a", status: "success" }] });
    expect(finalizeIdleQueuedTurn(done)).toBe(done);
  });
});

// ---- 批量同步与历史恢复 ----

describe("syncConversationImageTasks", () => {
  it("无待同步图片时原样返回且不请求", async () => {
    const items = [makeConversation([makeTurn({ images: [{ id: "a", status: "success" }] })])];
    const result = await syncConversationImageTasks(items);
    expect(result).toBe(items);
    expect(fetchImageTasksMock).not.toHaveBeenCalled();
  });

  it("按 taskId 拉取任务并更新图片状态、推导轮次状态并落盘", async () => {
    const items = [makeConversation([
      makeTurn({
        status: "generating",
        images: [
          { id: "img-1", taskId: "task-1", status: "loading" },
          { id: "img-2", taskId: "task-2", status: "loading" },
        ],
      }),
    ])];
    fetchImageTasksMock.mockResolvedValue({
      items: [
        makeTask({ id: "task-1", status: "success", data: [{ b64_json: "b64" }] }),
        makeTask({ id: "task-2", status: "error", error: "boom" }),
      ],
    });

    const result = await syncConversationImageTasks(items);
    expect(fetchImageTasksMock).toHaveBeenCalledWith(["task-1", "task-2"]);
    expect(saveImageConversationsMock).toHaveBeenCalledTimes(1);

    const turn = result[0].turns[0];
    expect(turn.images[0].status).toBe("success");
    expect(turn.images[1].status).toBe("error");
    expect(turn.status).toBe("error");
    expect(turn.error).toBe("其中 1 张未成功生成");
  });

  it("resultsDeleted 的轮次不参与同步", async () => {
    const items = [makeConversation([
      makeTurn({
        resultsDeleted: true,
        images: [{ id: "img-1", taskId: "task-1", status: "error" }],
      }),
    ])];
    const result = await syncConversationImageTasks(items);
    expect(result).toBe(items);
    expect(fetchImageTasksMock).not.toHaveBeenCalled();
  });

  it("请求失败时原样返回", async () => {
    const items = [makeConversation([makeTurn({ images: [{ id: "a", taskId: "t", status: "loading" }] })])];
    fetchImageTasksMock.mockRejectedValue(new Error("network"));
    const result = await syncConversationImageTasks(items);
    expect(result).toBe(items);
    expect(saveImageConversationsMock).not.toHaveBeenCalled();
  });
});

describe("recoverConversationHistory", () => {
  it("无 taskId 的残留 loading 图片标记为中断错误并收敛轮次终态", async () => {
    fetchImageTasksMock.mockResolvedValue({ items: [] });
    const items = [makeConversation([
      makeTurn({
        status: "generating",
        images: [
          { id: "img-1", status: "loading" }, // 无 taskId → 中断
          { id: "img-2", taskId: "task-2", status: "loading" }, // 有 taskId → 保留
        ],
      }),
      makeTurn({ id: "turn-2", status: "success" }),
    ])];

    const result = await recoverConversationHistory(items);
    const turn = result[0].turns[0];
    expect(turn.images[0].status).toBe("error");
    expect(turn.images[0].error).toContain("页面刷新或任务中断");
    expect(turn.images[1].status).toBe("loading");
    // 剩余 loading 图片无 running taskStatus → 保持 queued/generating 语义
    expect(turn.status).toBe("generating");
  });

  it("无需恢复的会话原样返回", async () => {
    const items = [makeConversation([makeTurn({ status: "success", images: [{ id: "a", status: "success" }] })])];
    const result = await recoverConversationHistory(items);
    expect(result[0]).toBe(items[0]);
    expect(fetchImageTasksMock).not.toHaveBeenCalled();
  });
});
