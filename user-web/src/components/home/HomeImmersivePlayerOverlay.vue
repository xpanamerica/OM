<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, shallowRef, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import * as videosApi from "@/api/videos";
import type { VideoListItem } from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";
import { injectAliplayerCssOnce } from "@/util/aliplayerAssets";

const props = defineProps<{
  modelValue: boolean;
  item: VideoListItem | null;
}>();

const emit = defineEmits<{ "update:modelValue": [v: boolean] }>();

const router = useRouter();
const auth = useAuthStore();

const frameRef = ref<HTMLElement | null>(null);
let frameResizeObserver: ResizeObserver | null = null;

const loading = ref(false);
const bootError = ref("");
const localSrc = ref<string | null>(null);
const needLoginPlay = ref(false);
const isVod = ref(false);
const vodReady = ref(false);
const aliWrapId = ref(`home-ali-${Math.random().toString(36).slice(2, 10)}`);
const player = shallowRef<AliplayerInstance | null>(null);
let aliScriptLoaded = false;

const videoDetail = ref<videosApi.VideoDetail | null>(null);

const comments = ref<videosApi.CommentOut[]>([]);
const commentTotal = ref(0);
const my = ref<videosApi.MyInteractions | null>(null);
const likesCount = ref(0);
const favCount = ref(0);
const draftComment = ref("");
const commentSending = ref(false);

/** 底部分区：简介 / 评论（模板式上滑面板） */
const sheetOpen = ref(false);
const sheetTab = ref<"intro" | "comments">("intro");

/** 作者「⋯」菜单：修改标题简介 */
const editMetaVisible = ref(false);
const editSaving = ref(false);
const editForm = reactive({ title: "", description: "" });

const titleText = computed(() => props.item?.title ?? "（无标题）");

const isOwner = computed(() => {
  const uid = auth.user?.id?.trim();
  const aid = props.item?.author_id?.trim();
  return Boolean(auth.isLoggedIn && uid && aid && uid === aid);
});

const videoStatus = computed(() => videoDetail.value?.status ?? props.item?.status ?? "");

const canOfflineOwn = computed(() => isOwner.value && videoStatus.value === "published");

/** 后端仅允许对 published 视频评论 */
const canCommentOnVideo = computed(() => (videoStatus.value || props.item?.status || "").trim() === "published");

const fullDescription = computed(() =>
  (videoDetail.value?.description ?? props.item?.description ?? "").trim(),
);

const needsMoreIntro = computed(
  () => fullDescription.value.length > 44 || /\n/.test(fullDescription.value),
);

const commentsNewestFirst = computed(() => {
  const a = comments.value;
  if (a.length <= 1) return a;
  return [...a].reverse();
});

function close() {
  sheetOpen.value = false;
  emit("update:modelValue", false);
}

function resolveStreamUrl(url: string): string {
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return resolveApiAssetUrl(url) ?? url;
}

function injectAliplayerScriptOnce(): Promise<void> {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://g.alicdn.com/de/prismplayer/2.15.2/aliplayer-min.js";
    s.onload = () => {
      aliScriptLoaded = true;
      resolve();
    };
    s.onerror = () => reject(new Error("播放器脚本加载失败"));
    document.body.appendChild(s);
  });
}

async function loadAliplayerScript(retries = 2): Promise<void> {
  if (aliScriptLoaded || window.Aliplayer) {
    aliScriptLoaded = true;
    return;
  }
  try {
    await injectAliplayerScriptOnce();
  } catch (e) {
    if (retries <= 1) throw e;
    await new Promise((r) => setTimeout(r, 900));
    await loadAliplayerScript(retries - 1);
  }
}

function disconnectFrameObserver() {
  if (frameResizeObserver && frameRef.value) {
    try {
      frameResizeObserver.unobserve(frameRef.value);
    } catch {
      /* ignore */
    }
  }
  frameResizeObserver?.disconnect();
  frameResizeObserver = null;
}

