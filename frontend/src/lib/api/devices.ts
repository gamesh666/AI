import { api } from "@/lib/api/client";
import type { AdminState, DeviceAudit, DeviceReport, EdgeDevice, Page, ReportFilters, ReportOptions } from "@/types";

/** Devices are created only by registering with a provisioning token; here they are edited. */
export interface DeviceInput {
  name: string;
  site_id?: string | null;
  // admin only
  mac_address?: string | null;
  owner_id?: string | null;
  admin_state?: AdminState;
}

export const devicesApi = {
  list: (q: { site_id?: string; status?: string } = {}) =>
    api.get<Page<EdgeDevice>>("/devices", { page_size: 500, ...q }),
  update: (id: string, body: Partial<DeviceInput>) => api.patch<EdgeDevice>(`/devices/${id}`, body),
  remove: (id: string) => api.del(`/devices/${id}`),
  audit: (id: string) => api.get<DeviceAudit[]>(`/devices/${id}/audit`),
  command: (id: string, command: string, params: Record<string, unknown> = {}) =>
    api.post<{ command_id: string }>(`/devices/${id}/commands`, { command, params }),
  // 出勤事件報表: built by the edge from its own database, uploaded back as PDF
  reportOptions: (id: string) => api.get<ReportOptions>(`/devices/${id}/report-options`),
  reports: (id: string) => api.get<DeviceReport[]>(`/devices/${id}/reports`),
  requestReport: (id: string, filters: ReportFilters) => api.post<DeviceReport>(`/devices/${id}/reports`, filters),
  reportDownload: (reportId: string) => api.get<{ url: string; filename: string }>(`/reports/${reportId}/download`),
};
