import { http } from "./http";

export type CategoryRow = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type TagRow = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
};

export async function listCategories(): Promise<CategoryRow[]> {
  const { data } = await http.get<CategoryRow[]>("/categories");
  return data;
}

export async function createCategory(body: { name: string; description?: string | null }): Promise<CategoryRow> {
  const { data } = await http.post<CategoryRow>("/categories", body);
  return data;
}

export async function patchCategory(
  id: string,
  body: { name?: string; description?: string | null },
): Promise<CategoryRow> {
  const { data } = await http.patch<CategoryRow>(`/categories/${id}`, body);
  return data;
}

export async function listTags(): Promise<TagRow[]> {
  const { data } = await http.get<TagRow[]>("/tags");
  return data;
}

export async function createTag(body: { name: string }): Promise<TagRow> {
  const { data } = await http.post<TagRow>("/tags", body);
  return data;
}

export async function patchTag(id: string, body: { name?: string }): Promise<TagRow> {
  const { data } = await http.patch<TagRow>(`/tags/${id}`, body);
  return data;
}
