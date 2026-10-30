import type { ReactNode } from "react";

import type { CPAImportJob } from "@/lib/api/cpa";

/** 浏览导入分页的候选页大小，CPA 与 Sub2API 共用 */
export const PAGE_SIZE_OPTIONS = ["50", "100", "200"] as const;

export type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number];

/**
 * 连接记录的最小公共结构：CPA 的 CPAPool 与 Sub2API 的 Sub2APIServer 均满足。
 * import_job 是两家后端共用的导入任务形态（CPAImportJob）。
 */
export type ConnectionRecord = {
  id: string;
  name: string;
  base_url: string;
  import_job?: CPAImportJob | null;
};

/** 浏览导入列表里条目的可选角标 */
export type RemoteItemBadge = {
  text: string;
  tone?: "success" | "info";
};

/** 浏览导入列表条目的展示形态，由适配层从各域的远程数据映射而来 */
export type RemoteItemView = {
  key: string;
  primary: string;
  secondary?: string | null;
  badges?: RemoteItemBadge[];
};

/** 编辑对话框表单渲染入参：form 状态由 ConnectionManager 托管，字段组件只做受控渲染 */
export type ConnectionFormContext<TConn extends ConnectionRecord, TForm> = {
  form: TForm;
  patchForm: (patch: Partial<TForm>) => void;
  editing: TConn | null;
};

/**
 * 「连接管理 + 浏览导入」公共适配层（审计 F-中4）：
 * CPA 与 Sub2API 各提供一个适配器实例，ConnectionManager 依此渲染
 * 连接卡片、编辑 Dialog 与浏览导入 Dialog，并提供 import_job 轮询。
 */
export type ConnectionAdapter<TConn extends ConnectionRecord, TForm, TItem> = {
  /** 卡片标题与副标题，如「CPA 连接管理」 */
  title: string;
  description: string;
  emptyTitle: string;
  emptyHint: string;
  usageNotes: ReactNode;
  /** 首次加载连接列表失败时的提示 */
  loadErrorText: string;

  fetchConnections: () => Promise<TConn[]>;
  deleteConnection: (id: string) => Promise<TConn[]>;
  /** 连接行第二行说明文案（base_url 之外的附加信息） */
  connectionSubtitle: (conn: TConn) => string;

  edit: {
    addDescription: string;
    editDescription: string;
    createForm: (conn: TConn | null) => TForm;
    renderFields: (ctx: ConnectionFormContext<TConn, TForm>) => ReactNode;
    /** 返回校验错误文案；通过时返回 null */
    validate: (form: TForm, editing: TConn | null) => string | null;
    /** 保存并返回最新连接列表；失败时抛错 */
    save: (form: TForm, editing: TConn | null) => Promise<TConn[]>;
  };

  browse: {
    /** 浏览加载成功提示，如「读取成功，共 N 个远程账号」 */
    loadSuccessText: (count: number) => string;
    loadErrorText: string;
    /** 拉取远程条目列表（含去重等规范化） */
    fetchItems: (conn: TConn) => Promise<TItem[]>;
    toItemView: (item: TItem) => RemoteItemView;
    filterItem: (item: TItem, query: string) => boolean;
    searchPlaceholder: string;
    emptyText: string;
    /** 浏览 Dialog 副标题，如「来自 主号池」 */
    originText: (conn: TConn) => string;
    startImport: (connId: string, keys: string[]) => Promise<CPAImportJob | null>;
  };
};
