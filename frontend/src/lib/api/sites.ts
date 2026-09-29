import { api } from "@/lib/api/client";
import type { Page, Site } from "@/types";

export interface SiteInput {
  name: string;
  address?: string | null;
  description?: string | null;
}

export const sitesApi = {
  list: () => api.get<Page<Site>>("/sites", { page_size: 500 }),
  create: (body: SiteInput) => api.post<Site>("/sites", body),
  update: (id: string, body: Partial<SiteInput>) => api.patch<Site>(`/sites/${id}`, body),
  remove: (id: string) => api.del(`/sites/${id}`),
};
