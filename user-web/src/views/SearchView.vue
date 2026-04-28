<script setup lang="ts">
import { defineAsyncComponent, onMounted, reactive, ref, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import * as searchApi from "@/api/search";
import type { VideoListItem } from "@/api/videos";
import { formatApiError } from "@/util/errors";
import { useIsMobile } from "@/composables/useIsMobile";

const route = useRoute();
const { isMobile } = useIsMobile();

const SearchResultsDesktopTable = defineAsyncComponent(() =>
  import("@/components/desktop/SearchResultsDesktopTable.vue"),
);

const loading = ref(false);
const list = ref<VideoListItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });
const form = reactive({
  keyword: "",
  sort_by: "latest" as "latest" | "views" | "likes",
});

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await searchApi.searchVideos({
      keyword: form.keyword || undefined,
      sort_by: form.sort_by,
      offset: page.offset,
      limit: page.limit,
    });
    list.value = items;
    total.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  const q = route.query.q;
  form.keyword = typeof q === "string" ? q : "";
  load();
});

watch(
  () => route.query.q,
  (q) => {
    form.keyword = typeof q === "string" ? q : "";
    page.offset = 0;
    load();
  },
);

function submit() {
  page.offset = 0;
  load();
}
</script>

<template>
  <div>
    <h2>搜索视频</h2>
    <el-form
      class="search-form"
      :inline="!isMobile"
      :label-position="isMobile ? 'top' : 'right'"
      label-width="72px"
      @submit.prevent="submit"
    >
      <el-form-item label="关键词">
        <el-input v-model="form.keyword" clearable placeholder="标题 / 描述" class="kw-input" />
      </el-form-item>
      <el-form-item label="排序">
        <el-select v-model="form.sort_by" class="sort-select">
          <el-option label="最新" value="latest" />
          <el-option label="播放" value="views" />
          <el-option label="点赞" value="likes" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit">搜索</el-button>
      </el-form-item>
    </el-form>

    <div v-loading="loading" class="list-wrap" :class="{ 'is-loading': loading }">
      <SearchResultsDesktopTable v-if="!isMobile" :list="list" />

      <ul v-else class="h5-card-list">
        <li v-for="row in list" :key="row.id" class="h5-card-list__item">
          <div class="h5-card-list__title">
            <RouterLink class="link" :to="`/videos/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
          </div>
          <div class="h5-card-list__meta">
            <span>{{ row.views_count ?? 0 }} 播放</span>
            <span>{{ row.likes_count ?? 0 }} 赞</span>
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
.kw-input {
  width: 260px;
}
.sort-select {
  width: 120px;
}

@media (max-width: 767px) {
  .kw-input,
  .sort-select {
    width: 100%;
  }
  .search-form :deep(.el-form-item) {
    margin-right: 0;
  }
}
</style>
