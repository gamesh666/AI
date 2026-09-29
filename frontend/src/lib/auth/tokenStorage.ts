import type { TokenPair } from "@/types";

// MVP: tokens in localStorage. Production hardening: move the refresh token to an
// httpOnly, SameSite=strict cookie issued by the backend.
const ACCESS_KEY = "aivms.access";
const REFRESH_KEY = "aivms.refresh";

const isBrowser = () => typeof window !== "undefined";

export const tokenStorage = {
  getAccess(): string | null {
    return isBrowser() ? localStorage.getItem(ACCESS_KEY) : null;
  },
  getRefresh(): string | null {
    return isBrowser() ? localStorage.getItem(REFRESH_KEY) : null;
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    window.dispatchEvent(new Event("aivms:tokens"));
  },
  clear() {
    if (!isBrowser()) return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    window.dispatchEvent(new Event("aivms:tokens"));
  },
};
