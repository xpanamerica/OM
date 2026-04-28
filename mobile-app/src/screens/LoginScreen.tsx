import React from "react";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/types";
import { LoginFormCard } from "../components/LoginFormCard";
import { useAuth } from "../context/AuthContext";
import { RootBottomNav } from "../components/RootBottomNav";
import { colors } from "../theme/tokens";
import { View, StyleSheet } from "react-native";

type Props = NativeStackScreenProps<RootStackParamList, "Login">;

export function LoginScreen({ navigation }: Props) {
  const { setToken } = useAuth();

  return (
    <View style={styles.screen}>
      <LoginFormCard
        showCancel
        onCancel={() => navigation.goBack()}
        onSuccess={async (access) => {
          await setToken(access);
          navigation.reset({ index: 0, routes: [{ name: "Main" }] });
        }}
      />
      <RootBottomNav active="Profile" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
});
