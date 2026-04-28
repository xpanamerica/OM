<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AlgorithmResetButton from "@/components/algorithm/AlgorithmResetButton.vue";
import * as profileApi from "@/api/profile";
import * as socialApi from "@/api/social";
import * as usersApi from "@/api/users";
import type { ProfileHub } from "@/api/profile";
import type { VideoListItem } from "@/api/videos";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";
import { formatApiError } from "@/util/errors";
import { ElMessage } from "@/util/elementPlusMessage";

const auth = useAuthStore();
const hub = ref<ProfileHub | null>(null);
const privacy = ref<socialApi.UserPrivacy | null>(null);
const friends = ref<socialApi.FollowUser[]>([]);
const loading = ref(false);
const avatarInputRef = ref<HTMLInputElement | null>(null);
const avatarUploading = ref(false);

const displayName = computed(() => auth.user?.username ?? auth.user?.email ?? "访客");
const initial = computed(() => {
  const s = displayName.value.trim();
  return s ? s.slice(0, 1).toUpperCase() : "?";
});

function coverOf(v: VideoListItem): string | undefined {
  return resolveApiAssetUrl(v.cover_url);
}

const avatarUrl = computed(() => resolveApiAssetUrl(hub.value?.avatar_url || auth.user?.avatar_url || ""));

