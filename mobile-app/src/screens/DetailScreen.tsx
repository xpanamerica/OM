import React, { useCallback } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Video, ResizeMode } from "expo-av";
import type { RootStackParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import * as videosApi from "../api/videos";
import { useAuth } from "../context/AuthContext";
import { RootBottomNav } from "../components/RootBottomNav";

type Props = NativeStackScreenProps<RootStackParamList, "Detail">;

export function DetailScreen({ navigation, route }: Props) {
  const { id } = route.params;
  const { token } = useAuth();

  const q = useQuery({
    queryKey: ["video", id, token],
    queryFn: () => videosApi.getVideo(id, token),
  });

  const playProbe = useQuery({
    queryKey: ["video-play", id, token],
    queryFn: () => videosApi.getVideoPlay(id, token!),
    enabled: Boolean(token) && q.data?.status === "published" && !q.data?.video_url,
  });

  const renderBody = useCallback(() => {
    if (q.isLoading) {
      return (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
      );
    }
    if (q.isError || !q.data) {
      return <Text style={styles.err}>无法加载稿件</Text>;
    }
    const v = q.data;
    return (
      <>
        <Text style={styles.title}>{v.title}</Text>
        <Text style={styles.meta}>
          {v.views_count} 播放 · {v.likes_count} 赞 · {v.favorites_count} 收藏 · {v.comments_count ?? 0} 评论 · {v.status}
        </Text>
        <View style={styles.stats}>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{v.views_count}</Text>
            <Text style={styles.statLabel}>播放</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{v.likes_count}</Text>
            <Text style={styles.statLabel}>点赞</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{v.favorites_count}</Text>
            <Text style={styles.statLabel}>收藏</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{v.comments_count ?? 0}</Text>
            <Text style={styles.statLabel}>评论</Text>
          </View>
        </View>
        <Pressable style={styles.authorBtn} onPress={() => navigation.navigate("UserProfile", { id: v.author_id })}>
          <Text style={styles.authorTxt}>查看作者主页</Text>
        </Pressable>
        {v.description ? <Text style={styles.desc}>{v.description}</Text> : null}
        {v.video_url ? (
          <View style={styles.player}>
            <Video
              style={StyleSheet.absoluteFill}
              source={{ uri: v.video_url }}
              useNativeControls
              resizeMode={ResizeMode.CONTAIN}
              shouldPlay
            />
          </View>
        ) : (
          <View style={styles.box}>
            <Text style={styles.boxT}>阿里云 VOD</Text>
            <Text style={styles.boxP}>
              站点 H5 使用 GET /videos/:id/play 返回的 play_auth 与 Web Aliplayer。React Native 需集成阿里云 ApsaraVideo 原生 SDK
              或 WebView；下方为是否成功请求播放凭证的探测结果：
            </Text>
            {!token ? (
              <Text style={styles.boxP}>请登录后请求播放凭证。</Text>
            ) : playProbe.isLoading ? (
              <ActivityIndicator color={colors.accent} />
            ) : playProbe.isError ? (
              <Text style={styles.err}>{playProbe.error instanceof Error ? playProbe.error.message : String(playProbe.error)}</Text>
            ) : playProbe.data ? (
              <Text style={styles.ok}>已获取凭证（vid 已就绪，不在 UI 展示 play_auth）。</Text>
            ) : null}
          </View>
        )}
      </>
    );
  }, [q, playProbe, token]);

  return (
    <View style={styles.screen}>
      <ScrollView style={styles.root} contentContainerStyle={styles.pad}>
        {renderBody()}
      </ScrollView>
      <RootBottomNav active="Feed" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 16, paddingBottom: 104 },
  center: { padding: 40, alignItems: "center" },
  title: { color: colors.text, fontSize: 20, fontWeight: "800" },
  meta: { color: colors.textMuted, marginTop: 8, fontSize: 13 },
  stats: { flexDirection: "row", gap: 8, marginTop: 14 },
  statBox: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  statNum: { color: colors.text, fontSize: 18, fontWeight: "900" },
  statLabel: { color: colors.textMuted, marginTop: 2, fontSize: 11, fontWeight: "700" },
  authorBtn: { alignSelf: "flex-start", marginTop: 10, paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999, backgroundColor: colors.surface },
  authorTxt: { color: colors.accent, fontWeight: "800", fontSize: 13 },
  desc: { color: colors.text, marginTop: 16, lineHeight: 22, fontSize: 15 },
  player: { marginTop: 20, width: "100%", aspectRatio: 16 / 9, backgroundColor: "#000", borderRadius: 12, overflow: "hidden" },
  box: {
    marginTop: 20,
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  boxT: { color: colors.accent, fontWeight: "800", marginBottom: 8 },
  boxP: { color: colors.textMuted, fontSize: 13, lineHeight: 20 },
  err: { color: colors.danger, marginTop: 12 },
  ok: { color: colors.text, marginTop: 10, fontWeight: "600" },
});
