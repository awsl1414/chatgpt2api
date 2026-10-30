"use client";

import { useRef, type ChangeEvent } from "react";
import { ArrowLeft, Files } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { getAccountJsonAccounts, readFileAsText } from "@/lib/account-import-parse";
import type { AccountImportPayload } from "@/lib/api/accounts";

// 一次文件读取的汇总结果：解析出的账号 + 未能提取成功的文件数
export type AccountJsonParseResult = {
  tokens: string[];
  accounts: AccountImportPayload[];
  parsedAccountCount: number;
  errorCount: number;
};

type AccountJsonPanelProps = {
  isSubmitting: boolean;
  /** 最近一次读取的解析结果；null 表示尚未读取 */
  pending: AccountJsonParseResult | null;
  onParsed: (result: AccountJsonParseResult) => void;
  onBack: () => void;
};

// 账号 JSON 文件导入面板：支持本项目导出的单账号对象 / 全部账号数组 / CPA JSON
export function AccountJsonPanel({ isSubmitting, pending, onParsed, onBack }: AccountJsonPanelProps) {
  const accountJsonInputRef = useRef<HTMLInputElement | null>(null);

  const handleFilesSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";

    if (files.length === 0) {
      return;
    }

    try {
      const results = await Promise.all(
        files.map(async (file) => {
          const raw = await readFileAsText(file);
          const parsed = JSON.parse(raw) as unknown;
          return getAccountJsonAccounts(parsed);
        }),
      );

      const accounts = results.flat();
      const tokens = accounts.map((item) => item.access_token);
      const parsedAccountCount = accounts.length;
      const errorCount = results.filter((item) => item.length === 0).length;

      if (parsedAccountCount === 0) {
        toast.error("这些账号 JSON 文件里没有读取到可用 access_token");
        return;
      }

      onParsed({ tokens, accounts, parsedAccountCount, errorCount });
    } catch (error) {
      const message = error instanceof Error ? error.message : "读取账号 JSON 文件失败";
      toast.error(message);
    }
  };

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 text-sm text-stone-500 transition hover:text-stone-800"
      >
        <ArrowLeft className="size-4" />
        返回导入方式
      </button>
      <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 p-5">
        <div className="space-y-2">
          <div className="text-sm font-medium text-stone-800">选择本地账号 JSON 文件</div>
          <div className="text-sm leading-6 text-stone-500">
            支持本项目导出的单账号对象或全部账号数组，也兼容每个文件一个账号对象的 CPA JSON。
            系统会自动提取 `access_token` 或 `accessToken`。
          </div>
        </div>
        <Button
          type="button"
          className="mt-4 rounded-xl bg-stone-950 text-white hover:bg-stone-800"
          onClick={() => accountJsonInputRef.current?.click()}
          disabled={isSubmitting}
        >
          <Files className="size-4" />
          选择 JSON 文件
        </Button>
      </div>
      <input
        ref={accountJsonInputRef}
        type="file"
        accept=".json,application/json"
        multiple
        className="hidden"
        onChange={(event) => void handleFilesSelected(event)}
      />
      {pending ? (
        <div className="rounded-2xl border border-stone-200 bg-white p-4 text-sm leading-6 text-stone-600">
          最近一次读取到 {pending.parsedAccountCount} 个 Token
          {pending.errorCount > 0 ? `，另有 ${pending.errorCount} 个文件未提取成功` : ""}。
        </div>
      ) : null}
    </div>
  );
}
