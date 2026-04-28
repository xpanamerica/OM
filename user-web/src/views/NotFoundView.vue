<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>

<template>
  <div class="wrap not-found-page">
    <el-result icon="warning" title="页面不存在" sub-title="请检查链接是否正确，或返回首页继续浏览。">
      <template #extra>
        <RouterLink to="/">
          <el-button type="primary">回首页</el-button>
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
