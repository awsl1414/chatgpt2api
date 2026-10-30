/**
 * 图片页 localStorage / sessionStorage key 常量（审计 F-低4）。
 * 所有 key 统一以 "chatgpt2api:image_" 为前缀，集中在此模块管理，避免魔法字符串散落。
 */

/** 最近一次选中的图片会话 ID（localStorage） */
export const ACTIVE_CONVERSATION_STORAGE_KEY = "chatgpt2api:image_active_conversation_id";
/** 最近一次使用的宽高比（localStorage） */
export const IMAGE_RATIO_STORAGE_KEY = "chatgpt2api:image_last_ratio";
/** 最近一次使用的清晰度档位（localStorage） */
export const IMAGE_TIER_STORAGE_KEY = "chatgpt2api:image_last_tier";
/** 最近一次使用的质量（localStorage） */
export const IMAGE_QUALITY_STORAGE_KEY = "chatgpt2api:image_last_quality";
/** 最近一次使用的模型（localStorage） */
export const IMAGE_MODEL_STORAGE_KEY = "chatgpt2api:image_last_model";
/** 最近一次使用的生成数量（localStorage） */
export const IMAGE_COUNT_STORAGE_KEY = "chatgpt2api:image_last_count";
/** 各会话滚动位置（sessionStorage） */
export const SCROLL_POSITIONS_STORAGE_KEY = "chatgpt2api:image_scroll_positions";
