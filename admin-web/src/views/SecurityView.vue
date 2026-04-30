<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as authApi from "@/api/auth";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const mfa = ref<authApi.MfaStatus | null>(null);
const setup = ref<authApi.MfaSetup | null>(null);
const code = ref("");
const recoveryConfirmed = ref(false);
const recoveryCodes = ref<string[]>([]);
const sessions = ref<authApi.AuthSession[]>([]);

async function load() {
  loading.value = true;
  try {
    const [mfaStatus, sessionRows] = await Promise.all([authApi.fetchMfaStatus(), authApi.listSessions()]);
    mfa.value = mfaStatus;
    sessions.value = sessionRows;
  } finally {
    loading.value = false;
  }
}

async function startSetup() {
  setup.value = await authApi.startMfaSetup();
  recoveryCodes.value = [];
  recoveryConfirmed.value = false;
}

async function enable() {
  try {
    if (!recoveryConfirmed.value) {
      ElMessage.warning("启用前请确认已准备好保存恢复码。");
      return;
    }
    const res = await authApi.enableMfa(code.value.trim());
    recoveryCodes.value = res.recovery_codes;
    setup.value = null;
    code.value = "";
    ElMessage.success("MFA 已启用，请保存恢复码");
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

async function revoke(id: string) {
  await authApi.revokeSession(id);
  await load();
}

async function revokeOthers() {
  const n = await authApi.revokeOtherSessions();
  ElMessage.success(`已撤销 ${n} 个其他会话`);
  await load();
}

onMounted(() => void load());
</script>

<template>
  <div v-loading="loading">
    <el-card class="card">
      <template #header>管理员 MFA</template>
      <el-alert v-if="mfa?.setup_required" type="warning" :closable="false" title="管理员账号必须启用 MFA" />
      <p>状态：{{ mfa?.enabled ? "已启用" : "未启用" }}</p>
      <el-button v-if="!mfa?.enabled && !setup" type="primary" @click="startSetup">启用 TOTP MFA</el-button>
      <div v-if="setup" class="setup">
        <p>认证器密钥：</p>
        <p class="mono">{{ setup.secret }}</p>
        <p class="mono">{{ setup.otpauth_uri }}</p>
        <el-button link type="primary" :href="setup.otpauth_uri" tag="a">打开认证器</el-button>
        <el-checkbox v-model="recoveryConfirmed">我知道恢复码只显示一次，并会立即保存</el-checkbox>
        <el-input v-model="code" class="code" placeholder="输入 6 位验证码" />
        <el-button type="primary" :disabled="!recoveryConfirmed" @click="enable">确认启用</el-button>
      </div>
      <el-alert v-if="recoveryCodes.length" type="success" :closable="false" title="恢复码只显示一次，请妥善保存">
        <p class="mono">{{ recoveryCodes.join(" ") }}</p>
      </el-alert>
    </el-card>

    <el-card class="card">
      <template #header>
        登录设备
        <el-button class="right" link type="danger" @click="revokeOthers">撤销其他设备</el-button>
      </template>
      <el-table :data="sessions" size="small">
        <el-table-column prop="device_label" label="设备" width="140" />
        <el-table-column prop="ip_address" label="IP" width="150" />
        <el-table-column prop="last_used_at" label="最近使用" min-width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.is_current" type="success">当前</el-tag>
            <el-button v-else link type="danger" @click="revoke(row.id)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.card {
  margin-bottom: 16px;
}
.mono {
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.code {
  max-width: 220px;
  margin-right: 8px;
}
.right {
  float: right;
}
</style>
