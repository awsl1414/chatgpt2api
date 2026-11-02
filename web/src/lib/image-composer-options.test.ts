/**
 * image-composer-options.ts 单测：模型尺寸能力表、档位置灰与切换模型回退。
 *
 * 依据工作区 `docs/size-verification.md`：
 * - codex 系列忽略 `size` → 整组比例档置灰；
 * - 2K/4K 对所有模型只兑现比例 → 置灰；
 * - picture_v2 的 1K 比例档可用。
 */
import { describe, expect, it } from "vitest";

import {
  IMAGE_MODEL_SIZE_CAPABILITIES,
  aspectFallbackForModel,
  aspectOptionNote,
  aspectOptions,
  baseImageModel,
  imageSizeCapability,
  isAspectOptionDisabled,
  modelUsesApiSize,
  modelUsesPromptSize,
  resolveRequestSize,
} from "@/lib/image-composer-options";

const optionOf = (ratio: string, tier: string) => {
  const option = aspectOptions.find((item) => item.ratio === ratio && item.tier === tier);
  if (!option) {
    throw new Error(`missing aspect option ${ratio}/${tier}`);
  }
  return option;
};

describe("模型能力表", () => {
  it("picture_v2 的接口 size 生效", () => {
    expect(modelUsesApiSize("gpt-image-2")).toBe(true);
    expect(modelUsesPromptSize("gpt-image-2")).toBe(true);
  });

  it.each(["codex-gpt-image-2", "codex-gpt-image-2.5-flare", "codex-gpt-image-2.5-sunburst"])(
    "%s 忽略接口 size，但提示词尺寸生效",
    (model) => {
      expect(modelUsesApiSize(model)).toBe(false);
      expect(modelUsesPromptSize(model)).toBe(true);
    },
  );

  it.each(["plus-", "team-", "pro-"])("%s 前缀不改变能力判定", (prefix) => {
    expect(baseImageModel(`${prefix}codex-gpt-image-2`)).toBe("codex-gpt-image-2");
    expect(modelUsesApiSize(`${prefix}codex-gpt-image-2`)).toBe(false);
    expect(modelUsesApiSize(`${prefix}gpt-image-2`)).toBe(true);
  });

  it("非图片模型没有能力记录", () => {
    expect(imageSizeCapability("gpt-5-5")).toBeNull();
    expect(modelUsesApiSize("gpt-5-5")).toBe(false);
    expect(modelUsesPromptSize("gpt-5-5")).toBe(false);
  });

  it("能力表覆盖全部已知图片模型", () => {
    expect(Object.keys(IMAGE_MODEL_SIZE_CAPABILITIES).sort()).toEqual([
      "codex-gpt-image-2",
      "codex-gpt-image-2.5-flare",
      "codex-gpt-image-2.5-sunburst",
      "gpt-image-2",
    ]);
  });
});

describe("档位置灰", () => {
  it("codex 下除 auto 外全部置灰", () => {
    for (const option of aspectOptions) {
      expect(isAspectOptionDisabled("codex-gpt-image-2", option)).toBe(option.tier !== "auto");
    }
  });

  it("picture_v2 下 2K/4K 置灰、1K 与 auto 可选", () => {
    for (const option of aspectOptions) {
      const expected = option.tier !== "1k" && option.tier !== "auto";
      expect(isAspectOptionDisabled("gpt-image-2", option)).toBe(expected);
    }
  });

  it("置灰说明文案区分两种原因", () => {
    expect(aspectOptionNote("codex-gpt-image-2", optionOf("16:9", "1k"))).toContain("不支持尺寸参数");
    expect(aspectOptionNote("gpt-image-2", optionOf("16:9", "4k"))).toContain("只影响比例");
    expect(aspectOptionNote("gpt-image-2", optionOf("16:9", "1k"))).toBeNull();
    expect(aspectOptionNote("gpt-image-2", optionOf("auto", "auto"))).toBeNull();
  });
});

describe("切换模型回退", () => {
  it("切到 codex 时从 1K 比例档回退到 auto", () => {
    const fallback = aspectFallbackForModel("codex-gpt-image-2", "16:9", "1k");
    expect(fallback?.tier).toBe("auto");
  });

  it("切到 picture_v2 时 2K 回退到同比例 1K", () => {
    expect(aspectFallbackForModel("gpt-image-2", "16:9", "4k")?.tier).toBe("1k");
    expect(aspectFallbackForModel("gpt-image-2", "1:1", "2k")?.ratio).toBe("1:1");
  });

  it("当前档位在新模型下仍可用时不回退", () => {
    expect(aspectFallbackForModel("gpt-image-2", "16:9", "1k")).toBeNull();
    expect(aspectFallbackForModel("codex-gpt-image-2", "auto", "auto")).toBeNull();
  });
});

describe("提交尺寸", () => {
  it("picture_v2 提交具体 size", () => {
    expect(resolveRequestSize("gpt-image-2", "1920", "1088")).toBe("1920x1088");
  });

  it("picture_v2 在 auto 档位下仍提交输入框里的宽高", () => {
    expect(resolveRequestSize("gpt-image-2", "", "")).toBe("1024x1024");
    expect(resolveRequestSize("gpt-image-2", "1280", "720")).toBe("1280x720");
  });

  it("codex 不提交 size", () => {
    expect(resolveRequestSize("codex-gpt-image-2", "1920", "1088")).toBeUndefined();
    expect(resolveRequestSize("plus-codex-gpt-image-2.5-flare", "1024", "1024")).toBeUndefined();
  });
});
