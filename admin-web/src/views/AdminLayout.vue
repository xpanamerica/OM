<script setup lang="ts">
import { computed } from "vue";
import { isNavigationFailure, NavigationFailureType, useRouter, useRoute, RouterView } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const active = computed(() => route.path);

const pageTitle = computed(() => {
  const last = route.matched[route.matched.length - 1];
  return (last?.meta?.title as string) || "";
});

/** 显式跳转：避免依赖 el-menu 内置 router（部分环境下 $router 与 push 行为不一致导致「点了没反应」） */
function onSideMenuSelect(index: string) {
  void router.push(index).catch((err: unknown) => {
    if (isNavigationFailure(err, NavigationFailureType.duplicated)) return;
    console.error("[admin-nav]", err);
  });
}

async function logout() {
  auth.logout();
  await router.replace({ name: "login" });
}
</script>

<template>
  <el-container class="layout">
    <el-aside class="aside" width="200px">
      <div class="brand">管理后台</div>
      <el-menu :default-active="active" mode="vertical" @select="onSideMenuSelect">
        <el-menu-item index="/videos">视频管理</el-menu-item>
        <el-menu-item index="/review">视频审核</el-menu-item>
        <el-menu-item index="/taxonomy">分类 / 标签</el-menu-item>
        <el-menu-item index="/concepts">概念</el-menu-item>
        <el-menu-item index="/learning-paths">学习路径</el-menu-item>
        <el-menu-item index="/users">用户</el-menu-item>
        <el-menu-item index="/stats">平台统计</el-menu-item>
        <el-menu-item index="/settings">平台设置</el-menu-item>
        <el-menu-item index="/invite-codes">内测邀请码</el-menu-item>
        <el-menu-item index="/registration-audit">注册审计</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="title">{{ pageTitle }}</span>
        <span class="spacer" />
        <span class="user">{{ auth.user?.username }}</span>
        <el-button link type="primary" @click="logout">退出</el-button>
      </el-header>
      <el-main>
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}
.brand {
  padding: 16px;
  font-weight: 600;
  border-bottom: 1px solid var(--el-border-color);
}
.header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color);
}
.layout :deep(.el-main) {
  min-width: 0;
}
.title {
  font-weight: 500;
}
.spacer {
  flex: 1;
}
.user {
  margin-right: 12px;
  color: var(--el-text-color-secondary);
}
</style>
