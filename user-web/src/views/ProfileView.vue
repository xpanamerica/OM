<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { useAuthStore } from "@/stores/auth";
import { formatApiError } from "@/util/errors";
import AlgorithmResetButton from "@/components/algorithm/AlgorithmResetButton.vue";

const auth = useAuthStore();
const router = useRouter();
const loading = ref(false);

onMounted(async () => {
  if (!auth.user && auth.token) {
    loading.value = true;
    try {
      await auth.fetchMe();
    } catch (e) {
      ElMessage.error(formatApiError(e));
    } finally {
      loading.value = false;
    }
  }
});

async function logout() {
  auth.logout();
  await router.push({ name: "home" });
}
</script>

<template>
  <div v-loading="loading" class="profile">
    <h2>个人中心</h2>
    <el-descriptions v-if="auth.user" border :column="1" class="prof-desc">
      <el-descriptions-item label="用户名">{{ auth.user.username }}</el-descriptions-item>
      <el-descriptions-item label="邮箱">{{ auth.user.email }}</el-descriptions-item>
      <el-descriptions-item label="角色">{{ auth.user.role }}</el-descriptions-item>
      <el-descriptions-item label="注册时间">{{ auth.user.created_at }}</el-descriptions-item>
    </el-descriptions>

    <nav class="quick" aria-label="账号功能">
      <RouterLink class="quick__a" to="/me/history">播放记录</RouterLink>
      <RouterLink class="quick__a" to="/me/favorites">我的收藏</RouterLink>
      <RouterLink class="quick__a" to="/me/security">账号安全</RouterLink>
    </nav>

    <div class="algorithm-entry">
      <AlgorithmResetButton />
    </div>

    <el-button v-if="auth.user" type="danger" plain class="logout" @click="logout">退出登录</el-button>
  </div>
</template>

<style scoped>
.profile {
  position: relative;
  padding: 18px;
  border: 1px solid rgba(103, 232, 249, 0.16);
  border-radius: 26px;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% -10%, rgba(34, 211, 238, 0.2), transparent 34%),
    radial-gradient(circle at 100% 10%, rgba(139, 92, 246, 0.16), transparent 32%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(2, 6, 23, 0.94));
  color: #f8fafc;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.2);
}
.profile h2 {
  margin-top: 0;
  color: #f8fafc;
}
.prof-desc {
  max-width: 520px;
}
.prof-desc :deep(.el-descriptions__body),
.prof-desc :deep(.el-descriptions__table),
.prof-desc :deep(.el-descriptions__cell),
.prof-desc :deep(.el-descriptions__label),
.prof-desc :deep(.el-descriptions__content) {
  background: rgba(15, 23, 42, 0.68) !important;
  color: #f8fafc;
  border-color: rgba(103, 232, 249, 0.14) !important;
}
.prof-desc :deep(.el-descriptions__label) {
  color: #93c5fd;
  font-weight: 900;
}
.quick {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 520px;
}
.quick__a {
  display: flex;
  align-items: center;
  min-height: 48px;
  padding: 0 16px;
  border-radius: 10px;
  text-decoration: none;
  color: #e0f2fe;
  font-size: 15px;
  font-weight: 500;
  border: 1px solid rgba(103, 232, 249, 0.16);
  background: rgba(15, 23, 42, 0.7);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.quick__a:hover {
  color: #67e8f9;
  border-color: rgba(103, 232, 249, 0.42);
  background: rgba(8, 47, 73, 0.55);
}
.logout {
  margin-top: 20px;
  min-height: 44px;
}
.algorithm-entry {
  max-width: 520px;
  margin-top: 20px;
}

@media (max-width: 767px) {
  .prof-desc {
    max-width: none;
  }
  .quick {
    max-width: none;
  }
  .algorithm-entry {
    max-width: none;
  }
}
</style>
