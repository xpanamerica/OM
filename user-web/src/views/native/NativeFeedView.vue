<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as videosApi from "@/api/videos";
import type { VideoListItem } from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";
import HomeImmersivePlayerOverlay from "@/components/home/HomeImmersivePlayerOverlay.vue";
import { useAuthStore } from "@/stores/auth";
import { useAlgorithmStore } from "@/stores/algorithm";
import { ALGORITHM_RESET_EVENT } from "@/composables/useAlgorithmReset";

type HomeTopTab = "following" | "discover" | "explore";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const algorithm = useAlgorithmStore();

const items = ref<VideoListItem[]>([]);
const loading = ref(false);
const loadingMore = ref(false);
const exhausted = ref(false);

const offset = ref(0);
const nextCursor = ref<string | null>(null);
const totalHint = ref(0);

const pageLimit = 12;

const feedOpen = ref(false);
const feedItem = ref<VideoListItem | null>(null);

const drawerOpen = ref(false);
const homeTab = ref<HomeTopTab>("discover");
const showOriginHint = computed(() => auth.isLoggedIn && algorithm.isOriginMode && !categoryId.value);

watch(feedOpen, (v) => {
  if (!v) feedItem.value = null;
});

const categoryId = computed(() => {
  const q = route.query.category_id;
  return typeof q === "string" && q.trim() ? q.trim() : null;
});

function shortAuthorLabel(authorId: string): string {
  const s = authorId.replace(/-/g, "");
  return s.length >= 6 ? `用户${s.slice(0, 6)}` : "创作者";
}

function authorLabel(row: VideoListItem): string {
  return row.author_username?.trim() || shortAuthorLabel(row.author_id);
}

function openAuthor(row: VideoListItem) {
  void router.push({ name: "user-profile", params: { id: row.author_id } });
}

function clearCategory() {
  router.replace({ name: "native-feed", query: {} });
}

async function resetAndLoad() {
  items.value = [];
  offset.value = 0;
  nextCursor.value = null;
  exhausted.value = false;
  totalHint.value = 0;
  await loadMore(true);
}

