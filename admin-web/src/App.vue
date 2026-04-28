<script setup lang="ts">
import { RouterView } from "vue-router";
import zhCn from "element-plus/es/locale/lang/zh-cn";
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
#app {
  min-height: 100%;
}
.skip-to-main {
  position: absolute;
  left: -9999px;
  top: auto;
  width: 1px;
  height: 1px;
  overflow: hidden;
}
.skip-to-main:focus {
  position: fixed;
  left: 12px;
  top: 12px;
  z-index: 9999;
  width: auto;
  height: auto;
  padding: 10px 14px;
  background: #1f2937;
  color: #fff;
  border-radius: 6px;
  text-decoration: none;
  font-size: 14px;
}
</style>
