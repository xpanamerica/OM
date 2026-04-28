<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { ConceptLinkedVideo } from "@/api/concepts";
import { formatConceptSegment } from "@/util/conceptSegment";

defineProps<{ videos: ConceptLinkedVideo[] }>();
</script>

<template>
  <el-table :data="videos" border stripe size="small">
    <el-table-column label="标题" min-width="200">
      <template #default="{ row: v }">
        <RouterLink class="link" :to="`/videos/${v.id}`">{{ v.title ?? "（无标题）" }}</RouterLink>
      </template>
    </el-table-column>
    <el-table-column label="片中范围" width="140" align="center">
      <template #default="{ row: v }">{{ formatConceptSegment(v) }}</template>
    </el-table-column>
    <el-table-column prop="views_count" label="播放" width="80" />
    <el-table-column prop="published_at" label="发布时间" width="170" />
  </el-table>
</template>

<style scoped>
.link {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
