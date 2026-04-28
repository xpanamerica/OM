import axios from "axios";
import { http } from "./http";
import { tryReadApiErrorMessageFromBlob } from "@/util/errors";
import { readHasMoreFromHeaders, readNextCursorFromHeaders } from "@/util/readPagingHeaders";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type TagBrief = { id: string; name: string };

export type VideoListItem = {
  id: string;
  title: string;
  /** 与列表接口一致；旧后端可能不返回该字段 */
  description?: string | null;
  cover_url: string | null;
  status: string;
  author_id: string;
  author_username?: string | null;
  category_id: string | null;
  views_count: number;
  likes_count: number;
  favorites_count: number;
  comments_count?: number;
  published_at: string | null;
  rejection_reason: string | null;
  vod_video_id: string | null;
  upload_status: string;
  transcode_status: string;
  duration_seconds: number | null;
  source_file_name: string | null;
  created_at: string;
  tags: TagBrief[];
  recommendation_reason?: Record<string, number> | null;
  recommendation_text?: string | null;
};

export type VideoDetail = VideoListItem & {
  description: string | null;
  video_url: string | null;
  updated_at: string;
  row_version: number;
};

export type VideoPlayResponse = {
  video_id: string;
  playback_mode: "vod" | "local";
  vod_video_id: string | null;
  play_auth: string | null;
  stream_url: string | null;
  expire_time: string | null;
  request_id: string | null;
};

export type MyInteractions = { liked: boolean; favorited: boolean };

/** 与后端 ``VideoInteractionCountsOut`` 一致 */
export type VideoInteractionCountsOut = {
  video_id: string;
  likes_count: number;
  favorites_count: number;
};

export type CommentOut = {
  id: string;
  video_id: string;
  user_id: string;
  content: string;
  created_at: string;
  updated_at: string;
};

