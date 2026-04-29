import React, { useMemo } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { colors } from "../theme/tokens";

type Props = {
  siteKey: string;
  origin: string;
  action?: string;
  onToken: (token: string) => void;
  onError?: (message: string) => void;
};

function html(siteKey: string, action?: string): string {
  const safeSiteKey = JSON.stringify(siteKey);
  const safeAction = JSON.stringify(action || "");
  return `<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>
  <style>
    html, body { margin: 0; padding: 0; background: transparent; }
    #widget { min-height: 65px; display: flex; align-items: center; justify-content: center; }
  </style>
</head>
<body>
  <div id="widget"></div>
  <script>
    function send(payload) {
      window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify(payload));
    }
    function render() {
      if (!window.turnstile) {
        setTimeout(render, 50);
        return;
      }
      window.turnstile.render("#widget", {
        sitekey: ${safeSiteKey},
        action: ${safeAction} || undefined,
        theme: "light",
        callback: function(token) { send({ type: "token", token: token }); },
        "expired-callback": function() { send({ type: "expired" }); },
        "error-callback": function(code) { send({ type: "error", code: code }); }
      });
    }
    render();
  </script>
</body>
</html>`;
}

export function TurnstileChallenge({ siteKey, origin, action, onToken, onError }: Props) {
  const source = useMemo(() => ({ html: html(siteKey, action), baseUrl: origin }), [siteKey, origin, action]);

  function handleMessage(event: WebViewMessageEvent) {
    try {
      const data = JSON.parse(event.nativeEvent.data) as { type?: string; token?: string; code?: string };
      if (data.type === "token" && data.token) {
        onToken(data.token);
      } else if (data.type === "expired") {
        onToken("");
      } else if (data.type === "error") {
        onToken("");
        onError?.(`Turnstile 验证加载失败：${data.code || "unknown"}`);
      }
    } catch {
      onError?.("Turnstile 验证返回了无法解析的数据");
    }
  }

  if (!siteKey) {
    return <Text style={styles.hint}>人机验证暂未配置，请联系管理员。</Text>;
  }

  if (Platform.OS === "web") {
    return <Text style={styles.hint}>请在用户站 Web 页面完成 Turnstile 登录验证。</Text>;
  }

  return (
    <View style={styles.box}>
      <WebView
        originWhitelist={["https://*", "http://*"]}
        source={source}
        onMessage={handleMessage}
        javaScriptEnabled
        domStorageEnabled
        scrollEnabled={false}
        style={styles.webview}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    height: 78,
    overflow: "hidden",
    borderRadius: 10,
    backgroundColor: colors.surface,
    marginBottom: 12,
  },
  webview: {
    flex: 1,
    backgroundColor: "transparent",
  },
  hint: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 12,
  },
});
