import { apiGetJson, apiPostJson, apiPostMultipart, readHasMore, readNextCursor, readTotalCount } from "./client";
import type { VideoDetail, VideoListItem, VideoPlayResponse } from "./types";

export async function listLatestVideos(
  params: { offset: number; limit: number },
  token?: string | null,
): Promise<{ items: VideoListItem[]; total: number }> {
  const q = new URLSearchParams({ offset: String(params.offset), limit: String(params.limit) });
  const { data, headers } = await apiGetJson<VideoListItem[]>(`/videos/latest?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}

export async function listTrendingVideos(
  params: { offset: number; limit: number },
  token?: string | null,
): Promise<{ items: VideoListItem[]; total: number }> {
  const q = new URLSearchParams({ offset: String(params.offset), limit: String(params.limit) });
  const { data, headers } = await apiGetJson<VideoListItem[]>(`/videos/trending?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}

export async function listFeedVideos(
  params: { offset: number; limit: number; page?: number },
  token?: string | null,
): Promise<{ items: VideoListItem[]; total: number }> {
  const q = new URLSearchParams({
    offset: String(params.offset),
    limit: String(params.limit),
    page: String(params.page ?? Math.floor(params.offset / Math.max(params.limit, 1)) + 1),
  });
  const { data } = await apiGetJson<{ items: VideoListItem[]; total: number }>(`/videos/feed?${q}`, { token });
  return { items: data.items, total: data.total };
}

export async function listVideosPaged(
  params: {
    limit: number;
    offset?: number;
    cursor?: string;
    category_id?: string;
    /** 须登录；仅返回当前用户关注作者的已发布视频 */
    followed_only?: boolean;
  },
  token?: string | null,
): Promise<{ items: VideoListItem[]; total: number; hasMore: boolean; nextCursor: string | null }> {
  const q = new URLSearchParams({ limit: String(params.limit) });
  if (params.cursor) q.set("cursor", params.cursor);
  else if (params.offset != null) q.set("offset", String(params.offset));
  if (params.category_id) q.set("category_id", params.category_id);
  if (params.followed_only) q.set("followed_only", "true");
  const { data, headers } = await apiGetJson<VideoListItem[]>(`/videos?${q}`, { token });
  return {
    items: data,
    total: readTotalCount(headers),
    hasMore: readHasMore(headers),
    nextCursor: readNextCursor(headers),
  };
}

export async function getVideo(id: string, token?: string | null): Promise<VideoDetail> {
  const { data } = await apiGetJson<VideoDetail>(`/videos/${id}`, { token });
  return data;
}

export async function getVideoPlay(id: string, token: string): Promise<VideoPlayResponse> {
  const { data } = await apiGetJson<VideoPlayResponse>(`/videos/${id}/play`, { token });
  return data;
}

export type VideoCreateInput = {
  title: string;
  description?: string | null;
  category_id?: string | null;
  tag_ids?: string[];
};

export async function createVideo(body: VideoCreateInput, token: string): Promise<VideoDetail> {
  const { data } = await apiPostJson<VideoDetail, VideoCreateInput>(
    "/videos",
    {
      title: body.title.trim(),
      description: body.description?.trim() || null,
      category_id: body.category_id || null,
      tag_ids: body.tag_ids ?? [],
    },
    { token },
  );
  return data;
}

export async function uploadLocalVideoMedia(
  videoId: string,
  file: { uri: string; name: string; type?: string | null },
  token: string,
): Promise<VideoDetail> {
  const fd = new FormData();
  fd.append("file", {
    uri: file.uri,
    name: file.name,
    type: file.type || "video/mp4",
  } as unknown as Blob);
  const { data } = await apiPostMultipart<VideoDetail>(`/videos/${videoId}/local-media`, fd, { token });
  return data;
}

export async function uploadVideoCover(
  videoId: string,
  file: { uri: string; name: string; type?: string | null },
  token: string,
): Promise<VideoDetail> {
  const fd = new FormData();
  fd.append("file", {
    uri: file.uri,
    name: file.name,
    type: file.type || "image/jpeg",
  } as unknown as Blob);
  const { data } = await apiPostMultipart<VideoDetail>(`/videos/${videoId}/cover`, fd, { token });
  return data;
}

export async function submitVideoForReview(videoId: string, token: string): Promise<VideoDetail> {
  const { data } = await apiPostJson<VideoDetail>(`/videos/${videoId}/submit-review`, {}, { token });
  return data;
}
