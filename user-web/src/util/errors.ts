import axios, { type AxiosError } from "axios";

type ApiErrorBody = {
  detail?: unknown;
  code?: unknown;
  message?: unknown;
};

const MAX_BLOB_ERROR_PARSE_BYTES = 65_536;

/**
 * 当 ``responseType: 'blob'`` 时，失败响应体常为 JSON Blob；解析出与 JSON 接口一致的可读文案。
 */
export async function tryReadApiErrorMessageFromBlob(blob: Blob): Promise<string | null> {
  if (!(blob instanceof Blob) || blob.size === 0 || blob.size > MAX_BLOB_ERROR_PARSE_BYTES) {
    return null;
  }
  let text: string;
  try {
    text = await blob.text();
  } catch {
    return null;
  }
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return null;
  }
  try {
    const data = JSON.parse(trimmed) as ApiErrorBody;
    const d = data?.detail;
    let msg: string | null = null;
    if (typeof d === "string" && d.trim()) {
      msg = withOptionalCode(d.trim(), data?.code);
    } else if (Array.isArray(d)) {
      msg = formatValidationErrors(d);
      if (msg) msg = withOptionalCode(msg, data?.code);
    } else if (typeof data?.message === "string" && data.message.trim()) {
      msg = withOptionalCode(data.message.trim(), data?.code);
    }
    return msg?.trim() || null;
  } catch {
    return null;
  }
}

function formatValidationErrors(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null;
  const parts = detail.map((x) => {
    if (typeof x !== "object" || x === null) return JSON.stringify(x);
    const o = x as Record<string, unknown>;
    if (typeof o.msg === "string") return String(o.msg);
    return JSON.stringify(x);
  });
  const s = parts.filter(Boolean).join("；");
  return s || null;
}

function withOptionalCode(msg: string, code: unknown): string {
  if (typeof code !== "string" || !code.trim()) return msg;
  if (msg.includes(code)) return msg;
  return `${msg}（${code}）`;
}

function append429Retry(msg: string, ax: AxiosError<ApiErrorBody>): string {
  const st = ax.response?.status;
  if (st !== 429) return msg;
  const h = ax.response?.headers;
  const g = h && typeof (h as { get?: (n: string) => string | undefined }).get === "function"
    ? (h as { get: (n: string) => string | undefined }).get.bind(h)
    : null;
  const ra = g?.("retry-after") ?? g?.("Retry-After");
  if (ra != null && String(ra).trim() !== "") return `${msg}（约 ${String(ra).trim()}s 后可重试）`;
  return msg;
}

/**
 * 将 API / Axios 错误转为用户可读文案（FastAPI ``detail`` + ``code``、422 数组、429 ``Retry-After``、无响应网络错误）。
 */
export function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<ApiErrorBody>;
    if (!ax.response) {
      const c = ax.code;
      if (c === "ERR_NETWORK" || ax.message === "Network Error") {
        return "网络异常，请检查网络或后端服务是否可达";
      }
      return ax.message?.trim() || "请求失败";
    }
    const data = ax.response.data;
    const d = data?.detail;
    let msg: string;
    if (typeof d === "string") {
      msg = withOptionalCode(d.trim() || "请求失败", data?.code);
    } else if (Array.isArray(d)) {
      msg = formatValidationErrors(d) || ax.message || "请求参数有误";
      msg = withOptionalCode(msg, data?.code);
    } else if (typeof data?.message === "string" && data.message.trim()) {
      msg = withOptionalCode(data.message.trim(), data?.code);
    } else {
      const st = ax.response.status;
      if (st === 404) {
        msg = "未找到请求的资源（404）。若刚部署过前后端，请确认接口版本与 VITE_API_BASE_URL 一致";
      } else if (st === 403) {
        msg = "无权执行此操作（403）";
      } else if (st === 401) {
        msg = "登录已失效或凭证无效（401），请重新登录";
      } else if (st === 502 || st === 503) {
        msg = "服务暂时不可用（502/503），请稍后重试";
      } else {
        msg = ax.message?.trim() || `请求失败（HTTP ${st}）`;
      }
    }
    return append429Retry(msg, ax);
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}
