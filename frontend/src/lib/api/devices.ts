import { api } from "@/lib/api/client";
import type { EdgeConnectionInfo, EdgeDevice, EdgeDeviceWithKey, Page } from "@/types";

export interface DeviceInput {
  device_uuid: string;
  name: string;
  site_id?: string | null;
}

export const devicesApi = {
  list: (q: { site_id?: string; status?: string } = {}) =>
    api.get<Page<EdgeDevice>>("/devices", { page_size: 500, ...q }),
  create: (body: DeviceInput) => api.post<EdgeDeviceWithKey>("/devices", body),
  update: (id: string, body: { name?: string; site_id?: string | null }) =>
    api.patch<EdgeDevice>(`/devices/${id}`, body),
  remove: (id: string) => api.del(`/devices/${id}`),
  connection: (id: string) => api.get<EdgeConnectionInfo>(`/devices/${id}/connection`),
  rotateKey: (id: string) => api.post<EdgeDeviceWithKey>(`/devices/${id}/rotate-key`),
  command: (id: string, command: string, params: Record<string, unknown> = {}) =>
    api.post<{ command_id: string }>(`/devices/${id}/commands`, { command, params }),
};
