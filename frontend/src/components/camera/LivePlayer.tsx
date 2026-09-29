"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { streamsApi } from "@/lib/api/streams";
import { WEBRTC_TIMEOUT_MS } from "@/lib/config";
import { errorMessage } from "@/lib/format";
import { startHls } from "@/lib/streaming/hls";
import { startWhep } from "@/lib/streaming/whep";

type Mode = "connecting" | "webrtc" | "hls" | "error";

/**
 * Live view: WebRTC (WHEP) first; if no media arrives within WEBRTC_TIMEOUT_MS or the
 * peer connection fails, fall back to HLS.
 */
export function LivePlayer({ cameraId, active = true }: { cameraId: string; active?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [mode, setMode] = useState<Mode>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let cleanup: (() => void) | null = null;
    let fallbackTimer: ReturnType<typeof setTimeout> | undefined;
    const video = videoRef.current;
    if (!video) return;

    const fail = (reason: string) => {
      if (cancelled) return;
      setMode("error");
      setError(reason);
    };

    const playHls = async (url: string, token: string) => {
      cleanup?.();
      cleanup = null;
      if (cancelled) return;
      try {
        const session = await startHls(video, url, token, fail);
        cleanup = session.close;
        setMode("hls");
        video.play().catch(() => undefined);
      } catch (e) {
        fail(errorMessage(e));
      }
    };

    (async () => {
      setMode("connecting");
      setError(null);
      let info;
      try {
        info = await streamsApi.get(cameraId);
      } catch (e) {
        return fail(errorMessage(e));
      }
      if (cancelled) return;

      let gotTrack = false;
      const fallback = () => {
        if (!gotTrack && !cancelled) playHls(info.hls_url, info.token);
      };
      try {
        const session = await startWhep(
          info.webrtc_url,
          info.token,
          (stream) => {
            gotTrack = true;
            clearTimeout(fallbackTimer);
            video.srcObject = stream;
            video.play().catch(() => undefined);
            setMode("webrtc");
          },
          () => (gotTrack ? fail("webrtc connection lost") : fallback()),
        );
        if (cancelled) return session.close();
        cleanup = () => {
          session.close();
          video.srcObject = null;
        };
        fallbackTimer = setTimeout(fallback, WEBRTC_TIMEOUT_MS);
      } catch {
        fallback();
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(fallbackTimer);
      cleanup?.();
    };
  }, [cameraId, active, attempt]);

  return (
    <div className="relative aspect-video w-full overflow-hidden bg-black">
      <video ref={videoRef} className="h-full w-full object-contain" muted playsInline autoPlay />
      <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] uppercase text-slate-300">
        {mode}
      </span>
      {mode === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/70 text-center text-xs text-slate-300">
          <span>Stream unavailable</span>
          {error && <span className="max-w-[90%] truncate text-slate-500">{error}</span>}
          <button onClick={retry} className="rounded bg-surface-600 px-2 py-1 hover:bg-surface-700">
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
