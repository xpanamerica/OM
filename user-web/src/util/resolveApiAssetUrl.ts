/** 将后端返回的相对 API 路径（如 ``/api/v1/covers/…``）转为浏览器可请求的绝对 URL。 */
export function resolveApiAssetUrl(pathOrUrl: string | null | undefined): string | undefined {
  const raw = pathOrUrl?.trim();
  if (!raw) return undefined;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  if (!raw.startsWith("/")) return raw;
  const base = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";
  if (base.startsWith("http://") || base.startsWith("https://")) {
    try {
      const u = new URL(base);
      return `${u.origin}${raw}`;
    } catch {
      /* fallthrough */
    }
  }
  if (typeof window !== "undefined") return `${window.location.origin}${raw}`;
  return raw;
}
