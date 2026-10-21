"use client";

// One WebSocket per browser tab; components subscribe to message types via useRealtime().
// Backend fans out through Redis Pub/Sub, so this works regardless of which backend replica we hit.

import { createContext, useContext, useEffect, useRef, useState } from "react";

import { refreshTokens } from "@/lib/api/client";
import { WS_URL } from "@/lib/config";
import { tokenStorage } from "@/lib/auth/tokenStorage";
import type { RealtimeMessage, RealtimeType } from "@/types";

type Listener = (msg: RealtimeMessage) => void;

interface RealtimeState {
  connected: boolean;
  subscribe: (type: RealtimeType, listener: Listener) => () => void;
}

const RealtimeContext = createContext<RealtimeState | null>(null);

const MAX_BACKOFF_MS = 15000;

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const listeners = useRef(new Map<RealtimeType, Set<Listener>>());
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let backoff = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const token = tokenStorage.getAccess();
      if (!token || closed) return;
      let opened = false;
      ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
      ws.onopen = () => {
        opened = true;
        backoff = 1000;
        setConnected(true);
      };
      ws.onmessage = (ev) => {
        let msg: RealtimeMessage;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        listeners.current.get(msg.type)?.forEach((fn) => fn(msg));
      };
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        // handshake rejected -> most likely an expired access token: refresh before retrying
        const retry = () => {
          timer = setTimeout(connect, backoff);
          backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
        };
        if (opened) retry();
        else refreshTokens().finally(retry);
      };
    };

    connect();
    const onTokens = () => {
      ws?.close();
    };
    window.addEventListener("aivms:tokens", onTokens);
    return () => {
      closed = true;
      clearTimeout(timer);
      window.removeEventListener("aivms:tokens", onTokens);
      ws?.close();
    };
  }, []);

  const subscribe = (type: RealtimeType, listener: Listener) => {
    const set = listeners.current.get(type) ?? new Set<Listener>();
    set.add(listener);
    listeners.current.set(type, set);
    return () => {
      set.delete(listener);
    };
  };

  return <RealtimeContext.Provider value={{ connected, subscribe }}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeStatus(): boolean {
  return useContext(RealtimeContext)?.connected ?? false;
}

/** Calls `handler` for every realtime message of `type`. Handler may change between renders. */
export function useRealtime<T>(type: RealtimeType, handler: (data: T, msg: RealtimeMessage<T>) => void) {
  const ctx = useContext(RealtimeContext);
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!ctx) return;
    return ctx.subscribe(type, (msg) => ref.current(msg.data as T, msg as RealtimeMessage<T>));
  }, [ctx, type]);
}
