import React, { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import type { CompositeScreenProps } from "@react-navigation/native";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { MainTabParamList, RootStackParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import { CreatorPanel } from "../components/CreatorPanel";
import { useAuth } from "../context/AuthContext";
import { useRootStackNavigation } from "../navigation/useRootStackNavigation";

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, "Create">,
  NativeStackScreenProps<RootStackParamList>
>;

export function CreateScreen(_props: Props) {
  const { token } = useAuth();
  const rootNav = useRootStackNavigation();

  useEffect(() => {
    if (!token) rootNav?.navigate("Login");
  }, [token, rootNav]);

  if (!token) {
    return (
      <View style={styles.hint}>
        <Text style={styles.hintTxt}>请先登录</Text>
      </View>
    );
  }
  return (
    <View style={styles.root}>
      <CreatorPanel
        token={token}
        onCreated={(id) => {
          rootNav?.navigate("PublishPreview", { id });
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hint: { flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" },
  hintTxt: { color: colors.textMuted },
});
