<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ElMessage, ElMessageBox } from "@/util/elementPlusMessage";
import axios from "axios";
import { useAuthStore } from "@/stores/auth";
import { useIsMobile } from "@/composables/useIsMobile";
import H5BackLink from "@/components/H5BackLink.vue";
import * as videosApi from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { imageFileToJpegFile } from "@/util/imageToJpegFile";
import { injectAliplayerCssOnce } from "@/util/aliplayerAssets";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { isMobile } = useIsMobile();

const VideoCommentsDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/VideoCommentsDesktopTable.vue"),
);

const videoId = computed(() => String(route.params.id));

const loading = ref(true);
const videoNotFound = ref(false);
const video = ref<videosApi.VideoDetail | null>(null);
const concepts = ref<videosApi.VideoConceptPublic[]>([]);
const comments = ref<videosApi.CommentOut[]>([]);
const commentTotal = ref(0);
const my = ref<videosApi.MyInteractions | null>(null);

const playLoading = ref(false);
const playInfo = ref<videosApi.VideoPlayResponse | null>(null);
const localPlaySrc = ref<string | null>(null);
let localProgressLastSent = 0;
const player = shallowRef<AliplayerInstance | null>(null);
let progressTimer: ReturnType<typeof setInterval> | null = null;
let aliScriptLoaded = false;

const newComment = ref("");
const commentLoading = ref(false);

const likesCount = ref(0);
const favCount = ref(0);

const attachmentUploading = ref(false);
const attachDetailInputRef = ref<HTMLInputElement | null>(null);
const localVideoDetailInputRef = ref<HTMLInputElement | null>(null);
const localVideoUploading = ref(false);
const coverDetailInputRef = ref<HTMLInputElement | null>(null);
const coverDetailUploading = ref(false);

const isVideoAuthor = computed(
  () => Boolean(auth.isLoggedIn && video.value && auth.user?.id === video.value.author_id),
);

const VIDEO_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已发布",
  rejected: "已驳回",
  offline: "已下架",
};

const videoStatusLabel = computed(() => {
  const s = video.value?.status;
  return s ? VIDEO_STATUS_LABEL[s] ?? s : "";
});
const canPreviewVideo = computed(() => {
  const st = video.value?.status;
  if (!st) return false;
  return st === "published" || (isVideoAuthor.value && ["draft", "pending_review", "rejected", "offline"].includes(st));
});
const coverUrl = computed(() => resolveApiAssetUrl(video.value?.cover_url || ""));
const titleInitial = computed(() => (video.value?.title?.trim()?.slice(0, 1).toUpperCase() || "OM"));

/** 与后端一致：仅 published 可评论 */
const canCommentOnThisVideo = computed(() => video.value?.status === "published");

