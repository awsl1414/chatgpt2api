"use client";

import type { ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

import { useAuthGuard } from "@/lib/use-auth-guard";
import type { AuthRole } from "@/store/auth";

type AuthGuardProps = {
  /** 允许访问的角色；为空表示任意已登录角色 */
  roles?: AuthRole[];
  /** 校验通过后渲染的页面内容 */
  children: (session: NonNullable<ReturnType<typeof useAuthGuard>["session"]>) => ReactNode;
};

/**
 * 页面级登录守卫：统一「校验中 / 未登录 / 角色不符」三态渲染。
 * 审计 F-中2：各页面整页复制的 gate + spinner 样板收敛到此组件。
 * 未登录与角色不符由 useAuthGuard 负责跳转，这里只负责占位与放行。
 */
export function AuthGuard({ roles, children }: AuthGuardProps) {
  const { isCheckingAuth, session } = useAuthGuard(roles);
  const roleAllowed = !roles || (session !== null && roles.includes(session.role));

  if (isCheckingAuth || !session || !roleAllowed) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <>{children(session)}</>;
}
