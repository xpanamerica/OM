import { ref } from "vue";
import * as algorithmResetApi from "@/api/algorithmReset";
import { useAlgorithmStore } from "@/stores/algorithm";
import { clearRecommendationLocalCache } from "@/util/clearRecommendationLocalCache";

export const ALGORITHM_RESET_EVENT = "om:algorithm-reset";

export function useAlgorithmReset() {
  const loading = ref(false);
  const error = ref<unknown>(null);
  const algorithm = useAlgorithmStore();

  async function resetAlgorithm() {
    if (loading.value) return null;
    loading.value = true;
    error.value = null;
    try {
      const result = await algorithmResetApi.algorithmReset();
      clearRecommendationLocalCache();
      algorithm.setState(result.data);
      window.dispatchEvent(new CustomEvent(ALGORITHM_RESET_EVENT, { detail: result.data }));
      return result;
    } catch (e) {
      error.value = e;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    error,
    resetAlgorithm,
  };
}
