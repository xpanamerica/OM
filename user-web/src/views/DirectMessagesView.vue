<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { formatApiError } from "@/util/errors";
import { useAuthStore } from "@/stores/auth";
import * as socialApi from "@/api/social";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

type MessageAttachment = socialApi.DirectMessageAttachment;
type RichMessageBody = {
  __om_dm_v1?: true;
  text?: string;
  attachments?: MessageAttachment[];
};

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const conversations = ref<socialApi.DirectConversation[]>([]);
const friends = ref<socialApi.FollowUser[]>([]);
const messages = ref<socialApi.DirectMessage[]>([]);
const loading = ref(false);
const text = ref("");
const sending = ref(false);
const emojiOpen = ref(false);
const pendingAttachments = ref<MessageAttachment[]>([]);
const attachmentObjectUrls = ref<Record<string, string>>({});
const threadRef = ref<HTMLElement | null>(null);
const imageInputRef = ref<HTMLInputElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const peerId = computed(() => String(route.params.peerId ?? ""));
const activePeer = computed(
  () => conversations.value.find((x) => x.peer.id === peerId.value)?.peer
    ?? friends.value.find((x) => x.id === peerId.value)
    ?? null,
);
const activePeerAvatar = computed(() => resolveApiAssetUrl(activePeer.value?.avatar_url || ""));
const friendsWithoutConversation = computed(() => {
  const ids = new Set(conversations.value.map((x) => x.peer.id));
  return friends.value.filter((x) => !ids.has(x.id));
});
const emojiGroups = [
  ["😀", "😄", "😁", "😂", "😊", "😍", "😘", "😎"],
  ["👍", "👏", "🙏", "💪", "🔥", "✨", "🎉", "❤️"],
  ["😢", "😭", "😅", "😴", "🤔", "🙌", "👌", "😇"],
];

async function loadConversations() {
  conversations.value = await socialApi.listConversations();
}

async function loadFriends() {
  friends.value = await socialApi.listMyFriends().catch(() => []);
}

async function loadMessages() {
  if (!peerId.value) {
    messages.value = [];
    return;
  }
  messages.value = await socialApi.listMessages(peerId.value);
  await loadConversations();
  await nextTick();
  threadRef.value?.scrollTo({ top: threadRef.value.scrollHeight });
}

let pollTimer: number | undefined;

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(() => {
    if (peerId.value) void loadMessages().catch(() => {});
    else void Promise.all([loadConversations(), loadFriends()]).catch(() => {});
  }, 5000);
}

function stopPolling() {
  if (pollTimer) window.clearInterval(pollTimer);
  pollTimer = undefined;
}

