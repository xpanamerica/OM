import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme/tokens";
import { getApiBaseUrl, getApiConfigurationError, getWebMixedContentError, LAN_DEPLOY_HINT } from "../config/env";

/**
 * 仅拦截「无法自动修复」的情况：生产非法 API、Web 混合内容。
 * 开发模式下占位符等无效配置已由运行时回退到本机默认，不在此拦截。
 * 版式与 ``LoginFormCard`` 同一套 surface / 圆角，避免首屏像另一套产品。
 */
export function ApiConfigGate({ children }: { children: React.ReactNode }) {
  const cfgErr = getApiConfigurationError();
  const base = getApiBaseUrl();
  const mixErr = base ? getWebMixedContentError(base) : null;
  const err = cfgErr || mixErr;

  if (!err) return <>{children}</>;

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.pad}>
        <View style={styles.card}>
          <Text style={styles.title}>{cfgErr ? "API 地址配置错误" : "无法访问 API（混合内容）"}</Text>
          <Text style={styles.body}>{err}</Text>
          <Text style={styles.h2}>请修改</Text>
          <Text style={styles.mono}>
            mobile-app/.env 中的 EXPO_PUBLIC_API_BASE_URL{"\n\n"}
            示例：{"\n"}
            EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000/api/v1
          </Text>
          <Text style={styles.h2}>说明</Text>
          <Text style={styles.body}>{LAN_DEPLOY_HINT}</Text>
          <Text style={styles.footer}>修改后请完全退出 Metro 并重新执行 npm start。</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 20, paddingTop: 48, flexGrow: 1 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  title: { color: "#fecaca", fontSize: 20, fontWeight: "900", marginBottom: 12 },
  h2: { color: colors.text, fontSize: 15, fontWeight: "800", marginTop: 16, marginBottom: 8 },
  body: { color: colors.textMuted, fontSize: 14, lineHeight: 22 },
  mono: {
    color: colors.accent,
    fontSize: 13,
    lineHeight: 20,
    fontFamily: "monospace",
    backgroundColor: "rgba(0,0,0,0.25)",
    padding: 12,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  footer: { color: colors.textMuted, fontSize: 12, marginTop: 24, lineHeight: 18 },
});
