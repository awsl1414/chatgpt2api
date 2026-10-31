/**
 * 图片管理页纯工具与标签逻辑单测。
 *
 * 覆盖点：
 * - formatSize / formatCapacity：KB 向上取整、MB 保留两位、GB 折算阈值
 * - imageKey：rel 优先、回退 url
 * - filterImagesByTags：空筛选原样返回、单标签、多标签 AND 语义、无标签图片被排除
 * - appendTag：空串/纯空白/已存在返回 null，正常追加不改动入参
 * - unusedTags：候选标签排除已拥有项
 */
import { describe, expect, it } from "vitest";

import type { ManagedImage } from "@/lib/api/images";
import { formatCapacity, formatSize, imageKey } from "@/lib/image-manager";
import { appendTag, filterImagesByTags, unusedTags } from "@/lib/image-tags";

function makeImage(overrides: Partial<ManagedImage>): ManagedImage {
  return {
    rel: "2026/10/31/a.png",
    name: "a.png",
    date: "2026-10-31",
    size: 1024,
    url: "https://example.test/a.png",
    created_at: "2026-10-31 10:00",
    ...overrides,
  };
}

describe("formatSize", () => {
  it("小于 1MB 时向上取整到 KB", () => {
    expect(formatSize(1)).toBe("1 KB");
    expect(formatSize(1025)).toBe("2 KB");
  });

  it("大于 1MB 时按 MB 保留两位小数", () => {
    expect(formatSize(1024 * 1024 + 1)).toBe("1.00 MB");
    expect(formatSize(3 * 1024 * 1024)).toBe("3.00 MB");
  });
});

describe("formatCapacity", () => {
  it("小于 1024MB 时按 MB 展示", () => {
    expect(formatCapacity(512)).toBe("512 MB");
    expect(formatCapacity(1023)).toBe("1023 MB");
  });

  it("达到 1024MB 时折算为 GB 并保留一位小数", () => {
    expect(formatCapacity(1024)).toBe("1.0 GB");
    expect(formatCapacity(1536)).toBe("1.5 GB");
  });
});

describe("imageKey", () => {
  it("优先返回 rel", () => {
    expect(imageKey(makeImage({ rel: "x/y.png" }))).toBe("x/y.png");
  });

  it("rel 为空时回退 url", () => {
    expect(imageKey(makeImage({ rel: "", url: "https://example.test/b.png" }))).toBe("https://example.test/b.png");
  });
});

describe("filterImagesByTags", () => {
  const items = [
    makeImage({ rel: "1", tags: ["风景", "蓝色"] }),
    makeImage({ rel: "2", tags: ["风景"] }),
    makeImage({ rel: "3" }),
  ];

  it("未选标签时原样返回", () => {
    expect(filterImagesByTags(items, [])).toEqual(items);
  });

  it("单标签筛选", () => {
    expect(filterImagesByTags(items, ["风景"]).map((item) => item.rel)).toEqual(["1", "2"]);
  });

  it("多标签为 AND 语义", () => {
    expect(filterImagesByTags(items, ["风景", "蓝色"]).map((item) => item.rel)).toEqual(["1"]);
  });

  it("无标签图片不会命中任何筛选", () => {
    expect(filterImagesByTags(items, ["风景"]).some((item) => item.rel === "3")).toBe(false);
  });
});

describe("appendTag", () => {
  it("正常追加并去除首尾空白", () => {
    const current = ["风景"];
    expect(appendTag(current, "  人像 ")).toEqual(["风景", "人像"]);
    expect(current).toEqual(["风景"]);
  });

  it("空串与纯空白返回 null", () => {
    expect(appendTag([], "")).toBeNull();
    expect(appendTag([], "   ")).toBeNull();
  });

  it("已存在返回 null", () => {
    expect(appendTag(["风景"], "风景")).toBeNull();
  });

  it("undefined 视为空列表", () => {
    expect(appendTag(undefined, "新标签")).toEqual(["新标签"]);
  });
});

describe("unusedTags", () => {
  it("排除图片已拥有的标签", () => {
    expect(unusedTags(["风景"], ["风景", "人像"])).toEqual(["人像"]);
  });

  it("图片无标签时返回全部", () => {
    expect(unusedTags(undefined, ["风景", "人像"])).toEqual(["风景", "人像"]);
  });
});
