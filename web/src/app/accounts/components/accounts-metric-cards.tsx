"use client";

import { Ban, CheckCircle2, CircleAlert, CircleOff, RefreshCw, UserRound } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatCompact } from "@/lib/account-format";
import { cn } from "@/lib/utils";

// 统计卡片的 key 与汇总对象的字段一一对应（quota 为格式化后的字符串，其余为数字）
export type MetricKey = "total" | "active" | "limited" | "abnormal" | "disabled" | "quota";

const metricCards: {
  key: MetricKey;
  label: string;
  color: string;
  icon: typeof UserRound;
}[] = [
  { key: "total", label: "账户总数", color: "text-stone-900", icon: UserRound },
  { key: "active", label: "正常账户", color: "text-emerald-600", icon: CheckCircle2 },
  { key: "limited", label: "限流账户", color: "text-orange-500", icon: CircleAlert },
  { key: "abnormal", label: "异常账户", color: "text-rose-500", icon: CircleOff },
  { key: "disabled", label: "禁用账户", color: "text-stone-500", icon: Ban },
  { key: "quota", label: "剩余额度", color: "text-blue-500", icon: RefreshCw },
];

type AccountsMetricCardsProps = {
  /** 展示值：静态汇总或刷新过程中的实时联动值（由调用方合并后传入） */
  summary: Record<MetricKey, number | string>;
};

// 号池统计卡片区：总数 / 各状态分布 / 剩余额度
export function AccountsMetricCards({ summary }: AccountsMetricCardsProps) {
  return (
    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
      {metricCards.map((item) => {
        const Icon = item.icon;
        const value = summary[item.key];
        return (
          <Card key={item.key} className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
            <CardContent className="p-4">
              <div className="mb-4 flex items-start justify-between">
                <span className="text-xs font-medium text-stone-400">{item.label}</span>
                <Icon className="size-4 text-stone-400" />
              </div>
              <div className={cn("text-[1.75rem] font-semibold tracking-tight", item.color)}>
                <span className={typeof value === "number" ? "" : "text-[1.1rem]"}>
                  {typeof value === "number" ? formatCompact(value) : value}
                </span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