function syncAliSizeToFrame() {
  const el = frameRef.value;
  const p = player.value;
  if (!el || !p?.setPlayerSize) return;
  const w = Math.max(160, el.clientWidth);
  const h = Math.max(200, el.clientHeight);
  try {
    p.setPlayerSize(w, h);
  } catch {
    /* ignore */
  }
}

function bindFrameResizeObserver() {
  disconnectFrameObserver();
  const el = frameRef.value;
  if (!el || typeof ResizeObserver === "undefined") return;
  frameResizeObserver = new ResizeObserver(() => syncAliSizeToFrame());
  frameResizeObserver.observe(el);
}

function destroyPlayer() {
  disconnectFrameObserver();
  try {
    player.value?.dispose?.();
  } catch {
    /* ignore */
  }
  player.value = null;
  vodReady.value = false;
  isVod.value = false;
}

function resetState() {
  sheetOpen.value = false;
  sheetTab.value = "intro";
  editMetaVisible.value = false;
  bootError.value = "";
  localSrc.value = null;
  needLoginPlay.value = false;
  videoDetail.value = null;
  destroyPlayer();
  comments.value = [];
  commentTotal.value = 0;
  my.value = null;
  likesCount.value = props.item?.likes_count ?? 0;
  favCount.value = props.item?.favorites_count ?? 0;
  draftComment.value = "";
}

function lockBody(lock: boolean) {
  if (typeof document === "undefined") return;
  document.body.style.overflow = lock ? "hidden" : "";
}

function goAuth() {
  void router.push({ name: "auth", query: { redirect: "/" } });
}

async function loadVideoDetail() {
  if (!props.item) return;
  try {
    videoDetail.value = await videosApi.getVideo(props.item.id);
  } catch {
    videoDetail.value = null;
  }
}

async function loadInteractions() {
  if (!props.item) return;
  likesCount.value = props.item.likes_count ?? 0;
  favCount.value = props.item.favorites_count ?? 0;
  if (!auth.isLoggedIn) {
    my.value = null;
    return;
  }
  try {
    const m = await videosApi.getMyInteractions(props.item.id);
    my.value = m;
  } catch {
    my.value = null;
  }
}

async function loadComments() {
  if (!props.item) return;
  try {
    const { items, total } = await videosApi.listComments(props.item.id, { limit: 80, offset: 0 });
    comments.value = items;
    commentTotal.value = total;
  } catch (e) {
    comments.value = [];
    commentTotal.value = 0;
    ElMessage.error(formatApiError(e));
  }
}

async function bootPlayback() {
  if (!props.item) return;
  needLoginPlay.value = false;
  localSrc.value = null;
  destroyPlayer();
  bootError.value = "";
  if (!auth.isLoggedIn) {
    needLoginPlay.value = true;
    return;
  }
  try {
    const p = await videosApi.getVideoPlay(props.item.id);
    if (p.playback_mode === "local" && p.stream_url) {
      localSrc.value = resolveStreamUrl(p.stream_url);
      void videosApi.postViewRecord(props.item.id, { progress_seconds: 0 }).catch(() => {});
      return;
    }
    if (p.vod_video_id && p.play_auth) {
      isVod.value = true;
      await injectAliplayerCssOnce();
      await loadAliplayerScript();
      const AP = window.Aliplayer;
      if (!AP) throw new Error("Aliplayer 不可用");
      await nextTick();
      const el = frameRef.value;
      const h = el ? Math.max(240, el.clientHeight) : 640;
      player.value = new AP({
        id: aliWrapId.value,
        vid: p.vod_video_id,
        playauth: p.play_auth,
        width: "100%",
        height: `${h}px`,
      });
      vodReady.value = true;
      bindFrameResizeObserver();
      syncAliSizeToFrame();
      void videosApi.postViewRecord(props.item.id, { progress_seconds: 0 }).catch(() => {});
      return;
    }
    bootError.value = "暂无可播媒资";
  } catch (e) {
    bootError.value = formatApiError(e);
  }
}

