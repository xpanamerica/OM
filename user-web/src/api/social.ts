import { http } from "./http";
import type { VideoListItem } from "./videos";

export type ProfileVisibility = "public" | "followers" | "mutual" | "private";
export type MessagePermission = "everyone" | "following" | "mutual" | "none";

export type UserBrief = {
  id: string;
  username: string;
  avatar_url?: string | null;
};

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

export async function fetchMyPrivacy(): Promise<UserPrivacy> {
  const { data } = await http.get<UserPrivacy>("/users/me/privacy");
  return data;
}

export async function updateMyPrivacy(payload: Partial<UserPrivacy>): Promise<UserPrivacy> {
  const { data } = await http.patch<UserPrivacy>("/users/me/privacy", payload);
  return data;
}

export async function fetchUserProfile(userId: string): Promise<PublicUserProfile> {
  const { data } = await http.get<PublicUserProfile>(`/users/${userId}/profile`);
  return data;
}

export async function followUser(userId: string): Promise<void> {
  await http.post(`/users/${userId}/follow`);
}

export async function unfollowUser(userId: string): Promise<void> {
  await http.delete(`/users/${userId}/follow`);
}

export async function sendFriendRequest(userId: string, message?: string): Promise<FriendRequest> {
  const { data } = await http.post<FriendRequest>(`/users/${userId}/friend-requests`, { message: message || null });
  return data;
}

export async function listFriendRequests(box: "incoming" | "outgoing" = "incoming"): Promise<FriendRequest[]> {
  const { data } = await http.get<FriendRequest[]>("/users/me/friend-requests", {
    params: { box, status: "pending", offset: 0, limit: 100 },
  });
  return data;
}

export async function acceptFriendRequest(requestId: string): Promise<FriendRequest> {
  const { data } = await http.post<FriendRequest>(`/users/me/friend-requests/${requestId}/accept`);
  return data;
}

export async function rejectFriendRequest(requestId: string): Promise<FriendRequest> {
  const { data } = await http.post<FriendRequest>(`/users/me/friend-requests/${requestId}/reject`);
  return data;
}

export async function blockUser(userId: string): Promise<void> {
  await http.post(`/users/${userId}/block`);
}

export async function unblockUser(userId: string): Promise<void> {
  await http.delete(`/users/${userId}/block`);
}

export async function listFollowing(userId: string): Promise<FollowUser[]> {
  const { data } = await http.get<FollowUser[]>(`/users/${userId}/following`, { params: { offset: 0, limit: 50 } });
  return data;
}

export async function listFollowers(userId: string): Promise<FollowUser[]> {
  const { data } = await http.get<FollowUser[]>(`/users/${userId}/followers`, { params: { offset: 0, limit: 50 } });
  return data;
}

export async function listMyFriends(): Promise<FollowUser[]> {
  const { data } = await http.get<FollowUser[]>("/users/me/friends", { params: { offset: 0, limit: 100 } });
  return data;
}

export async function listConversations(): Promise<DirectConversation[]> {
  const { data } = await http.get<DirectConversation[]>("/direct-messages/conversations");
  return data;
}

export async function listMessages(peerId: string): Promise<DirectMessage[]> {
  const { data } = await http.get<DirectMessage[]>(`/direct-messages/conversations/${peerId}/messages`, {
    params: { offset: 0, limit: 100 },
  });
  return data;
}

export async function sendMessage(peerId: string, body: string): Promise<DirectMessage> {
  const { data } = await http.post<DirectMessage>(`/direct-messages/conversations/${peerId}/messages`, { body });
  return data;
}

export async function uploadMessageAttachment(peerId: string, file: File): Promise<DirectMessageAttachment> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await http.post<DirectMessageAttachment>(`/direct-messages/conversations/${peerId}/attachments`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function downloadMessageAttachmentBlob(url: string): Promise<Blob> {
  const path = url.replace(/^\/api\/v1(?=\/)/, "");
  const res = await http.get<Blob>(path, { responseType: "blob" });
  return res.data;
}
