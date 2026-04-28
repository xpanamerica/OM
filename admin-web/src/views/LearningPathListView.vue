<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as lpApi from "@/api/learningPaths";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<lpApi.LearningPathRow[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

const dlg = ref(false);
const form = reactive({
  id: "",
  title: "",
  description: "",
  is_published: false,
});

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await lpApi.listLearningPaths({
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

function openEdit(row: lpApi.LearningPathRow) {
  form.id = row.id;
  form.title = row.title;
  form.description = row.description ?? "";
  form.is_published = row.is_published;
  dlg.value = true;
}

async function save() {
  try {
    await lpApi.patchLearningPath(form.id, {
      title: form.title,
      description: form.description || null,
      is_published: form.is_published,
    });
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
    <p class="hint">管理员可查看全部路径；此处仅支持修改元数据（标题 / 描述 / 发布状态）。</p>
    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="is_published" label="已发布" width="88">
        <template #default="{ row }">
          {{ row.is_published ? "是" : "否" }}
        </template>
      </el-table-column>
      <el-table-column prop="creator_id" label="创建者" width="260" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="88">
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

    <el-dialog v-model="dlg" title="编辑学习路径" width="520px" destroy-on-close>
      <el-form label-width="96px">
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="已发布">
          <el-switch v-model="form.is_published" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hint {
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
</style>