async function loadMore(initial = false) {
  if (categoryId.value) {
    if (!initial && (loadingMore.value || exhausted.value)) return;
    if (initial) loading.value = true;
    else loadingMore.value = true;
    try {
      const { items: chunk, hasMore, nextCursor: nc, total } = await videosApi.listVideosPaged({
        limit: pageLimit,
        category_id: categoryId.value,
        ...(nextCursor.value ? { cursor: nextCursor.value } : { offset: offset.value }),
      });
      totalHint.value = total;
      if (initial) items.value = chunk;
      else items.value = items.value.concat(chunk);
      nextCursor.value = nc;
      offset.value += chunk.length;
      exhausted.value = !hasMore;
    } catch (e) {
      ElMessage.error(formatApiError(e));
    } finally {
      loading.value = false;
      loadingMore.value = false;
    }
    return;
  }

  const tab = homeTab.value;
  if (tab === "following" && !auth.isLoggedIn) {
    items.value = [];
    totalHint.value = 0;
    exhausted.value = true;
    return;
  }

  if (!initial && (loadingMore.value || exhausted.value)) return;
  if (initial) loading.value = true;
  else loadingMore.value = true;
  try {
    if (tab === "following") {
      const { items: chunk, hasMore, nextCursor: nc, total } = await videosApi.listVideosPaged({
        limit: pageLimit,
        followed_only: true,
        ...(nextCursor.value ? { cursor: nextCursor.value } : { offset: offset.value }),
      });
      totalHint.value = total;
      if (initial) items.value = chunk;
      else items.value = items.value.concat(chunk);
      nextCursor.value = nc;
      offset.value += chunk.length;
      exhausted.value = !hasMore;
    } else if (tab === "discover") {
      if (auth.isLoggedIn && algorithm.algorithmMode !== "personalized") {
        const page = Math.floor(offset.value / pageLimit) + 1;
        const { items: chunk, hasMore, total } = await videosApi.listFeedVideos({
          offset: offset.value,
          limit: pageLimit,
          page,
        });
        totalHint.value = total;
        if (initial) items.value = chunk;
        else items.value = items.value.concat(chunk);
        offset.value += chunk.length;
        exhausted.value = !hasMore || chunk.length === 0;
        return;
      }
      const { items: chunk, total } = await videosApi.listLatestVideos({
        offset: offset.value,
        limit: pageLimit,
      });
      totalHint.value = total;
      if (initial) items.value = chunk;
      else items.value = items.value.concat(chunk);
      offset.value += chunk.length;
      exhausted.value = offset.value >= total || chunk.length === 0;
    } else {
      const { items: chunk, total } = await videosApi.listTrendingVideos({
        offset: offset.value,
        limit: pageLimit,
      });
      totalHint.value = total;
      if (initial) items.value = chunk;
      else items.value = items.value.concat(chunk);
      offset.value += chunk.length;
      exhausted.value = offset.value >= total || chunk.length === 0;
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function onPageScroll() {
  const el = document.scrollingElement || document.documentElement;
  const near = el.scrollHeight - el.scrollTop - window.innerHeight < 280;
  if (near) void loadMore(false);
}

function openFeed(it: VideoListItem) {
  feedItem.value = it;
  feedOpen.value = true;
}

function setHomeTab(t: HomeTopTab) {
  homeTab.value = t;
  void resetAndLoad();
}

function onAlgorithmReset() {
  homeTab.value = "discover";
  void resetAndLoad();
}

onMounted(() => {
  window.addEventListener("scroll", onPageScroll, { passive: true });
  window.addEventListener(ALGORITHM_RESET_EVENT, onAlgorithmReset);
  void resetAndLoad();
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", onPageScroll);
  window.removeEventListener(ALGORITHM_RESET_EVENT, onAlgorithmReset);
});

watch(
  () => categoryId.value,
  () => {
    void resetAndLoad();
  },
);

watch(
  () => auth.isLoggedIn,
  () => {
    if (homeTab.value === "following") void resetAndLoad();
  },
);

watch(
  () => algorithm.algorithmMode,
  () => {
    if (homeTab.value === "discover") void resetAndLoad();
  },
);
</script>

<template>
  <div class="native-stack native-feed-root">
    <header class="xhs-top">
      <button type="button" class="xhs-icon-btn" aria-label="打开菜单" @click="drawerOpen = true">
        <span class="xhs-ico" aria-hidden="true">☰</span>
      </button>
      <div class="xhs-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          class="xhs-tab"
          :class="{ 'xhs-tab--on': homeTab === 'following' && !categoryId }"
          :aria-selected="homeTab === 'following' && !categoryId"
          @click="categoryId ? router.replace({ name: 'native-feed' }) : setHomeTab('following')"
        >
          关注
        </button>
        <button
          type="button"
          role="tab"
          class="xhs-tab"
          :class="{ 'xhs-tab--on': homeTab === 'discover' && !categoryId }"
          :aria-selected="homeTab === 'discover' && !categoryId"
          @click="categoryId ? router.replace({ name: 'native-feed' }) : setHomeTab('discover')"
        >
          发现
        </button>
        <button
          type="button"
          role="tab"
          class="xhs-tab"
          :class="{ 'xhs-tab--on': homeTab === 'explore' && !categoryId }"
          :aria-selected="homeTab === 'explore' && !categoryId"
          @click="categoryId ? router.replace({ name: 'native-feed' }) : setHomeTab('explore')"
        >
          探索
        </button>
      </div>
      <RouterLink class="xhs-icon-btn" :to="{ name: 'native-discover' }" aria-label="搜索与发现">
        <span class="xhs-ico" aria-hidden="true">⌕</span>
      </RouterLink>
    </header>

    <div v-if="homeTab === 'following' && !categoryId && !auth.isLoggedIn" class="xhs-login-hint">
      <span>登录后可查看关注作者的更新</span>
      <RouterLink class="xhs-login-hint__a" :to="{ name: 'auth', query: { redirect: '/feed' } }">去登录</RouterLink>
    </div>

    <div v-if="categoryId" class="native-chip-row native-feed__chips">
      <span class="native-feed__pill">已选分类</span>
      <button type="button" class="native-chip native-chip--on" @click="clearCategory">清除筛选</button>
    </div>

    <div v-if="showOriginHint" class="origin-hint">
      <span class="origin-hint__spark" aria-hidden="true">✦</span>
      <span>归源模式已开启：你正在随机、多元地重新探索世界。</span>
    </div>

    <section class="native-card native-feed-card xhs-feed-card">
      <div v-loading="loading" class="native-feed" :class="{ 'is-loading': loading }">
        <div class="native-feed__scroll">
          <div class="native-feed-grid xhs-grid">
            <article
              v-for="row in items"
              :key="row.id"
              class="native-feed-tile xhs-tile"
              role="button"
              tabindex="0"
              @click="openFeed(row)"
              @keydown.enter.prevent="openFeed(row)"
            >
              <div class="native-feed-tile__thumb xhs-thumb">
                <img
                  v-if="resolveApiAssetUrl(row.cover_url)"
                  class="native-feed-tile__img"
                  :src="resolveApiAssetUrl(row.cover_url)"
                  :alt="row.title ?? ''"
                  loading="lazy"
                />
                <div v-else class="native-feed-tile__img native-feed-tile__img--ph" aria-hidden="true" />
              </div>
              <div class="native-feed-tile__body xhs-body">
                <h3 class="native-feed-tile__title">{{ row.title || "（无标题）" }}</h3>
                <div class="xhs-foot">
                  <div class="xhs-metrics" aria-label="互动数据">
                    <span title="点赞">♡ {{ row.likes_count ?? 0 }}</span>
                    <span title="收藏">☆ {{ row.favorites_count ?? 0 }}</span>
                    <span title="评论">💬 {{ row.comments_count ?? 0 }}</span>
                  </div>
                </div>
                <div class="xhs-publine">
                  <span class="xhs-publine__label">作者：</span>
                  <button type="button" class="xhs-author-inline" @click.stop="openAuthor(row)">
                    {{ authorLabel(row) }}
                  </button>
                  <span class="xhs-publine__sep">·</span>
                  <span class="xhs-publine__views">{{ row.views_count ?? 0 }} 播放</span>
                </div>
                <div v-if="row.recommendation_text" class="xhs-reason">{{ row.recommendation_text }}</div>
              </div>
            </article>
          </div>

          <div v-if="loadingMore" class="native-feed__end">加载中…</div>
          <div v-else-if="exhausted && items.length" class="native-feed__end">已到底 · 共 {{ totalHint }} 条</div>
          <div v-else-if="!loading && !items.length" class="native-feed__end">
            {{ homeTab === "following" && !auth.isLoggedIn ? "登录后查看关注动态" : "暂无内容" }}
          </div>
        </div>
      </div>
    </section>

    <HomeImmersivePlayerOverlay v-model="feedOpen" :item="feedItem" />

    <Teleport to="body">
      <div v-show="drawerOpen" class="xhs-drawer-root" @keydown.escape.prevent="drawerOpen = false">
        <aside class="xhs-drawer" @click.stop>
          <div class="xhs-drawer-brand">恒频OM</div>
          <p class="xhs-drawer-sub">
            {{ auth.user?.username?.trim() ? `Hi，${auth.user.username}` : "访客" }}
          </p>
          <RouterLink class="xhs-drawer-link" :to="{ name: 'native-feed' }" @click="drawerOpen = false">首页</RouterLink>
          <RouterLink
            class="xhs-drawer-link"
            :to="auth.isLoggedIn ? { name: 'history' } : { name: 'auth', query: { redirect: '/me/history' } }"
            @click="drawerOpen = false"
          >
            历史记录
          </RouterLink>
          <RouterLink
            class="xhs-drawer-link"
            :to="auth.isLoggedIn ? { name: 'favorites' } : { name: 'auth', query: { redirect: '/me/favorites' } }"
            @click="drawerOpen = false"
          >
            个人收藏
          </RouterLink>
          <RouterLink
            class="xhs-drawer-link"
            :to="auth.isLoggedIn ? { name: 'messages' } : { name: 'auth', query: { redirect: '/me/messages' } }"
            @click="drawerOpen = false"
          >
            互动消息
          </RouterLink>
          <RouterLink class="xhs-drawer-link" :to="{ name: 'native-hub' }" @click="drawerOpen = false">个人中心</RouterLink>
        </aside>
        <button type="button" class="xhs-drawer-backdrop" aria-label="关闭菜单" @click="drawerOpen = false" />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.native-feed-root {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(circle at 16% -8%, rgba(34, 211, 238, 0.22), transparent 30%),
    radial-gradient(circle at 88% 12%, rgba(139, 92, 246, 0.18), transparent 34%),
    radial-gradient(circle at 50% 105%, rgba(14, 165, 233, 0.12), transparent 40%),
    #050506;
}

.native-feed-root::before,
.native-feed-root::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.native-feed-root::before {
  background-image:
    radial-gradient(circle, rgba(255, 255, 255, 0.42) 0 1px, transparent 1.4px),
    radial-gradient(circle, rgba(103, 232, 249, 0.28) 0 1px, transparent 1.6px);
  background-size: 72px 72px, 118px 118px;
  background-position: 8px 10px, 42px 56px;
  opacity: 0.28;
  mask-image: linear-gradient(to bottom, #000 0%, transparent 70%);
}

.native-feed-root::after {
  inset: 12% -30% auto 45%;
  height: 220px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.14), rgba(167, 139, 250, 0.16), transparent);
  filter: blur(10px);
  transform: rotate(-12deg);
}

.native-feed-root > * {
  position: relative;
  z-index: 1;
}

.xhs-top {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 4px 10px;
  border-bottom: 1px solid rgba(103, 232, 249, 0.12);
  border-radius: 0 0 22px 22px;
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.74), rgba(2, 6, 23, 0.22));
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.xhs-icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--native-text-primary);
  text-decoration: none;
  border-radius: 10px;
  -webkit-tap-highlight-color: transparent;
  cursor: pointer;
}

