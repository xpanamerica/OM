const ALIPLAYER_CSS =
  "https://g.alicdn.com/de/prismplayer/2.15.2/skins/default/aliplayer-min.css";

let cssPromise: Promise<void> | null = null;

/** 仅播放前拉取，减轻非播放页首屏；并发调用合并为同一 Promise */
export function injectAliplayerCssOnce(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  if (cssPromise) return cssPromise;

  cssPromise = new Promise((resolve, reject) => {
    const dup = document.querySelector<HTMLLinkElement>('link[data-app="aliplayer-prism-css"]');
    if (dup?.href?.includes("aliplayer-min.css")) {
      resolve();
      return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = ALIPLAYER_CSS;
    link.crossOrigin = "anonymous";
    link.setAttribute("data-app", "aliplayer-prism-css");
    link.onload = () => resolve();
    link.onerror = () => {
      cssPromise = null;
      link.remove();
      reject(new Error("播放器样式加载失败"));
    };
    document.head.appendChild(link);
  });

  return cssPromise;
}
