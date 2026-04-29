<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<adminApi.AdminRegistrationAttemptItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

async function load() {
  loading.value = true;
  try {
    const out = await adminApi.adminListRegistrationAttempts({
      offset: page.offset,
      limit: page.limit,
    });
    rows.value = out.items;
    total.value = out.total;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

function formatDt(v: string): string {
  return v.replace("T", " ").replace("+00:00", " UTC");
}

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <span>注册审计</span>
          <el-button size="small" @click="load">刷新</el-button>
        </div>
      </template>

      <el-table :data="rows" stripe style="width: 100%">
        <el-table-column prop="created_at" label="时间" min-width="170">
          <template #default="{ row }">{{ formatDt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="success" label="成功" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? "是" : "否" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" width="140" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
        <el-table-column prop="username" label="用户名" width="120" show-overflow-tooltip />
        <el-table-column prop="invite_code_submitted" label="邀请码（提交）" width="160" show-overflow-tooltip />
        <el-table-column prop="failure_reason" label="失败原因" min-width="160" show-overflow-tooltip />
        <el-table-column prop="user_agent" label="UA" min-width="120" show-overflow-tooltip />
      </el-table>

      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next, sizes"
          :total="total"
          :page-size="page.limit"
          :page-sizes="[10, 20, 50]"
          :current-page="Math.floor(page.offset / page.limit) + 1"
          @size-change="
            (s: number) => {
              page.limit = s;
              page.offset = 0;
              void load();
            }
          "
          @current-change="
            (p: number) => {
              page.offset = (p - 1) * page.limit;
              void load();
            }
          "
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
