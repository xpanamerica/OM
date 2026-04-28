import React, { memo, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import { Image } from "expo-image";
import * as VideoThumbnails from "expo-video-thumbnails";
import { colors } from "../theme/tokens";
import * as categoriesApi from "../api/categories";
import * as videosApi from "../api/videos";
import type { CategoryPublic } from "../api/types";

type Props = {
  token: string;
  onCreated?: (id: string) => void;
};

/** 对接 ``POST /videos``；与 user-web 创建草稿一致 */
function CreatorPanelInner({ token, onCreated }: Props) {
  const [cats, setCats] = useState<CategoryPublic[]>([]);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [catId, setCatId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [videoFile, setVideoFile] = useState<{ uri: string; name: string; type?: string | null } | null>(null);
  const [coverFile, setCoverFile] = useState<{ uri: string; name: string; type?: string | null } | null>(null);
  const [coverPickerOpen, setCoverPickerOpen] = useState(false);
  const [thumbGenerating, setThumbGenerating] = useState(false);
  const [frameCandidates, setFrameCandidates] = useState<Array<{ uri: string; name: string; type: string; timeLabel: string }>>([]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const { items } = await categoriesApi.listCategories(token);
        if (!c) setCats(items);
      } catch (e) {
        if (!c) setErr(String(e));
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [token]);

  async function submit() {
    const t = title.trim();
    if (!t) {
      setErr("请填写标题");
      return;
    }
    if (!videoFile) {
      setErr("请选择视频文件");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      let v = await videosApi.createVideo(
        { title: t, description: desc.trim() || null, category_id: catId || null },
        token,
      );
      if (coverFile) {
        v = await videosApi.uploadVideoCover(v.id, coverFile, token);
      }
      v = await videosApi.uploadLocalVideoMedia(v.id, videoFile, token);
      try {
        v = await videosApi.submitVideoForReview(v.id, token);
        Alert.alert("视频发布成功", "即将进入预览页。");
      } catch (e) {
        Alert.alert("已保存", `上传成功，但自动提交审核失败：${e instanceof Error ? e.message : String(e)}`);
      }
      setTitle("");
      setDesc("");
      setCatId("");
      setVideoFile(null);
      setCoverFile(null);
      onCreated?.(v.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function pickVideo() {
    const result = await DocumentPicker.getDocumentAsync({
      type: "video/*",
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    setVideoFile({
      uri: asset.uri,
      name: asset.name || `video-${Date.now()}.mp4`,
      type: asset.mimeType || "video/mp4",
    });
    setCoverFile(null);
    setFrameCandidates([]);
  }

  async function pickCover() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("需要相册权限", "请允许访问相册后再选择封面。");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [16, 9],
      quality: 0.9,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    setCoverFile({
      uri: asset.uri,
      name: asset.fileName || `cover-${Date.now()}.jpg`,
      type: asset.mimeType || "image/jpeg",
    });
    setCoverPickerOpen(false);
  }

  async function generateCoverCandidates() {
    if (!videoFile) {
      Alert.alert("请先选择视频", "选择视频后才能从视频中生成封面。");
      return;
    }
    setThumbGenerating(true);
    try {
      const times = [500, 1500, 3000, 5000, 8000, 12000];
      const out: Array<{ uri: string; name: string; type: string; timeLabel: string }> = [];
      for (let i = 0; i < times.length; i += 1) {
        try {
          const r = await VideoThumbnails.getThumbnailAsync(videoFile.uri, { time: times[i], quality: 0.88 });
          out.push({ uri: r.uri, name: `cover-frame-${i + 1}.jpg`, type: "image/jpeg", timeLabel: `${Math.round(times[i] / 1000)}s` });
        } catch {
          // 短视频可能没有对应时间点，跳过即可。
        }
      }
      setFrameCandidates(out);
      if (!out.length) Alert.alert("生成失败", "请尝试选择上传封面，或换一段视频再试。");
    } finally {
      setThumbGenerating(false);
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.pad}>
      <Text style={styles.h}>创作中心</Text>
      <Text style={styles.sub}>选择视频与封面后发布；暂时不上传其他附件，成功后回到个人主页。</Text>
      <Text style={styles.label}>标题 *</Text>
      <TextInput value={title} onChangeText={setTitle} placeholder="标题" placeholderTextColor={colors.textMuted} style={styles.input} />
      <Text style={styles.label}>简介</Text>
      <TextInput
        value={desc}
        onChangeText={setDesc}
        placeholder="可选"
        placeholderTextColor={colors.textMuted}
        style={[styles.input, styles.area]}
        multiline
      />
      <Text style={styles.label}>分类</Text>
      <View style={styles.chips}>
        <Pressable onPress={() => setCatId("")} style={[styles.chip, !catId && styles.chipOn]}>
          <Text style={styles.chipTxt}>不选</Text>
        </Pressable>
        {cats.map((c) => (
          <Pressable key={c.id} onPress={() => setCatId(c.id)} style={[styles.chip, catId === c.id && styles.chipOn]}>
            <Text style={styles.chipTxt}>{c.name}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.mediaCard}>
        <Text style={styles.mediaTitle}>媒体文件</Text>
        <Text style={styles.mediaSub}>先选择视频；视频选好后可从预览帧中挑选封面，或上传图片。</Text>
        <View style={styles.mediaBtns}>
          <Pressable style={styles.mediaBtn} onPress={() => void pickVideo()}>
            <Text style={styles.mediaBtnTxt}>选择视频文件</Text>
          </Pressable>
          {videoFile ? (
            <Pressable style={styles.mediaBtn} onPress={() => setCoverPickerOpen(true)}>
              <Text style={styles.mediaBtnTxt}>设置封面</Text>
            </Pressable>
          ) : null}
        </View>
        {videoFile ? <Text style={styles.fileLine} numberOfLines={1}>视频：{videoFile.name}</Text> : null}
        {coverFile ? <Text style={styles.fileLine} numberOfLines={1}>封面：{coverFile.name}</Text> : null}
      </View>
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <Pressable onPress={submit} disabled={busy} style={[styles.btn, busy && styles.btnDis]}>
        <Text style={styles.btnTxt}>{busy ? "上传中…" : "上传并自动提交审核"}</Text>
      </Pressable>
      <Modal visible={coverPickerOpen} transparent animationType="slide" onRequestClose={() => setCoverPickerOpen(false)}>
        <View style={styles.sheetBackdrop}>
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <View style={styles.sheetTitleBox}>
                <Text style={styles.sheetTitle}>选择封面</Text>
                <Text style={styles.sheetSub}>从视频预览帧中选择，或上传自己的封面。</Text>
              </View>
              <Pressable style={styles.sheetClose} onPress={() => setCoverPickerOpen(false)}>
                <Text style={styles.sheetCloseTxt}>×</Text>
              </Pressable>
            </View>
            <View style={styles.mediaBtns}>
              <Pressable style={[styles.mediaBtn, styles.mediaBtnPrimary]} onPress={() => void generateCoverCandidates()} disabled={thumbGenerating}>
                <Text style={styles.mediaBtnPrimaryTxt}>{thumbGenerating ? "生成中…" : "从视频生成"}</Text>
              </Pressable>
              <Pressable style={styles.mediaBtn} onPress={() => void pickCover()}>
                <Text style={styles.mediaBtnTxt}>选择上传</Text>
              </Pressable>
            </View>
            {frameCandidates.length > 0 ? (
              <View style={styles.frameGrid}>
                {frameCandidates.map((item) => (
                  <Pressable
                    key={item.uri}
                    style={styles.frameCard}
                    onPress={() => {
                      setCoverFile(item);
                      setCoverPickerOpen(false);
                    }}
                  >
                    <Image source={{ uri: item.uri }} style={styles.frameImg} contentFit="cover" />
                    <Text style={styles.frameTime}>{item.timeLabel}</Text>
                  </Pressable>
                ))}
              </View>
            ) : (
              <Text style={styles.frameEmpty}>点击“从视频生成”后，会出现多张候选封面。</Text>
            )}
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

export const CreatorPanel = memo(CreatorPanelInner);

const styles = StyleSheet.create({
  pad: { padding: 16, paddingBottom: 32 },
  h: { color: colors.text, fontSize: 18, fontWeight: "800" },
  sub: { color: colors.textMuted, fontSize: 12, marginTop: 6, marginBottom: 14 },
  label: { color: colors.textMuted, fontSize: 12, fontWeight: "700", marginBottom: 6 },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    color: colors.text,
    fontSize: 16,
    marginBottom: 12,
    backgroundColor: colors.surface,
  },
  area: { minHeight: 100, textAlignVertical: "top" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipOn: { borderColor: colors.accent, backgroundColor: "rgba(34,211,238,0.12)" },
  chipTxt: { color: colors.text, fontSize: 12, fontWeight: "700" },
  mediaCard: {
    marginBottom: 12,
    padding: 14,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.accent,
  },
  mediaTitle: { color: colors.text, fontSize: 14, fontWeight: "900" },
  mediaSub: { color: colors.textMuted, fontSize: 12, marginTop: 4, marginBottom: 10 },
  mediaBtns: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  mediaBtn: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 9,
    backgroundColor: colors.bg,
  },
  mediaBtnTxt: { color: colors.accent, fontWeight: "900", fontSize: 12 },
  mediaBtnPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  mediaBtnPrimaryTxt: { color: "#042f2e", fontWeight: "900", fontSize: 12 },
  fileLine: { color: colors.text, fontSize: 12, marginTop: 8 },
  err: { color: colors.danger, marginBottom: 10 },
  btn: {
    backgroundColor: colors.accent,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 8,
  },
  btnDis: { opacity: 0.6 },
  btnTxt: { color: "#042f2e", fontWeight: "800", fontSize: 16 },
  center: { padding: 24, alignItems: "center" },
  sheetBackdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.62)" },
  sheet: { maxHeight: "78%", padding: 16, borderTopLeftRadius: 22, borderTopRightRadius: 22, backgroundColor: colors.surface, borderTopWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  sheetHead: { flexDirection: "row", justifyContent: "space-between", gap: 12, marginBottom: 14 },
  sheetTitleBox: { flex: 1 },
  sheetTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  sheetSub: { color: colors.textMuted, fontSize: 12, marginTop: 5 },
  sheetClose: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.08)" },
  sheetCloseTxt: { color: colors.text, fontSize: 24, fontWeight: "800" },
  frameGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 14 },
  frameCard: { width: "31%", overflow: "hidden", borderRadius: 12, backgroundColor: colors.bg, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  frameImg: { width: "100%", aspectRatio: 16 / 9, backgroundColor: colors.bg },
  frameTime: { position: "absolute", right: 5, bottom: 5, overflow: "hidden", borderRadius: 999, paddingHorizontal: 6, paddingVertical: 2, color: "#042f2e", backgroundColor: colors.accent, fontSize: 10, fontWeight: "900" },
  frameEmpty: { color: colors.textMuted, textAlign: "center", paddingVertical: 22, fontSize: 13 },
});
