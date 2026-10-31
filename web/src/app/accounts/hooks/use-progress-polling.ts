"use client";

import { useEffect, useRef } from "react";

import type { RefreshProgressResponse } from "@/lib/api/accounts";

// 统一的后端进度轮询 hook：收敛账号页原本 4 处各自为政的 setInterval 轮询
// （审计 F-高5 轮询泄漏 / F-中6 进度轮询 4 种写法）。
// 所有定时器登记在 ref 中，组件卸载时统一清理，杜绝卸载后继续 setState。

type PollOptions = {
  /** 轮询间隔，默认 300ms（与后端进度刷新粒度匹配） */
  intervalMs?: number;
  /** 每次轮询到未完成的中间进度时回调 */
  onUpdate?: (progress: RefreshProgressResponse) => void;
};

type TimerId = ReturnType<typeof setInterval> | ReturnType<typeof setTimeout>;

export function useProgressPolling() {
  const timersRef = useRef<Set<TimerId>>(new Set());

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const timerId of timers) {
        clearInterval(timerId);
        clearTimeout(timerId);
      }
      timers.clear();
    };
  }, []);

  const registerInterval = (callback: () => void, intervalMs: number) => {
    const timerId = setInterval(callback, intervalMs);
    timersRef.current.add(timerId);
    return timerId;
  };

  /** 受管 setTimeout：到点自动移出登记表，卸载时同样会被清理 */
  const wait = (ms: number) =>
    new Promise<void>((resolve) => {
      const timerId = setTimeout(() => {
        timersRef.current.delete(timerId);
        resolve();
      }, ms);
      timersRef.current.add(timerId);
    });

  /** 轮询直到 done：完成时返回最后一次进度响应；后端报错或请求失败时 reject */
  const poll = (
    fetchProgress: () => Promise<RefreshProgressResponse>,
    options: PollOptions = {},
  ): Promise<RefreshProgressResponse> => {
    const { intervalMs = 300, onUpdate } = options;
    return new Promise<RefreshProgressResponse>((resolve, reject) => {
      const timerId = registerInterval(() => {
        void (async () => {
          try {
            const progress = await fetchProgress();
            if (progress.done) {
              clearInterval(timerId);
              timersRef.current.delete(timerId);
              if (progress.error) {
                reject(new Error(progress.error));
                return;
              }
              onUpdate?.(progress);
              resolve(progress);
            } else {
              onUpdate?.(progress);
            }
          } catch (error) {
            clearInterval(timerId);
            timersRef.current.delete(timerId);
            reject(error instanceof Error ? error : new Error(String(error)));
          }
        })();
      }, intervalMs);
    });
  };

  return { poll, wait };
}
