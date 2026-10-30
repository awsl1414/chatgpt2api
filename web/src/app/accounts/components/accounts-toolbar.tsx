"use client";

import { Download, RefreshCw } from "lucide-react";

import { AccountImportDialog } from "@/app/accounts/components/account-import-dialog";
import { Button } from "@/components/ui/button";
import type { Account } from "@/lib/api/accounts";
import { cn } from "@/lib/utils";

type AccountsToolbarProps = {
  accounts: Account[];
  isLoading: boolean;
  isRefreshing: boolean;
  isDeleting: boolean;
  onLoadAccounts: () => void;
  onRefreshAll: () => void;
  onExportTokens: () => void;
  onImported: (items: Account[]) => void;
};

// 账号页页头操作区：手动刷新、一键刷新全量、导入 Dialog 入口、导出全部 Token
export function AccountsToolbar({
  accounts,
  isLoading,
  isRefreshing,
  isDeleting,
  onLoadAccounts,
  onRefreshAll,
  onExportTokens,
  onImported,
}: AccountsToolbarProps) {
  return (
    <section className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-1">
        <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">
          Account Pool
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">号池管理</h1>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          className="h-10 rounded-xl border-stone-200 bg-white/80 px-4 text-stone-700 hover:bg-white"
          onClick={onLoadAccounts}
          disabled={isLoading || isRefreshing || isDeleting}
        >
          <RefreshCw className={cn("size-4", isLoading ? "animate-spin" : "")} />
          刷新
        </Button>
        <Button
          variant="outline"
          className="h-10 rounded-xl border-stone-200 bg-white/80 px-4 text-stone-700 hover:bg-white"
          onClick={onRefreshAll}
          disabled={isLoading || isRefreshing || isDeleting || accounts.length === 0}
        >
          <RefreshCw className={cn("size-4", isRefreshing ? "animate-spin" : "")} />
          一键刷新所有账号信息和额度
        </Button>
        <AccountImportDialog
          disabled={isLoading || isRefreshing || isDeleting}
          onImported={onImported}
        />
        <Button
          variant="outline"
          className="h-10 rounded-xl border-stone-200 bg-white/80 px-4 text-stone-700 hover:bg-white"
          onClick={onExportTokens}
          disabled={accounts.length === 0}
        >
          <Download className="size-4" />
          导出全部 Token
        </Button>
      </div>
    </section>
  );
}
