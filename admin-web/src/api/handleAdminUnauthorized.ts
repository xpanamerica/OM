import type { Router } from "vue-router";

export async function handleAdminUnauthorizedRedirect(opts: {
  clearSession: () => void;
  getRouter: () => Router | null;
  isDev: boolean;
}): Promise<void> {
  opts.clearSession();
  const router = opts.getRouter();
  if (!router) {
    if (opts.isDev) {
      console.warn(
        "[http] 401：router 未绑定（应在 app.use(router) 后调用 bindAppRouter），已跳过跳转登录页",
      );
    }
    return;
  }
  if (router.currentRoute.value.name !== "login") {
    await router.replace({
      name: "login",
      query: { redirect: router.currentRoute.value.fullPath },
    });
  }
}
