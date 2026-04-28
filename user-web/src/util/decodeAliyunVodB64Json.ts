/** 解码阿里云 VOD ``CreateUploadVideo`` 返回的 Base64 JSON（UploadAddress / UploadAuth）。 */
export function decodeAliyunVodB64Json(b64: string): Record<string, unknown> {
  const normalized = b64.trim().replace(/-/g, "+").replace(/_/g, "/");
  const padLen = (4 - (normalized.length % 4)) % 4;
  const padded = normalized + "=".repeat(padLen);
  let binary: string;
  try {
    binary = atob(padded);
  } catch {
    throw new Error("VOD 上传凭证 Base64 无效或损坏");
  }
  try {
    const v = JSON.parse(binary) as unknown;
    if (typeof v !== "object" || v === null || Array.isArray(v)) {
      throw new Error("VOD 上传地址/凭证 JSON 结构异常");
    }
    return v as Record<string, unknown>;
  } catch (e) {
    if (e instanceof SyntaxError) {
      throw new Error("VOD 上传凭证无法解析为 JSON");
    }
    throw e;
  }
}
