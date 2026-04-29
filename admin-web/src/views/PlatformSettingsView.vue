<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const saving = ref(false);
const form = reactive<adminApi.AdminPlatformSettings>({
  video_publish_without_review_enabled: false,
  registration_invite_code_required: false,
});

async function load() {
  loading.value = true;
  try {
    const settings = await adminApi.adminGetPlatformSettings();
    form.video_publish_without_review_enabled = settings.video_publish_without_review_enabled;
    form.registration_invite_code_required = settings.registration_invite_code_required;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const settings = await adminApi.adminUpdatePlatformSettings({
      video_publish_without_review_enabled: form.video_publish_without_review_enabled,
      registration_invite_code_required: form.registration_invite_code_required,
    });
    form.video_publish_without_review_enabled = settings.video_publish_without_review_enabled;
    form.registration_invite_code_required = settings.registration_invite_code_required;
    ElMessage.success("平台设置已保存");
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="settings-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>视频发布审核</span>
          <el-button size="small" @click="load">刷新</el-button>
        </div>
      </template>

      <el-form label-position="top">
        <el-form-item label="允许所有用户发布视频不经过审核">
          <el-switch
            v-model="form.video_publish_without_review_enabled"
            active-text="开启：提交后直接发布"
            inactive-text="关闭：提交后进入审核"
          />
          <p class="hint">
            开启后，用户在前台提交视频时会直接变为已发布状态，不再进入“视频审核”的待审核队列。
          </p>
        </el-form-item>

        <el-divider />

        <div class="card-head">
          <span>注册与内测</span>
        </div>
        <el-form-item label="注册必须凭邀请码（内测模式）">
          <el-switch
            v-model="form.registration_invite_code_required"
            active-text="开启：仅持有效邀请码可注册"
            inactive-text="关闭：开放注册（正式上线前可关闭此项）"
          />
          <p class="hint">
            开启后，前台注册须填写未过期且未用完的邀请码；邀请码在「内测邀请码」菜单生成与管理。
          </p>
        </el-form-item>

        <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 760px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hint {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