export async function listVideos(params: {
  offset: number;
  limit: number;
  category_id?: string;
  tag_id?: string;
}): Promise<{ items: VideoListItem[]; total: number }> {
  const { data, headers } = await http.get<VideoListItem[]>("/videos", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function listLatestVideos(params: { offset: number; limit: number }): Promise<{
  items: VideoListItem[];
  total: number;
}> {
  const { data, headers } = await http.get<VideoListItem[]>("/videos/latest", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

/** 与后端 ``GET /videos/trending`` 一致（仅已发布，热度排序）。 */
export async function listTrendingVideos(params: { offset: number; limit: number }): Promise<{
  items: VideoListItem[];
  total: number;
}> {
  const { data, headers } = await http.get<VideoListItem[]>("/videos/trending", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

/** 通用列表 + ``cursor`` 续页（与 ``offset`` 互斥）；响应头 ``X-Has-More`` / ``X-Next-Cursor``。 */
export async function listVideosPaged(params: {
  offset?: number;
  limit: number;
  cursor?: string;
  category_id?: string;
  tag_id?: string;
  /** 须登录；仅返回关注作者的已发布视频 */
  followed_only?: boolean;
}): Promise<{
  items: VideoListItem[];
  total: number;
  hasMore: boolean;
  nextCursor: string | null;
}> {
  const { data, headers } = await http.get<VideoListItem[]>("/videos", { params });
  return {
    items: data,
    total: readTotalCountFromHeaders(headers),
    hasMore: readHasMoreFromHeaders(headers),
    nextCursor: readNextCursorFromHeaders(headers),
  };
}

export type VideoFeedResponse = {
  items: VideoListItem[];
  total: number;
  hasMore: boolean;
  nextCursor: string | null;
  algorithmMode: "origin" | "personalized" | string;
  personalized: boolean;
  explanation: string | null;
};

export async function listFeedVideos(params: {
  offset: number;
  limit: number;
  page?: number;
}): Promise<VideoFeedResponse> {
  const { data } = await http.get<VideoFeedResponse>("/videos/feed", { params });
  return data;
}

export type VideoCreateInput = {
  title: string;
  description?: string | null;
  category_id?: string | null;
  tag_ids?: string[];
};

/** ``PATCH /videos/{id}``：仅作者或管理员；字段均可选，只传需更新的键。 */
export type VideoPatchBody = Partial<{
  title: string;
  description: string | null;
  category_id: string | null;
  status: string;
  tag_ids: string[];
}>;

export async function patchVideo(videoId: string, body: VideoPatchBody): Promise<VideoDetail> {
  const { data } = await http.patch<VideoDetail>(`/videos/${videoId}`, body);
  return data;
}

/** ``POST /videos/{id}/submit-review``：作者将 ``draft`` → ``pending_review``（公开列表仍仅展示已发布）。 */
export async function submitVideoForReview(videoId: string): Promise<VideoDetail> {
  const { data } = await http.post<VideoDetail>(`/videos/${videoId}/submit-review`, {});
  return data;
}

/** ``POST /videos``：需登录；新稿默认 draft。 */
export async function createVideo(body: VideoCreateInput): Promise<VideoDetail> {
  const { data } = await http.post<VideoDetail>("/videos", {
    title: body.title.trim(),
    description: body.description?.trim() || null,
    category_id: body.category_id || null,
    tag_ids: body.tag_ids ?? [],
  });
  return data;
}

export type VideoBindVodInput = {
  vod_video_id: string;
  source_file_name?: string | null;
  upload_status?: string | null;
  transcode_status?: string | null;
};

/** PATCH /videos/{id}/bind-vod：作者或管理员绑定 VOD VideoId。 */
export async function bindVodToVideo(videoId: string, body: VideoBindVodInput): Promise<VideoDetail> {
  const payload: Record<string, string> = { vod_video_id: body.vod_video_id.trim() };
  const sfn = body.source_file_name?.trim();
  if (sfn) payload.source_file_name = sfn;
  const us = body.upload_status?.trim();
  if (us) payload.upload_status = us;
  const ts = body.transcode_status?.trim();
  if (ts) payload.transcode_status = ts;
  const { data } = await http.patch<VideoDetail>(`/videos/${videoId}/bind-vod`, payload);
  return data;
}

export type VideoAttachmentOut = {
  id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
};

export async function listVideoAttachments(videoId: string): Promise<VideoAttachmentOut[]> {
  const { data } = await http.get<VideoAttachmentOut[]>(`/videos/${videoId}/attachments`);
  return data;
}

export async function uploadVideoAttachment(videoId: string, file: File): Promise<VideoAttachmentOut> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await http.post<VideoAttachmentOut>(`/videos/${videoId}/attachments`, fd, {
    timeout: 600_000,
  });
  return data;
}

export async function downloadVideoAttachmentBlob(videoId: string, attachmentId: string): Promise<Blob> {
  try {
    const res = await http.get<Blob>(`/videos/${videoId}/attachments/${attachmentId}/file`, {
      responseType: "blob",
      timeout: 600_000,
    });
    const { data, headers } = res;
    if (!(data instanceof Blob)) {
      throw new Error("下载响应异常");
    }
    const ct = String(headers["content-type"] ?? "").toLowerCase();
    if (ct.includes("application/json") || ct.includes("problem+json")) {
      const parsed = await tryReadApiErrorMessageFromBlob(data);
      if (parsed) throw new Error(parsed);
    }
    if (data.size < 8192) {
      const head = await data.slice(0, 1).text();
      if (head === "{" || head === "[") {
        const parsed = await tryReadApiErrorMessageFromBlob(data);
        if (parsed) throw new Error(parsed);
      }
    }
    return data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data instanceof Blob) {
      const parsed = await tryReadApiErrorMessageFromBlob(e.response.data);
      if (parsed) throw new Error(parsed);
    }
    throw e;
  }
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2_000);
}

export async function getVideo(id: string): Promise<VideoDetail> {
  const { data } = await http.get<VideoDetail>(`/videos/${id}`);
  return data;
}

export async function getVideoPlay(id: string): Promise<VideoPlayResponse> {
  const { data } = await http.get<VideoPlayResponse>(`/videos/${id}/play`);
  return data;
}

/**
 * 本机成片上传：默认走 ``PUT …/local-media-binary``（原始 body，少一次服务端整文件拷贝，大文件更快）；
 * 无扩展名时回退 ``POST …/local-media``（multipart）。
 */
export async function uploadLocalVideoMedia(videoId: string, file: File): Promise<VideoDetail> {
  const rawName = file.name || "";
  const dot = rawName.lastIndexOf(".");
  const suffix = dot >= 0 ? rawName.slice(dot).toLowerCase() : "";
  if (suffix && suffix.length <= 16 && suffix.startsWith(".")) {
    const q = new URLSearchParams();
    q.set("suffix", suffix);
    if (rawName.trim()) q.set("source_name", rawName.trim());
    const ct =
      file.type && !file.type.toLowerCase().startsWith("multipart/") ? file.type : "application/octet-stream";
    const { data } = await http.put<VideoDetail>(`/videos/${videoId}/local-media-binary?${q.toString()}`, file, {
      timeout: 600_000,
      headers: { "Content-Type": ct },
    });
    return data;
  }
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post<VideoDetail>(`/videos/${videoId}/local-media`, form, {
    timeout: 600_000,
  });
  return data;
}

/** ``POST /videos/{id}/cover``：JPEG 封面（与 ``GET /covers/{id}.jpg`` 对应）。 */
export async function uploadVideoCover(videoId: string, jpegFile: File): Promise<VideoDetail> {
  const form = new FormData();
  form.append("file", jpegFile);
  const { data } = await http.post<VideoDetail>(`/videos/${videoId}/cover`, form, {
    timeout: 120_000,
  });
  return data;
}

export async function getMyInteractions(videoId: string): Promise<MyInteractions> {
  const { data } = await http.get<MyInteractions>(`/videos/${videoId}/my-interactions`);
  return data;
}

export async function likeVideo(videoId: string): Promise<VideoInteractionCountsOut> {
  const { data } = await http.post<VideoInteractionCountsOut>(`/videos/${videoId}/like`);
  return data;
}

export async function unlikeVideo(videoId: string): Promise<VideoInteractionCountsOut> {
  const { data } = await http.delete<VideoInteractionCountsOut>(`/videos/${videoId}/like`);
  return data;
}

export async function favoriteVideo(videoId: string): Promise<VideoInteractionCountsOut> {
  const { data } = await http.post<VideoInteractionCountsOut>(`/videos/${videoId}/favorite`);
  return data;
}

export async function unfavoriteVideo(videoId: string): Promise<VideoInteractionCountsOut> {
  const { data } = await http.delete<VideoInteractionCountsOut>(`/videos/${videoId}/favorite`);
  return data;
}

export async function postViewRecord(
  videoId: string,
  body: { progress_seconds: number; last_viewed_at?: string | null },
): Promise<unknown> {
  const { data } = await http.post(`/videos/${videoId}/view-record`, body);
  return data;
}

export async function listComments(
  videoId: string,
  params: { offset?: number; limit?: number },
): Promise<{ items: CommentOut[]; total: number }> {
  const { data, headers } = await http.get<CommentOut[]>(`/videos/${videoId}/comments`, {
    params,
    headers: {
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
  });
  const items = Array.isArray(data) ? data : [];
  const fromHeader = readTotalCountFromHeaders(headers);
  const total = Math.max(fromHeader, items.length);
  return { items, total };
}

export async function postComment(videoId: string, content: string): Promise<CommentOut> {
  const { data } = await http.post<CommentOut>(`/videos/${videoId}/comments`, { content });
  return data;
}

export async function deleteComment(commentId: string): Promise<void> {
  await http.delete(`/comments/${commentId}`);
}

export type VideoConceptPublic = {
  concept_id: string;
  concept_name: string;
  start_time_seconds: number | null;
  end_time_seconds: number | null;
};

export async function listVideoConcepts(videoId: string): Promise<VideoConceptPublic[]> {
  const { data } = await http.get<VideoConceptPublic[]>(`/videos/${videoId}/concepts`);
  return data;
}
