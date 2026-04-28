/** 与 user-web / 后端 ``VideoListItem`` 对齐 */
export type VideoListItem = {
  id: string;
  title: string;
  cover_url: string | null;
  status: string;
  author_id: string;
  author_username?: string | null;
  category_id: string | null;
  views_count: number;
  likes_count: number;
  favorites_count: number;
  comments_count?: number;
  published_at: string | null;
  rejection_reason: string | null;
  vod_video_id: string | null;
  upload_status: string;
  transcode_status: string;
  duration_seconds: number | null;
  source_file_name: string | null;
  created_at: string;
  tags: { id: string; name: string }[];
  recommendation_reason?: Record<string, number> | null;
  recommendation_text?: string | null;
};

export type VideoDetail = VideoListItem & {
  description: string | null;
  video_url: string | null;
  updated_at: string;
  row_version: number;
};

export type VideoPlayResponse = {
  video_id: string;
  vod_video_id: string;
  play_auth: string;
  expire_time: string | null;
  request_id: string | null;
};

export type UserPublic = {
  id: string;
  email: string;
  username: string;
  avatar_url?: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type CategoryPublic = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type?: string;
};

export type LearningPathPublic = {
  id: string;
  title: string;
  description: string | null;
  creator_id: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
};
