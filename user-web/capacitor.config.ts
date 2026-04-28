import type { CapacitorConfig } from "@capacitor/cli";

/**
 * 阶段 20.2：最小 App 壳（Web 资源来自 `vite build` 输出目录 `dist`）。
 * 使用 `npm run build:cap`（`--base ./`）以便在 file/capacitor 协议下正确解析资源。
 */
const config: CapacitorConfig = {
  /** 拉丁路径标识 OM_Media → 反向域名应用 ID（界面 appName 仍为「恒频OM」） */
  appId: "com.ommedia.user",
  appName: "恒频OM",
  webDir: "dist",
  /**
   * 开发期若 API 为 HTTP：允许 WebView 明文（生产请改 HTTPS 并在原生侧关闭）。
   * @see docs/CAPACITOR_20.2.md
   */
  server: {
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
