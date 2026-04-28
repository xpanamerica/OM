import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { MainTabParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import * as notificationsApi from "../api/notifications";
import * as socialApi from "../api/social";

type Props = BottomTabScreenProps<MainTabParamList, "Messages">;
type MessageFeedRow =
  | { kind: "notification"; notification: notificationsApi.UserNotification }
  | { kind: "request"; request: socialApi.FriendRequest }
  | { kind: "conversation"; conversation: socialApi.DirectConversation }
  | { kind: "friend"; friend: socialApi.FollowUser };

function iconForKind(kind: string): string {
  if (kind === "follow") return "person-add";
  if (kind === "direct_message") return "chatbubble-ellipses";
  if (kind === "comment" || kind === "mention") return "chatbox";
  if (kind === "like" || kind === "favorite") return "heart";
  return "notifications";
}

function timeLabel(raw: string): string {
  const d = new Date(raw);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (now.getTime() - d.getTime() < 48 * 60 * 60 * 1000) return "昨天";
  return d.toLocaleDateString([], { month: "2-digit", day: "2-digit" });
}

function messagePreview(raw: string | null | undefined): string {
  if (!raw) return "暂无消息";
  try {
    const data = JSON.parse(raw) as { __om_dm_v1?: boolean; text?: string; attachments?: Array<{ content_type?: string | null }> };
    if (data.__om_dm_v1) {
      const text = data.text?.trim();
      if (text) return text;
      const first = data.attachments?.[0];
      if (first?.content_type?.startsWith("image/")) return "[图片]";
      if (first) return "[附件]";
    }
  } catch {
    // 兼容旧的纯文本私信。
  }
  return raw.trim() || "新消息";
}

export function MessagesScreen(_props: Props) {
  const { token } = useAuth();
  const [items, setItems] = useState<notificationsApi.UserNotification[]>([]);
  const [conversations, setConversations] = useState<socialApi.DirectConversation[]>([]);
  const [friends, setFriends] = useState<socialApi.FollowUser[]>([]);
  const [friendRequests, setFriendRequests] = useState<socialApi.FriendRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<"likes" | "follows" | "comments" | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    const [r, convs, fs, reqs] = await Promise.all([
      notificationsApi.listMyNotifications({ offset: 0, limit: 50 }, token),
      socialApi.listConversations(token).catch(() => []),
      socialApi.listMyFriends(token).catch(() => []),
      socialApi.listFriendRequests(token, "incoming").catch(() => []),
    ]);
    setItems(r.items);
    setConversations(convs);
    setFriends(fs);
    setFriendRequests(reqs);
  }, [token]);

  useEffect(() => {
    let c = false;
    setLoading(true);
    void load()
      .catch(() => {})
      .finally(() => {
        if (!c) setLoading(false);
      });
    return () => {
      c = true;
    };
  }, [load]);

  async function onRefresh() {
    if (!token) return;
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  async function decideFriendRequest(requestId: string, accept: boolean) {
    if (!token) return;
    try {
      if (accept) await socialApi.acceptFriendRequest(requestId, token);
      else await socialApi.rejectFriendRequest(requestId, token);
      await load();
    } catch (e) {
      Alert.alert("处理失败", e instanceof Error ? e.message : String(e));
    }
  }

  async function onOpen(row: notificationsApi.UserNotification) {
    if (!token) return;
    if (!row.read_at) {
      try {
        await notificationsApi.markNotificationRead(row.id, token);
        setItems((prev) =>
          prev.map((x) =>
            x.id === row.id ? { ...x, read_at: new Date().toISOString() } : x,
          ),
        );
      } catch {
        /* ignore */
      }
    }
    openActionUrl(row.action_url);
  }

  function openActionUrl(actionUrl: string | null) {
    if (!actionUrl) return;
    const videoMatch = actionUrl.match(/^\/videos\/([^/?#]+)/);
    if (videoMatch?.[1]) {
      _props.navigation.getParent()?.navigate("Detail", { id: videoMatch[1] });
      return;
    }
    const userMatch = actionUrl.match(/^\/users\/([^/?#]+)/);
    if (userMatch?.[1]) {
      _props.navigation.getParent()?.navigate("UserProfile", { id: userMatch[1] });
      return;
    }
    const dmMatch = actionUrl.match(/^\/me\/direct-messages\/([^/?#]+)/);
    if (dmMatch?.[1]) {
      _props.navigation.getParent()?.navigate("DirectMessages", { peerId: dmMatch[1] });
    }
  }

  const unreadCount = items.filter((item) => !item.read_at).length;
  const quickCards = [
    { key: "likes", icon: "heart" as const, title: "赞和收藏", tone: styles.quickHot, count: items.filter((x) => ["like", "favorite"].includes(x.kind)).length },
    { key: "follows", icon: "person-add" as const, title: "新增关注", tone: styles.quickAqua, count: items.filter((x) => x.kind === "follow" || x.kind === "friend_request_accepted").length + friendRequests.length },
    { key: "comments", icon: "chatbox-ellipses" as const, title: "评论和@", tone: styles.quickViolet, count: items.filter((x) => ["comment", "mention"].includes(x.kind)).length },
  ];
  const visibleItems = items.filter((row) => {
    if (!activeFilter) return true;
    if (activeFilter === "likes") return ["like", "favorite"].includes(row.kind);
    if (activeFilter === "follows") return row.kind === "follow" || row.kind === "friend_request_accepted";
    return ["comment", "mention"].includes(row.kind);
  });
  const conversationPeerIds = new Set(conversations.map((it) => it.peer.id));
  const feedRows: MessageFeedRow[] = [
    ...(!activeFilter ? conversations.slice(0, 8).map((conversation) => ({ kind: "conversation" as const, conversation })) : []),
    ...(!activeFilter || activeFilter === "follows" ? friendRequests.map((request) => ({ kind: "request" as const, request })) : []),
    ...visibleItems.map((notification) => ({ kind: "notification" as const, notification })),
    ...(!activeFilter ? friends.filter((friend) => !conversationPeerIds.has(friend.id)).slice(0, 3).map((friend) => ({ kind: "friend" as const, friend })) : []),
  ];

  if (!token) {
    return (
      <View style={styles.center}>
        <Text style={styles.hint}>请先登录</Text>
      </View>
    );
  }

  if (loading && items.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.root}
      contentContainerStyle={styles.pad}
      data={feedRows}
      keyExtractor={(it) =>
        it.kind === "notification" ? it.notification.id : it.kind === "request" ? `request-${it.request.id}` : it.kind === "conversation" ? `conversation-${it.conversation.id}` : `friend-${it.friend.id}`
      }
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      ListHeaderComponent={
        <>
          <View style={styles.topbar}>
            <View style={styles.topSpacer} />
            <Text style={styles.pageTitle}>Messages</Text>
            <Pressable style={styles.groupsLink} onPress={() => _props.navigation.getParent()?.navigate("DirectMessages", {})}>
              <Text style={styles.groupsTxt}>更多分组</Text>
            </Pressable>
          </View>
          <View style={styles.quickGrid}>
            {quickCards.map((card) => (
              <Pressable
                key={card.key}
                style={[styles.quickCard, activeFilter === card.key && styles.quickCardActive]}
                onPress={() => setActiveFilter(activeFilter === card.key ? null : card.key as "likes" | "follows" | "comments")}
              >
                <View style={[styles.quickIcon, card.tone]}>
                  <Ionicons name={card.icon} size={26} color="#fff" />
                  {card.count > 0 ? (
                    <View style={styles.quickBadge}>
                      <Text style={styles.quickBadgeTxt}>{card.count > 99 ? "99+" : card.count}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.quickTitle}>{card.title}</Text>
                <Text style={styles.quickCount}>{activeFilter === card.key ? "正在查看" : "点击查看"}</Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.syncRow}>
            <Text style={styles.syncTxt}>{friendRequests.length > 0 ? `${friendRequests.length} 条好友申请` : unreadCount > 0 ? `${unreadCount} 条未读` : "下拉刷新后查看最新消息"}</Text>
            <Pressable onPress={() => void onRefresh()}><Text style={styles.syncAction}>刷新</Text></Pressable>
          </View>
        </>
      }
      renderItem={({ item }) => {
        if (item.kind === "request") {
          return (
            <View style={[styles.row, styles.requestRow]}>
              <View style={styles.avatar}><Text style={styles.avatarTxt}>{item.request.requester.username.slice(0, 1).toUpperCase()}</Text></View>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle} numberOfLines={1}>{item.request.requester.username}</Text>
                <Text style={styles.body} numberOfLines={1}>{item.request.message || "请求添加你为好友"}</Text>
              </View>
              <View style={styles.reqActions}>
                <Pressable style={[styles.reqBtn, styles.reqAccept]} onPress={() => void decideFriendRequest(item.request.id, true)}>
                  <Text style={styles.reqAcceptTxt}>通过</Text>
                </Pressable>
                <Pressable style={styles.reqBtn} onPress={() => void decideFriendRequest(item.request.id, false)}>
                  <Text style={styles.reqRejectTxt}>拒绝</Text>
                </Pressable>
              </View>
            </View>
          );
        }
        if (item.kind === "friend") {
          return (
            <Pressable style={styles.row} onPress={() => _props.navigation.getParent()?.navigate("DirectMessages", { peerId: item.friend.id })}>
              <View style={styles.avatar}><Text style={styles.avatarTxt}>{item.friend.username.slice(0, 1).toUpperCase()}</Text></View>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle} numberOfLines={1}>{item.friend.username}</Text>
                <Text style={styles.body} numberOfLines={1}>我们已互相关注，开始聊天吧</Text>
              </View>
              <Text style={styles.meta}>{timeLabel(item.friend.followed_at)}</Text>
            </Pressable>
          );
        }
        if (item.kind === "conversation") {
          return (
            <Pressable style={styles.row} onPress={() => _props.navigation.getParent()?.navigate("DirectMessages", { peerId: item.conversation.peer.id })}>
              <View style={styles.avatar}><Ionicons name="chatbubble-ellipses" size={20} color="#fff" /></View>
              <View style={styles.rowMain}>
                <Text style={[styles.rowTitle, item.conversation.unread_count > 0 && styles.rowTitleUnread]} numberOfLines={1}>{item.conversation.peer.username}</Text>
                <Text style={styles.body} numberOfLines={1}>{item.conversation.last_message_preview || messagePreview(item.conversation.last_message?.body)}</Text>
              </View>
              <View style={styles.rowSide}>
                <Text style={styles.meta}>{timeLabel(item.conversation.updated_at || item.conversation.last_message?.created_at || new Date().toISOString())}</Text>
                {item.conversation.unread_count > 0 ? <View style={styles.unreadDot} /> : null}
              </View>
            </Pressable>
          );
        }
        return (
          <Pressable
            style={styles.row}
            onPress={() => void onOpen(item.notification)}
          >
              <View style={styles.avatar}><Ionicons name={iconForKind(item.notification.kind) as keyof typeof Ionicons.glyphMap} size={20} color="#fff" /></View>
            <View style={styles.rowMain}>
              <Text style={[styles.rowTitle, !item.notification.read_at && styles.rowTitleUnread]} numberOfLines={1}>{item.notification.title}</Text>
              {item.notification.body ? <Text style={styles.body} numberOfLines={1}>{item.notification.body}</Text> : <Text style={styles.body} numberOfLines={1}>查看详情</Text>}
            </View>
            <View style={styles.rowSide}>
              <Text style={styles.meta}>{timeLabel(item.notification.created_at)}</Text>
              {!item.notification.read_at ? <View style={styles.unreadDot} /> : null}
            </View>
          </Pressable>
        );
      }}
      ListEmptyComponent={<Text style={styles.empty}>暂无消息，下拉刷新后再查看。</Text>}
      ListFooterComponent={
        <View style={styles.recommend}>
          <View style={styles.recommendHead}>
            <Text style={styles.recommendTitle}>推荐给你</Text>
            <Text style={styles.recommendClose}>Close</Text>
          </View>
          <Pressable style={styles.discoverRow} onPress={() => _props.navigation.navigate("Discover")}>
            <View style={styles.discoverAvatar}><Text style={styles.discoverAvatarTxt}>＋</Text></View>
            <View style={styles.rowMain}>
              <Text style={styles.rowTitle}>发现更多创作者</Text>
              <Text style={styles.body}>浏览内容后可进入主页添加好友</Text>
            </View>
            <Text style={styles.followBtn}>去看看</Text>
          </Pressable>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { paddingHorizontal: 18, paddingTop: 4, paddingBottom: 30 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg },
  hint: { color: colors.textMuted },
  topbar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  topSpacer: { width: 82 },
  pageTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  groupsLink: { width: 82, alignItems: "flex-end" },
  groupsTxt: { color: colors.accent, fontSize: 14, fontWeight: "800" },
  quickGrid: { flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  quickCard: {
    width: "31%",
    alignItems: "center",
    minHeight: 92,
    borderRadius: 20,
    paddingTop: 8,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.12)",
  },
  quickCardActive: { borderColor: "rgba(103,232,249,0.65)", backgroundColor: "rgba(34,211,238,0.12)" },
  quickIcon: { width: 48, height: 48, borderRadius: 16, alignItems: "center", justifyContent: "center", marginBottom: 6 },
  quickBadge: { position: "absolute", right: -7, top: -7, minWidth: 22, height: 22, paddingHorizontal: 5, borderRadius: 11, borderWidth: 2, borderColor: colors.bg, backgroundColor: "#f8fafc", alignItems: "center", justifyContent: "center" },
  quickBadgeTxt: { color: "#0f172a", fontSize: 12, fontWeight: "900" },
  quickHot: { backgroundColor: "#fb7185" },
  quickAqua: { backgroundColor: colors.accent },
  quickViolet: { backgroundColor: "#8b5cf6" },
  quickTitle: { color: "#e2e8f0", fontSize: 12, fontWeight: "800", textAlign: "center" },
  quickCount: { color: colors.textMuted, fontSize: 11, fontWeight: "800", marginTop: 4 },
  syncRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  syncTxt: { color: colors.textMuted, fontSize: 12 },
  syncAction: { color: colors.accent, fontSize: 12, fontWeight: "800" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
  },
  requestRow: { backgroundColor: "rgba(34,211,238,0.12)", borderRadius: 18, paddingHorizontal: 12, marginBottom: 6 },
  reqActions: { flexDirection: "row", gap: 6 },
  reqBtn: { borderWidth: StyleSheet.hairlineWidth, borderColor: "#d7e3f3", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 7, backgroundColor: "#fff" },
  reqAccept: { backgroundColor: colors.accent, borderColor: colors.accent },
  reqAcceptTxt: { color: "#042f2e", fontWeight: "900", fontSize: 12 },
  reqRejectTxt: { color: "#cbd5e1", fontWeight: "900", fontSize: 12 },
  avatar: { width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent },
  avatarTxt: { color: "#fff", fontSize: 15, fontWeight: "900" },
  rowMain: { flex: 1, minWidth: 0 },
  rowTitle: { color: colors.text, fontSize: 16, fontWeight: "800" },
  rowTitleUnread: { fontWeight: "900" },
  body: { color: colors.textMuted, fontSize: 14, marginTop: 4 },
  rowSide: { minWidth: 54, alignItems: "flex-end", gap: 9 },
  meta: { color: "#64748b", fontSize: 12 },
  unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#ff2d55" },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: 24 },
  recommend: { marginTop: 18 },
  recommendHead: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
  recommendTitle: { color: colors.textMuted, fontSize: 13, fontWeight: "700" },
  recommendClose: { color: colors.textMuted, fontSize: 13 },
  discoverRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  discoverAvatar: { width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(34,211,238,0.14)" },
  discoverAvatarTxt: { color: colors.accent, fontSize: 22, fontWeight: "900" },
  followBtn: { color: colors.accent, borderColor: colors.accent, borderWidth: StyleSheet.hairlineWidth, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 6, overflow: "hidden", fontWeight: "900" },
});
