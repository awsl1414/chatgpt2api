/**
 * image-composer-options.ts 单测：模型尺寸能力表、比例档可用性、说明文案与提交尺寸。
 *
 * 依据工作区 `docs/size-verification.md`：
 * - 比例对所有模型都有效（§4.3、§5），因此**没有任何比例档应被置灰**；
 * - 2K/4K 只兑现比例、不兑现像素（§5），应标注而非禁用；
 * - codex 忽略上游 `tools[0].size`（§3），但提示词比例有效，因此仍须提交 size。
 */
import { describe, expect, it } from "vitest";

import {
  IMAGE_MODEL_SIZE_CAPABILITIES,
  aspectOptionNote,
  aspectOptions,
  baseImageModel,
  imageSizeCapability,
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
  it.each([
    "gpt-image-2",
    "codex-gpt-image-2",
    "codex-gpt-image-2.5-flare",
    "codex-gpt-image-2.5-sunburst",
  ])("%s 的提示词比例通道有效", (model) => {
    expect(modelUsesPromptSize(model)).toBe(true);
  });

  it.each(["plus-", "team-", "pro-"])("%s 前缀不改变能力判定", (prefix) => {
    expect(baseImageModel(`${prefix}codex-gpt-image-2`)).toBe("codex-gpt-image-2");
    expect(modelUsesPromptSize(`${prefix}codex-gpt-image-2`)).toBe(true);
  });

  it("非图片模型没有能力记录", () => {
    expect(imageSizeCapability("gpt-5-5")).toBeNull();
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

describe("比例档可用性", () => {
  it("每个档位都出现在选项列表里（没有档位被移除）", () => {
    // 2K/4K 与 1K 档位全部保留：比例是真能兑现的能力，只做标注、不做禁用
    const tiers = new Set(aspectOptions.map((option) => option.tier));
    expect(tiers).toEqual(new Set(["1k", "2k", "4k", "auto"]));
    expect(aspectOptions.length).toBe(13);
  });
});

describe("档位说明文案", () => {
  it("1K 与 auto 无需额外说明", () => {
    expect(aspectOptionNote("codex-gpt-image-2", optionOf("16:9", "1k"))).toBeNull();
    expect(aspectOptionNote("gpt-image-2", optionOf("auto", "auto"))).toBeNull();
  });

  it("2K/4K 标注「比例有效、像素不兑现」", () => {
    const note2k = aspectOptionNote("gpt-image-2", optionOf("16:9", "2k"));
    expect(note2k).toContain("16:9 比例有效");
    expect(note2k).toContain("1.57M");
    expect(note2k).toContain("2K");

    const note4k = aspectOptionNote("codex-gpt-image-2", optionOf("9:16", "4k"));
    expect(note4k).toContain("9:16 比例有效");
    expect(note4k).toContain("4K");
  });
});

describe("提交尺寸", () => {
  it.each([
    "gpt-image-2",
    "codex-gpt-image-2",
    "codex-gpt-image-2.5-flare",
    "plus-codex-gpt-image-2",
  ])("%s 都提交 size（后端据此构造提示词）", (model) => {
    expect(resolveRequestSize(model, "1920", "1088")).toBe("1920x1088");
  });

  it("W/H 为空时回退 1024x1024", () => {
    expect(resolveRequestSize("codex-gpt-image-2", "", "")).toBe("1024x1024");
  });

  it("2K/4K 档位提交对应像素（比例意图的载体）", () => {
    expect(resolveRequestSize("gpt-image-2", "3840", "2160")).toBe("3840x2160");
    expect(resolveRequestSize("codex-gpt-image-2", "2160", "3840")).toBe("2160x3840");
  });
});
