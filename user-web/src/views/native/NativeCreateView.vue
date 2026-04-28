<script setup lang="ts">
import { onMounted, onBeforeUnmount, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as videosApi from "@/api/videos";
import * as categoriesApi from "@/api/categories";
import type { CategoryPublic } from "@/api/categories";
import { formatApiError } from "@/util/errors";
import { imageFileToJpegFile } from "@/util/imageToJpegFile";

const router = useRouter();

const categories = ref<CategoryPublic[]>([]);
const loadingCats = ref(true);
const submitting = ref(false);
const uploadHint = ref("");

const videoInputRef = ref<HTMLInputElement | null>(null);
const coverInputRef = ref<HTMLInputElement | null>(null);
const videoFile = ref<File | null>(null);
const coverFile = ref<File | null>(null);
const coverPreviewUrl = ref<string | null>(null);
const coverPickerOpen = ref(false);
const generatingFrames = ref(false);
const frameCandidates = ref<Array<{ file: File; url: string; timeLabel: string }>>([]);

const form = reactive({
  title: "",
  description: "",
  category_id: "" as string,
});

const VIDEO_ACCEPT = ".mp4,.mov,.mkv,.webm,video/*";
const COVER_ACCEPT = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";

function revokeCoverPreview() {
  if (coverPreviewUrl.value) {
    URL.revokeObjectURL(coverPreviewUrl.value);
    coverPreviewUrl.value = null;
  }
}

function clearFrameCandidates() {
  for (const item of frameCandidates.value) URL.revokeObjectURL(item.url);
  frameCandidates.value = [];
}

async function loadCats() {
  loadingCats.value = true;
  try {
    const { items } = await categoriesApi.listCategories();
    categories.value = items;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loadingCats.value = false;
  }
}

onMounted(() => {
  void loadCats();
});

onBeforeUnmount(() => {
  revokeCoverPreview();
  clearFrameCandidates();
});

function onPickVideo(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  input.value = "";
  videoFile.value = f;
  clearFrameCandidates();
  if (!f) {
    clearCover();
    coverPickerOpen.value = false;
  }
}

function onClearVideo() {
  videoFile.value = null;
  coverPickerOpen.value = false;
  clearFrameCandidates();
  clearCover();
}

function onPickCover(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const f = input.files?.[0] ?? null;
  input.value = "";
  revokeCoverPreview();
  coverFile.value = f;
  if (f && f.type.startsWith("image/")) {
    coverPreviewUrl.value = URL.createObjectURL(f);
    coverPickerOpen.value = false;
  }
}

function clearCover() {
  revokeCoverPreview();
  coverFile.value = null;
}

function openCoverPicker() {
  if (!videoFile.value) {
    ElMessage.warning("请先选择视频文件");
    return;
  }
  coverPickerOpen.value = true;
}

async function generateCoverCandidates(): Promise<void> {
  if (!videoFile.value) {
    ElMessage.warning("请先选择视频文件");
    return;
  }
  generatingFrames.value = true;
  uploadHint.value = "正在生成封面候选…";
  const vf = videoFile.value;
  const url = URL.createObjectURL(vf);
  try {
    const candidates = await new Promise<Array<{ file: File; url: string; timeLabel: string }>>((resolve) => {
      const video = document.createElement("video");
      video.muted = true;
      video.playsInline = true;
      video.setAttribute("playsinline", "");
      video.setAttribute("webkit-playsinline", "");
      video.preload = "auto";
      video.src = url;

      let settled = false;
      let timer: number;
      const done = (items: Array<{ file: File; url: string; timeLabel: string }>) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        URL.revokeObjectURL(url);
        try {
          video.removeAttribute("src");
          video.load();
        } catch {
          /* ignore */
        }
        resolve(items);
      };
      timer = window.setTimeout(() => done([]), 45_000);

      const grabFrame = async () => {
        try {
          const w = video.videoWidth || 0;
          const h = video.videoHeight || 0;
          if (w < 2 || h < 2) {
            done([]);
            return;
          }
          const dur = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 8;
          const times = [0.06, 0.16, 0.28, 0.42, 0.58, 0.74].map((p) => Math.min(Math.max(dur * p, 0.1), Math.max(dur - 0.1, 0.1)));
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          if (!ctx) return done([]);
          const out: Array<{ file: File; url: string; timeLabel: string }> = [];
          for (let i = 0; i < times.length; i += 1) {
            await new Promise<void>((next) => {
              video.onseeked = () => next();
              video.currentTime = times[i];
            });
            ctx.drawImage(video, 0, 0, w, h);
            const blob = await new Promise<Blob | null>((next) => canvas.toBlob(next, "image/jpeg", 0.9));
            if (blob) {
              const file = new File([blob], `cover-frame-${i + 1}.jpg`, { type: "image/jpeg" });
              out.push({ file, url: URL.createObjectURL(file), timeLabel: `${Math.round(times[i])}s` });
            }
          }
          done(out);
        } catch {
          done([]);
        }
      };

      video.onloadedmetadata = () => {
        void grabFrame();
      };
      video.onerror = () => done([]);
      video.load();
    });
    clearFrameCandidates();
    frameCandidates.value = candidates;
    if (!candidates.length) {
      ElMessage.error("生成失败：请尝试选择上传封面图或换一段视频再试");
      return;
    }
    ElMessage.success("已生成封面候选，请选择一张作为封面");
  } finally {
    generatingFrames.value = false;
    uploadHint.value = "";
  }
}

