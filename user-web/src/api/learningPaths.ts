import { http } from "./http";
import type { VideoListItem } from "./videos";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type LearningPathPublic = {
  id: string;
  title: string;
  description: string | null;
  creator_id: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
};

export type LearningPathItem = {
  order_index: number;
  video_id: string;
  note: string | null;
  video: VideoListItem | null;
};

export type LearningPathDetail = LearningPathPublic & {
  items: LearningPathItem[];
};

export async function listLearningPaths(params: {
  offset: number;
  limit: number;
}): Promise<{ items: LearningPathPublic[]; total: number }> {
  const { data, headers } = await http.get<LearningPathPublic[]>("/learning-paths", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function getLearningPath(id: string): Promise<LearningPathDetail> {
  const { data } = await http.get<LearningPathDetail>(`/learning-paths/${id}`);
  return data;
}
