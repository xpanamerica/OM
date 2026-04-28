<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { LearningPathItem } from "@/api/learningPaths";

defineProps<{ items: LearningPathItem[] }>();
</script>

<template>
  <el-table :data="items" border size="small">
    <el-table-column prop="order_index" label="#" width="56" />
    <el-table-column label="视频" min-width="220">
      <template #default="{ row }">
        <RouterLink v-if="row.video" class="link" :to="`/videos/${row.video_id}`">
          {{ row.video.title }}
        </RouterLink>
        <span v-else class="muted">视频暂不可用（已下架或未发布）</span>
      </template>
    </el-table-column>
    <el-table-column prop="note" label="备注" show-overflow-tooltip />
  </el-table>
</template>

<style scoped>
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.muted {
  color: var(--el-text-color-placeholder);
}
</style>
