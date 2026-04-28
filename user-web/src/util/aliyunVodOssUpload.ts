import OSS from "ali-oss";
import { isLikelyStsOrSignatureError } from "./aliyunVodOssCredentialError";
import { decodeAliyunVodB64Json } from "./decodeAliyunVodB64Json";

export { isLikelyStsOrSignatureError } from "./aliyunVodOssCredentialError";

function endpointHost(endpointRaw: string): string {
  const host = endpointRaw.replace(/^https?:\/\//, "").split("/")[0] ?? endpointRaw;
  return host.replace(/-internal\./i, ".");
}

function inferOssRegion(host: string): string {
  const publicHost = host.replace(/-internal\./i, ".");
  const m = /^oss-([a-z0-9-]+)\.aliyuncs\.com$/i.exec(publicHost);
  return m ? `oss-${m[1]}` : "oss-cn-shanghai";
}

/** ali-oss browser multipart checkpoint（与 ``managed-upload.js`` 结构一致） */
export type AliOssMultipartCheckpoint = {
  file: File;
  name: string;
  fileSize: number;
  partSize: number;
  uploadId: string;
  doneParts: Array<{ number: number; etag: string }>;
};

function isMultipartCheckpoint(x: unknown): x is AliOssMultipartCheckpoint {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.uploadId === "string" &&
    o.uploadId.length > 0 &&
    typeof o.name === "string" &&
    typeof o.fileSize === "number" &&
    typeof o.partSize === "number" &&
    Array.isArray(o.doneParts)
  );
}

function fileNameFromUploadAddressB64(b64: string): string {
  const addr = decodeAliyunVodB64Json(b64);
  return String(addr.FileName ?? addr.fileName ?? "").trim();
}

type OssUploadParts = {
  client: OSS;
  objectName: string;
};

function buildOssClientFromB64(uploadAddressB64: string, uploadAuthB64: string): OssUploadParts {
  const addr = decodeAliyunVodB64Json(uploadAddressB64);
  const auth = decodeAliyunVodB64Json(uploadAuthB64);

  const endpointRaw = String(addr.Endpoint ?? addr.endpoint ?? "").trim();
  const bucket = String(addr.Bucket ?? addr.bucket ?? "").trim();
  const objectName = String(addr.FileName ?? addr.fileName ?? "").trim();
  if (!endpointRaw || !bucket || !objectName) {
    throw new Error("UploadAddress 缺少 Endpoint / Bucket / FileName");
  }

  const accessKeyId = String(auth.AccessKeyId ?? auth.accessKeyId ?? "").trim();
  const accessKeySecret = String(auth.AccessKeySecret ?? auth.accessKeySecret ?? "").trim();
  const securityToken = String(auth.SecurityToken ?? auth.securityToken ?? "").trim();
  if (!accessKeyId || !accessKeySecret || !securityToken) {
    throw new Error("UploadAuth 缺少 STS 字段");
  }

  const host = endpointHost(endpointRaw);
  const region = inferOssRegion(host);

  const client = new OSS({
    region,
    bucket,
    endpoint: host,
    secure: true,
    accessKeyId,
    accessKeySecret,
    stsToken: securityToken,
  });

  return { client, objectName };
}

const DEFAULT_PART_SIZE = 1024 * 1024;
const DEFAULT_PARALLEL = 4;
/** 与 ``ali-oss`` 默认 STS 周期相比留余量：极长任务可多次刷新续传 */
const MAX_CREDENTIAL_REFRESH_CYCLES = 12;

export type VodOssUploadPhase = "uploading" | "refreshing_credentials";

export type VodOssUploadOptions = {
  /**
   * 检测到 STS/签名类错误时调用，用新 ``upload_address`` / ``upload_auth`` 重建客户端；
   * 若已有分片进度且 OSS 对象键未变，则 **checkpoint 续传**，否则整段重传。
   */
  onCredentialsExpired?: () => Promise<{ upload_address: string; upload_auth: string }>;
  /** 供 UI 提示「正在刷新上传凭证」等 */
  onPhase?: (phase: VodOssUploadPhase) => void;
};

/**
 * 使用 CreateUploadVideo（或 RefreshUploadVideo）返回的地址与 STS 凭证，将文件直传至 VOD 分配的 OSS 对象。
 * 小文件由 ali-oss 内部走 ``put``，大文件走 multipart；凭证过期时在 ``onCredentialsExpired`` 存在时刷新并重试。
 */
export async function uploadLocalFileToVodOss(
  file: File,
  uploadAddressB64: string,
  uploadAuthB64: string,
  onProgress?: (percent0to100: number) => void,
  options?: VodOssUploadOptions,
): Promise<void> {
  const refresh = options?.onCredentialsExpired;
  const onPhase = options?.onPhase;

  let addressB64 = uploadAddressB64;
  let authB64 = uploadAuthB64;
  let refreshCycles = 0;
  /** 盒装引用：progress 回调内赋值，避免 TS 将外层 ``let`` 窄化为恒为 ``null``。 */
  const multipartCheckpoint: { current: AliOssMultipartCheckpoint | null } = { current: null };

  const reportProgress = async (p: number, cp?: unknown) => {
    if (isMultipartCheckpoint(cp)) {
      multipartCheckpoint.current = cp;
    }
    onProgress?.(Math.min(100, Math.max(0, Math.round(Number(p) * 100))));
  };

  for (;;) {
    const { client, objectName } = buildOssClientFromB64(addressB64, authB64);
    const cp = multipartCheckpoint.current;
    const canResume =
      refresh != null &&
      cp != null &&
      Boolean(cp.uploadId) &&
      cp.name === objectName &&
      cp.fileSize === file.size;

    try {
      onPhase?.("uploading");
      await client.multipartUpload(objectName, file, {
        parallel: DEFAULT_PARALLEL,
        partSize: DEFAULT_PART_SIZE,
        ...(canResume ? { checkpoint: cp } : {}),
        progress: async (p: number, cpx?: unknown) => {
          await reportProgress(p, cpx);
        },
      });
      return;
    } catch (err) {
      if (!refresh || !isLikelyStsOrSignatureError(err) || refreshCycles >= MAX_CREDENTIAL_REFRESH_CYCLES) {
        throw err;
      }
      refreshCycles += 1;
      onPhase?.("refreshing_credentials");
      const next = await refresh();
      const newKey = fileNameFromUploadAddressB64(next.upload_address);
      const cur = multipartCheckpoint.current;
      if (!cur || cur.name !== newKey) {
        multipartCheckpoint.current = null;
      }
      addressB64 = next.upload_address;
      authB64 = next.upload_auth;
    }
  }
}
