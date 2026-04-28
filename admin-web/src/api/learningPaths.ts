import { http } from "./http";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type LearningPathRow = {
  id: string;
  title: string;
  description: string | null;
  creator_id: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
};

export async function listLearningPaths(params: {
  offset: number;
  limit: number;
}): Promise<{ items: LearningPathRow[]; total: number }> {
  const { data, headers } = await http.get<LearningPathRow[]>("/learning-paths", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function patchLearningPath(
  id: string,
  body: Partial<{ title: string; description: string | null; is_published: boolean }>,
): Promise<LearningPathRow> {
  const { data } = await http.patch<LearningPathRow>(`/learning-paths/${id}`, body);
  return data;
}
