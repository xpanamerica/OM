import { http } from "./http";
import type { VideoListItem } from "./admin";

export type VideoResponse = VideoListItem & {
  description: string | null;
  video_url: string | null;
  updated_at: string;
  row_version: number;
};

export type VideoWorkflowEvent = {
  id: string;
  video_id: string;
  actor_id: string | null;
  action: string;
  from_status: string;
  to_status: string;
  detail: Record<string, unknown> | null;
  created_at: string;
};

export async function getVideo(videoId: string): Promise<VideoResponse> {
  const { data } = await http.get<VideoResponse>(`/videos/${videoId}`);
  return data;
}

export async function patchVideo(
  videoId: string,
  body: Partial<{
    title: string;
    description: string | null;
    cover_url: string | null;
    video_url: string | null;
    category_id: string | null;
    status: string;
    tag_ids: string[];
  }>,
): Promise<VideoResponse> {
  const { data } = await http.patch<VideoResponse>(`/videos/${videoId}`, body);
  return data;
}

export async function submitReviewVideo(videoId: string): Promise<VideoResponse> {
  const { data } = await http.post<VideoResponse>(`/videos/${videoId}/submit-review`);
  return data;
}

export async function approveVideo(videoId: string): Promise<VideoResponse> {
  const { data } = await http.post<VideoResponse>(`/videos/${videoId}/approve`);
  return data;
}

export async function rejectVideo(videoId: string, rejection_reason: string): Promise<VideoResponse> {
  const { data } = await http.post<VideoResponse>(`/videos/${videoId}/reject`, { rejection_reason });
  return data;
}

export async function offlineVideo(videoId: string): Promise<VideoResponse> {
  const { data } = await http.post<VideoResponse>(`/videos/${videoId}/offline`);
  return data;
}

export async function deleteVideo(videoId: string): Promise<void> {
  await http.delete(`/videos/${videoId}`);
}

export async function listWorkflowEvents(videoId: string): Promise<VideoWorkflowEvent[]> {
  const { data } = await http.get<VideoWorkflowEvent[]>(`/videos/${videoId}/workflow-events`, {
    params: { limit: 100, offset: 0 },
  });
  return data;
}
