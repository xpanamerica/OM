import React, { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import type { VideoListItem } from "../api/types";
import { colors } from "../theme/tokens";

type Props = {
  item: VideoListItem;
  onPress: () => void;
  onAuthorPress?: () => void;
};

function shortAuthorLabel(authorId: string): string {
  const s = authorId.replace(/-/g, "");
  return s.length >= 6 ? `用户${s.slice(0, 6)}` : "创作者";
}

function authorLabel(item: VideoListItem): string {
  return item.author_username?.trim() || shortAuthorLabel(item.author_id);
}

function XhsFeedCardInner({ item, onPress, onAuthorPress }: Props) {
  const title = (item.title || "（无标题）").trim();
  return (
    <Pressable onPress={onPress} style={styles.card} accessibilityRole="button">
      <View style={styles.thumbWrap}>
        {item.cover_url ? (
          <Image
            source={{ uri: item.cover_url }}
            style={StyleSheet.absoluteFill}
            contentFit="cover"
            recyclingKey={item.id}
            transition={160}
          />
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.thumbPh]} />
        )}
      </View>
      <View style={styles.body}>
        <Text style={styles.title} numberOfLines={2}>
          {title}
        </Text>
        <View style={styles.row}>
          <View style={styles.metrics}>
            <View style={styles.metric}>
              <Ionicons name="heart-outline" size={16} color={colors.textMuted} />
              <Text style={styles.likeTxt}>{item.likes_count ?? 0}</Text>
            </View>
            <View style={styles.metric}>
              <Ionicons name="bookmark-outline" size={16} color={colors.textMuted} />
              <Text style={styles.likeTxt}>{item.favorites_count ?? 0}</Text>
            </View>
            <View style={styles.metric}>
              <Ionicons name="chatbubble-outline" size={16} color={colors.textMuted} />
              <Text style={styles.likeTxt}>{item.comments_count ?? 0}</Text>
            </View>
          </View>
        </View>
        <Pressable onPress={onAuthorPress} style={styles.publine}>
          <Text style={styles.publineLabel}>作者：</Text>
          <Text style={styles.publineAuthor} numberOfLines={1} ellipsizeMode="tail">
            {authorLabel(item)}
          </Text>
        </Pressable>
        {item.recommendation_text ? (
          <Text style={styles.reason} numberOfLines={2}>
            {item.recommendation_text}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

export const XhsFeedCard = memo(XhsFeedCardInner);

const styles = StyleSheet.create({
  card: {
    flex: 1,
    marginHorizontal: 4,
    marginBottom: 10,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  thumbWrap: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: "#1a1a22",
  },
  thumbPh: { backgroundColor: "#252530" },
  body: { paddingHorizontal: 8, paddingTop: 8, paddingBottom: 10 },
  title: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 18,
    minHeight: 36,
  },
  row: {
    marginTop: 9,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-start",
  },
  metrics: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 4 },
  metric: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 3 },
  likeTxt: { fontSize: 13, color: colors.textMuted, fontWeight: "800" },
  publine: { marginTop: 6, flexDirection: "row", alignItems: "center", minWidth: 0, maxWidth: "100%" },
  publineLabel: { flexShrink: 0, fontSize: 11, color: colors.textMuted, fontWeight: "700" },
  publineAuthor: { flex: 1, minWidth: 0, fontSize: 11, color: colors.accent, fontWeight: "800" },
  reason: {
    marginTop: 7,
    paddingHorizontal: 7,
    paddingVertical: 5,
    borderRadius: 9,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(125, 211, 252, 0.28)",
    backgroundColor: "rgba(14, 165, 233, 0.08)",
    color: "#93c5fd",
    fontSize: 10,
    lineHeight: 14,
    fontWeight: "800",
  },
});
