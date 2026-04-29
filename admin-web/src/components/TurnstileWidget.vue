<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps<{ sitekey: string; action?: string }>();

const emit = defineEmits<{
  verified: [token: string];
  expired: [];
  error: [];
}>();

const container = ref<HTMLElement | null>(null);
let widgetId: string | null = null;
let scriptPromise: Promise<void> | null = null;

function loadTurnstileScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-turnstile-api="true"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Turnstile script failed to load")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.dataset.turnstileApi = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Turnstile script failed to load"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

async function renderWidget() {
  if (!props.sitekey || !container.value) return;
  await loadTurnstileScript();
  await nextTick();
  if (!window.turnstile || !container.value || widgetId) return;
  widgetId = window.turnstile.render(container.value, {
    sitekey: props.sitekey,
    action: props.action,
    theme: "light",
    callback: (token: string) => emit("verified", token),
    "expired-callback": () => emit("expired"),
    "error-callback": () => emit("error"),
  });
}

function reset() {
  if (window.turnstile && widgetId) {
    window.turnstile.reset(widgetId);
  }
}

defineExpose({ reset });

onMounted(() => {
  void renderWidget();
});

onBeforeUnmount(() => {
  if (window.turnstile && widgetId) {
    window.turnstile.remove(widgetId);
  }
  widgetId = null;
});

watch(
  () => props.sitekey,
  () => {
    if (window.turnstile && widgetId) {
      window.turnstile.remove(widgetId);
      widgetId = null;
    }
    void renderWidget();
  },
);
</script>

<template>
  <div ref="container" class="turnstile-widget"></div>
</template>

<style scoped>
.turnstile-widget {
  min-height: 65px;
}
</style>
