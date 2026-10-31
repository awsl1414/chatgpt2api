"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FileJson, Files, KeyRound, LoaderCircle, LogIn, ServerCog, Upload } from "lucide-react";
import { toast } from "sonner";

import { copyToClipboard } from "@/lib/clipboard";
import { AccountJsonPanel, type AccountJsonParseResult } from "@/app/accounts/components/import-panels/account-json-panel";
import { CodexAuthPanel } from "@/app/accounts/components/import-panels/codex-auth-panel";
import { OAuthPanel } from "@/app/accounts/components/import-panels/oauth-panel";
import { SessionPanel } from "@/app/accounts/components/import-panels/session-panel";
import { TokenPanel } from "@/app/accounts/components/import-panels/token-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getCodexAuthAccount, getSessionAccessToken, splitTokens } from "@/lib/account-import-parse";
import {
  createAccounts,
  finishOAuthLogin,
  startOAuthLogin,
  type Account,
  type AccountImportPayload,
  type OAuthLoginStartResponse,
} from "@/lib/api/accounts";
import { cn } from "@/lib/utils";
import { actionError } from "@/lib/action-result";

type ImportMethod = "menu" | "token" | "session" | "codex-auth" | "account-json" | "oauth";

type AccountImportDialogProps = {
  disabled?: boolean;
  onImported: (items: Account[]) => void;
};

type MethodCardProps = {
  title: string;
  description: string;
  icon: typeof KeyRound;
  onClick: () => void;
};

function MethodCard({ title, description, icon: Icon, onClick }: MethodCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-2xl border border-stone-200 bg-white p-0 text-left transition hover:border-stone-300 hover:bg-stone-50"
    >
      <Card className="rounded-2xl border-0 bg-transparent shadow-none">
        <CardContent className="flex items-start gap-4 p-4">
          <div className="rounded-xl bg-stone-100 p-3 text-stone-700">
            <Icon className="size-5" />
          </div>
          <div className="space-y-1">
            <div className="text-sm font-semibold text-stone-900">{title}</div>
            <div className="text-sm leading-6 text-stone-500">{description}</div>
          </div>
        </CardContent>
      </Card>
    </button>
  );
}

// 各 method 的标题与描述映射
const methodMeta: Record<Exclude<ImportMethod, "menu">, { title: string; description: string }> = {
  token: {
    title: "导入 Access Token",
    description: "支持手动粘贴或从 TXT 文件导入，一行一个 Token。",
  },
  session: {
    title: "导入 Session JSON",
    description: "粘贴完整 Session JSON，系统会自动提取 accessToken。",
  },
  "codex-auth": {
    title: "导入 Codex 认证 JSON",
    description: "粘贴 Codex 认证 JSON，系统会按 codex 来源导入。",
  },
  oauth: {
    title: "OAuth 登录已有账号",
    description: "用浏览器跑一遍 OpenAI 标准 OAuth，拿回 refresh_token 后系统会自动续期。",
  },
  "account-json": {
    title: "导入账号 JSON",
    description: "支持读取本项目导出的单账号对象或全部账号数组，并在提交前做数量确认。",
  },
};

