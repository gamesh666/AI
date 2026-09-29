import { api } from "@/lib/api/client";
import type { Page, Role, User } from "@/types";

export interface UserInput {
  username: string;
  email?: string | null;
  full_name?: string | null;
  role: Role;
  is_active: boolean;
  password?: string;
}

export const usersApi = {
  list: () => api.get<Page<User>>("/users", { page_size: 500 }),
  create: (body: UserInput & { password: string }) => api.post<User>("/users", body),
  update: (id: string, body: Partial<UserInput>) => api.patch<User>(`/users/${id}`, body),
  remove: (id: string) => api.del(`/users/${id}`),
};
