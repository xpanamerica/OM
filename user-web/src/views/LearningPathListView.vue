<script setup lang="ts">
import { defineAsyncComponent, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useIsMobile } from "@/composables/useIsMobile";
import * as lpApi from "@/api/learningPaths";
import { formatApiError } from "@/util/errors";

const { isMobile } = useIsMobile();

const LearningPathListDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/LearningPathListDesktopTable.vue"),
);

const loading = ref(false);
const rows = ref<lpApi.LearningPathPublic[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await lpApi.listLearningPaths({
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
    <h2>学习路径</h2>
    <p class="hint">未登录仅展示已发布路径；登录后可见本人未发布路径（若有）。</p>

    <div v-loading="loading" class="list-wrap" :class="{ 'is-loading': loading }">
      <LearningPathListDesktopTable v-if="!isMobile" :rows="rows" />

      <ul v-else class="h5-card-list">
        <li v-for="row in rows" :key="row.id" class="h5-card-list__item">
          <div class="h5-card-list__title">
            <RouterLink class="link" :to="`/learning-paths/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
          </div>
          <div class="h5-card-list__meta">
            <span>{{ row.is_published ? "已发布" : "未发布" }}</span>
            <span v-if="row.updated_at">更新 {{ row.updated_at }}</span>
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
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.pager {
  margin-top: 12px;
}
</style>
