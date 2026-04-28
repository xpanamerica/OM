/**
 * 首屏后再预取高频页面 chunk，减轻与首页接口的带宽/连接竞争；省流模式跳过。
 */
export function scheduleIdleRoutePrefetch(): void {
  if (typeof window === "undefined") return;
  const conn = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  if (conn?.saveData) return;

  const run = () => {
    void import("@/views/VideoListView.vue");
    void import("@/views/VideoDetailView.vue");
    void import("@/views/SearchView.vue");
  };

  if (typeof globalThis.requestIdleCallback === "function") {
    globalThis.requestIdleCallback(() => run(), { timeout: 2800 });
  } else {
    globalThis.setTimeout(run, 1600);
  }
}
