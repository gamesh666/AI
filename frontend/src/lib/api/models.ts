import { api } from "@/lib/api/client";
import type { ModelUsageOverview } from "@/types";

export const modelsApi = {
  /** what the edges report running, grouped by model */
  inUse: () => api.get<ModelUsageOverview>("/ai-models/in-use"),
};
