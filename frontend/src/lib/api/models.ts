import { api } from "@/lib/api/client";
import type { AIModel, ModelUsageOverview, Page } from "@/types";

export interface AIModelInput {
  name: string;
  version: string;
  model_type: string;
  labels: string[];
  model_path: string;
  description?: string | null;
}

export const modelsApi = {
  /** what the edges report running, grouped by model */
  inUse: () => api.get<ModelUsageOverview>("/ai-models/in-use"),
  list: () => api.get<Page<AIModel>>("/ai-models", { page_size: 500 }),
  create: (body: AIModelInput) => api.post<AIModel>("/ai-models", body),
  update: (id: string, body: Partial<AIModelInput>) => api.patch<AIModel>(`/ai-models/${id}`, body),
  remove: (id: string) => api.del(`/ai-models/${id}`),
};
