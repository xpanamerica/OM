/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  Aliplayer?: new (opts: Record<string, unknown>) => AliplayerInstance;
}

interface AliplayerInstance {
  dispose?: () => void;
  getCurrentTime?: () => number;
  on?: (ev: string, fn: () => void) => void;
  /** 阿里云 Web 播放器：调整尺寸（存在则随屏旋转更新） */
  setPlayerSize?: (width: string | number, height: string | number) => void;
}