async function maybeAutoSubmitDraft() {
  if (!video.value || !isVideoAuthor.value || video.value.status !== "draft") return;
  try {
    const v = await videosApi.submitVideoForReview(videoId.value);
    video.value = v;
    ElMessage.success("已自动提交审核");
  } catch {
    /* 已待审或状态不允许时忽略 */
  }
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

/** CDN 偶发抖动时自动重试一次，降低「脚本加载失败」误报 */
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

function clearProgressTimer() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

function clearLocalPlayback() {
  localPlaySrc.value = null;
  localProgressLastSent = 0;
}

function destroyPlayer() {
  clearProgressTimer();
  try {
    player.value?.dispose?.();
  } catch {
    /* ignore */
  }
  player.value = null;
}

function onLocalVideoTimeupdate(ev: Event) {
  const el = ev.target as HTMLVideoElement;
  const t = el.currentTime;
  if (t - localProgressLastSent < 14) return;
  localProgressLastSent = t;
  void reportProgress(t);
}

async function reportProgress(seconds: number) {
  if (!auth.isLoggedIn || video.value?.status !== "published") return;
  try {
    await videosApi.postViewRecord(videoId.value, { progress_seconds: Math.max(0, Math.floor(seconds)) });
  } catch {
    /* ignore */
  }
}

function viewportWidth(): number {
  if (typeof window === "undefined") return 360;
  return Math.round(window.visualViewport?.width ?? window.innerWidth);
}

function aliPlayerHeightPx(): string {
  if (typeof window === "undefined") return "480px";
  if (!window.matchMedia("(max-width: 767px)").matches) return "480px";
  const w = Math.min(Math.max(viewportWidth() - 32, 280), 720);
  return `${Math.max(200, Math.round((w * 9) / 16))}px`;
}

let resizeDebounce: ReturnType<typeof setTimeout> | null = null;

/** 竖屏旋转、地址栏显隐后同步播放器尺寸（SDK 支持时） */
function scheduleResizePlayer() {
  if (resizeDebounce) clearTimeout(resizeDebounce);
  resizeDebounce = setTimeout(() => {
    resizeDebounce = null;
    const p = player.value;
    if (!p?.setPlayerSize) return;
    try {
      p.setPlayerSize("100%", aliPlayerHeightPx());
    } catch {
      /* ignore */
    }
  }, 200);
}

function bindPlayerResizeListeners() {
  window.addEventListener("resize", scheduleResizePlayer, { passive: true });
  window.addEventListener("orientationchange", scheduleResizePlayer, { passive: true } as AddEventListenerOptions);
  window.visualViewport?.addEventListener("resize", scheduleResizePlayer, { passive: true });
}

function unbindPlayerResizeListeners() {
  window.removeEventListener("resize", scheduleResizePlayer);
  window.removeEventListener("orientationchange", scheduleResizePlayer);
  window.visualViewport?.removeEventListener("resize", scheduleResizePlayer);
  if (resizeDebounce) {
    clearTimeout(resizeDebounce);
    resizeDebounce = null;
  }
}

async function startPlayback() {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    ElMessage.warning("当前网络离线，请连接网络后再试播放");
    return;
  }
  if (!auth.isLoggedIn) {
    ElMessage.warning("请先登录后再播放");
    return;
  }
  const st = video.value?.status;
  const authorMayPreview =
    isVideoAuthor.value &&
    !!st &&
    st !== "published" &&
    (st === "draft" || st === "pending_review" || st === "rejected" || st === "offline");
  if (st !== "published" && !authorMayPreview) {
    ElMessage.info("仅已发布视频对访客开放播放");
    return;
  }
  clearLocalPlayback();
  destroyPlayer();
  playLoading.value = true;
  try {
    const p = await videosApi.getVideoPlay(videoId.value);
    playInfo.value = p;
    if (p.playback_mode === "local" && p.stream_url) {
      localPlaySrc.value = p.stream_url;
      void reportProgress(0);
      return;
    }
    if (!p.vod_video_id || !p.play_auth) {
      throw new Error("暂无可播媒资：请先在创作页上传本站视频或绑定阿里云点播");
    }
    await injectAliplayerCssOnce();
    await loadAliplayerScript();
    const AP = window.Aliplayer;
    if (!AP) throw new Error("Aliplayer 不可用");
    await new Promise((r) => setTimeout(r, 50));
    player.value = new AP({
      id: "ali-player-wrap",
      vid: p.vod_video_id,
      playauth: p.play_auth,
      width: "100%",
      height: aliPlayerHeightPx(),
    });
    scheduleResizePlayer();
    clearProgressTimer();
    progressTimer = setInterval(() => {
      const t = player.value?.getCurrentTime?.();
      if (t != null && !Number.isNaN(t)) void reportProgress(t);
    }, 15000);
    void reportProgress(0);
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    playLoading.value = false;
  }
}

function goAuthForInteraction() {
  void router.push({ name: "auth", query: { redirect: route.fullPath } });
}

function formatCount(value: number | null | undefined): string {
  const n = Number(value ?? 0);
  if (n >= 10000) return `${(n / 10000).toFixed(n >= 100000 ? 0 : 1)}万`;
  return String(n);
}

