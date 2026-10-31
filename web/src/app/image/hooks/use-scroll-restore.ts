"use client";

import { useCallback, useEffect, useLayoutEffect, useRef } from "react";

import { SCROLL_POSITIONS_STORAGE_KEY } from "@/lib/image-storage-keys";
import type { ImageConversation } from "@/store/image-conversations";

/** 距底部超过该阈值视为「离开最新消息」，显示回到底部按钮 */
const SCROLL_TO_LATEST_THRESHOLD = 160;

/** 从 sessionStorage 读取各会话的滚动位置快照 */
function loadScrollPositions(): Map<string, number> {
  if (typeof window === "undefined") return new Map();
  try {
    const raw = window.sessionStorage.getItem(SCROLL_POSITIONS_STORAGE_KEY);
    if (!raw) return new Map();
    const parsed = JSON.parse(raw) as Record<string, number>;
    return new Map(Object.entries(parsed));
  } catch {
    return new Map();
  }
}

/** 把各会话滚动位置快照写入 sessionStorage（空间不足时静默丢弃） */
function saveScrollPositions(positions: Map<string, number>) {
  if (typeof window === "undefined") return;
  try {
    const obj: Record<string, number> = {};
    positions.forEach((value, key) => { obj[key] = value; });
    window.sessionStorage.setItem(SCROLL_POSITIONS_STORAGE_KEY, JSON.stringify(obj));
  } catch {
    // sessionStorage may be full or unavailable
  }
}

function getResultsDistanceFromBottom(element: HTMLElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight;
}

type UseScrollRestoreResult = {
  /** 结果区滚动容器 ref */
  resultsViewportRef: React.RefObject<HTMLDivElement | null>;
  /** 「滚动到最新消息」悬浮按钮 ref（显隐由滚动逻辑直接操作 DOM） */
  scrollToLatestBtnRef: React.RefObject<HTMLButtonElement | null>;
  /** 绑定到滚动容器的 onScroll 处理（rAF 节流 + debounce 保存位置） */
  handleResultsScroll: () => void;
  /** 平滑滚动到底部并进入粘底模式 */
  scrollResultsToLatest: (behavior?: ScrollBehavior) => void;
  /** 提交/新建时调用：进入粘底模式并隐藏悬浮按钮 */
  stickToBottom: () => void;
};

/**
 * 图片会话结果区的滚动位置保存/恢复（审计 §5）：
 * - 滚动时 debounce 300ms 把当前会话 scrollTop 存入 sessionStorage；
 * - 切换会话时先保存旧会话位置，若有快照则隐藏容器后双 rAF 恢复，避免看到顶部闪烁；
 * - 无快照时按粘底（跟随最新）逻辑处理；卸载时落盘当前位置；
 * - 粘底判定基于距底部阈值，恢复期间忽略滚动事件。
 */
