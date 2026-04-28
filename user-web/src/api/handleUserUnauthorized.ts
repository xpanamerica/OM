import type { Router } from "vue-router";

/** 供 axios 401 分支与单测复用 */
export function routeMatchedRequiresAuth(router: Router): boolean {
  return router.currentRoute.value.matched.some((r) => r.meta.requiresAuth === true);
}

export async function handleUserUnauthorizedRedirect(opts: {
  hadToken: boolean;
  logout: () => void;
  getRouter: () => Router | null;
  isDev: boolean;
}): Promise<void> {
  if (!opts.hadToken) return;
  opts.logout();
  const router = opts.getRouter();
  if (!router) {
    if (opts.isDev) {
      console.warn(
        "[http] 401：router 未绑定（应在 app.use(router) 后调用 bindAppRouter），已跳过 SPA 跳转",
      );
    }
    return;
  }
  if (routeMatchedRequiresAuth(router)) {
    await router.replace({ name: "auth", query: { redirect: router.currentRoute.value.fullPath } });
  }
}
