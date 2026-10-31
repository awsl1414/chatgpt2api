"use client";

import { AuthGuard } from "@/components/auth-guard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ChatPanel } from "./components/chat-panel";
import { PptPanel } from "./components/ppt-panel";
import { PsdPanel } from "./components/psd-panel";
import { SearchPanel } from "./components/search-panel";
import { SkillPanel } from "./components/skill-panel";

const tabs = [
  { value: "skills", title: "搜索Skills" },
  { value: "search", title: "搜索" },
  { value: "ppt", title: "PPT生成" },
  { value: "psd", title: "PSD生成" },
  { value: "chat", title: "对话" },
];

export default function DebugPage() {
  return (
    <AuthGuard roles={["admin"]}>
      {() => (
        <Tabs defaultValue="skills" className="mx-auto flex min-h-[calc(100vh-49px)] w-full max-w-[1600px] flex-col gap-4 px-4 pt-3 pb-6 md:px-8">
          <TabsList variant="line" className="w-full">
            {tabs.map(({ value, title }) => (
              <TabsTrigger key={value} value={value}>
                {title}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="skills">
            <SkillPanel />
          </TabsContent>
          <TabsContent value="search" className="min-h-0">
            <SearchPanel />
          </TabsContent>
          <TabsContent value="ppt" className="min-h-0">
            <PptPanel />
          </TabsContent>
          <TabsContent value="psd" className="min-h-0">
            <PsdPanel />
          </TabsContent>
          <TabsContent value="chat" className="min-h-0">
            <ChatPanel />
          </TabsContent>
        </Tabs>
      )}
    </AuthGuard>
  );
}
