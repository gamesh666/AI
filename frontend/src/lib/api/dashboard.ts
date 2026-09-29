import { api } from "@/lib/api/client";
import type { DashboardSummary } from "@/types";

export const dashboardApi = {
  // "today" = since the viewer's local midnight
  summary: () => {
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    return api.get<DashboardSummary>("/dashboard/summary", { since: midnight.toISOString() });
  },
};
