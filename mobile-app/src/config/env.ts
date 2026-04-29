import { getExpoGoProjectConfig } from "expo";
import { Platform } from "react-native";
import Constants from "expo-constants";

const DEV_BACKEND_PORT = 8000;

type Extra = { apiBaseUrl?: string; turnstileSiteKey?: string; turnstileOrigin?: string };

function fromExtra(): string {
  const extra = Constants.expoConfig?.extra as Extra | undefined;
  return (extra?.apiBaseUrl ?? "").trim();
}

function fromEnv(): string {
  if (typeof process === "undefined" || !process.env) return "";
  return (process.env.EXPO_PUBLIC_API_BASE_URL ?? "").trim();
}

function turnstileSiteKeyFromEnv(): string {
  if (typeof process === "undefined" || !process.env) return "";
  return (process.env.EXPO_PUBLIC_TURNSTILE_SITE_KEY ?? "").trim();
}

function turnstileOriginFromEnv(): string {
  if (typeof process === "undefined" || !process.env) return "";
  return (process.env.EXPO_PUBLIC_TURNSTILE_ORIGIN ?? "").trim();
}

/** 开发模式下最近一次因非法而忽略的显式 API 配置（用于 Feed 提示） */
let lastIgnoredInvalidRaw: string | null = null;

export function getLastIgnoredInvalidApiRaw(): string | null {
  return lastIgnoredInvalidRaw;
}

/**
 * 检测「从文档复制但未替换」的占位符或非法示例。
 */
export function validateApiBaseUrl(raw: string): string | null {
  const t = raw.trim();
  if (!t) return null;

  const placeholderPatterns: RegExp[] = [
    /你的后端/i,
    /你的电脑/i,
    /电脑局域网IP/i,
    /局域网IP/i,
    /your-host/i,
    /yourhost/i,
    /replace-me/i,
    /changeme/i,
    /<\s*https?:/i,
    /\$\{\s*[^}]+\s*\}/,
  ];
  for (const re of placeholderPatterns) {
    if (re.test(t)) {
      return `API 地址含有未替换的占位符或示例文案。请改为真实地址，例如：http://192.168.1.100:8000/api/v1`;
    }
  }

  try {
    const u = new URL(t);
    if (!u.hostname) return "API 地址缺少主机名";
  } catch {
    return "API 地址不是合法 URL（需含协议与主机，如 http://192.168.1.100:8000/api/v1）";
  }

  return null;
}

/**
 * 仅生产构建：显式配置了非法 URL 时返回说明。开发模式会回退到本机默认，不返回错误以免无法登录。
 */
export function getApiConfigurationError(): string | null {
  if (__DEV__) return null;
  const raw = (fromExtra() || fromEnv()).trim();
  if (!raw) return null;
  return validateApiBaseUrl(raw);
}

/** Web：HTTPS 页面请求 HTTP API 会被浏览器拦截 */
export function getWebMixedContentError(apiBase: string): string | null {
  if (Platform.OS !== "web") return null;
  const loc = (globalThis as { location?: { protocol?: string } }).location;
  if (!loc?.protocol || loc.protocol !== "https:") return null;
  if (apiBase.toLowerCase().startsWith("http://")) {
    return "当前页面为 HTTPS，不能请求 HTTP 接口（混合内容策略）。请将后端配置为 HTTPS，或在开发时用 HTTP 打开前端（如 http://localhost:8081）。";
  }
  return null;
}

/**
 * 从 Metro / Expo 注入的调试主机解析「开发电脑」主机名（真机扫 QR 连 Metro 时通常为局域网 IPv4）。
 */
function hostFromDebuggerStyle(raw: string): string | null {
  const t = raw.trim();
  if (!t) return null;
  if (t.startsWith("[")) {
    const end = t.indexOf("]");
    if (end > 1) return t.slice(1, end).trim();
    return null;
  }
  const lastColon = t.lastIndexOf(":");
  if (lastColon > 0 && /^\d+$/.test(t.slice(lastColon + 1))) {
    return t.slice(0, lastColon).trim();
  }
  return t;
}

/** 隧道 / 公网入口：不能当作本机 API 的默认主机 */
function isUnsuitablePackagerHost(hostname: string): boolean {
  const h = hostname.trim().toLowerCase();
  if (!h || h === "localhost" || h === "127.0.0.1") return true;
  if (h === "10.0.2.2") return true;
  return /\.(exp\.direct|ngrok\.io|ngrok-free\.app)$/i.test(h) || /\.tunnel\./i.test(h);
}

