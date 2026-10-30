"use client";

import { ArrowLeft } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";

type CodexAuthPanelProps = {
  value: string;
  onChange: (value: string) => void;
  onBack: () => void;
};

// Codex 认证 JSON 导入面板：粘贴 Codex CLI 的 auth.json 内容
export function CodexAuthPanel({ value, onChange, onBack }: CodexAuthPanelProps) {
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
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">Codex 认证 JSON</label>
        <Textarea
          placeholder='粘贴包含 "access_token"、"refresh_token"、"id_token" 的 Codex 认证 JSON...'
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-64 resize-none rounded-xl border-stone-200 font-mono text-xs"
        />
      </div>
    </div>
  );
}
