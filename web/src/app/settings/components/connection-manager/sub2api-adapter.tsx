"use client";

import { useState } from "react";
import { Eye, EyeOff, Layers, Link2, LoaderCircle, Mail, RefreshCcw, Unplug } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createSub2APIServer,
  deleteSub2APIServer,
  fetchSub2APIServerAccounts,
  fetchSub2APIServerGroups,
  fetchSub2APIServers,
  startSub2APIImport,
  updateSub2APIServer,
  type Sub2APIRemoteAccount,
  type Sub2APIRemoteGroup,
  type Sub2APIServer,
} from "@/lib/api/sub2api";
import { actionError } from "@/lib/action-result";

import type { ConnectionAdapter, ConnectionFormContext } from "./types";

type Sub2APIForm = {
  name: string;
  base_url: string;
  email: string;
  password: string;
  api_key: string;
  group_id: string;
  authMode: "password" | "api_key";
};

type Sub2APIEditFieldsProps = ConnectionFormContext<Sub2APIServer, Sub2APIForm>;

/** Sub2API 编辑表单：认证方式切换与「拉取分组」逻辑为本域私有，分组状态在组件内部 */
function Sub2APIEditFields({ form, patchForm, editing }: Sub2APIEditFieldsProps) {
  const [showSecret, setShowSecret] = useState(false);
  const [remoteGroups, setRemoteGroups] = useState<Sub2APIRemoteGroup[] | null>(null);
  const [isLoadingGroups, setIsLoadingGroups] = useState(false);

  const handleFetchGroups = async () => {
    if (!editing) {
      toast.error("请先保存连接后再拉取分组");
      return;
    }
    setIsLoadingGroups(true);
    try {
      const data = await fetchSub2APIServerGroups(editing.id);
      setRemoteGroups(data.groups);
      if (data.groups.length === 0) {
        toast.message("远端没有配置分组");
      } else {
        toast.success(`读取到 ${data.groups.length} 个分组`);
      }
    } catch (error) {
      toast.error(actionError(error, "拉取分组失败"));
    } finally {
      setIsLoadingGroups(false);
    }
  };

  return (
    <>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">名称（可选）</label>
        <Input
          value={form.name}
          onChange={(event) => patchForm({ name: event.target.value })}
          placeholder="例如：自建 sub2api"
          className="h-11 rounded-xl border-stone-200 bg-white"
        />
      </div>
      <div className="space-y-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
          <Link2 className="size-3.5" />
          Sub2API 地址
        </label>
        <Input
          value={form.base_url}
          onChange={(event) => patchForm({ base_url: event.target.value })}
          placeholder="http://your-sub2api-host:8080"
          className="h-11 rounded-xl border-stone-200 bg-white"
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">认证方式</label>
        <Select value={form.authMode} onValueChange={(value) => patchForm({ authMode: value as Sub2APIForm["authMode"] })}>
          <SelectTrigger className="h-11 rounded-xl border-stone-200 bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="password">管理员邮箱 + 密码</SelectItem>
            <SelectItem value="api_key">Admin API Key</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {form.authMode === "password" ? (
        <>
          <div className="space-y-2">
            <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
              <Mail className="size-3.5" />
              管理员邮箱
            </label>
            <Input
              value={form.email}
              onChange={(event) => patchForm({ email: event.target.value })}
              placeholder="admin@example.com"
              className="h-11 rounded-xl border-stone-200 bg-white"
            />
          </div>
          <div className="space-y-2">
            <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
              <Unplug className="size-3.5" />
              管理员密码
            </label>
            <div className="relative">
              <Input
                type={showSecret ? "text" : "password"}
                value={form.password}
                onChange={(event) => patchForm({ password: event.target.value })}
                placeholder={editing ? "留空则不修改密码" : "管理员密码"}
                className="h-11 rounded-xl border-stone-200 bg-white pr-10"
              />
              <button
                type="button"
                className="absolute top-1/2 right-3 -translate-y-1/2 text-stone-400 transition hover:text-stone-600"
                onClick={() => setShowSecret((prev) => !prev)}
              >
                {showSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="space-y-2">
          <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
            <Unplug className="size-3.5" />
            Admin API Key
          </label>
          <div className="relative">
            <Input
              type={showSecret ? "text" : "password"}
              value={form.api_key}
              onChange={(event) => patchForm({ api_key: event.target.value })}
              placeholder={editing ? "留空则不修改密钥" : "Sub2API Admin API Key"}
              className="h-11 rounded-xl border-stone-200 bg-white pr-10"
            />
            <button
              type="button"
              className="absolute top-1/2 right-3 -translate-y-1/2 text-stone-400 transition hover:text-stone-600"
              onClick={() => setShowSecret((prev) => !prev)}
            >
              {showSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>
      )}
      <div className="space-y-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
          <Layers className="size-3.5" />
          分组（可选）
        </label>
        {remoteGroups && remoteGroups.length > 0 ? (
          <Select
            value={form.group_id || "__all__"}
            onValueChange={(value) => patchForm({ group_id: value === "__all__" ? "" : value })}
          >
            <SelectTrigger className="h-11 rounded-xl border-stone-200 bg-white">
              <SelectValue placeholder="选择分组" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">全部分组（不限制）</SelectItem>
              <SelectItem value="ungrouped">未分组</SelectItem>
              {remoteGroups.map((group) => (
                <SelectItem key={group.id} value={group.id}>
                  {group.name || `Group ${group.id}`}
                  {group.platform ? `（${group.platform}）` : ""}
                  {group.account_count ? ` · ${group.active_account_count}/${group.account_count}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            value={form.group_id}
            onChange={(event) => patchForm({ group_id: event.target.value })}
            placeholder="留空则同步所有分组；或填写分组 ID / ungrouped"
            className="h-11 rounded-xl border-stone-200 bg-white"
          />
        )}
        {editing ? (
          <div className="flex items-center justify-between gap-2 text-xs text-stone-500">
            <span>同步时会用分组 ID 过滤，留空 = 同步所有 OpenAI OAuth 账号。</span>
            <Button
              variant="outline"
              className="h-8 rounded-lg border-stone-200 bg-white px-2 text-xs text-stone-600"
              onClick={() => void handleFetchGroups()}
              disabled={isLoadingGroups}
            >
              {isLoadingGroups ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <RefreshCcw className="size-3.5" />
              )}
              {remoteGroups ? "重新拉取" : "拉取分组"}
            </Button>
          </div>
        ) : (
          <div className="text-xs text-stone-500">
            添加完连接后可在编辑对话框里点「拉取分组」选择具体分组。
          </div>
        )}
      </div>
    </>
  );
}

function normalizeRemoteAccounts(items: Sub2APIRemoteAccount[]) {
  const seen = new Set<string>();
  const accounts: Sub2APIRemoteAccount[] = [];
  for (const item of items) {
    const id = String(item.id || "").trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    accounts.push({
      id,
      name: String(item.name || "").trim(),
      email: String(item.email || "").trim(),
      plan_type: String(item.plan_type || "").trim(),
      status: String(item.status || "").trim(),
      expires_at: String(item.expires_at || "").trim(),
      has_refresh_token: Boolean(item.has_refresh_token),
    });
  }
  return accounts;
}

/** Sub2API 域的连接管理适配层，交给公共 ConnectionManager 渲染 */
export const sub2apiConnectionAdapter: ConnectionAdapter<Sub2APIServer, Sub2APIForm, Sub2APIRemoteAccount> = {
  title: "Sub2API 连接管理",
  description: "配置 Sub2API 服务器后，可查询其中的 OpenAI OAuth 账号并批量导入本地号池。",
  emptyTitle: "暂无 Sub2API 连接",
  emptyHint: "点击「添加连接」保存你的 Sub2API 信息。",
  usageNotes: (
    <>
      <li>输入 Sub2API 地址和管理员账户（或 Admin API Key），保存为一个连接。</li>
      <li>点击某个连接的「同步」会拉取其中 platform=openai 且 type=oauth 的账号列表。</li>
      <li>勾选需要的账号后后端会并发拉取 access_token，自动导入本地号池并刷新状态。</li>
      <li>仅会读取 sub2api 凭据中的 access_token；refresh_token 等字段不会写入本地。</li>
    </>
  ),
  loadErrorText: "加载 Sub2API 连接失败",

  fetchConnections: async () => {
    const data = await fetchSub2APIServers();
    return data.servers;
  },
  deleteConnection: async (id) => {
    const data = await deleteSub2APIServer(id);
    return data.servers;
  },
  connectionSubtitle: (conn) =>
    `${conn.base_url}${conn.email ? ` · ${conn.email}` : conn.has_api_key ? " · API Key" : ""}${
      conn.group_id ? ` · 分组 ${conn.group_id}` : " · 全部分组"
    }`,

  edit: {
    addDescription: "添加一个新的 Sub2API 连接",
    editDescription: "修改 Sub2API 连接信息",
    createForm: (conn) => ({
      name: conn?.name ?? "",
      base_url: conn?.base_url ?? "",
      email: conn?.email ?? "",
      password: "",
      api_key: "",
      group_id: conn?.group_id ?? "",
      authMode: conn?.has_api_key ? "api_key" : "password",
    }),
    renderFields: (ctx) => <Sub2APIEditFields {...ctx} />,
    validate: (form, editing) => {
      if (!form.base_url.trim()) {
        return "请输入 Sub2API 地址";
      }
      if (form.authMode === "password") {
        if (!form.email.trim()) {
          return "请输入管理员邮箱";
        }
        if (!editing && !form.password.trim()) {
          return "请输入管理员密码";
        }
      } else if (!editing && !form.api_key.trim()) {
        return "请输入 Admin API Key";
      }
      return null;
    },
    save: async (form, editing) => {
      if (editing) {
        const updates: Parameters<typeof updateSub2APIServer>[1] = {
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          group_id: form.group_id.trim(),
        };
        if (form.authMode === "password") {
          updates.email = form.email.trim();
          if (form.password.trim()) {
            updates.password = form.password.trim();
          }
          updates.api_key = "";
        } else {
          if (form.api_key.trim()) {
            updates.api_key = form.api_key.trim();
          }
          updates.email = "";
          updates.password = "";
        }
        const data = await updateSub2APIServer(editing.id, updates);
        return data.servers;
      }
      const data = await createSub2APIServer({
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        email: form.authMode === "password" ? form.email.trim() : "",
        password: form.authMode === "password" ? form.password.trim() : "",
        api_key: form.authMode === "api_key" ? form.api_key.trim() : "",
        group_id: form.group_id.trim(),
      });
      return data.servers;
    },
  },

  browse: {
    loadSuccessText: (count) => `读取成功，共 ${count} 个 OpenAI 账号`,
    loadErrorText: "读取 Sub2API 账号失败",
    fetchItems: async (conn) => {
      const data = await fetchSub2APIServerAccounts(conn.id);
      return normalizeRemoteAccounts(data.accounts);
    },
    toItemView: (item) => ({
      key: item.id,
      primary: item.email || item.name || item.id,
      secondary: `id ${item.id}${item.expires_at ? ` · 过期 ${item.expires_at}` : ""}`,
      badges: [
        ...(item.plan_type ? [{ text: item.plan_type }] : []),
        ...(item.status ? [{ text: item.status, tone: item.status === "active" ? ("success" as const) : ("info" as const) }] : []),
      ],
    }),
    filterItem: (item, query) =>
      item.email.toLowerCase().includes(query) ||
      item.name.toLowerCase().includes(query) ||
      item.plan_type.toLowerCase().includes(query) ||
      item.id.toLowerCase().includes(query),
    searchPlaceholder: "搜索邮箱、套餐或名称",
    emptyText: "没有匹配的账号",
    originText: (conn) => `来自 ${conn.name || conn.base_url}`,
    startImport: async (connId, keys) => {
      const result = await startSub2APIImport(connId, keys);
      return result.import_job;
    },
  },
};
