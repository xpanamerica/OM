<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useIsMobile } from "@/composables/useIsMobile";
import H5BackLink from "@/components/H5BackLink.vue";
import * as lpApi from "@/api/learningPaths";
import { formatApiError } from "@/util/errors";

const route = useRoute();
const { isMobile } = useIsMobile();
const id = computed(() => String(route.params.id));

const LearningPathDetailItemsDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/LearningPathDetailItemsDesktopTable.vue"),
);

const loading = ref(true);
const detail = ref<lpApi.LearningPathDetail | null>(null);

async function load() {
  loading.value = true;
  try {
    detail.value = await lpApi.getLearningPath(id.value);
  } catch (e) {
    detail.value = null;
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(id, load);
</script>

<template>
  <div v-loading="loading" class="lp-detail">
    <template v-if="detail">
      <H5BackLink :to="{ name: 'learning-paths' }" label="返回学习路径" />
      <h2>{{ detail.title ?? "（无标题）" }}</h2>
      <p class="meta">{{ detail.is_published ? "已发布" : "未发布" }}</p>
      <p v-if="detail.description" class="desc">{{ detail.description }}</p>
      <h3>条目</h3>

      <LearningPathDetailItemsDesktopTable v-if="!isMobile" :items="detail.items" />

      <ol v-else class="h5-card-list lp-items-m">
        <li v-for="row in detail.items" :key="`${row.order_index}-${row.video_id}`" class="h5-card-list__item">
          <div class="h5-card-list__row">
            <span class="lp-idx">#{{ row.order_index }}</span>
            <span v-if="row.note" class="h5-card-list__muted">{{ row.note }}</span>
          </div>
          <div class="h5-card-list__title">
            <RouterLink v-if="row.video" class="link" :to="`/videos/${row.video_id}`">
              {{ row.video.title ?? "（无标题）" }}
            </RouterLink>
            <span v-else class="muted">视频暂不可用（已下架或未发布）</span>
          </div>
        </li>
      </ol>
    </template>
  </div>
</template>

<style scoped>
.lp-detail h3 {
  margin-top: 20px;
  margin-bottom: 10px;
}
.meta {
  color: var(--el-text-color-secondary);
}
.desc {
  white-space: pre-wrap;
  line-height: 1.6;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.muted {
  color: var(--el-text-color-placeholder);
}
.lp-items-m {
  list-style: none;
  margin: 0;
  padding: 0;
}
.lp-idx {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

@media (max-width: 767px) {
  .lp-detail h2 {
    font-size: 20px;
    line-height: 1.35;
  }
}
</style>
