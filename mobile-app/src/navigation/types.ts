import type { NavigatorScreenParams } from "@react-navigation/native";

export type MainTabParamList = {
  Feed: undefined;
  Discover: undefined;
  Create: undefined;
  Messages: undefined;
  Profile: undefined;
};

export type RootStackParamList = {
  Main: NavigatorScreenParams<MainTabParamList>;
  Detail: { id: string };
  PublishPreview: { id: string };
  Login: undefined;
  History: undefined;
  Favorites: undefined;
  UserProfile: { id: string };
  DirectMessages: { peerId?: string };
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
