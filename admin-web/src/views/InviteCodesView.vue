<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<adminApi.AdminInviteCodeItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

const createOpen = ref(false);
const createBusy = ref(false);
const createForm = reactive<{ max_uses: number }>({ max_uses: 1 });
const createExpires = ref<Date | null>(null);

const revoking = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    const out = await adminApi.adminListInviteCodes({
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

async function onCreate() {
  createBusy.value = true;
  try {
    const body: { max_uses: number; expires_at?: string } = { max_uses: createForm.max_uses };
    if (createExpires.value) {
      body.expires_at = createExpires.value.toISOString();
    }
    const { invite } = await adminApi.adminCreateInviteCode(body);
    ElMessage.success(`已生成邀请码：${invite.code}`);
    createOpen.value = false;
    createForm.max_uses = 1;
    createExpires.value = null;
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    createBusy.value = false;
  }
}

async function onRevoke(row: adminApi.AdminInviteCodeItem) {
  try {
    await ElMessageBox.confirm(`确认作废邀请码「${row.code}」？作废后不可再用于注册。`, "作废邀请码", {
      type: "warning",
      confirmButtonText: "作废",
      cancelButtonText: "取消",
    });
    revoking.value = row.id;
    await adminApi.adminRevokeInviteCode(row.id);
    ElMessage.success("已作废");
    await load();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    ElMessage.error(formatApiError(e));
  } finally {
    revoking.value = null;
  }
}

function formatDt(v: string | null): string {
  if (!v) return "—";
  return v.replace("T", " ").replace("+00:00", " UTC");
}

onMounted(load);
</script>

<template>
  <div v-loading="loading" class="page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <span>内测邀请码</span>
          <div class="actions">
            <el-button size="small" @click="load">刷新</el-button>
            <el-button type="primary" size="small" @click="createOpen = true">生成邀请码</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" stripe style="width: 100%">
        <el-table-column prop="code" label="邀请码" min-width="160" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="used_count" label="已用次数" width="100" />
        <el-table-column prop="max_uses" label="上限" width="80" />
        <el-table-column label="过期时间" min-width="170">
          <template #default="{ row }">{{ formatDt(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column label="使用时间" min-width="170">
          <template #default="{ row }">{{ formatDt(row.used_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              link
              type="danger"
              :loading="revoking === row.id"
              @click="onRevoke(row)"
            >
              作废
            </el-button>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="page.limit"
          :current-page="Math.floor(page.offset / page.limit) + 1"
          @current-change="
            (p: number) => {
              page.offset = (p - 1) * page.limit;
              void load();
            }
          "
        />
      </div>
    </el-card>

    <el-dialog v-model="createOpen" title="生成邀请码" width="420px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="最大使用次数（默认 1 为一次性）">
          <el-input-number v-model="createForm.max_uses" :min="1" :max="100000" />
        </el-form-item>
        <el-form-item label="过期时间（可选，留空表示不过期）">
          <el-date-picker
            v-model="createExpires"
            type="datetime"
            placeholder="选择日期时间"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="createBusy" @click="onCreate">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.actions {
  display: flex;
  gap: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
