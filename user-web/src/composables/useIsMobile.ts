import { onBeforeUnmount, onMounted, ref } from "vue";

const MOBILE_MQ = "(max-width: 767px)";

function readMatches(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(MOBILE_MQ).matches;
}

/**
 * 与 H5 / TabBar 断点一致：≤767px 视为手机。
 * 首帧即读取 matchMedia，避免 mounted 前误判桌面导致顶栏/布局闪动。
 */
export function useIsMobile() {
  const isMobile = ref(readMatches());
  let mql: MediaQueryList | null = null;

  function onMqChange() {
    isMobile.value = mql?.matches ?? readMatches();
  }

  onMounted(() => {
    mql = window.matchMedia(MOBILE_MQ);
    isMobile.value = mql.matches;
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onMqChange);
    } else {
      mql.addListener(onMqChange);
    }
  });

  onBeforeUnmount(() => {
    if (mql) {
      if (typeof mql.removeEventListener === "function") {
        mql.removeEventListener("change", onMqChange);
      } else {
        mql.removeListener(onMqChange);
      }
    }
    mql = null;
  });

  return { isMobile };
}
