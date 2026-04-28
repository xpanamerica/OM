import { apiGetJson, readTotalCount } from "./client";
import type { LearningPathPublic } from "./types";

export async function listLearningPaths(
  params: { offset?: number; limit?: number },
  token?: string | null,
): Promise<{ items: LearningPathPublic[]; total: number }> {
  const q = new URLSearchParams({
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 30),
  });
  const { data, headers } = await apiGetJson<LearningPathPublic[]>(`/learning-paths?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}
