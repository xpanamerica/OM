import { apiGetJson, readHasMore, readNextCursor } from "./client";
import type { CategoryPublic } from "./types";

export async function listCategories(token?: string | null): Promise<{
  items: CategoryPublic[];
  hasMore: boolean;
  nextCursor: string | null;
}> {
  const { data, headers } = await apiGetJson<CategoryPublic[]>("/categories", { token });
  return { items: data, hasMore: readHasMore(headers), nextCursor: readNextCursor(headers) };
}
