import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { colors } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";
import { useAuth } from "../context/AuthContext";
import * as socialApi from "../api/social";
import { getApiBaseUrl } from "../config/env";
import { RootBottomNav } from "../components/RootBottomNav";

type Props = NativeStackScreenProps<RootStackParamList, "UserProfile">;

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

export function UserProfileScreen({ navigation, route }: Props) {
  const { token } = useAuth();
  const [profile, setProfile] = useState<socialApi.PublicUserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setProfile(await socialApi.fetchUserProfile(route.params.id, token));
    } catch (e) {
      setErr(String(e));
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [route.params.id, token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleFollow() {
    if (!token || !profile) return navigation.navigate("Login");
    if (profile.is_following) await socialApi.unfollowUser(profile.user.id, token);
    else await socialApi.followUser(profile.user.id, token);
    await load();
  }

  async function addFriend() {
    if (!token || !profile) return navigation.navigate("Login");
    if (profile.friend_request_status === "accepted") {
      navigation.navigate("DirectMessages", { peerId: profile.user.id });
      return;
    }
    if (profile.friend_request_status === "incoming_pending") {
      navigation.navigate("Main", { screen: "Messages" });
      return;
    }
    if (profile.friend_request_status === "outgoing_pending") {
      Alert.alert("已发送", "好友申请已发送，请等待对方处理。");
      return;
    }
    await socialApi.sendFriendRequest(profile.user.id, token);
    Alert.alert("已发送", "对方可在消息中选择通过或拒绝。");
    await load();
  }

  if (loading) {
    return (
      <View style={styles.screen}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
        <RootBottomNav active="Profile" />
      </View>
    );
  }

  if (!profile) {
    return (
      <View style={styles.screen}>
        <View style={styles.center}>
          <Text style={styles.err}>{err ?? "无法打开用户主页"}</Text>
        </View>
        <RootBottomNav active="Profile" />
      </View>
    );
  }

  return (
    <View style={styles.screen}>
      <ScrollView style={styles.root} contentContainerStyle={styles.pad}>
        <View style={styles.hero}>
        <View style={styles.avatar}>
          {resolveApiPath(profile.user.avatar_url) ? (
            <Image source={{ uri: resolveApiPath(profile.user.avatar_url) }} style={styles.avatarImg} contentFit="cover" />
          ) : (
            <Text style={styles.avatarTxt}>{profile.user.username.slice(0, 1).toUpperCase()}</Text>
          )}
        </View>
        <Text style={styles.name}>{profile.user.username}</Text>
        <Text style={styles.sub}>{profile.is_mutual ? "互相关注" : profile.follows_me ? "关注了你" : "恒频OM 用户"}</Text>
        <View style={styles.stats}>
          <View style={styles.stat}><Text style={styles.statNum}>{profile.following_count}</Text><Text style={styles.statLbl}>关注</Text></View>
          <View style={styles.stat}><Text style={styles.statNum}>{profile.followers_count}</Text><Text style={styles.statLbl}>粉丝</Text></View>
          <View style={styles.stat}><Text style={styles.statNum}>{profile.friends_count}</Text><Text style={styles.statLbl}>好友</Text></View>
        </View>
        <View style={styles.actions}>
          <Pressable style={[styles.btn, styles.primary]} onPress={() => void toggleFollow()}>
            <Text style={styles.primaryTxt}>{profile.is_following ? "已关注" : "关注"}</Text>
          </Pressable>
          <Pressable style={[styles.btn, styles.primary]} onPress={() => void addFriend()}>
            <Text style={styles.primaryTxt}>
              {profile.friend_request_status === "accepted"
                ? "已是好友"
                : profile.friend_request_status === "outgoing_pending"
                  ? "等待通过"
                  : profile.friend_request_status === "incoming_pending"
                    ? "去处理"
                    : "添加好友"}
            </Text>
          </Pressable>
          <Pressable
            style={[styles.btn, !profile.can_message && styles.disabled]}
            disabled={!profile.can_message}
            onPress={() => navigation.navigate("DirectMessages", { peerId: profile.user.id })}
          >
            <Text style={styles.btnTxt}>{profile.can_message ? "私信" : "不可私信"}</Text>
          </Pressable>
        </View>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>频友发布</Text>
          {profile.recent_videos.length === 0 ? (
            <Text style={styles.empty}>暂无公开作品</Text>
          ) : (
            profile.recent_videos.map((v) => (
              <Pressable key={v.id} style={styles.videoRow} onPress={() => navigation.navigate("Detail", { id: v.id })}>
                <Text style={styles.videoTitle}>{v.title}</Text>
                <Text style={styles.videoMeta}>{v.views_count} 浏览</Text>
              </Pressable>
            ))
          )}
        </View>
      </ScrollView>
      <RootBottomNav active="Profile" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 14, paddingBottom: 96 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg, padding: 24 },
  err: { color: colors.danger, textAlign: "center" },
  hero: { alignItems: "center", backgroundColor: colors.surface, borderRadius: 18, padding: 18, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.accent, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  avatarImg: { width: "100%", height: "100%" },
  avatarTxt: { color: "#fff", fontSize: 28, fontWeight: "800" },
  name: { marginTop: 10, color: colors.text, fontSize: 22, fontWeight: "800" },
  sub: { marginTop: 4, color: colors.textMuted },
  stats: { flexDirection: "row", gap: 8, justifyContent: "center", marginTop: 12, width: "100%" },
  stat: { flex: 1, alignItems: "center", borderRadius: 12, backgroundColor: colors.bg, paddingVertical: 8 },
  statNum: { color: colors.text, fontWeight: "900", fontSize: 18 },
  statLbl: { color: colors.textMuted, fontWeight: "800", fontSize: 11, marginTop: 2 },
  actions: { flexDirection: "row", justifyContent: "center", gap: 8, marginTop: 14, width: "100%" },
  btn: { flex: 1, minWidth: 0, alignItems: "center", paddingHorizontal: 8, paddingVertical: 9, borderRadius: 999, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  primary: { backgroundColor: colors.accent, borderColor: colors.accent },
  disabled: { opacity: 0.5 },
  btnTxt: { color: colors.text, fontWeight: "800" },
  primaryTxt: { color: "#fff", fontWeight: "800" },
  card: { marginTop: 12, backgroundColor: colors.surface, borderRadius: 16, padding: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: "800", marginBottom: 10 },
  empty: { color: colors.textMuted },
  videoRow: { paddingVertical: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  videoTitle: { color: colors.text, fontWeight: "700" },
  videoMeta: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
});
