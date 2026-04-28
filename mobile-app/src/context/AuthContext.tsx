import * as SecureStore from "expo-secure-store";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { UserPublic } from "../api/types";
import * as usersApi from "../api/users";

/** 与路径标识 OM_Media 对齐；升级后本地需重新登录 */
const TOKEN_KEY = "ommedia_access_token";

type AuthCtx = {
  token: string | null;
  /** 当前登录用户；无 token 或未拉取成功时为 null */
  me: UserPublic | null;
  setToken: (t: string | null) => Promise<void>;
  /** 手动刷新 ``/users/me``（例如改资料后） */
  refreshMe: () => Promise<void>;
  isReady: boolean;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [me, setMe] = useState<UserPublic | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const t = await SecureStore.getItemAsync(TOKEN_KEY);
        if (alive) setTokenState(t);
      } finally {
        if (alive) setIsReady(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const refreshMe = useCallback(async () => {
    const t = token?.trim();
    if (!t) {
      setMe(null);
      return;
    }
    try {
      const u = await usersApi.fetchMe(t);
      setMe(u);
    } catch {
      setMe(null);
    }
  }, [token]);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const setToken = useCallback(async (t: string | null) => {
    if (t) await SecureStore.setItemAsync(TOKEN_KEY, t);
    else {
      try {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
      } catch {
        /* 无密钥时忽略 */
      }
      setMe(null);
    }
    setTokenState(t);
  }, []);

  const v = useMemo(
    () => ({ token, me, setToken, refreshMe, isReady }),
    [token, me, setToken, refreshMe, isReady],
  );
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
