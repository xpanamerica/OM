const EXACT_KEYS = new Set([
  "feed_cache",
  "recommendation_cache",
  "interest_state",
  "personalized_feed",
  "personalized_feed_localStorage",
  "user_algorithm_state_cache",
]);

const KEY_PATTERNS = [
  /^feed[:_-]/i,
  /^recommendation[:_-]/i,
  /^interest[:_-]/i,
  /^personalized[_:-]?feed/i,
  /^user[_:-]?algorithm[_:-]?state[_:-]?cache/i,
];

export function clearRecommendationLocalCache(): string[] {
  const removed: string[] = [];
  for (let i = localStorage.length - 1; i >= 0; i -= 1) {
    const key = localStorage.key(i);
    if (!key) continue;
    const shouldRemove = EXACT_KEYS.has(key) || KEY_PATTERNS.some((pattern) => pattern.test(key));
    if (!shouldRemove) continue;
    localStorage.removeItem(key);
    removed.push(key);
  }
  sessionStorage.removeItem("feed_cache");
  sessionStorage.removeItem("recommendation_cache");
  return removed;
}
