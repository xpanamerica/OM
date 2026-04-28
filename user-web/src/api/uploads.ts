import { http } from "./http";

export type VodCreateUploadVideoBody = {
  title: string;
  filename: string;
  file_size: number;
  description?: string | null;
  cover_url?: string | null;
};

export type VodCreateUploadVideoResponse = {
  video_id_from_vod: string;
  upload_address: string;
  upload_auth: string;
  request_id: string;
};

/** ``POST /uploads/vod/create-upload-video``：需登录；服务端调阿里云 CreateUploadVideo。 */
export async function createVodUploadVideo(body: VodCreateUploadVideoBody): Promise<VodCreateUploadVideoResponse> {
  const { data } = await http.post<VodCreateUploadVideoResponse>("/uploads/vod/create-upload-video", {
    title: body.title.trim(),
    filename: body.filename.trim(),
    file_size: body.file_size,
    description: body.description?.trim() || null,
    cover_url: body.cover_url?.trim() || null,
  });
  return data;
}

export type VodRefreshUploadVideoBody = {
  vod_video_id: string;
};

/** ``POST /uploads/vod/refresh-upload-video``：大文件上传中途 STS 过期时刷新凭证；不消耗每日 Create 次数。 */
export async function refreshVodUploadVideo(body: VodRefreshUploadVideoBody): Promise<VodCreateUploadVideoResponse> {
  const { data } = await http.post<VodCreateUploadVideoResponse>("/uploads/vod/refresh-upload-video", {
    vod_video_id: body.vod_video_id.trim(),
  });
  return data;
}
