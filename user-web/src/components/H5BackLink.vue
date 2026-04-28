<script setup lang="ts">
import type { RouteLocationRaw } from "vue-router";
import { RouterLink } from "vue-router";

defineProps<{
  to: RouteLocationRaw;
  label: string;
}>();
</script>

<template>
  <div class="h5-mobile-only h5-back-wrap">
    <RouterLink class="h5-back-link" :to="to">
      <span class="h5-back-link__icon" aria-hidden="true">‹</span>
      {{ label }}
    </RouterLink>
  </div>
</template>
