import { api } from "@/lib/api/client";
import type { Page, Site } from "@/types";

export interface SiteInput {
  name: string;
  code: string;
  address?: string | null;
  description?: string | null;
  owner_id?: string | null;
  profile?: string | null;
  license_code?: string | null;
  license_until?: string | null;
  contract_no?: string | null;
  term_years?: number | null;
  transaction_type?: string | null;
}

export const sitesApi = {
  list: () => api.get<Page<Site>>("/sites", { page_size: 500 }),
  create: (body: SiteInput) => api.post<Site>("/sites", body),
  update: (id: string, body: Partial<SiteInput>) => api.patch<Site>(`/sites/${id}`, body),
  remove: (id: string) => api.del(`/sites/${id}`),
};