async function openSession() {
  if (!props.item) return;
  loading.value = true;
  resetState();
  try {
    if (auth.isLoggedIn && !auth.user) {
      try {
        await auth.fetchMe();
      } catch {
        /* ignore */
      }
    }
    await Promise.all([loadVideoDetail(), loadInteractions(), loadComments(), bootPlayback()]);
    await nextTick();
    if (vodReady.value) {
      bindFrameResizeObserver();
      syncAliSizeToFrame();
    }
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.modelValue, props.item?.id] as const,
  ([open]) => {
    if (open && props.item) {
      lockBody(true);
      void openSession();
    } else {
      lockBody(false);
      destroyPlayer();
      localSrc.value = null;
    }
  },
);

onBeforeUnmount(() => {
  lockBody(false);
  destroyPlayer();
});

function openIntroSheet() {
  sheetTab.value = "intro";
  sheetOpen.value = true;
}

function openCommentsSheet() {
  sheetTab.value = "comments";
  sheetOpen.value = true;
}

function closeSheet() {
  sheetOpen.value = false;
}

function goDetail() {
  if (!props.item) return;
  const id = props.item.id;
  close();
  void router.push({ name: "video-detail", params: { id } });
}

function openEditMetaDialog() {
  if (!props.item) return;
  editForm.title = (videoDetail.value?.title ?? props.item.title ?? "").trim() || (props.item.title ?? "");
  editForm.description = (videoDetail.value?.description ?? props.item?.description ?? "").trim();
  editMetaVisible.value = true;
}

async function saveEditMeta() {
  if (!props.item) return;
  const title = editForm.title.trim();
  if (!title) {
    ElMessage.warning("标题不能为空");
    return;
  }
  editSaving.value = true;
  try {
    const v = await videosApi.patchVideo(props.item.id, {
      title,
      description: editForm.description.trim() || null,
    });
    videoDetail.value = v;
    editMetaVisible.value = false;
    ElMessage.success("已保存");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    editSaving.value = false;
  }
}

function goReplaceCoverVideo() {
  goDetail();
}

function currentShareUrl(): string {
  if (!props.item || typeof window === "undefined") return "";
  const path = router.resolve({ name: "video-detail", params: { id: props.item.id } }).href;
  return `${window.location.origin}${path}`;
}

async function copyShareLink() {
  const url = currentShareUrl();
  if (!url) return;
  try {
    await navigator.clipboard.writeText(url);
    ElMessage.success("链接已复制");
  } catch {
    ElMessage.error("复制失败，请手动复制浏览器地址栏链接");
  }
}

async function shareToFriend() {
  const url = currentShareUrl();
  if (!url) return;
  const shareApi = navigator as Navigator & {
    share?: (data: { title?: string; text?: string; url?: string }) => Promise<void>;
  };
  if (shareApi.share) {
    try {
      await shareApi.share({ title: titleText.value, text: titleText.value, url });
      return;
    } catch {
      /* 用户取消或系统分享不可用时回退复制链接 */
    }
  }
  await copyShareLink();
}

async function shareToTimeline() {
  await copyShareLink();
  ElMessage.success("作品链接已复制，可粘贴到动态发布");
}

function saveSharePosterHint() {
  ElMessage.info("分享图功能即将开放；当前可先复制链接分享。");
}

function goWorkStatsHint() {
  ElMessage.info("作品数据即将开放；播放量与点赞可在当前页查看。");
}

function goVisibilityHint() {
  ElMessage.info("审核状态与可见范围请在「作品管理」中查看。");
  goDetail();
}

