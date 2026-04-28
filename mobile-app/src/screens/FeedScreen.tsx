import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import type { CompositeScreenProps } from "@react-navigation/native";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import type { MainTabParamList, RootStackParamList } from "../navigation/types";
import { colors, appBrandName } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import { useHomeFeed, type HomeFeedTab } from "../hooks/useHomeFeed";
import { XhsFeedCard } from "../components/XhsFeedCard";
import { useRootStackNavigation } from "../navigation/useRootStackNavigation";
import {
  getApiBaseUrl,
  getLastIgnoredInvalidApiRaw,
  hasConfiguredApiBase,
  shouldWarnLanMisconfig,
} from "../config/env";

const BRAND_BLUE = colors.accent;

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, "Feed">,
  NativeStackScreenProps<RootStackParamList>
>;

export function FeedScreen({ navigation: tabNavigation }: Props) {
  const insets = useSafeAreaInsets();
  const { token, me } = useAuth();
  const rootNav = useRootStackNavigation();
  const [homeTab, setHomeTab] = useState<HomeFeedTab>("discover");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { flatItems, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, refetch, isFetching } =
    useHomeFeed(homeTab, token);
  const showRefreshing = isFetching && !isFetchingNextPage;

  const onTab = useCallback(
    (t: HomeFeedTab) => {
      setHomeTab(t);
    },
    [],
  );

  const openDiscoverSearch = useCallback(() => {
    tabNavigation.navigate("Discover");
  }, [tabNavigation]);

  const listFooter = (
    <View>
      {isFetchingNextPage ? (
        <View style={styles.footer}>
          <ActivityIndicator color={BRAND_BLUE} />
        </View>
      ) : null}
      {__DEV__ ? (
        <Text style={styles.devFoot} numberOfLines={3}>
          API: {getApiBaseUrl()}
          {getLastIgnoredInvalidApiRaw() ? ` · 已忽略无效配置` : ""}
          {shouldWarnLanMisconfig() ? ` · 真机请检查局域网 API` : ""}
          {!hasConfiguredApiBase() && !getLastIgnoredInvalidApiRaw() ? ` · 未显式配置 API` : ""}
        </Text>
      ) : null}
    </View>
  );

  const showLoginHint = homeTab === "following" && !token;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View pointerEvents="none" style={styles.cosmosOne} />
      <View pointerEvents="none" style={styles.cosmosTwo} />
      <View pointerEvents="none" style={styles.starVeil}>
        <View style={styles.starA} />
        <View style={styles.starB} />
        <View style={styles.starC} />
      </View>
      <View style={styles.topBar}>
        <Pressable
          accessibilityLabel="打开菜单"
          hitSlop={12}
          onPress={() => setDrawerOpen(true)}
          style={styles.iconBtn}
        >
          <Ionicons name="menu" size={24} color={colors.text} />
        </Pressable>
        <View style={styles.tabs}>
          {(
            [
              ["following", "关注"],
              ["discover", "发现"],
              ["explore", "探索"],
            ] as const
          ).map(([key, label]) => {
            const on = homeTab === key;
            return (
              <Pressable key={key} onPress={() => onTab(key)} style={styles.tabHit}>
                <Text style={[styles.tabTxt, on && styles.tabTxtOn]}>{label}</Text>
                {on ? <View style={styles.tabUnd} /> : <View style={styles.tabUndPh} />}
              </Pressable>
            );
          })}
        </View>
        <Pressable accessibilityLabel="搜索与发现" hitSlop={12} onPress={openDiscoverSearch} style={styles.iconBtn}>
          <Ionicons name="search-outline" size={22} color={colors.text} />
        </Pressable>
      </View>

      {showLoginHint ? (
        <View style={styles.loginBanner}>
          <Text style={styles.loginBannerTxt}>登录后可查看关注作者的更新</Text>
          <Pressable onPress={() => rootNav?.navigate("Login")}>
            <Text style={styles.loginBannerBtn}>去登录</Text>
          </Pressable>
        </View>
      ) : null}

      <FlatList
        data={flatItems}
        key={`${homeTab}-${token ?? ""}`}
        keyExtractor={(it) => it.id}
        numColumns={2}
        columnWrapperStyle={styles.colWrap}
        refreshing={showRefreshing}
        onRefresh={() => void refetch()}
        renderItem={({ item }) => (
          <XhsFeedCard
            item={item}
            onPress={() => rootNav?.navigate("Detail", { id: item.id })}
            onAuthorPress={() => rootNav?.navigate("UserProfile", { id: item.author_id })}
          />
        )}
        ListEmptyComponent={
          isLoading ? (
            <View style={styles.center}>
              <ActivityIndicator color={BRAND_BLUE} />
            </View>
          ) : showLoginHint ? (
            <Text style={styles.empty}>登录后查看关注动态</Text>
          ) : (
            <Text style={styles.empty}>暂无内容</Text>
          )
        }
        onEndReached={() => {
          if (hasNextPage && !isFetchingNextPage && !showLoginHint) void fetchNextPage();
        }}
        onEndReachedThreshold={0.4}
        contentContainerStyle={styles.listPad}
        ListFooterComponent={listFooter}
      />

      <Modal visible={drawerOpen} animationType="fade" transparent onRequestClose={() => setDrawerOpen(false)}>
        <View style={styles.modalRow}>
          <View style={[styles.drawer, { paddingTop: insets.top + 12 }]}>
            <Text style={styles.drawerBrand}>{appBrandName}</Text>
            <Text style={styles.drawerHi} numberOfLines={1}>
              {me?.username ? `Hi，${me.username}` : "访客"}
            </Text>
            <Pressable
              style={styles.drawerLink}
              onPress={() => {
                setDrawerOpen(false);
                tabNavigation.navigate("Feed");
              }}
            >
              <Text style={styles.drawerLinkTxt}>首页</Text>
            </Pressable>
            <Pressable
              style={styles.drawerLink}
              onPress={() => {
                setDrawerOpen(false);
                if (!token) rootNav?.navigate("Login");
                else rootNav?.navigate("History");
              }}
            >
              <Text style={styles.drawerLinkTxt}>历史记录</Text>
            </Pressable>
            <Pressable
              style={styles.drawerLink}
              onPress={() => {
                setDrawerOpen(false);
                if (!token) rootNav?.navigate("Login");
                else rootNav?.navigate("Favorites");
              }}
            >
              <Text style={styles.drawerLinkTxt}>个人收藏</Text>
            </Pressable>
            <Pressable
              style={styles.drawerLink}
              onPress={() => {
                setDrawerOpen(false);
                if (!token) rootNav?.navigate("Login");
                else tabNavigation.navigate("Messages");
              }}
            >
              <Text style={styles.drawerLinkTxt}>互动消息</Text>
            </Pressable>
            <Pressable
              style={styles.drawerLink}
              onPress={() => {
                setDrawerOpen(false);
                tabNavigation.navigate("Profile");
              }}
            >
              <Text style={styles.drawerLinkTxt}>个人中心</Text>
            </Pressable>
          </View>
          <Pressable style={styles.backdrop} onPress={() => setDrawerOpen(false)} />
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, overflow: "hidden" },
  cosmosOne: {
    position: "absolute",
    right: -110,
    top: -80,
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: "rgba(34,211,238,0.16)",
  },
  cosmosTwo: {
    position: "absolute",
    left: -120,
    top: 190,
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: "rgba(139,92,246,0.13)",
  },
  starVeil: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },
  starA: { position: "absolute", left: 32, top: 88, width: 2, height: 2, borderRadius: 1, backgroundColor: "rgba(255,255,255,0.72)" },
  starB: { position: "absolute", right: 74, top: 156, width: 3, height: 3, borderRadius: 2, backgroundColor: "rgba(103,232,249,0.7)" },
  starC: { position: "absolute", left: "48%", top: 260, width: 2, height: 2, borderRadius: 1, backgroundColor: "rgba(255,255,255,0.58)" },
  topBar: {
    zIndex: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 6,
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(103,232,249,0.13)",
    backgroundColor: "rgba(2,6,23,0.40)",
  },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  tabs: { flex: 1, flexDirection: "row", justifyContent: "center", alignItems: "flex-end", gap: 4 },
  tabHit: { alignItems: "center", paddingHorizontal: 10, paddingVertical: 4 },
  tabTxt: { fontSize: 15, fontWeight: "600", color: colors.textMuted },
  tabTxtOn: { color: colors.text, fontWeight: "800" },
  tabUnd: { marginTop: 4, height: 3, width: 22, borderRadius: 2, backgroundColor: BRAND_BLUE },
  tabUndPh: { marginTop: 4, height: 3, width: 22 },
  loginBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "rgba(34,211,238,0.10)",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  loginBannerTxt: { flex: 1, fontSize: 13, color: colors.text, marginRight: 8 },
  loginBannerBtn: { fontSize: 13, fontWeight: "800", color: BRAND_BLUE },
  listPad: { paddingHorizontal: 8, paddingTop: 10, paddingBottom: 24 },
  colWrap: { justifyContent: "space-between" },
  center: { paddingVertical: 48, alignItems: "center" },
  empty: { color: colors.textMuted, textAlign: "center", padding: 32, fontSize: 14 },
  footer: { paddingVertical: 16, alignItems: "center" },
  devFoot: {
    fontSize: 10,
    color: colors.textMuted,
    paddingHorizontal: 12,
    paddingBottom: 8,
    fontFamily: "monospace",
  },
  modalRow: { flex: 1, flexDirection: "row" },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)" },
  drawer: {
    width: "33%",
    minWidth: 108,
    maxWidth: 188,
    backgroundColor: BRAND_BLUE,
    paddingHorizontal: 9,
    paddingBottom: 16,
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: "rgba(255,255,255,0.18)",
  },
  drawerBrand: { fontSize: 18, fontWeight: "900", color: "#fff", marginBottom: 5 },
  drawerHi: { fontSize: 14, color: "rgba(255,255,255,0.78)", marginBottom: 14 },
  drawerLink: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "rgba(255,255,255,0.18)" },
  drawerLinkTxt: { fontSize: 15, fontWeight: "800", color: "rgba(255,255,255,0.94)" },
});
