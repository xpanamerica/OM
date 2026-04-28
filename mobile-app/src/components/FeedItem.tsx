import React, { memo, useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { Video, ResizeMode } from "expo-av";
import { colors } from "../theme/tokens";
import type { VideoListItem } from "../api/types";

type Props = {
  item: VideoListItem;
  isActive: boolean;
  /** 仅当详情接口返回可直连地址时自动播放（多数 VOD 为 play_auth，见 README） */
  directPlayUrl?: string | null;
  onPress: () => void;
};

/**
 * 单列 Feed 行：expo-image 懒解码；可见项可 expo-av 静音循环（有直连 URL 时）。
 */
function FeedItemInner({ item, isActive, directPlayUrl, onPress }: Props) {
  const opacity = useRef(new Animated.Value(0)).current;
  const videoRef = useRef<InstanceType<typeof Video> | null>(null);

  useEffect(() => {
    Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }).start();
  }, [opacity]);

  useEffect(() => {
    if (!directPlayUrl || !videoRef.current) return;
    if (isActive) void videoRef.current.playAsync();
    else void videoRef.current.pauseAsync();
  }, [isActive, directPlayUrl]);

  const showVideo = Boolean(directPlayUrl && isActive);

  return (
    <Animated.View style={{ opacity }}>
      <Pressable onPress={onPress} style={styles.card} accessibilityRole="button">
        <View style={styles.media}>
          {showVideo ? (
            <Video
              ref={(r) => {
                videoRef.current = r;
              }}
              style={StyleSheet.absoluteFill}
              source={{ uri: directPlayUrl! }}
              resizeMode={ResizeMode.COVER}
              isMuted
              shouldPlay={isActive}
              isLooping
              useNativeControls={false}
            />
          ) : item.cover_url ? (
            <Image
              source={{ uri: item.cover_url }}
              style={StyleSheet.absoluteFill}
              contentFit="cover"
              recyclingKey={item.id}
              transition={200}
              priority={isActive ? "high" : "normal"}
            />
          ) : (
            <View style={styles.ph} />
          )}
          <View style={styles.shade} />
          <View style={styles.body}>
            <View style={styles.pill}>
              <Text style={styles.pillTxt}>{showVideo ? "预览播放" : "封面"}</Text>
            </View>
            <Text style={styles.title} numberOfLines={3}>
              {item.title || "（无标题）"}
            </Text>
            <Text style={styles.meta}>
              {item.views_count ?? 0} 播放 · {item.likes_count ?? 0} 赞
              {item.duration_seconds != null ? ` · ${item.duration_seconds}s` : ""}
            </Text>
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

export const FeedItem = memo(FeedItemInner);

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 12,
    marginBottom: 14,
    borderRadius: 16,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  media: { aspectRatio: 9 / 15, backgroundColor: "#000" },
  ph: { ...StyleSheet.absoluteFillObject, backgroundColor: "#1e1e2e" },
  shade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "transparent",
    borderBottomWidth: 120,
    borderBottomColor: "rgba(0,0,0,0.55)",
  },
  body: { position: "absolute", left: 0, right: 0, bottom: 0, padding: 14 },
  pill: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(34,211,238,0.2)",
    marginBottom: 8,
  },
  pillTxt: { color: colors.accent, fontSize: 11, fontWeight: "800" },
  title: { color: "#fff", fontSize: 16, fontWeight: "800" },
  meta: { color: "rgba(255,255,255,0.85)", fontSize: 12, marginTop: 6, fontWeight: "600" },
});
