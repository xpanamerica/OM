<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import axios from "axios";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import * as authApi from "@/api/auth";
import { formatApiError } from "@/util/errors";
import { useIsMobile } from "@/composables/useIsMobile";
import MobileTabBar from "@/components/MobileTabBar.vue";
import TurnstileWidget from "@/components/TurnstileWidget.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const { isMobile } = useIsMobile();

const tab = ref<"login" | "register">("login");
const loading = ref(false);
const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY?.trim() ?? "";

const loginForm = reactive({ username: "", password: "" });
const mfaForm = reactive({ code: "" });
const regForm = reactive({ email: "", username: "", password: "", invite_code: "" });
const inviteRequired = ref(false);
const mfaChallengeToken = ref("");
const mfaSetupRequired = ref(false);
const mfaSetup = ref<authApi.MfaSetup | null>(null);
const loginFailedCount = ref(0);
const loginTurnstileToken = ref("");
const registerTurnstileToken = ref("");
const loginTurnstile = ref<InstanceType<typeof TurnstileWidget> | null>(null);
const registerTurnstile = ref<InstanceType<typeof TurnstileWidget> | null>(null);
const showLoginTurnstile = computed(() => loginFailedCount.value >= 3);

function requireTurnstileToken(token: string) {
  if (!turnstileSiteKey) {
    ElMessage.error("人机验证暂未配置，请联系管理员。");
    return false;
  }
  if (!token) {
    ElMessage.error("请先完成人机验证。");
    return false;
  }
  return true;
}

function apiErrorCode(err: unknown): string | null {
  if (!axios.isAxiosError(err)) return null;
  const code = (err.response?.data as { code?: unknown } | undefined)?.code;
  return typeof code === "string" ? code : null;
}

async function loadRegistrationOptions() {
  try {
    const o = await authApi.fetchRegistrationOptions();
    inviteRequired.value = o.invite_code_required;
  } catch {
    inviteRequired.value = false;
  }
}

async function onLogin() {
  if (showLoginTurnstile.value && !requireTurnstileToken(loginTurnstileToken.value)) {
    return;
  }
  loading.value = true;
  try {
    const result = await auth.login(loginForm.username, loginForm.password, showLoginTurnstile.value ? loginTurnstileToken.value : undefined);
    if (result?.mfa_required) {
      mfaChallengeToken.value = result.mfa_challenge_token || "";
      mfaSetupRequired.value = Boolean(result.mfa_setup_required);
      if (mfaSetupRequired.value) {
        mfaSetup.value = await authApi.startMfaSetup(mfaChallengeToken.value);
      }
      ElMessage.info(mfaSetupRequired.value ? "请先启用 MFA 后完成登录" : "请输入 MFA 验证码");
      return;
    }
    loginFailedCount.value = 0;
    loginTurnstileToken.value = "";
    const r = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(r || "/");
    ElMessage.success("登录成功");
  } catch (e) {
    const code = apiErrorCode(e);
    if (code === "TURNSTILE_REQUIRED" || code === "TURNSTILE_INVALID") {
      loginFailedCount.value = Math.max(loginFailedCount.value, 3);
    } else {
      loginFailedCount.value += 1;
    }
    loginTurnstileToken.value = "";
    loginTurnstile.value?.reset();
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function onMfaSubmit() {
  if (!mfaChallengeToken.value || !mfaForm.code.trim()) return;
  loading.value = true;
  try {
    if (mfaSetupRequired.value) {
      const enabled = await authApi.enableMfa(mfaForm.code.trim(), mfaChallengeToken.value);
      if (enabled.recovery_codes.length) {
        ElMessage.success(`MFA 已启用，请保存恢复码：${enabled.recovery_codes.join(" ")}`);
      }
    }
    await auth.verifyMfaLogin(mfaChallengeToken.value, mfaForm.code.trim());
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
  if (!requireTurnstileToken(registerTurnstileToken.value)) {
    return;
  }
  loading.value = true;
  try {
    const body: authApi.RegisterBody = {
      email: regForm.email,
      username: regForm.username,
      password: regForm.password,
      turnstile_token: registerTurnstileToken.value,
    };
    const ic = regForm.invite_code.trim();
    if (ic) {
      body.invite_code = ic;
    }
    await auth.registerAndHintLogin(body);
    ElMessage.success("注册已提交，请等待后台验证通过后再登录");
    tab.value = "login";
    loginForm.username = regForm.username;
    registerTurnstileToken.value = "";
    registerTurnstile.value?.reset();
  } catch (e) {
    registerTurnstileToken.value = "";
    registerTurnstile.value?.reset();
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

watch(
  () => loginForm.username,
  () => {
    loginFailedCount.value = 0;
    loginTurnstileToken.value = "";
    loginTurnstile.value?.reset();
  },
);

onMounted(() => {
  void loadRegistrationOptions();
});
</script>

<template>
  <div class="auth-shell">
    <div class="wrap auth-page">
      <el-card class="card auth-card">
        <el-tabs v-model="tab" @tab-change="(name: string | number) => name === 'register' && void loadRegistrationOptions()">
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
              <template v-if="mfaChallengeToken">
                <el-alert
                  v-if="mfaSetupRequired && mfaSetup"
                  class="mfa-alert"
                  type="warning"
                  :closable="false"
                  title="管理员需要先启用 MFA"
                >
                  <p>请用认证器 App 扫描或手动输入密钥：</p>
                  <p class="mfa-secret">{{ mfaSetup.secret }}</p>
                  <p class="mfa-uri">{{ mfaSetup.otpauth_uri }}</p>
                </el-alert>
                <el-form-item label="MFA 验证码">
                  <el-input v-model="mfaForm.code" autocomplete="one-time-code" placeholder="6 位验证码或恢复码" />
                </el-form-item>
              </template>
              <el-form-item v-if="showLoginTurnstile" label="验证">
                <TurnstileWidget
                  v-if="turnstileSiteKey"
                  ref="loginTurnstile"
                  :sitekey="turnstileSiteKey"
                  action="login"
                  @verified="(token) => (loginTurnstileToken = token)"
                  @expired="loginTurnstileToken = ''"
                  @error="loginTurnstileToken = ''"
                />
                <p v-else class="reg-hint">人机验证暂未配置，请联系管理员。</p>
              </el-form-item>
              <el-form-item>
                <el-button v-if="!mfaChallengeToken" type="primary" native-type="submit" :loading="loading">登录</el-button>
                <el-button v-else type="primary" :loading="loading" @click="onMfaSubmit">完成 MFA 登录</el-button>
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
              <el-form-item label="邀请码">
                <el-input
                  v-model="regForm.invite_code"
                  autocomplete="off"
                  :placeholder="inviteRequired ? '内测必填' : '内测选填（平台开启校验时必填）'"
                />
                <p v-if="inviteRequired" class="reg-hint">当前为内测阶段，注册需要有效邀请码。</p>
              </el-form-item>
              <el-form-item label="验证">
                <TurnstileWidget
                  v-if="turnstileSiteKey"
                  ref="registerTurnstile"
                  :sitekey="turnstileSiteKey"
                  action="register"
                  @verified="(token) => (registerTurnstileToken = token)"
                  @expired="registerTurnstileToken = ''"
                  @error="registerTurnstileToken = ''"
                />
                <p v-else class="reg-hint">人机验证暂未配置，请联系管理员。</p>
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
.reg-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.mfa-alert {
  margin-bottom: 16px;
}
.mfa-secret,
.mfa-uri {
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
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
