<script setup lang="ts">
import { onMounted } from "vue";
import { RouterView } from "vue-router";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { scheduleIdleRoutePrefetch } from "@/util/idlePrefetchRoutes";

onMounted(() => {
  scheduleIdleRoutePrefetch();
});
</script>

<template>
  <a class="skip-to-main" href="#main-content">跳到主要内容</a>
  <el-config-provider :locale="zhCn">
    <div id="main-content" class="main-content-root" tabindex="-1">
      <RouterView />
    </div>
  </el-config-provider>
</template>

<style>
html {
  box-sizing: border-box;
}
*,
*::before,
*::after {
  box-sizing: inherit;
}
html,
body,
#app {
  height: 100%;
  margin: 0;
}
/* H5：避免长词、表格残留或子元素 margin 导致整页横向拖动 */
#app {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
}

/* 键盘用户：跳过导航直达主内容（WCAG 2.4.1） */
.skip-to-main {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.skip-to-main:focus {
  position: fixed;
  left: 12px;
  top: max(12px, env(safe-area-inset-top, 0px));
  z-index: 10000;
  clip: auto;
  width: auto;
  height: auto;
  margin: 0;
  padding: 12px 18px;
  overflow: visible;
  white-space: normal;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  outline: none;
}
.skip-to-main:focus-visible {
  outline: 3px solid #fff;
  outline-offset: 2px;
}
.main-content-root {
  outline: none;
}
</style>
