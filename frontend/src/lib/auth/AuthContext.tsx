"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { authApi } from "@/lib/api/auth";
import { tokenStorage } from "@/lib/auth/tokenStorage";
import type { Role, User } from "@/types";

const LEVEL: Record<Role, number> = { viewer: 10, operator: 20, admin: 30 };

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (min: Role) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!tokenStorage.getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch {
      tokenStorage.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // signed out in another tab (manually or by the idle timer) -> sign out here too
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || (e.key === "aivms.access" && !e.newValue)) {
        if (!tokenStorage.getAccess()) setUser(null);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    tokenStorage.set(await authApi.login(username, password));
    setUser(await authApi.me());
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh();
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      /* already invalid */
    }
    tokenStorage.clear();
    setUser(null);
  }, []);

  const hasRole = useCallback((min: Role) => !!user && LEVEL[user.role] >= LEVEL[min], [user]);

  const value = useMemo(() => ({ user, loading, login, logout, hasRole }), [user, loading, login, logout, hasRole]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
