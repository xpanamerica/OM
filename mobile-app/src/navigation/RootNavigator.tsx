import React from "react";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { RootStackParamList } from "./types";
import { colors } from "../theme/tokens";
import { MainTabNavigator } from "./MainTabNavigator";
import { DetailScreen } from "../screens/DetailScreen";
import { PublishPreviewScreen } from "../screens/PublishPreviewScreen";
import { LoginScreen } from "../screens/LoginScreen";
import { HistoryScreen } from "../screens/HistoryScreen";
import { FavoritesScreen } from "../screens/FavoritesScreen";
import { UserProfileScreen } from "../screens/UserProfileScreen";
import { DirectMessagesScreen } from "../screens/DirectMessagesScreen";
import { useAuth } from "../context/AuthContext";

const Stack = createNativeStackNavigator<RootStackParamList>();

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.bg,
    card: colors.bg,
    text: colors.text,
    border: colors.border,
    primary: colors.accent,
  },
};

export function RootNavigator() {
  const { isReady } = useAuth();
  if (!isReady) return null;

  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        initialRouteName="Main"
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerTintColor: colors.text,
          headerTitleStyle: { fontWeight: "800" },
          contentStyle: { backgroundColor: colors.bg },
          animation: "slide_from_right",
          gestureEnabled: true,
          fullScreenGestureEnabled: true,
        }}
      >
        <Stack.Screen name="Main" component={MainTabNavigator} options={{ headerShown: false }} />
        <Stack.Screen name="Detail" component={DetailScreen} options={{ title: "视频" }} />
        <Stack.Screen name="PublishPreview" component={PublishPreviewScreen} options={{ title: "发布预览" }} />
        <Stack.Screen name="History" component={HistoryScreen} options={{ title: "历史记录" }} />
        <Stack.Screen name="Favorites" component={FavoritesScreen} options={{ title: "个人收藏" }} />
        <Stack.Screen name="UserProfile" component={UserProfileScreen} options={{ title: "用户主页" }} />
        <Stack.Screen name="DirectMessages" component={DirectMessagesScreen} options={{ title: "私信" }} />
        <Stack.Screen
          name="Login"
          component={LoginScreen}
          options={{ title: "登录", presentation: "modal" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
