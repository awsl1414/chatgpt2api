"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle, Search } from "lucide-react";
import { toast } from "sonner";

import { AccountEditDialog } from "@/app/accounts/components/account-edit-dialog";
import { AccountsMetricCards, type MetricKey } from "@/app/accounts/components/accounts-metric-cards";
import { AccountsTable } from "@/app/accounts/components/accounts-table";
import { AccountsToolbar } from "@/app/accounts/components/accounts-toolbar";
import { accountStatusOptions } from "@/app/accounts/components/status-meta";
import { initialProgressState, ProgressBanner, type ProgressState } from "@/app/accounts/components/progress-banner";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePagination } from "@/hooks/use-pagination";
import { useProgressPolling } from "@/hooks/use-progress-polling";
import { formatCompact, formatQuotaSummary } from "@/lib/account-format";
import {
  deleteAccounts,
  fetchAccounts,
  fetchRefreshProgress,
  fetchReLoginProgress,
  reLoginAccounts,
  refreshAccounts,
  updateAccount,
  type Account,
  type AccountStatus,
} from "@/lib/api/accounts";
import { fetchModels, type Model } from "@/lib/api/models";
import { useAuthGuard } from "@/lib/use-auth-guard";

// 导出全部 Token：纯 DOM 下载行为，不参与渲染
function downloadTokens(accounts: Account[]) {
  const content = `${accounts.map((account) => account.access_token).join("\n")}\n`;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `accounts-${Date.now()}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

function displayAccountType(account: Account) {
  return account.type || "Free";
}

function AccountsPageContent() {
  const didLoadRef = useRef(false);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [availableModels, setAvailableModels] = useState<Model[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<AccountStatus | "all">("all");
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshingTokens, setRefreshingTokens] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRelogining, setIsRelogining] = useState(false);
  const [progress, setProgress] = useState<ProgressState>(initialProgressState);
  const [refreshSummary, setRefreshSummary] = useState<Record<MetricKey, number | string> | null>(null);

  const { poll, wait } = useProgressPolling();

  const loadAccounts = async (silent = false) => {
    if (!silent) {
      setIsLoading(true);
    }
    try {
      const data = await fetchAccounts();
      setAccounts(data.items);
      setSelectedIds((prev) => prev.filter((id) => data.items.some((item) => item.access_token === id)));
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载账户失败";
      toast.error(message);
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  };

  const loadModels = async () => {
    setIsLoadingModels(true);
    try {
      const data = await fetchModels();
      setAvailableModels(Array.isArray(data.data) ? data.data : []);
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载模型列表失败";
      toast.error(message);
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    if (didLoadRef.current) {
      return;
    }
    didLoadRef.current = true;
    void loadAccounts();
    void loadModels();
  }, []);

  const filteredAccounts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return accounts.filter((account) => {
      const searchMatched =
        normalizedQuery.length === 0 || (account.email ?? "").toLowerCase().includes(normalizedQuery);
      const typeMatched = typeFilter === "all" || displayAccountType(account) === typeFilter;
      const statusMatched = statusFilter === "all" || account.status === statusFilter;
      return searchMatched && typeMatched && statusMatched;
    });
  }, [accounts, query, statusFilter, typeFilter]);

  const pagination = usePagination(filteredAccounts);
  const { pageItems: currentRows } = pagination;

  const allCurrentSelected =
    currentRows.length > 0 && currentRows.every((row) => selectedIds.includes(row.access_token));

  const summary = useMemo(() => {
    const total = accounts.length;
    const active = accounts.filter((item) => item.status === "正常").length;
    const limited = accounts.filter((item) => item.status === "限流").length;
    const abnormal = accounts.filter((item) => item.status === "异常").length;
    const disabled = accounts.filter((item) => item.status === "禁用").length;
    const quota = formatQuotaSummary(accounts);

    return { total, active, limited, abnormal, disabled, quota };
  }, [accounts]);

  const accountTypeOptions = useMemo(
    () => [
      { label: "全部类型", value: "all" },
      ...Array.from(new Set(accounts.map(displayAccountType))).map((type) => ({ label: type, value: type })),
    ],
    [accounts],
  );

  const selectedTokens = useMemo(() => {
    const selectedSet = new Set(selectedIds);
    return accounts.filter((item) => selectedSet.has(item.access_token)).map((item) => item.access_token);
  }, [accounts, selectedIds]);

  const abnormalTokens = useMemo(() => {
    return accounts.filter((item) => item.status === "异常").map((item) => item.access_token);
  }, [accounts]);

  const handleDeleteTokens = async (tokens: string[]) => {
    if (tokens.length === 0) {
      toast.error("请先选择要删除的账户");
      return;
    }

    setIsDeleting(true);
    try {
      const data = await deleteAccounts(tokens);
      setAccounts(data.items);
      setSelectedIds((prev) => prev.filter((id) => data.items.some((item) => item.access_token === id)));
      toast.success(`删除 ${data.removed ?? 0} 个账户`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除账户失败";
      toast.error(message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRefreshAccounts = async (accessTokens: string[]) => {
    if (accessTokens.length === 0) {
      toast.error("没有需要刷新的账户");
      return;
    }

    if (accessTokens.length === 1) {
      setRefreshingTokens((prev) => new Set([...prev, accessTokens[0]]));
      try {
        const { progress_id } = await refreshAccounts(accessTokens);
        // 单账号：轮询等待完成，落库结果在完成回调中应用
        await poll(() => fetchRefreshProgress(progress_id), {
          intervalMs: 500,
          onUpdate: (p) => {
            if (p.done && p.result) {
              setAccounts(p.result.items);
              setSelectedIds((prev) =>
                prev.filter((id) => p.result!.items.some((item) => item.access_token === id)),
              );
            }
          },
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "刷新账户失败";
        toast.error(message);
      } finally {
        setRefreshingTokens((prev) => {
          const next = new Set(prev);
          next.delete(accessTokens[0]);
          return next;
        });
      }
      return;
    }

    setIsRefreshing(true);

    // 计算非选中账号的基数（统计卡片联动用）
    const selectedTokenSet = new Set(accessTokens);
    const baseAccountsList = accounts.filter((a) => !selectedTokenSet.has(a.access_token));
    const baseActive = baseAccountsList.filter((a) => a.status === "正常").length;
    const baseLimited = baseAccountsList.filter((a) => a.status === "限流").length;
    const baseAbnormal = baseAccountsList.filter((a) => a.status === "异常").length;
    const baseDisabled = baseAccountsList.filter((a) => a.status === "禁用").length;
    const baseQuotaNum = baseAccountsList
      .filter((a) => a.status === "正常")
      .reduce((s, a) => s + Math.max(0, a.quota), 0);

    // 显示进度条（只显示当前任务，不含分类统计）
    const total = accessTokens.length;
    setProgress({ visible: true, current: 0, total, message: "正在刷新账号信息...", email: "" });

    try {
      const { progress_id } = await refreshAccounts(accessTokens);

      const data = await poll(() => fetchRefreshProgress(progress_id), {
        intervalMs: 300,
        onUpdate: (p) => {
          // 实时更新进度与统计卡片：基数 + 已刷新的累加结果
          setProgress((prev) => ({ ...prev, current: p.processed }));
          setRefreshSummary({
            total: accounts.length,
            active: baseActive + ((p.status_counts?.["正常"]) ?? 0),
            limited: baseLimited + ((p.status_counts?.["限流"]) ?? 0),
            abnormal: baseAbnormal + ((p.status_counts?.["异常"]) ?? 0),
            disabled: baseDisabled + ((p.status_counts?.["禁用"]) ?? 0),
            quota: formatCompact(baseQuotaNum + (p.total_quota ?? 0)),
          });
        },
      });

      if (!data.result) {
        throw new Error("刷新结果为空");
      }

      // 刷新完成，更新数据与进度展示
      setProgress((prev) => ({ ...prev, current: prev.total, message: "刷新完成" }));
      setRefreshSummary(null);
      const items = data.result.items;
      setAccounts(items);
      setSelectedIds((prev) => prev.filter((id) => items.some((item) => item.access_token === id)));

      const relogined = data.result.relogined ?? 0;
      if (relogined > 0) {
        // 后端 auto_relogin_after_refresh 在后台线程执行且没有进度接口（services/account/password_login.py
        // re_login_thread），这里只展示真实状态文本，不做本地计数模拟（审计 F-中6）
        setProgress({
          visible: true,
          current: total,
          total,
          message: `刷新完成，已触发 ${relogined} 个账号在后台重新登录`,
          email: "",
        });
      }
      void wait(800).then(() => setProgress(initialProgressState));

      if ((data.result.errors ?? []).length > 0) {
        const firstError = data.result.errors?.[0]?.error;
        toast.error(
          `刷新成功 ${data.result.refreshed} 个，失败 ${(data.result.errors ?? []).length} 个${firstError ? `，首个错误：${firstError}` : ""}`,
        );
      } else {
        toast.success(`刷新成功 ${data.result.refreshed} 个账户${relogined > 0 ? `，已触发 ${relogined} 个账号重新登录` : ""}`);
      }
    } catch (error) {
      setProgress(initialProgressState);
      setRefreshSummary(null);
      const message = error instanceof Error ? error.message : "刷新账户失败";
      toast.error(message);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleReLogin = async (accessTokens: string[]) => {
    if (accessTokens.length === 0) {
      toast.error("请先选择要恢复的账户");
      return;
    }

    // 只处理异常账号，过滤非异常账号
    const tokens = accessTokens.filter((token) => {
      const account = accounts.find((a) => a.access_token === token);
      return account?.status === "异常";
    });

    if (tokens.length === 0) {
      toast.error("选中账号中没有异常账号");
      return;
    }

    if (tokens.length < accessTokens.length) {
      toast.info(`已过滤 ${accessTokens.length - tokens.length} 个非异常账号`);
    }

    setIsRelogining(true);

    // 计算非选中账号的基数（统计卡片联动用）
    const selectedTokenSet = new Set(tokens);
    const baseAccountsList = accounts.filter((a) => !selectedTokenSet.has(a.access_token));
    const baseActive = baseAccountsList.filter((a) => a.status === "正常").length;
    const baseLimited = baseAccountsList.filter((a) => a.status === "限流").length;
    const baseAbnormal = baseAccountsList.filter((a) => a.status === "异常").length;
    const baseDisabled = baseAccountsList.filter((a) => a.status === "禁用").length;

    // 显示进度条（真实进度）
    const total = tokens.length;
    setProgress({ visible: true, current: 0, total, message: "正在尝试恢复异常账号...", email: "" });

    try {
      const { progress_id } = await reLoginAccounts(tokens);

      // 轮询进度到完成
      await poll(() => fetchReLoginProgress(progress_id), {
        intervalMs: 300,
        onUpdate: (p) => {
          const results = p.results ?? [];
          // 找到最新一条有错误的结果
          const lastErrorResult = [...results].reverse().find((r) => r.error);
          const emailHint = lastErrorResult
            ? `失败: ${lastErrorResult.token} ${lastErrorResult.error ?? ""}`
            : `已处理 ${p.processed}/${p.total}`;
          setProgress((prev) => ({
            ...prev,
            current: p.processed,
            email: emailHint,
            message: "正在尝试恢复异常账号...",
          }));

          // 实时更新统计卡片：基数 + 已处理的恢复结果
          let runningActive = baseActive;
          let runningAbnormal = baseAbnormal;
          let runningDisabled = baseDisabled;
          for (const r of results) {
            if (r.status === "成功") {
              runningActive += 1;
              runningAbnormal -= 1;
            } else if (r.status === "禁用") {
              runningDisabled += 1;
              runningAbnormal -= 1;
            }
            // "异常"或"跳过"：保持异常状态不变
          }
          setRefreshSummary({
            total: accounts.length,
            active: runningActive,
            limited: baseLimited,
            abnormal: runningAbnormal,
            disabled: runningDisabled,
            quota: summary.quota,
          });
        },
      });

      setProgress((prev) => ({ ...prev, current: prev.total, message: "恢复流程已完成" }));
      setRefreshSummary(null);

      // 等待后台线程完成，再拉取最新数据
      await wait(500);
      try {
        const freshData = await fetchAccounts();
        setAccounts(freshData.items);
        setSelectedIds((prev) => prev.filter((id) => freshData.items.some((item) => item.access_token === id)));
      } catch { /* 静默失败 */ }

      setProgress({ visible: true, current: total, total, message: "恢复完成", email: "" });
      void wait(800).then(() => setProgress(initialProgressState));

      toast.success(`恢复流程已全部完成`);
    } catch (error) {
      setProgress(initialProgressState);
      setRefreshSummary(null);
      const message = error instanceof Error ? error.message : "重新登录失败";
      toast.error(message);
    } finally {
      setIsRelogining(false);
    }
  };

  const handleUpdateAccount = async (updates: { status: AccountStatus; proxy: string }) => {
    if (!editingAccount) {
      return;
    }

    setIsUpdating(true);
    try {
      const data = await updateAccount(editingAccount.access_token, {
        status: updates.status,
        proxy: updates.proxy,
      });
      setAccounts(data.items);
      setSelectedIds((prev) => prev.filter((id) => data.items.some((item) => item.access_token === id)));
      setEditingAccount(null);
      toast.success("账号信息已更新");
    } catch (error) {
      const message = error instanceof Error ? error.message : "更新账号失败";
      toast.error(message);
    } finally {
      setIsUpdating(false);
    }
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...currentRows.map((item) => item.access_token)])));
      return;
    }
    setSelectedIds((prev) => prev.filter((id) => !currentRows.some((row) => row.access_token === id)));
  };

  const toggleSelectRow = (token: string, checked: boolean) => {
    setSelectedIds((prev) =>
      checked ? Array.from(new Set([...prev, token])) : prev.filter((item) => item !== token),
    );
  };

  return (
    <>
      <AccountsToolbar
        accounts={accounts}
        isLoading={isLoading}
        isRefreshing={isRefreshing}
        isDeleting={isDeleting}
        onLoadAccounts={() => void loadAccounts()}
        onRefreshAll={() => void handleRefreshAccounts(accounts.map((item) => item.access_token))}
        onExportTokens={() => downloadTokens(accounts)}
        onImported={(items) => {
          setAccounts(items);
          setSelectedIds([]);
          pagination.resetPage();
        }}
      />

      <ProgressBanner progress={progress} />

      {editingAccount && (
        <AccountEditDialog
          key={editingAccount.access_token}
          account={editingAccount}
          isUpdating={isUpdating}
          onClose={() => setEditingAccount(null)}
          onSubmit={(updates) => void handleUpdateAccount(updates)}
        />
      )}

      <section className="space-y-3">
        <AccountsMetricCards summary={refreshSummary ?? summary} />
        <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
          <CardContent className="p-4">
            <div className="mb-3 text-sm font-medium text-stone-700">
              系统可用模型
              <span className="ml-1 text-stone-400">({availableModels.length})</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {availableModels.length > 0 ? (
                availableModels.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    className="inline-flex cursor-pointer items-center rounded-full border border-stone-200 bg-white px-2.5 py-1 text-xs font-medium text-stone-700 transition hover:border-stone-300 hover:bg-stone-50"
                    onClick={() => {
                      void navigator.clipboard.writeText(model.id);
                      toast.success("模型名已复制");
                    }}
                    title={`点击复制 ${model.id}`}
                  >
                    <img
                      src="/openai.svg"
                      alt=""
                      aria-hidden="true"
                      className="mr-1.5 size-3.5 shrink-0"
                    />
                    {model.id}
                  </button>
                ))
              ) : isLoadingModels ? (
                <span className="text-sm text-stone-400">正在加载模型列表...</span>
              ) : (
                <span className="text-sm text-stone-400">当前暂无可用模型</span>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight">账户列表</h2>
            <Badge variant="secondary" className="rounded-lg bg-stone-200 px-2 py-0.5 text-stone-700">
              {filteredAccounts.length}
            </Badge>
          </div>

          <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
            <div className="relative min-w-[260px]">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-stone-400" />
              <Input
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  pagination.resetPage();
                }}
                placeholder="搜索邮箱"
                className="h-10 rounded-xl border-stone-200 bg-white/85 pl-10"
              />
            </div>
            <Select
              value={typeFilter}
              onValueChange={(value) => {
                setTypeFilter(value);
                pagination.resetPage();
              }}
            >
              <SelectTrigger className="h-10 w-full rounded-xl border-stone-200 bg-white/85 lg:w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {accountTypeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(value) => {
                setStatusFilter(value as AccountStatus | "all");
                pagination.resetPage();
              }}
            >
              <SelectTrigger className="h-10 w-full rounded-xl border-stone-200 bg-white/85 lg:w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {accountStatusOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {isLoading && accounts.length === 0 ? (
          <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
            <CardContent className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
              <div className="rounded-xl bg-stone-100 p-3 text-stone-500">
                <LoaderCircle className="size-5 animate-spin" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-stone-700">正在加载账户</p>
                <p className="text-sm text-stone-500">从后端同步账号列表和状态。</p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <AccountsTable
            rows={currentRows}
            selectedIds={selectedIds}
            allCurrentSelected={allCurrentSelected}
            selectedTokens={selectedTokens}
            abnormalTokens={abnormalTokens}
            refreshingTokens={refreshingTokens}
            isRefreshing={isRefreshing}
            isRelogining={isRelogining}
            isDeleting={isDeleting}
            isUpdating={isUpdating}
            onToggleAll={toggleSelectAll}
            onToggleRow={toggleSelectRow}
            onRefreshTokens={(tokens) => void handleRefreshAccounts(tokens)}
            onReLogin={(tokens) => void handleReLogin(tokens)}
            onDeleteTokens={(tokens) => void handleDeleteTokens(tokens)}
            onEdit={setEditingAccount}
            pagination={{
              total: filteredAccounts.length,
              startIndex: pagination.startIndex,
              page: pagination.page,
              pageCount: pagination.pageCount,
              pageSize: pagination.pageSize,
              onPageChange: pagination.setPage,
              onPageSizeChange: pagination.setPageSize,
            }}
          />
        )}
      </section>
    </>
  );
}

export default function AccountsPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);

  if (isCheckingAuth || !session || session.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <AccountsPageContent />;
}
