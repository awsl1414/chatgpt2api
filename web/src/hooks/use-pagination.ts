"use client";

import { useCallback, useEffect, useState } from "react";

// 统一的分页 hook：替换各页面手写的 page/pageSize/pageCount/safePage 切片逻辑
// （审计 F-中3「手写分页 5 处」的收敛点）。pageSize 以字符串持有，直接适配 Select 的 value。

type UsePaginationResult<T> = {
  /** 当前页码（已收敛到 [1, pageCount] 区间） */
  page: number;
  pageCount: number;
  /** 当前页首条数据在全量列表中的下标（0 起） */
  startIndex: number;
  /** 当前页数据切片 */
  pageItems: T[];
  pageSize: string;
  /** 翻页（入参会被钳制到合法区间） */
  setPage: (page: number) => void;
  /** 修改每页条数并回到第 1 页 */
  setPageSize: (size: string) => void;
  /** 筛选条件变化后重置回第 1 页 */
  resetPage: () => void;
};

export function usePagination<T>(items: T[], initialPageSize = "10"): UsePaginationResult<T> {
  const [page, setPageState] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  const pageCount = Math.max(1, Math.ceil(items.length / Number(pageSize)));
  // 数据量减少（筛选/删除）时页码可能越界，读取时收敛即可，无需额外 effect
  const safePage = Math.min(page, pageCount);
  const startIndex = (safePage - 1) * Number(pageSize);
  const pageItems = items.slice(startIndex, startIndex + Number(pageSize));

  const setPage = useCallback(
    (next: number) => {
      setPageState(Math.min(Math.max(1, next), Math.max(1, Math.ceil(items.length / Number(pageSize)))));
    },
    [items.length, pageSize],
  );

  const setPageSize = useCallback((size: string) => {
    setPageSizeState(size);
    setPageState(1);
  }, []);

  const resetPage = useCallback(() => {
    setPageState(1);
  }, []);

  return { page: safePage, pageCount, startIndex, pageItems, pageSize, setPage, setPageSize, resetPage };
}
