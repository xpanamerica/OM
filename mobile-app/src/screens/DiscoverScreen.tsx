import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  type LayoutChangeEvent,
  Modal,
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { CompositeScreenProps } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { MainTabParamList, RootStackParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import { useAuth } from "../context/AuthContext";
import * as videosApi from "../api/videos";
import * as searchApi from "../api/search";
import * as learningPathsApi from "../api/learningPaths";
import * as algorithmApi from "../api/algorithm";
import type { VideoListItem } from "../api/types";
import { useRootStackNavigation } from "../navigation/useRootStackNavigation";

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, "Discover">,
  NativeStackScreenProps<RootStackParamList>
>;

export function DiscoverScreen(_props: Props) {
  const { token } = useAuth();
  const rootNav = useRootStackNavigation();
  const [kw, setKw] = useState("");
  const [modePanelOpen, setModePanelOpen] = useState(false);
  const [algorithmState, setAlgorithmState] = useState<algorithmApi.AlgorithmState | null>(null);
  const [customParams, setCustomParams] = useState<algorithmApi.AlgorithmParameters>({
    randomness: 50,
    diversity: 70,
    depth: 50,
    entertainment: 50,
    challenge: 50,
    novelty: 60,
  });
  /** 已提交的查询条件（避免 ``setState`` 与 ``refetch`` 竞态） */
  const [querySpec, setQuerySpec] = useState<{ keyword: string }>({
    keyword: "",
  });

  const modeOptions: Array<{ key: algorithmApi.AlgorithmMode; title: string; desc: string }> = [
    { key: "origin", title: "归源模式", desc: "完全随机、无画像、多样性最大" },
    { key: "efficiency", title: "效率模式", desc: "快速获取高密度、高价值内容" },
    { key: "growth", title: "成长模式", desc: "反舒适区，挑战认知边界" },
    { key: "emotion", title: "情绪模式", desc: "放松、娱乐、沉浸，但可控" },
    { key: "custom", title: "自定义模式", desc: "训练自己的世界模型" },
  ];

  const trending = useQuery({
    queryKey: ["discover-trending", token],
    queryFn: () => videosApi.listTrendingVideos({ offset: 0, limit: 10 }, token),
  });

  const paths = useQuery({
    queryKey: ["discover-paths", token],
    queryFn: () => learningPathsApi.listLearningPaths({ offset: 0, limit: 12 }, token),
  });

  const filtered = useQuery({
    queryKey: ["discover-videos", token, querySpec.keyword],
    queryFn: () =>
      querySpec.keyword.trim()
        ? searchApi.searchVideos(
            { keyword: querySpec.keyword.trim(), offset: 0, limit: 20, sort_by: "latest" },
            token,
          )
        : videosApi.listVideosPaged({ limit: 20, offset: 0 }, token),
    enabled: Boolean(querySpec.keyword.trim()),
  });

  const goVideo = useCallback(
    (id: string) => {
      rootNav?.navigate("Detail", { id });
    },
    [rootNav],
  );

  const runSearch = useCallback(() => {
    setQuerySpec({ keyword: kw });
  }, [kw]);

  const algorithmQuery = useQuery({
    queryKey: ["algorithm-state", token],
    queryFn: () => algorithmApi.getAlgorithmState(token!),
    enabled: Boolean(token),
  });
  const attentionQuery = useQuery({
    queryKey: ["attention-index", token],
    queryFn: () => algorithmApi.getAttentionIndex(token!),
    enabled: Boolean(token && modePanelOpen),
  });
  const aiAgentQuery = useQuery({
    queryKey: ["ai-agent-panel", token],
    queryFn: () => algorithmApi.getAiAgentPanel(token!),
    enabled: Boolean(token && modePanelOpen),
  });
  const governanceQuery = useQuery({
    queryKey: ["governance-power", token],
    queryFn: () => algorithmApi.getGovernancePower(token!),
    enabled: Boolean(token && modePanelOpen),
  });

  React.useEffect(() => {
    if (algorithmQuery.data?.data) setAlgorithmState(algorithmQuery.data.data);
  }, [algorithmQuery.data]);

  async function chooseMode(mode: algorithmApi.AlgorithmMode) {
    if (!token) return;
    const result = await algorithmApi.updateAlgorithmState(token, {
      mode,
      parameters: mode === "custom" ? customParams : undefined,
    });
    setAlgorithmState(result.data);
    setModePanelOpen(false);
  }

  const activeModeTitle = modeOptions.find((item) => item.key === algorithmState?.mode)?.title ?? "算法模式";

  const renderVideoRow = useCallback(
    ({ item }: { item: VideoListItem }) => (
      <Pressable style={styles.vRow} onPress={() => goVideo(item.id)}>
        <Text style={styles.vTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.vMeta}>{item.views_count} 次播放</Text>
      </Pressable>
    ),
    [goVideo],
  );

  const listData = filtered.data?.items ?? [];
  const listLoading =
    filtered.isFetching &&
    Boolean(querySpec.keyword.trim());

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.pad} keyboardShouldPersistTaps="handled">
      <View style={styles.discoverHero}>
        <View pointerEvents="none" style={styles.heroOrb} />
        <View style={styles.heroHead}>
          <Text style={styles.heroTitle}>发现</Text>
          <Pressable style={styles.heroMode} onPress={() => setModePanelOpen(true)}>
            <Text style={styles.heroModeLabel}>算法模式</Text>
            <Text style={styles.heroModeText}>{activeModeTitle}</Text>
          </Pressable>
        </View>
        <View style={styles.searchRow}>
          <TextInput
            value={kw}
            onChangeText={setKw}
            placeholder="关键词"
            placeholderTextColor="#8b94a7"
            style={styles.input}
            onSubmitEditing={runSearch}
          />
          <Pressable onPress={runSearch} style={styles.searchBtn}>
            <Text style={styles.searchBtnTxt}>搜索</Text>
          </Pressable>
        </View>
      </View>

      <Text style={styles.h}>趋势</Text>
      {trending.isLoading ? (
        <ActivityIndicator color={colors.accent} style={{ marginVertical: 12 }} />
      ) : (
        <View style={styles.card}>
          {(trending.data?.items ?? []).slice(0, 6).map((v) => (
            <Pressable key={v.id} style={styles.vRow} onPress={() => goVideo(v.id)}>
              <Text style={styles.vTitle} numberOfLines={2}>
                {v.title}
              </Text>
              <Text style={styles.vMeta}>{v.views_count} 次播放</Text>
            </Pressable>
          ))}
          {!trending.data?.items?.length ? <Text style={styles.muted}>暂无趋势稿件</Text> : null}
        </View>
      )}

      {querySpec.keyword.trim() && (
        <>
          <Text style={styles.h}>筛选结果</Text>
          {listLoading ? (
            <ActivityIndicator color={colors.accent} style={{ marginVertical: 16 }} />
          ) : (
            <FlatList
              data={listData}
              keyExtractor={(it) => it.id}
              renderItem={renderVideoRow}
              scrollEnabled={false}
              ListEmptyComponent={<Text style={styles.muted}>无结果</Text>}
            />
          )}
        </>
      )}

      <Modal visible={modePanelOpen} transparent animationType="slide" onRequestClose={() => setModePanelOpen(false)}>
        <View style={styles.modeRoot}>
          <Pressable style={styles.modeBackdrop} onPress={() => setModePanelOpen(false)} />
          <View style={styles.modeSheet}>
            <View style={styles.modeHead}>
              <View>
                <Text style={styles.modeKicker}>透明算法控制面板</Text>
                <Text style={styles.modeTitle}>选择你的世界模型</Text>
              </View>
              <Pressable style={styles.modeClose} onPress={() => setModePanelOpen(false)}>
                <Text style={styles.modeCloseTxt}>×</Text>
              </Pressable>
            </View>
            {modeOptions.map((item) => (
              <Pressable key={item.key} style={[styles.modeCard, algorithmState?.mode === item.key && styles.modeCardOn]} onPress={() => void chooseMode(item.key)}>
                <Text style={styles.modeCardTitle}>{item.title}</Text>
                <Text style={styles.modeCardDesc}>{item.desc}</Text>
              </Pressable>
            ))}
            <View style={styles.insightStrip}>
              <View style={styles.insightBox}>
                <Text style={styles.insightNum}>{attentionQuery.data?.data.attentionIndex ?? "—"}</Text>
                <Text style={styles.insightLabel}>Attention Index</Text>
              </View>
              <View style={styles.insightBox}>
                <Text style={styles.insightNum}>{governanceQuery.data?.votingPower ?? "—"}</Text>
                <Text style={styles.insightLabel}>治理投票权重</Text>
              </View>
              <Text style={styles.agentText}>
                {aiAgentQuery.data?.summary ?? "AI Agent 将生成总结、注意力优化和学习路径建议。"}
              </Text>
            </View>
            <Text style={styles.modeCustomTitle}>自定义参数</Text>
            {([
              ["randomness", "随机性"],
              ["diversity", "多样性"],
              ["depth", "深度"],
              ["entertainment", "娱乐性"],
              ["challenge", "认知挑战"],
              ["novelty", "新颖性"],
            ] as const).map(([key, label]) => (
              <DragParam
                key={key}
                label={label}
                value={customParams[key]}
                onChange={(value) => setCustomParams((p) => ({ ...p, [key]: value }))}
              />
            ))}
            <Pressable style={styles.customApply} onPress={() => void chooseMode("custom")}>
              <Text style={styles.customApplyText}>应用自定义模式</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Text style={styles.h}>学习路径</Text>
      {paths.isLoading ? (
        <ActivityIndicator color={colors.accent} style={{ marginVertical: 12 }} />
      ) : (
        <View style={styles.card}>
          {(paths.data?.items ?? []).map((p) => (
            <View key={p.id} style={styles.pathRow}>
              <Text style={styles.pathTitle}>{p.title}</Text>
              {p.description ? (
                <Text style={styles.muted} numberOfLines={2}>
                  {p.description}
                </Text>
              ) : null}
            </View>
          ))}
          {!paths.data?.items?.length ? <Text style={styles.muted}>暂无路径</Text> : null}
        </View>
      )}
    </ScrollView>
  );
}

