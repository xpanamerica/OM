import React, { memo, useRef } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { colors } from "../theme/tokens";
import type { VideoListItem } from "../api/types";

type Props = {
  item: VideoListItem;
  onPress?: () => void;
  compact?: boolean;
};

/** 高密度内容卡片（发现区 / 推荐横滑）；缩放动画走 native driver（60fps） */
function ContentCardInner({ item, onPress, compact }: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  const pressIn = () => {
    Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, friction: 6, tension: 400 }).start();
  };
  const pressOut = () => {
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, friction: 6, tension: 400 }).start();
  };

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        accessibilityRole="button"
        onPressIn={pressIn}
        onPressOut={pressOut}
        onPress={onPress}
        style={[styles.wrap, compact && styles.wrapCompact]}
      >
        <View style={[styles.thumb, compact && styles.thumbCompact]}>
          {item.cover_url ? (
            <Image source={{ uri: item.cover_url }} style={StyleSheet.absoluteFill} contentFit="cover" transition={120} />
          ) : (
            <View style={styles.ph} />
          )}
        </View>
        <Text style={styles.title} numberOfLines={compact ? 2 : 3}>
          {item.title || "（无标题）"}
        </Text>
        <Text style={styles.meta}>
          {item.views_count ?? 0} 播放 · {item.likes_count ?? 0} 赞
        </Text>
      </Pressable>
    </Animated.View>
  );
}

export const ContentCard = memo(ContentCardInner);

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    overflow: "hidden",
    paddingBottom: 10,
  },
  wrapCompact: { width: 148, marginRight: 10 },
  thumb: { aspectRatio: 16 / 9, backgroundColor: "#1a1a24" },
  thumbCompact: { aspectRatio: 9 / 14 },
  ph: { flex: 1, backgroundColor: "#27272a" },
  title: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    marginTop: 8,
    paddingHorizontal: 10,
  },
  meta: { color: colors.textMuted, fontSize: 11, marginTop: 4, paddingHorizontal: 10 },
});
