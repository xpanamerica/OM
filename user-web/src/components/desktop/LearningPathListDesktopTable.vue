<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { LearningPathPublic } from "@/api/learningPaths";

defineProps<{ rows: LearningPathPublic[] }>();
</script>

<template>
  <el-table :data="rows" border stripe size="small">
    <el-table-column label="标题" min-width="200">
      <template #default="{ row }">
        <RouterLink class="link" :to="`/learning-paths/${row.id}`">{{ row.title ?? "（无标题）" }}</RouterLink>
      </template>
    </el-table-column>
    <el-table-column label="发布" width="80">
      <template #default="{ row }">{{ row.is_published ? "是" : "否" }}</template>
    </el-table-column>
    <el-table-column prop="updated_at" label="更新" width="170" />
  </el-table>
</template>

<style scoped>
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
