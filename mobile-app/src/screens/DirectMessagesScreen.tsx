import React, { useCallback, useEffect, useState } from "react";
import { Alert, FlatList, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { colors } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";
import { useAuth } from "../context/AuthContext";
import * as socialApi from "../api/social";
import { getApiBaseUrl } from "../config/env";
import { RootBottomNav } from "../components/RootBottomNav";

type Props = NativeStackScreenProps<RootStackParamList, "DirectMessages">;
type RichMessageBody = {
  __om_dm_v1?: true;
  text?: string;
  attachments?: socialApi.DirectMessageAttachment[];
};

const EMOJIS = ["😀", "😄", "😂", "😍", "👍", "👏", "🙏", "🔥", "✨", "🎉", "❤️", "😭", "😅", "🤔", "💪", "👌"];

function parseMessageBody(raw: string): RichMessageBody {
  try {
    const data = JSON.parse(raw) as RichMessageBody;
    if (data?.__om_dm_v1) return data;
  } catch {
    /* old plain text message */
  }
  return { text: raw, attachments: [] };
}

function messagePreview(raw: string | null | undefined): string {
  if (!raw) return "暂无消息";
  const body = parseMessageBody(raw);
  const text = body.text?.trim();
  if (text) return text;
  const first = body.attachments?.[0];
  if (first?.content_type?.startsWith("image/")) return "[图片]";
  if (first) return "[附件]";
  return "新消息";
}

function isImageAttachment(a: socialApi.DirectMessageAttachment): boolean {
  return Boolean(a.content_type?.startsWith("image/"));
}

function attachmentUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  const api = getApiBaseUrl().replace(/\/$/, "");
  if (url.startsWith("/api/v1/")) return `${api.replace(/\/api\/v1$/, "")}${url}`;
  return `${api}${url.startsWith("/") ? url : `/${url}`}`;
}

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

