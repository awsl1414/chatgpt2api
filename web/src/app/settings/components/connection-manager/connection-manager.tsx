"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Import, LoaderCircle, Pencil, Plus, Save, Search, ServerCog, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { useInitialLoad } from "@/hooks/use-initial-load";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { actionError } from "@/lib/action-result";

import { ImportJobPanel } from "./import-job-panel";
import { usePagination } from "@/hooks/use-pagination";
import { PAGE_SIZE_OPTIONS, type ConnectionAdapter, type ConnectionRecord } from "./types";

type ConnectionManagerProps<TConn extends ConnectionRecord, TForm, TItem> = {
  adapter: ConnectionAdapter<TConn, TForm, TItem>;
};

const POLL_INTERVAL_MS = 1500;

/**
 * 「连接管理 + 浏览导入」公共组件（审计 F-中4）：
 * 连接列表、编辑 Dialog、浏览导入 Dialog 与 import_job 轮询全部在此实现，
 * CPA 与 Sub2API 通过各自的 ConnectionAdapter 复用同一套交互。
 * 连接列表是服务端数据快照，只保存在本组件局部状态（审计 F-高3）。
 */
export function ConnectionManager<TConn extends ConnectionRecord, TForm, TItem>({
  adapter,
}: ConnectionManagerProps<TConn, TForm, TItem>) {
  const pollTimerRef = useRef<number | null>(null);

  const [connections, setConnections] = useState<TConn[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loadingItemsId, setLoadingItemsId] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TConn | null>(null);
  const [form, setForm] = useState<TForm>(() => adapter.edit.createForm(null));
  const [isSaving, setIsSaving] = useState(false);

  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserConn, setBrowserConn] = useState<TConn | null>(null);
  const [remoteItems, setRemoteItems] = useState<TItem[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [itemQuery, setItemQuery] = useState("");
  const [isStartingImport, setIsStartingImport] = useState(false);

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const refreshConnections = async (silent = false) => {
    if (!silent) {
      setIsLoading(true);
    }
    try {
      const data = await adapter.fetchConnections();
      setConnections(data);
    } catch (error) {
      if (silent) {
        // 轮询导入进度失败时停止轮询，避免每 1.5s 反复报错
        stopPolling();
        toast.error("查询导入进度失败");
        return;
      }
      toast.error(actionError(error, adapter.loadErrorText));
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  };

  useInitialLoad(() => {
    void refreshConnections();
  });

  // 有 pending/running 的导入任务时每 1.5s 轮询连接列表刷新进度
  useEffect(() => {
    const hasRunningJobs = connections.some((conn) => {
      const status = conn.import_job?.status;
      return status === "pending" || status === "running";
    });
    if (!hasRunningJobs) {
      stopPolling();
      return;
    }
    pollTimerRef.current = window.setInterval(() => {
      void refreshConnections(true);
    }, POLL_INTERVAL_MS);
    return () => stopPolling();
  }, [connections]);

  const openAddDialog = () => {
    setEditing(null);
    setForm(adapter.edit.createForm(null));
    setDialogOpen(true);
  };

  const openEditDialog = (conn: TConn) => {
    setEditing(conn);
    setForm(adapter.edit.createForm(conn));
    setDialogOpen(true);
  };

  const patchForm = (patch: Partial<TForm>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const handleSave = async () => {
    const validationError = adapter.edit.validate(form, editing);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    setIsSaving(true);
    try {
      const list = await adapter.edit.save(form, editing);
      setConnections(list);
      setDialogOpen(false);
      toast.success(editing ? "连接已更新" : "连接已添加");
    } catch (error) {
      toast.error(actionError(error, "保存失败"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (conn: TConn) => {
    setDeletingId(conn.id);
    try {
      const list = await adapter.deleteConnection(conn.id);
      setConnections(list);
      toast.success("连接已删除");
    } catch (error) {
      toast.error(actionError(error, "删除失败"));
    } finally {
      setDeletingId(null);
    }
  };

  const handleBrowse = async (conn: TConn) => {
    setLoadingItemsId(conn.id);
    try {
      const items = await adapter.browse.fetchItems(conn);
      setRemoteItems(items);
      setBrowserConn(conn);
      setSelectedKeys([]);
      setItemQuery("");
      setItemPage(1);
      setBrowserOpen(true);
      toast.success(adapter.browse.loadSuccessText(items.length));
    } catch (error) {
      toast.error(actionError(error, adapter.browse.loadErrorText));
    } finally {
      setLoadingItemsId(null);
    }
  };

  // 远程条目 → 展示视图，与原始条目一一对应，便于筛选时复用各域自己的 filterItem
  const itemPairs = useMemo(
    () => remoteItems.map((item) => ({ item, view: adapter.browse.toItemView(item) })),
    [remoteItems, adapter],
  );

  const filteredPairs = useMemo(() => {
    const query = itemQuery.trim().toLowerCase();
    if (!query) {
      return itemPairs;
    }
    return itemPairs.filter((pair) => adapter.browse.filterItem(pair.item, query));
  }, [itemQuery, itemPairs, adapter]);

  const filteredViews = filteredPairs.map((pair) => pair.view);

  const { page: safePage, pageCount, pageSize, setPageSize, setPage: setItemPage, pageItems: pagedViews } =
    usePagination(filteredViews, "100");
  const allFilteredSelected =
    filteredViews.length > 0 && filteredViews.every((view) => selectedKeys.includes(view.key));

  const toggleItem = (key: string, checked: boolean) => {
    setSelectedKeys((prev) => {
      if (checked) {
        return Array.from(new Set([...prev, key]));
      }
      return prev.filter((item) => item !== key);
    });
  };

  const handleToggleSelectAllFiltered = (checked: boolean) => {
    if (checked) {
      setSelectedKeys(Array.from(new Set([...selectedKeys, ...filteredViews.map((view) => view.key)])));
      return;
    }
    const filteredSet = new Set(filteredViews.map((view) => view.key));
    setSelectedKeys((prev) => prev.filter((key) => !filteredSet.has(key)));
  };

  const handleStartImport = async () => {
    if (!browserConn) {
      return;
    }
    if (selectedKeys.length === 0) {
      toast.error("请先选择要导入的账号");
      return;
    }

    setIsStartingImport(true);
    try {
      const job = await adapter.browse.startImport(browserConn.id, selectedKeys);
      setConnections((prev) =>
        prev.map((conn) => (conn.id === browserConn.id ? { ...conn, import_job: job } : conn)),
      );
      setBrowserOpen(false);
      toast.success("导入任务已启动");
    } catch (error) {
      toast.error(actionError(error, "启动导入失败"));
    } finally {
      setIsStartingImport(false);
    }
  };

  return (
    <>
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-6 p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-stone-100">
                <ServerCog className="size-5 text-stone-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{adapter.title}</h2>
                <p className="text-sm text-stone-500">{adapter.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {connections.length > 0 ? <Badge className="rounded-md px-2.5 py-1">{connections.length} 个连接</Badge> : null}
              <Button
                className="h-9 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
                onClick={openAddDialog}
              >
                <Plus className="size-4" />
                添加连接
              </Button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-10">
              <LoaderCircle className="size-5 animate-spin text-stone-400" />
            </div>
          ) : connections.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-stone-50 px-6 py-10 text-center">
              <ServerCog className="size-8 text-stone-300" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-stone-600">{adapter.emptyTitle}</p>
                <p className="text-sm text-stone-400">{adapter.emptyHint}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {connections.map((conn) => {
                const isBusy = deletingId === conn.id || loadingItemsId === conn.id;
                return (
                  <div key={conn.id} className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-stone-800">{conn.name || conn.base_url}</div>
                        <div className="truncate text-xs text-stone-400">{adapter.connectionSubtitle(conn)}</div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          className="rounded-lg p-2 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700"
                          onClick={() => openEditDialog(conn)}
                          disabled={isBusy}
                          title="编辑"
                        >
                          <Pencil className="size-4" />
                        </button>
                        <button
                          type="button"
                          className="rounded-lg p-2 text-stone-400 transition hover:bg-rose-50 hover:text-rose-500"
                          onClick={() => void handleDelete(conn)}
                          disabled={isBusy}
                          title="删除"
                        >
                          {deletingId === conn.id ? (
                            <LoaderCircle className="size-4 animate-spin" />
                          ) : (
                            <Trash2 className="size-4" />
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        className="h-8 rounded-lg border-stone-200 bg-white px-3 text-xs text-stone-600"
                        onClick={() => void handleBrowse(conn)}
                        disabled={isBusy}
                      >
                        {loadingItemsId === conn.id ? (
                          <LoaderCircle className="size-3.5 animate-spin" />
                        ) : (
                          <Import className="size-3.5" />
                        )}
                        同步
                      </Button>
                    </div>

                    {conn.import_job ? <ImportJobPanel job={conn.import_job} /> : null}
                  </div>
                );
              })}
            </div>
          )}

          <div className="rounded-xl bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-500">
            <p className="font-medium text-stone-600">使用说明</p>
            <ul className="mt-1 list-inside list-disc space-y-0.5">{adapter.usageNotes}</ul>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent showCloseButton={false} className="rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>{editing ? "编辑连接" : "添加连接"}</DialogTitle>
            <DialogDescription className="text-sm leading-6">
              {editing ? adapter.edit.editDescription : adapter.edit.addDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">{adapter.edit.renderFields({ form, patchForm, editing })}</div>
          <DialogFooter className="pt-2">
            <Button
              variant="secondary"
              className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
              onClick={() => setDialogOpen(false)}
              disabled={isSaving}
            >
              取消
            </Button>
            <Button
              className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
              onClick={() => void handleSave()}
              disabled={isSaving}
            >
              {isSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
              {editing ? "保存修改" : "添加"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={browserOpen} onOpenChange={setBrowserOpen}>
        <DialogContent showCloseButton={false} className="max-h-[90vh] max-w-5xl rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>选择要导入的账号</DialogTitle>
            <DialogDescription className="text-sm leading-6">
              {browserConn ? adapter.browse.originText(browserConn) : adapter.title}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative min-w-[260px]">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-stone-400" />
              <Input
                value={itemQuery}
                onChange={(event) => {
                  setItemQuery(event.target.value);
                  setItemPage(1);
                }}
                placeholder={adapter.browse.searchPlaceholder}
                className="h-10 rounded-xl border-stone-200 bg-white pl-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={pageSize}
                onValueChange={setPageSize}
              >
                <SelectTrigger className="h-10 w-[120px] rounded-xl border-stone-200 bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZE_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option} / 页
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
                onClick={() => handleToggleSelectAllFiltered(!allFilteredSelected)}
              >
                {allFilteredSelected ? "取消全选" : "全选筛选结果"}
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-stone-200">
            <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3 text-sm text-stone-500">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={allFilteredSelected}
                  onCheckedChange={(checked) => handleToggleSelectAllFiltered(Boolean(checked))}
                />
                <span>筛选结果 {filteredViews.length} 个</span>
              </div>
              <span>已选 {selectedKeys.length} 个</span>
            </div>
            <div className="max-h-[420px] overflow-auto">
              {pagedViews.length === 0 ? (
                <div className="flex items-center justify-center py-12 text-sm text-stone-400">
                  {adapter.browse.emptyText}
                </div>
              ) : (
                <div className="divide-y divide-stone-100">
                  {pagedViews.map((view) => (
                    <label key={view.key} className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-stone-50">
                      <Checkbox
                        checked={selectedKeys.includes(view.key)}
                        onCheckedChange={(checked) => toggleItem(view.key, Boolean(checked))}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-stone-700">{view.primary}</span>
                          {(view.badges ?? []).map((badge) => (
                            <Badge
                              key={badge.text}
                              variant={badge.tone}
                              className={badge.tone ? "rounded-md" : "rounded-md bg-stone-100 text-stone-600"}
                            >
                              {badge.text}
                            </Badge>
                          ))}
                        </div>
                        {view.secondary ? (
                          <div className="truncate text-xs text-stone-400">{view.secondary}</div>
                        ) : null}
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between text-sm text-stone-500">
            <span>
              第 {filteredViews.length === 0 ? 0 : (safePage - 1) * Number(pageSize) + 1} -{" "}
              {Math.min(safePage * Number(pageSize), filteredViews.length)} 条，共 {filteredViews.length} 条
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-3"
                onClick={() => setItemPage(Math.max(1, safePage - 1))}
                disabled={safePage <= 1}
              >
                上一页
              </Button>
              <span>
                {safePage}/{pageCount}
              </span>
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-3"
                onClick={() => setItemPage(Math.min(pageCount, safePage + 1))}
                disabled={safePage >= pageCount}
              >
                下一页
              </Button>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              variant="secondary"
              className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
              onClick={() => setBrowserOpen(false)}
              disabled={isStartingImport}
            >
              取消
            </Button>
            <Button
              className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
              onClick={() => void handleStartImport()}
              disabled={isStartingImport || selectedKeys.length === 0}
            >
              {isStartingImport ? <LoaderCircle className="size-4 animate-spin" /> : <Import className="size-4" />}
              导入选中账号
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
