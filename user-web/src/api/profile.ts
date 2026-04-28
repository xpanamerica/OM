import { http } from "./http";
import type { VideoListItem } from "./videos";

export type ProfileHub = {
  following_count: number;
  followers_count: number;
  friends_count: number;
  pending_friend_request_count: number;
  likes_and_favorites_received: number;
  avatar_url?: string | null;
  unread_notification_count: number;
  recent_videos: VideoListItem[];
};

export async function fetchProfileHub(): Promise<ProfileHub> {
  const { data } = await http.get<ProfileHub>("/users/me/profile-hub");
  return data;
}
