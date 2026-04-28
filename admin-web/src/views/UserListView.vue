<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<adminApi.UserPublic[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });
const filters = reactive({
  role: "" as string,
  is_active: "" as "" | "true" | "false",
  keyword: "",
});

const toggling = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await adminApi.adminListUsers({
      offset: page.offset,
      limit: page.limit,
      role: filters.role || undefined,
      is_active: filters.is_active === "" ? undefined : filters.is_active === "true",
      keyword: filters.keyword || undefined,
    });
    rows.value = items;
    total.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function onActiveChange(row: adminApi.UserPublic, val: boolean) {
  toggling.value = row.id;
  try {
    await adminApi.adminSetUserActive(row.id, val);
    row.is_active = val;
    ElMessage.success(val ? "已启用" : "已禁用");
  } catch (e) {
    ElMessage.error(formatApiError(e));
    await load();
  } finally {
    toggling.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <el-space wrap style="margin-bottom: 12px">
      <el-select v-model="filters.role" clearable placeholder="角色" style="width: 120px">
        <el-option label="user" value="user" />
        <el-option label="admin" value="admin" />
      </el-select>
      <el-select v-model="filters.is_active" clearable placeholder="启用" style="width: 120px">
        <el-option label="是" value="true" />
        <el-option label="否" value="false" />
      </el-select>
      <el-input v-model="filters.keyword" clearable placeholder="邮箱或用户名" style="width: 220px" />
      <el-button type="primary" @click="((page.offset = 0), load())">查询</el-button>
    </el-space>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip />
      <el-table-column prop="role" label="角色" width="88" />
      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            :loading="toggling === row.id"
            @change="(v: boolean) => onActiveChange(row, v)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="170" />
    </el-table>

    <el-pagination
      :current-page="Math.floor(page.offset / page.limit) + 1"
      :page-size="page.limit"
      :total="total"
      layout="total, prev, pager, next"
      style="margin-top: 12px"
      @current-change="
        (p: number) => {
          page.offset = (p - 1) * page.limit;
          load();
        }
      "
    />
  </div>
</template>
