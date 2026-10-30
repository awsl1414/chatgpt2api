"use client";

import { useState } from "react";
import { Eye, EyeOff, Link2, Unplug } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  createCPAPool,
  deleteCPAPool,
  fetchCPAPoolFiles,
  fetchCPAPools,
  startCPAImport,
  updateCPAPool,
  type CPAPool,
  type CPARemoteFile,
} from "@/lib/api/cpa";

import type { ConnectionAdapter } from "./types";

type CpaPoolForm = {
  name: string;
  base_url: string;
  secret_key: string;
};

function CpaEditFields({ form, patchForm, editing }: { form: CpaPoolForm; patchForm: (patch: Partial<CpaPoolForm>) => void; editing: CPAPool | null }) {
  const [showSecret, setShowSecret] = useState(false);

  return (
    <>
      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">名称（可选）</label>
        <Input
          value={form.name}
          onChange={(event) => patchForm({ name: event.target.value })}
          placeholder="例如：主号池、备用池"
          className="h-11 rounded-xl border-stone-200 bg-white"
        />
      </div>
      <div className="space-y-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
          <Link2 className="size-3.5" />
          CPA 地址
        </label>
        <Input
          value={form.base_url}
          onChange={(event) => patchForm({ base_url: event.target.value })}
          placeholder="http://your-cpa-host:8317"
          className="h-11 rounded-xl border-stone-200 bg-white"
        />
      </div>
      <div className="space-y-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-stone-700">
          <Unplug className="size-3.5" />
          Management Secret Key
        </label>
        <div className="relative">
          <Input
            type={showSecret ? "text" : "password"}
            value={form.secret_key}
            onChange={(event) => patchForm({ secret_key: event.target.value })}
            placeholder={editing ? "留空则不修改密钥" : "CPA 管理密钥"}
            className="h-11 rounded-xl border-stone-200 bg-white pr-10"
          />
          <button
            type="button"
            className="absolute top-1/2 right-3 -translate-y-1/2 text-stone-400 transition hover:text-stone-600"
            onClick={() => setShowSecret(!showSecret)}
          >
            {showSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
      </div>
    </>
  );
}

function normalizeRemoteFiles(items: CPARemoteFile[]) {
  const seen = new Set<string>();
  const files: CPARemoteFile[] = [];
  for (const item of items) {
    const name = String(item.name || "").trim();
    if (!name || seen.has(name)) {
      continue;
    }
    seen.add(name);
    files.push({
      name,
      email: String(item.email || "").trim(),
    });
  }
  return files;
}

/** CPA（CLIProxyAPI）域的连接管理适配层，交给公共 ConnectionManager 渲染 */
export const cpaConnectionAdapter: ConnectionAdapter<CPAPool, CpaPoolForm, CPARemoteFile> = {
  title: "CPA 连接管理",
  description: "先配置连接，再按需查询远程账号并选择导入到本地号池。",
  emptyTitle: "暂无 CPA 连接",
  emptyHint: "点击「添加连接」保存你的 CLIProxyAPI 信息。",
  usageNotes: (
    <>
      <li>页面进入后先读取系统里已配置的 CPA 连接。</li>
      <li>点击某个连接的「同步」后，会先读取远程账号列表并展示给前端选择。</li>
      <li>确认选择后，后端后台下载对应 access_token 并导入本地号池。</li>
      <li>前端只轮询导入进度，不直接参与 download。</li>
    </>
  ),
  loadErrorText: "加载 CPA 连接失败",

  fetchConnections: async () => {
    const data = await fetchCPAPools();
    return data.pools;
  },
  deleteConnection: async (id) => {
    const data = await deleteCPAPool(id);
    return data.pools;
  },
  connectionSubtitle: (conn) => conn.base_url,

  edit: {
    addDescription: "添加一个新的 CLIProxyAPI 连接",
    editDescription: "修改 CPA 连接信息",
    createForm: (conn) => ({
      name: conn?.name ?? "",
      base_url: conn?.base_url ?? "",
      secret_key: "",
    }),
    renderFields: ({ form, patchForm, editing }) => (
      <CpaEditFields form={form} patchForm={patchForm} editing={editing} />
    ),
    validate: (form, editing) => {
      if (!form.base_url.trim()) {
        return "请输入 CPA 地址";
      }
      if (!editing && !form.secret_key.trim()) {
        return "请输入 Secret Key";
      }
      return null;
    },
    save: async (form, editing) => {
      if (editing) {
        const data = await updateCPAPool(editing.id, {
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          secret_key: form.secret_key.trim() || undefined,
        });
        return data.pools;
      }
      const data = await createCPAPool({
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        secret_key: form.secret_key.trim(),
      });
      return data.pools;
    },
  },

  browse: {
    loadSuccessText: (count) => `读取成功，共 ${count} 个远程账号`,
    loadErrorText: "读取远程账号失败",
    fetchItems: async (conn) => {
      const data = await fetchCPAPoolFiles(conn.id);
      return normalizeRemoteFiles(data.files);
    },
    toItemView: (item) => ({
      key: item.name,
      primary: item.email || item.name,
      secondary: item.name,
    }),
    filterItem: (item, query) =>
      item.email.toLowerCase().includes(query) || item.name.toLowerCase().includes(query),
    searchPlaceholder: "搜索 email 或文件名",
    emptyText: "没有匹配的远程账号",
    originText: (conn) => `来自 ${conn.name || conn.base_url}`,
    startImport: async (connId, keys) => {
      const result = await startCPAImport(connId, keys);
      return result.import_job;
    },
  },
};