function formatDate(raw: string | null | undefined): string {
  if (!raw) return "未发布";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString([], { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "未知时长";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function handleEditCommand(command: string) {
  if (command === "cover") coverDetailInputRef.value?.click();
  if (command === "local-video") localVideoDetailInputRef.value?.click();
  if (command === "attachment") attachDetailInputRef.value?.click();
}

async function onLikeClick() {
  if (!auth.isLoggedIn) {
    goAuthForInteraction();
    return;
  }
  await toggleLike();
}

async function onFavoriteClick() {
  if (!auth.isLoggedIn) {
    goAuthForInteraction();
    return;
  }
  await toggleFavorite();
}

async function toggleLike() {
  try {
    if (my.value?.liked) {
      const o = await videosApi.unlikeVideo(videoId.value);
      likesCount.value = o.likes_count;
      my.value = { ...my.value, liked: false };
    } else {
      const o = await videosApi.likeVideo(videoId.value);
      likesCount.value = o.likes_count;
      my.value = { liked: true, favorited: my.value?.favorited ?? false };
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function toggleFavorite() {
  try {
    if (my.value?.favorited) {
      const o = await videosApi.unfavoriteVideo(videoId.value);
      favCount.value = o.favorites_count;
      my.value = { liked: my.value?.liked ?? false, favorited: false };
    } else {
      const o = await videosApi.favoriteVideo(videoId.value);
      favCount.value = o.favorites_count;
      my.value = { liked: my.value?.liked ?? false, favorited: true };
    }
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function loadComments() {
  try {
    const { items, total } = await videosApi.listComments(videoId.value, { limit: 50, offset: 0 });
    comments.value = items;
    commentTotal.value = total;
  } catch (e) {
    comments.value = [];
    commentTotal.value = 0;
    ElMessage.error(formatApiError(e));
  }
}

async function submitComment() {
  const t = newComment.value.trim();
  if (!t) return;
  if (!auth.isLoggedIn) return ElMessage.warning("请先登录");
  if (!canCommentOnThisVideo.value) {
    ElMessage.warning("仅已发布作品可评论");
    return;
  }
  commentLoading.value = true;
  try {
    await videosApi.postComment(videoId.value, t);
    newComment.value = "";
    ElMessage.success("已发表");
    await loadComments();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    commentLoading.value = false;
  }
}

async function removeComment(c: videosApi.CommentOut) {
  try {
    await ElMessageBox.confirm("删除该评论？", "确认", { type: "warning" });
    await videosApi.deleteComment(c.id);
    ElMessage.success("已删除");
    await loadComments();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  }
}

async function onAddAttachmentDetail(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (!files.length || !video.value) return;
  attachmentUploading.value = true;
  try {
    for (const f of files) {
      await videosApi.uploadVideoAttachment(video.value.id, f);
    }
    ElMessage.success(files.length === 1 ? "已上传附件" : `已上传 ${files.length} 个附件`);
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    attachmentUploading.value = false;
  }
}

async function onPickLocalVideoDetail(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const f = input.files?.[0];
  input.value = "";
  if (!f || !video.value) return;
  localVideoUploading.value = true;
  try {
    const v = await videosApi.uploadLocalVideoMedia(video.value.id, f);
    video.value = v;
    ElMessage.success("本站视频已更新，可点击下方加载播放预览");
    await maybeAutoSubmitDraft();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    localVideoUploading.value = false;
  }
}

async function onPickCoverDetail(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const f = input.files?.[0];
  input.value = "";
  if (!f || !video.value) return;
  coverDetailUploading.value = true;
  try {
    const jpeg = await imageFileToJpegFile(f, f.name);
    const v = await videosApi.uploadVideoCover(video.value.id, jpeg);
    video.value = v;
    ElMessage.success("封面已更新");
    await maybeAutoSubmitDraft();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    coverDetailUploading.value = false;
  }
}

async function loadAll() {
  loading.value = true;
  videoNotFound.value = false;
  clearLocalPlayback();
  destroyPlayer();
  playInfo.value = null;
  try {
    const v = await videosApi.getVideo(videoId.value);
    video.value = v;
    likesCount.value = v.likes_count;
    favCount.value = v.favorites_count;
    const [vc, cm] = await Promise.all([
      videosApi.listVideoConcepts(videoId.value).catch(() => []),
      loadComments().catch(() => undefined),
    ]);
    concepts.value = vc;
    if (auth.isLoggedIn) {
      try {
        my.value = await videosApi.getMyInteractions(videoId.value);
      } catch {
        my.value = null;
      }
    } else {
      my.value = null;
    }

    void cm;
  } catch (e) {
    video.value = null;
    videoNotFound.value = axios.isAxiosError(e) && e.response?.status === 404;
    if (!videoNotFound.value) ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  bindPlayerResizeListeners();
  loadAll();
});
watch(videoId, loadAll);

watch(
  () => auth.token,
  () => {
    loadAll();
  },
);

onBeforeUnmount(() => {
  unbindPlayerResizeListeners();
  clearLocalPlayback();
  destroyPlayer();
});
</script>

<template>
  <div v-loading="loading" class="video-detail-shell">
    <el-empty
      v-if="!loading && videoNotFound"
      description="视频不存在、未发布或无权查看"
    />
    <template v-else-if="video">
      <section class="video-detail-page">
        <div class="detail-nav">
          <H5BackLink :to="{ name: 'videos' }" label="返回视频列表" />
          <el-dropdown v-if="isVideoAuthor" trigger="click" popper-class="video-edit-menu" @command="handleEditCommand">
            <el-button class="edit-trigger" type="primary">
              编辑
              <span aria-hidden="true">⌄</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="cover">
                  <span class="edit-menu-item">
                    <b>更换封面</b>
                    <small>用于首页、列表与播放前视觉</small>
                  </span>
                </el-dropdown-item>
                <el-dropdown-item command="local-video">
                  <span class="edit-menu-item">
                    <b>替换视频</b>
                    <small>上传本站视频，发布后可直接播放</small>
                  </span>
                </el-dropdown-item>
                <el-dropdown-item command="attachment">
                  <span class="edit-menu-item">
                    <b>上传附件</b>
                    <small>图片、PDF、Word 等作者资料</small>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <input
          v-if="isVideoAuthor"
          ref="coverDetailInputRef"
          type="file"
          class="att-file-input"
          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
          @change="onPickCoverDetail"
        />
        <input
          v-if="isVideoAuthor"
          ref="localVideoDetailInputRef"
          type="file"
          class="att-file-input"
          accept=".mp4,.mov,.mkv,.webm,video/*"
          @change="onPickLocalVideoDetail"
        />
        <input
          v-if="isVideoAuthor"
          ref="attachDetailInputRef"
          type="file"
          class="att-file-input"
          multiple
          @change="onAddAttachmentDetail"
        />

        <section class="detail-hero">
          <div class="preview-card">
            <div
              v-if="canPreviewVideo"
              class="player-shell hero-player"
              :class="{ 'player-shell--active': !!player || !!localPlaySrc }"
              aria-live="polite"
            >
              <video
                v-if="localPlaySrc"
                class="player-box"
                controls
                playsinline
                preload="metadata"
                crossorigin="anonymous"
                :src="localPlaySrc"
                :style="{ width: '100%', height: aliPlayerHeightPx(), background: '#000' }"
                @timeupdate="onLocalVideoTimeupdate"
              />
              <div v-else id="ali-player-wrap" class="player-box" />
              <div v-if="!localPlaySrc && !player" class="preview-placeholder">
                <img v-if="coverUrl" :src="coverUrl" alt="" />
                <span v-else class="cover-fallback">{{ titleInitial }}</span>
                <div class="preview-overlay">
                  <b>视频播放</b>
                  <small>{{ canPreviewVideo ? "点击后加载播放器并开始播放" : "当前状态暂不可播放" }}</small>
                  <el-button type="primary" round :loading="playLoading" :disabled="!canPreviewVideo" @click="startPlayback">
                    立即播放
                  </el-button>
                </div>
              </div>
            </div>
            <div v-else class="player-shell hero-player">
              <div class="preview-placeholder">
                <img v-if="coverUrl" :src="coverUrl" alt="" />
                <span v-else class="cover-fallback">{{ titleInitial }}</span>
                <div class="preview-overlay">
                  <b>暂不可公开播放</b>
                  <small>稿件通过审核并发布后将开放播放。</small>
                </div>
              </div>
            </div>
            <div class="stat-grid" aria-label="播放与互动信息">
              <span>
                <b>{{ formatCount(video.views_count) }}</b>
                <small>播放</small>
              </span>
              <span>
                <b>{{ formatCount(likesCount) }}</b>
                <small>点赞</small>
              </span>
              <span>
                <b>{{ formatCount(favCount) }}</b>
                <small>收藏</small>
              </span>
              <span>
                <b>{{ formatCount(commentTotal) }}</b>
                <small>评论</small>
              </span>
            </div>
          </div>

          <aside class="detail-panel">
            <div class="status-row">
              <span class="status-pill">{{ videoStatusLabel || "未知状态" }}</span>
              <span>{{ formatDuration(video.duration_seconds) }}</span>
            </div>
            <h1>{{ video.title ?? "（无标题）" }}</h1>
            <p v-if="video.description" class="desc">{{ video.description }}</p>
            <p v-else class="desc desc--muted">作者还没有填写简介。</p>
            <div class="meta-line">
              <RouterLink class="author-link" :to="{ name: 'user-profile', params: { id: video.author_id } }">
                作者主页
              </RouterLink>
              <span>发布于 {{ formatDate(video.published_at) }}</span>
            </div>
            <div class="actions hero-actions" role="group" aria-label="点赞与收藏">
              <el-button
                class="act-btn"
                :class="{ 'act-btn--guest': !auth.isLoggedIn }"
                :type="auth.isLoggedIn && my?.liked ? 'primary' : 'default'"
                :plain="!auth.isLoggedIn"
                @click="onLikeClick"
              >
                <span class="act-btn__label">{{ auth.isLoggedIn && my?.liked ? "已赞" : "点赞" }}</span>
                <span v-if="likesCount > 0" class="act-btn__count" aria-hidden="true">{{ likesCount }}</span>
              </el-button>
              <el-button
                class="act-btn"
                :class="{ 'act-btn--guest': !auth.isLoggedIn }"
                :type="auth.isLoggedIn && my?.favorited ? 'warning' : 'default'"
                :plain="!auth.isLoggedIn"
                @click="onFavoriteClick"
              >
                <span class="act-btn__label">{{ auth.isLoggedIn && my?.favorited ? "已收藏" : "收藏" }}</span>
                <span v-if="favCount > 0" class="act-btn__count" aria-hidden="true">{{ favCount }}</span>
              </el-button>
            </div>
            <p v-if="playInfo?.expire_time" class="play-expire">播放凭证有效期至 {{ formatDate(playInfo.expire_time) }}</p>
          </aside>
        </section>
      </section>

      <el-alert
        v-if="isVideoAuthor && video.status === 'draft'"
        type="warning"
        :closable="false"
        show-icon
        class="workflow-alert"
      >
        <template #title>当前为「草稿」</template>
        <p>
          在<strong>创作页</strong>保存时会自动送审。若在此补传本站视频或封面，也会再次尝试自动送审。公开列表仅展示<strong>已发布</strong>内容，需管理员在后台通过审核。
        </p>
      </el-alert>

      <el-alert
        v-else-if="isVideoAuthor && video.status === 'pending_review'"
        type="info"
        :closable="false"
        show-icon
        class="workflow-alert"
      >
        <template #title>待管理员审核</template>
        <p>通过后状态变为「已发布」，本稿将出现在公开列表；在此之前他人无法在列表中搜到本稿。</p>
      </el-alert>

      <el-alert
        v-else-if="isVideoAuthor && video.status === 'rejected'"
        type="error"
        :closable="false"
        show-icon
        class="workflow-alert"
      >
        <template #title>审核未通过</template>
        <p v-if="video.rejection_reason">{{ video.rejection_reason }}</p>
        <p v-else>（无驳回说明）请按运营要求修改后，由管理员将稿件打回可编辑状态或重新走审核流程。</p>
      </el-alert>

      <div v-if="concepts.length" class="block">
        <h3>相关概念</h3>
        <el-space wrap>
          <RouterLink v-for="c in concepts" :key="c.concept_id" :to="`/concepts/${c.concept_id}`" class="link">
            {{ c.concept_name ?? "（未命名）" }}
          </RouterLink>
        </el-space>
      </div>

      <div class="block">
        <h3>评论（{{ commentTotal }}）</h3>
        <el-input
          v-if="auth.isLoggedIn"
          v-model="newComment"
          type="textarea"
          :rows="3"
          placeholder="写评论…"
          :disabled="!canCommentOnThisVideo"
          style="margin-bottom: 8px"
        />
        <el-alert
          v-if="auth.isLoggedIn && !canCommentOnThisVideo"
          title="当前为草稿 / 待审核 / 已下架等状态时不可评论，发布通过后即可评论。"
          type="info"
          :closable="false"
          style="margin-bottom: 8px"
        />
        <el-button
          v-if="auth.isLoggedIn"
          class="act-btn act-btn--block"
          type="primary"
          :loading="commentLoading"
          :disabled="!canCommentOnThisVideo"
          @click="submitComment"
        >
          发表评论
        </el-button>
        <template v-else>
          <el-alert title="登录后即可评论、点赞与收藏。" type="info" :closable="false" style="margin: 8px 0" />
          <el-button class="act-btn act-btn--block" type="primary" @click="goAuthForInteraction">去登录</el-button>
        </template>

        <div v-if="!isMobile" class="comment-desktop-wrap">
          <VideoCommentsDesktopTable
            :comments="comments"
            :logged-in="auth.isLoggedIn"
            :current-user-id="auth.user?.id"
            @delete="removeComment"
          />
        </div>

        <ul v-else class="h5-card-list comment-m" style="margin-top: 12px">
          <li v-for="row in comments" :key="row.id" class="h5-card-list__item">
            <div class="comment-m__body">{{ row.content }}</div>
            <div class="h5-card-list__meta">
              <span class="comment-m__uid">{{ row.user_id }}</span>
              <span>{{ row.created_at }}</span>
            </div>
            <div v-if="auth.isLoggedIn && row.user_id === auth.user?.id" class="comment-m__act">
              <el-button type="danger" link @click="removeComment(row)">删除</el-button>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.video-detail-shell {
  min-height: calc(100dvh - 72px);
  margin: -20px calc(50% - 50vw) -24px;
  padding: 18px max(16px, calc(50vw - 560px)) calc(92px + env(safe-area-inset-bottom, 0px));
  background:
    radial-gradient(circle at 12% -8%, rgba(34, 211, 238, 0.18), transparent 30%),
    radial-gradient(circle at 92% 10%, rgba(139, 92, 246, 0.18), transparent 34%),
    linear-gradient(180deg, #070b16 0%, #050506 58%, #081018 100%);
  color: #f8fafc;
  overflow-x: hidden;
  overscroll-behavior-x: none;
}

.video-detail-page {
  position: relative;
}

.detail-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.detail-nav :deep(a) {
  color: #67e8f9;
  font-weight: 800;
  text-decoration: none;
}

.edit-trigger {
  min-width: 88px;
  border: 0;
  border-radius: 999px;
  background:
    linear-gradient(135deg, rgba(34, 211, 238, 0.96), rgba(167, 139, 250, 0.95));
  color: #04111f;
  font-weight: 900;
  box-shadow: 0 16px 36px rgba(34, 211, 238, 0.26);
}

.detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(300px, 0.82fr);
  gap: 14px;
  align-items: start;
  max-width: 1120px;
  margin: 0 auto;
}

.preview-card,
.detail-panel,
.block {
  border: 1px solid rgba(103, 232, 249, 0.14);
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.08), transparent 42%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(2, 6, 23, 0.9));
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.preview-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 26px;
  min-width: 0;
}

.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-radius: 24px;
  padding: 18px;
}

.status-row,
.meta-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #94a3b8;
  font-size: 13px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(103, 232, 249, 0.28);
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.12);
  color: #67e8f9;
  font-size: 12px;
  font-weight: 900;
}

.detail-panel h1 {
  margin: 0;
  color: #f8fafc;
  font-size: clamp(26px, 4.2vw, 44px);
  line-height: 1.02;
  font-weight: 950;
  letter-spacing: -0.07em;
  word-break: break-word;
}

.author-link,
.link {
  color: #67e8f9;
  font-weight: 800;
  text-decoration: none;
}

.desc {
  margin: 0;
  color: #cbd5e1;
  white-space: pre-wrap;
  line-height: 1.65;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.desc--muted,
.hint,
.play-expire {
  color: #94a3b8;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(2, 6, 23, 0.62);
}

.stat-grid span {
  min-width: 0;
  padding: 9px 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.09), transparent 50%),
    rgba(15, 23, 42, 0.58);
  text-align: center;
}

.stat-grid b,
.stat-grid small {
  display: block;
}

.stat-grid b {
  color: #f8fafc;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 17px;
  line-height: 1.1;
}

.stat-grid small {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-actions {
  justify-content: center;
}

.hero-actions .act-btn {
  flex: 0 1 220px;
  width: 100%;
  max-width: 220px;
  margin: 0 !important;
}

.act-btn {
  min-height: 42px;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-weight: 800;
}

.hero-actions :deep(.el-button.act-btn) {
  border-color: rgba(103, 232, 249, 0.22);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.9), rgba(2, 6, 23, 0.86));
  color: #e2e8f0;
}

.hero-actions :deep(.el-button.act-btn.el-button--primary),
.hero-actions :deep(.el-button.act-btn.el-button--warning) {
  border-color: rgba(34, 211, 238, 0.42);
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.92), rgba(167, 139, 250, 0.88));
  color: #04111f;
}

