<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as notificationsApi from "@/api/notifications";
import * as socialApi from "@/api/social";
import { formatApiError } from "@/util/errors";

const router = useRouter();
const loading = ref(false);
const items = ref<notificationsApi.UserNotification[]>([]);
const conversations = ref<socialApi.DirectConversation[]>([]);
const friends = ref<socialApi.FollowUser[]>([]);
const friendRequests = ref<socialApi.FriendRequest[]>([]);
const activeFilter = ref<"likes" | "follows" | "comments" | null>(null);
type QuickKey = "likes" | "follows" | "comments";

const unreadItems = computed(() => items.value.filter((x) => !x.read_at));
const grouped = computed(() => ({
  likes: items.value.filter((x) => ["like", "favorite"].includes(x.kind)).length,
  follows: items.value.filter((x) => x.kind === "follow" || x.kind === "friend_request_accepted").length + friendRequests.value.length,
  comments: items.value.filter((x) => ["comment", "mention"].includes(x.kind)).length,
}));
const quickCards = computed(() => [
  { key: "likes", title: "赞和收藏", count: grouped.value.likes, tone: "hot" },
  { key: "follows", title: "新增关注", count: grouped.value.follows, tone: "aqua" },
  { key: "comments", title: "评论和@", count: grouped.value.comments, tone: "violet" },
]);
const displayRows = computed(() => {
  const visibleItems = items.value.filter((row) => {
    if (!activeFilter.value) return true;
    if (activeFilter.value === "likes") return ["like", "favorite"].includes(row.kind);
    if (activeFilter.value === "follows") return row.kind === "follow" || row.kind === "friend_request_accepted";
    return ["comment", "mention"].includes(row.kind);
  });
  const conversationRows = conversations.value.slice(0, 8).map((c) => ({
    id: `conversation-${c.id}`,
    title: c.peer.username,
    body: messagePreview(c.last_message_preview || c.last_message?.body),
    date: c.updated_at || c.last_message?.created_at || new Date().toISOString(),
    unread: c.unread_count > 0,
    avatar: c.peer.username.slice(0, 1).toUpperCase(),
    action: () => router.push({ name: "direct-messages", params: { peerId: c.peer.id } }),
  }));
  const conversationPeerIds = new Set(conversations.value.map((c) => c.peer.id));
  const directRows = friends.value.filter((friend) => !conversationPeerIds.has(friend.id)).slice(0, 3).map((friend) => ({
    id: `friend-${friend.id}`,
    title: friend.username,
    body: friend.is_mutual ? "我们已互相关注，开始聊天吧" : "点击打开会话",
    date: friend.followed_at,
    unread: false,
    avatar: friend.username.slice(0, 1).toUpperCase(),
    action: () => router.push({ name: "direct-messages", params: { peerId: friend.id } }),
  }));
  const notificationRows = visibleItems.slice(0, 20).map((row) => ({
    id: row.id,
    title: row.title,
    body: row.kind === "direct_message" ? messagePreview(row.body) : row.body || "查看详情",
    date: row.created_at,
    unread: !row.read_at,
    avatar: iconForKind(row.kind),
    action: () => openRow(row),
  }));
  return activeFilter.value ? notificationRows : [...conversationRows, ...notificationRows, ...directRows];
});

function iconForKind(kind: string) {
  if (kind === "follow") return "人";
  if (kind === "direct_message") return "聊";
  if (kind === "comment" || kind === "mention") return "@";
  if (kind === "like" || kind === "favorite") return "赞";
  return "铃";
}

function messagePreview(raw: string | null | undefined) {
  if (!raw) return "暂无消息";
  try {
    const data = JSON.parse(raw) as { __om_dm_v1?: boolean; text?: string; attachments?: Array<{ content_type?: string | null }> };
    if (data.__om_dm_v1) {
      const body = data.text?.trim();
      if (body) return body;
      const first = data.attachments?.[0];
      if (first?.content_type?.startsWith("image/")) return "[图片]";
      if (first) return "[附件]";
    }
  } catch {
    /* plain text */
  }
  return raw.trim() || "新消息";
}

