/** 多请求并发 401 时串行执行登出/跳转，避免重复 replace 与竞态。 */
let tail: Promise<void> = Promise.resolve();

export function enqueueUnauthorized401(run: () => Promise<void>): Promise<void> {
  const done = tail.then(run, run);
  tail = done.catch(() => {});
  return done;
}
