import { defineStore } from "pinia";
import { ref, computed } from "vue";
import * as authApi from "@/api/auth";
import * as usersApi from "@/api/users";

const STORAGE_KEY = "user_access_token";

let crossTabListenerBound = false;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(localStorage.getItem(STORAGE_KEY) ?? "");
  const user = ref<usersApi.UserPublic | null>(null);

  const isLoggedIn = computed(() => Boolean(token.value));

  function setToken(t: string) {
    token.value = t;
    if (t) localStorage.setItem(STORAGE_KEY, t);
    else localStorage.removeItem(STORAGE_KEY);
  }

  /** 其它标签页登录/退出时同步本会话，避免「一边已登出一边仍带旧 Token 请求」 */
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
        void fetchMe().catch(() => logout());
      }
    });
  }

  function logout() {
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
    await fetchMe();
  }

  async function registerAndHintLogin(body: authApi.RegisterBody) {
    await authApi.register(body);
  }

  return {
    token,
    user,
    isLoggedIn,
    setToken,
    attachCrossTabSessionSync,
    logout,
    fetchMe,
    login,
    registerAndHintLogin,
  };
});
