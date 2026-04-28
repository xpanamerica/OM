import { apiGetJson, apiPatchJson, apiPostJson, readTotalCount } from "./client";

export type UserNotification = {
  id: string;
  title: string;
  body: string | null;
  kind: string;
  action_url: string | null;
  read_at: string | null;
  created_at: string;
};

export async function getUnreadCount(token: string): Promise<number> {
  const { data } = await apiGetJson<{ unread_count: number }>("/users/me/notifications/unread-count", { token });
  return data.unread_count;
}

export async function listMyNotifications(
  params: { offset: number; limit: number },
  token: string,
): Promise<{ items: UserNotification[]; total: number }> {
  const q = new URLSearchParams({ offset: String(params.offset), limit: String(params.limit) });
  const { data, headers } = await apiGetJson<UserNotification[]>(`/users/me/notifications?${q}`, { token });
  return { items: data, total: readTotalCount(headers) };
}

export async function markNotificationRead(notificationId: string, token: string): Promise<UserNotification> {
  const { data } = await apiPatchJson<UserNotification, Record<string, never>>(
    `/users/me/notifications/${notificationId}/read`,
    {},
    { token },
  );
  return data;
}

export async function markAllNotificationsRead(token: string): Promise<number> {
  const { data } = await apiPostJson<{ marked: number }, Record<string, never>>(
    "/users/me/notifications/read-all",
    {},
    { token },
  );
  return data.marked;
}
