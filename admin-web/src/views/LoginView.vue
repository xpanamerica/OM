<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import { formatApiError } from "@/util/errors";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const loading = ref(false);
/** 两项拆成独立 ref，且不用 el-form：避免 Element Plus Form 在嵌入式 WebView（如 Cursor Simple Browser）里切换焦点时错误重置字段。 */
const username = ref("");
const password = ref("");

async function onSubmit() {
  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect || "/");
    ElMessage.success("登录成功");
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="wrap">
    <el-card class="card" shadow="hover">
      <template #header>管理后台登录</template>
      <!-- 原生 form：不用 el-form / el-form-item，减轻 WebView 与字段注册交互问题 -->
      <form class="login-form" autocomplete="on" @submit.prevent="onSubmit">
        <div class="row">
          <label class="label" for="admin-login-username">用户名或邮箱</label>
          <el-input
            id="admin-login-username"
            v-model="username"
            name="username"
            type="text"
            autocomplete="username"
            placeholder="用户名或邮箱"
            spellcheck="false"
            input-style="width: 100%"
          />
        </div>
        <div class="row">
          <label class="label" for="admin-login-password">密码</label>
          <el-input
            id="admin-login-password"
            v-model="password"
            name="password"
            type="password"
            show-password
            autocomplete="current-password"
            spellcheck="false"
            input-style="width: 100%"
          />
        </div>
        <div class="actions">
          <el-button type="primary" native-type="submit" :loading="loading">登录</el-button>
        </div>
      </form>
    </el-card>
  </div>
</template>

<style scoped>
.wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.card {
  width: 400px;
}
.login-form {
  margin: 0;
}
.row {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}
.label {
  flex: 0 0 96px;
  padding-right: 8px;
  font-size: 14px;
  color: #606266;
  line-height: 32px;
}
.row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}
.actions {
  padding-left: 96px;
}
</style>
