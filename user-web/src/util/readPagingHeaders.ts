/** 从 Axios 响应头读取 ``X-Has-More``（大小写不敏感）。 */
export function readHasMoreFromHeaders(headers: unknown): boolean {
  const v = readHeader(headers, "x-has-more");
  if (v == null) return false;
  return String(v).trim().toLowerCase() === "true";
}

/** 从 Axios 响应头读取 ``X-Next-Cursor``；无则 ``null``。 */
export function readNextCursorFromHeaders(headers: unknown): string | null {
  const v = readHeader(headers, "x-next-cursor");
  if (v == null || String(v).trim() === "") return null;
  return String(v).trim();
}

function readHeader(headers: unknown, name: string): string | undefined {
  if (headers == null) return undefined;
  const h = headers as { get?: (n: string) => string | number | undefined | null };
  if (typeof h.get === "function") {
    const v = h.get(name);
    if (v != null && v !== "") return String(v);
  }
  const o = headers as Record<string, string | string[] | undefined>;
  const raw = o[name] ?? o[name.toUpperCase()] ?? o[name.toLowerCase()];
  const s = Array.isArray(raw) ? raw[0] : raw;
  return s != null && String(s).trim() !== "" ? String(s) : undefined;
}
