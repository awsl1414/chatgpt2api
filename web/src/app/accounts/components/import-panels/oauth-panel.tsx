"use client";

import { ArrowLeft, Copy, ExternalLink, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { OAuthLoginStartResponse } from "@/lib/api/accounts";

type OAuthPanelProps = {
  emailHint: string;
  onEmailHintChange: (value: string) => void;
  session: OAuthLoginStartResponse | null;
  callbackInput: string;
  onCallbackInputChange: (value: string) => void;
  starting: boolean;
  onStart: () => void;
  onCopyAuthorizeUrl: () => void;
  /** 重新生成：清空当前 session 与 callback 输入 */
  onReset: () => void;
  /** 返回导入方式菜单（保留已获取的 session） */
  onBack: () => void;
};

// OAuth 登录面板：起授权 → 浏览器登录 → 回填 callback URL 换 token
// 状态与 API 调用由父组件（Dialog 主编排）持有，本组件只做展示与事件转发
export function OAuthPanel({
  emailHint,
  onEmailHintChange,
  session,
  callbackInput,
  onCallbackInputChange,
  starting,
  onStart,
  onCopyAuthorizeUrl,
  onReset,
  onBack,
}: OAuthPanelProps) {
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
      <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm leading-6 text-stone-600 space-y-2">
        <div className="font-medium text-stone-800">操作步骤</div>
        <ol className="list-decimal pl-5 space-y-1">
          <li>（可选）填写你 ChatGPT 账号的邮箱，登录页会预填。</li>
          <li>点击下方&quot;打开授权页面&quot;，在新标签里登录自己的 ChatGPT 账号。</li>
          <li>登录完成后浏览器会跳到 <code className="rounded bg-stone-200 px-1">platform.openai.com/auth/callback?code=...</code>。立刻从地址栏复制整段 URL（或开 F12 在 Network 里抓到 callback 那一行，右键 Copy → Copy URL）。</li>
          <li>把 callback URL 粘到下面输入框，点&quot;完成导入&quot;。</li>
        </ol>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">邮箱（可选预填）</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={emailHint}
          onChange={(event) => onEmailHintChange(event.target.value)}
          disabled={Boolean(session) || starting}
          className="w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-stone-400"
        />
      </div>
      {!session ? (
        <Button
          type="button"
          className="h-10 rounded-xl bg-stone-950 text-white hover:bg-stone-800"
          onClick={onStart}
          disabled={starting}
        >
          {starting ? <LoaderCircle className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
          打开授权页面
        </Button>
      ) : (
        <div className="space-y-3">
          <div className="rounded-2xl border border-stone-200 bg-white p-3 text-xs leading-6 text-stone-600 break-all font-mono">
            {session.authorize_url}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              className="rounded-xl border-stone-200 bg-white"
              onClick={onCopyAuthorizeUrl}
            >
              <Copy className="size-4" />
              复制授权 URL
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl border-stone-200 bg-white"
              onClick={() => window.open(session.authorize_url, "_blank", "noopener,noreferrer")}
            >
              <ExternalLink className="size-4" />
              再次打开
            </Button>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl border-stone-200 bg-white"
              onClick={onReset}
            >
              重新生成
            </Button>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">粘贴 callback URL（或仅 code）</label>
            <Textarea
              placeholder={"https://platform.openai.com/auth/callback?code=...&state=..."}
              value={callbackInput}
              onChange={(event) => onCallbackInputChange(event.target.value)}
              className="min-h-24 resize-none rounded-xl border-stone-200 font-mono text-xs"
            />
          </div>
        </div>
      )}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        <div className="font-medium">注意</div>
        <div>
          授权码（code）只能使用一次。如果浏览器的 callback 页加载完成、显示了 OpenAI 的错误页，那 code 大概率已经被消耗，
          请点击&quot;重新生成&quot;再走一次。整个流程在 10 分钟内完成即可。
        </div>
      </div>
    </div>
  );
}
