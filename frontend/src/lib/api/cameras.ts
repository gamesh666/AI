import { api } from "@/lib/api/client";
import type { Camera, Page, StreamInfo, StreamType } from "@/types";

export interface CameraInput {
  edge_device_id: string;
  code: string;
  name: string;
  // write-only: the API never returns the camera address or credentials
  rtsp_url?: string;
  rtsp_username?: string;
  rtsp_password?: string;
  onvif_url?: string | null;
  enabled: boolean;
  ai_enabled: boolean;
  ai_model_id?: string | null;
  stream_enabled: boolean;
  annotated_stream_enabled: boolean;
  original_stream_enabled: boolean;
  resolution?: string | null;
  stream_fps: number;
  inference_fps: number;
  bitrate: string;
  gop_size: number;
}

export const camerasApi = {
  list: (q: { site_id?: string; edge_device_id?: string; enabled?: boolean } = {}) =>
    api.get<Page<Camera>>("/cameras", { page_size: 500, ...q }),
  create: (body: CameraInput) => api.post<Camera>("/cameras", body),
  update: (id: string, body: Partial<CameraInput>) => api.patch<Camera>(`/cameras/${id}`, body),
  remove: (id: string) => api.del(`/cameras/${id}`),
  /** WebRTC/HLS playback URLs + short-lived token for one stream path. */
  stream: (id: string, type: StreamType = "ai") => api.get<StreamInfo>(`/cameras/${id}/stream`, { type }),
};
