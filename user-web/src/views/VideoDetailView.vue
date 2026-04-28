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

const attachments = ref<videosApi.VideoAttachmentOut[]>([]);
const attachmentsLoading = ref(false);
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

async function downloadAttachment(row: videosApi.VideoAttachmentOut) {
  try {
    const blob = await videosApi.downloadVideoAttachmentBlob(videoId.value, row.id);
    videosApi.triggerBlobDownload(blob, row.original_filename);
  } catch (e) {
    ElMessage.error(formatApiError(e));
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
    attachments.value = await videosApi.listVideoAttachments(videoId.value);
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

    attachments.value = [];
    if (auth.isLoggedIn && auth.user?.id === v.author_id) {
      attachmentsLoading.value = true;
      try {
        attachments.value = await videosApi.listVideoAttachments(videoId.value);
      } catch {
        attachments.value = [];
      } finally {
        attachmentsLoading.value = false;
      }
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
  <div v-loading="loading">
    <el-empty
      v-if="!loading && videoNotFound"
      description="视频不存在、未发布或无权查看"
    />
    <template v-else-if="video">
      <H5BackLink :to="{ name: 'videos' }" label="返回视频列表" />
      <h2>{{ video.title ?? "（无标题）" }}</h2>
      <p class="meta">
        {{ video.views_count ?? 0 }} 播放 · {{ likesCount }} 赞 · {{ favCount }} 收藏
        ·
        <RouterLink class="author-link" :to="{ name: 'user-profile', params: { id: video.author_id } }">
          作者主页
        </RouterLink>
        <span v-if="video.published_at"> · 发布于 {{ video.published_at }}</span>
        <span v-if="isVideoAuthor && videoStatusLabel"> · 状态：{{ videoStatusLabel }}</span>
      </p>
      <p v-if="video.description" class="desc">{{ video.description }}</p>

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

      <div v-if="isVideoAuthor" class="block">
        <h3>封面图</h3>
        <p class="hint">JPEG；上传后用于首页与列表展示（通过审核且已发布后对外可见）。</p>
        <input
          ref="coverDetailInputRef"
          type="file"
          class="att-file-input"
          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
          @change="onPickCoverDetail"
        />
        <el-button type="primary" plain :loading="coverDetailUploading" @click="coverDetailInputRef?.click()">
          上传或替换封面
        </el-button>
      </div>

      <div v-if="isVideoAuthor" class="block">
        <h3>本站视频（磁盘）</h3>
        <p class="hint">与创作页相同：上传到 API 所在服务器，免阿里云亦可预览/播放（已发布或作者预览）。可多次上传替换。</p>
        <input
          ref="localVideoDetailInputRef"
          type="file"
          class="att-file-input"
          accept=".mp4,.mov,.mkv,.webm,video/*"
          @change="onPickLocalVideoDetail"
        />
        <el-button type="primary" plain :loading="localVideoUploading" @click="localVideoDetailInputRef?.click()">
          上传或替换本站视频
        </el-button>
      </div>

      <div v-if="isVideoAuthor" v-loading="attachmentsLoading" class="block">
        <h3>稿件附件</h3>
        <p class="hint">图片、PDF、Word 等，与视频一样保存在服务器磁盘；仅作者可见与管理。可多选一次上传多个。</p>
        <input
          ref="attachDetailInputRef"
          type="file"
          class="att-file-input"
          multiple
          @change="onAddAttachmentDetail"
        />
        <el-button type="primary" plain :loading="attachmentUploading" @click="attachDetailInputRef?.click()">
          上传附件
        </el-button>
        <el-empty v-if="!attachments.length" description="暂无附件" :image-size="72" style="margin-top: 12px" />
        <ul v-else class="att-list">
          <li v-for="a in attachments" :key="a.id" class="att-row">
            <span class="att-name">{{ a.original_filename }}</span>
            <span class="att-meta">{{ (a.size_bytes / 1024).toFixed(1) }} KB</span>
            <el-button type="primary" link @click="downloadAttachment(a)">下载</el-button>
          </li>
        </ul>
      </div>

      <div class="block actions" role="group" aria-label="点赞与收藏">
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

      <div
        v-if="video.status === 'published' || (isVideoAuthor && ['draft', 'pending_review', 'rejected', 'offline'].includes(video.status))"
        class="block"
      >
        <h3>播放</h3>
        <p class="hint h5-desktop-only">
          登录后点击加载：若视频在本站磁盘，将使用浏览器内置播放器；若仅绑定阿里云点播，则使用阿里云 Web 播放器。
        </p>
        <p class="hint hint--m h5-mobile-only">登录后可加载播放（需网络畅通）。</p>
        <el-button type="primary" :loading="playLoading" @click="startPlayback">加载播放器</el-button>
        <div v-if="localPlaySrc" class="player-shell player-shell--active" aria-live="polite">
          <video
            class="player-box"
            controls
            playsinline
            preload="metadata"
            crossorigin="anonymous"
            :src="localPlaySrc"
            :style="{ width: '100%', height: aliPlayerHeightPx(), background: '#000' }"
            @timeupdate="onLocalVideoTimeupdate"
          />
        </div>
        <div
          v-else
          class="player-shell"
          :class="{ 'player-shell--active': !!player }"
          aria-live="polite"
        >
          <div id="ali-player-wrap" class="player-box" />
        </div>
      </div>
      <el-alert v-else title="该稿件非发布状态，不提供公开播放。" type="info" :closable="false" show-icon />

      <div class="block">
        <h3>评论（{{ commentTotal }}）</h3>
        <el-input
          v-if="auth.isLoggedIn"
          v-model="newComment"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
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
h2 {
  word-break: break-word;
  overflow-wrap: anywhere;
}
.meta {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.author-link {
  color: var(--native-accent);
  font-weight: 700;
  text-decoration: none;
}
.desc {
  white-space: pre-wrap;
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.workflow-alert {
  margin-top: 16px;
}
.block {
  margin-top: 24px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
@media (max-width: 767px) {
  .actions {
    gap: 12px;
  }
  .actions .act-btn {
    flex: 1 1 calc(50% - 6px);
    min-width: 0;
  }
}
.act-btn {
  min-height: 48px;
  padding: 0 22px;
}
.act-btn__label {
  font-weight: 600;
}
.act-btn__count {
  margin-left: 6px;
  font-size: 13px;
  font-weight: 500;
  opacity: 0.85;
}
.act-btn--guest {
  border-width: 1.5px;
}
.act-btn--block {
  width: 100%;
  margin-top: 4px;
}
/* 未实例化播放器前预留 16:9，降低 CLS；实例化后由 SDK 接管高度 */
.player-shell {
  margin-top: 12px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 10px;
  overflow: hidden;
  contain: layout style;
}
.player-shell:not(.player-shell--active) {
  aspect-ratio: 16 / 9;
  min-height: 200px;
  max-height: min(72vh, 800px);
  background: linear-gradient(160deg, #1a1d22 0%, #0a0b0d 100%);
  border: 1px solid var(--el-border-color-lighter);
}
.player-shell--active {
  aspect-ratio: auto;
  min-height: 0;
  max-height: none;
  background: transparent;
  border-color: transparent;
}
.player-box {
  margin-top: 0;
  min-height: 0;
  max-width: 100%;
  width: 100%;
  box-sizing: border-box;
}
.hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.hint--m {
  margin-bottom: 10px;
}
.comment-m__body {
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
.comment-desktop-wrap {
  margin-top: 12px;
}

@media (max-width: 767px) {
  h2 {
    font-size: 20px;
    line-height: 1.35;
  }
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.att-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  overflow: hidden;
}

.att-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.att-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.att-name {
  flex: 1 1 160px;
  min-width: 0;
  word-break: break-word;
}

.att-meta {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
