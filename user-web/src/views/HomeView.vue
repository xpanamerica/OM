<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as videosApi from "@/api/videos";
import type { VideoListItem } from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";
import HomeImmersivePlayerOverlay from "@/components/home/HomeImmersivePlayerOverlay.vue";

const latest = ref<videosApi.VideoListItem[]>([]);
const loading = ref(true);

const feedOpen = ref(false);
const feedItem = ref<VideoListItem | null>(null);

function openFeed(it: VideoListItem) {
  feedItem.value = it;
  feedOpen.value = true;
}

watch(feedOpen, (v) => {
  if (!v) feedItem.value = null;
});

onMounted(async () => {
  loading.value = true;
  try {
    const v = await videosApi.listLatestVideos({ offset: 0, limit: 30 });
    latest.value = v.items;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-loading="loading" class="home" :class="{ 'is-loading': loading }">
    <section class="sec">
      <h2 class="sec__h">最新视频</h2>
      <div class="video-grid">
        <el-card v-for="x in latest" :key="x.id" shadow="hover" class="card">
          <button
            type="button"
            class="card-media"
            :aria-label="`播放：${x.title ?? '视频'}`"
            @click="openFeed(x)"
          >
            <img
              v-if="resolveApiAssetUrl(x.cover_url)"
              class="card-cover"
              :src="resolveApiAssetUrl(x.cover_url)"
              :alt="x.title ?? ''"
              loading="lazy"
            />
            <div v-else class="card-cover card-cover--ph" aria-hidden="true" />
          </button>
          <RouterLink class="title" :to="`/videos/${x.id}`">{{ x.title ?? "（无标题）" }}</RouterLink>
          <div class="meta">{{ x.views_count ?? 0 }} 次播放</div>
        </el-card>
      </div>
    </section>

    <HomeImmersivePlayerOverlay v-model="feedOpen" :item="feedItem" />
  </div>
</template>

<style scoped>
.home {
  padding-bottom: 4px;
}
.sec {
  margin-top: 8px;
}
.sec:first-child {
  margin-top: 0;
}
.sec__h {
  font-size: 18px;
  margin: 0 0 12px;
  font-weight: 600;
}
.video-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}
.card {
  margin-bottom: 0;
}
.card :deep(.el-card__body) {
  padding: 8px;
}
.card-media {
  display: block;
  width: calc(100% + 16px);
  margin: -8px -8px 6px;
  padding: 0;
  border: none;
  border-radius: 4px 4px 0 0;
  overflow: hidden;
  cursor: pointer;
  background: none;
  text-align: left;
  font: inherit;
  color: inherit;
}
.card-media:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.card-cover {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  display: block;
  background: #0f172a;
}
.card-cover--ph {
  min-height: 72px;
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #312e81 100%);
}
.title {
  font-weight: 500;
  text-decoration: none;
  color: var(--el-color-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.35;
  word-break: break-word;
}
.meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

@media (min-width: 768px) {
  .video-grid {
    gap: 12px;
  }
  .card :deep(.el-card__body) {
    padding: 12px;
  }
  .card-media {
    width: calc(100% + 24px);
    margin: -12px -12px 8px;
  }
  .title {
    font-size: 13px;
  }
  .meta {
    font-size: 12px;
  }
}
</style>
