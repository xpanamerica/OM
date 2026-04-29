import { getApiBaseUrl, getApiConfigurationError, getWebMixedContentError, LAN_DEPLOY_HINT } from "../config/env";

/**
 * 与 user-web 一致：``Authorization: Bearer``；根路径见 ``getApiBaseUrl``。
 */
function baseUrl(): string {
  const cfgErr = getApiConfigurationError();
  if (cfgErr) {
    throw new Error(`${cfgErr}\n${LAN_DEPLOY_HINT}`);
  }
  const u = getApiBaseUrl().trim();
  if (!u) {
    throw new Error(`未配置有效 API 根地址。\n${LAN_DEPLOY_HINT}`);
  }
  const mix = getWebMixedContentError(u);
  if (mix) {
    throw new Error(`${mix}\n${LAN_DEPLOY_HINT}`);
  }
  return u.replace(/\/$/, "");
}

function wrapNetworkError(url: string, err: unknown): Error {
  let root = "";
  try {
    root = baseUrl();
  } catch {
    root = getApiBaseUrl().trim() || "(API 未配置或无效)";
  }
  const msg = err instanceof Error ? err.message : String(err);
  return new Error(
    `网络请求失败：${msg}\n请求：${url}\n当前 API 根：${root}\n${LAN_DEPLOY_HINT}`,
  );
}

async function fetchOrExplain(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (e) {
    throw wrapNetworkError(url, e);
  }
}

export type ApiFetchInit = RequestInit & { token?: string | null; skipAuth?: boolean };

export class ApiHttpError extends Error {
  status: number;
  path: string;
  code: string | null;
  detail: string | null;

  constructor(status: number, path: string, text: string) {
    let code: string | null = null;
    let detail: string | null = null;
    try {
      const body = JSON.parse(text) as { code?: unknown; detail?: unknown; message?: unknown };
      if (typeof body.code === "string") code = body.code;
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.message === "string") detail = body.message;
    } catch {
      /* 非 JSON 错误体保留原始片段 */
    }
    super(detail ? `${detail}${code ? `（${code}）` : ""}` : `HTTP ${status} ${path}: ${text.slice(0, 200)}`);
    this.name = "ApiHttpError";
    this.status = status;
    this.path = path;
    this.code = code;
    this.detail = detail;
  }
}

export function getResolvedApiBaseUrl(): string {
  return baseUrl();
}

export function readTotalCount(headers: Headers): number {
  const raw = headers.get("x-total-count") ?? headers.get("X-Total-Count");
  const n = Number(String(raw ?? "").trim());
  return Number.isFinite(n) ? n : 0;
}

export function readHasMore(headers: Headers): boolean {
  const v = (headers.get("x-has-more") ?? headers.get("X-Has-More") ?? "").toLowerCase();
  return v === "true";
}

export function readNextCursor(headers: Headers): string | null {
  const v = headers.get("x-next-cursor") ?? headers.get("X-Next-Cursor");
  if (!v || !v.trim()) return null;
  return v.trim();
}

export async function apiGetJson<T>(path: string, init?: ApiFetchInit): Promise<{ data: T; headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "GET", headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as T;
  return { data, headers: res.headers };
}

export async function apiPatchJson<T, B = unknown>(
  path: string,
  body: B,
  init?: ApiFetchInit,
): Promise<{ data: T; headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "PATCH", headers, body: JSON.stringify(body) });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as T;
  return { data, headers: res.headers };
}

export async function apiPostJson<T, B = unknown>(
  path: string,
  body: B,
  init?: ApiFetchInit,
): Promise<{ data: T; headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as T;
  return { data, headers: res.headers };
}

export async function apiDelete(path: string, init?: ApiFetchInit): Promise<{ headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "DELETE", headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  return { headers: res.headers };
}

export async function apiPostForm<T>(
  path: string,
  body: URLSearchParams,
  init?: ApiFetchInit,
): Promise<{ data: T; headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/x-www-form-urlencoded");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "POST", headers, body: body.toString() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiHttpError(res.status, path, text);
  }
  const data = (await res.json()) as T;
  return { data, headers: res.headers };
}

export async function apiPostMultipart<T>(
  path: string,
  body: FormData,
  init?: ApiFetchInit,
): Promise<{ data: T; headers: Headers }> {
  const url = `${baseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  const t = init?.token?.trim();
  if (t && !init?.skipAuth) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetchOrExplain(url, { ...init, method: "POST", headers, body });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  const data = (await res.json()) as T;
  return { data, headers: res.headers };
}
