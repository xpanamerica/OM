/**
 * 判断 OSS / STS 直传错误是否值得通过 **RefreshUploadVideo** 换新凭证后重试。
 * 覆盖常见 XML 体、ali-oss 包装字段与部分英文文案（显式排除本机时钟漂移类错误）。
 */
export function isLikelyStsOrSignatureError(err: unknown): boolean {
  const o = err as Record<string, unknown> | null;
  if (!o || typeof o !== "object") return false;

  const code = String(o.code ?? "").trim();
  const name = String(o.name ?? "").trim();
  const msg = String(o.message ?? "").toLowerCase();
  const status = typeof o.status === "number" ? o.status : undefined;

  const codeL = code.toLowerCase();
  const nameL = name.toLowerCase();

  if (codeL === "requesttimetooskewed" || nameL === "requesttimetooskewed" || msg.includes("requesttimetooskewed")) {
    return false;
  }

  const xmlish = msg.replace(/\s+/g, " ");
  if (/<code>\s*securitytokenexpired\s*<\/code>/i.test(xmlish)) return true;
  if (/<code>\s*invalidsecuritytoken\s*<\/code>/i.test(xmlish)) return true;
  if (/<code>\s*tokenrefreshrequired\s*<\/code>/i.test(xmlish)) return true;
  if (/<code>\s*accessdenied\s*<\/code>/i.test(xmlish) && (msg.includes("expired") || msg.includes("token"))) {
    return true;
  }

  if (codeL.includes("securitytokenexpired") || nameL.includes("securitytokenexpired")) return true;
  if (codeL.includes("invalidsecuritytoken") || nameL.includes("invalidsecuritytoken")) return true;
  if (codeL === "invalidaccesskeyid" || nameL === "invalidaccesskeyid") return true;
  if (codeL === "signaturedoesnotmatch" || nameL === "signaturedoesnotmatch") return true;
  if (codeL === "accessdenied" && (msg.includes("expired") || msg.includes("token") || msg.includes("sts"))) {
    return true;
  }

  if (msg.includes("securitytokenexpired") || msg.includes("invalidsecuritytoken")) return true;
  if (msg.includes("token has expired") || msg.includes("token expired")) return true;
  if (msg.includes("expiredtoken") || msg.includes("expired token")) return true;
  if (msg.includes("accesskeyid") && msg.includes("invalid")) return true;
  if (msg.includes("signature we calculated does not match")) return true;

  if (status === 403 && (msg.includes("expired") || msg.includes("token") || msg.includes("security"))) return true;
  if (status === 400 && (msg.includes("token") || msg.includes("security"))) return true;

  return false;
}
