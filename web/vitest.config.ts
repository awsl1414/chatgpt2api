import path from "node:path";

import { defineConfig } from "vitest/config";

// 单测配置：node 环境 + "@" 别名对齐 tsconfig paths，仅收集 src 下的 .test.ts
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
