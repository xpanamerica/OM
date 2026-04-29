import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { colors } from "../theme/tokens";
import { login } from "../api/auth";
import { ApiHttpError } from "../api/client";
import { getApiBaseUrl, getTurnstileOrigin, getTurnstileSiteKey, LAN_DEPLOY_HINT } from "../config/env";
import { TurnstileChallenge } from "./TurnstileChallenge";

type Props = {
  /** 登录成功并取得 access_token 后调用（由外层写入 SecureStore / 导航） */
  onSuccess: (accessToken: string) => void | Promise<void>;
  showCancel?: boolean;
  onCancel?: () => void;
  /** ``embedded``：用于 Tab 内个人中心等场景，不占满全屏高度 */
  variant?: "screen" | "embedded";
};

/**
 * 与 ``LoginScreen`` 使用同一套视觉与交互，避免「全屏登录」与「个人中心内嵌登录」两套样式。
 */
export function LoginFormCard({ onSuccess, showCancel, onCancel, variant = "screen" }: Props) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failedCount, setFailedCount] = useState(0);
  const [turnstileToken, setTurnstileToken] = useState("");
  const showTurnstile = failedCount >= 3;
  const turnstileSiteKey = getTurnstileSiteKey();
  const turnstileOrigin = getTurnstileOrigin();

  async function submit() {
    if (showTurnstile && !turnstileToken) {
      setErr(turnstileSiteKey ? "请先完成人机验证。" : "人机验证暂未配置，请联系管理员。");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const { access_token } = await login(u.trim(), p, showTurnstile ? turnstileToken : undefined);
      setFailedCount(0);
      setTurnstileToken("");
      await onSuccess(access_token);
    } catch (e) {
      if (e instanceof ApiHttpError && (e.code === "TURNSTILE_REQUIRED" || e.code === "TURNSTILE_INVALID")) {
        setFailedCount((n) => Math.max(n, 3));
      } else {
        setFailedCount((n) => n + 1);
      }
      setTurnstileToken("");
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const rootStyle = variant === "embedded" ? styles.rootEmbedded : styles.root;

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={rootStyle}>
      <View style={styles.card}>
        <Text style={styles.h}>登录</Text>
        <Text style={styles.sub}>
          OAuth2 密码模式，与 user-web 相同 POST /auth/login。账号须在后端已存在。
        </Text>
        <View style={styles.hintBox}>
          <Text style={styles.hintTitle}>本机作服务器 / 他人登录</Text>
          <Text style={styles.hintBody}>{LAN_DEPLOY_HINT}</Text>
          <Text style={styles.hintMono} numberOfLines={2}>
            当前 API：{getApiBaseUrl()}
          </Text>
        </View>
        <Text style={styles.label}>用户名或邮箱</Text>
        <TextInput
          autoCapitalize="none"
          value={u}
          onChangeText={setU}
          style={styles.input}
          placeholder="username / email"
          placeholderTextColor={colors.textMuted}
        />
        <Text style={styles.label}>密码</Text>
        <TextInput
          secureTextEntry
          value={p}
          onChangeText={setP}
          style={styles.input}
          placeholder="••••••••"
          placeholderTextColor={colors.textMuted}
        />
        {showTurnstile ? (
          <TurnstileChallenge
            siteKey={turnstileSiteKey}
            origin={turnstileOrigin}
            action="login"
            onToken={setTurnstileToken}
            onError={setErr}
          />
        ) : null}
        {err ? <Text style={styles.err}>{err}</Text> : null}
        <Pressable onPress={submit} disabled={busy} style={[styles.btn, busy && styles.dis]}>
          <Text style={styles.btnTxt}>{busy ? "登录中…" : "登录"}</Text>
        </Pressable>
        {showCancel && onCancel ? (
          <Pressable onPress={onCancel} style={styles.back}>
            <Text style={styles.backTxt}>取消</Text>
          </Pressable>
        ) : null}
      </View>
    </KeyboardAvoidingView>
  );
}

export const loginFormCardStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, justifyContent: "center", padding: 20 },
  rootEmbedded: { backgroundColor: colors.bg, paddingHorizontal: 4, paddingVertical: 12 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  h: { color: colors.text, fontSize: 22, fontWeight: "800" },
  sub: { color: colors.textMuted, fontSize: 12, marginTop: 8, marginBottom: 10 },
  hintBox: {
    marginBottom: 14,
    padding: 10,
    borderRadius: 10,
    backgroundColor: "rgba(34,211,238,0.08)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(34,211,238,0.25)",
  },
  hintTitle: { color: colors.accent, fontSize: 12, fontWeight: "800", marginBottom: 6 },
  hintBody: { color: colors.textMuted, fontSize: 11, lineHeight: 16, marginBottom: 8 },
  hintMono: { color: colors.text, fontSize: 10, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  label: { color: colors.textMuted, fontSize: 12, fontWeight: "700", marginBottom: 6 },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    color: colors.text,
    marginBottom: 12,
    fontSize: 16,
  },
  err: { color: colors.danger, marginBottom: 10 },
  btn: { backgroundColor: colors.accent, paddingVertical: 14, borderRadius: 12, alignItems: "center", marginTop: 8 },
  dis: { opacity: 0.6 },
  btnTxt: { color: "#042f2e", fontWeight: "800", fontSize: 16 },
  back: { marginTop: 16, alignItems: "center" },
  backTxt: { color: colors.accent, fontWeight: "700" },
});

const styles = loginFormCardStyles;
