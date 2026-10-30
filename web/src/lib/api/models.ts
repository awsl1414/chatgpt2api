import { httpRequest } from "@/lib/api/client";
import type { ImageModel } from "@/lib/api/types";

export type Model = {
  id: string;
  object: string;
  created: number;
  owned_by: string;
  permission: unknown[];
  root: string;
  parent: string | null;
};

type ModelListResponse = {
  object: string;
  data: Model[];
};

export async function fetchModels() {
  return httpRequest<ModelListResponse>("/v1/models");
}

// 对应后端 utils/helper.is_codex_image_model：codex-gpt-image-2 走 Codex 通道
export function isCodexImageModel(model: ImageModel) {
  return model.toLowerCase().includes("codex");
}

// codex-gpt-image-* 公开模型名 → 展示名（对应上游工具层模型 ID = 去掉 "codex-" 前缀）
const PLAN_PREFIXES = ["plus-", "team-", "pro-"];

function baseImageModelLabel(base: string): string | null {
  const codexMatch = base.match(/^codex-gpt-image-([\d.]+)(?:-(\w+))?$/);
  if (codexMatch) {
    const variant = codexMatch[2] ? ` ${codexMatch[2][0].toUpperCase()}${codexMatch[2].slice(1)}` : "";
    // codex 与官网通道同ID不同名，必须保留 Codex 标识以区分两条生图链路
    return `GPT Image ${codexMatch[1]}${variant} (Codex)`;
  }
  if (base === "gpt-image-2") {
    return "GPT Image 2";
  }
  return null;
}

// plus-/team-/pro- 前缀表示锁定对应套餐的账号池，展示时以角标形式保留
export function imageModelLabel(model: ImageModel): string {
  const normalized = model.toLowerCase();
  const planPrefix = PLAN_PREFIXES.find((prefix) => normalized.startsWith(prefix));
  const base = planPrefix ? normalized.slice(planPrefix.length) : normalized;
  const label = baseImageModelLabel(base);
  if (!label) {
    return model;
  }
  return planPrefix ? `${planPrefix.slice(0, -1).toUpperCase()} · ${label}` : label;
}
