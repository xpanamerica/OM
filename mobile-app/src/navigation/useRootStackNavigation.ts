import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "./types";

/** Tab 内屏幕取包裹它们的根 Stack 导航器（用于打开 ``Login`` / ``Detail`` 等） */
export function useRootStackNavigation(): NativeStackNavigationProp<RootStackParamList> | undefined {
  const nav = useNavigation();
  return nav.getParent() as NativeStackNavigationProp<RootStackParamList> | undefined;
}
