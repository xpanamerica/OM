import { apiGetJson, readTotalCount } from "./client";
import type { VideoListItem } from "./types";

export async function searchVideos(
  params: {
    keyword?: string;
    category_id?: string;
    sort_by?: "latest" | "views" | "likes";
    offset?: number;
    limit?: number;
  },
  token?: string | null,
): Promise<{ items: VideoListItem[]; total: number }> {
  const q = new URLSearchParams();
  q.set("offset", String(params.offset ?? 0));
  q.set("limit", String(params.limit ?? 20));
  q.set("sort_by", params.sort_by ?? "latest");
  if (params.keyword?.trim()) q.set("keyword", params.keyword.trim());
  if (params.category_id) q.set("category_id", params.category_id);
  const { data, headers } = await apiGetJson<VideoListItem[]>(`/search/videos?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}
