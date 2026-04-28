import React, { memo, useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useFocusEffect } from "@react-navigation/native";
import { colors } from "../theme/tokens";
import { getApiBaseUrl } from "../config/env";
import * as profileApi from "../api/profile";
import type { ProfileHub } from "../api/profile";
import type { VideoListItem } from "../api/types";
import * as usersApi from "../api/users";
import * as socialApi from "../api/social";
import { LoginFormCard } from "./LoginFormCard";
import { useRootStackNavigation } from "../navigation/useRootStackNavigation";

type Props = {
  token: string | null;
  onAuthenticated: (accessToken: string) => Promise<void>;
  onLogout: () => void;
};

const winW = Dimensions.get("window").width;
const pad = 12;
const gap = 10;
const cellW = (winW - pad * 2 - gap) / 2;

function resolveCover(path: string | null | undefined): string | undefined {
  const raw = path?.trim();
  if (!raw) return undefined;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  if (!raw.startsWith("/")) return raw;
  const base = getApiBaseUrl().replace(/\/$/, "");
  if (base.startsWith("http://") || base.startsWith("https://")) {
    try {
      return `${new URL(base).origin}${raw}`;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function resolveApiPath(path: string | null | undefined): string | undefined {
  const raw = path?.trim();
  if (!raw) return undefined;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  if (!raw.startsWith("/")) return raw;
  const base = getApiBaseUrl().replace(/\/$/, "");
  try {
    const u = new URL(base);
    return `${u.origin}${raw}`;
  } catch {
    return undefined;
  }
}

function ProfileDashboardInner({ token, onAuthenticated, onLogout }: Props) {
  const rootNav = useRootStackNavigation();
  const [hub, setHub] = useState<ProfileHub | null>(null);
  const [privacy, setPrivacy] = useState<socialApi.UserPrivacy | null>(null);
  const [friends, setFriends] = useState<socialApi.FollowUser[]>([]);
  const [meName, setMeName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setHub(null);
      setFriends([]);
      setMeName("");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const [h, me, p, fs] = await Promise.all([
        profileApi.fetchProfileHub(token),
        usersApi.fetchMe(token),
        socialApi.fetchMyPrivacy(token),
        socialApi.listMyFriends(token).catch(() => []),
      ]);
      setHub(h);
      setMeName(me.username);
      setAvatarUrl(h.avatar_url || me.avatar_url || null);
      setPrivacy(p);
      setFriends(fs);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      setHub(null);
      setMeName("");
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      if (!token) return;
      void load();
    }, [token, load]),
  );

  if (!token) {
    return (
      <ScrollView contentContainerStyle={styles.embedScroll} keyboardShouldPersistTaps="handled">
        <LoginFormCard
          variant="embedded"
          onSuccess={async (access) => {
            await onAuthenticated(access);
          }}
        />
      </ScrollView>
    );
  }

  if (loading && !hub) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  const display = meName || "用户";
  const initial = (display.trim().slice(0, 1) || "?").toUpperCase();
  const avatarUri = resolveApiPath(avatarUrl);

  async function pickAvatar() {
    if (!token) return;
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("需要相册权限", "请允许访问相册后再上传头像。");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.88,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    try {
      const me = await usersApi.uploadMyAvatar(
        {
          uri: asset.uri,
          name: asset.fileName || `avatar-${Date.now()}.jpg`,
          type: asset.mimeType || "image/jpeg",
        },
        token,
      );
      setAvatarUrl(me.avatar_url || null);
      await load();
    } catch (e) {
      Alert.alert("头像上传失败", e instanceof Error ? e.message : String(e));
    }
  }

  async function savePrivacy(next: Partial<socialApi.UserPrivacy>) {
    if (!token) return;
    setPrivacy(await socialApi.updateMyPrivacy(token, next));
  }

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollPad} keyboardShouldPersistTaps="handled">
      {err ? <Text style={styles.errTop}>{err}</Text> : null}

      {hub ? (
        <>
          <View style={styles.hero}>
            <View style={styles.heroBg} />
            <View style={styles.heroInner}>
              <View style={styles.topRow}>
                <Pressable style={styles.avatar} onPress={() => void pickAvatar()}>
                  {avatarUri ? (
                    <Image source={{ uri: avatarUri }} style={styles.avatarImg} contentFit="cover" />
                  ) : (
                    <Text style={styles.avatarTxt}>{initial}</Text>
                  )}
                </Pressable>
                <View style={styles.idBlock}>
                  <Text style={styles.heroName} numberOfLines={1}>
                    {display}
                  </Text>
                  <Text style={styles.heroSub}>恒频OM · 个人中心</Text>
                  <Text style={styles.heroBio}>历史记录、收藏与互动消息</Text>
                </View>
              </View>
              <View style={styles.statsRow}>
                <View style={styles.statCell}>
                  <Text style={styles.statNum}>{hub.following_count}</Text>
                  <Text style={styles.statLbl}>关注</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statNum}>{hub.followers_count}</Text>
                  <Text style={styles.statLbl}>粉丝</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statNum}>{hub.friends_count}</Text>
                  <Text style={styles.statLbl}>好友</Text>
                </View>
              </View>
            </View>
          </View>

          <View style={styles.friendCard}>
            <View style={styles.friendHead}>
              <View>
                <Text style={styles.friendTitle}>好友列表</Text>
                <Text style={styles.friendHint}>
                  {hub.pending_friend_request_count > 0 ? `${hub.pending_friend_request_count} 条申请待处理` : "通过申请后的好友会显示在这里"}
                </Text>
              </View>
              <Pressable onPress={() => rootNav?.navigate("Main", { screen: "Messages" })}>
                <Text style={styles.friendAction}>处理申请</Text>
              </Pressable>
            </View>
            {friends.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.friendStrip}>
                {friends.slice(0, 8).map((friend) => (
                  <Pressable key={friend.id} style={styles.friendChip} onPress={() => rootNav?.navigate("UserProfile", { id: friend.id })}>
                    <View style={styles.friendAvatar}>
                      <Text style={styles.friendAvatarTxt}>{friend.username.slice(0, 1).toUpperCase()}</Text>
                    </View>
                    <Text style={styles.friendName} numberOfLines={1}>{friend.username}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : (
              <Text style={styles.friendEmpty}>暂无好友，去发现页浏览创作者并发送好友申请。</Text>
            )}
          </View>

          <View style={styles.shortcuts}>
            <Pressable style={styles.scard} onPress={() => rootNav?.navigate("History")}>
              <Text style={styles.scardIco}>⏱</Text>
              <Text style={styles.scardT}>历史记录</Text>
              <Text style={styles.scardS}>看过的视频</Text>
            </Pressable>
            <Pressable style={styles.scard} onPress={() => rootNav?.navigate("Main", { screen: "Messages" })}>
              <Text style={styles.scardIco}>💬</Text>
              <Text style={styles.scardT}>互动消息</Text>
              <Text style={styles.scardS}>评论与提醒</Text>
              {hub.unread_notification_count > 0 ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeTxt}>{hub.unread_notification_count > 99 ? "99+" : hub.unread_notification_count}</Text>
                </View>
              ) : null}
            </Pressable>
            <Pressable style={styles.scard} onPress={() => rootNav?.navigate("Favorites")}>
              <Text style={styles.scardIco}>♥</Text>
              <Text style={styles.scardT}>个人收藏</Text>
              <Text style={styles.scardS}>收藏的视频</Text>
            </Pressable>
          </View>

          <View style={styles.shortcuts}>
            <Pressable style={styles.scard} onPress={() => rootNav?.navigate("DirectMessages", {})}>
              <Text style={styles.scardIco}>✉</Text>
              <Text style={styles.scardT}>私信</Text>
              <Text style={styles.scardS}>互关对话</Text>
            </Pressable>
            <Pressable
              style={styles.scard}
              onPress={() => void savePrivacy({ profile_visibility: privacy?.profile_visibility === "public" ? "mutual" : "public" })}
            >
              <Text style={styles.scardIco}>🔒</Text>
              <Text style={styles.scardT}>主页权限</Text>
              <Text style={styles.scardS}>{privacy?.profile_visibility === "public" ? "所有人" : "互相关注"}</Text>
            </Pressable>
            <Pressable
              style={styles.scard}
              onPress={() => void savePrivacy({ message_permission: privacy?.message_permission === "everyone" ? "mutual" : "everyone" })}
            >
              <Text style={styles.scardIco}>🛡</Text>
              <Text style={styles.scardT}>私信权限</Text>
              <Text style={styles.scardS}>{privacy?.message_permission === "everyone" ? "所有人" : "互相关注"}</Text>
            </Pressable>
          </View>

          <View style={styles.linksRow}>
            <Text style={styles.linkMuted}>账号与资料请使用网页端「个人中心」</Text>
            <Pressable style={styles.discBtn} onPress={() => rootNav?.navigate("Main", { screen: "Discover" })}>
              <Text style={styles.linkTxt}>去发现 →</Text>
            </Pressable>
          </View>

          <View style={styles.works}>
            <View style={styles.worksHead}>
              <Text style={styles.worksTitle}>我的作品</Text>
              <Pressable onPress={() => rootNav?.navigate("Main", { screen: "Create" })}>
                <Text style={styles.worksMore}>去创作</Text>
              </Pressable>
            </View>
            {hub.recent_videos.length === 0 ? (
              <Text style={styles.empty}>暂无稿件</Text>
            ) : (
              <View style={styles.grid}>
                {hub.recent_videos.map((v) => (
                  <VideoCell key={v.id} v={v} onOpen={() => rootNav?.navigate("Detail", { id: v.id })} />
                ))}
              </View>
            )}
          </View>

          <Pressable onPress={onLogout} style={styles.out}>
            <Text style={styles.outTxt}>退出登录</Text>
          </Pressable>
        </>
      ) : null}
    </ScrollView>
  );
}