.act-btn__label {
  font-weight: 800;
}

.act-btn__count {
  margin-left: 6px;
  font-size: 13px;
  opacity: 0.85;
}

.act-btn--guest {
  border-width: 1.5px;
}

.act-btn--block {
  width: 100%;
  margin-top: 4px;
}

.player-shell {
  position: relative;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  contain: layout style;
  background: linear-gradient(160deg, #111827 0%, #020617 100%);
}

.hero-player {
  min-height: 0;
  aspect-ratio: 16 / 9;
}

.player-shell--active {
  aspect-ratio: auto;
  min-height: 0;
  height: auto;
  background: #000;
}

.player-box {
  margin-top: 0;
  min-height: 0;
  max-width: 100%;
  width: 100%;
  box-sizing: border-box;
}

.preview-placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 20%, rgba(34, 211, 238, 0.16), transparent 44%),
    #020617;
}

.preview-placeholder img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.68;
  filter: saturate(1.08) contrast(1.08);
}

.preview-placeholder::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(2, 6, 23, 0.16), rgba(2, 6, 23, 0.82)),
    radial-gradient(circle at 50% 54%, rgba(34, 211, 238, 0.22), transparent 32%);
}

.cover-fallback {
  position: relative;
  z-index: 1;
  color: rgba(248, 250, 252, 0.08);
  font-size: clamp(92px, 18vw, 180px);
  font-weight: 950;
  letter-spacing: -0.12em;
}

