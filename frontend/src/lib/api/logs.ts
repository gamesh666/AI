import { api } from "@/lib/api/client";
import type { EdgeLog, Page } from "@/types";

export interface LogQuery {
  page?: number;
  page_size?: number;
  start?: string;
  end?: string;
  site_id?: string;
  edge_device_id?: string;
  camera_id?: string;
  event_type?: string;
  severity?: string;
  status?: string;
  q?: string;
}

export const logsApi = {
  list: (q: LogQuery) => api.get<Page<EdgeLog>>("/logs", { ...q }),
  types: () => api.get<string[]>("/logs/types"),
};
