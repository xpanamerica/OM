<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import { formatApiError } from "@/util/errors";
import { useIsMobile } from "@/composables/useIsMobile";
import MobileTabBar from "@/components/MobileTabBar.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const { isMobile } = useIsMobile();

const tab = ref<"login" | "register">("login");
const loading = ref(false);

const loginForm = reactive({ username: "", password: "" });
const regForm = reactive({ email: "", username: "", password: "" });

async function onLogin() {
  loading.value = true;
  try {
    await auth.login(loginForm.username, loginForm.password);
    const r = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(r || "/");
    ElMessage.success("登录成功");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function onRegister() {
  loading.value = true;
  try {
    await auth.registerAndHintLogin({
      email: regForm.email,
      username: regForm.username,
      password: regForm.password,
    });
    ElMessage.success("注册成功，请登录");
    tab.value = "login";
    loginForm.username = regForm.username;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-shell">
    <div class="wrap auth-page">
      <el-card class="card auth-card">
        <el-tabs v-model="tab">
          <el-tab-pane label="登录" name="login">
            <el-form
              :label-position="isMobile ? 'top' : 'right'"
              :label-width="isMobile ? undefined : '96px'"
              @submit.prevent="onLogin"
            >
              <el-form-item label="用户名或邮箱">
                <el-input v-model="loginForm.username" autocomplete="username" placeholder="用户名或邮箱" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="loginForm.password" type="password" show-password autocomplete="current-password" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" native-type="submit" :loading="loading">登录</el-button>
                <el-button @click="router.push('/')">返回首页</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="注册" name="register">
            <el-form
              :label-position="isMobile ? 'top' : 'right'"
              :label-width="isMobile ? undefined : '72px'"
              @submit.prevent="onRegister"
            >
              <el-form-item label="邮箱">
                <el-input v-model="regForm.email" type="email" autocomplete="email" />
              </el-form-item>
              <el-form-item label="用户名">
                <el-input v-model="regForm.username" autocomplete="username" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="regForm.password" type="password" show-password autocomplete="new-password" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" native-type="submit" :loading="loading">注册</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
    <MobileTabBar :visible="isMobile" :native-ui="isMobile" />
  </div>
</template>

<style scoped>
.wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  padding: 24px;
}
.card {
  width: 420px;
  max-width: 100%;
}
@media (max-width: 767px) {
  .auth-shell {
    min-height: 100%;
    background: #f5f7fa;
  }
  .wrap {
    min-height: 100%;
    padding-bottom: calc(var(--h5-tabbar-height) + env(safe-area-inset-bottom, 0px) + 16px);
  }
}
</style>
