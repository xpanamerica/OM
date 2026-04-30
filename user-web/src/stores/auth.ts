import { defineStore } from "pinia";
import { ref, computed } from "vue";
import * as authApi from "@/api/auth";
import * as usersApi from "@/api/users";

const CHANNEL_NAME = "user_auth_session";

let crossTabListenerBound = false;
let channel: BroadcastChannel | null = null;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>("");
  const user = ref<usersApi.UserPublic | null>(null);

  const isLoggedIn = computed(() => Boolean(token.value));

  function setToken(t: string) {
    token.value = t;
  }

  function broadcast(type: "login" | "logout") {
    channel?.postMessage({ type });
  }

  /** 其它标签页登录/退出时同步状态，但不广播 access token。 */
  function attachCrossTabSessionSync() {
    if (typeof window === "undefined" || crossTabListenerBound) return;
    crossTabListenerBound = true;
    if ("BroadcastChannel" in window) {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = (e: MessageEvent<{ type?: string }>) => {
        if (e.data?.type === "logout") {
          clearSession();
        } else if (e.data?.type === "login" && !token.value) {
          void restoreSession();
        }
      }
    }
  }

  function clearSession() {
    token.value = "";
    user.value = null;
  }

  function logout() {
    void authApi.logout().catch(() => undefined);
    clearSession();
    broadcast("logout");
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
    await fetchMe();
    broadcast("login");
    return result;
  }

  async function verifyMfaLogin(challengeToken: string, code: string) {
    const result = await authApi.verifyMfaLogin(challengeToken, code);
    const access_token = result.access_token;
    if (!access_token) throw new Error("MFA 登录响应缺少 access token");
    setToken(access_token);
    await fetchMe();
    broadcast("login");
    return result;
  }

  async function restoreSession() {
    const { access_token } = await authApi.refreshAccessToken();
    if (!access_token) throw new Error("刷新响应缺少 access token");
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
    clearSession,
    logout,
    fetchMe,
    login,
    verifyMfaLogin,
    restoreSession,
    registerAndHintLogin,
  };
});
