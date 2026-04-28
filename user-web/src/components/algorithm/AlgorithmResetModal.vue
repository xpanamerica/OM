<script setup lang="ts">
defineProps<{
  visible: boolean;
  loading?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="ar-modal-root" @click.self="emit('close')">
      <section class="ar-modal" role="dialog" aria-modal="true" aria-labelledby="ar-modal-title">
        <div class="ar-modal__mark" aria-hidden="true">✦</div>
        <h2 id="ar-modal-title">确认归源？</h2>
        <p>
          这将重置你的个性化推荐状态。之后你看到的内容将重新从随机、多元、非画像化的方式开始分发。
          你的账号、作品、收藏和关注不会被删除。
        </p>
        <div class="ar-modal__actions">
          <button type="button" class="ar-modal__ghost" :disabled="loading" @click="emit('close')">暂不归源</button>
          <button type="button" class="ar-modal__primary" :disabled="loading" @click="emit('confirm')">
            {{ loading ? "归源中…" : "确认归源" }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.ar-modal-root {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(2, 6, 23, 0.68);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.ar-modal {
  width: min(420px, 100%);
  padding: 22px;
  border: 1px solid rgba(167, 139, 250, 0.26);
  border-radius: 24px;
  background:
    radial-gradient(circle at 10% 0%, rgba(34, 211, 238, 0.18), transparent 36%),
    linear-gradient(160deg, #101827, #05070d);
  color: #f8fafc;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}
.ar-modal__mark {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: #dbeafe;
  background: linear-gradient(135deg, #22d3ee, #8b5cf6);
  font-size: 22px;
  box-shadow: 0 14px 32px rgba(34, 211, 238, 0.22);
}
.ar-modal h2 {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 900;
}
.ar-modal p {
  margin: 0;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.75;
}
.ar-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
.ar-modal button {
  min-height: 40px;
  border: 0;
  border-radius: 999px;
  padding: 0 16px;
  font: inherit;
  font-weight: 900;
  cursor: pointer;
}
.ar-modal button:disabled {
  cursor: wait;
  opacity: 0.62;
}
.ar-modal__ghost {
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.08);
}
.ar-modal__primary {
  color: #06111f;
  background: linear-gradient(135deg, #67e8f9, #a78bfa);
}
</style>
