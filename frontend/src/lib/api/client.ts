import { API_BASE } from "@/lib/config";
import { tokenStorage } from "@/lib/auth/tokenStorage";
import type { TokenPair } from "@/types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
  auth?: boolean;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${API_BASE}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

// single in-flight refresh shared by concurrent 401s
let refreshing: Promise<boolean> | null = null;

export async function refreshTokens(): Promise<boolean> {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) return false;
  refreshing ??= (async () => {
    try {
      const res = await fetch(buildUrl("/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) {
        tokenStorage.clear();
        return false;
      }
      tokenStorage.set((await res.json()) as TokenPair);
      return true;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

export async function request<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const { method = "GET", body, query, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = tokenStorage.getAccess();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401 && auth && !retried && (await refreshTokens())) {
    return request<T>(path, opts, true);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
};
