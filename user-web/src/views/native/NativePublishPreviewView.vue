<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as videosApi from "@/api/videos";
import type { VideoDetail } from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

const route = useRoute();
const video = ref<VideoDetail | null>(null);
const loading = ref(true);

const id = computed(() => String(route.params.id || ""));
const authorName = computed(() => video.value?.author_username?.trim() || "我的作品");
const statusText = computed(() => {
  const status = video.value?.status;
  if (status === "published") return "已发布";
  if (status === "pending_review") return "审核中";
  if (status === "draft") return "草稿";
  if (status === "rejected") return "需修改";
  return "已保存";
});

async function load() {
  if (!id.value) return;
  loading.value = true;
  try {
    video.value = await videosApi.getVideo(id.value);
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div v-loading="loading" class="publish-preview">
    <section v-if="video" class="preview-hero">
      <div class="preview-orbit" aria-hidden="true" />
      <div class="preview-author">
        <div class="preview-avatar">{{ authorName.slice(0, 1).toUpperCase() }}</div>
        <div class="preview-author__main">
          <p class="preview-kicker">视频发布成功</p>
          <h1>{{ authorName }}</h1>
          <span>{{ statusText }} · {{ video.title || "未命名作品" }}</span>
        </div>
        <RouterLink class="preview-pill" :to="{ name: 'native-hub' }">个人中心</RouterLink>
      </div>

      <div class="preview-stage">
        <video
          v-if="resolveApiAssetUrl(video.video_url)"
          class="preview-video"
          :src="resolveApiAssetUrl(video.video_url) || undefined"
          :poster="resolveApiAssetUrl(video.cover_url) || undefined"
          controls
          playsinline
        />
        <div v-else class="preview-fallback">
          <img v-if="resolveApiAssetUrl(video.cover_url)" :src="resolveApiAssetUrl(video.cover_url) || undefined" alt="" />
          <div class="preview-fallback__text">
            <strong>预览已生成</strong>
            <span>视频正在完成转码或审核，可稍后在个人中心继续查看。</span>
          </div>
        </div>
      </div>

      <div class="preview-info">
        <div>
          <p class="preview-label">作品标题</p>
          <h2>{{ video.title || "未命名作品" }}</h2>
        </div>
        <p v-if="video.description" class="preview-desc">{{ video.description }}</p>
        <div class="preview-metrics">
          <span>{{ video.views_count ?? 0 }} 播放</span>
          <span>{{ video.likes_count ?? 0 }} 点赞</span>
          <span>{{ video.favorites_count ?? 0 }} 收藏</span>
        </div>
      </div>
    </section>

    <section v-else-if="!loading" class="preview-empty">
      <h1>未找到预览内容</h1>
      <RouterLink class="preview-pill" :to="{ name: 'native-create' }">重新发布</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.publish-preview {
  position: relative;
  min-height: calc(100vh - 96px);
  padding: 10px 0 28px;
  color: #f8fafc;
}

.preview-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(103, 232, 249, 0.18);
  border-radius: 28px;
  padding: 14px;
  background:
    radial-gradient(circle at 12% -10%, rgba(34, 211, 238, 0.28), transparent 32%),
    radial-gradient(circle at 100% 18%, rgba(167, 139, 250, 0.24), transparent 34%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.9), rgba(2, 6, 23, 0.96));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.34);
}

.preview-orbit {
  position: absolute;
  inset: -120px -120px auto auto;
  width: 260px;
  height: 260px;
  border: 1px solid rgba(103, 232, 249, 0.2);
  border-radius: 999px;
  box-shadow: inset 0 0 42px rgba(34, 211, 238, 0.1);
  pointer-events: none;
}

.preview-author {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.preview-avatar {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 18px;
  background: linear-gradient(135deg, #67e8f9, #a78bfa);
  color: #06111f;
  font-size: 20px;
  font-weight: 900;
}

.preview-author__main {
  min-width: 0;
  flex: 1;
}

.preview-kicker,
.preview-label {
  margin: 0;
  color: #67e8f9;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.preview-author h1 {
  margin: 2px 0;
  font-size: 18px;
  font-weight: 950;
}

.preview-author span {
  display: block;
  overflow: hidden;
  color: #cbd5e1;
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.preview-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 9px 12px;
  background: rgba(255, 255, 255, 0.1);
  color: #e0f2fe;
  text-decoration: none;
  font-size: 12px;
  font-weight: 900;
}

.preview-stage {
  position: relative;
  z-index: 1;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 24px;
  background: #020617;
}

.preview-video,
.preview-fallback {
  display: block;
  width: 100%;
  aspect-ratio: 9 / 16;
  max-height: min(68vh, 780px);
  object-fit: contain;
  background: #000;
}

.preview-fallback {
  position: relative;
  display: grid;
  place-items: center;
}

.preview-fallback img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.5;
  filter: blur(10px) saturate(1.2);
}

.preview-fallback__text {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 8px;
  padding: 18px;
  text-align: center;
}

.preview-fallback__text strong {
  font-size: 20px;
}

.preview-fallback__text span,
.preview-desc {
  color: #cbd5e1;
  line-height: 1.6;
}

.preview-info {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 14px;
  border-radius: 22px;
  background: rgba(15, 23, 42, 0.64);
}

.preview-info h2 {
  margin: 4px 0 0;
  font-size: 20px;
}

.preview-desc {
  margin: 0;
  font-size: 14px;
}

.preview-metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-metrics span {
  border-radius: 999px;
  padding: 7px 10px;
  background: rgba(34, 211, 238, 0.1);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 900;
}

.preview-empty {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 36px 16px;
}

@media (min-width: 860px) {
  .preview-hero {
    display: grid;
    grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }

  .preview-author {
    grid-column: 1 / -1;
  }

  .preview-info {
    margin-top: 0;
    min-height: 100%;
    align-content: start;
  }
}
</style>
