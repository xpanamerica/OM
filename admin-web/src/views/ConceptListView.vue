<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as conceptsApi from "@/api/concepts";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<conceptsApi.ConceptRow[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

const dlg = ref(false);
const form = reactive({ id: "", name: "", description: "" });

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await conceptsApi.listConcepts({
      offset: page.offset,
      limit: page.limit,
    });
    rows.value = items;
    total.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

function openNew() {
  form.id = "";
  form.name = "";
  form.description = "";
  dlg.value = true;
}

function openEdit(row: conceptsApi.ConceptRow) {
  form.id = row.id;
  form.name = row.name;
  form.description = row.description ?? "";
  dlg.value = true;
}

async function save() {
  try {
    if (form.id) {
      await conceptsApi.patchConcept(form.id, {
        name: form.name || undefined,
        description: form.description || null,
      });
    } else {
      await conceptsApi.createConcept({ name: form.name, description: form.description || null });
    }
    ElMessage.success("已保存");
    dlg.value = false;
    await load();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

onMounted(load);
</script>

<template>
  <div>
    <el-button type="primary" size="small" @click="openNew">新建概念</el-button>
    <el-table v-loading="loading" :data="rows" border stripe size="small" style="margin-top: 12px">
      <el-table-column prop="name" label="名称" width="200" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
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

    <el-dialog v-model="dlg" :title="form.id ? '编辑概念' : '新建概念'" width="520px" destroy-on-close>
      <el-form label-width="72px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
