<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "@/util/elementPlusMessage";
import * as adminApi from "@/api/admin";
import * as videosApi from "@/api/videos";
import { formatApiError } from "@/util/errors";

const loading = ref(false);
const rows = ref<adminApi.VideoListItem[]>([]);
const total = ref(0);
const page = reactive({ offset: 0, limit: 20 });

const eventsOpen = ref(false);
const eventsLoading = ref(false);
const events = ref<videosApi.VideoWorkflowEvent[]>([]);
const eventsVideoId = ref("");

async function load() {
  loading.value = true;
  try {
    const { items, total: t } = await adminApi.adminListVideos({
      offset: page.offset,
      limit: page.limit,
      status: "pending_review",
    });
    rows.value = items;
    total.value = t;
  } catch (e) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

async function approve(row: adminApi.VideoListItem) {
  try {
    await ElMessageBox.confirm(`通过审核：${row.title}?`, "确认", { type: "warning" });
    await videosApi.approveVideo(row.id);
    ElMessage.success("已通过");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  }
}

async function reject(row: adminApi.VideoListItem) {
  try {
    const { value } = await ElMessageBox.prompt("驳回原因", `驳回：${row.title}`, {
      confirmButtonText: "提交",
      cancelButtonText: "取消",
      inputPattern: /\S+/,
      inputErrorMessage: "请填写原因",
    });
    await videosApi.rejectVideo(row.id, value.trim());
    ElMessage.success("已驳回");
    await load();
  } catch (e) {
    if (e !== "cancel") ElMessage.error(formatApiError(e));
  }
}

async function showEvents(row: adminApi.VideoListItem) {
  eventsVideoId.value = row.id;
  eventsOpen.value = true;
  eventsLoading.value = true;
  try {
    events.value = await videosApi.listWorkflowEvents(row.id);
  } catch (e) {
    ElMessage.error(formatApiError(e));
    events.value = [];
  } finally {
    eventsLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <p class="hint">仅列出「待审核」视频；通过 / 驳回调用审核接口。</p>
    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="author_id" label="作者" width="260" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="success" link @click="approve(row)">通过</el-button>
          <el-button type="danger" link @click="reject(row)">驳回</el-button>
          <el-button type="primary" link @click="showEvents(row)">审计</el-button>
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

    <el-dialog v-model="eventsOpen" :title="`工作流审计 ${eventsVideoId}`" width="720px" destroy-on-close>
      <el-table v-loading="eventsLoading" :data="events" size="small" border>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column prop="from_status" label="从" width="100" />
        <el-table-column prop="to_status" label="到" width="100" />
        <el-table-column prop="actor_id" label="操作人" width="220" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.hint {
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
</style>
