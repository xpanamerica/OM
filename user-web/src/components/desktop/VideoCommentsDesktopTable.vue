<script setup lang="ts">
import type { CommentOut } from "@/api/videos";

const props = defineProps<{
  comments: CommentOut[];
  loggedIn: boolean;
  currentUserId?: string;
}>();

const emit = defineEmits<{
  delete: [row: CommentOut];
}>();

function canDelete(row: CommentOut) {
  return props.loggedIn && props.currentUserId != null && row.user_id === props.currentUserId;
}
</script>

<template>
  <el-table :data="comments" size="small" border>
    <el-table-column prop="content" label="内容" min-width="200" />
    <el-table-column prop="user_id" label="用户" width="220" show-overflow-tooltip />
    <el-table-column prop="created_at" label="时间" width="170" />
    <el-table-column v-if="loggedIn" label="" width="72">
      <template #default="{ row }">
        <el-button v-if="canDelete(row)" type="danger" link @click="emit('delete', row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
