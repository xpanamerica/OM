/**
 * 从 Axios 响应头读取 ``X-Total-Count``（与 user-web 同逻辑）。
 */
export function readTotalCountFromHeaders(headers: unknown): number {
  if (headers == null) return 0;
  const h = headers as { get?: (name: string) => string | number | undefined | null };
  if (typeof h.get === "function") {
    const v = h.get("x-total-count");
    if (v != null && v !== "") {
      const n = Number(String(v).trim());
      return Number.isFinite(n) ? n : 0;
    }
  }
  const o = headers as Record<string, string | string[] | undefined>;
  const raw = o["x-total-count"] ?? o["X-Total-Count"];
  const s = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(String(s ?? "").trim());
  return Number.isFinite(n) ? n : 0;
}
