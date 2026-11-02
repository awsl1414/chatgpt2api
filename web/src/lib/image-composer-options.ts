import type { ImageModel } from "@/lib/api/types";

/**
 * 图片生成参数的纯数据与纯函数（审计 F-中5）：
 * 宽高比预设、模型尺寸能力表、切换模型时的尺寸回退。
 * 不依赖 React 与 UI 组件，供 useImageComposer 与 ImageComposer 共享，
 * 避免 hook 反向依赖页面组件。
 *
 * 能力语义与后端 `utils/image_size.py` 的 `IMAGE_SIZE_CAPABILITIES` 一一对应，
 * 依据是工作区 `docs/size-verification.md` 的 103 条真实出图实测。两侧必须同步修改。
 */

/** 一个宽高比预设：ratio/tier 为持久化选项，width/height 为提交给后端的 size */
export type AspectOption = {
  ratio: string;
  tier: string;
  width: string;
  height: string;
  label: string;
  /** 该档位实际兑现的是什么，用于 UI 说明文案 */
  note: string;
};

/**
 * 单个模型对尺寸请求的遵循能力（与后端能力表逐字段对应）。
 * - `apiSizeEffective`：提交的 `size` 能否决定出图宽高比；
 * - `promptSizeEffective`：提示词里写出的尺寸/比例能否决定出图宽高比。
 *
 * 两条通道都不兑现绝对像素：所有模型出图面积恒定约 1.57M 像素。
 */
export type ImageSizeCapability = {
  apiSizeEffective: boolean;
  promptSizeEffective: boolean;
};

/** 后端 `utils/image_size.py` 的镜像：键为去掉 plus-/team-/pro- 前缀的基础模型名 */
export const IMAGE_MODEL_SIZE_CAPABILITIES: Record<string, ImageSizeCapability> = {
  "gpt-image-2": { apiSizeEffective: true, promptSizeEffective: true },
  "codex-gpt-image-2": { apiSizeEffective: false, promptSizeEffective: true },
  "codex-gpt-image-2.5-flare": { apiSizeEffective: false, promptSizeEffective: true },
  "codex-gpt-image-2.5-sunburst": { apiSizeEffective: false, promptSizeEffective: true },
};

const PLAN_PREFIXES = ["plus-", "team-", "pro-"];

/** 去掉 plus-/team-/pro- 套餐前缀（对应后端 `utils.helper.split_image_model`） */
export function baseImageModel(model: ImageModel): string {
  const normalized = String(model || "").toLowerCase().trim();
  const prefix = PLAN_PREFIXES.find((item) => normalized.startsWith(item));
  return prefix ? normalized.slice(prefix.length) : normalized;
}

/** 返回模型的尺寸能力；非图片模型返回 null */
export function imageSizeCapability(model: ImageModel): ImageSizeCapability | null {
  return IMAGE_MODEL_SIZE_CAPABILITIES[baseImageModel(model)] ?? null;
}

/** 提交的 `size` 是否对该模型生效 */
export function modelUsesApiSize(model: ImageModel): boolean {
  return imageSizeCapability(model)?.apiSizeEffective ?? false;
}

/** 尺寸意图是否必须写进提示词（codex 系列唯一有效通道） */
export function modelUsesPromptSize(model: ImageModel): boolean {
  return imageSizeCapability(model)?.promptSizeEffective ?? false;
}

/** 所有模型统一的出图面积（实测恒定 1,572,864 px = 1024×1536） */
export const NORMALIZED_OUTPUT_AREA_PX = 1_572_864;

/** 出图面积的中文近似说法，用于 UI 说明 */
export const NORMALIZED_OUTPUT_AREA_LABEL = "约 1.57M 像素";