function DragParam({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  const [width, setWidth] = useState(1);
  const clamp = useCallback((next: number) => Math.max(0, Math.min(100, Math.round(next))), []);
  const updateFromX = useCallback(
    (x: number) => {
      onChange(clamp((x / Math.max(width, 1)) * 100));
    },
    [clamp, onChange, width],
  );
  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (evt) => updateFromX(evt.nativeEvent.locationX),
        onPanResponderMove: (evt) => updateFromX(evt.nativeEvent.locationX),
      }),
    [updateFromX],
  );
  const onLayout = useCallback((event: LayoutChangeEvent) => setWidth(Math.max(1, event.nativeEvent.layout.width)), []);
  return (
    <View style={styles.paramRow}>
      <View style={styles.paramTop}>
        <Text style={styles.paramText}>{label}</Text>
        <Text style={styles.paramValue}>{value}</Text>
      </View>
      <View style={styles.sliderTrack} onLayout={onLayout} {...responder.panHandlers}>
        <View style={[styles.sliderFill, { width: `${value}%` }]} />
        <View style={[styles.sliderKnob, { left: `${value}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 14, paddingBottom: 32 },
  discoverHero: {
    position: "relative",
    overflow: "hidden",
    marginBottom: 12,
    padding: 16,
    borderRadius: 26,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.18)",
    backgroundColor: "rgba(15,23,42,0.9)",
  },
  heroOrb: {
    position: "absolute",
    right: -82,
    top: -58,
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: "rgba(34,211,238,0.14)",
    borderWidth: 1,
    borderColor: "rgba(103,232,249,0.18)",
  },
  heroHead: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 12,
  },
  heroTitle: {
    color: colors.text,
    fontSize: 38,
    lineHeight: 42,
    fontWeight: "900",
    letterSpacing: -2,
  },
  heroMode: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.24)",
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: "rgba(2,6,23,0.62)",
  },
  heroModeLabel: {
    color: colors.accent,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1,
  },
  heroModeText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "900",
    marginTop: 2,
  },
  h: { color: colors.text, fontSize: 17, fontWeight: "800", marginTop: 8, marginBottom: 10 },
  searchRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(148,163,184,0.24)",
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 13,
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
    backgroundColor: "rgba(2,6,23,0.72)",
  },
  searchBtn: {
    backgroundColor: colors.accent,
    minWidth: 86,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 18,
  },
  searchBtnTxt: { color: "#042f2e", fontWeight: "900", fontSize: 17 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: 10,
    marginBottom: 8,
  },
  vRow: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  vTitle: { color: colors.accent, fontWeight: "700", fontSize: 15 },
  vMeta: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  muted: { color: colors.textMuted, fontSize: 13, marginVertical: 8 },
  pathRow: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pathTitle: { color: colors.text, fontWeight: "800", fontSize: 15 },
  modeRoot: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(2,6,23,0.68)" },
  modeBackdrop: { ...StyleSheet.absoluteFillObject },
  modeSheet: {
    maxHeight: "86%",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 18,
    backgroundColor: "#101827",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(103,232,249,0.2)",
  },
  modeHead: { flexDirection: "row", justifyContent: "space-between", gap: 12, marginBottom: 12 },
  modeKicker: { color: colors.accent, fontSize: 12, fontWeight: "900" },
  modeTitle: { color: colors.text, fontSize: 21, fontWeight: "900", marginTop: 4 },
  modeClose: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.08)" },
  modeCloseTxt: { color: colors.text, fontSize: 24 },
  modeCard: { padding: 12, borderRadius: 18, borderWidth: StyleSheet.hairlineWidth, borderColor: "rgba(148,163,184,0.16)", backgroundColor: "rgba(15,23,42,0.72)", marginBottom: 10 },
  modeCardOn: { borderColor: "rgba(103,232,249,0.68)", backgroundColor: "rgba(8,47,73,0.62)" },
  modeCardTitle: { color: colors.text, fontSize: 15, fontWeight: "900" },
  modeCardDesc: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  insightStrip: {
    marginVertical: 10,
    padding: 10,
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(125,211,252,0.24)",
    backgroundColor: "rgba(15,23,42,0.6)",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  insightBox: { flex: 1, minWidth: 120 },
  insightNum: { color: "#e0f2fe", fontSize: 18, fontWeight: "900" },
  insightLabel: { color: "#93c5fd", fontSize: 11, fontWeight: "800", marginTop: 2 },
  agentText: { width: "100%", color: "#93c5fd", fontSize: 11, lineHeight: 16, fontWeight: "700" },
  modeCustomTitle: { color: colors.text, fontSize: 15, fontWeight: "900", marginTop: 6, marginBottom: 8 },
  paramRow: { paddingVertical: 8 },
  paramTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  paramText: { color: "#cbd5e1", fontSize: 12, fontWeight: "800" },
  paramValue: { color: colors.accent, fontSize: 12, fontWeight: "900" },
  sliderTrack: {
    height: 18,
    justifyContent: "center",
    borderRadius: 999,
    backgroundColor: "rgba(148, 163, 184, 0.16)",
  },
  sliderFill: {
    height: 5,
    borderRadius: 999,
    backgroundColor: colors.accent,
  },
  sliderKnob: {
    position: "absolute",
    top: 3,
    width: 12,
    height: 12,
    marginLeft: -6,
    borderRadius: 999,
    backgroundColor: "#e0f2fe",
    borderWidth: 2,
    borderColor: colors.accent,
  },
  customApply: { marginTop: 8, minHeight: 42, borderRadius: 999, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent },
  customApplyText: { color: "#042f2e", fontSize: 14, fontWeight: "900" },
});
