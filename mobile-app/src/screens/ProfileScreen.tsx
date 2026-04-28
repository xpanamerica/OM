import React from "react";
import { StyleSheet, View } from "react-native";
import type { CompositeScreenProps } from "@react-navigation/native";
import type { BottomTabScreenProps } from "@react-navigation/bottom-tabs";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { MainTabParamList, RootStackParamList } from "../navigation/types";
import { colors } from "../theme/tokens";
import { ProfileDashboard } from "../components/ProfileDashboard";
import { useAuth } from "../context/AuthContext";

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, "Profile">,
  NativeStackScreenProps<RootStackParamList>
>;

export function ProfileScreen(_props: Props) {
  const { token, setToken } = useAuth();
  return (
    <View style={styles.root}>
      <ProfileDashboard
        token={token}
        onAuthenticated={async (access) => {
          await setToken(access);
        }}
        onLogout={() => void setToken(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
});
