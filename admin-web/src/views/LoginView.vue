<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import axios from "axios";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import * as authApi from "@/api/auth";
import { formatApiError } from "@/util/errors";
import TurnstileWidget from "@/components/TurnstileWidget.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const loading = ref(false);
const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY?.trim() ?? "";
/** 两项拆成独立 ref，且不用 el-form：避免 Element Plus Form 在嵌入式 WebView（如 Cursor Simple Browser）里切换焦点时错误重置字段。 */
const username = ref("");
const password = ref("");
const mfaCode = ref("");
const mfaChallengeToken = ref("");
const mfaSetupRequired = ref(false);
const mfaSetup = ref<authApi.MfaSetup | null>(null);
const failedCount = ref(0);
const turnstileToken = ref("");
const turnstile = ref<InstanceType<typeof TurnstileWidget> | null>(null);
const showTurnstile = computed(() => failedCount.value >= 3);

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

async function onSubmit() {
  if (showTurnstile.value && !requireTurnstileToken(turnstileToken.value)) {
    return;
  }
  loading.value = true;
  try {
    const result = await auth.login(username.value.trim(), password.value, showTurnstile.value ? turnstileToken.value : undefined);
    if (result?.mfa_required) {
      mfaChallengeToken.value = result.mfa_challenge_token || "";
      mfaSetupRequired.value = Boolean(result.mfa_setup_required);
      if (mfaSetupRequired.value) {
        mfaSetup.value = await authApi.startMfaSetup(mfaChallengeToken.value);
      }
      ElMessage.info(mfaSetupRequired.value ? "管理员需要先启用 MFA" : "请输入 MFA 验证码");
      return;
    }
    failedCount.value = 0;
    turnstileToken.value = "";
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect || "/");
    ElMessage.success("登录成功");
  } catch (e: unknown) {
    const code = apiErrorCode(e);
    if (code === "TURNSTILE_REQUIRED" || code === "TURNSTILE_INVALID") {
      failedCount.value = Math.max(failedCount.value, 3);
    } else {
      failedCount.value += 1;
    }
    turnstileToken.value = "";
    turnstile.value?.reset();
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function onMfaSubmit() {
  loading.value = true;
  try {
    if (mfaSetupRequired.value) {
      const enabled = await authApi.enableMfa(mfaCode.value.trim(), mfaChallengeToken.value);
      if (enabled.recovery_codes.length) {
        ElMessage.success(`MFA 已启用，请保存恢复码：${enabled.recovery_codes.join(" ")}`);
      }
    }
    await auth.verifyMfaLogin(mfaChallengeToken.value, mfaCode.value.trim());
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect || "/");
    ElMessage.success("登录成功");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

watch(username, () => {
  failedCount.value = 0;
  turnstileToken.value = "";
  turnstile.value?.reset();
});
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
        <div v-if="mfaChallengeToken" class="row">
          <label class="label" for="admin-login-mfa">MFA</label>
          <div class="turnstile-cell">
            <el-alert
              v-if="mfaSetupRequired && mfaSetup"
              type="warning"
              :closable="false"
              title="首次登录管理后台需启用 MFA"
            >
              <p>认证器密钥：{{ mfaSetup.secret }}</p>
              <p class="hint break">{{ mfaSetup.otpauth_uri }}</p>
            </el-alert>
            <el-input id="admin-login-mfa" v-model="mfaCode" autocomplete="one-time-code" placeholder="6 位验证码或恢复码" />
          </div>
        </div>
        <div v-if="showTurnstile" class="row">
          <label class="label">验证</label>
          <div class="turnstile-cell">
            <TurnstileWidget
              v-if="turnstileSiteKey"
              ref="turnstile"
              :sitekey="turnstileSiteKey"
              action="login"
              @verified="(token) => (turnstileToken = token)"
              @expired="turnstileToken = ''"
              @error="turnstileToken = ''"
            />
            <p v-else class="hint">人机验证暂未配置，请联系管理员。</p>
          </div>
        </div>
        <div class="actions">
          <el-button v-if="!mfaChallengeToken" type="primary" native-type="submit" :loading="loading">登录</el-button>
          <el-button v-else type="primary" :loading="loading" @click="onMfaSubmit">完成 MFA 登录</el-button>
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
.turnstile-cell {
  flex: 1;
  min-width: 0;
}
.hint {
  margin: 0;
  color: #909399;
  font-size: 12px;
}
.break {
  word-break: break-all;
}
.actions {
  padding-left: 96px;
}
</style>
