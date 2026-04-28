<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useIsMobile } from "@/composables/useIsMobile";
import MobileTabBar from "@/components/MobileTabBar.vue";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const { isMobile } = useIsMobile();

const NATIVE_ROUTE_NAMES = new Set([
  "native-feed",
  "native-discover",
  "native-create",
  "native-publish-preview",
  "native-hub",
  "messages",
  "direct-messages",
]);

const isNativeShell = computed(
  () => isMobile.value && typeof route.name === "string" && NATIVE_ROUTE_NAMES.has(route.name),
);

watch(
  [() => route.name, isMobile],
  ([n, mobile]) => {
    const on = mobile && typeof n === "string" && NATIVE_ROUTE_NAMES.has(n);
    document.documentElement.classList.toggle("native-shell-active", on);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  document.documentElement.classList.remove("native-shell-active");
  document.removeEventListener("visibilitychange", refreshSessionOnFocus);
});

/** 用户端主布局内始终保留底部 TabBar；断点由 TabBar 自身 CSS + main 底部留白媒体查询控制 */
const tabBarVisible = computed(() => {
  const n = route.name;
  return typeof n === "string";
});

/** 小屏顶栏：已登录时展示用户名（登录名），避免泛称「账号」 */
const headerAccountLabel = computed(() => {
  const u = auth.user;
  if (!u) return "账号";
  const name = (u.username || "").trim();
  if (name) return name.length > 12 ? `${name.slice(0, 12)}…` : name;
  const em = (u.email || "").trim();
  if (em) return em.length > 14 ? `${em.slice(0, 14)}…` : em;
  return "账号";
});

function refreshSessionOnFocus() {
  if (document.visibilityState !== "visible") return;
  if (!auth.token?.trim()) return;
  void auth.fetchMe().catch(() => {
    /* 令牌仍有效但 /me 失败时保留本地 token，由后续请求 401 再统一处理 */
  });
}

onMounted(() => {
  document.addEventListener("visibilitychange", refreshSessionOnFocus);
});

async function logout() {
  auth.logout();
  await router.push({ name: "home" });
}
</script>

<template>
  <el-container class="root main-layout" :class="{ 'main-layout--native': isNativeShell }">
    <el-header class="header">
      <RouterLink class="logo" to="/">恒频OM</RouterLink>
      <div class="header-m">
        <RouterLink v-if="!auth.isLoggedIn" class="header-m__link" :to="{ name: 'auth' }">登录</RouterLink>
        <RouterLink v-else class="header-m__link header-m__user" :to="{ name: 'profile' }" :title="auth.user?.username || auth.user?.email || ''">
          {{ headerAccountLabel }}
        </RouterLink>
      </div>
      <nav class="nav" aria-label="站点导航">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/videos">视频</RouterLink>
        <RouterLink to="/search">搜索</RouterLink>
        <RouterLink to="/learning-paths">学习路径</RouterLink>
        <template v-if="auth.isLoggedIn">
          <RouterLink to="/me">个人中心</RouterLink>
          <RouterLink to="/me/history">播放记录</RouterLink>
          <RouterLink to="/me/favorites">收藏</RouterLink>
          <el-button link type="primary" @click="logout">退出</el-button>
        </template>
        <RouterLink v-else to="/auth">登录</RouterLink>
      </nav>
    </el-header>
    <el-main class="main" :class="{ 'main--tabbar': tabBarVisible }">
      <RouterView />
    </el-main>
    <MobileTabBar :visible="tabBarVisible" :native-ui="isMobile" />
  </el-container>
</template>

<style scoped>
.root {
  min-height: 100%;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid var(--el-border-color);
}
.main-layout--native {
  background:
    radial-gradient(circle at 12% -8%, rgba(34, 211, 238, 0.22), transparent 30%),
    linear-gradient(180deg, #07111f 0%, #050506 62%, #081018 100%);
}
.main-layout--native .header {
  border-bottom-color: rgba(255, 255, 255, 0.07);
  background: #07111f;
  color: #e2e8f0;
}
.main-layout--native .logo,
.main-layout--native .header-m__link {
  color: #67e8f9;
}
.logo {
  font-weight: 700;
  text-decoration: none;
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.header-m {
  margin-left: auto;
  display: none;
}
.header-m__link {
  min-height: 40px;
  min-width: 44px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--el-color-primary);
  text-decoration: none;
}
.header-m__user {
  max-width: min(42vw, 160px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  justify-content: flex-end;
}
.nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}
.nav a {
  text-decoration: none;
  color: var(--el-text-color-regular);
}
.nav a.router-link-active {
  color: var(--el-color-primary);
  font-weight: 500;
}
.main {
  max-width: 1100px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

@media (max-width: 767px) {
  .header {
    gap: 12px;
    height: auto !important;
    min-height: 52px;
    padding: 10px 14px;
    padding-top: max(10px, env(safe-area-inset-top, 0px));
    flex-wrap: wrap;
    border-bottom-color: rgba(255, 255, 255, 0.07);
    background: #050506;
  }
  .main-layout--native .header {
    min-height: 42px;
    padding: 6px 16px;
    padding-top: max(6px, env(safe-area-inset-top, 0px));
  }
  .main-layout--native .logo {
    font-size: 15px;
  }
  .main-layout--native .header-m__link {
    min-height: 32px;
    padding: 0 4px;
    font-size: 13px;
  }
  .logo {
    font-size: 17px;
  }
  .header-m {
    display: flex;
  }
  .nav {
    display: none;
  }
  .main {
    padding: 12px 14px 16px;
    max-width: none;
    min-width: 0;
  }
  .main-layout--native .main {
    padding: 0 10px 10px;
  }
  .root,
  .main {
    background: #050506;
  }
  .main.main--tabbar {
    padding-bottom: calc(var(--h5-tabbar-height) + env(safe-area-inset-bottom, 0px) + 12px);
  }
  .main-layout--native .main.main--tabbar {
    padding-bottom: calc(var(--h5-tabbar-height) + env(safe-area-inset-bottom, 0px) + 6px);
  }
}
</style>