function directMessagePeerId(row: notificationsApi.UserNotification) {
  const fromUrl = row.action_url?.match(/^\/me\/direct-messages\/([^/?#]+)/)?.[1];
  if (fromUrl) return fromUrl;
  if (row.kind !== "direct_message") return "";
  const matchedConversation = conversations.value.find((c) => row.title.includes(c.peer.username));
  if (matchedConversation) return matchedConversation.peer.id;
  const matchedFriend = friends.value.find((friend) => row.title.includes(friend.username));
  return matchedFriend?.id || "";
}

function timeLabel(raw: string) {
  const d = new Date(raw);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 24 * 60 * 60 * 1000 && d.getDate() === now.getDate()) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (diff < 48 * 60 * 60 * 1000) return "昨天";
  return d.toLocaleDateString([], { month: "2-digit", day: "2-digit" });
}

function toggleQuickCard(key: string) {
  const next = key as QuickKey;
  activeFilter.value = activeFilter.value === next ? null : next;
}

async function load() {
  loading.value = true;
  try {
    const [r, conversationRows, friendRows, requestRows] = await Promise.all([
      notificationsApi.listMyNotifications({ offset: 0, limit: 50 }),
      socialApi.listConversations().catch(() => []),
      socialApi.listMyFriends().catch(() => []),
      socialApi.listFriendRequests("incoming").catch(() => []),
    ]);
    items.value = r.items;
    conversations.value = conversationRows;
    friends.value = friendRows;
    friendRequests.value = requestRows;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function decideFriendRequest(requestId: string, accept: boolean) {
  try {
    if (accept) {
      await socialApi.acceptFriendRequest(requestId);
      ElMessage.success("已通过好友申请");
    } else {
      await socialApi.rejectFriendRequest(requestId);
      ElMessage.success("已拒绝好友申请");
    }
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function openRow(row: notificationsApi.UserNotification) {
  if (!row.read_at) {
    try {
      await notificationsApi.markNotificationRead(row.id);
      row.read_at = new Date().toISOString();
    } catch (e) {
      ElMessage.error(formatApiError(e));
    }
  }
  const peerId = directMessagePeerId(row);
  if (peerId) {
    void router.push({ name: "direct-messages", params: { peerId } });
    return;
  }
  if (row.action_url?.startsWith("/")) {
    void router.push(row.action_url);
  }
}

async function markAll() {
  try {
    await notificationsApi.markAllNotificationsRead();
    ElMessage.success("已全部标为已读");
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

onMounted(() => void load());
</script>

<template>
  <div v-loading="loading" class="native-stack messages-page">
    <div class="topbar">
      <span />
      <h1>Messages</h1>
      <RouterLink class="groups-link" :to="{ name: 'direct-messages' }">更多分组</RouterLink>
    </div>

    <section class="quick-grid">
      <button
        v-for="card in quickCards"
        :key="card.key"
        type="button"
        class="quick-card"
        :class="{ active: activeFilter === card.key }"
        @click="toggleQuickCard(card.key)"
      >
        <span class="quick-icon" :class="card.tone">
          <svg v-if="card.key === 'likes'" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 21s-7.2-4.35-9.4-8.75C.86 8.78 2.7 5 6.38 5c2.02 0 3.33 1.1 4.02 2.1C11.08 6.1 12.4 5 14.42 5c3.68 0 5.52 3.78 3.78 7.25C16 16.65 12 21 12 21Z" />
            <path d="M17.8 3.1 19 1l1.2 2.1 2.2 1.1-2.2 1.1L19 7.4l-1.2-2.1-2.2-1.1 2.2-1.1Z" />
          </svg>
          <svg v-else-if="card.key === 'follows'" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M9.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2C5.3 13 2 15.2 2 18v1.2C2 20.2 2.8 21 3.8 21h11.4c1 0 1.8-.8 1.8-1.8V18c0-2.8-3.3-5-7.5-5Z" />
            <path d="M19 9V6h-2V4h2V1h2v3h2v2h-2v3h-2Z" />
          </svg>
          <svg v-else viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 4.5C4 3.12 5.12 2 6.5 2h11C18.88 2 20 3.12 20 4.5v9c0 1.38-1.12 2.5-2.5 2.5H9l-5 5v-16.5Z" />
            <path d="M8 8h8v1.8H8V8Zm0 4h5.5v1.8H8V12Z" />
          </svg>
          <i v-if="card.count > 0" class="quick-badge">{{ card.count > 99 ? "99+" : card.count }}</i>
        </span>
        <b>{{ card.title }}</b>
        <small v-if="activeFilter === card.key">正在查看</small>
      </button>
    </section>

    <div class="toolbar">
      <span>{{ friendRequests.length > 0 ? `${friendRequests.length} 条好友申请` : unreadItems.length > 0 ? `${unreadItems.length} 条未读` : "消息已同步" }}</span>
      <button v-if="unreadItems.length > 0" type="button" @click="markAll">全部已读</button>
      <button v-else type="button" @click="load">刷新</button>
    </div>

    <section v-if="friendRequests.length > 0 && (!activeFilter || activeFilter === 'follows')" class="request-list">
      <article v-for="req in friendRequests" :key="req.id" class="request-card">
        <span class="row-avatar">{{ req.requester.username.slice(0, 1).toUpperCase() }}</span>
        <span class="row-main">
          <b>{{ req.requester.username }}</b>
          <small>{{ req.message || "请求添加你为好友，通过后会进入好友列表" }}</small>
        </span>
        <span class="request-actions">
          <button type="button" class="accept" @click="decideFriendRequest(req.id, true)">通过</button>
          <button type="button" @click="decideFriendRequest(req.id, false)">拒绝</button>
        </span>
      </article>
    </section>

    <section class="message-list">
      <button
        v-for="row in displayRows"
        :key="row.id"
        type="button"
        class="message-row"
        :class="{ unread: row.unread }"
        @click="row.action"
      >
        <span class="row-avatar">{{ row.avatar }}</span>
        <span class="row-main">
          <b>{{ row.title }}</b>
          <small>{{ row.body }}</small>
        </span>
        <span class="row-side">
          <small>{{ timeLabel(row.date) }}</small>
          <i v-if="row.unread" />
        </span>
      </button>
      <p v-if="displayRows.length === 0" class="empty">暂无消息，下拉或点击刷新后再查看。</p>
    </section>

    <section class="recommend-card">
      <div class="recommend-head">
        <span>推荐给你</span>
        <button type="button" @click="load">刷新</button>
      </div>
      <RouterLink class="discover-row" :to="{ name: 'native-discover' }">
        <span class="discover-avatar">＋</span>
        <span>
          <b>发现更多创作者</b>
          <small>浏览内容后可进入主页添加好友</small>
        </span>
        <em>去看看</em>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped>
.messages-page {
  min-height: 100%;
  margin: 0 -10px;
  padding: 8px 12px 24px;
  max-width: calc(100vw - 0px);
  overflow-x: hidden;
  background:
    radial-gradient(circle at 16% -10%, rgba(34, 211, 238, 0.28), transparent 34%),
    radial-gradient(circle at 96% 2%, rgba(59, 130, 246, 0.2), transparent 28%),
    linear-gradient(180deg, #07111f 0%, #050506 58%, #081018 100%);
  color: #f8fafc;
}
.topbar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  margin-bottom: 12px;
}
.topbar h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #f8fafc;
}
.groups-link {
  justify-self: end;
  color: #67e8f9;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.quick-card {
  position: relative;
  min-height: 92px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.04));
  color: #f8fafc;
  cursor: pointer;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
.quick-card.active {
  border-color: rgba(103, 232, 249, 0.56);
  box-shadow: 0 16px 38px rgba(34, 211, 238, 0.18);
}
.quick-icon {
  position: relative;
  width: 46px;
  height: 46px;
  margin: 8px auto 6px;
  border-radius: 17px;
  display: grid;
  place-items: center;
  color: #fff;
}
.quick-badge {
  position: absolute;
  right: -7px;
  top: -7px;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  border: 2px solid #07111f;
  background: #f8fafc;
  color: #0f172a;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
  line-height: 1;
}
.quick-icon svg {
  width: 23px;
  height: 23px;
  fill: currentColor;
}
.quick-icon.hot {
  background: linear-gradient(135deg, #fb7185, #f97316);
  box-shadow: 0 12px 26px rgba(251, 113, 133, 0.28);
}
.quick-icon.aqua {
  background: linear-gradient(135deg, #22d3ee, #2563eb);
  box-shadow: 0 12px 26px rgba(34, 211, 238, 0.25);
}
.quick-icon.violet {
  background: linear-gradient(135deg, #a78bfa, #06b6d4);
  box-shadow: 0 12px 26px rgba(167, 139, 250, 0.24);
}
.quick-card b,
.quick-card small {
  display: block;
}
.quick-card b {
  font-size: 12px;
  color: #e2e8f0;
}
.quick-card small {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 800;
}
.toolbar,
.recommend-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 6px 0 8px;
  color: #94a3b8;
  font-size: 13px;
}
.toolbar button,
.recommend-head button {
  border: 0;
  background: transparent;
  color: #67e8f9;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
}
.message-list {
  display: grid;
  gap: 2px;
}
.request-list {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}
.request-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.14), rgba(15, 23, 42, 0.82));
  border: 1px solid rgba(103, 232, 249, 0.24);
}
.request-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.request-actions button {
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.75);
  color: #cbd5e1;
  padding: 7px 10px;
  font-weight: 900;
  cursor: pointer;
}
.request-actions button.accept {
  background: #22d3ee;
  border-color: #22d3ee;
  color: #042f2e;
}
.message-row,
.discover-row {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: transparent;
  color: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  font: inherit;
}
.row-avatar,
.discover-avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: #2f80ed;
  color: #fff;
  font-weight: 900;
}
.row-main,
.discover-row span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
.row-main b,
.row-main small,
.discover-row b,
.discover-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-main b,
.discover-row b {
  font-size: 15px;
  color: #f8fafc;
}
.row-main small,
.discover-row small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 12px;
}
.row-side {
  width: 48px;
  min-width: 48px;
  max-width: 48px;
  flex: 0 0 48px;
  display: grid;
  justify-items: end;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}
.row-side small {
  max-width: 100%;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-side i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff2d55;
}
.message-row.unread .row-main b {
  font-weight: 900;
}
.recommend-card {
  margin-top: 16px;
}
.discover-row {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.discover-row em {
  color: #67e8f9;
  font-style: normal;
  font-weight: 900;
}
.empty {
  color: #94a3b8;
  font-size: 14px;
}
</style>
