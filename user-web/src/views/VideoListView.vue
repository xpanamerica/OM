<script setup lang="ts">
import { defineAsyncComponent, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useIsMobile } from "@/composables/useIsMobile";
import * as videosApi from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

const { isMobile } = useIsMobile();

const VideoListDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/VideoListDesktopTable.vue"),
);

const loading = ref(false);
const rows = ref<videosApi.VideoListItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await videosApi.listVideos({
      offset: page.offset,
      limit: page.limit,
    });
    rows.value = items;
    total.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <h2>视频</h2>
    <p class="hint">列表由后端按身份过滤；未登录仅展示已发布内容。</p>

    <div v-loading="loading" class="list-wrap" :class="{ 'is-loading': loading }">
      <VideoListDesktopTable v-if="!isMobile" :rows="rows" />

      <ul v-else class="h5-card-list">
        <li v-for="row in rows" :key="row.id" class="h5-card-list__item">
          <RouterLink v-if="resolveApiAssetUrl(row.cover_url)" class="h5-card-list__media" :to="`/videos/${row.id}`">
            <img class="h5-card-list__cover" :src="resolveApiAssetUrl(row.cover_url)" :alt="row.title ?? ''" loading="lazy" />
          </RouterLink>
          <div class="h5-card-list__title">
            <RouterLink class="link" :to="`/videos/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
          </div>
          <div class="h5-card-list__meta">
            <span>{{ row.views_count ?? 0 }} 播放</span>
            <span>{{ row.likes_count ?? 0 }} 赞</span>
            <span v-if="row.created_at">{{ row.created_at }}</span>
          </div>
        </li>
      </ul>
    </div>

    <el-pagination
      :current-page="Math.floor(page.offset / page.limit) + 1"
      :page-size="page.limit"
      :total="total"
      layout="total, prev, pager, next"
      class="pager"
      small
      @current-change="
        (p: number) => {
          page.offset = (p - 1) * page.limit;
          load();
        }
      "
    />
  </div>
</template>

<style scoped>
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.h5-card-list__media {
  display: block;
  margin: 0 0 8px;
  border-radius: 6px;
  overflow: hidden;
}
.h5-card-list__cover {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  display: block;
  background: #0f172a;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.pager {
  margin-top: 12px;
}
</style>
