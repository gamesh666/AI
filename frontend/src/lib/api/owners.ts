import { api } from "@/lib/api/client";
import type { Owner, ProvisioningToken, ProvisioningTokenCreated } from "@/types";

export interface OwnerInput {
  name: string;
  company_name?: string | null;
  company_address?: string | null;
  company_phone?: string | null;
  tax_id?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
}

export interface TokenInput {
  label?: string | null;
  site_id?: string | null;
  device_prefix: string;
  max_devices?: number | null;
  expires_at?: string | null;
}

export const ownersApi = {
  list: () => api.get<Owner[]>("/owners"),
  create: (body: OwnerInput) => api.post<Owner>("/owners", body),
  update: (id: string, body: Partial<OwnerInput>) => api.patch<Owner>(`/owners/${id}`, body),
  remove: (id: string) => api.del(`/owners/${id}`),
  tokens: (id: string) => api.get<ProvisioningToken[]>(`/owners/${id}/tokens`),
  createToken: (id: string, body: TokenInput) => api.post<ProvisioningTokenCreated>(`/owners/${id}/tokens`, body),
  revokeToken: (tokenId: string) => api.post<ProvisioningToken>(`/provisioning-tokens/${tokenId}/revoke`),
};
