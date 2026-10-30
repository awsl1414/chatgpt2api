"use client";

// 账号页状态徽标的图标与配色映射，以及状态下拉选项（过滤器与编辑 Dialog 共用）
import type { ComponentProps } from "react";
import { Ban, CheckCircle2, CircleAlert, CircleOff } from "lucide-react";

import type { Badge } from "@/components/ui/badge";
import type { AccountStatus } from "@/lib/api/accounts";

export const accountStatusOptions: { label: string; value: AccountStatus | "all" }[] = [
  { label: "全部状态", value: "all" },
  { label: "正常", value: "正常" },
  { label: "限流", value: "限流" },
  { label: "异常", value: "异常" },
  { label: "禁用", value: "禁用" },
];

export const statusMeta: Record<
  AccountStatus,
  {
    icon: typeof CheckCircle2;
    badge: ComponentProps<typeof Badge>["variant"];
  }
> = {
  正常: { icon: CheckCircle2, badge: "success" },
  限流: { icon: CircleAlert, badge: "warning" },
  异常: { icon: CircleOff, badge: "danger" },
  禁用: { icon: Ban, badge: "secondary" },
};
