import { isCodexImageModel } from "@/lib/api/models";
import type { ImageModel } from "@/lib/api/types";

/**
 * 图片生成参数的纯数据与纯函数（审计 F-中5）：
 * 宽高比预设、Codex 专属档位判定、切换模型时的尺寸回退。
 * 不依赖 React 与 UI 组件，供 useImageComposer 与 ImageComposer 共享，
 * 避免 hook 反向依赖页面组件。
 */

/** 一个宽高比预设：ratio/tier 为持久化选项，width/height 为实际生成尺寸 */
export type AspectOption = {
  ratio: string;
  tier: string;
  width: string;
  height: string;
  label: string;
};

/** 2K/4K 档位仅 Codex 模型支持，非 Codex 模型的宽高比选项需要置灰 */
export const codexExclusiveTiers = new Set(["2k", "4k"]);

export const aspectOptions: readonly AspectOption[] = [
  { ratio: "1:1", tier: "1k", width: "1024", height: "1024", label: "1:1" },
  { ratio: "2:3", tier: "1k", width: "1024", height: "1536", label: "2:3" },
  { ratio: "3:2", tier: "1k", width: "1536", height: "1024", label: "3:2" },
  { ratio: "3:4", tier: "1k", width: "1024", height: "1365", label: "3:4" },
  { ratio: "4:3", tier: "1k", width: "1365", height: "1024", label: "4:3" },
  { ratio: "9:16", tier: "1k", width: "1088", height: "1920", label: "9:16" },
  { ratio: "16:9", tier: "1k", width: "1920", height: "1088", label: "16:9" },
  { ratio: "1:1", tier: "2k", width: "2048", height: "2048", label: "1:1(2k)" },
  { ratio: "16:9", tier: "2k", width: "2560", height: "1440", label: "16:9(2k)" },
  { ratio: "9:16", tier: "2k", width: "1440", height: "2560", label: "9:16(2k)" },
  { ratio: "16:9", tier: "4k", width: "3840", height: "2160", label: "16:9(4k)" },
  { ratio: "9:16", tier: "4k", width: "2160", height: "3840", label: "9:16(4k)" },
  { ratio: "auto", tier: "auto", width: "1024", height: "1024", label: "auto" },
];

/**
 * 切换到非 Codex 模型时，若当前档位不被支持，回退到同比例的 1K 档（无匹配则回 auto）。
 * @returns null 表示当前尺寸无需调整
 */
export function aspectFallbackForModel(
  model: ImageModel,
  ratio: string,
  tier: string,
): AspectOption | null {
  if (isCodexImageModel(model) || !codexExclusiveTiers.has(tier)) {
    return null;
  }
  return (
    aspectOptions.find((option) => option.tier === "1k" && option.ratio === ratio) ??
    aspectOptions.find((option) => option.tier === "auto") ??
    null
  );
}
