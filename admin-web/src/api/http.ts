import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";
import { getAppRouter } from "@/router/ready";
import { handleAdminUnauthorizedRedirect } from "./handleAdminUnauthorized";
import { enqueueUnauthorized401 } from "./unauthorized401Queue";

declare module "axios" {
  export interface AxiosRequestConfig {
    /** 为 true 时 401 不跳转登录（如探测请求） */
    skipAuthRedirect?: boolean;
  }
}

function getBaseURL(): string {
  const u = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!u) {
    throw new Error("缺少环境变量 VITE_API_BASE_URL");
  }
  return u.replace(/\/$/, "");
}

export const http: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 60_000,
});

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore();
  const t = auth.token?.trim();
  if (t) {
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

http.interceptors.response.use(
  (res) => res,
  async (err) => {
    const status = err.response?.status;
    const cfg = err.config as InternalAxiosRequestConfig & { skipAuthRedirect?: boolean };
    const url = String(cfg?.url ?? "");
    if (import.meta.env.DEV && status === 404) {
      const base = cfg?.baseURL ?? "";
      console.warn("[api 404]", String(cfg?.method ?? "GET").toUpperCase(), `${base}${url}`);
    }
    if (status === 401 && !url.endsWith("/auth/login") && !cfg?.skipAuthRedirect) {
      await enqueueUnauthorized401(async () => {
        const auth = useAuthStore();
        await handleAdminUnauthorizedRedirect({
          clearSession: () => auth.clearSession(),
          getRouter: getAppRouter,
          isDev: import.meta.env.DEV,
        });
      });
    }
    return Promise.reject(err);
  },
);
