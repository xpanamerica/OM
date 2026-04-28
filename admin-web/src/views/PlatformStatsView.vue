<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const stats = ref<adminApi.AdminPlatformStats | null>(null);

async function load() {
  loading.value = true;
  try {
    stats.value = await adminApi.adminPlatformStats();
  } catch (e) {
    ElMessage.error(formatApiError(e));
    stats.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <el-button size="small" @click="load">刷新</el-button>
    <el-descriptions v-if="stats" border title="平台统计" :column="2" style="margin-top: 16px">
      <el-descriptions-item label="用户总数">{{ stats.users_total }}</el-descriptions-item>
      <el-descriptions-item label="视频总数">{{ stats.videos_total }}</el-descriptions-item>
      <el-descriptions-item label="已发布视频">{{ stats.videos_published }}</el-descriptions-item>
      <el-descriptions-item label="待审核视频">{{ stats.videos_pending_review }}</el-descriptions-item>
      <el-descriptions-item label="播放量合计">{{ stats.total_views_count }}</el-descriptions-item>
      <el-descriptions-item label="点赞合计">{{ stats.total_likes_count }}</el-descriptions-item>
      <el-descriptions-item label="收藏合计">{{ stats.total_favorites_count }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>
