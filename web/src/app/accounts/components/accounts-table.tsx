"use client";

import { ChevronLeft, ChevronRight, Copy, LoaderCircle, LogIn, Pencil, RefreshCw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { statusMeta } from "@/app/accounts/components/status-meta";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { displayAccountSource, displayAccountType, formatQuota, formatRestoreAt, maskToken } from "@/lib/account-format";
import type { Account } from "@/lib/api/accounts";
import { cn } from "@/lib/utils";

type AccountsPaginationProps = {
  total: number;
  startIndex: number;
  page: number;
  pageCount: number;
  pageSize: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: string) => void;
};

// 分页器：页码窗口 ±1 + 首尾页与省略号；页数据切片由 use-pagination 提供
function AccountsPagination({ total, startIndex, page, pageCount, pageSize, onPageChange, onPageSizeChange }: AccountsPaginationProps) {
  const paginationItems = (() => {
    const items: (number | "...")[] = [];
    const start = Math.max(1, page - 1);
    const end = Math.min(pageCount, page + 1);

    if (start > 1) items.push(1);
    if (start > 2) items.push("...");
    for (let current = start; current <= end; current += 1) items.push(current);
    if (end < pageCount - 1) items.push("...");
    if (end < pageCount) items.push(pageCount);

    return items;
  })();

  return (
    <div className="border-t border-stone-100 px-4 py-4">
      <div className="flex items-center justify-center gap-3 overflow-x-auto whitespace-nowrap">
        <div className="shrink-0 text-sm text-stone-500">
          显示第 {total === 0 ? 0 : startIndex + 1} -{" "}
          {Math.min(startIndex + Number(pageSize), total)} 条，共{" "}
          {total} 条
        </div>

        <span className="shrink-0 text-sm leading-none text-stone-500">
          {page} / {pageCount} 页
        </span>
        <Select
          value={pageSize}
          onValueChange={onPageSizeChange}
        >
          <SelectTrigger className="h-10 w-[108px] shrink-0 rounded-lg border-stone-200 bg-white text-sm leading-none">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="10">10 / 页</SelectItem>
            <SelectItem value="20">20 / 页</SelectItem>
            <SelectItem value="50">50 / 页</SelectItem>
            <SelectItem value="100">100 / 页</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="icon"
          className="size-10 shrink-0 rounded-lg border-stone-200 bg-white"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="size-4" />
        </Button>
        {paginationItems.map((item, index) =>
          item === "..." ? (
            <span key={`ellipsis-${index}`} className="px-1 text-sm text-stone-400">
              ...
            </span>
          ) : (
            <Button
              key={item}
              variant={item === page ? "default" : "outline"}
              className={cn(
                "h-10 min-w-10 shrink-0 rounded-lg px-3",
                item === page
                  ? "bg-stone-950 text-white hover:bg-stone-800"
                  : "border-stone-200 bg-white text-stone-700",
              )}
              onClick={() => onPageChange(item)}
            >
              {item}
            </Button>
          ),
        )}
        <Button
          variant="outline"
          size="icon"
          className="size-10 shrink-0 rounded-lg border-stone-200 bg-white"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

type AccountsTableProps = {
  rows: Account[];
  selectedIds: string[];
  allCurrentSelected: boolean;
  selectedTokens: string[];
  abnormalTokens: string[];
  refreshingTokens: Set<string>;
  isRefreshing: boolean;
  isRelogining: boolean;
  isDeleting: boolean;
  isUpdating: boolean;
  onToggleAll: (checked: boolean) => void;
  onToggleRow: (token: string, checked: boolean) => void;
  onRefreshTokens: (tokens: string[]) => void;
  onReLogin: (tokens: string[]) => void;
  onDeleteTokens: (tokens: string[]) => void;
  onEdit: (account: Account) => void;
  pagination: AccountsPaginationProps;
};

// 账号表格卡片：批量操作条、表格主体、空状态与底部分页器
export function AccountsTable({
  rows,
  selectedIds,
  allCurrentSelected,
  selectedTokens,
  abnormalTokens,
  refreshingTokens,
  isRefreshing,
  isRelogining,
  isDeleting,
  isUpdating,
  onToggleAll,
  onToggleRow,
  onRefreshTokens,
  onReLogin,
  onDeleteTokens,
  onEdit,
  pagination,
}: AccountsTableProps) {
  return (
    <Card className="overflow-hidden rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-0 p-0">
        <div className="flex flex-col gap-3 border-b border-stone-100 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2 text-sm text-stone-500">
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-stone-500 hover:bg-stone-100"
              onClick={() => onRefreshTokens(selectedTokens)}
              disabled={selectedTokens.length === 0 || isRefreshing}
            >
              {isRefreshing ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              刷新选中账号信息和额度
            </Button>
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-amber-600 hover:bg-amber-50 hover:text-amber-700"
              onClick={() => onReLogin(selectedTokens)}
              disabled={selectedTokens.length === 0 || isRelogining}
              title="尝试密码登录恢复账号"
            >
              {isRelogining ? <LoaderCircle className="size-4 animate-spin" /> : <LogIn className="size-4" />}
              尝试恢复异常账号
            </Button>
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-rose-500 hover:bg-rose-50 hover:text-rose-600"
              onClick={() => onDeleteTokens(abnormalTokens)}
              disabled={abnormalTokens.length === 0 || isDeleting}
            >
              {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              移除异常账号
            </Button>
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-rose-500 hover:bg-rose-50 hover:text-rose-600"
              onClick={() => onDeleteTokens(selectedTokens)}
              disabled={selectedTokens.length === 0 || isDeleting}
            >
              {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              删除所选
            </Button>
            {selectedIds.length > 0 ? (
              <span className="rounded-lg bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-600">
                已选择 {selectedIds.length} 项
              </span>
            ) : null}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-left">
            <thead className="border-b border-stone-100 text-[11px] text-stone-400 uppercase tracking-[0.18em]">
              <tr>
                <th className="w-12 px-4 py-3">
                  <Checkbox
                    checked={allCurrentSelected}
                    onCheckedChange={(checked) => onToggleAll(Boolean(checked))}
                  />
                </th>
                <th className="w-56 px-4 py-3">token</th>
                <th className="w-28 px-4 py-3">类型</th>
                <th className="w-24 px-4 py-3">来源</th>
                <th className="w-24 px-4 py-3">状态</th>
                <th className="w-56 px-4 py-3">账号信息</th>
                <th className="w-32 px-4 py-3">创建时间</th>
                <th className="w-24 px-4 py-3">额度</th>
                <th className="w-40 px-4 py-3">恢复时间</th>
                <th className="w-18 px-4 py-3">在途</th>
                <th className="w-18 px-4 py-3">成功</th>
                <th className="w-18 px-4 py-3">失败</th>
                <th className="w-24 px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((account) => {
                const status = statusMeta[account.status];
                const StatusIcon = status.icon;

                return (
                  <tr
                    key={account.access_token}
                    className="border-b border-stone-100/80 text-sm text-stone-600 transition-colors hover:bg-stone-50/70"
                  >
                    <td className="px-4 py-3">
                      <Checkbox
                        checked={selectedIds.includes(account.access_token)}
                        onCheckedChange={(checked) => onToggleRow(account.access_token, Boolean(checked))}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium tracking-tight text-stone-700">
                          {maskToken(account.access_token)}
                        </span>
                        <button
                          type="button"
                          className="rounded-lg p-1 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700"
                          onClick={() => {
                            void navigator.clipboard.writeText(account.access_token);
                            toast.success("token 已复制");
                          }}
                        >
                          <Copy className="size-4" />
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary" className="rounded-md bg-stone-100 text-stone-700">
                        {displayAccountType(account)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="rounded-md border-stone-200 text-stone-600">
                        {displayAccountSource(account)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={status.badge}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1"
                      >
                        <StatusIcon className="size-3.5" />
                        {account.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs leading-5 text-stone-500">{account.email ?? "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-xs leading-5 text-stone-500">
                      {formatCreatedAt(account.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="info" className="rounded-md">
                        {formatQuota(account)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs leading-5 text-stone-500">
                      {(() => {
                        const restore = formatRestoreAt(account.restore_at);
                        return (
                          <div className="space-y-0.5">
                            {restore.relative ? <div className="font-medium text-stone-700">{restore.relative}</div> : null}
                            <div>{restore.absolute}</div>
                          </div>
                        );
                      })()}
                    </td>
                    <td className="px-4 py-3">
                      {(() => {
                        const inflight = account.image_inflight ?? 0;
                        return (
                          <span
                            className={
                              inflight > 0
                                ? "font-semibold text-amber-600"
                                : "text-stone-400"
                            }
                            title={
                              inflight > 0
                                ? "当前正在生成的图片数。号池空闲时此值持续 > 0，说明并发槽位泄漏、该账号已被静默排除出调度"
                                : "当前无在途生图任务"
                            }
                          >
                            {inflight}
                          </span>
                        );
                      })()}
                    </td>
                    <td className="px-4 py-3 text-stone-500">{account.success}</td>
                    <td className="px-4 py-3 text-stone-500">{account.fail}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-stone-400">
                        <button
                          type="button"
                          className="rounded-lg p-2 transition hover:bg-stone-100 hover:text-stone-700"
                          onClick={() => onEdit(account)}
                          disabled={isUpdating}
                        >
                          <Pencil className="size-4" />
                        </button>
                        <button
                          type="button"
                          className="rounded-lg p-2 transition hover:bg-stone-100 hover:text-stone-700"
                          onClick={() => onRefreshTokens([account.access_token])}
                          disabled={isRefreshing || refreshingTokens.has(account.access_token)}
                        >
                          <RefreshCw className={cn("size-4", (isRefreshing || refreshingTokens.has(account.access_token)) ? "animate-spin" : "")} />
                        </button>
                        <button
                          type="button"
                          className="rounded-lg p-2 transition hover:bg-rose-50 hover:text-rose-500"
                          onClick={() => onDeleteTokens([account.access_token])}
                          disabled={isDeleting}
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {rows.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
              <div className="rounded-xl bg-stone-100 p-3 text-stone-500">
                <Search className="size-5" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-stone-700">没有匹配的账户</p>
                <p className="text-sm text-stone-500">调整筛选条件或搜索关键字后重试。</p>
              </div>
            </div>
          ) : null}
        </div>

        <AccountsPagination {...pagination} />
      </CardContent>
    </Card>
  );
}

// 创建时间展示：后端返回 UTC 无时区后缀，补 "Z" 后本地化；解析失败回退为原始日期部分
function formatCreatedAt(raw?: string | null) {
  if (!raw) return "—";
  try {
    const date = new Date(raw + "Z");
    if (isNaN(date.getTime())) return String(raw).slice(0, 10);
    return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return String(raw).slice(0, 10);
  }
}
