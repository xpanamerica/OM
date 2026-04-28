import { apiGetJson, apiPostMultipart, readTotalCount } from "./client";
import type { UserPublic, VideoListItem } from "./types";

export type ViewRecordOut = {
  id: string;
  user_id: string;
  video_id: string;
  progress_seconds: number;
  last_viewed_at: string;
  created_at: string;
  updated_at: string;
  video_title?: string | null;
};

export async function fetchMe(token: string): Promise<UserPublic> {
  const { data } = await apiGetJson<UserPublic>("/users/me", { token });
  return data;
}

export async function uploadMyAvatar(
  file: { uri: string; name: string; type?: string | null },
  token: string,
): Promise<UserPublic> {
  const fd = new FormData();
  fd.append("file", {
    uri: file.uri,
    name: file.name,
    type: file.type || "image/jpeg",
  } as unknown as Blob);
  const { data } = await apiPostMultipart<UserPublic>("/users/me/avatar", fd, { token });
  return data;
}

export async function listMyViewRecords(
  params: { offset: number; limit: number },
  token: string,
): Promise<{ items: ViewRecordOut[]; total: number }> {
  const q = new URLSearchParams({ offset: String(params.offset), limit: String(params.limit) });
  const { data, headers } = await apiGetJson<ViewRecordOut[]>(`/users/me/view-records?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}

export async function listMyFavoriteVideos(
  params: { offset: number; limit: number },
  token: string,
): Promise<{ items: VideoListItem[]; total: number }> {
  const q = new URLSearchParams({ offset: String(params.offset), limit: String(params.limit) });
  const { data, headers } = await apiGetJson<VideoListItem[]>(`/users/me/favorite-videos?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}
