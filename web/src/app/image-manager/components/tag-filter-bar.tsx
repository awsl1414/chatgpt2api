"use client";

import { Tag, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLongPress } from "@/hooks/use-long-press";

const LONG_PRESS_MS = 800;

type TagFilterBarProps = {
  allTags: string[];
  selectedTags: string[];
  onToggle: (tag: string) => void;
  onClear: () => void;
  /** 长按标签触发删除确认 */
  onRequestDelete: (tag: string) => void;
};

/** 单个标签 chip：点击切换筛选，长按触发删除确认 */
function TagFilterChip({
  tag,
  active,
  onToggle,
  onRequestDelete,
}: {
  tag: string;
  active: boolean;
  onToggle: () => void;
  onRequestDelete: () => void;
}) {
  const { isPressing, ...pressHandlers } = useLongPress(onRequestDelete, LONG_PRESS_MS);

  return (
    <span className="relative inline-flex items-center" {...pressHandlers}>
      <button type="button" onClick={onToggle}>
        <Badge
          variant={active ? "default" : "outline"}
          className={`cursor-pointer rounded-md transition-all hover:opacity-80 ${isPressing ? "ring-2 ring-red-400 ring-offset-1" : ""}`}
        >
          {tag}
        </Badge>
      </button>
      {isPressing ? (
        <span className="pointer-events-none absolute inset-0 overflow-hidden rounded-md">
          <span className="absolute inset-0 animate-[grow_800ms_linear_forwards] rounded-md bg-red-400/20" />
        </span>
      ) : null}
    </span>
  );
}

/** 图片管理页顶部标签筛选条：标签为空时不渲染 */
export function TagFilterBar({ allTags, selectedTags, onToggle, onClear, onRequestDelete }: TagFilterBarProps) {
  if (allTags.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-stone-500">
        <Tag className="mr-1 inline size-3.5" />
        标签筛选：
      </span>
      {allTags.map((tag) => (
        <TagFilterChip
          key={tag}
          tag={tag}
          active={selectedTags.includes(tag)}
          onToggle={() => onToggle(tag)}
          onRequestDelete={() => onRequestDelete(tag)}
        />
      ))}
      {selectedTags.length > 0 ? (
        <button type="button" onClick={onClear}>
          <Badge variant="secondary" className="cursor-pointer rounded-md">
            <X className="mr-0.5 size-3" />
            清除
          </Badge>
        </button>
      ) : null}
    </div>
  );
}
