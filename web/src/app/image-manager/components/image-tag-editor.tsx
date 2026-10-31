"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ManagedImage } from "@/lib/api/images";
import { unusedTags } from "@/lib/image-tags";

type ImageTagEditorProps = {
  image: ManagedImage;
  allTags: string[];
  onAdd: (rawTag: string) => boolean;
  onRemove: (tag: string) => void;
  onPick: (tag: string) => void;
};

/**
 * 单张图片的标签编辑区：已选标签可单独移除，末尾「+」弹层支持输入新标签
 * 或点选已有标签。弹层开关与输入框状态在此本地持有，不上升到页面。
 */
export function ImageTagEditor({ image, allTags, onAdd, onRemove, onPick }: ImageTagEditorProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const candidates = unusedTags(image.tags, allTags);

  const submit = () => {
    if (onAdd(input)) {
      setInput("");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {(image.tags ?? []).map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-0.5 rounded-md py-0 pr-0.5 text-[10px]">
          {tag}
          <button
            type="button"
            className="inline-flex size-3.5 items-center justify-center rounded-full hover:bg-stone-300"
            onClick={() => onRemove(tag)}
          >
            <X className="size-2.5" />
          </button>
        </Badge>
      ))}
      <Popover
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          setInput("");
        }}
      >
        <PopoverTrigger asChild>
          <button
            type="button"
            className="inline-flex size-5 items-center justify-center rounded-full border border-dashed border-stone-300 text-stone-400 hover:border-stone-500 hover:text-stone-600"
            title="添加标签"
          >
            <Plus className="size-3" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-2">
          <div className="space-y-2">
            <div className="text-xs font-medium text-stone-500">添加标签</div>
            <div className="flex gap-1">
              <Input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="输入标签名"
                className="h-8 text-xs"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    submit();
                  }
                }}
              />
              <Button size="icon" variant="outline" className="size-8 shrink-0" onClick={submit}>
                <Plus className="size-3.5" />
              </Button>
            </div>
            {candidates.length > 0 ? (
              <div className="flex flex-wrap gap-1 border-t border-stone-100 pt-2">
                {candidates.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => {
                      onPick(tag);
                      setOpen(false);
                    }}
                  >
                    <Badge variant="outline" className="cursor-pointer rounded-md text-[10px] hover:bg-stone-100">
                      {tag}
                    </Badge>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
