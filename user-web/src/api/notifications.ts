import { http } from "./http";
import { readTotalCountFromHeaders } from "@/util/readTotalCountHeader";

export type UserNotification = {
  id: string;
  title: string;
  body: string | null;
  kind: string;
  action_url: string | null;
  read_at: string | null;
  created_at: string;
};

export async function listMyNotifications(params: {
  offset: number;
  limit: number;
}): Promise<{ items: UserNotification[]; total: number; unreadCount: number }> {
  const { data, headers } = await http.get<UserNotification[]>("/users/me/notifications", { params });
  const raw = headers["x-unread-count"] ?? headers["X-Unread-Count"];
  const unreadCount = Number.parseInt(String(raw ?? "0"), 10);
  return {
    items: data,
    total: readTotalCountFromHeaders(headers),
    unreadCount: Number.isFinite(unreadCount) ? unreadCount : 0,
  };
}

export async function getMyNotificationsUnreadCount(): Promise<number> {
  const { data } = await http.get<{ unread_count: number }>("/users/me/notifications/unread-count");
  return data.unread_count;
}

export async function markNotificationRead(notificationId: string): Promise<UserNotification> {
  const { data } = await http.patch<UserNotification>(`/users/me/notifications/${notificationId}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await http.post<{ marked: number }>("/users/me/notifications/read-all");
  return data.marked;
}