.xhs-icon-btn:active {
  opacity: 0.85;
}

.xhs-ico {
  font-size: 20px;
  line-height: 1;
  font-weight: 700;
}

.xhs-tabs {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 4px;
}

.xhs-tab {
  border: none;
  background: transparent;
  padding: 6px 12px 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

.xhs-tab--on {
  color: var(--native-text-primary);
  font-weight: 800;
}

.xhs-tab--on::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 22px;
  height: 3px;
  border-radius: 2px;
  background: var(--native-accent);
}

.xhs-login-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  font-size: 13px;
  background: var(--native-accent-dim);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.origin-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 4px 10px;
  padding: 10px 12px;
  border: 1px solid rgba(103, 232, 249, 0.2);
  border-radius: 16px;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.16), transparent 46%),
    rgba(15, 23, 42, 0.72);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 800;
}

.origin-hint__spark {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #06111f;
  background: linear-gradient(135deg, #67e8f9, #a78bfa);
  font-size: 13px;
}

.xhs-login-hint__a {
  font-weight: 800;
  color: var(--native-accent);
  text-decoration: none;
}

.xhs-feed-card {
  border: none;
  box-shadow: none;
  background: transparent;
}

.xhs-tile {
  position: relative;
}

.xhs-tile::before {
  content: "";
  position: absolute;
  inset: -1px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.12), rgba(167, 139, 250, 0.08), transparent 55%);
  opacity: 0.7;
  pointer-events: none;
}

