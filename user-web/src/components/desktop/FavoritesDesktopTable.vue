<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { VideoListItem } from "@/api/videos";

defineProps<{ rows: VideoListItem[] }>();
</script>

<template>
  <el-table :data="rows" border stripe size="small">
    <el-table-column label="标题" min-width="220">
      <template #default="{ row }">
        <RouterLink class="link" :to="`/videos/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
      </template>
    </el-table-column>
    <el-table-column prop="views_count" label="播放" width="80" />
  </el-table>
</template>

<style scoped>
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