// 账号导入 Dialog：只负责 method 导航、各面板状态持有与提交；面板 UI 见 import-panels/
export function AccountImportDialog({ disabled, onImported }: AccountImportDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState<ImportMethod>("menu");
  const [tokenInput, setTokenInput] = useState("");
  const [sessionInput, setSessionInput] = useState("");
  const [codexAuthInput, setCodexAuthInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingAccountJsonImport, setPendingAccountJsonImport] = useState<AccountJsonParseResult | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [oauthEmailHint, setOauthEmailHint] = useState("");
  const [oauthSession, setOauthSession] = useState<OAuthLoginStartResponse | null>(null);
  const [oauthCallbackInput, setOauthCallbackInput] = useState("");
  const [oauthStarting, setOauthStarting] = useState(false);

  const resetState = () => {
    setMethod("menu");
    setTokenInput("");
    setSessionInput("");
    setCodexAuthInput("");
    setPendingAccountJsonImport(null);
    setConfirmOpen(false);
    setOauthEmailHint("");
    setOauthSession(null);
    setOauthCallbackInput("");
    setOauthStarting(false);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      resetState();
    }
  };

  const submitTokens = async (tokens: string[], successText?: string, accountPayloads: AccountImportPayload[] = []) => {
    const normalizedTokens = tokens.map((item) => item.trim()).filter(Boolean);

    if (normalizedTokens.length === 0) {
      toast.error("请先提供至少一个可用 Token");
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await createAccounts(normalizedTokens, accountPayloads);
      onImported(data.items);
      setOpen(false);
      resetState();

      if ((data.errors?.length ?? 0) > 0) {
        const firstError = data.errors?.[0]?.error;
        toast.error(
          `${successText ?? "导入完成"}，新增 ${data.added ?? 0} 个，已刷新 ${data.refreshed ?? 0} 个，失败 ${data.errors?.length ?? 0} 个${firstError ? `，首个错误：${firstError}` : ""}`,
        );
      } else {
        toast.success(
          `${successText ?? "导入完成"}，新增 ${data.added ?? 0} 个，跳过 ${data.skipped ?? 0} 个重复项，已自动刷新账号信息`,
        );
      }
    } catch (error) {
      const message = actionError(error, "导入账户失败");
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleImportTokenText = async () => {
    await submitTokens(splitTokens(tokenInput), "Access Token 导入完成");
  };

  // 起授权：拿 authorize URL，立刻在新窗口打开，方便用户登录
  const handleStartOAuth = async () => {
    setOauthStarting(true);
    try {
      const data = await startOAuthLogin(oauthEmailHint.trim());
      setOauthSession(data);
      setOauthCallbackInput("");
      if (typeof window !== "undefined") {
        window.open(data.authorize_url, "_blank", "noopener,noreferrer");
      }
      toast.success("已打开 OpenAI 授权页面，请在登录后复制 callback URL 回来");
    } catch (error) {
      const message = actionError(error, "OAuth 起始失败");
      toast.error(message);
    } finally {
      setOauthStarting(false);
    }
  };

  // 用粘贴回来的 callback URL 完成换 token + 落盘
  const handleFinishOAuth = async () => {
    if (!oauthSession) {
      toast.error("请先点击\"打开授权页面\"获取 session");
      return;
    }
    const trimmed = oauthCallbackInput.trim();
    if (!trimmed) {
      toast.error("请粘贴 callback URL 或 code");
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await finishOAuthLogin(oauthSession.session_id, trimmed);
      onImported(data.items);
      setOpen(false);
      resetState();

      if ((data.errors?.length ?? 0) > 0) {
        const firstError = data.errors?.[0]?.error;
        toast.error(
          `OAuth 登录完成，新增 ${data.added ?? 0} 个，已刷新 ${data.refreshed ?? 0} 个，失败 ${data.errors?.length ?? 0} 个${firstError ? `，首个错误：${firstError}` : ""}`,
        );
      } else {
        toast.success(
          `OAuth 登录完成，新增 ${data.added ?? 0} 个，跳过 ${data.skipped ?? 0} 个重复项，已自动刷新账号信息`,
        );
      }
    } catch (error) {
      const message = actionError(error, "OAuth 换 token 失败");
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 复制 authorize URL 到剪贴板（适配浏览器和 fallback）
  const handleCopyAuthorizeUrl = async () => {
    if (!oauthSession) {
      return;
    }
    try {
      await copyToClipboard(oauthSession.authorize_url, "授权 URL 已复制到剪贴板");
    } catch {
      toast.error("复制失败，请手动选择并复制");
    }
  };

  const handleImportSessionJson = async () => {
    if (!sessionInput.trim()) {
      toast.error("请先粘贴完整 Session JSON");
      return;
    }

    try {
      const payload = JSON.parse(sessionInput) as unknown;
      const token = getSessionAccessToken(payload);

      if (!token) {
        toast.error("未从 Session JSON 中提取到 accessToken");
        return;
      }

      await submitTokens([token], "Session JSON 导入完成");
    } catch (error) {
      const message = actionError(error, "Session JSON 解析失败");
      toast.error(message);
    }
  };

  const handleImportCodexAuthJson = async () => {
    if (!codexAuthInput.trim()) {
      toast.error("请先粘贴 Codex 认证 JSON");
      return;
    }

    try {
      const payload = JSON.parse(codexAuthInput) as unknown;
      const account = getCodexAuthAccount(payload);

      if (!account) {
        toast.error("未从 Codex 认证 JSON 中提取到 access_token");
        return;
      }

      await submitTokens([account.access_token], "Codex 认证 JSON 导入完成", [account]);
    } catch (error) {
      const message = actionError(error, "Codex 认证 JSON 解析失败");
      toast.error(message);
    }
  };

  const handleAccountJsonParsed = (result: AccountJsonParseResult) => {
    setPendingAccountJsonImport(result);
    setConfirmOpen(true);
  };

  const footerDisabled = disabled || isSubmitting;

  const renderMethodBody = () => {
    if (method === "token") {
      return (
        <TokenPanel
          value={tokenInput}
          onChange={setTokenInput}
          isSubmitting={isSubmitting}
          onBack={() => setMethod("menu")}
        />
      );
    }

    if (method === "session") {
      return (
        <SessionPanel
          value={sessionInput}
          onChange={setSessionInput}
          onBack={() => setMethod("menu")}
        />
      );
    }

    if (method === "oauth") {
      return (
        <OAuthPanel
          emailHint={oauthEmailHint}
          onEmailHintChange={setOauthEmailHint}
          session={oauthSession}
          callbackInput={oauthCallbackInput}
          onCallbackInputChange={setOauthCallbackInput}
          starting={oauthStarting}
          onStart={() => void handleStartOAuth()}
          onCopyAuthorizeUrl={() => void handleCopyAuthorizeUrl()}
          onReset={() => {
            setOauthSession(null);
            setOauthCallbackInput("");
          }}
          onBack={() => setMethod("menu")}
        />
      );
    }

    if (method === "account-json") {
      return (
        <AccountJsonPanel
          isSubmitting={isSubmitting}
          pending={pendingAccountJsonImport}
          onParsed={handleAccountJsonParsed}
          onBack={() => setMethod("menu")}
        />
      );
    }

    if (method === "codex-auth") {
      return (
        <CodexAuthPanel
          value={codexAuthInput}
          onChange={setCodexAuthInput}
          onBack={() => setMethod("menu")}
        />
      );
    }

    return (
      <div className="space-y-3">
        <MethodCard
          title="OAuth 登录已有账号（带自动刷新）"
          description="用浏览器登录自己的 ChatGPT 账号，回填 callback URL 即可拿到 refresh_token，后台会自动续期。"
          icon={LogIn}
          onClick={() => setMethod("oauth")}
        />
        <MethodCard
          title="导入 Access Token"
          description="支持直接粘贴，一行一个；也支持从 TXT 文件读取，一行一个。"
          icon={KeyRound}
          onClick={() => setMethod("token")}
        />
        <MethodCard
          title="导入 Session JSON"
          description="从 chatgpt.com 的 session 接口复制完整 JSON，自动提取 accessToken。"
          icon={FileJson}
          onClick={() => setMethod("session")}
        />
        <MethodCard
          title="导入 Codex 认证 JSON"
          description="粘贴 Codex 认证 JSON，导入后账号来源标记为 codex。"
          icon={FileJson}
          onClick={() => setMethod("codex-auth")}
        />
        <MethodCard
          title="导入账号 JSON 文件"
          description="支持本项目导出的单账号 JSON 或全部账号数组，也兼容 CPA JSON 文件。"
          icon={Files}
          onClick={() => setMethod("account-json")}
        />
        <MethodCard
          title="从远程 CPA 服务器导入"
          description="前往设置页面配置远程 CPA 服务器后再执行导入。"
          icon={Files}
          onClick={() => {
            setOpen(false);
            resetState();
            router.push("/settings");
          }}
        />
        <MethodCard
          title="从 Sub2API 服务器导入"
          description="前往设置页面配置 Sub2API 服务器，再选择其中的 OpenAI 账号导入。"
          icon={ServerCog}
          onClick={() => {
            setOpen(false);
            resetState();
            router.push("/settings");
          }}
        />
      </div>
    );
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <Button
          className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
          onClick={() => setOpen(true)}
          disabled={disabled}
        >
          <Upload className="size-4" />
          导入
        </Button>
        <DialogContent showCloseButton={false} className="rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>
              {method === "menu" ? "导入账户" : methodMeta[method].title}
            </DialogTitle>
            <DialogDescription className="text-sm leading-6">
              {method === "menu"
                ? "选择一种导入方式。导入成功后会自动拉取邮箱、类型和额度。"
                : methodMeta[method].description}
            </DialogDescription>
          </DialogHeader>

          {renderMethodBody()}

          <DialogFooter className="pt-2">
            <Button
              variant="secondary"
              className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
              onClick={() => setOpen(false)}
              disabled={footerDisabled}
            >
              取消
            </Button>
            {method === "token" ? (
              <Button
                className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
                onClick={() => void handleImportTokenText()}
                disabled={footerDisabled}
              >
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
                导入 Token
              </Button>
            ) : null}
            {method === "session" ? (
              <Button
                className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
                onClick={() => void handleImportSessionJson()}
                disabled={footerDisabled}
              >
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
                导入 JSON
              </Button>
            ) : null}
            {method === "codex-auth" ? (
              <Button
                className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
                onClick={() => void handleImportCodexAuthJson()}
                disabled={footerDisabled}
              >
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
                导入 JSON
              </Button>
            ) : null}
            {method === "oauth" ? (
              <Button
                className={cn(
                  "h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800",
                  !oauthSession ? "hidden" : "",
                )}
                onClick={() => void handleFinishOAuth()}
                disabled={footerDisabled || !oauthSession || !oauthCallbackInput.trim()}
              >
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
                完成导入
              </Button>
            ) : null}
            {method === "account-json" ? (
              <Button
                className={cn(
                  "h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800",
                  !pendingAccountJsonImport ? "hidden" : "",
                )}
                onClick={() => setConfirmOpen(true)}
                disabled={footerDisabled || !pendingAccountJsonImport}
              >
                查看导入确认
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>确认导入账号 Token</DialogTitle>
            <DialogDescription className="text-sm leading-6">
              {pendingAccountJsonImport
                ? `确认识别到 ${pendingAccountJsonImport.parsedAccountCount} 个 Token，是否确认导入？`
                : "尚未读取到可导入的 Token。"}
              {pendingAccountJsonImport?.errorCount
                ? `，另有 ${pendingAccountJsonImport.errorCount} 个文件未提取成功。`
                : "。"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="pt-2">
            <Button
              variant="secondary"
              className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
              onClick={() => setConfirmOpen(false)}
              disabled={isSubmitting}
            >
              返回
            </Button>
            <Button
              className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
              onClick={() =>
                void submitTokens(
                  pendingAccountJsonImport?.tokens ?? [],
                  "账号 JSON 导入完成",
                  pendingAccountJsonImport?.accounts ?? [],
                )
              }
              disabled={isSubmitting || !pendingAccountJsonImport}
            >
              {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
              确认导入
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
