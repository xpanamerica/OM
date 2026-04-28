import React, { useMemo } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { ResizeMode, Video } from "expo-av";
import type { RootStackParamList } from "../navigation/types";
import { getApiBaseUrl } from "../config/env";
import { useAuth } from "../context/AuthContext";
import { RootBottomNav } from "../components/RootBottomNav";
import { colors } from "../theme/tokens";
import * as videosApi from "../api/videos";

type Props = NativeStackScreenProps<RootStackParamList, "PublishPreview">;

function resolveApiPath(path: string | null | undefined): string | undefined {
  const raw = path?.trim();
  if (!raw) return undefined;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  if (!raw.startsWith("/")) return raw;
  try {
    return `${new URL(getApiBaseUrl()).origin}${raw}`;
  } catch {
    return undefined;
  }
}

function statusLabel(status: string | undefined): string {
  if (status === "published") return "已发布";
  if (status === "pending_review") return "审核中";
  if (status === "draft") return "草稿";
  if (status === "rejected") return "需修改";
  return "已保存";
}

export function PublishPreviewScreen({ navigation, route }: Props) {
  const { token } = useAuth();
  const { id } = route.params;
  const q = useQuery({
    queryKey: ["publish-preview", id, token],
    queryFn: () => videosApi.getVideo(id, token),
  });

  const v = q.data;
  const authorName = v?.author_username?.trim() || "我的作品";
  const coverUri = useMemo(() => resolveApiPath(v?.cover_url), [v?.cover_url]);
  const videoUri = useMemo(() => resolveApiPath(v?.video_url), [v?.video_url]);

  return (
    <View style={styles.screen}>
      <ScrollView style={styles.root} contentContainerStyle={styles.pad}>
        {q.isLoading ? (
          <View style={styles.center}>
            <ActivityIndicator color={colors.accent} />
          </View>
        ) : q.isError || !v ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>未找到预览内容</Text>
            <Pressable style={styles.pill} onPress={() => navigation.navigate("Main", { screen: "Create" })}>
              <Text style={styles.pillText}>重新发布</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.hero}>
            <View style={styles.orbitOne} />
            <View style={styles.orbitTwo} />
            <View style={styles.authorRow}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{authorName.slice(0, 1).toUpperCase()}</Text>
              </View>
              <View style={styles.authorMain}>
                <Text style={styles.kicker}>视频发布成功</Text>
                <Text style={styles.authorName} numberOfLines={1}>{authorName}</Text>
                <Text style={styles.meta} numberOfLines={1}>
                  {statusLabel(v.status)} · {v.title || "未命名作品"}
                </Text>
              </View>
              <Pressable style={styles.pill} onPress={() => navigation.navigate("Main", { screen: "Profile" })}>
                <Text style={styles.pillText}>个人中心</Text>
              </Pressable>
            </View>

            <View style={styles.stage}>
              {videoUri ? (
                <Video
                  style={StyleSheet.absoluteFill}
                  source={{ uri: videoUri }}
                  useNativeControls
                  resizeMode={ResizeMode.CONTAIN}
                  shouldPlay
                />
              ) : (
                <View style={styles.fallback}>
                  {coverUri ? <Image source={{ uri: coverUri }} style={StyleSheet.absoluteFill} contentFit="cover" /> : null}
                  <View style={styles.fallbackShade} />
                  <Text style={styles.fallbackTitle}>预览已生成</Text>
                  <Text style={styles.fallbackText}>视频正在完成转码或审核，可稍后在个人中心继续查看。</Text>
                </View>
              )}
            </View>

            <View style={styles.info}>
              <Text style={styles.kicker}>作品标题</Text>
              <Text style={styles.title}>{v.title || "未命名作品"}</Text>
              {v.description ? <Text style={styles.desc}>{v.description}</Text> : null}
              <View style={styles.metrics}>
                <Text style={styles.metric}>{v.views_count ?? 0} 播放</Text>
                <Text style={styles.metric}>{v.likes_count ?? 0} 点赞</Text>
                <Text style={styles.metric}>{v.favorites_count ?? 0} 收藏</Text>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
      <RootBottomNav active="Create" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  root: { flex: 1 },
  pad: { padding: 14, paddingBottom: 112 },
  center: { paddingVertical: 60, alignItems: "center" },
  hero: {
    overflow: "hidden",
    borderRadius: 28,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.22)",
    backgroundColor: "rgba(15,23,42,0.92)",
    padding: 14,
  },
  orbitOne: {
    position: "absolute",
    right: -90,
    top: -100,
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 1,
    borderColor: "rgba(103,232,249,0.16)",
    backgroundColor: "rgba(34,211,238,0.08)",
  },
  orbitTwo: {
    position: "absolute",
    left: -70,
    bottom: 130,
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: "rgba(167,139,250,0.12)",
  },
  authorRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 14 },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  avatarText: { color: "#06111f", fontWeight: "900", fontSize: 20 },
  authorMain: { flex: 1, minWidth: 0 },
  kicker: { color: colors.accent, fontSize: 12, fontWeight: "900", letterSpacing: 1 },
  authorName: { color: colors.text, fontSize: 18, fontWeight: "900", marginTop: 2 },
  meta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  pill: { borderRadius: 999, paddingHorizontal: 12, paddingVertical: 9, backgroundColor: "rgba(255,255,255,0.10)" },
  pillText: { color: "#e0f2fe", fontSize: 12, fontWeight: "900" },
  stage: { width: "100%", aspectRatio: 9 / 16, maxHeight: 660, borderRadius: 24, overflow: "hidden", backgroundColor: "#000" },
  fallback: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  fallbackShade: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(2,6,23,0.56)" },
  fallbackTitle: { color: colors.text, fontSize: 20, fontWeight: "900", marginBottom: 8 },
  fallbackText: { color: colors.textMuted, textAlign: "center", lineHeight: 20 },
  info: { marginTop: 14, borderRadius: 22, padding: 14, backgroundColor: "rgba(2,6,23,0.44)" },
  title: { color: colors.text, fontSize: 20, fontWeight: "900", marginTop: 4 },
  desc: { color: colors.text, opacity: 0.86, lineHeight: 22, marginTop: 10 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  metric: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 7,
    color: "#dbeafe",
    fontSize: 12,
    fontWeight: "900",
    backgroundColor: "rgba(34,211,238,0.10)",
  },
  empty: { paddingVertical: 60, alignItems: "center", gap: 12 },
  emptyTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
});
