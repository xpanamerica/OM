<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { VideoListItem } from "@/api/videos";
import { resolveApiAssetUrl } from "@/util/resolveApiAssetUrl";

defineProps<{ rows: VideoListItem[] }>();
</script>

<template>
  <el-table :data="rows" border stripe size="small">
    <el-table-column label="封面" width="100">
      <template #default="{ row }">
        <el-image
          v-if="resolveApiAssetUrl(row.cover_url)"
          class="tbl-cover"
          :src="resolveApiAssetUrl(row.cover_url)"
          fit="cover"
          lazy
        />
        <span v-else class="tbl-cover-ph">—</span>
      </template>
    </el-table-column>
    <el-table-column label="标题" min-width="220">
      <template #default="{ row }">
        <RouterLink class="link" :to="`/videos/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
      </template>
    </el-table-column>
    <el-table-column prop="views_count" label="播放" width="80" />
    <el-table-column prop="likes_count" label="点赞" width="80" />
    <el-table-column prop="created_at" label="创建时间" width="170" />
  </el-table>
</template>

<style scoped>
.tbl-cover {
  width: 72px;
  height: 40px;
  border-radius: 4px;
}
.tbl-cover-ph {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