async function load() {
  loading.value = true;
  try {
    await Promise.all([loadConversations(), loadFriends()]);
    await loadMessages();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function send() {
  const body = text.value.trim();
  const attachments = pendingAttachments.value;
  if (!peerId.value || (!body && attachments.length === 0)) return;
  try {
    sending.value = true;
    await socialApi.sendMessage(peerId.value, JSON.stringify({ __om_dm_v1: true, text: body, attachments }));
    text.value = "";
    pendingAttachments.value = [];
    emojiOpen.value = false;
    await loadMessages();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    sending.value = false;
  }
}

function parseMessageBody(raw: string): RichMessageBody {
  try {
    const data = JSON.parse(raw) as RichMessageBody;
    if (data && data.__om_dm_v1) return data;
  } catch {
    /* old plain-text messages */
  }
  return { text: raw, attachments: [] };
}

function messagePreview(raw: string | null | undefined) {
  if (!raw) return "暂无消息";
  const parsed = parseMessageBody(raw);
  const body = parsed.text?.trim();
  if (body) return body;
  const first = parsed.attachments?.[0];
  if (first?.content_type?.startsWith("image/")) return "[图片]";
  if (first) return "[附件]";
  return "新消息";
}

function conversationPreview(c: socialApi.DirectConversation) {
  return c.last_message_preview || messagePreview(c.last_message?.body);
}

function appendEmoji(emoji: string) {
  text.value += emoji;
}

async function uploadFiles(files: FileList | null) {
  if (!peerId.value || !files?.length) return;
  try {
    for (const file of Array.from(files)) {
      const uploaded = await socialApi.uploadMessageAttachment(peerId.value, file);
      pendingAttachments.value.push(uploaded);
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    if (imageInputRef.value) imageInputRef.value.value = "";
    if (fileInputRef.value) fileInputRef.value.value = "";
  }
}

function removePendingAttachment(id: string) {
  pendingAttachments.value = pendingAttachments.value.filter((x) => x.id !== id);
}

function isImageAttachment(a: MessageAttachment) {
  return Boolean(a.content_type?.startsWith("image/"));
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function attachmentPreviewUrl(a: MessageAttachment) {
  const existing = attachmentObjectUrls.value[a.id];
  if (existing) return existing;
  void socialApi.downloadMessageAttachmentBlob(a.url).then((blob) => {
    attachmentObjectUrls.value = { ...attachmentObjectUrls.value, [a.id]: URL.createObjectURL(blob) };
  }).catch(() => {});
  return "";
}

async function downloadAttachment(a: MessageAttachment) {
  try {
    const blob = await socialApi.downloadMessageAttachmentBlob(a.url);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = a.original_filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

function openPeer(id: string) {
  void router.push({ name: "direct-messages", params: { peerId: id } });
}

function backToList() {
  void router.push({ name: "direct-messages" });
}

onMounted(() => {
  void load();
  startPolling();
});
onBeforeUnmount(() => {
  stopPolling();
  Object.values(attachmentObjectUrls.value).forEach((url) => URL.revokeObjectURL(url));
});
watch(peerId, () => {
  void loadMessages();
  startPolling();
});
</script>

<template>
  <div v-loading="loading" class="dm native-stack">
    <div class="head">
      <div>
        <h1>消息</h1>
        <p>好友、关注与私信会话集中在这里，重要更新不会错过。</p>
      </div>
      <RouterLink :to="{ name: 'messages' }">互动通知</RouterLink>
    </div>

    <div class="layout" :class="{ 'has-peer': Boolean(peerId) }">
      <aside class="list">
        <div class="list-head">
          <b>会话列表</b>
          <small>{{ conversations.length + friendsWithoutConversation.length }} 个联系人</small>
        </div>
        <button
          v-for="c in conversations"
          :key="c.id"
          type="button"
          class="conv"
          :class="{ active: c.peer.id === peerId }"
          @click="openPeer(c.peer.id)"
        >
          <span class="avatar">
            <img v-if="resolveApiAssetUrl(c.peer.avatar_url || '')" :src="resolveApiAssetUrl(c.peer.avatar_url || '')" alt="" />
            <span v-else>{{ c.peer.username.slice(0, 1).toUpperCase() }}</span>
          </span>
          <span class="conv-main">
            <b>{{ c.peer.username }}</b>
            <small>{{ conversationPreview(c) }}</small>
          </span>
          <em v-if="c.unread_count > 0">{{ c.unread_count }}</em>
        </button>
        <div v-if="friendsWithoutConversation.length > 0" class="friend-section">
          <h2>好友</h2>
          <button
            v-for="friend in friendsWithoutConversation"
            :key="friend.id"
            type="button"
            class="conv"
            :class="{ active: friend.id === peerId }"
            @click="openPeer(friend.id)"
          >
            <span class="avatar">
              <img v-if="resolveApiAssetUrl(friend.avatar_url || '')" :src="resolveApiAssetUrl(friend.avatar_url || '')" alt="" />
              <span v-else>{{ friend.username.slice(0, 1).toUpperCase() }}</span>
            </span>
            <span class="conv-main">
              <b>{{ friend.username }}</b>
              <small>点击开始聊天</small>
            </span>
          </button>
        </div>
        <p v-if="conversations.length === 0 && friendsWithoutConversation.length === 0" class="empty">
          暂无私信会话，互相关注后好友会出现在这里。
        </p>
      </aside>

      <section class="thread-card">
        <template v-if="peerId">
          <div class="thread-title">
            <button type="button" class="back-btn" @click="backToList">‹</button>
            <span class="avatar thread-avatar">
              <img v-if="activePeerAvatar" :src="activePeerAvatar" alt="" />
              <span v-else>{{ activePeer?.username?.slice(0, 1).toUpperCase() || "聊" }}</span>
            </span>
            <span class="thread-name">
              <RouterLink v-if="activePeer" :to="{ name: 'user-profile', params: { id: activePeer.id } }">
                {{ activePeer.username }}
              </RouterLink>
              <span v-else>新的对话</span>
              <small>互相关注后可持续对话</small>
            </span>
            <button type="button" class="more-btn" title="更多">…</button>
          </div>
          <div ref="threadRef" class="thread">
            <div v-if="activePeer && messages.length === 0" class="greet-card">
              <div>
                <b>打个招呼</b>
                <small>用一句轻松的话开启聊天</small>
              </div>
              <button type="button" @click="text = '你好，很高兴认识你'">你好</button>
              <button type="button" @click="text = '我们已互相关注，开始聊聊吧'">开始聊聊</button>
              <button type="button" @click="appendEmoji('😊')">😊</button>
              <button type="button" @click="appendEmoji('👏')">👏</button>
            </div>
            <p v-if="messages.length === 0" class="empty">还没有消息，打个招呼吧。</p>
            <div
              v-for="m in messages"
              :key="m.id"
              class="bubble"
              :class="{ mine: m.sender_id === auth.user?.id }"
            >
              <div class="bubble-card">
                <p v-if="parseMessageBody(m.body).text" class="bubble-text">{{ parseMessageBody(m.body).text }}</p>
                <div v-if="parseMessageBody(m.body).attachments?.length" class="bubble-files">
                  <button
                    v-for="a in parseMessageBody(m.body).attachments"
                    :key="a.id"
                    type="button"
                    class="file-chip"
                    :class="{ 'file-chip--image': isImageAttachment(a) }"
                    @click="downloadAttachment(a)"
                  >
                    <img v-if="isImageAttachment(a) && attachmentPreviewUrl(a)" :src="attachmentPreviewUrl(a)" :alt="a.original_filename" />
                    <span v-else class="file-icon">📎</span>
                    <span class="file-meta">
                      <b>{{ a.original_filename }}</b>
                      <small>{{ formatFileSize(a.size_bytes) }}</small>
                    </span>
                  </button>
                </div>
              </div>
              <small>{{ new Date(m.created_at).toLocaleString([], { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) }}</small>
            </div>
          </div>
          <form class="composer" @submit.prevent="send">
            <div v-if="pendingAttachments.length" class="pending-files">
              <button
                v-for="a in pendingAttachments"
                :key="a.id"
                type="button"
                class="pending-file"
                @click="removePendingAttachment(a.id)"
              >
                {{ isImageAttachment(a) ? "图片" : "附件" }} · {{ a.original_filename }} ×
              </button>
            </div>
            <div v-if="emojiOpen" class="emoji-panel">
              <div v-for="(group, idx) in emojiGroups" :key="idx" class="emoji-row">
                <button v-for="emoji in group" :key="emoji" type="button" @click="appendEmoji(emoji)">
                  {{ emoji }}
                </button>
              </div>
            </div>
            <div class="composer-row">
              <button type="button" class="tool-btn" title="表情" @click="emojiOpen = !emojiOpen">☺</button>
              <button type="button" class="tool-btn" title="图片" @click="imageInputRef?.click()">🖼</button>
              <button type="button" class="tool-btn" title="附件" @click="fileInputRef?.click()">＋</button>
              <input
                ref="imageInputRef"
                class="hidden-input"
                type="file"
                accept="image/*"
                multiple
                @change="uploadFiles(($event.target as HTMLInputElement).files)"
              />
              <input
                ref="fileInputRef"
                class="hidden-input"
                type="file"
                accept=".txt,.md,.pdf,.doc,.docx,image/*"
                multiple
                @change="uploadFiles(($event.target as HTMLInputElement).files)"
              />
              <input v-model="text" maxlength="4000" placeholder="友好一点..." />
              <button class="send-btn" type="submit" :disabled="sending || (!text.trim() && pendingAttachments.length === 0)">
                发送
              </button>
            </div>
          </form>
        </template>
        <p v-else class="empty center">请选择左侧会话，或从用户主页点击「私信」。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dm {
  min-height: calc(100dvh - 48px - var(--h5-tabbar-height, 72px));
  margin: 0 -10px;
  padding: 8px 10px 0;
  background:
    radial-gradient(circle at 16% -10%, rgba(34, 211, 238, 0.16), transparent 32%),
    linear-gradient(180deg, #07111f 0%, #050506 60%, #081018 100%);
  color: #f8fafc;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
  color: #f8fafc;
}
h1 {
  margin: 0;
  font-size: 17px;
  line-height: 1.2;
}
.head p,
.empty {
  margin: 3px 0 0;
  color: var(--native-text-muted);
  font-size: 12px;
}
.head a {
  color: var(--native-accent);
  font-weight: 800;
  font-size: 12px;
  text-decoration: none;
}
.layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 12px;
}
.list,
.thread-card {
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.88));
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.26);
}
.list {
  padding: 10px;
}
.list-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  padding: 4px 8px 8px;
  color: #e2e8f0;
}
.list-head b {
  font-size: 15px;
}
.list-head small {
  color: #64748b;
  font-size: 11px;
}
.conv {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: #f8fafc;
  cursor: pointer;
  text-align: left;
}
.conv.active {
  background: rgba(34, 211, 238, 0.12);
  box-shadow: inset 0 0 0 1px rgba(103, 232, 249, 0.16);
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #22d3ee, #2563eb);
  color: #fff;
  font-weight: 800;
  overflow: hidden;
  flex-shrink: 0;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.friend-section {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.friend-section h2 {
  margin: 0 0 8px;
  color: var(--native-text-muted);
  font-size: 12px;
  font-weight: 900;
}
.conv-main {
  flex: 1;
  min-width: 0;
}
.conv-main b,
.conv-main small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-main small {
  color: #94a3b8;
  margin-top: 2px;
}
.conv em {
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  border-radius: 999px;
  background: var(--native-accent);
  color: #fff;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}
.thread-card {
  min-height: 560px;
  max-height: calc(100dvh - 132px);
  display: flex;
  flex-direction: column;
}
.thread-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-weight: 800;
  background: rgba(2, 6, 23, 0.42);
}
.thread-title a {
  color: #f8fafc;
  text-decoration: none;
}
.back-btn,
.more-btn {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.07);
  color: #e2e8f0;
  font-size: 24px;
  cursor: pointer;
}
.more-btn {
  margin-left: auto;
  font-size: 20px;
}
.thread-avatar {
  width: 34px;
  height: 34px;
}
.thread-name {
  display: grid;
  min-width: 0;
}
.thread-name small {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}
.thread {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background:
    radial-gradient(circle at 20% 0%, rgba(34, 211, 238, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(6, 182, 212, 0.06), transparent 38%);
}
.greet-card {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 auto 18px;
  max-width: 560px;
  padding: 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.greet-card div {
  flex: 1;
  min-width: 0;
}
.greet-card b,
.greet-card small {
  display: block;
}
.greet-card b {
  color: #f8fafc;
}
.greet-card small {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
}
.greet-card button {
  border: 0;
  border-radius: 14px;
  padding: 8px 10px;
  background: rgba(34, 211, 238, 0.14);
  color: #67e8f9;
  font-weight: 900;
  cursor: pointer;
}
.bubble {
  max-width: min(78%, 560px);
  margin-bottom: 12px;
}
.bubble-card {
  display: inline-block;
  padding: 10px 12px;
  border-radius: 18px 18px 18px 6px;
  background: rgba(255, 255, 255, 0.1);
  color: #f8fafc;
  text-align: left;
}
.bubble-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble small {
  display: block;
  margin-top: 4px;
  color: var(--native-text-muted);
  font-size: 10px;
}
.bubble.mine {
  margin-left: auto;
  text-align: right;
}
.bubble.mine .bubble-card {
  background: var(--native-accent);
  color: #042f2e;
  border-radius: 18px 18px 6px 18px;
}
.composer {
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(2, 6, 23, 0.82);
}
.composer-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.composer input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--native-border);
  border-radius: 999px;
  padding: 10px 14px;
  font: inherit;
  color: var(--native-text-primary, #f8fafc);
  background: rgba(255, 255, 255, 0.06);
}
.composer button {
  border: 0;
  border-radius: 999px;
  min-height: 40px;
  padding: 0 18px;
  background: var(--native-accent);
  color: #042f2e;
  font-weight: 800;
  cursor: pointer;
}
.composer .send-btn {
  flex: 0 0 auto;
  min-width: 70px;
  box-shadow: 0 8px 22px rgba(34, 211, 238, 0.28);
}
.composer button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.tool-btn {
  width: 40px;
  padding: 0 !important;
  background: color-mix(in srgb, var(--native-accent) 12%, transparent) !important;
  color: var(--native-accent) !important;
}
.hidden-input {
  display: none;
}
.emoji-panel {
  padding: 10px;
  margin-bottom: 10px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--native-accent) 10%, var(--native-bg-surface));
}
.emoji-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.emoji-row:last-child {
  margin-bottom: 0;
}
.emoji-row button {
  width: 34px;
  min-height: 34px;
  padding: 0;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  font-size: 18px;
}
.pending-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.pending-file {
  min-height: 30px !important;
  padding: 0 10px !important;
  background: color-mix(in srgb, var(--native-accent) 10%, transparent) !important;
  color: var(--native-accent) !important;
  font-size: 12px;
}
.bubble-files {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}
.file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
  max-width: 320px;
  padding: 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  color: #111827;
  border: 0;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.bubble.mine .file-chip {
  background: rgba(255, 255, 255, 0.94);
}
.file-chip--image {
  display: block;
  padding: 0;
  overflow: hidden;
}
.file-chip img {
  display: block;
  width: min(260px, 100%);
  max-height: 260px;
  object-fit: cover;
}
.file-icon {
  font-size: 20px;
}
.file-meta {
  min-width: 0;
}
.file-meta b,
.file-meta small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-meta small {
  margin-top: 2px;
  color: #64748b;
}
.center {
  margin: auto;
}
@media (max-width: 760px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .head {
    min-height: 30px;
  }
  .layout.has-peer .list {
    display: none;
  }
  .list {
    min-height: calc(100dvh - 142px);
  }
  .thread-card {
    min-height: calc(100dvh - 142px);
    max-height: calc(100dvh - 142px);
    border-radius: 18px 18px 0 0;
  }
  .layout.has-peer .thread-card {
    animation: dm-thread-slide-in 220ms cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform, opacity;
  }
  .greet-card {
    flex-wrap: wrap;
  }
}

@keyframes dm-thread-slide-in {
  from {
    opacity: 0.94;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .layout.has-peer .thread-card {
    animation: none;
    will-change: auto;
  }
}
</style>