.preview-overlay {
  position: relative;
  z-index: 2;
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
}

.preview-overlay b {
  color: #f8fafc;
  font-size: clamp(24px, 4vw, 42px);
  font-weight: 950;
  letter-spacing: -0.06em;
}

.preview-overlay small {
  color: #cbd5e1;
}

.workflow-alert {
  max-width: 1120px;
  margin: 12px auto 0;
}

.block {
  max-width: 1120px;
  margin: 14px auto 0;
  border-radius: 24px;
  padding: 16px;
}

.block h3 {
  margin: 0 0 10px;
  color: #f8fafc;
}

.hint {
  margin: 0;
  font-size: 13px;
}

.asset-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.att-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  overflow: hidden;
}

.att-list {
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.att-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.att-name {
  flex: 1 1 160px;
  min-width: 0;
  color: #e2e8f0;
  word-break: break-word;
}

.att-meta {
  color: #94a3b8;
  font-size: 13px;
}

.comment-desktop-wrap {
  margin-top: 12px;
}

.comment-m__body {
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.comment-m__uid {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.comment-m__act {
  margin-top: 8px;
}

.video-detail-shell :deep(.el-textarea__inner),
.video-detail-shell :deep(.el-input__wrapper) {
  border-color: rgba(103, 232, 249, 0.16);
  background: rgba(15, 23, 42, 0.76);
  color: #f8fafc;
  box-shadow: none;
}

.video-detail-shell :deep(.el-table),
.video-detail-shell :deep(.el-table tr),
.video-detail-shell :deep(.el-table th.el-table__cell),
.video-detail-shell :deep(.el-table td.el-table__cell) {
  background: transparent;
  color: #e2e8f0;
}

.video-detail-shell :deep(.el-table) {
  --el-table-border-color: rgba(255, 255, 255, 0.08);
  --el-table-header-bg-color: rgba(15, 23, 42, 0.86);
  --el-table-row-hover-bg-color: rgba(34, 211, 238, 0.08);
}

.video-detail-shell :deep(.el-loading-mask) {
  background: rgba(2, 6, 23, 0.78);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

:global(.video-edit-menu) {
  border: 1px solid rgba(103, 232, 249, 0.16) !important;
  border-radius: 18px !important;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.16), transparent 42%),
    rgba(2, 6, 23, 0.96) !important;
  box-shadow: 0 18px 46px rgba(0, 0, 0, 0.42) !important;
  overflow: hidden;
}

:global(.video-edit-menu .el-dropdown-menu) {
  background: transparent;
  padding: 6px;
}

:global(.video-edit-menu .el-dropdown-menu__item) {
  min-width: 220px;
  min-height: 58px;
  padding: 8px 10px;
  border-radius: 12px;
  color: #e2e8f0;
}

:global(.video-edit-menu .el-dropdown-menu__item:not(.is-disabled):focus),
:global(.video-edit-menu .el-dropdown-menu__item:not(.is-disabled):hover) {
  background: rgba(34, 211, 238, 0.12);
  color: #67e8f9;
}

:global(.video-edit-menu .edit-menu-item) {
  display: grid;
  gap: 3px;
  line-height: 1.2;
}

:global(.video-edit-menu .edit-menu-item b) {
  color: #f8fafc;
  font-size: 13px;
  font-weight: 900;
}

:global(.video-edit-menu .edit-menu-item small) {
  color: #94a3b8;
  font-size: 11px;
}

@media (max-width: 900px) {
  .video-detail-shell {
    margin: 0 -10px -10px;
    padding: 10px 10px calc(92px + env(safe-area-inset-bottom, 0px));
  }

  .detail-hero {
    grid-template-columns: 1fr;
  }

  .detail-panel,
  .preview-card,
  .block {
    border-radius: 20px;
  }

  .hero-player {
    min-height: 0;
  }
}

@media (max-width: 560px) {
  .detail-nav {
    align-items: flex-start;
    padding: 0 2px;
  }

  .detail-panel {
    padding: 16px;
  }

  .stat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
    padding: 8px;
  }

  .stat-grid span {
    padding: 8px 3px;
    border-radius: 12px;
  }

  .stat-grid b {
    font-size: 16px;
  }

  .stat-grid small {
    font-size: 10px;
  }

  .actions .act-btn {
    flex: 1 1 0;
    max-width: none;
    min-width: 0;
  }

  .asset-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
