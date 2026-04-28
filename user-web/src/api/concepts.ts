import { http } from "./http";
import type { VideoListItem } from "./videos";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

/** 与后端 ``ConceptLinkedVideoOut`` 一致：列表项 + 片段时间标注 */
export type ConceptLinkedVideo = VideoListItem & {
  start_time_seconds: number | null;
  end_time_seconds: number | null;
};

export type ConceptPublic = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export async function listConcepts(params: {
  offset: number;
  limit: number;
}): Promise<{ items: ConceptPublic[]; total: number }> {
  const { data, headers } = await http.get<ConceptPublic[]>("/concepts", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function getConcept(id: string): Promise<ConceptPublic> {
  const { data } = await http.get<ConceptPublic>(`/concepts/${id}`);
  return data;
}

export async function listConceptVideos(
  conceptId: string,
  params: { offset: number; limit: number },
  signal?: AbortSignal,
): Promise<{ items: ConceptLinkedVideo[]; total: number }> {
  const { data, headers } = await http.get<ConceptLinkedVideo[]>(`/concepts/${conceptId}/videos`, {
    params,
    signal,
  });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}
