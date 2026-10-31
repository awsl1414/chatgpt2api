"use client";

import { useCallback, useRef, useState } from "react";

type LongPressHandlers = {
  onMouseDown: (event: React.MouseEvent) => void;
  onMouseUp: () => void;
  onMouseLeave: () => void;
  onTouchStart: (event: React.TouchEvent) => void;
  onTouchEnd: () => void;
};

/**
 * 长按手势 hook：按下超过 `ms` 毫秒后触发 `onLongPress`，松开/移出即取消。
 * 返回的 handlers 可直接展开到元素上；同时暴露 `isPressing` 供 UI 展示按压态。
 * 定时器在组件卸载时不会残留——每次取消都会清理。
 */
export function useLongPress(onLongPress: () => void, ms: number): LongPressHandlers & { isPressing: boolean } {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(false);
  const [isPressing, setIsPressing] = useState(false);

  const stop = useCallback(() => {
    activeRef.current = false;
    setIsPressing(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    activeRef.current = true;
    setIsPressing(true);
    timerRef.current = setTimeout(() => {
      if (activeRef.current) {
        activeRef.current = false;
        setIsPressing(false);
        onLongPress();
      }
    }, ms);
  }, [ms, onLongPress]);

  return {
    isPressing,
    onMouseDown: start,
    onMouseUp: stop,
    onMouseLeave: stop,
    onTouchStart: start,
    onTouchEnd: stop,
  };
}
