import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import type { MainTabParamList } from "./types";
import { colors } from "../theme/tokens";
import { FeedScreen } from "../screens/FeedScreen";
import { DiscoverScreen } from "../screens/DiscoverScreen";
import { CreateScreen } from "../screens/CreateScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { MessagesScreen } from "../screens/MessagesScreen";
import { XhsTabBar } from "./XhsTabBar";

const Tab = createBottomTabNavigator<MainTabParamList>();

export function MainTabNavigator() {
  return (
    <Tab.Navigator
      tabBar={(props) => <XhsTabBar {...props} />}
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: "800" },
        headerShadowVisible: false,
      }}
    >
      <Tab.Screen
        name="Feed"
        component={FeedScreen}
        options={{
          title: "首页",
          headerShown: false,
        }}
      />
      <Tab.Screen
        name="Discover"
        component={DiscoverScreen}
        options={{
          title: "发现",
        }}
      />
      <Tab.Screen
        name="Create"
        component={CreateScreen}
        options={{
          title: "创作",
        }}
      />
      <Tab.Screen
        name="Messages"
        component={MessagesScreen}
        options={{
          title: "互动消息",
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{
          title: "个人",
        }}
      />
    </Tab.Navigator>
  );
}
