import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { AlgorithmState } from "@/api/algorithmReset";

const STORAGE_KEY = "user_algorithm_state";

function readInitialState(): AlgorithmState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as AlgorithmState;
    return data && typeof data.mode === "string" ? data : null;
  } catch {
    return null;
  }
}

export const useAlgorithmStore = defineStore("algorithm", () => {
  const state = ref<AlgorithmState | null>(readInitialState());

  const algorithmMode = computed(() => state.value?.mode ?? "personalized");
  const personalized = computed(() => state.value?.personalized ?? true);
  const isOriginMode = computed(() => algorithmMode.value === "origin" || personalized.value === false);

  function setState(next: AlgorithmState) {
    state.value = next;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function clearState() {
    state.value = null;
    localStorage.removeItem(STORAGE_KEY);
  }

  return {
    state,
    algorithmMode,
    personalized,
    isOriginMode,
    setState,
    clearState,
  };
});
