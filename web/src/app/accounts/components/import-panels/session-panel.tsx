"use client";

import { ArrowLeft, ExternalLink } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";

const sessionUrl = "https://chatgpt.com/api/auth/session";

type SessionPanelProps = {
  value: string;
  onChange: (value: string) => void;
  onBack: () => void;
};

// Session JSON 导入面板：粘贴 chatgpt.com session 接口返回的完整 JSON
export function SessionPanel({ value, onChange, onBack }: SessionPanelProps) {
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
      <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm leading-6 text-stone-600">
        打开
        {" "}
        <a
          href={sessionUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium text-stone-900 underline underline-offset-4"
        >
          {sessionUrl}
          <ExternalLink className="size-3.5" />
        </a>
        ，复制页面返回的完整 JSON，系统会自动提取其中的 `accessToken` 导入。
      </div>
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        <div className="font-medium">风险提示</div>
        <div>
          不要使用自己的大号，尽量使用不常用的小号进行导入，避免出现封号风险。本项目不承担任何封号风险责任。
        </div>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">Session JSON</label>
        <Textarea
          placeholder='粘贴完整 JSON，例如包含 "accessToken" 的对象...'
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-56 resize-none rounded-xl border-stone-200 font-mono text-xs"
        />
      </div>
    </div>
  );
}
