/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_TURNSTILE_SITE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  Aliplayer?: new (opts: Record<string, unknown>) => AliplayerInstance;
  turnstile?: TurnstileApi;
}

interface AliplayerInstance {
  dispose?: () => void;
  getCurrentTime?: () => number;
  on?: (ev: string, fn: () => void) => void;
  /** 阿里云 Web 播放器：调整尺寸（存在则随屏旋转更新） */
  setPlayerSize?: (width: string | number, height: string | number) => void;
}

interface TurnstileApi {
  render: (
    container: string | HTMLElement,
    options: {
      sitekey: string;
      action?: string;
      theme?: "light" | "dark" | "auto";
      callback?: (token: string) => void;
      "expired-callback"?: () => void;
      "error-callback"?: () => void;
    },
  ) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId: string) => void;
}