function selectFrameCandidate(item: { file: File; url: string }) {
  revokeCoverPreview();
  coverFile.value = item.file;
  coverPreviewUrl.value = URL.createObjectURL(item.file);
  coverPickerOpen.value = false;
  ElMessage.success("已选择视频帧作为封面");
}

function clearMediaSelection() {
  videoFile.value = null;
  coverPickerOpen.value = false;
  clearFrameCandidates();
  clearCover();
}

async function submit() {
  const t = form.title.trim();
  if (!t) {
    ElMessage.warning("请填写标题");
    return;
  }
  if (!videoFile.value) {
    ElMessage.warning("请先选择视频文件");
    return;
  }
  submitting.value = true;
  uploadHint.value = "";
  let draft: videosApi.VideoDetail | null = null;
  try {
    uploadHint.value = "创建稿件…";
    draft = await videosApi.createVideo({
      title: t,
      description: form.description.trim() || null,
      category_id: form.category_id || null,
    });

    if (coverFile.value) {
      uploadHint.value = "上传封面…";
      const jpeg = await imageFileToJpegFile(coverFile.value, coverFile.value.name);
      const v = await videosApi.uploadVideoCover(draft.id, jpeg);
      draft = v;
    }

    if (videoFile.value) {
      const vf = videoFile.value;
      uploadHint.value = "正在上传视频到本站服务器…";
      const v = await videosApi.uploadLocalVideoMedia(draft.id, vf);
      draft = v;
    }

    uploadHint.value = "正在提交审核…";
    try {
      draft = await videosApi.submitVideoForReview(draft.id);
      ElMessage.success("视频发布成功");
    } catch (e) {
      ElMessage.warning(`内容已保存，但自动送审失败：${formatApiError(e)} 请到详情页重试或联系管理员。`);
    }

    await router.push({ name: "native-publish-preview", params: { id: draft.id } });
    clearMediaSelection();
    clearCover();
  } catch (e) {
    const detail = formatApiError(e);
    if (draft) {
      ElMessage.error(`${detail} — 稿件已保留，将跳转详情页以便稍后继续。`);
      try {
        await router.push({ name: "native-hub" });
      } catch {
        /* ignore */
      }
      clearMediaSelection();
    } else {
      ElMessage.error(detail);
    }
  } finally {
    submitting.value = false;
    uploadHint.value = "";
  }
}
</script>

