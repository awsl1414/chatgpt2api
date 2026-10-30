"use client";

import { useRef, type ChangeEvent } from "react";
import { ArrowLeft, FileText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { readFileAsText, splitTokens } from "@/lib/account-import-parse";

type TokenPanelProps = {
  value: string;
  onChange: (value: string) => void;
  isSubmitting: boolean;
  onBack: () => void;
};

// Access Token 导入面板：支持直接粘贴与从 TXT 文件读取（一行一个）
export function TokenPanel({ value, onChange, isSubmitting, onBack }: TokenPanelProps) {
  const txtInputRef = useRef<HTMLInputElement | null>(null);
  const tokenCount = splitTokens(value).length;

  const handleTxtSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) {
      return;
    }

    try {
      const content = await readFileAsText(file);
      const tokens = splitTokens(content);

      if (tokens.length === 0) {
        toast.error("TXT 文件里没有读取到有效 Token");
        return;
      }

      onChange([...splitTokens(value), ...tokens].join("\n"));
      toast.success(`已从 ${file.name} 读取 ${tokens.length} 个 Token`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "读取 TXT 文件失败";
      toast.error(message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-sm text-stone-500 transition hover:text-stone-800"
        >
          <ArrowLeft className="size-4" />
          返回导入方式
        </button>
        <span className="text-xs text-stone-400">当前识别 {tokenCount} 个 Token</span>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">Access Token 列表</label>
        <Textarea
          placeholder="每行一个 Access Token..."
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-56 resize-none rounded-xl border-stone-200"
        />
      </div>
      <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="text-sm font-medium text-stone-800">从 TXT 文件导入</div>
            <div className="text-sm leading-6 text-stone-500">支持 `.txt`，文件内容也是一行一个 Token。</div>
          </div>
          <Button
            type="button"
            variant="outline"
            className="rounded-xl border-stone-200 bg-white"
            onClick={() => txtInputRef.current?.click()}
            disabled={isSubmitting}
          >
            <FileText className="size-4" />
            选择 TXT
          </Button>
        </div>
      </div>
      <input
        ref={txtInputRef}
        type="file"
        accept=".txt,text/plain"
        className="hidden"
        onChange={(event) => void handleTxtSelected(event)}
      />
    </div>
  );
}
