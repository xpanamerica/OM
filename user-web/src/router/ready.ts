import type { Router } from "vue-router";

let appRouter: Router | null = null;

/** 在 `app.use(router)` 之后调用一次，供 `http` 等模块在运行期安全取路由（避免与 `api → http → router → auth → api` 的静态环） */
export function bindAppRouter(router: Router): void {
  appRouter = router;
}

export function getAppRouter(): Router | null {
  return appRouter;
}
