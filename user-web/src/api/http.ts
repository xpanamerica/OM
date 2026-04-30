import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";
import { getAppRouter } from "@/router/ready";
import { handleUserUnauthorizedRedirect } from "./handleUserUnauthorized";
import { enqueueUnauthorized401 } from "./unauthorized401Queue";

declare module "axios" {
  export interface AxiosRequestConfig {
    /** 为 true 时 401 不触发登出与跳转（如探测接口） */
    skipAuthRedirect?: boolean;
    _retryAuthRefresh?: boolean;
  }
}

type TokenResponse = { access_token: string; token_type: string };

let refreshPromise: Promise<string> | null = null;

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const prefix = `${encodeURIComponent(name)}=`;
  const found = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

function csrfHeaders(): Record<string, string> {
  const token = readCookie("om_csrf_token");
  return token ? { "X-CSRF-Token": token } : {};
}

function getBaseURL(): string {
  const u = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!u) throw new Error("缺少环境变量 VITE_API_BASE_URL");
  return u.replace(/\/$/, "");
}

export const http: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 90_000,
  withCredentials: true,
});

async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post<TokenResponse>(`${getBaseURL()}/auth/refresh`, undefined, {
        withCredentials: true,
        headers: csrfHeaders(),
      })
      .then((res) => res.data.access_token)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore();
  const t = auth.token?.trim();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  if (!["get", "head", "options"].includes(String(config.method ?? "get").toLowerCase())) {
    Object.assign(config.headers, csrfHeaders());
  }
  return config;
});

http.interceptors.response.use(
  (res) => res,
  async (err) => {
    const status = err.response?.status;
    const cfg = err.config as InternalAxiosRequestConfig & { skipAuthRedirect?: boolean };
    if (import.meta.env.DEV && status === 404) {
      const base = cfg?.baseURL ?? "";
      const path = cfg?.url ?? "";
      console.warn("[api 404]", String(cfg?.method ?? "GET").toUpperCase(), `${base}${path}`);
    }
    const url = String(cfg?.url ?? "");
    const isAuthEndpoint =
      url.endsWith("/auth/login") || url.endsWith("/auth/refresh") || url.endsWith("/auth/logout");
    if (status === 401 && cfg && !cfg._retryAuthRefresh && !isAuthEndpoint) {
      try {
        cfg._retryAuthRefresh = true;
        const accessToken = await refreshAccessToken();
        const auth = useAuthStore();
        auth.setToken(accessToken);
        cfg.headers.Authorization = `Bearer ${accessToken}`;
        return http.request(cfg);
      } catch {
        // 交给下面统一 401 分支清理会话并按当前路由决定是否跳转。
      }
    }
    if (status === 401 && !isAuthEndpoint && !cfg?.skipAuthRedirect) {
      await enqueueUnauthorized401(async () => {
        const auth = useAuthStore();
        const hadToken = Boolean(auth.token?.trim());
        await handleUserUnauthorizedRedirect({
          hadToken,
          logout: () => auth.clearSession(),
          getRouter: getAppRouter,
          isDev: import.meta.env.DEV,
        });
      });
    }
    return Promise.reject(err);
  },
);
