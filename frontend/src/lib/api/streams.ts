import { api } from "@/lib/api/client";
import type { StreamInfo } from "@/types";

export const streamsApi = {
  get: (cameraId: string) => api.get<StreamInfo>(`/streams/${cameraId}`),
};
