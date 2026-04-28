import { http } from "./http";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type ConceptRow = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export async function listConcepts(params: {
  offset: number;
  limit: number;
}): Promise<{ items: ConceptRow[]; total: number }> {
  const { data, headers } = await http.get<ConceptRow[]>("/concepts", { params });
  return { items: data, total: readTotalCountFromHeaders(headers) };
}

export async function createConcept(body: {
  name: string;
  description?: string | null;
}): Promise<ConceptRow> {
  const { data } = await http.post<ConceptRow>("/concepts", body);
  return data;
}

export async function patchConcept(
  id: string,
  body: { name?: string; description?: string | null },
): Promise<ConceptRow> {
  const { data } = await http.patch<ConceptRow>(`/concepts/${id}`, body);
  return data;
}