.xhs-grid {
  gap: 10px 8px;
}

.xhs-thumb {
  aspect-ratio: 3 / 4;
}

.xhs-body {
  padding-top: 8px;
}

.xhs-foot {
  display: flex;
  align-items: center;
  justify-content: stretch;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.xhs-metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  min-width: 0;
  font-weight: 800;
  font-size: clamp(12px, 3.2vw, 14px);
  line-height: 1.15;
}

.xhs-metrics span {
  flex: 1 1 0;
  min-width: 0;
  white-space: nowrap;
  text-align: center;
}

.xhs-publine {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
}

.xhs-publine__label,
.xhs-publine__sep,
.xhs-publine__views {
  flex: 0 0 auto;
}

.xhs-reason {
  margin-top: 6px;
  padding: 6px 7px;
  border: 1px solid rgba(103, 232, 249, 0.14);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.42);
  color: #93c5fd;
  font-size: 10px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xhs-author-inline {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--native-accent);
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.is-loading {
  min-height: min(36vh, 320px);
}

.xhs-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  flex-direction: row;
}

.xhs-drawer-backdrop {
  flex: 1;
  border: none;
  margin: 0;
  padding: 0;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.45);
}

.xhs-drawer {
  width: 33.333vw;
  min-width: 108px;
  max-width: 188px;
  background: linear-gradient(180deg, var(--native-accent) 0%, #0891b2 100%);
  padding: 12px 9px;
  box-shadow: 4px 0 18px rgba(8, 145, 178, 0.26);
  overflow-y: auto;
  color: #fff;
}

.xhs-drawer-brand {
  font-size: clamp(15px, 4.1vw, 18px);
  font-weight: 900;
  color: #fff;
  margin-bottom: 5px;
  line-height: 1.15;
  word-break: keep-all;
}

.xhs-drawer-sub {
  margin: 0 0 14px;
  font-size: clamp(12px, 3.3vw, 14px);
  color: rgba(255, 255, 255, 0.78);
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xhs-drawer-link {
  display: block;
  padding: 10px 0;
  font-size: clamp(13px, 3.6vw, 15px);
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
  text-decoration: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.18);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.xhs-drawer-link:active {
  opacity: 0.88;
}
</style>
