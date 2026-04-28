<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const auth = useAuthStore();

withDefaults(defineProps<{ visible: boolean; nativeUi?: boolean }>(), { nativeUi: false });

const tab = computed(() => {
  const n = route.name;
  if (n === "native-feed" || n === "home" || n === "videos" || n === "video-detail") return "feed";
  if (
    n === "native-discover" ||
    n === "search" ||
    n === "learning-paths" ||
    n === "learning-path-detail" ||
    n === "concept-detail"
  )
    return "discover";
  if (n === "native-create" || n === "native-publish-preview") return "create";
  if (n === "messages" || n === "direct-messages") return "messages";
  if (n === "native-hub" || n === "profile" || n === "history" || n === "favorites" || n === "user-profile") return "hub";
  return "";
});

const createTo = computed(() =>
  auth.isLoggedIn ? { name: "native-create" as const } : { name: "auth" as const, query: { redirect: "/create" } },
);

const messagesTo = computed(() =>
  auth.isLoggedIn ? { name: "messages" as const } : { name: "auth" as const, query: { redirect: "/me/messages" } },
);

function ariaPage(on: boolean): "page" | undefined {
  return on ? "page" : undefined;
}
</script>

<template>
  <nav v-show="visible" class="m-tabbar m-tabbar--xhs" :class="{ 'm-tabbar--native': nativeUi }" aria-label="主导航">
    <div class="m-tabbar__side">
      <RouterLink
        class="m-tab"
        :class="{ 'm-tab--on': tab === 'feed' }"
        :to="{ name: 'native-feed' }"
        :aria-current="ariaPage(tab === 'feed')"
      >
        <svg class="m-tab__svg" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8h5z" />
        </svg>
        <span class="m-tab__txt">首页</span>
      </RouterLink>
      <RouterLink
        class="m-tab"
        :class="{ 'm-tab--on': tab === 'discover' }"
        :to="{ name: 'native-discover' }"
        :aria-current="ariaPage(tab === 'discover')"
      >
        <svg class="m-tab__svg" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 10.9c-.61 0-1.1.49-1.1 1.1s.49 1.1 1.1 1.1 1.1-.49 1.1-1.1-.49-1.1-1.1-1.1zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm2.19 12.19L6 18l3.81-8.19L18 6l-3.81 8.19z"
          />
        </svg>
        <span class="m-tab__txt">发现</span>
      </RouterLink>
    </div>

    <div class="m-tabbar__fab-wrap">
      <RouterLink class="m-tab-fab" :to="createTo" :aria-current="ariaPage(tab === 'create')" aria-label="创作">
        <span class="m-tab-fab__plus">+</span>
      </RouterLink>
    </div>

    <div class="m-tabbar__side">
      <RouterLink
        class="m-tab"
        :class="{ 'm-tab--on': tab === 'messages' }"
        :to="messagesTo"
        :aria-current="ariaPage(tab === 'messages')"
      >
        <svg class="m-tab__svg" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="currentColor"
            d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"
          />
        </svg>
        <span class="m-tab__txt">消息</span>
      </RouterLink>
      <RouterLink
        class="m-tab"
        :class="{ 'm-tab--on': tab === 'hub' }"
        :to="{ name: 'native-hub' }"
        :aria-current="ariaPage(tab === 'hub')"
      >
        <svg class="m-tab__svg" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"
          />
        </svg>
        <span class="m-tab__txt">个人</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.m-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  box-sizing: border-box;
  background: var(--el-bg-color);
  background: color-mix(in srgb, var(--el-bg-color) 94%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.07);
}

.m-tabbar--xhs {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  justify-content: space-between;
  padding: 6px 4px calc(6px + env(safe-area-inset-bottom, 0px));
  min-height: calc(var(--h5-tabbar-height) + env(safe-area-inset-bottom, 0px));
}

.m-tabbar__side {
  flex: 1;
  display: flex;
  flex-direction: row;
  justify-content: space-around;
  align-items: flex-end;
  gap: 4px;
}

.m-tabbar__fab-wrap {
  width: 72px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  padding-bottom: 2px;
}

.m-tab-fab {
  width: 52px;
  height: 44px;
  border-radius: 14px;
  background: var(--native-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(34, 211, 238, 0.38);
  -webkit-tap-highlight-color: transparent;
}

.m-tab-fab:active {
  opacity: 0.92;
}

.m-tab-fab__plus {
  font-size: 30px;
  font-weight: 300;
  line-height: 1;
  margin-top: -2px;
}

.m-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-height: 48px;
  padding: 4px 2px;
  text-decoration: none;
  color: var(--el-text-color-secondary);
  font-size: 10px;
  font-weight: 600;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  box-sizing: border-box;
}

.m-tab:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
  border-radius: 10px;
  z-index: 1;
}

.m-tab:active {
  opacity: 0.88;
}

.m-tab--on {
  color: var(--native-accent);
  font-weight: 800;
}

.m-tab__svg {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  opacity: 0.92;
}

.m-tab__txt {
  line-height: 1.15;
  letter-spacing: 0.02em;
}

@media (min-width: 768px) {
  .m-tabbar {
    display: none !important;
  }
}
</style>
