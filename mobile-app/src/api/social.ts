import { apiDelete, apiGetJson, apiPatchJson, apiPostJson, apiPostMultipart } from "./client";
import type { VideoListItem } from "./types";

export type ProfileVisibility = "public" | "followers" | "mutual" | "private";
export type MessagePermission = "everyone" | "following" | "mutual" | "none";

export type UserBrief = { id: string; username: string; avatar_url?: string | null };
export type UserPrivacy = {
  profile_visibility: ProfileVisibility;
  message_permission: MessagePermission;
};
export type PublicUserProfile = {
  user: UserBrief;
  following_count: number;
  followers_count: number;
  friends_count: number;
  likes_and_favorites_received: number;
  is_following: boolean;
  follows_me: boolean;
  is_mutual: boolean;
  is_blocked: boolean;
  blocked_me: boolean;
  can_message: boolean;
  friend_request_status: "none" | "incoming_pending" | "outgoing_pending" | "accepted" | "rejected";
  privacy: UserPrivacy;
  recent_videos: VideoListItem[];
};
export type FollowUser = UserBrief & {
  followed_at: string;
  is_following: boolean;
  follows_me: boolean;
  is_mutual: boolean;
};
export type DirectMessage = {
  id: string;
  conversation_id: string;
  sender_id: string;
  recipient_id: string;
  body: string;
  read_at: string | null;
  created_at: string;
};
export type DirectMessageAttachment = {
  id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  url: string;
  created_at: string;
};
export type DirectConversation = {
  id: string;
  peer: UserBrief;
  last_message: DirectMessage | null;
  last_message_preview?: string | null;
  unread_count: number;
  updated_at: string | null;
};

export type FriendRequest = {
  id: string;
  requester: UserBrief;
  recipient: UserBrief;
  status: "pending" | "accepted" | "rejected" | "cancelled";
  message?: string | null;
  decided_at?: string | null;
  created_at: string;
};

export async function fetchUserProfile(userId: string, token: string | null): Promise<PublicUserProfile> {
  const { data } = await apiGetJson<PublicUserProfile>(`/users/${userId}/profile`, { token });
  return data;
}

export async function fetchMyPrivacy(token: string): Promise<UserPrivacy> {
  const { data } = await apiGetJson<UserPrivacy>("/users/me/privacy", { token });
  return data;
}

export async function updateMyPrivacy(token: string, payload: Partial<UserPrivacy>): Promise<UserPrivacy> {
  const { data } = await apiPatchJson<UserPrivacy>("/users/me/privacy", payload, { token });
  return data;
}

export async function followUser(userId: string, token: string): Promise<void> {
  await apiPostJson<unknown>(`/users/${userId}/follow`, {}, { token });
}

export async function unfollowUser(userId: string, token: string): Promise<void> {
  await apiDelete(`/users/${userId}/follow`, { token });
}

export async function sendFriendRequest(userId: string, token: string, message?: string): Promise<FriendRequest> {
  const { data } = await apiPostJson<FriendRequest>(`/users/${userId}/friend-requests`, { message: message || null }, { token });
  return data;
}

export async function listFriendRequests(token: string, box: "incoming" | "outgoing" = "incoming"): Promise<FriendRequest[]> {
  const q = new URLSearchParams({ box, status: "pending", offset: "0", limit: "100" });
  const { data } = await apiGetJson<FriendRequest[]>(`/users/me/friend-requests?${q}`, { token });
  return data;
}

export async function acceptFriendRequest(requestId: string, token: string): Promise<FriendRequest> {
  const { data } = await apiPostJson<FriendRequest>(`/users/me/friend-requests/${requestId}/accept`, {}, { token });
  return data;
}

export async function rejectFriendRequest(requestId: string, token: string): Promise<FriendRequest> {
  const { data } = await apiPostJson<FriendRequest>(`/users/me/friend-requests/${requestId}/reject`, {}, { token });
  return data;
}

export async function blockUser(userId: string, token: string): Promise<void> {
  await apiPostJson<unknown>(`/users/${userId}/block`, {}, { token });
}

export async function unblockUser(userId: string, token: string): Promise<void> {
  await apiDelete(`/users/${userId}/block`, { token });
}

export async function listConversations(token: string): Promise<DirectConversation[]> {
  const { data } = await apiGetJson<DirectConversation[]>("/direct-messages/conversations", { token });
  return data;
}

export async function listMyFriends(token: string): Promise<FollowUser[]> {
  const { data } = await apiGetJson<FollowUser[]>("/users/me/friends", { token });
  return data;
}

export async function listMessages(peerId: string, token: string): Promise<DirectMessage[]> {
  const { data } = await apiGetJson<DirectMessage[]>(`/direct-messages/conversations/${peerId}/messages`, {
    token,
  });
  return data;
}

export async function sendMessage(peerId: string, body: string, token: string): Promise<DirectMessage> {
  const { data } = await apiPostJson<DirectMessage>(`/direct-messages/conversations/${peerId}/messages`, { body }, { token });
  return data;
}

export async function uploadMessageAttachment(
  peerId: string,
  file: { uri: string; name: string; type?: string | null },
  token: string,
): Promise<DirectMessageAttachment> {
  const fd = new FormData();
  fd.append("file", {
    uri: file.uri,
    name: file.name,
    type: file.type || "application/octet-stream",
  } as unknown as Blob);
  const { data } = await apiPostMultipart<DirectMessageAttachment>(
    `/direct-messages/conversations/${peerId}/attachments`,
    fd,
    { token },
  );
  return data;
}
