/**
 * 从 Axios 响应头读取 ``X-Total-Count``。
 * AxiosHeaders.get 大小写不敏感，优先使用 ``get``，避免仅用 bracket 访问时取不到导致分页总数恒为 0。
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
