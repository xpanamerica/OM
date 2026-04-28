import { useInfiniteQuery } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import * as videosApi from "../api/videos";
import type { VideoListItem } from "../api/types";

export type HomeFeedTab = "following" | "discover" | "explore";

const PAGE = 12;

function dedupeById(items: VideoListItem[]): VideoListItem[] {
  const seen = new Set<string>();
  const out: VideoListItem[] = [];
  for (const it of items) {
    if (seen.has(it.id)) continue;
    seen.add(it.id);
    out.push(it);
  }
  return out;
}

/**
 * 首页三 Tab：关注（followed_only）、发现（最新）、探索（热门）；与 user-web NativeFeedView 语义对齐。
 */
export function useHomeFeed(tab: HomeFeedTab, token: string | null) {
  const enabled = tab !== "following" || Boolean(token);

  const query = useInfiniteQuery({
    queryKey: ["home-feed", tab, token],
    enabled,
    queryFn: async ({ pageParam }) => {
      const offset = pageParam as number;
      if (tab === "following") {
        const r = await videosApi.listVideosPaged(
          { offset, limit: PAGE, followed_only: true },
          token,
        );
        return { items: r.items, total: r.total };
      }
      if (tab === "discover") {
        if (token) return videosApi.listFeedVideos({ offset, limit: PAGE }, token);
        return videosApi.listLatestVideos({ offset, limit: PAGE }, token);
      }
      return videosApi.listTrendingVideos({ offset, limit: PAGE }, token);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      const offset = lastPageParam as number;
      const nextOffset = offset + lastPage.items.length;
      if (lastPage.items.length === 0 || nextOffset >= lastPage.total) return undefined;
      return nextOffset;
    },
  });

  const flatItems = useMemo(() => dedupeById(query.data?.pages.flatMap((p) => p.items) ?? []), [query.data]);

  const refetchAll = useCallback(() => void query.refetch(), [query]);

  return { ...query, flatItems, refetchAll };
}
