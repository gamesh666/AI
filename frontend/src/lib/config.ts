// NEXT_PUBLIC_* values are inlined at build time (see frontend/Dockerfile build arg).
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const API_BASE = `${API_URL}/api/v1`;
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws`;

// how long to wait for a WebRTC track before falling back to HLS
export const WEBRTC_TIMEOUT_MS = 6000;
