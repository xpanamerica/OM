import React, { memo } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme/tokens";
import type { VideoListItem } from "../api/types";
import { ContentCard } from "./ContentCard";

type Props = {
  title?: string;
  items: VideoListItem[];
  onSelect: (id: string) => void;
  loading?: boolean;
};

/** 横向趋势 / 推荐带：数据源由父组件用 ``/videos/trending`` 等注入 */
function AIRecommendationSectionInner({ title = "为你推荐", items, onSelect, loading }: Props) {
  return (
    <View style={styles.block}>
      <View style={styles.head}>
        <Text style={styles.h}>{title}</Text>
        {loading ? <Text style={styles.sub}>加载中…</Text> : <Text style={styles.sub}>热度与偏好（本地键同步站点）</Text>}
      </View>
      <FlatList
        horizontal
        data={items}
        keyExtractor={(x) => x.id}
        renderItem={({ item }) => (
          <View style={styles.cardSlot}>
            <ContentCard compact item={item} onPress={() => onSelect(item.id)} />
          </View>
        )}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.list}
        windowSize={3}
        maxToRenderPerBatch={4}
        initialNumToRender={4}
        removeClippedSubviews
      />
    </View>
  );
}

export const AIRecommendationSection = memo(AIRecommendationSectionInner);

const styles = StyleSheet.create({
  block: { marginBottom: 18 },
  head: { paddingHorizontal: 16, marginBottom: 10 },
  h: { color: colors.text, fontSize: 17, fontWeight: "800" },
  sub: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  list: { paddingHorizontal: 12 },
  cardSlot: { marginRight: 10 },
});
