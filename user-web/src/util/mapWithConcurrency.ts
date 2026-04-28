/**
 * 对 ``items`` 执行 ``mapper``，最多同时 ``limit`` 个在飞；**结果下标与输入一致**（先完成的会填自己的槽位）。
 */
export async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  mapper: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  if (items.length === 0) return [];
  const results = new Array<R>(items.length);
  let next = 0;
  const workerCount = Math.min(Math.max(1, limit), items.length);

  async function worker(): Promise<void> {
    for (;;) {
      const idx = next++;
      if (idx >= items.length) break;
      results[idx] = await mapper(items[idx]!, idx);
    }
  }

  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}
