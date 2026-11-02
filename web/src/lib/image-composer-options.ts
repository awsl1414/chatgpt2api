import type { ImageModel } from "@/lib/api/types";

/**
 * 图片生成参数的纯数据与纯函数（审计 F-中5）：
 * 宽高比预设、模型尺寸能力表、尺寸档位的说明文案。
 * 不依赖 React 与 UI 组件，供 useImageComposer 与 ImageComposer 共享，
 * 避免 hook 反向依赖页面组件。
 *
 * 能力语义与后端 `utils/image_size.py` 的 `IMAGE_SIZE_CAPABILITIES` 一一对应，
 * 依据是工作区 `docs/size-verification.md` 的 103 条真实出图实测。两侧必须同步修改。
 *
 * 核心事实（决定这里所有规则）：
 * - **比例对所有模型都有效**：请求的尺寸/比例由服务端写进提示词，四个已测模型
 *   都会按该比例出图（§4.3、§5 逐档验证）；
 * - **绝对像素对所有模型都无效**：出图面积恒定约 1.57M 像素（§8.3）；
 * - **接口 `size` 只在 picture_v2 生效**：picture_v2 精确跟随（§5）；
 *   codex 系列的 `tools[0].size` 收到但被完全忽略（§3），其比例只能靠提示词。
 *
 * 因此：**没有任何比例档位应该被置灰**——比例是真能兑现的能力。2K/4K 档位
 * 需要标注的只是「像素不兑现」，不是禁用。方向词的注入策略属于后端决策
 * （见 `utils/image_size.py`），前端只负责把尺寸如实提交。
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
 * 单个模型对尺寸请求的遵循能力（与后端 `ImageSizeCapability` 逐字段对应）。
 * - `apiSizeEffective`：请求的 `size` 字段能否决定出图宽高比
 *   （picture_v2 为 true；codex 系列为 false，其 `tools[0].size` 被上游忽略）；
 * - `promptSizeEffective`：提示词里的尺寸/比例能否决定出图宽高比（所有已测模型为 true），
 *   前端据此决定比例选择器是否可用与说明文案。
 *
 * 两者都不代表绝对像素可兑现：出图面积恒约 1.57M 像素。
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

/** 请求 `size` 字段对该模型是否生效（picture_v2 为 true，codex 系列为 false） */
export function modelUsesApiSize(model: ImageModel): boolean {
  return imageSizeCapability(model)?.apiSizeEffective ?? false;
}

/** 提示词里的比例对该模型是否有效（所有已测图片模型均为 true） */
export function modelUsesPromptSize(model: ImageModel): boolean {
  return imageSizeCapability(model)?.promptSizeEffective ?? false;
}

/** 出图面积的中文近似说法，用于 UI 说明（实测所有模型恒定约 1.57M 像素 = 1024×1536） */
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
 * 该档位在当前模型下的说明文案；返回 null 表示无需额外提示。
 * 文案直接对应用户能观察到的事实：比例兑现，像素不兑现。
 *
 * 注意：**没有任何档位需要置灰**。比例是实测中所有模型都稳定兑现的能力
 * （服务端把请求尺寸写成提示词里的比例语句），2K/4K 的差异只是绝对像素
 * 不兑现——那是标注问题，不是可用性问题。
 */
export function aspectOptionNote(_model: ImageModel, option: AspectOption): string | null {
  if (option.tier === "auto" || option.tier === "1k") {
    return null;
  }
  // 2K/4K 档位：比例精确兑现，但绝对像素恒为 1.57M（§5 实测）
  return `${option.ratio} 比例有效，实际输出 ${NORMALIZED_OUTPUT_AREA_LABEL}（不兑现 ${option.tier.toUpperCase()} 像素）`;
}

/**
 * 生成提交给后端的 size 字符串。
 *
 * 所有模型都提交：请求 `size` 由服务端统一写进提示词，是唯一被证实的比例通道。
 * 即便 codex 的上游工具字段会忽略它，后端仍需要这个值来构造提示词——
 * 不提交等于放弃比例控制。
 */
export function resolveRequestSize(
  _model: ImageModel,
  width: string,
  height: string,
): string {
  return `${width || 1024}x${height || 1024}`;
}
