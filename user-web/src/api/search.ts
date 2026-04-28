import { http } from "./http";
import type { VideoListItem } from "./videos";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export async function searchVideos(params: {
  keyword?: string;
  category_id?: string;
  tag_id?: string;
  sort_by?: "latest" | "views" | "likes";
  offset: number;
  limit: number;
}): Promise<{ items: VideoListItem[]; total: number }> {
  const { data, headers } = await http.get<VideoListItem[]>("/search/videos", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}
