import { defineStore } from "pinia";
import { ref, computed } from "vue";
import * as authApi from "@/api/auth";
import * as usersApi from "@/api/users";

const CHANNEL_NAME = "admin_auth_session";

let crossTabListenerBound = false;
let channel: BroadcastChannel | null = null;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>("");
  const user = ref<usersApi.UserMe | null>(null);

  const isAdmin = computed(() => user.value?.role === "admin");

  function setToken(t: string) {
    token.value = t;
  }

  function broadcast(type: "login" | "logout") {
    channel?.postMessage({ type });
  }

  function attachCrossTabSessionSync() {
    if (typeof window === "undefined" || crossTabListenerBound) return;
    crossTabListenerBound = true;
    if ("BroadcastChannel" in window) {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = (e: MessageEvent<{ type?: string }>) => {
        if (e.data?.type === "logout") {
          clearSession();
        } else if (e.data?.type === "login" && !token.value) {
          void restoreSession().catch(() => clearSession());
        }
      }
    }
  }

  function clearSession() {
    token.value = "";
    user.value = null;
  }

  async function fetchMe() {
    const me = await usersApi.fetchMe();
    user.value = me;
    return me;
  }

  async function login(username: string, password: string, turnstileToken?: string) {
    const result = await authApi.login(username, password, turnstileToken);
    if (result.mfa_required) return result;
    const access_token = result.access_token;
    if (!access_token) throw new Error("登录响应缺少 access token");
    setToken(access_token);
    const me = await fetchMe();
    if (me.role !== "admin") {
      clearSession();
      throw new Error("非管理员账号，无法进入管理后台");
    }
    broadcast("login");
    return result;
  }

  async function verifyMfaLogin(challengeToken: string, code: string) {
    const result = await authApi.verifyMfaLogin(challengeToken, code);
    const access_token = result.access_token;
    if (!access_token) throw new Error("MFA 登录响应缺少 access token");
    setToken(access_token);
    const me = await fetchMe();
    if (me.role !== "admin") {
      clearSession();
      throw new Error("非管理员账号，无法进入管理后台");
    }
    broadcast("login");
    return result;
  }

  function logout() {
    void authApi.logout().catch(() => undefined);
    clearSession();
    broadcast("logout");
  }

  async function restoreSession() {
    const { access_token } = await authApi.refreshAccessToken();
    if (!access_token) throw new Error("刷新响应缺少 access token");
    setToken(access_token);
    const me = await fetchMe();
    if (me.role !== "admin") {
      clearSession();
      throw new Error("非管理员账号，无法进入管理后台");
    }
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
    verifyMfaLogin,
    restoreSession,
    logout,
  };
});
