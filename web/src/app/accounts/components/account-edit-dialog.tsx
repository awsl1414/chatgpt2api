"use client";

import { useState } from "react";
import { Link2, LoaderCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
import { testProxy } from "@/lib/api/settings";
import type { Account, AccountStatus } from "@/lib/api/accounts";
import { actionError } from "@/lib/action-result";

type AccountEditDialogProps = {
  /** 当前编辑的账号；由父组件以 key=access_token 挂载，保证每次打开都从 props 初始化 */
  account: Account;
  isUpdating: boolean;
  onClose: () => void;
  onSubmit: (updates: { status: AccountStatus; proxy: string }) => void;
};

// 编辑 Dialog：修改账号状态与专属代理；代理连通性测试内聚在此，测试结果只做提示不落库
export function AccountEditDialog({ account, isUpdating, onClose, onSubmit }: AccountEditDialogProps) {
  const [editStatus, setEditStatus] = useState<AccountStatus>(account.status);
  const [editProxy, setEditProxy] = useState(account.proxy ?? "");
  const [isTestingProxy, setIsTestingProxy] = useState(false);

  const handleTestProxy = async () => {
    const candidate = editProxy.trim();
    if (!candidate) {
      toast.error("请先填写代理地址");
      return;
    }
    setIsTestingProxy(true);
    try {
      const data = await testProxy(candidate);
      if (data.result.ok) {
        toast.success(`代理可用（${data.result.latency_ms} ms，HTTP ${data.result.status}）`);
      } else {
        toast.error(`代理不可用：${data.result.error ?? "未知错误"}`);
      }
    } catch (error) {
      toast.error(actionError(error, "测试代理失败"));
    } finally {
      setIsTestingProxy(false);
    }
  };

  const statusOptions = ["正常", "限流", "异常", "禁用"] as const;

  return (
    <Dialog open onOpenChange={(open) => (!open ? onClose() : null)}>
      <DialogContent showCloseButton={false} className="rounded-2xl p-6">
        <DialogHeader className="gap-2">
          <DialogTitle>编辑账户</DialogTitle>
          <DialogDescription className="text-sm leading-6">
            手动修改账号状态和专属代理。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">状态</label>
            <Select value={editStatus} onValueChange={(value) => setEditStatus(value as AccountStatus)}>
              <SelectTrigger className="h-11 rounded-xl border-stone-200 bg-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">账号代理</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={editProxy}
                onChange={(event) => setEditProxy(event.target.value)}
                placeholder="留空则按 稳定代理运行时 > 直连 回退，例如 http://127.0.0.1:7890"
                className="h-11 rounded-xl border-stone-200 bg-white"
              />
              <Button
                variant="outline"
                className="h-11 rounded-xl border-stone-200 bg-white px-4 text-stone-700 sm:w-24"
                onClick={() => void handleTestProxy()}
                disabled={isTestingProxy}
              >
                {isTestingProxy ? <LoaderCircle className="size-4 animate-spin" /> : <Link2 className="size-4" />}
                测试
              </Button>
            </div>
          </div>
        </div>
        <DialogFooter className="pt-2">
          <Button
            variant="secondary"
            className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200"
            onClick={onClose}
            disabled={isUpdating}
          >
            取消
          </Button>
          <Button
            className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
            onClick={() => onSubmit({ status: editStatus, proxy: editProxy.trim() })}
            disabled={isUpdating}
          >
            {isUpdating ? <LoaderCircle className="size-4 animate-spin" /> : null}
            保存修改
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
