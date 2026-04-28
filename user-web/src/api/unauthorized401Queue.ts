/**
 * 将 401 处理串入单一微队列，避免多请求同时 401 时重复 logout/replace（竞态与路由抖动）。
 */
let tail: Promise<void> = Promise.resolve();

export function enqueueUnauthorized401(run: () => Promise<void>): Promise<void> {
  const done = tail.then(run, run);
  tail = done.catch(() => {});
  return done;
}