async function confirmOfflineOwn() {
  if (!props.item || !canOfflineOwn.value) return;
  try {
    await ElMessageBox.confirm(
      "下架后他人将无法在公开列表中看到本作品，确定要下架吗？",
      "下架作品",
      { type: "warning", confirmButtonText: "下架", cancelButtonText: "取消" },
    );
    const v = await videosApi.patchVideo(props.item.id, { status: "offline" });
    videoDetail.value = v;
    ElMessage.success("已从公开列表下架");
    close();
    void router.push({ path: "/" });
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  }
}

async function onLike() {
  if (!props.item) return;
  if (!auth.isLoggedIn) {
    goAuth();
    return;
  }
  try {
    if (my.value?.liked) {
      const o = await videosApi.unlikeVideo(props.item.id);
      likesCount.value = o.likes_count;
      my.value = { liked: false, favorited: my.value?.favorited ?? false };
    } else {
      const o = await videosApi.likeVideo(props.item.id);
      likesCount.value = o.likes_count;
      my.value = { liked: true, favorited: my.value?.favorited ?? false };
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function onFavorite() {
  if (!props.item) return;
  if (!auth.isLoggedIn) {
    goAuth();
    return;
  }
  try {
    if (my.value?.favorited) {
      const o = await videosApi.unfavoriteVideo(props.item.id);
      favCount.value = o.favorites_count;
      my.value = { liked: my.value?.liked ?? false, favorited: false };
    } else {
      const o = await videosApi.favoriteVideo(props.item.id);
      favCount.value = o.favorites_count;
      my.value = { liked: my.value?.liked ?? false, favorited: true };
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function sendComment() {
  const t = draftComment.value.trim();
  if (!props.item || !t) return;
  if (!auth.isLoggedIn) {
    goAuth();
    return;
  }
  if (!canCommentOnVideo.value) {
    ElMessage.warning("仅已发布作品可评论");
    return;
  }
  commentSending.value = true;
  try {
    await videosApi.postComment(props.item.id, t);
    draftComment.value = "";
    ElMessage.success("已发送");
    await loadComments();
    sheetTab.value = "comments";
    sheetOpen.value = true;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    commentSending.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue && item" class="imm" role="dialog" aria-modal="true" aria-label="视频播放">
      <header class="imm__topbar">
        <button type="button" class="imm__x" aria-label="关闭" @click="close">×</button>
        <div class="imm__top-actions">
          <el-dropdown trigger="click" placement="bottom-end" popper-class="imm-owner-dd">
            <button type="button" class="imm__share" aria-haspopup="menu" aria-label="分享">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14"
                />
              </svg>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="shareToFriend">发送给好友</el-dropdown-item>
                <el-dropdown-item @click="shareToTimeline">分享到动态</el-dropdown-item>
                <el-dropdown-item @click="copyShareLink">复制作品链接</el-dropdown-item>
                <el-dropdown-item @click="saveSharePosterHint">保存分享图</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-dropdown
            v-if="isOwner"
            trigger="click"
            placement="bottom-end"
            popper-class="imm-owner-dd"
          >
            <button type="button" class="imm__dots" aria-haspopup="menu" aria-label="更多">⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled class="imm-dd-head">编辑</el-dropdown-item>
                <el-dropdown-item @click="openEditMetaDialog">修改标题和简介</el-dropdown-item>
                <el-dropdown-item @click="goReplaceCoverVideo">更换封面与视频</el-dropdown-item>
                <el-dropdown-item divided disabled class="imm-dd-head">作品</el-dropdown-item>
                <el-dropdown-item @click="goWorkStatsHint">作品数据</el-dropdown-item>
                <el-dropdown-item @click="goDetail">作品管理</el-dropdown-item>
                <el-dropdown-item @click="goVisibilityHint">权限与可见性</el-dropdown-item>
                <el-dropdown-item v-if="canOfflineOwn" divided @click="confirmOfflineOwn">下架作品</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <el-dialog
        v-model="editMetaVisible"
        title="修改标题和简介"
        width="92%"
        append-to-body
        destroy-on-close
        class="imm-edit-dialog"
        :z-index="5200"
        @closed="editSaving = false"
      >
        <div class="imm-edit-fields">
          <label class="imm-edit-label">标题</label>
          <el-input v-model="editForm.title" maxlength="512" show-word-limit placeholder="标题" />
          <label class="imm-edit-label">简介</label>
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="5"
            maxlength="2000"
            show-word-limit
            placeholder="作品简介（可选）"
          />
        </div>
        <template #footer>
          <el-button @click="editMetaVisible = false">取消</el-button>
          <el-button type="primary" :loading="editSaving" @click="saveEditMeta">保存</el-button>
        </template>
      </el-dialog>

      <!-- 上：竖屏 9:16 视频区铺满 -->
      <div v-loading="loading" class="imm__stage">
        <p v-if="bootError && !localSrc && !vodReady && !needLoginPlay" class="imm__err">{{ bootError }}</p>

        <div v-if="needLoginPlay" class="imm__gate imm__gate--stage">
          <p class="imm__gate-t">登录后即可播放全片</p>
          <button type="button" class="imm__btn imm__btn--pri" @click="goAuth">去登录</button>
        </div>

        <div ref="frameRef" class="imm__frame916">
          <video
            v-if="localSrc"
            class="imm__vid"
            controls
            playsinline
            preload="metadata"
            crossorigin="anonymous"
            :src="localSrc"
          />
          <div v-show="isVod" :id="aliWrapId" class="imm__ali" />
        </div>
      </div>

      <!-- 下：简介（截断）+ 输入 + 点赞 / 评论 / 收藏 -->
      <footer class="imm__dock safe-bottom">
        <div class="imm__dock-top">
          <h2 class="imm__title">{{ titleText }}</h2>
          <div v-if="fullDescription" class="imm__intro-block">
            <p class="imm__desc imm__desc--clamp">{{ fullDescription }}</p>
            <button v-if="needsMoreIntro" type="button" class="imm__more" @click="openIntroSheet">more</button>
          </div>
          <p v-else class="imm__desc imm__desc--muted">暂无简介</p>
        </div>

        <div v-if="auth.isLoggedIn" class="imm__compose">
          <input
            v-model="draftComment"
            class="imm__input"
            type="text"
            maxlength="2000"
            placeholder="说点什么…"
            enterkeyhint="send"
            :disabled="!canCommentOnVideo"
            @keyup.enter="sendComment"
          />
          <button
            type="button"
            class="imm__send"
            :disabled="!canCommentOnVideo || commentSending || !draftComment.trim()"
            @click="sendComment"
          >
            {{ commentSending ? "…" : "发送" }}
          </button>
        </div>
        <button v-else type="button" class="imm__btn imm__btn--ghost full" @click="goAuth">登录后评论</button>
        <p v-if="auth.isLoggedIn && !canCommentOnVideo" class="imm__hint">当前状态不可评论（仅已发布作品开放评论）</p>

        <div class="imm__actions">
          <button type="button" class="imm__act" :class="{ 'imm__act--on': my?.liked }" :aria-label="my?.liked ? '已赞' : '点赞'" @click="onLike">
            <svg class="imm__act-ico" viewBox="0 0 24 24" aria-hidden="true">
              <path
                :fill="my?.liked ? 'currentColor' : 'none'"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78Z"
              />
            </svg>
            <span class="imm__act-n">{{ likesCount }}</span>
          </button>
          <button type="button" class="imm__act" :class="{ 'imm__act--on': my?.favorited }" :aria-label="my?.favorited ? '已收藏' : '收藏'" @click="onFavorite">
            <svg class="imm__act-ico" viewBox="0 0 24 24" aria-hidden="true">
              <path
                :fill="my?.favorited ? 'currentColor' : 'none'"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="m12 2 2.9 6.1L21 11l-6.1 2.9L12 20l-2.9-6.1L3 11l6.1-2.9L12 2Z"
              />
            </svg>
            <span class="imm__act-n">{{ favCount }}</span>
          </button>
          <button type="button" class="imm__act" aria-label="评论" @click="openCommentsSheet">
            <svg class="imm__act-ico" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5Z"
              />
            </svg>
            <span class="imm__act-n">{{ commentTotal }}</span>
          </button>
        </div>
      </footer>

      <!-- 底部分频：简介 / 评论 -->
      <Transition name="imm-sheet">
        <div v-if="sheetOpen" class="imm__sheet-back" role="presentation" @click.self="closeSheet">
          <div class="imm__sheet" @click.stop>
            <div class="imm__sheet-handle" aria-hidden="true" />
            <div class="imm__sheet-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                :aria-selected="sheetTab === 'intro'"
                :class="['imm__tab', { 'imm__tab--on': sheetTab === 'intro' }]"
                @click="sheetTab = 'intro'"
              >
                简介
              </button>
              <button
                type="button"
                role="tab"
                :aria-selected="sheetTab === 'comments'"
                :class="['imm__tab', { 'imm__tab--on': sheetTab === 'comments' }]"
                @click="sheetTab = 'comments'"
              >
                评论 · {{ commentTotal }}
              </button>
            </div>
            <div class="imm__sheet-body">
              <div v-show="sheetTab === 'intro'" class="imm__sheet-pane">
                <p v-if="fullDescription" class="imm__intro-full">{{ fullDescription }}</p>
                <p v-else class="imm__desc imm__desc--muted">作者未填写简介</p>
              </div>
              <div v-show="sheetTab === 'comments'" class="imm__sheet-pane imm__sheet-pane--scroll">
                <template v-if="auth.isLoggedIn">
                  <div class="imm__sheet-compose">
                    <input
                      v-model="draftComment"
                      class="imm__sheet-input"
                      type="text"
                      maxlength="2000"
                      placeholder="写评论…"
                      enterkeyhint="send"
                      :disabled="!canCommentOnVideo"
                      @keyup.enter="sendComment"
                    />
                    <button
                      type="button"
                      class="imm__sheet-send"
                      :disabled="!canCommentOnVideo || commentSending || !draftComment.trim()"
                      @click="sendComment"
                    >
                      {{ commentSending ? "…" : "发送" }}
                    </button>
                  </div>
                  <p v-if="!canCommentOnVideo" class="imm__sheet-note">当前状态不可评论（仅已发布作品开放）</p>
                </template>
                <button v-else type="button" class="imm__sheet-auth" @click="goAuth">登录后参与评论</button>
                <div v-if="!comments.length" class="imm__comments-empty">暂无评论</div>
                <div v-for="c in commentsNewestFirst" :key="c.id" class="imm__c-line">{{ c.content }}</div>
              </div>
            </div>
            <button type="button" class="imm__sheet-close" aria-label="收起" @click="closeSheet">收起</button>
          </div>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<style scoped>
.imm {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: #050506;
  color: #f3f4f6;
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-height: 100dvh;
  padding: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.imm__topbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(8px + env(safe-area-inset-top, 0px)) 10px 6px;
  box-sizing: border-box;
  pointer-events: none;
}

.imm__topbar > * {
  pointer-events: auto;
}

.imm__x {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
}

.imm__top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  pointer-events: auto;
}

.imm__dots,
.imm__share {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  font-size: 22px;
  line-height: 1;
  letter-spacing: 0.02em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0 6px;
  flex-shrink: 0;
}

.imm__share {
  padding: 0;
}

.imm__share svg {
  width: 21px;
  height: 21px;
  display: block;
}

.imm-edit-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.imm-edit-label {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
}

/* 上区：9:16 竖屏铺满（在可用高度内最大内接） */
.imm__stage {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: calc(48px + env(safe-area-inset-top, 0px)) 0 6px;
  box-sizing: border-box;
  background: radial-gradient(ellipse at center, #111827 0%, #050506 70%);
}

.imm__err {
  position: absolute;
  top: 52px;
  left: 12px;
  right: 12px;
  z-index: 2;
  color: #fca5a5;
  font-size: 13px;
  text-align: center;
}

.imm__gate--stage {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(5, 5, 6, 0.72);
}
.imm__gate-t {
  margin: 0 0 12px;
  font-size: 15px;
}

/* 竖屏 9:16：在可用高度与屏宽内取最大内接矩形（模板式铺满） */
.imm__frame916 {
  position: relative;
  aspect-ratio: 9 / 16;
  height: min(calc(100dvh - 200px), calc(100vw * 16 / 9));
  width: auto;
  max-width: 100vw;
  max-height: calc(100dvh - 200px);
  margin: 0 auto;
  border-radius: 14px;
  overflow: hidden;
  background: #000;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
}

.imm__vid {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  background: #000;
}

.imm__ali {
  width: 100%;
  height: 100%;
  min-height: 200px;
}

/* 下区：底栏 */
.imm__dock {
  flex: 0 0 auto;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding: 10px max(12px, env(safe-area-inset-left, 0px)) calc(12px + env(safe-area-inset-bottom, 0px))
    max(12px, env(safe-area-inset-right, 0px));
  box-sizing: border-box;
  overflow-x: hidden;
  background: linear-gradient(180deg, rgba(5, 5, 6, 0) 0%, rgba(17, 24, 39, 0.97) 28%, #111827 100%);
  border-top: 1px solid rgba(51, 65, 85, 0.55);
}

.safe-bottom {
  padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
}

.imm__dock-top {
  margin-bottom: 8px;
}

.imm__title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-word;
}

.imm__intro-block {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 10px;
  align-items: start;
}

.imm__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #cbd5e1;
  word-break: break-word;
  white-space: pre-wrap;
}

.imm__desc--clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.imm__desc--muted {
  color: #64748b;
  font-size: 13px;
}

.imm__more {
  grid-column: 2;
  grid-row: 1;
  align-self: end;
  border: none;
  background: none;
  color: var(--el-color-primary, #60a5fa);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 0;
  white-space: nowrap;
}

.imm__compose {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin-bottom: 10px;
}

.imm__input {
  min-width: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.75);
  color: #f8fafc;
  padding: 10px 14px;
  font-size: 14px;
  margin-bottom: 0;
}

.imm__input:disabled {
  opacity: 0.55;
}

.imm__send {
  justify-self: end;
  border: none;
  border-radius: 999px;
  padding: 10px 12px;
  min-width: 3.25rem;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.imm__send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.imm__hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

.imm__sheet-compose {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin-bottom: 12px;
  position: sticky;
  top: 0;
  z-index: 1;
  padding-bottom: 8px;
  background: linear-gradient(180deg, #0f172a 0%, #0f172a 88%, transparent 100%);
}

.imm__sheet-input {
  min-width: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  padding: 10px 10px;
  font-size: 14px;
}

.imm__sheet-input:disabled {
  opacity: 0.55;
}

.imm__sheet-send {
  justify-self: end;
  border: none;
  border-radius: 12px;
  padding: 0 12px;
  min-width: 3.25rem;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.imm__sheet-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.imm__sheet-note {
  margin: 0 0 10px;
  font-size: 12px;
  color: #94a3b8;
}

.imm__sheet-auth {
  width: 100%;
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(30, 41, 59, 0.6);
  color: #e2e8f0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.imm__actions {
  display: flex;
  justify-content: space-around;
  gap: 8px;
}

.imm__act {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 10px 6px;
  border: none;
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.85);
  color: #e2e8f0;
  cursor: pointer;
  font-size: 13px;
}

.imm__act--on {
  color: #67e8f9;
}

.imm__act-ico {
  width: 24px;
  height: 24px;
  display: block;
}
.imm__act-n {
  font-size: 12px;
  opacity: 0.85;
}

.imm__btn {
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: transparent;
  color: #e2e8f0;
}
.imm__btn--pri {
  background: var(--el-color-primary, #409eff);
  border-color: var(--el-color-primary, #409eff);
  color: #fff;
}
.imm__btn--ghost {
  background: rgba(30, 41, 59, 0.6);
}
.imm__btn.full {
  width: 100%;
  margin-bottom: 10px;
}

/* 底部分频面板 */
.imm__sheet-back {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.imm__sheet {
  width: 100%;
  max-width: 100%;
  max-height: min(78dvh, 640px);
  background: #0f172a;
  border-radius: 16px 16px 0 0;
  padding: 8px max(12px, env(safe-area-inset-right, 0px)) calc(14px + env(safe-area-inset-bottom, 0px))
    max(12px, env(safe-area-inset-left, 0px));
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  border-top: 1px solid rgba(71, 85, 105, 0.6);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.35);
  overflow-x: hidden;
  align-self: stretch;
}

.imm__sheet-handle {
  width: 36px;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.45);
  margin: 4px auto 10px;
}

.imm__sheet-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  min-width: 0;
  max-width: 100%;
}

.imm__tab {
  flex: 1 1 0;
  min-width: 0;
  padding: 10px 8px;
  border-radius: 10px;
  border: 1px solid rgba(71, 85, 105, 0.65);
  background: rgba(30, 41, 59, 0.5);
  color: #94a3b8;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.imm__tab--on {
  color: #f8fafc;
  border-color: color-mix(in srgb, var(--el-color-primary, #409eff) 55%, transparent);
  background: color-mix(in srgb, var(--el-color-primary, #409eff) 18%, rgba(15, 23, 42, 0.9));
}

.imm__sheet-body {
  flex: 1;
  min-height: 0;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.imm__sheet-pane {
  min-height: 120px;
  max-height: min(52dvh, 420px);
  overflow-y: auto;
  overflow-x: hidden;
  max-width: 100%;
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
  font-size: 14px;
  line-height: 1.55;
  color: #e2e8f0;
}

.imm__sheet-pane--scroll {
  padding-right: 2px;
}

.imm__intro-full {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.imm__comments-empty {
  opacity: 0.65;
  padding: 12px 0;
  font-size: 14px;
}

.imm__c-line {
  padding: 10px 0;
  border-bottom: 1px solid rgba(51, 65, 85, 0.55);
  word-break: break-word;
}

.imm__sheet-close {
  margin-top: 12px;
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: rgba(51, 65, 85, 0.55);
  color: #e2e8f0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.imm-sheet-enter-active,
.imm-sheet-leave-active {
  transition: opacity 0.22s ease;
}
.imm-sheet-enter-active .imm__sheet,
.imm-sheet-leave-active .imm__sheet {
  transition: transform 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}
.imm-sheet-enter-from,
.imm-sheet-leave-to {
  opacity: 0;
}
.imm-sheet-enter-from .imm__sheet,
.imm-sheet-leave-to .imm__sheet {
  transform: translateY(100%);
}
.imm-sheet-enter-to .imm__sheet,
.imm-sheet-leave-from .imm__sheet {
  transform: translateY(0);
}
</style>

<style>
/* 下拉挂在 body，须高于全屏播放层 z-index */
.imm-owner-dd.el-popper {
  z-index: 5000 !important;
}
.imm-owner-dd .el-dropdown-menu {
  min-width: 232px;
  padding: 6px 0;
}
.imm-owner-dd .imm-dd-head {
  font-size: 11px !important;
  font-weight: 700 !important;
  color: #64748b !important;
  letter-spacing: 0.06em;
  cursor: default !important;
  background: transparent !important;
}
.imm-owner-dd .el-dropdown-menu__item:not(.is-disabled) {
  font-size: 14px;
}
</style>
