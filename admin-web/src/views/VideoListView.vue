<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import * as taxonomyApi from "@/api/taxonomy";
import * as videosApi from "@/api/videos";
import type { VideoResponse } from "@/api/videos";
import { formatApiError } from "@/util/errors";

const STATUSES = ["draft", "pending_review", "published", "rejected", "offline"] as const;

const loading = ref(false);
const rows = ref<adminApi.VideoListItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });
const filters = reactive({
  status: "" as string,
  keyword: "",
});

const categories = ref<taxonomyApi.CategoryRow[]>([]);
const editOpen = ref(false);
const editLoading = ref(false);
/** 打开编辑弹窗时的状态，用于保存时选择 PATCH 或审核专用 POST */
const editInitialStatus = ref("");
const editForm = reactive({
  id: "",
  title: "",
  description: "",
  category_id: "" as string | null,
  status: "",
  tag_ids: "" as string,
});

/** 平台下架（published → offline），须走 POST /offline，勿用 PATCH 改状态 */
const offlineId = ref<string | null>(null);
const deleteId = ref<string | null>(null);

async function confirmDelete(row: adminApi.VideoListItem) {
  try {
    await ElMessageBox.confirm(
      `将永久删除视频「${row.title}」及其评论、点赞等关联数据，且不可恢复。确定删除？`,
      "删除视频",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
    deleteId.value = row.id;
    await videosApi.deleteVideo(row.id);
    ElMessage.success("已删除");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  } finally {
    deleteId.value = null;
  }
}

async function confirmPlatformOffline(row: adminApi.VideoListItem) {
  try {
    await ElMessageBox.confirm(
      `确认将已发布视频「${row.title}」做平台下架？（published → offline）`,
      "平台下架",
      { type: "warning", confirmButtonText: "下架", cancelButtonText: "取消" },
    );
    offlineId.value = row.id;
    await videosApi.offlineVideo(row.id);
    ElMessage.success("已下架");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  } finally {
    offlineId.value = null;
  }
}

async function loadCategories() {
  try {
    categories.value = await taxonomyApi.listCategories();
  } catch {
    categories.value = [];
  }
}

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await adminApi.adminListVideos({
      offset: page.offset,
      limit: page.limit,
      status: filters.status || undefined,
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

function openEdit(row: adminApi.VideoListItem) {
  editForm.id = row.id;
  editForm.title = row.title;
  editForm.description = "";
  editForm.category_id = row.category_id;
  const st = String(row.status ?? "").trim();
  editForm.status = st;
  editInitialStatus.value = st;
  editForm.tag_ids = row.tags.map((x) => x.id).join(",");
  editOpen.value = true;
  editLoading.value = true;
  videosApi
    .getVideo(row.id)
    .then((v: VideoResponse) => {
      editForm.description = v.description ?? "";
    })
    .catch(() => {
      editForm.description = "";
    })
    .finally(() => {
      editLoading.value = false;
    });
}

async function saveEdit() {
  editLoading.value = true;
  try {
    const tag_ids = editForm.tag_ids
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const oldSt = String(editInitialStatus.value ?? "").trim();
    const newSt = String(editForm.status ?? "").trim();
    const meta = {
      title: editForm.title,
      description: editForm.description || null,
      category_id: editForm.category_id || null,
      tag_ids: tag_ids.length ? tag_ids : undefined,
    };

    if (oldSt !== newSt) {
      if (oldSt === "draft" && newSt === "published") {
        ElMessage.warning("不能从草稿直接发布：请先改为「待审核」保存（提交审核），再在「视频审核」页通过，或在此保存为待审核后再改为已发布。");
        return;
      }
      if (oldSt === "pending_review" && newSt === "published") {
        await ElMessageBox.confirm(`确认审核通过并发布？「${editForm.title}」`, "发布", {
          type: "success",
          confirmButtonText: "通过并发布",
          cancelButtonText: "取消",
        });
        await videosApi.approveVideo(editForm.id);
        editInitialStatus.value = "published";
        editForm.status = "published";
        await videosApi.patchVideo(editForm.id, meta);
      } else if (oldSt === "pending_review" && newSt === "rejected") {
        const { value } = await ElMessageBox.prompt("驳回原因", `驳回：${editForm.title}`, {
          confirmButtonText: "提交",
          cancelButtonText: "取消",
          inputPattern: /\S+/,
          inputErrorMessage: "请填写原因",
        });
        await videosApi.rejectVideo(editForm.id, value.trim());
        editInitialStatus.value = "rejected";
        editForm.status = "rejected";
        await videosApi.patchVideo(editForm.id, meta);
      } else if (oldSt === "draft" && newSt === "pending_review") {
        await ElMessageBox.confirm("将提交审核（草稿 → 待审核）？", "提交审核", { type: "info" });
        await videosApi.submitReviewVideo(editForm.id);
        editInitialStatus.value = "pending_review";
        editForm.status = "pending_review";
        await videosApi.patchVideo(editForm.id, meta);
      } else if (oldSt === "published" && newSt === "offline") {
        await ElMessageBox.confirm(
          `确认将已发布视频「${editForm.title}」做平台下架？（published → offline）`,
          "平台下架",
          { type: "warning", confirmButtonText: "下架", cancelButtonText: "取消" },
        );
        await videosApi.offlineVideo(editForm.id);
        editInitialStatus.value = "offline";
        editForm.status = "offline";
        await videosApi.patchVideo(editForm.id, meta);
      } else if (oldSt === "rejected" && newSt === "draft") {
        await videosApi.patchVideo(editForm.id, { ...meta, status: "draft" });
        editInitialStatus.value = "draft";
        editForm.status = "draft";
      } else {
        ElMessage.error(
          "该状态变更不能在此用「保存」直接完成：请使用「视频审核」页的通过/驳回，或平台下架按钮；草稿→待审核可在本页保存。",
        );
        return;
      }
    } else {
      await videosApi.patchVideo(editForm.id, { ...meta, status: newSt });
    }
    ElMessage.success("已保存");
    editOpen.value = false;
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  } finally {
    editLoading.value = false;
  }
}

onMounted(() => {
  loadCategories();
  load();
});
</script>

<template>
  <div>
    <el-space wrap style="margin-bottom: 12px">
      <el-select v-model="filters.status" clearable placeholder="状态" style="width: 160px">
        <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
      </el-select>
      <el-input v-model="filters.keyword" clearable placeholder="标题关键字" style="width: 220px" />
      <el-button type="primary" @click="((page.offset = 0), load())">查询</el-button>
    </el-space>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="author_id" label="作者" width="280" show-overflow-tooltip />
      <el-table-column prop="views_count" label="播放" width="72" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button
            v-if="row.status === 'published'"
            type="danger"
            link
            :loading="offlineId === row.id"
            @click="confirmPlatformOffline(row)"
          >
            平台下架
          </el-button>
          <el-button type="danger" link :loading="deleteId === row.id" @click="confirmDelete(row)">删除</el-button>
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

    <el-dialog v-model="editOpen" title="编辑视频" width="560px" destroy-on-close>
      <el-form v-loading="editLoading" label-width="96px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category_id" clearable filterable placeholder="可选" style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签 ID">
          <el-input v-model="editForm.tag_ids" placeholder="逗号分隔 UUID" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
