import { http } from "./http";
import type { VideoListItem } from "./videos";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type { VideoListItem } from "./videos";

export type UserPublic = {
  id: string;
  email: string;
  username: string;
  avatar_url?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export async function fetchMe(): Promise<UserPublic> {
  const { data } = await http.get<UserPublic>("/users/me");
  return data;
}

export async function uploadMyAvatar(file: File): Promise<UserPublic> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await http.post<UserPublic>("/users/me/avatar", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export type ViewRecordOut = {
  id: string;
  user_id: string;
  video_id: string;
  progress_seconds: number;
  last_viewed_at: string;
  created_at: string;
  updated_at: string;
  /** 后端 JOIN videos.title；旧环境可能缺省 */
  video_title?: string | null;
};

export async function listMyViewRecords(params: {
  offset: number;
  limit: number;
}): Promise<{ items: ViewRecordOut[]; total: number }> {
  const { data, headers } = await http.get<ViewRecordOut[]>("/users/me/view-records", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function listMyFavoriteVideos(params: {
  offset: number;
  limit: number;
}): Promise<{ items: VideoListItem[]; total: number }> {
  const { data, headers } = await http.get<VideoListItem[]>("/users/me/favorite-videos", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}
