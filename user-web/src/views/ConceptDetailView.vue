<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, reactive, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useIsMobile } from "@/composables/useIsMobile";
import H5BackLink from "@/components/H5BackLink.vue";
import * as conceptsApi from "@/api/concepts";
import { formatConceptSegment } from "@/util/conceptSegment";
import { formatApiError } from "@/util/errors";

const route = useRoute();
const { isMobile } = useIsMobile();
const id = computed(() => String(route.params.id));

const ConceptVideosDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/ConceptVideosDesktopTable.vue"),
);

const loading = ref(true);
const row = ref<conceptsApi.ConceptPublic | null>(null);

const vLoading = ref(false);
const videos = ref<conceptsApi.ConceptLinkedVideo[]>([]);
const vTotal = ref(0);
const vPage = reactive({ offset: 0, limit: 20 });

async function load() {
  loading.value = true;
  try {
    row.value = await conceptsApi.getConcept(id.value);
  } catch (e) {
    row.value = null;
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function loadVideos() {
  vLoading.value = true;
  try {
    const { items, total } = await conceptsApi.listConceptVideos(id.value, {
      offset: vPage.offset,
      limit: vPage.limit,
    });
    videos.value = items;
    vTotal.value = total;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    vLoading.value = false;
  }
}

onMounted(async () => {
  await load();
  await loadVideos();
});
watch(id, async () => {
  vPage.offset = 0;
  await load();
  await loadVideos();
});
</script>

<template>
  <div v-loading="loading">
    <template v-if="row">
      <H5BackLink :to="{ name: 'home' }" label="返回首页" />
      <h2>{{ row.name ?? "（未命名）" }}</h2>
      <p v-if="row.description" class="desc">{{ row.description }}</p>
      <p class="meta">更新于 {{ row.updated_at }}</p>

      <h3 class="sub">关联视频</h3>
      <p class="hint">以下为已上线且与本概念绑定的稿件；若标注了片段时间，可在「片中范围」查看。</p>

      <el-empty v-if="!vLoading && vTotal === 0" description="暂无关联的已发布视频" />

      <p v-else-if="!vLoading && vTotal > 0 && vTotal <= vPage.limit" class="total-line">共 {{ vTotal }} 条</p>

      <template v-if="vLoading || vTotal > 0">
        <div v-loading="vLoading" class="list-wrap" :class="{ 'is-loading': vLoading }">
          <ConceptVideosDesktopTable v-if="!isMobile" :videos="videos" />

          <ul v-else class="h5-card-list">
            <li v-for="v in videos" :key="v.id" class="h5-card-list__item">
              <div class="h5-card-list__title">
                <RouterLink class="link" :to="`/videos/${v.id}`">{{ v.title ?? "（无标题）" }}</RouterLink>
              </div>
              <div class="h5-card-list__meta">
                <span>片中 {{ formatConceptSegment(v) }}</span>
                <span>{{ v.views_count ?? 0 }} 播放</span>
                <span v-if="v.published_at">{{ v.published_at }}</span>
              </div>
            </li>
          </ul>
        </div>

        <el-pagination
          v-if="vTotal > vPage.limit"
          :current-page="Math.floor(vPage.offset / vPage.limit) + 1"
          :page-size="vPage.limit"
          :total="vTotal"
          layout="total, prev, pager, next"
          class="pager"
          small
          @current-change="
            (p: number) => {
              vPage.offset = (p - 1) * vPage.limit;
              loadVideos();
            }
          "
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.desc {
  white-space: pre-wrap;
  line-height: 1.6;
}
.meta {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.sub {
  margin-top: 24px;
  margin-bottom: 8px;
}
.hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.pager {
  margin-top: 12px;
}
.total-line {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 8px;
}

@media (max-width: 767px) {
  h2 {
    font-size: 20px;
  }
}
</style>