async function loadHub() {
  if (!auth.isLoggedIn) {
    hub.value = null;
    friends.value = [];
    return;
  }
  loading.value = true;
  try {
    const [h, p, fs] = await Promise.all([
      profileApi.fetchProfileHub(),
      socialApi.fetchMyPrivacy(),
      socialApi.listMyFriends().catch(() => []),
    ]);
    hub.value = h;
    privacy.value = p;
    friends.value = fs;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function savePrivacy() {
  if (!privacy.value) return;
  try {
    privacy.value = await socialApi.updateMyPrivacy(privacy.value);
    ElMessage.success("隐私设置已保存");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function onPickAvatar(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  avatarUploading.value = true;
  try {
    const me = await usersApi.uploadMyAvatar(file);
    auth.user = me;
    await loadHub();
    ElMessage.success("头像已更新");
  } catch (err) {
    ElMessage.error(formatApiError(err));
  } finally {
    avatarUploading.value = false;
    input.value = "";
  }
}

onMounted(() => {
  void loadHub();
});

watch(
  () => auth.isLoggedIn,
  () => {
    void loadHub();
  },
);
</script>

<template>
  <div v-loading="loading" class="native-stack hub-root">
    <!-- 未登录：简化引导 -->
    <template v-if="!auth.isLoggedIn">
      <div class="guest-card native-card">
        <div class="guest-label">当前身份</div>
        <div class="guest-name">{{ displayName }}</div>
        <RouterLink class="native-btn native-btn--primary guest-login" :to="{ name: 'auth', query: { redirect: '/hub' } }">
          登录
        </RouterLink>
      </div>
    </template>

    <!-- 已登录：个人中心概览 -->
    <template v-else-if="hub">
      <section class="xhs-hero">
        <div class="xhs-hero-bg" aria-hidden="true" />
        <div class="xhs-hero-content">
          <div class="xhs-top-row">
            <button type="button" class="xhs-avatar" :disabled="avatarUploading" aria-label="上传头像" @click="avatarInputRef?.click()">
              <img v-if="avatarUrl" :src="avatarUrl" alt="" />
              <span v-else>{{ initial }}</span>
            </button>
            <input ref="avatarInputRef" class="avatar-file" type="file" accept="image/jpeg,image/png,image/webp" @change="onPickAvatar" />
            <div class="xhs-identity">
              <h1 class="xhs-name">{{ displayName }}</h1>
              <p class="xhs-idline">恒频OM · {{ auth.user?.email }}</p>
              <p class="xhs-bio">历史记录、收藏与互动消息一站查看</p>
            </div>
          </div>
          <div class="xhs-stats">
            <div class="xhs-stat">
              <span class="xhs-stat-num">{{ hub.following_count }}</span>
              <span class="xhs-stat-label">关注</span>
            </div>
            <div class="xhs-stat">
              <span class="xhs-stat-num">{{ hub.followers_count }}</span>
              <span class="xhs-stat-label">粉丝</span>
            </div>
            <div class="xhs-stat">
              <span class="xhs-stat-num">{{ hub.friends_count }}</span>
              <span class="xhs-stat-label">好友</span>
            </div>
            <div class="xhs-stat">
              <span class="xhs-stat-num">{{ hub.likes_and_favorites_received }}</span>
              <span class="xhs-stat-label">获赞收藏</span>
            </div>
          </div>
        </div>
      </section>

      <section class="xhs-shortcuts">
        <RouterLink class="xhs-scard" :to="{ name: 'history' }">
          <span class="xhs-scard-ico" aria-hidden="true">⏱</span>
          <span class="xhs-scard-t">历史记录</span>
          <span class="xhs-scard-s">看过的视频</span>
        </RouterLink>
        <RouterLink class="xhs-scard" :to="{ name: 'messages' }">
          <span class="xhs-scard-ico" aria-hidden="true">💬</span>
          <span class="xhs-scard-t">互动消息</span>
          <span class="xhs-scard-s">评论与提醒</span>
          <span v-if="hub.unread_notification_count > 0" class="xhs-dot">{{ hub.unread_notification_count > 99 ? "99+" : hub.unread_notification_count }}</span>
        </RouterLink>
        <RouterLink class="xhs-scard" :to="{ name: 'direct-messages' }">
          <span class="xhs-scard-ico" aria-hidden="true">✉</span>
          <span class="xhs-scard-t">私信</span>
          <span class="xhs-scard-s">好友对话</span>
        </RouterLink>
        <RouterLink class="xhs-scard" :to="{ name: 'favorites' }">
          <span class="xhs-scard-ico" aria-hidden="true">♥</span>
          <span class="xhs-scard-t">个人收藏</span>
          <span class="xhs-scard-s">收藏的视频</span>
        </RouterLink>
      </section>

      <section class="friends-card">
        <div class="friends-head">
          <div>
            <h2>好友列表</h2>
            <p>{{ hub.pending_friend_request_count > 0 ? `${hub.pending_friend_request_count} 条申请待处理` : "通过申请后的好友会显示在这里" }}</p>
          </div>
          <RouterLink :to="{ name: 'messages' }">处理申请</RouterLink>
        </div>
        <div v-if="friends.length > 0" class="friend-strip">
          <RouterLink v-for="friend in friends.slice(0, 8)" :key="friend.id" class="friend-chip" :to="{ name: 'user-profile', params: { id: friend.id } }">
            <span>{{ friend.username.slice(0, 1).toUpperCase() }}</span>
            <b>{{ friend.username }}</b>
          </RouterLink>
        </div>
        <p v-else class="friends-empty">暂无好友，去浏览创作者主页并发送好友申请。</p>
      </section>

      <section v-if="privacy" class="privacy-card">
        <div class="privacy-head">
          <div>
            <h2>隐私设置</h2>
            <p>控制谁能浏览你的个人主页、谁能给你发私信。</p>
          </div>
          <button type="button" @click="savePrivacy">保存</button>
        </div>
        <label>
          主页浏览
          <select v-model="privacy.profile_visibility">
            <option value="public">所有人</option>
            <option value="followers">关注我的人</option>
            <option value="mutual">互相关注</option>
            <option value="private">仅自己</option>
          </select>
        </label>
        <label>
          私信权限
          <select v-model="privacy.message_permission">
            <option value="everyone">所有人</option>
            <option value="following">我关注的人</option>
            <option value="mutual">互相关注</option>
            <option value="none">关闭私信</option>
          </select>
        </label>
      </section>

      <AlgorithmResetButton />

      <p class="xhs-links">
        <RouterLink :to="{ name: 'profile' }">账号与资料</RouterLink>
        <span class="xhs-sep">·</span>
        <RouterLink :to="{ name: 'search' }">高级搜索</RouterLink>
      </p>

      <section class="xhs-works">
        <div class="xhs-works-head">
          <h2 class="xhs-works-title">我的作品</h2>
          <RouterLink class="xhs-works-more" :to="{ name: 'native-create' }">去创作</RouterLink>
        </div>
        <div v-if="hub.recent_videos.length === 0" class="xhs-empty">暂无稿件，去创作页发布你的第一条视频</div>
        <div v-else class="xhs-grid">
          <RouterLink
            v-for="v in hub.recent_videos"
            :key="v.id"
            class="xhs-cell"
            :to="{ name: 'video-detail', params: { id: v.id } }"
          >
            <div class="xhs-thumb-wrap">
              <img v-if="coverOf(v)" class="xhs-thumb" :src="coverOf(v)" :alt="v.title" loading="lazy" />
              <div v-else class="xhs-thumb xhs-thumb--ph">{{ v.title.slice(0, 1) }}</div>
              <span class="xhs-status" :data-st="v.status">{{ v.status }}</span>
            </div>
            <div class="xhs-cell-title">{{ v.title }}</div>
            <div class="xhs-cell-meta">{{ v.views_count }} 浏览</div>
          </RouterLink>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.hub-root {
  padding-bottom: 24px;
}

.guest-card {
  padding: 20px;
  margin: 12px 12px 0;
}
.guest-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--native-text-muted);
  text-transform: uppercase;
}
.guest-name {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 800;
  color: var(--native-text-primary);
}
.guest-login {
  display: inline-block;
  margin-top: 16px;
  text-decoration: none;
}

.xhs-hero {
  position: relative;
  margin: 0 0 12px;
  border-radius: 0 0 20px 20px;
  overflow: hidden;
  color: #fff;
}
.xhs-hero-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(145deg, #2a2420 0%, #1a1a1e 45%, #121218 100%);
  opacity: 1;
}
.xhs-hero-bg::after {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 120% 80% at 20% 0%, rgba(255, 120, 80, 0.18), transparent 55%);
  pointer-events: none;
}
.xhs-hero-content {
  position: relative;
  padding: 20px 16px 18px;
}
.xhs-top-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.xhs-avatar {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #22d3ee, #2563eb);
  border: 2px solid rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 800;
  color: #fff;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
}
.xhs-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.xhs-avatar:disabled {
  opacity: 0.65;
  cursor: wait;
}
.avatar-file {
  display: none;
}
.xhs-identity {
  flex: 1;
  min-width: 0;
}
.xhs-name {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.25;
}
.xhs-idline {
  margin: 6px 0 0;
  font-size: 12px;
  opacity: 0.75;
  word-break: break-all;
}
.xhs-bio {
  margin: 8px 0 0;
  font-size: 13px;
  opacity: 0.85;
  line-height: 1.4;
}
.xhs-stats {
  display: flex;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  justify-content: space-around;
  gap: 8px;
}
.xhs-stat {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.xhs-stat-num {
  font-size: 18px;
  font-weight: 800;
}
.xhs-stat-label {
  font-size: 11px;
  opacity: 0.75;
  font-weight: 600;
}

.xhs-shortcuts {
  display: flex;
  gap: 10px;
  padding: 0 12px;
  margin-bottom: 10px;
}
.xhs-scard {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 12px 10px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(103, 232, 249, 0.16);
  text-decoration: none;
  color: #f8fafc;
  min-height: 88px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
}
.xhs-scard-ico {
  font-size: 18px;
  margin-bottom: 6px;
  opacity: 0.85;
}
.xhs-scard-t {
  font-size: 13px;
  font-weight: 800;
  color: #f8fafc;
}
.xhs-scard-s {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}
.friends-card {
  padding: 14px;
  margin: 0 12px 10px;
  border: 1px solid rgba(103, 232, 249, 0.16);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.14), transparent 42%),
    rgba(15, 23, 42, 0.76);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.22);
}
.friends-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.friends-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 900;
  color: #f8fafc;
}
.friends-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.friends-head a {
  flex-shrink: 0;
  color: var(--native-accent);
  font-size: 13px;
  font-weight: 900;
  text-decoration: none;
}
.friend-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.friend-chip {
  min-width: 72px;
  display: grid;
  justify-items: center;
  gap: 6px;
  color: #f8fafc;
  text-decoration: none;
}
.friend-chip span {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 900;
  background: linear-gradient(135deg, #22d3ee, #2563eb);
}
.friend-chip b {
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.friends-empty {
  margin: 0;
  color: #94a3b8;
  font-size: 13px;
}
.xhs-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  line-height: 18px;
  text-align: center;
  background:rgb(36, 76, 255);
  color: #fff;
}

.privacy-card {
  margin: 0 12px 12px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.76);
  border: 1px solid rgba(103, 232, 249, 0.16);
  color: #f8fafc;
}
.privacy-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.privacy-head h2 {
  margin: 0;
  font-size: 16px;
  color: #f8fafc;
}
.privacy-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.privacy-head button {
  align-self: flex-start;
  border: 0;
  border-radius: 999px;
  background: var(--native-accent);
  color: #fff;
  padding: 7px 14px;
  font-weight: 800;
  cursor: pointer;
}
.privacy-card label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
}
.privacy-card select {
  min-width: 8rem;
  border-radius: 10px;
  border: 1px solid rgba(103, 232, 249, 0.22);
  padding: 8px;
  background: #020617;
  color: #f8fafc;
}

