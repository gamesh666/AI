import { api } from "@/lib/api/client";
import type { DetectionEvent, Page } from "@/types";

export interface EventQuery {
  page?: number;
  page_size?: number;
  start?: string;
  end?: string;
  site_id?: string;
  camera_id?: string;
  edge_device_id?: string;
  class_name?: string;
  min_confidence?: number;
}

export const eventsApi = {
  list: (q: EventQuery) => api.get<Page<DetectionEvent>>("/events", { ...q }),
  classes: () => api.get<string[]>("/events/classes"),
};
