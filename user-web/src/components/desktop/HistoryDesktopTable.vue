<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { ViewRecordOut } from "@/api/users";

defineProps<{ rows: ViewRecordOut[] }>();
</script>

<template>
  <el-table :data="rows" border stripe size="small">
    <el-table-column label="视频" min-width="240">
      <template #default="{ row }">
        <RouterLink class="link" :to="`/videos/${row.video_id}`">
          {{ row.video_title?.trim() || `视频 ${row.video_id}` }}
        </RouterLink>
      </template>
    </el-table-column>
    <el-table-column prop="progress_seconds" label="进度(秒)" width="100" />
    <el-table-column prop="last_viewed_at" label="最近观看" width="180" />
  </el-table>
</template>

<style scoped>
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