<template>
  <div v-loading="loadingCats" class="native-stack create-page">
    <div class="native-title-row">
      <div>
        <h1 class="native-h1">创作</h1>
        <p class="native-hint">
          选择<strong>视频</strong>与<strong>封面</strong>后即可发布；暂时不上传其他附件，流程更轻更快。
        </p>
      </div>
    </div>

    <div class="native-card">
      <label class="native-form-label" for="ct">标题 *</label>
      <input id="ct" v-model="form.title" class="native-input" maxlength="512" placeholder="稿件标题" />
    </div>

    <div class="native-card">
      <label class="native-form-label" for="cd">简介</label>
      <textarea id="cd" v-model="form.description" class="native-textarea" placeholder="可选" />
    </div>

    <div class="native-card">
      <label class="native-form-label" for="cc">分类</label>
      <select id="cc" v-model="form.category_id" class="native-select">
        <option value="">（不选）</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
    </div>

    <div class="native-card media-card">
      <div class="native-form-label">媒体文件</div>
      <p class="native-mini">先选择视频；视频选好后再设置封面，可从视频预览帧中挑选，也可上传图片。</p>
      <div class="row-btns">
        <button type="button" class="native-btn native-btn--ghost" @click="videoInputRef?.click()">选择视频文件</button>
        <button v-if="videoFile" type="button" class="native-btn native-btn--ghost" @click="openCoverPicker">设置封面</button>
        <button v-if="coverFile" type="button" class="native-btn native-btn--ghost" @click="clearCover">清除封面</button>
        <button v-if="videoFile" type="button" class="native-btn native-btn--ghost" @click="onClearVideo">清除</button>
      </div>
      <input
        ref="videoInputRef"
        type="file"
        class="sr-only"
        :accept="VIDEO_ACCEPT"
        @change="onPickVideo"
      />
      <p v-if="videoFile" class="file-chip">{{ videoFile.name }}（{{ (videoFile.size / (1024 * 1024)).toFixed(2) }} MB）</p>
      <input
        ref="coverInputRef"
        type="file"
        class="sr-only"
        :accept="COVER_ACCEPT"
        @change="onPickCover"
      />
      <div v-if="coverPreviewUrl || coverFile" class="cover-preview-wrap">
        <img v-if="coverPreviewUrl" class="cover-preview" :src="coverPreviewUrl" alt="封面预览" />
      </div>
    </div>

    <div v-if="coverPickerOpen" class="cover-sheet-backdrop" @click.self="coverPickerOpen = false">
      <section class="cover-sheet" role="dialog" aria-modal="true" aria-label="选择封面">
        <div class="cover-sheet-head">
          <div>
            <h2>选择封面</h2>
            <p>从视频预览帧里挑一张，或上传自己的封面图。</p>
          </div>
          <button type="button" class="sheet-close" @click="coverPickerOpen = false">×</button>
        </div>
        <div class="cover-sheet-actions">
          <button type="button" class="native-btn native-btn--primary" :disabled="generatingFrames" @click="generateCoverCandidates">
            {{ generatingFrames ? "生成中…" : "从视频生成" }}
          </button>
          <button type="button" class="native-btn native-btn--ghost" @click="coverInputRef?.click()">选择上传</button>
        </div>
        <div v-if="frameCandidates.length" class="frame-grid">
          <button v-for="item in frameCandidates" :key="item.url" type="button" class="frame-card" @click="selectFrameCandidate(item)">
            <img :src="item.url" alt="" />
            <span>{{ item.timeLabel }}</span>
          </button>
        </div>
        <p v-else class="frame-empty">点击“从视频生成”后，会出现多张候选封面。</p>
      </section>
    </div>

    <p v-if="uploadHint" class="upload-hint">{{ uploadHint }}</p>

    <button type="button" class="native-btn native-btn--primary create-submit" :disabled="submitting" @click="submit">
      {{ submitting ? "处理中…" : "上传并自动提交审核" }}
    </button>
  </div>
</template>

<style scoped>
.create-page {
  padding-bottom: 24px;
}

.create-submit {
  width: 100%;
  margin-top: 4px;
}

.native-mini {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  line-height: 1.45;
}

.row-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.file-chip {
  margin: 8px 0 0;
  font-size: 13px;
  word-break: break-all;
}

.cover-preview-wrap {
  margin-top: 10px;
}

.cover-preview {
  max-width: 100%;
  max-height: 200px;
  border-radius: 8px;
  object-fit: contain;
  background: #111;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.upload-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-color-primary, #409eff);
}

.media-card {
  border: 1px solid color-mix(in srgb, var(--el-color-primary, #409eff) 35%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--el-color-primary, #409eff) 12%, transparent);
}
.cover-sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.cover-sheet {
  width: min(720px, 100%);
  max-height: min(78vh, 720px);
  overflow: auto;
  padding: 16px;
  border-radius: 22px 22px 0 0;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(180deg, #111827, #050506);
  color: #f8fafc;
  box-shadow: 0 -18px 50px rgba(0, 0, 0, 0.45);
}
.cover-sheet-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.cover-sheet h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 900;
}
.cover-sheet p {
  margin: 5px 0 0;
  color: #94a3b8;
  font-size: 13px;
}
.sheet-close {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.08);
  font-size: 24px;
  cursor: pointer;
}
.cover-sheet-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.frame-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.frame-card {
  position: relative;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(34, 211, 238, 0.22);
  border-radius: 14px;
  background: #020617;
  cursor: pointer;
}
.frame-card img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}
.frame-card span {
  position: absolute;
  right: 6px;
  bottom: 6px;
  padding: 2px 7px;
  border-radius: 999px;
  color: #042f2e;
  background: #67e8f9;
  font-size: 11px;
  font-weight: 900;
}
.frame-empty {
  padding: 18px 0;
  text-align: center;
}
</style>
