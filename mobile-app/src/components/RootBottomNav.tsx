import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import type { MainTabParamList, RootStackParamList } from "../navigation/types";

type ActiveTab = keyof MainTabParamList;
type TabItem = {
  key: ActiveTab;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
};

const TABS: TabItem[] = [
  { key: "Feed", label: "首页", icon: "home-outline", iconActive: "home" },
  { key: "Discover", label: "发现", icon: "compass-outline", iconActive: "compass" },
  { key: "Messages", label: "消息", icon: "chatbubble-ellipses-outline", iconActive: "chatbubble-ellipses" },
  { key: "Profile", label: "个人", icon: "person-circle-outline", iconActive: "person-circle" },
];

export function RootBottomNav({ active = "Feed" }: { active?: ActiveTab }) {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { token } = useAuth();

  function go(tab: ActiveTab) {
    if ((tab === "Messages" || tab === "Profile") && !token) {
      navigation.navigate("Login");
      return;
    }
    navigation.navigate("Main", { screen: tab });
  }

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 6) }]}>
      {TABS.slice(0, 2).map((tab) => (
        <Pressable key={tab.key} style={styles.btn} onPress={() => go(tab.key)}>
          <Ionicons name={active === tab.key ? tab.iconActive : tab.icon} size={22} color={active === tab.key ? colors.accent : colors.textMuted} />
          <Text style={[styles.label, active === tab.key && styles.labelOn]}>{tab.label}</Text>
        </Pressable>
      ))}
      <Pressable style={styles.fab} onPress={() => (token ? navigation.navigate("Main", { screen: "Create" }) : navigation.navigate("Login"))}>
        <Ionicons name="add" size={34} color="#fff" />
      </Pressable>
      {TABS.slice(2).map((tab) => (
        <Pressable key={tab.key} style={styles.btn} onPress={() => go(tab.key)}>
          <Ionicons name={active === tab.key ? tab.iconActive : tab.icon} size={22} color={active === tab.key ? colors.accent : colors.textMuted} />
          <Text style={[styles.label, active === tab.key && styles.labelOn]}>{tab.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-around",
    paddingTop: 6,
    paddingHorizontal: 4,
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  btn: { flex: 1, alignItems: "center", paddingVertical: 4, gap: 2 },
  label: { color: colors.textMuted, fontSize: 10, fontWeight: "600" },
  labelOn: { color: colors.accent, fontWeight: "800" },
  fab: {
    width: 52,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
    marginHorizontal: 8,
    marginBottom: 2,
  },
});
