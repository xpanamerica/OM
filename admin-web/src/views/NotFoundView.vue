<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="wrap">
    <el-result icon="warning" title="页面不存在" sub-title="该路径未配置，请从左侧菜单进入功能页。">
      <template #extra>
        <RouterLink to="/videos">
          <el-button type="primary">去视频管理</el-button>
        </RouterLink>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.wrap {
  padding: 48px 16px;
}
</style>
