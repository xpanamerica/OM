import { defineStore } from "pinia";
import { ref, computed } from "vue";
import * as authApi from "@/api/auth";
import * as usersApi from "@/api/users";

const STORAGE_KEY = "admin_access_token";

let crossTabListenerBound = false;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(localStorage.getItem(STORAGE_KEY) ?? "");
  const user = ref<usersApi.UserMe | null>(null);

  const isAdmin = computed(() => user.value?.role === "admin");

  function setToken(t: string) {
    token.value = t;
    if (t) localStorage.setItem(STORAGE_KEY, t);
    else localStorage.removeItem(STORAGE_KEY);
  }

  function attachCrossTabSessionSync() {
    if (typeof window === "undefined" || crossTabListenerBound) return;
    crossTabListenerBound = true;
    window.addEventListener("storage", (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY || e.storageArea !== localStorage) return;
      if (!e.newValue) {
        if (token.value) {
          token.value = "";
          user.value = null;
        }
        return;
      }
      if (e.newValue !== token.value) {
        token.value = e.newValue;
        void fetchMe().catch(() => clearSession());
      }
    });
  }

  function clearSession() {
    token.value = "";
    user.value = null;
    localStorage.removeItem(STORAGE_KEY);
  }

  async function fetchMe() {
    const me = await usersApi.fetchMe();
    user.value = me;
    return me;
  }

  async function login(username: string, password: string) {
    const { access_token } = await authApi.login(username, password);
    setToken(access_token);
    const me = await fetchMe();
    if (me.role !== "admin") {
      clearSession();
      throw new Error("非管理员账号，无法进入管理后台");
    }
  }

  function logout() {
    clearSession();
  }

  return {
    token,
    user,
    isAdmin,
    setToken,
    attachCrossTabSessionSync,
    clearSession,
    fetchMe,
    login,
    logout,
  };
});