function VideoCell({ v, onOpen }: { v: VideoListItem; onOpen: () => void }) {
  const uri = resolveCover(v.cover_url);
  return (
    <Pressable style={[styles.cell, { width: cellW }]} onPress={onOpen}>
      <View style={styles.thumbWrap}>
        {uri ? (
          <Image source={{ uri }} style={styles.thumb} contentFit="cover" />
        ) : (
          <View style={[styles.thumb, styles.thumbPh]}>
            <Text style={styles.thumbPhTxt}>{v.title.slice(0, 1)}</Text>
          </View>
        )}
        <View style={styles.stBadge}>
          <Text style={styles.stTxt}>{v.status}</Text>
        </View>
      </View>
      <Text style={styles.cellTitle} numberOfLines={2}>
        {v.title}
      </Text>
      <Text style={styles.cellMeta}>{v.views_count} 浏览</Text>
    </Pressable>
  );
}

export const ProfileDashboard = memo(ProfileDashboardInner);

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  scrollPad: { paddingBottom: 32 },
  embedScroll: { flexGrow: 1, paddingBottom: 24 },
  center: { flex: 1, padding: 32, alignItems: "center", justifyContent: "center" },
  errTop: { color: colors.danger, padding: 12, textAlign: "center" },

  hero: {
    marginBottom: 12,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    overflow: "hidden",
  },
  heroBg: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#1a1a1e",
  },
  heroInner: { padding: 20, paddingTop: 16 },
  topRow: { flexDirection: "row", gap: 14 },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.accent,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.25)",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  avatarImg: { width: "100%", height: "100%" },
  avatarTxt: { color: "#fff", fontSize: 26, fontWeight: "800" },
  idBlock: { flex: 1, minWidth: 0 },
  heroName: { color: "#fff", fontSize: 20, fontWeight: "800" },
  heroSub: { color: "rgba(255,255,255,0.75)", fontSize: 12, marginTop: 6 },
  heroBio: { color: "rgba(255,255,255,0.85)", fontSize: 13, marginTop: 8 },
  statsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "flex-start",
    marginTop: 18,
    paddingTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "rgba(255,255,255,0.15)",
    gap: 8,
  },
  statCell: { flex: 1, alignItems: "center", gap: 4, minWidth: 0 },
  statNum: { color: "#fff", fontSize: 18, fontWeight: "800" },
  statLbl: { color: "rgba(255,255,255,0.75)", fontSize: 11, fontWeight: "600", textAlign: "center" },

  friendCard: {
    marginHorizontal: pad,
    marginBottom: 10,
    padding: 14,
    borderRadius: 18,
    backgroundColor: "rgba(15,23,42,0.76)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.16)",
  },
  friendHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 },
  friendTitle: { color: colors.text, fontSize: 16, fontWeight: "900" },
  friendHint: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  friendAction: { color: colors.accent, fontSize: 13, fontWeight: "900" },
  friendStrip: { gap: 10 },
  friendChip: { width: 72, alignItems: "center", gap: 6 },
  friendAvatar: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent },
  friendAvatarTxt: { color: "#fff", fontWeight: "900" },
  friendName: { maxWidth: 72, color: colors.text, fontSize: 12, fontWeight: "700" },
  friendEmpty: { color: colors.textMuted, fontSize: 13 },

  shortcuts: { flexDirection: "row", gap: 10, paddingHorizontal: pad, marginBottom: 10 },
  scard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: 12,
    minHeight: 88,
    position: "relative",
  },
  scardIco: { fontSize: 18, marginBottom: 6 },
  scardT: { fontSize: 13, fontWeight: "800", color: colors.text },
  scardS: { fontSize: 11, color: colors.textMuted, marginTop: 4 },
  badge: {
    position: "absolute",
    top: 8,
    right: 8,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  badgeTxt: { color: "#fff", fontSize: 10, fontWeight: "800" },

  linksRow: { paddingHorizontal: pad, marginBottom: 14, alignItems: "center", gap: 8 },
  linkMuted: { fontSize: 12, color: colors.textMuted, textAlign: "center" },
  discBtn: { paddingVertical: 4 },
  linkTxt: { color: colors.accent, fontWeight: "800", fontSize: 14 },

  works: {
    marginHorizontal: pad,
    padding: 14,
    borderRadius: 16,
    backgroundColor: "rgba(15,23,42,0.76)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.16)",
  },
  worksHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  worksTitle: { fontSize: 16, fontWeight: "800", color: colors.text },
  worksMore: { fontSize: 13, fontWeight: "700", color: colors.accent },
  empty: { fontSize: 13, color: colors.textMuted, paddingVertical: 8 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap },
  cell: { marginBottom: 4 },
  thumbWrap: {
    borderRadius: 12,
    overflow: "hidden",
    aspectRatio: 3 / 4,
    backgroundColor: "#020617",
  },
  thumb: { width: "100%", height: "100%" },
  thumbPh: { alignItems: "center", justifyContent: "center" },
  thumbPhTxt: { fontSize: 28, fontWeight: "800", color: colors.textMuted },
  stBadge: {
    position: "absolute",
    left: 6,
    bottom: 6,
    backgroundColor: "rgba(0,0,0,0.55)",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  stTxt: { color: "#fff", fontSize: 10, fontWeight: "700" },
  cellTitle: { marginTop: 8, fontSize: 13, fontWeight: "700", color: colors.text },
  cellMeta: { fontSize: 11, color: colors.textMuted, marginTop: 4, marginBottom: 8 },

  out: { marginTop: 20, marginHorizontal: pad, paddingVertical: 12, alignItems: "center" },
  outTxt: { color: colors.danger, fontWeight: "700" },
});
