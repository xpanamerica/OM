import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import * as usersApi from "../api/users";
import { useRootStackNavigation } from "../navigation/useRootStackNavigation";
import { RootBottomNav } from "../components/RootBottomNav";

type Props = NativeStackScreenProps<RootStackParamList, "History">;

export function HistoryScreen(_props: Props) {
  const { token } = useAuth();
  const rootNav = useRootStackNavigation();
  const [items, setItems] = useState<Awaited<ReturnType<typeof usersApi.listMyViewRecords>>["items"]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    const r = await usersApi.listMyViewRecords({ offset: 0, limit: 50 }, token);
    setItems(r.items);
  }, [token]);

  useEffect(() => {
    let c = false;
    setLoading(true);
    void load()
      .catch(() => {})
      .finally(() => {
        if (!c) setLoading(false);
      });
    return () => {
      c = true;
    };
  }, [load]);

  async function onRefresh() {
    if (!token) return;
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  if (!token) {
    return (
      <View style={styles.screen}>
        <View style={styles.center}>
          <Text style={styles.hint}>请先登录</Text>
        </View>
        <RootBottomNav active="Profile" />
      </View>
    );
  }

  if (loading && items.length === 0) {
    return (
      <View style={styles.screen}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
        <RootBottomNav active="Profile" />
      </View>
    );
  }

  return (
    <View style={styles.screen}>
      <FlatList
        style={styles.root}
        contentContainerStyle={styles.pad}
        data={items}
        keyExtractor={(it) => it.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
        renderItem={({ item }) => (
          <Pressable
            style={styles.row}
            onPress={() => rootNav?.navigate("Detail", { id: item.video_id })}
          >
            <Text style={styles.rowTitle} numberOfLines={2}>
              {item.video_title ?? "视频"}
            </Text>
            <Text style={styles.rowMeta}>
              进度 {Math.floor(item.progress_seconds)}s ·{" "}
              {new Date(item.last_viewed_at).toLocaleString()}
            </Text>
          </Pressable>
        )}
        ListEmptyComponent={<Text style={styles.empty}>暂无播放记录</Text>}
      />
      <RootBottomNav active="Profile" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 16, paddingBottom: 96 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg },
  hint: { color: colors.textMuted },
  row: {
    padding: 14,
    marginBottom: 10,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  rowTitle: { color: colors.text, fontSize: 15, fontWeight: "700" },
  rowMeta: { color: colors.textMuted, fontSize: 12, marginTop: 6 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: 24 },
});
