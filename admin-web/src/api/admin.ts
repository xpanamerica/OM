import { http } from "./http";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type VideoListItem = {
  id: string;
  title: string;
  cover_url: string | null;
  status: string;
  author_id: string;
  category_id: string | null;
  views_count: number;
  likes_count: number;
  favorites_count: number;
  published_at: string | null;
  rejection_reason: string | null;
  vod_video_id: string | null;
  upload_status: string;
  transcode_status: string;
  duration_seconds: number | null;
  source_file_name: string | null;
  created_at: string;
  tags: { id: string; name: string }[];
};

export type UserPublic = {
  id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type AdminPlatformStats = {
  users_total: number;
  videos_total: number;
  videos_published: number;
  videos_pending_review: number;
  total_views_count: number;
  total_likes_count: number;
  total_favorites_count: number;
};

export type AdminPlatformSettings = {
  video_publish_without_review_enabled: boolean;
};

export async function adminListVideos(params: {
  offset: number;
  limit: number;
  status?: string;
  author_id?: string;
  category_id?: string;
  keyword?: string;
}): Promise<{ items: VideoListItem[]; total: number }> {
  const { data, headers } = await http.get<VideoListItem[]>("/admin/videos", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function adminListUsers(params: {
  offset: number;
  limit: number;
  role?: string;
  is_active?: boolean;
  keyword?: string;
}): Promise<{ items: UserPublic[]; total: number }> {
  const { data, headers } = await http.get<UserPublic[]>("/admin/users", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function adminSetUserActive(userId: string, is_active: boolean): Promise<UserPublic> {
  const { data } = await http.patch<UserPublic>(`/admin/users/${userId}/active`, { is_active });
  return data;
}

export async function adminPlatformStats(): Promise<AdminPlatformStats> {
  const { data } = await http.get<AdminPlatformStats>("/admin/statistics/platform");
  return data;
}

export async function adminGetPlatformSettings(): Promise<AdminPlatformSettings> {
  const { data } = await http.get<AdminPlatformSettings>("/admin/settings");
  return data;
}

export async function adminUpdatePlatformSettings(
  payload: Partial<AdminPlatformSettings>,
): Promise<AdminPlatformSettings> {
  const { data } = await http.patch<AdminPlatformSettings>("/admin/settings", payload);
  return data;
}