export function useScrollRestore(conversation: ImageConversation | null): UseScrollRestoreResult {
  const resultsViewportRef = useRef<HTMLDivElement>(null);
  const scrollToLatestBtnRef = useRef<HTMLButtonElement>(null);
  const lastConversationIdRef = useRef<string | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const scrollRafRef = useRef<number | null>(null);
  const scrollSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollPositionsRef = useRef<Map<string, number>>(loadScrollPositions());
  const isRestoringScrollRef = useRef(false);
  const scrollRestoreGenerationRef = useRef(0);

  const scrollResultsToLatest = useCallback((behavior: ScrollBehavior = "smooth") => {
    const element = resultsViewportRef.current;
    if (!element) {
      return;
    }

    shouldStickToBottomRef.current = true;
    const btn = scrollToLatestBtnRef.current;
    if (btn) btn.style.display = "none";
    element.scrollTo({
      top: element.scrollHeight,
      behavior,
    });
  }, []);

  const stickToBottom = useCallback(() => {
    shouldStickToBottomRef.current = true;
    const btn = scrollToLatestBtnRef.current;
    if (btn) btn.style.display = "none";
  }, []);

  const handleResultsScroll = useCallback(() => {
    if (scrollRafRef.current !== null) {
      return;
    }

    scrollRafRef.current = window.requestAnimationFrame(() => {
      scrollRafRef.current = null;
      const element = resultsViewportRef.current;
      if (!element) {
        return;
      }

      // 恢复滚动位置期间不处理滚动事件
      if (isRestoringScrollRef.current) {
        return;
      }

      // 保存当前会话的滚动位置（debounce 300ms 写入 sessionStorage）
      const convId = lastConversationIdRef.current;
      if (convId) {
        scrollPositionsRef.current.set(convId, element.scrollTop);
        if (scrollSaveTimerRef.current) clearTimeout(scrollSaveTimerRef.current);
        scrollSaveTimerRef.current = setTimeout(() => {
          scrollSaveTimerRef.current = null;
          saveScrollPositions(scrollPositionsRef.current);
        }, 300);
      }

      const isAwayFromLatest = getResultsDistanceFromBottom(element) > SCROLL_TO_LATEST_THRESHOLD;
      shouldStickToBottomRef.current = !isAwayFromLatest;
      // 直接操作 DOM 控制按钮显隐，避免 setState 触发全组件重渲染
      const btn = scrollToLatestBtnRef.current;
      if (btn) {
        if (isAwayFromLatest) {
          btn.style.display = "";
        } else {
          btn.style.display = "none";
        }
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
      }
      if (scrollSaveTimerRef.current !== null) {
        clearTimeout(scrollSaveTimerRef.current);
      }
      // 组件卸载时保存当前会话滚动位置到 sessionStorage
      const element = resultsViewportRef.current;
      const convId = lastConversationIdRef.current;
      if (element && convId) {
        scrollPositionsRef.current.set(convId, element.scrollTop);
      }
      saveScrollPositions(scrollPositionsRef.current);
    };
  }, []);

  // 切换会话时保存旧会话滚动位置，并隐藏容器防止闪烁
  useLayoutEffect(() => {
    if (!conversation) {
      lastConversationIdRef.current = null;
      shouldStickToBottomRef.current = true;
      const btn = scrollToLatestBtnRef.current;
      if (btn) btn.style.display = "none";
      return;
    }

    const element = resultsViewportRef.current;
    if (!element) {
      return;
    }

    const didSwitchConversation = lastConversationIdRef.current !== conversation.id;

    if (didSwitchConversation) {
      // 递增 generation，使之前未完成的 rAF 回调失效
      scrollRestoreGenerationRef.current += 1;

      // 先保存旧会话的滚动位置（lastConversationIdRef 还是旧值）
      const oldConvId = lastConversationIdRef.current;
      if (oldConvId) {
        scrollPositionsRef.current.set(oldConvId, element.scrollTop);
        saveScrollPositions(scrollPositionsRef.current);
      }
      // 更新为新会话 ID
      lastConversationIdRef.current = conversation.id;

      // 如果有保存的滚动位置，隐藏容器防止用户看到 scrollTop=0 的内容
      const savedScrollTop = scrollPositionsRef.current.get(conversation.id);
      if (savedScrollTop != null && savedScrollTop > 0) {
        element.style.visibility = "hidden";
        isRestoringScrollRef.current = true;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在会话切换时执行一次
  }, [conversation?.id]);

  // 恢复滚动位置或跟随最新内容
  useEffect(() => {
    if (!conversation) {
      return;
    }

    const element = resultsViewportRef.current;
    if (!element) {
      return;
    }

    const savedScrollTop = scrollPositionsRef.current.get(conversation.id);

    if (savedScrollTop != null && savedScrollTop > 0) {
      // 捕获当前 generation，用于检测是否已被新的切换取代
      const generation = scrollRestoreGenerationRef.current;
      // 容器已在 useLayoutEffect 中设为 visibility:hidden，用户看不到滚动过程
      requestAnimationFrame(() => {
        // 如果 generation 已变，说明用户又切换了，放弃本次恢复
        if (scrollRestoreGenerationRef.current !== generation) return;
        element.scrollTop = savedScrollTop;
        // 再等一帧确保 scrollTop 生效后再显示容器
        requestAnimationFrame(() => {
          // 再次检查 generation
          if (scrollRestoreGenerationRef.current !== generation) return;
          const isAwayFromLatest = getResultsDistanceFromBottom(element) > SCROLL_TO_LATEST_THRESHOLD;
          shouldStickToBottomRef.current = !isAwayFromLatest;
          const btn = scrollToLatestBtnRef.current;
          if (btn) btn.style.display = isAwayFromLatest ? "" : "none";
          // 显示容器 — 用户直接看到正确位置的内容
          element.style.visibility = "";
          isRestoringScrollRef.current = false;
        });
      });
      // 恢复后清除保存的位置，下次内容更新时走正常的 shouldFollowLatest 逻辑
      scrollPositionsRef.current.delete(conversation.id);
      return;
    }

    // 无保存位置，按正常逻辑处理
    const shouldFollowLatest =
      shouldStickToBottomRef.current ||
      getResultsDistanceFromBottom(element) <= SCROLL_TO_LATEST_THRESHOLD;

    if (shouldFollowLatest) {
      requestAnimationFrame(() => scrollResultsToLatest("smooth"));
      return;
    }

    const btn = scrollToLatestBtnRef.current;
    if (btn) btn.style.display = "";
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 会话内容变化（updatedAt/轮数）时重新执行
  }, [conversation?.id, conversation?.updatedAt, conversation?.turns.length, scrollResultsToLatest]);

  return {
    resultsViewportRef,
    scrollToLatestBtnRef,
    handleResultsScroll,
    scrollResultsToLatest,
    stickToBottom,
  };
}