export const aspectOptions: readonly AspectOption[] = [
  { ratio: "1:1", tier: "1k", width: "1024", height: "1024", label: "1:1", note: "方形" },
  { ratio: "2:3", tier: "1k", width: "1024", height: "1536", label: "2:3", note: "竖版" },
  { ratio: "3:2", tier: "1k", width: "1536", height: "1024", label: "3:2", note: "横版" },
  { ratio: "3:4", tier: "1k", width: "1024", height: "1365", label: "3:4", note: "竖版" },
  { ratio: "4:3", tier: "1k", width: "1365", height: "1024", label: "4:3", note: "横版" },
  { ratio: "9:16", tier: "1k", width: "1088", height: "1920", label: "9:16", note: "竖版" },
  { ratio: "16:9", tier: "1k", width: "1920", height: "1088", label: "16:9", note: "横版" },
  { ratio: "1:1", tier: "2k", width: "2048", height: "2048", label: "1:1(2k)", note: "方形" },
  { ratio: "16:9", tier: "2k", width: "2560", height: "1440", label: "16:9(2k)", note: "横版" },
  { ratio: "9:16", tier: "2k", width: "1440", height: "2560", label: "9:16(2k)", note: "竖版" },
  { ratio: "16:9", tier: "4k", width: "3840", height: "2160", label: "16:9(4k)", note: "横版" },
  { ratio: "9:16", tier: "4k", width: "2160", height: "3840", label: "9:16(4k)", note: "竖版" },
  { ratio: "auto", tier: "auto", width: "1024", height: "1024", label: "auto", note: "由模型决定" },
];

/**
 * 该比例档位在给定模型下是否可选。
 *
 * 实测结论（size-verification.md §5、§7）：
 * - codex 系列完全无视 `size`，整组比例选择器都应置灰（方向由提示词决定）；
 * - 2K/4K 对**所有**模型都只兑现比例、不兑现像素，因此整组置灰，
 *   避免用户以为能出 2K/4K 像素。
 */
export function isAspectOptionDisabled(model: ImageModel, option: AspectOption): boolean {
  if (option.tier === "auto") {
    return false;
  }
  if (!modelUsesApiSize(model)) {
    return true;
  }
  return option.tier !== "1k";
}

/** 当前模型下可选的档位列表（供 UI 与回退逻辑共用） */
export function selectableAspectOptions(model: ImageModel): readonly AspectOption[] {
  return aspectOptions.filter((option) => !isAspectOptionDisabled(model, option));
}

/**
 * 该档位在当前模型下的说明文案；返回 null 表示无需额外提示。
 * 文案直接对应用户能观察到的事实，不做「支持/不支持」的含糊表述。
 */
export function aspectOptionNote(model: ImageModel, option: AspectOption): string | null {
  if (option.tier === "auto") {
    return null;
  }
  if (!modelUsesApiSize(model)) {
    return "该模型不支持尺寸参数，出图方向由提示词决定";
  }
  if (option.tier !== "1k") {
    return `2K/4K 只影响比例，实际约 ${NORMALIZED_OUTPUT_AREA_LABEL}`;
  }
  return null;
}

/**
 * 切换模型时收敛当前档位到新模型可用的档位。
 *
 * - codex 系列不接受 `size`：统一落到 `auto`（不再伪造一个无效尺寸）；
 * - picture_v2：2K/4K 回退到同比例 1K 档，无匹配则回 auto。
 *
 * @returns null 表示当前档位在新模型下仍可用，无需调整
 */
export function aspectFallbackForModel(
  model: ImageModel,
  ratio: string,
  tier: string,
): AspectOption | null {
  if (tier === "auto") {
    return null;
  }
  if (!modelUsesApiSize(model)) {
    return aspectOptions.find((option) => option.tier === "auto") ?? null;
  }
  if (tier === "1k") {
    return null;
  }
  return (
    aspectOptions.find((option) => option.tier === "1k" && option.ratio === ratio) ??
    aspectOptions.find((option) => option.tier === "auto") ??
    null
  );
}

/**
 * 生成提交给后端的 size 字符串。
 *
 * 模型不接受 `size` 时返回 `undefined`（不提交该字段，而不是提交一个无效值）。
 * 接受 `size` 时按当前 W/H 提交：`auto` 档位同样使用输入框里的值，
 * 因此用户手动改过宽高后不会因为没选比例档而丢失。
 */
export function resolveRequestSize(
  model: ImageModel,
  width: string,
  height: string,
): string | undefined {
  if (!modelUsesApiSize(model)) {
    return undefined;
  }
  return `${width || 1024}x${height || 1024}`;
}
