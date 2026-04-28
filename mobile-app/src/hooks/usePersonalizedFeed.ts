import AsyncStorage from "@react-native-async-storage/async-storage";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import * as videosApi from "../api/videos";
import type { VideoListItem } from "../api/types";

/** 与 user-web ``NativeFeedView`` / ``native_feed_pref_v1`` 对齐 */
export const FEED_PREF_KEY = "native_feed_pref_v1";

export type FeedMode = "latest" | "trending" | "smart";

type Pref = { latest: number; trending: number };

async function readPref(): Promise<Pref> {
  try {
    const raw = await AsyncStorage.getItem(FEED_PREF_KEY);
    if (!raw) return { latest: 1, trending: 1 };
    const o = JSON.parse(raw) as Partial<Pref>;
    return {
      latest: Math.max(0, Number(o.latest) || 0),
      trending: Math.max(0, Number(o.trending) || 0),
    };
  } catch {
    return { latest: 1, trending: 1 };
  }
}

export async function bumpFeedPref(key: "latest" | "trending") {
  const p = await readPref();
  p[key] += 1;
  await AsyncStorage.setItem(FEED_PREF_KEY, JSON.stringify(p));
}

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

const PAGE = 12;

function resolveListMode(mode: FeedMode, pref: Pref): "latest" | "trending" {
  if (mode === "latest" || mode === "trending") return mode;
  return pref.trending > pref.latest ? "trending" : "latest";
}

/**
 * 无限滚动 + 个性化：与后端 ``/videos/latest``、``/videos/trending`` 一致。
 * ``smart`` 根据本地偏好键解析为 latest/trending（与站点 H5 行为一致）。
 */
export function usePersonalizedFeed(mode: FeedMode, token: string | null) {
  const [pref, setPref] = useState<Pref>({ latest: 1, trending: 1 });

  useEffect(() => {
    void readPref().then(setPref);
  }, [mode]);

  const listMode = resolveListMode(mode, pref);

  const query = useInfiniteQuery({
    queryKey: ["personalized-feed", listMode, token, mode === "smart" ? pref : "fixed"],
    queryFn: async ({ pageParam }) => {
      const offset = pageParam as number;
      if (listMode === "latest") {
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

  const flatItems = dedupeById(query.data?.pages.flatMap((p) => p.items) ?? []);

  const bumpLatest = useCallback(() => void bumpFeedPref("latest"), []);
  const bumpTrending = useCallback(() => void bumpFeedPref("trending"), []);

  const refetchPref = useCallback(() => void readPref().then(setPref), []);

  return {
    ...query,
    flatItems,
    listMode,
    bumpLatest,
    bumpTrending,
    refetchPref,
  };
}
