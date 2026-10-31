"use client";

import { useEffect, useRef } from "react";

/**
 * 仅在首次挂载时执行一次的加载 hook（strict mode 重挂载安全）。
 * 收敛各页面手写的 didLoadRef + useEffect 守卫三连（审查 R3-L3）。
 * `load` 每次渲染都会是新引用也无妨——守卫保证只执行一次。
 */
export function useInitialLoad(load: () => void): void {
  const didLoadRef = useRef(false);

  useEffect(() => {
    if (didLoadRef.current) {
      return;
    }
    didLoadRef.current = true;
    load();
    // 依赖与旧手写实现的空数组语义一致：仅首次挂载执行
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
