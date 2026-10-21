import { api, request } from "@/lib/api/client";
import type { TokenPair, User } from "@/types";

export const authApi = {
  login: (username: string, password: string) =>
    request<TokenPair>("/auth/login", { method: "POST", body: { username, password }, auth: false }),
  logout: (refresh_token: string) => api.post<void>("/auth/logout", { refresh_token }),
  me: () => api.get<User>("/auth/me"),
};
