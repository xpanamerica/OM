<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { formatApiError } from "@/util/errors";
import * as socialApi from "@/api/social";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

const route = useRoute();
const router = useRouter();
const userId = computed(() => String(route.params.id));
const loading = ref(false);
const profile = ref<socialApi.PublicUserProfile | null>(null);
const following = ref<socialApi.FollowUser[]>([]);
const followers = ref<socialApi.FollowUser[]>([]);

const avatarUrl = computed(() => resolveApiAssetUrl(profile.value?.user.avatar_url || ""));
const friendLabel = computed(() => {
  if (!profile.value) return "添加好友";
  if (profile.value.friend_request_status === "accepted") return "已是好友";
  if (profile.value.friend_request_status === "outgoing_pending") return "等待通过";
  if (profile.value.friend_request_status === "incoming_pending") return "去处理";
  return "添加好友";
});

async function load() {
  loading.value = true;
  try {
    profile.value = await socialApi.fetchUserProfile(userId.value);
    const [a, b] = await Promise.all([
      socialApi.listFollowing(userId.value).catch(() => []),
      socialApi.listFollowers(userId.value).catch(() => []),
    ]);
    following.value = a;
    followers.value = b;
  } catch (e) {
    profile.value = null;
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function toggleFollow() {
  if (!profile.value) return;
  try {
    if (profile.value.is_following) await socialApi.unfollowUser(profile.value.user.id);
    else await socialApi.followUser(profile.value.user.id);
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

function openDm() {
  if (!profile.value) return;
  void router.push({ name: "direct-messages", params: { peerId: profile.value.user.id } });
}

async function addFriend() {
  if (!profile.value) return;
  try {
    if (profile.value.friend_request_status === "accepted") {
      openDm();
      return;
    }
    if (profile.value.friend_request_status === "incoming_pending") {
      void router.push({ name: "messages" });
      return;
    }
    if (profile.value.friend_request_status === "outgoing_pending") {
      ElMessage.info("好友申请已发送，请等待对方处理");
      return;
    }
    await socialApi.sendFriendRequest(profile.value.user.id);
    ElMessage.success("好友申请已发送，对方可在消息中选择通过或拒绝");
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

onMounted(() => void load());
watch(userId, () => void load());
</script>

<template>
  <div v-loading="loading" class="native-stack user-profile">
    <RouterLink class="back" :to="{ name: 'native-hub' }">← 返回</RouterLink>
    <section v-if="profile" class="hero">
      <div class="avatar">
        <img v-if="avatarUrl" :src="avatarUrl" alt="" />
        <span v-else>{{ profile.user.username.slice(0, 1).toUpperCase() }}</span>
      </div>
      <div class="main">
        <h1>{{ profile.user.username }}</h1>
        <p class="hint">
          {{ profile.is_mutual ? "互相关注" : profile.follows_me ? "关注了你" : "恒频OM 用户" }}
        </p>
        <div class="stats">
          <span><b>{{ profile.following_count }}</b><small>关注</small></span>
          <span><b>{{ profile.followers_count }}</b><small>粉丝</small></span>
          <span><b>{{ profile.friends_count }}</b><small>好友</small></span>
        </div>
        <div class="actions">
          <button type="button" class="primary" @click="toggleFollow">
            {{ profile.is_following ? "已关注" : "关注" }}
          </button>
          <button type="button" class="primary" @click="addFriend">
            {{ friendLabel }}
          </button>
          <button type="button" :disabled="!profile.can_message" @click="openDm">
            {{ profile.can_message ? "私信" : "不可私信" }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="profile" class="card">
      <h2>频友发布</h2>
      <p v-if="profile.recent_videos.length === 0" class="empty">暂无公开作品</p>
      <div v-else class="grid">
        <RouterLink
          v-for="v in profile.recent_videos"
          :key="v.id"
          class="work"
          :to="{ name: 'video-detail', params: { id: v.id } }"
        >
          <img v-if="resolveApiAssetUrl(v.cover_url)" :src="resolveApiAssetUrl(v.cover_url)" :alt="v.title" />
          <div v-else class="cover-ph">{{ v.title.slice(0, 1) }}</div>
          <span>{{ v.title }}</span>
        </RouterLink>
      </div>
    </section>

    <section v-if="profile" class="card rels">
      <div>
        <h2>关注</h2>
        <RouterLink v-for="u in following" :key="u.id" :to="{ name: 'user-profile', params: { id: u.id } }">
          {{ u.username }}
        </RouterLink>
        <p v-if="following.length === 0" class="empty">暂无关注</p>
      </div>
      <div>
        <h2>粉丝</h2>
        <RouterLink v-for="u in followers" :key="u.id" :to="{ name: 'user-profile', params: { id: u.id } }">
          {{ u.username }}
        </RouterLink>
        <p v-if="followers.length === 0" class="empty">暂无粉丝</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.user-profile {
  padding-bottom: 28px;
}
.back {
  display: inline-block;
  margin-bottom: 12px;
  color: var(--native-text-muted);
  text-decoration: none;
}
.hero,
.card {
  border-radius: 18px;
  background: var(--native-bg-surface, #fff);
  border: 1px solid var(--native-border);
  padding: 16px;
  margin-bottom: 12px;
}
.hero {
  display: flex;
  gap: 14px;
}
.avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #22d3ee, #2563eb);
  color: #fff;
  font-size: 24px;
  font-weight: 800;
  overflow: hidden;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.main {
  flex: 1;
  min-width: 0;
}
h1,
h2 {
  margin: 0;
}
h1 {
  font-size: 22px;
}
h2 {
  font-size: 16px;
  margin-bottom: 12px;
}
.hint,
.empty {
  color: var(--native-text-muted);
  font-size: 13px;
}
.stats {
  display: flex;
  gap: 8px;
  margin: 10px 0;
  width: 100%;
}
.stats span {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 6px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--native-accent) 8%, transparent);
}
.stats b {
  font-size: 18px;
}
.stats small {
  color: var(--native-text-muted);
  font-size: 11px;
  font-weight: 800;
}
.actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
  margin-top: 12px;
}
button {
  border-radius: 999px;
  border: 1px solid var(--native-border, #d7e3f3);
  background: #fff;
  padding: 9px 10px;
  font-weight: 800;
  cursor: pointer;
  color: var(--native-text-primary, #111827);
  min-width: 0;
  white-space: nowrap;
}
button.primary {
  background: var(--native-accent, #2f80ed);
  color: #fff;
  border-color: var(--native-accent, #2f80ed);
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.work {
  color: inherit;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
}
.work img,
.cover-ph {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: 12px;
  background: #eee;
  display: grid;
  place-items: center;
  margin-bottom: 6px;
}
.rels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.rels a {
  display: block;
  color: var(--native-text-primary);
  text-decoration: none;
  margin-bottom: 8px;
  font-weight: 700;
}
</style>
