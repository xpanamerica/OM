<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "@/util/elementPlusMessage";
import { formatApiError } from "@/util/errors";
import { useAlgorithmReset } from "@/composables/useAlgorithmReset";
import AlgorithmResetModal from "./AlgorithmResetModal.vue";

const emit = defineEmits<{
  success: [];
}>();

const router = useRouter();
const modalOpen = ref(false);
const { loading, resetAlgorithm } = useAlgorithmReset();

async function confirmReset() {
  try {
    const result = await resetAlgorithm();
    if (!result) return;
    modalOpen.value = false;
    ElMessage.success("你已归源。系统将不再基于旧画像推送内容。");
    emit("success");
    await router.push({ name: "native-feed", query: { origin: "1", t: String(Date.now()) } });
  } catch (e) {
    ElMessage.error(formatApiError(e) || "归源失败，请稍后再试。");
  }
}
</script>

<template>
  <section class="ar-card">
    <div class="ar-card__icon" aria-hidden="true">⌁</div>
    <div class="ar-card__main">
      <p class="ar-card__eyebrow">算法与推荐</p>
      <h2>一键归源</h2>
      <p class="ar-card__desc">重置算法画像，回到开放探索。</p>
      <p class="ar-card__note">这不会删除你的账号、作品、收藏、关注和评论。</p>
    </div>
    <button type="button" class="ar-card__btn" :disabled="loading" @click="modalOpen = true">
      {{ loading ? "归源中…" : "一键归源" }}
    </button>
    <AlgorithmResetModal
      :visible="modalOpen"
      :loading="loading"
      @close="modalOpen = false"
      @confirm="confirmReset"
    />
  </section>
</template>

<style scoped>
.ar-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  margin: 12px 0;
  padding: 16px;
  border: 1px solid rgba(103, 232, 249, 0.18);
  border-radius: 22px;
  overflow: hidden;
  background:
    radial-gradient(circle at 10% -10%, rgba(34, 211, 238, 0.22), transparent 34%),
    linear-gradient(145deg, rgba(15, 23, 42, 0.96), rgba(17, 24, 39, 0.88));
  color: #f8fafc;
  box-shadow: 0 18px 42px rgba(2, 6, 23, 0.22);
}
.ar-card::after {
  content: "";
  position: absolute;
  inset: auto -20% -50% 30%;
  height: 110px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.22), transparent 66%);
  pointer-events: none;
}
.ar-card__icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #22d3ee, #8b5cf6);
  color: #fff;
  font-size: 24px;
  font-weight: 900;
}
.ar-card__main {
  min-width: 0;
}
.ar-card__eyebrow {
  margin: 0 0 5px;
  color: #67e8f9;
  font-size: 12px;
  font-weight: 900;
}
.ar-card h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 900;
}
.ar-card__desc,
.ar-card__note {
  margin: 8px 0 0;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.55;
}
.ar-card__note {
  color: #94a3b8;
}
.ar-card__btn {
  grid-column: 1 / -1;
  min-height: 42px;
  border: 0;
  border-radius: 999px;
  color: #06111f;
  background: linear-gradient(135deg, #67e8f9, #a78bfa);
  font: inherit;
  font-weight: 900;
  cursor: pointer;
  box-shadow: 0 12px 28px rgba(34, 211, 238, 0.18);
}
.ar-card__btn:disabled {
  cursor: wait;
  opacity: 0.62;
}
@media (min-width: 680px) {
  .ar-card {
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
  }
  .ar-card__btn {
    grid-column: auto;
    padding: 0 20px;
  }
}
</style>
