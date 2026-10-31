"use client";

import { toast } from "sonner";

import { AuthGuard } from "@/components/auth-guard";
import { useInitialLoad } from "@/hooks/use-initial-load";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { BackupSettingsCard } from "./components/backup-settings-card";
import { ApiDocsCard } from "./components/api-docs-card";
import { ConfigCard } from "./components/config-card";
import { cpaConnectionAdapter } from "./components/connection-manager/cpa-adapter";
import { ConnectionManager } from "./components/connection-manager/connection-manager";
import { sub2apiConnectionAdapter } from "./components/connection-manager/sub2api-adapter";
import { ProxyRuntimeCard } from "./components/proxy-runtime-card";
import { SettingsHeader } from "./components/settings-header";
import { ThirdPartyAppsCard } from "./components/third-party-apps-card";
import { UserKeysCard } from "./components/user-keys-card";
import { useConfigStore } from "./store/config";

const settingsTabs = [
  { value: "basic", title: "基础配置" },
  { value: "backup", title: "备份" },
  { value: "keys", title: "用户密钥" },
  { value: "api-docs", title: "接口接入" },
  { value: "canvas", title: "画布入口" },
  { value: "proxy", title: "FlareSolverr" },
  { value: "cpa", title: "CPA" },
  { value: "sub2api", title: "Sub2API" },
];

function SettingsDataController() {
  const loadConfig = useConfigStore((state) => state.loadConfig);
  const loadUpstreamModels = useConfigStore((state) => state.loadUpstreamModels);

  useInitialLoad(() => {
    void loadConfig().then((result) => {
      if (!result.ok) {
        toast.error(result.error ?? "加载系统配置失败");
      }
    });
    void loadUpstreamModels();
  });

  return null;
}

function SettingsPageContent() {
  return (
    <>
      <SettingsDataController />
      <SettingsHeader />
      <Tabs defaultValue="basic" className="space-y-4">
        <div className="sticky top-3 z-20 overflow-x-auto rounded-xl border border-white/80 bg-white/90 px-3 py-2 shadow-sm backdrop-blur">
          <TabsList variant="line" className="min-w-max justify-start">
            {settingsTabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value} className="px-4">
                {tab.title}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        <TabsContent value="basic">
          <ConfigCard />
        </TabsContent>
        <TabsContent value="proxy">
          <ProxyRuntimeCard />
        </TabsContent>
        <TabsContent value="backup">
          <BackupSettingsCard />
        </TabsContent>
        <TabsContent value="keys">
          <UserKeysCard />
        </TabsContent>
        <TabsContent value="canvas">
          <ThirdPartyAppsCard />
        </TabsContent>
        <TabsContent value="api-docs">
          <ApiDocsCard />
        </TabsContent>
        <TabsContent value="cpa">
          <ConnectionManager adapter={cpaConnectionAdapter} />
        </TabsContent>
        <TabsContent value="sub2api">
          <ConnectionManager adapter={sub2apiConnectionAdapter} />
        </TabsContent>
      </Tabs>
    </>
  );
}

export default function SettingsPage() {
  return (
    <AuthGuard roles={["admin"]}>
      {() => <SettingsPageContent />}
    </AuthGuard>
  );
}
