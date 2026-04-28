import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";
import { getAppRouter } from "@/router/ready";
import { handleUserUnauthorizedRedirect } from "./handleUserUnauthorized";
import { enqueueUnauthorized401 } from "./unauthorized401Queue";

declare module "axios" {
  export interface AxiosRequestConfig {
    /** 为 true 时 401 不触发登出与跳转（如探测接口） */
    skipAuthRedirect?: boolean;
  }
}

function getBaseURL(): string {
  const u = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!u) throw new Error("缺少环境变量 VITE_API_BASE_URL");
  return u.replace(/\/$/, "");
}

export const http: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 90_000,
});

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore();
  const t = auth.token?.trim();
  if (t) config.headers.Authorization = `Bearer ${t}`;
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
    if (status === 401 && !String(cfg?.url ?? "").endsWith("/auth/login") && !cfg?.skipAuthRedirect) {
      await enqueueUnauthorized401(async () => {
        const auth = useAuthStore();
        const hadToken = Boolean(auth.token?.trim());
        await handleUserUnauthorizedRedirect({
          hadToken,
          logout: () => auth.logout(),
          getRouter: getAppRouter,
          isDev: import.meta.env.DEV,
        });
      });
    }
    return Promise.reject(err);
  },
);
