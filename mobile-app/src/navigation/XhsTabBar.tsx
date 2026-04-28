import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import { useRootStackNavigation } from "./useRootStackNavigation";

const BRAND_BLUE = colors.accent;

type TabVisual = { key: string; label: string; icon: keyof typeof Ionicons.glyphMap; iconActive: keyof typeof Ionicons.glyphMap };

const LEFT: TabVisual[] = [
  { key: "Feed", label: "首页", icon: "home-outline", iconActive: "home" },
  { key: "Discover", label: "发现", icon: "compass-outline", iconActive: "compass" },
];

const RIGHT: TabVisual[] = [
  { key: "Messages", label: "消息", icon: "chatbubble-ellipses-outline", iconActive: "chatbubble-ellipses" },
  { key: "Profile", label: "个人", icon: "person-circle-outline", iconActive: "person-circle" },
];

export function XhsTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const rootNav = useRootStackNavigation();

  function renderSideItem(routeName: string, visual: TabVisual) {
    const routeIndex = state.routes.findIndex((r) => r.name === routeName);
    if (routeIndex < 0) return null;
    const focused = state.index === routeIndex;
    const color = focused ? BRAND_BLUE : colors.textMuted;
    const onPress = () => {
      const event = navigation.emit({
        type: "tabPress",
        target: state.routes[routeIndex].key,
        canPreventDefault: true,
      });
      if (routeName === "Messages" && !token) {
        event.preventDefault();
        rootNav?.navigate("Login");
        return;
      }
      if (!focused && !event.defaultPrevented) {
        navigation.navigate(routeName);
      }
    };
    return (
      <Pressable key={visual.key} accessibilityRole="button" onPress={onPress} style={styles.sideBtn}>
        <Ionicons name={focused ? visual.iconActive : visual.icon} size={22} color={color} />
        <Text style={[styles.sideLbl, focused && styles.sideLblOn]} numberOfLines={1}>
          {visual.label}
        </Text>
      </Pressable>
    );
  }

  const createIndex = state.routes.findIndex((r) => r.name === "Create");
  const createFocused = state.index === createIndex;
  const onCreate = () => {
    const key = state.routes[createIndex]?.key;
    if (!key) return;
    const e = navigation.emit({ type: "tabPress", target: key, canPreventDefault: true });
    if (!token) {
      e.preventDefault();
      rootNav?.navigate("Login");
      return;
    }
    if (!e.defaultPrevented) navigation.navigate("Create");
  };

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 6) }]}>
      <View style={styles.side}>
        {LEFT.map((v) => renderSideItem(v.key, v))}
      </View>
      <View style={styles.centerSlot}>
        <Pressable
          onPress={onCreate}
          style={[styles.fab, createFocused && styles.fabOn]}
          accessibilityRole="button"
          accessibilityLabel="创作"
        >
          <Ionicons name="add" size={34} color="#fff" />
        </Pressable>
      </View>
      <View style={styles.side}>
        {RIGHT.map((v) => renderSideItem(v.key, v))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    paddingTop: 6,
    paddingHorizontal: 4,
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  side: { flex: 1, flexDirection: "row", justifyContent: "space-around", alignItems: "flex-end" },
  sideBtn: { flex: 1, alignItems: "center", paddingVertical: 4, gap: 2 },
  sideLbl: { fontSize: 10, fontWeight: "600", color: colors.textMuted },
  sideLblOn: { color: BRAND_BLUE, fontWeight: "800" },
  centerSlot: {
    width: 88,
    alignItems: "center",
    justifyContent: "flex-end",
    marginBottom: 2,
  },
  fab: {
    width: 52,
    height: 44,
    borderRadius: 14,
    backgroundColor: BRAND_BLUE,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.35,
    shadowRadius: 4,
    elevation: 6,
  },
  fabOn: { opacity: 0.92 },
});
