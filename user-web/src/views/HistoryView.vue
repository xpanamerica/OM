<script setup lang="ts">
import { defineAsyncComponent, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useIsMobile } from "@/composables/useIsMobile";
import * as usersApi from "@/api/users";
import { formatApiError } from "@/util/errors";

const { isMobile } = useIsMobile();

const HistoryDesktopTable = defineAsyncComponent(() => import("@/components/desktop/HistoryDesktopTable.vue"));

const loading = ref(false);
const rows = ref<usersApi.ViewRecordOut[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await usersApi.listMyViewRecords({
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
    <h2>历史记录</h2>

    <div v-loading="loading" class="list-wrap" :class="{ 'is-loading': loading }">
      <HistoryDesktopTable v-if="!isMobile" :rows="rows" />

      <ul v-else class="h5-card-list">
        <li v-for="row in rows" :key="row.id" class="h5-card-list__item">
          <div class="h5-card-list__title">
            <RouterLink class="link" :to="`/videos/${row.video_id}`">
              {{ row.video_title?.trim() || `视频 ${row.video_id}` }}
            </RouterLink>
          </div>
          <div class="h5-card-list__meta">
            <span>进度 {{ row.progress_seconds ?? 0 }} 秒</span>
            <span v-if="row.last_viewed_at">{{ row.last_viewed_at }}</span>
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
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.pager {
  margin-top: 12px;
}
</style>