export function DirectMessagesScreen({ navigation, route }: Props) {
  const { token, me } = useAuth();
  const [convs, setConvs] = useState<socialApi.DirectConversation[]>([]);
  const [friends, setFriends] = useState<socialApi.FollowUser[]>([]);
  const [msgs, setMsgs] = useState<socialApi.DirectMessage[]>([]);
  const [text, setText] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [pending, setPending] = useState<socialApi.DirectMessageAttachment[]>([]);
  const [sending, setSending] = useState(false);
  const peerId = route.params?.peerId ?? "";

  const load = useCallback(async () => {
    if (!token) return navigation.navigate("Login");
    const [cs, fs] = await Promise.all([
      socialApi.listConversations(token),
      socialApi.listMyFriends(token).catch(() => []),
    ]);
    setConvs(cs);
    setFriends(fs);
    if (peerId) setMsgs(await socialApi.listMessages(peerId, token));
  }, [navigation, peerId, token]);

  useEffect(() => {
    void load().catch(() => {});
  }, [load]);

  async function send() {
    const body = text.trim();
    if (!token || !peerId || (!body && pending.length === 0)) return;
    setSending(true);
    try {
      await socialApi.sendMessage(peerId, JSON.stringify({ __om_dm_v1: true, text: body, attachments: pending }), token);
      setText("");
      setPending([]);
      setEmojiOpen(false);
      await load();
    } finally {
      setSending(false);
    }
  }

  async function uploadPicked(file: { uri: string; name: string; type?: string | null }) {
    if (!token || !peerId) return;
    try {
      const uploaded = await socialApi.uploadMessageAttachment(peerId, file, token);
      setPending((prev) => prev.concat(uploaded));
    } catch (e) {
      Alert.alert("上传失败", e instanceof Error ? e.message : String(e));
    }
  }

  async function pickImage() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("需要相册权限", "请允许访问相册后再上传图片。");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    await uploadPicked({
      uri: asset.uri,
      name: asset.fileName || `image-${Date.now()}.jpg`,
      type: asset.mimeType || "image/jpeg",
    });
  }

  async function pickDocument() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ["text/*", "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "image/*"],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    await uploadPicked({
      uri: asset.uri,
      name: asset.name || `file-${Date.now()}`,
      type: asset.mimeType || "application/octet-stream",
    });
  }

  const convPeerIds = new Set(convs.map((it) => it.peer.id));
  const peerRows = [
    ...convs.map((it) => ({
      id: it.peer.id,
      username: it.peer.username,
      avatarUrl: it.peer.avatar_url,
      unread: it.unread_count,
      preview: it.last_message_preview || messagePreview(it.last_message?.body),
      date: it.updated_at || it.last_message?.created_at || "",
      kind: "conversation" as const,
    })),
    ...friends
      .filter((it) => !convPeerIds.has(it.id))
      .map((it) => ({ id: it.id, username: it.username, avatarUrl: it.avatar_url, unread: 0, preview: "我们已互相关注，开始聊天吧", date: it.followed_at, kind: "friend" as const })),
  ];
  const activePeer = peerRows.find((it) => it.id === peerId);

  if (!peerId) {
    return (
      <View style={styles.root}>
        <View style={styles.listTopbar}>
          <Pressable style={styles.backIcon} onPress={() => navigation.goBack()}>
            <Ionicons name="chevron-back" size={22} color={colors.text} />
          </Pressable>
          <Text style={styles.listTitle}>消息列表</Text>
          <Pressable style={styles.topAction} onPress={() => void load()}>
            <Ionicons name="refresh" size={18} color={colors.accent} />
          </Pressable>
        </View>
        <FlatList
          data={peerRows}
          keyExtractor={(it) => `${it.kind}-${it.id}`}
          contentContainerStyle={styles.listPad}
          renderItem={({ item }) => (
            <Pressable style={styles.convRow} onPress={() => navigation.setParams({ peerId: item.id })}>
              <View style={styles.avatar}>
                {item.avatarUrl ? <Image source={{ uri: attachmentUrl(item.avatarUrl) }} style={styles.avatarImg} /> : <Text style={styles.avatarTxt}>{item.username.slice(0, 1).toUpperCase()}</Text>}
              </View>
              <View style={styles.convMain}>
                <Text style={styles.convName} numberOfLines={1}>{item.username}</Text>
                <Text style={styles.convPreview} numberOfLines={1}>{item.preview}</Text>
              </View>
              <View style={styles.convSide}>
                <Text style={styles.meta}>{item.date ? new Date(item.date).toLocaleDateString([], { month: "2-digit", day: "2-digit" }) : ""}</Text>
                {item.unread > 0 ? <Text style={styles.badge}>{item.unread}</Text> : null}
              </View>
            </Pressable>
          )}
          ListEmptyComponent={<Text style={styles.empty}>暂无会话，互相关注后的好友会出现在这里。</Text>}
          ListFooterComponent={<View style={styles.listFooter}><Text style={styles.footerTitle}>推荐入口</Text><Text style={styles.footerText}>浏览创作者主页后，可关注或添加好友并开始对话。</Text></View>}
        />
        <RootBottomNav active="Messages" />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.chatTopbar}>
        <Pressable style={styles.backIcon} onPress={() => navigation.setParams({ peerId: undefined })}>
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </Pressable>
        <View style={styles.chatAvatar}>
          {activePeer?.avatarUrl ? <Image source={{ uri: attachmentUrl(activePeer.avatarUrl) }} style={styles.avatarImg} /> : <Text style={styles.avatarTxt}>{activePeer?.username?.slice(0, 1).toUpperCase() || "聊"}</Text>}
        </View>
        <View style={styles.chatTitleBox}>
          <Text style={styles.chatTitle} numberOfLines={1}>{activePeer?.username || "新的对话"}</Text>
          <Text style={styles.chatSub}>互相关注后可持续对话</Text>
        </View>
        <Ionicons name="ellipsis-horizontal" size={22} color={colors.textMuted} />
      </View>
      <FlatList
        data={msgs}
        keyExtractor={(it) => it.id}
        contentContainerStyle={styles.msgPad}
        ListHeaderComponent={
          <View style={styles.greetPanel}>
            <Text style={styles.greetTitle}>打个招呼</Text>
            <View style={styles.greetRow}>
              {["你好", "开始聊聊", "😊", "👏"].map((item) => (
                <Pressable key={item} style={styles.greetBtn} onPress={() => setText((v) => (item.length > 2 ? item : `${v}${item}`))}>
                  <Text style={styles.greetTxt}>{item}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        }
        renderItem={({ item }) => {
          const mine = item.sender_id === me?.id;
          const body = parseMessageBody(item.body);
          return (
            <View style={[styles.msg, mine && styles.mine]}>
              <View style={[styles.msgBubble, mine && styles.mineBubble]}>
                {body.text ? <Text style={[styles.msgText, mine && styles.mineText]}>{body.text}</Text> : null}
                {body.attachments?.map((a) =>
                  isImageAttachment(a) ? (
                    <Image
                      key={a.id}
                      source={{ uri: attachmentUrl(a.url), headers: token ? { Authorization: `Bearer ${token}` } : undefined }}
                      style={styles.msgImage}
                    />
                  ) : (
                    <Text key={a.id} style={[styles.fileCard, mine && styles.mineFileCard]}>
                      附件 {a.original_filename} · {fileSize(a.size_bytes)}
                    </Text>
                  ),
                )}
              </View>
              <Text style={[styles.meta, mine && styles.mineMeta]}>{new Date(item.created_at).toLocaleString([], { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</Text>
            </View>
          );
        }}
        ListEmptyComponent={<Text style={styles.empty}>还没有消息，先发一句问候吧。</Text>}
      />
      <View style={styles.composer}>
          {pending.length ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.pendingRow}>
              {pending.map((a) => (
                <Pressable key={a.id} style={styles.pendingChip} onPress={() => setPending((prev) => prev.filter((x) => x.id !== a.id))}>
                  <Text style={styles.pendingTxt} numberOfLines={1}>
                    {isImageAttachment(a) ? "图片" : "附件"} · {a.original_filename} ×
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          ) : null}
          {emojiOpen ? (
            <View style={styles.emojiPanel}>
              {EMOJIS.map((emoji) => (
                <Pressable key={emoji} style={styles.emojiBtn} onPress={() => setText((v) => `${v}${emoji}`)}>
                  <Text style={styles.emojiTxt}>{emoji}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
          <View style={styles.composerRow}>
            <Pressable style={styles.toolBtn} onPress={() => setEmojiOpen((v) => !v)}>
              <Text style={styles.toolTxt}>☺</Text>
            </Pressable>
            <Pressable style={styles.toolBtn} onPress={() => void pickImage()}>
              <Text style={styles.toolTxt}>图</Text>
            </Pressable>
            <Pressable style={styles.toolBtn} onPress={() => void pickDocument()}>
              <Text style={styles.toolTxt}>＋</Text>
            </Pressable>
            <TextInput value={text} onChangeText={setText} style={styles.input} placeholder="发消息..." placeholderTextColor={colors.textMuted} />
            <Pressable style={[styles.send, sending && styles.sendOff]} onPress={() => void send()} disabled={sending}>
              <Text style={styles.sendTxt}>发送</Text>
            </Pressable>
          </View>
        </View>
      <RootBottomNav active="Messages" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  listTopbar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingTop: 6, paddingBottom: 10 },
  backIcon: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.07)" },
  listTitle: { color: colors.text, fontSize: 17, fontWeight: "900" },
  topAction: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(34,211,238,0.12)" },
  listPad: { paddingHorizontal: 18, paddingBottom: 92 },
  convRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 11, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "rgba(255,255,255,0.08)" },
  avatar: { width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent, overflow: "hidden" },
  chatAvatar: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent, overflow: "hidden" },
  avatarImg: { width: "100%", height: "100%" },
  avatarTxt: { color: "#fff", fontWeight: "900", fontSize: 16 },
  convMain: { flex: 1, minWidth: 0 },
  convName: { color: colors.text, fontWeight: "900", fontSize: 16 },
  convPreview: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  convSide: { alignItems: "flex-end", minWidth: 54, gap: 7 },
  badge: { color: "#042f2e", backgroundColor: colors.accent, borderRadius: 999, overflow: "hidden", paddingHorizontal: 7, fontSize: 11, fontWeight: "900" },
  listFooter: { marginTop: 18, padding: 14, borderRadius: 18, backgroundColor: "rgba(255,255,255,0.06)", borderWidth: StyleSheet.hairlineWidth, borderColor: "rgba(255,255,255,0.1)" },
  footerTitle: { color: colors.text, fontWeight: "900", fontSize: 14 },
  footerText: { color: colors.textMuted, marginTop: 6, lineHeight: 18 },
  chatTopbar: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 14, paddingTop: 6, paddingBottom: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "rgba(255,255,255,0.08)" },
  chatTitleBox: { flex: 1, minWidth: 0 },
  chatTitle: { color: colors.text, fontSize: 16, fontWeight: "900" },
  chatSub: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  msgPad: { padding: 12, paddingBottom: 20 },
  greetPanel: { marginBottom: 18, padding: 12, borderRadius: 18, backgroundColor: "rgba(255,255,255,0.07)", borderWidth: StyleSheet.hairlineWidth, borderColor: "rgba(255,255,255,0.09)" },
  greetTitle: { color: colors.textMuted, fontSize: 12, fontWeight: "800", textAlign: "center", marginBottom: 10 },
  greetRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center" },
  greetBtn: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 14, backgroundColor: "rgba(34,211,238,0.12)" },
  greetTxt: { color: colors.accent, fontWeight: "900" },
  msg: { maxWidth: "82%", marginBottom: 10 },
  mine: { alignSelf: "flex-end" },
  msgBubble: { backgroundColor: colors.surface, borderRadius: 16, padding: 10, overflow: "hidden" },
  mineBubble: { backgroundColor: colors.accent },
  msgText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  mineText: { color: "#042f2e", fontWeight: "700" },
  msgImage: { width: 210, height: 210, borderRadius: 12, marginTop: 6, backgroundColor: colors.bg },
  fileCard: { color: colors.text, backgroundColor: "rgba(255,255,255,0.08)", borderRadius: 10, padding: 8, marginTop: 6 },
  mineFileCard: { color: "#042f2e", backgroundColor: "rgba(255,255,255,0.34)" },
  meta: { color: colors.textMuted, fontSize: 10, marginTop: 4 },
  mineMeta: { textAlign: "right" },
  empty: { color: colors.textMuted, padding: 16, textAlign: "center" },
  composer: { padding: 8, paddingBottom: 82, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(2,6,23,0.92)" },
  composerRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  toolBtn: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  toolTxt: { color: colors.accent, fontSize: 16, fontWeight: "900" },
  input: { flex: 1, minWidth: 0, backgroundColor: colors.surface, borderRadius: 999, paddingHorizontal: 14, color: colors.text },
  send: { minWidth: 58, minHeight: 34, backgroundColor: colors.accent, borderRadius: 999, paddingHorizontal: 12, alignItems: "center", justifyContent: "center" },
  sendOff: { opacity: 0.5 },
  sendTxt: { color: "#042f2e", fontWeight: "900" },
  emojiPanel: { flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 10, marginBottom: 8, borderRadius: 16, backgroundColor: colors.surface },
  emojiBtn: { width: 34, height: 34, alignItems: "center", justifyContent: "center", borderRadius: 10, backgroundColor: colors.bg },
  emojiTxt: { fontSize: 20 },
  pendingRow: { gap: 8, paddingBottom: 8 },
  pendingChip: { maxWidth: 180, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, backgroundColor: colors.surface },
  pendingTxt: { color: colors.accent, fontSize: 12, fontWeight: "800" },
});
