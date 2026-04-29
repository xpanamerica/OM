/* eslint-env node */
/**
 * 动态配置：把 EXPO_PUBLIC_API_BASE_URL 写入 extra，供运行时与 Metro 内联变量共用。
 * 保留 app.json 中的 name、slug、ios、android 等静态字段。
 */
const appJson = require("./app.json");

const apiBaseUrl =
  (process.env.EXPO_PUBLIC_API_BASE_URL && String(process.env.EXPO_PUBLIC_API_BASE_URL).trim()) || "";
const turnstileSiteKey =
  (process.env.EXPO_PUBLIC_TURNSTILE_SITE_KEY && String(process.env.EXPO_PUBLIC_TURNSTILE_SITE_KEY).trim()) || "";
const turnstileOrigin =
  (process.env.EXPO_PUBLIC_TURNSTILE_ORIGIN && String(process.env.EXPO_PUBLIC_TURNSTILE_ORIGIN).trim()) || "";

module.exports = {
  expo: {
    ...appJson.expo,
    extra: {
      ...(appJson.expo.extra || {}),
      apiBaseUrl,
      turnstileSiteKey,
      turnstileOrigin,
    },
  },
};
