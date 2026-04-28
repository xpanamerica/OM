<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "@/util/elementPlusMessage";
import * as taxonomyApi from "@/api/taxonomy";
import { formatApiError } from "@/util/errors";

const tab = ref<"cat" | "tag">("cat");
const loading = ref(false);

const categories = ref<taxonomyApi.CategoryRow[]>([]);
const tags = ref<taxonomyApi.TagRow[]>([]);

const catDialog = ref(false);
const catForm = reactive({ id: "", name: "", description: "" });
const tagDialog = ref(false);
const tagForm = reactive({ id: "", name: "" });

async function loadAll() {
  loading.value = true;
  try {
    const [c, t] = await Promise.all([taxonomyApi.listCategories(), taxonomyApi.listTags()]);
    categories.value = c;
    tags.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

function openNewCategory() {
  catForm.id = "";
  catForm.name = "";
  catForm.description = "";
  catDialog.value = true;
}

function openEditCategory(row: taxonomyApi.CategoryRow) {
  catForm.id = row.id;
  catForm.name = row.name;
  catForm.description = row.description ?? "";
  catDialog.value = true;
}

async function saveCategory() {
  try {
    if (catForm.id) {
      await taxonomyApi.patchCategory(catForm.id, {
        name: catForm.name || undefined,
        description: catForm.description || null,
      });
    } else {
      await taxonomyApi.createCategory({ name: catForm.name, description: catForm.description || null });
    }
    ElMessage.success("已保存");
    catDialog.value = false;
    await loadAll();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

function openNewTag() {
  tagForm.id = "";
  tagForm.name = "";
  tagDialog.value = true;
}

function openEditTag(row: taxonomyApi.TagRow) {
  tagForm.id = row.id;
  tagForm.name = row.name;
  tagDialog.value = true;
}

async function saveTag() {
  try {
    if (tagForm.id) {
      await taxonomyApi.patchTag(tagForm.id, { name: tagForm.name || undefined });
    } else {
      await taxonomyApi.createTag({ name: tagForm.name });
    }
    ElMessage.success("已保存");
    tagDialog.value = false;
    await loadAll();
  } catch (e) {
    ElMessage.error(formatApiError(e));
  }
}

onMounted(loadAll);
</script>

<template>
  <div v-loading="loading">
    <el-tabs v-model="tab">
      <el-tab-pane label="分类" name="cat">
        <el-button type="primary" size="small" @click="openNewCategory">新建分类</el-button>
        <el-table :data="categories" border stripe size="small" style="margin-top: 12px">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" link @click="openEditCategory(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="标签" name="tag">
        <el-button type="primary" size="small" @click="openNewTag">新建标签</el-button>
        <el-table :data="tags" border stripe size="small" style="margin-top: 12px">
          <el-table-column prop="name" label="名称" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" link @click="openEditTag(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="catDialog" :title="catForm.id ? '编辑分类' : '新建分类'" width="480px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="catForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="catForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tagDialog" :title="tagForm.id ? '编辑标签' : '新建标签'" width="400px" destroy-on-close>
      <el-form label-width="64px">
        <el-form-item label="名称">
          <el-input v-model="tagForm.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