.xhs-links {
  text-align: center;
  font-size: 13px;
  margin: 4px 0 16px;
  color: var(--native-text-muted);
}
.xhs-links a {
  color: var(--native-accent);
  font-weight: 600;
  text-decoration: none;
}
.xhs-sep {
  margin: 0 6px;
  opacity: 0.5;
}

.xhs-works {
  margin: 0 12px;
  padding: 16px 14px 20px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.76);
  color: #f8fafc;
  border: 1px solid rgba(103, 232, 249, 0.16);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.22);
}
.xhs-works-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.xhs-works-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: #f8fafc;
}
.xhs-works-more {
  font-size: 13px;
  font-weight: 700;
  color: var(--native-accent);
  text-decoration: none;
}
.xhs-empty {
  font-size: 13px;
  color: #94a3b8;
  padding: 12px 0;
}
.xhs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.xhs-cell {
  text-decoration: none;
  color: inherit;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.62);
  border: 1px solid rgba(103, 232, 249, 0.12);
}
.xhs-thumb-wrap {
  position: relative;
  aspect-ratio: 3 / 4;
  background: #020617;
}
.xhs-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.xhs-thumb--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 800;
  color: #94a3b8;
}
.xhs-status {
  position: absolute;
  left: 6px;
  bottom: 6px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  text-transform: uppercase;
}
.xhs-cell-title {
  padding: 8px 8px 0;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.xhs-cell-meta {
  padding: 4px 8px 10px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
