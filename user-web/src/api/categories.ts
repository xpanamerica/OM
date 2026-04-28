import { http } from "./http";
import { readHasMoreFromHeaders, readNextCursorFromHeaders } from "@/util/readPagingHeaders";

export type CategoryPublic = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

/** 公开列表；不带 limit 时后端可返回全量（offset≠0 会 400）。 */
export async function listCategories(params?: {
  limit?: number;
  offset?: number;
  cursor?: string;
}): Promise<{ items: CategoryPublic[]; hasMore: boolean; nextCursor: string | null }> {
  const { data, headers } = await http.get<CategoryPublic[]>("/categories", { params });
  return {
    items: data,
    hasMore: readHasMoreFromHeaders(headers),
    nextCursor: readNextCursorFromHeaders(headers),
  };
}