function getDevPackagerHostname(): string | null {
  const dbg = getExpoGoProjectConfig()?.debuggerHost?.trim();
  if (dbg) {
    const host = hostFromDebuggerStyle(dbg);
    if (host && !isUnsuitablePackagerHost(host)) return host;
  }

  const hostUri = Constants.expoConfig?.hostUri?.trim();
  if (hostUri) {
    try {
      if (hostUri.includes("://")) {
        const u = new URL(hostUri);
        if (u.hostname && !isUnsuitablePackagerHost(u.hostname)) return u.hostname;
      } else {
        const host = hostFromDebuggerStyle(hostUri);
        if (host && !isUnsuitablePackagerHost(host)) return host;
      }
    } catch {
      const host = hostFromDebuggerStyle(hostUri);
      if (host && !isUnsuitablePackagerHost(host)) return host;
    }
  }

  const legacy = (Constants.expoGoConfig as { debuggerHost?: string } | null)?.debuggerHost?.trim();
  if (legacy) {
    const host = hostFromDebuggerStyle(legacy);
    if (host && !isUnsuitablePackagerHost(host)) return host;
  }

  return null;
}

/**
 * 开发默认 API 根：
 * - **真机**：尽量用 Expo/Metro 提供的调试主机（与扫码连 Metro 的电脑 IP 一致），无需手写 .env 局域网 IP。
 * - Android 模拟器 → 10.0.2.2；iOS 模拟器 / Web → 127.0.0.1。
 */
export function getDevApiFallback(): string {
  if (__DEV__ && Constants.isDevice === true && Platform.OS !== "web") {
    const lan = getDevPackagerHostname();
    if (lan) {
      return `http://${lan}:${DEV_BACKEND_PORT}/api/v1`;
    }
  }

  if (Platform.OS === "android") return `http://10.0.2.2:${DEV_BACKEND_PORT}/api/v1`;
  return `http://127.0.0.1:${DEV_BACKEND_PORT}/api/v1`;
}

export const LAN_DEPLOY_HINT =
  "本机作服务器时：手机与电脑同 Wi‑Fi；手动配置时请填电脑局域网 IP。仅起 local-beta（Nginx:8080）用 :8080；仅起 backend compose（API:8000）用 :8000。未配置时开发模式会尽量从 Metro 调试主机推断。";

/**
 * API 根路径。
 * - 合法显式配置：直接使用。
 * - 占位符等非法显式配置：**开发模式**下忽略并回退到本机默认，保证本地可登录调试。
 * - 未配置：开发模式回退本机默认；生产返回空。
 */
export function getApiBaseUrl(): string {
  const explicit = (fromExtra() || fromEnv()).trim();

  if (explicit && validateApiBaseUrl(explicit) === null) {
    lastIgnoredInvalidRaw = null;
    return explicit.replace(/\/$/, "");
  }

  if (explicit && validateApiBaseUrl(explicit)) {
    if (__DEV__) {
      lastIgnoredInvalidRaw = explicit;
      // eslint-disable-next-line no-console
      console.warn(
        "[OM_Media mobile] EXPO_PUBLIC_API_BASE_URL 无效，已忽略并改用开发默认:",
        getDevApiFallback(),
        "原值:",
        explicit,
      );
    } else {
      lastIgnoredInvalidRaw = null;
      return "";
    }
  }

  if (__DEV__) {
    if (!explicit) {
      lastIgnoredInvalidRaw = null;
    }
    const fb = getDevApiFallback();
    const tail = Constants.isDevice ? "（真机已尽量按 Metro 调试主机推断局域网 IP）" : "";
    // eslint-disable-next-line no-console
    console.warn(`[OM_Media mobile] 未设置有效 EXPO_PUBLIC_API_BASE_URL，已使用开发默认: ${fb}${tail ? ` ${tail}` : ""}`);
    return fb.replace(/\/$/, "");
  }

  lastIgnoredInvalidRaw = null;
  return "";
}

export function hasConfiguredApiBase(): boolean {
  const raw = (fromExtra() || fromEnv()).trim();
  if (!raw) return false;
  return validateApiBaseUrl(raw) === null;
}

export function isInsecureHttpApi(): boolean {
  return getApiBaseUrl().toLowerCase().startsWith("http://");
}

export function getTurnstileSiteKey(): string {
  const extra = Constants.expoConfig?.extra as Extra | undefined;
  return (extra?.turnstileSiteKey ?? turnstileSiteKeyFromEnv()).trim();
}

export function getTurnstileOrigin(): string {
  const extra = Constants.expoConfig?.extra as Extra | undefined;
  const configured = (extra?.turnstileOrigin ?? turnstileOriginFromEnv()).trim();
  if (configured) return configured.replace(/\/$/, "");
  try {
    const api = new URL(getApiBaseUrl());
    return `${api.protocol}//${api.host}`;
  } catch {
    return "https://app.omhengpin.com";
  }
}

export function shouldWarnLanMisconfig(): boolean {
  if (!__DEV__ || Constants.isDevice !== true) return false;
  const u = getApiBaseUrl().toLowerCase();
  if (!u) return false;
  if (u.includes("127.0.0.1") || u.includes("localhost")) return true;
  // 真机上的 10.0.2.2 仅对模拟器有意义，连不到电脑上的后端
  if (u.includes("10.0.2.2")) return true;
  return false;
}
