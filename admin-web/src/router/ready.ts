import type { Router } from "vue-router";

let appRouter: Router | null = null;

/** 在 `app.use(router)` 之后调用，供 `http` 等在运行期取路由，避免 `api → http → router → auth → api` 静态循环依赖 */
export function bindAppRouter(router: Router): void {
  appRouter = router;
}

export function getAppRouter(): Router | null {
  return appRouter;
}
