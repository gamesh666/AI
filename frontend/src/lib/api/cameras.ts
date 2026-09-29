import { api } from "@/lib/api/client";
import type { Camera, Page } from "@/types";

export interface CameraInput {
  edge_device_id: string;
  name: string;
  rtsp_url: string;
  rtsp_username?: string;
  // write-only: the API never returns RTSP credentials
  rtsp_password?: string;
  onvif_url?: string | null;
  enabled: boolean;
  ai_enabled: boolean;
  ai_model_id?: string | null;
}

export const camerasApi = {
  list: (q: { site_id?: string; edge_device_id?: string; enabled?: boolean } = {}) =>
    api.get<Page<Camera>>("/cameras", { page_size: 500, ...q }),
  create: (body: CameraInput) => api.post<Camera>("/cameras", body),
  update: (id: string, body: Partial<CameraInput>) => api.patch<Camera>(`/cameras/${id}`, body),
  remove: (id: string) => api.del(`/cameras/${id}`),
};
