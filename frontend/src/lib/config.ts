// NEXT_PUBLIC_* values are inlined at build time (see frontend/Dockerfile build arg).
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const API_BASE = `${API_URL}/api/v1`;
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws`;

// how long to wait for a WebRTC track before falling back to HLS
export const WEBRTC_TIMEOUT_MS = 6000;

// sign out after this long without mouse / keyboard / touch activity (0 = never)
const idleMinutes = Number(process.env.NEXT_PUBLIC_IDLE_LOGOUT_MINUTES ?? "10");
export const IDLE_LOGOUT_MS = Number.isFinite(idleMinutes) && idleMinutes > 0 ? idleMinutes * 60_000 : 0;
export const IDLE_LOGOUT_MINUTES = IDLE_LOGOUT_MS / 60_000;
export const IDLE_WARNING_MS = Math.min(60_000, IDLE_LOGOUT_MS / 2);
