"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth/AuthContext";
import { IDLE_LOGOUT_MS, IDLE_WARNING_MS } from "@/lib/config";
import { useI18n } from "@/lib/i18n/I18nProvider";

// shared by all tabs: activity in one tab keeps the others signed in too
const ACTIVITY_KEY = "aivms.lastActivity";
// tells the login page (in every tab) why the user was signed out
export const IDLE_FLAG_KEY = "aivms.idleLogoutAt";
const EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "wheel", "scroll"] as const;

function readActivity(fallback: number): number {
  try {
    return Number(localStorage.getItem(ACTIVITY_KEY)) || fallback;
  } catch {
    return fallback;
  }
}

/**
 * Signs the user out after IDLE_LOGOUT_MS without mouse / keyboard / touch activity (default 10 min,
 * NEXT_PUBLIC_IDLE_LOGOUT_MINUTES; 0 disables). A warning with a countdown appears 60 s before.
 */
export function IdleLogout() {
  const { logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const last = useRef(Date.now());
  const [remaining, setRemaining] = useState<number | null>(null);

  const touch = useCallback(() => {
    const now = Date.now();
    if (now - last.current < 2000) return; // throttle
    last.current = now;
    try {
      localStorage.setItem(ACTIVITY_KEY, String(now));
    } catch {
      /* ignore */
    }
    setRemaining(null);
  }, []);

  useEffect(() => {
    if (IDLE_LOGOUT_MS <= 0) return;
    last.current = 0;
    touch();
    EVENTS.forEach((e) => window.addEventListener(e, touch, { passive: true }));
    const onVisible = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onVisible);

    let done = false;
    function check() {
      if (done) return;
      last.current = Math.max(last.current, readActivity(last.current));
      const idle = Date.now() - last.current;
      if (idle >= IDLE_LOGOUT_MS) {
        done = true;
        try {
          localStorage.setItem(IDLE_FLAG_KEY, String(Date.now()));
        } catch {
          /* ignore */
        }
        logout().finally(() => router.replace("/login"));
      } else if (idle >= IDLE_LOGOUT_MS - IDLE_WARNING_MS) {
        setRemaining(Math.ceil((IDLE_LOGOUT_MS - idle) / 1000));
      } else {
        setRemaining(null);
      }
    }
    const timer = setInterval(check, 1000);
    return () => {
      clearInterval(timer);
      EVENTS.forEach((e) => window.removeEventListener(e, touch));
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [touch, logout, router]);

  if (remaining === null) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" role="alertdialog">
      <div className="w-full max-w-sm space-y-3 rounded-lg border border-amber-500/40 bg-surface-800 p-5 text-center">
        <h2 className="text-lg font-semibold">{t("idle.title")}</h2>
        <p className="text-sm text-slate-300">{t("idle.countdown", { n: remaining })}</p>
        <Button className="w-full" onClick={() => ((last.current = 0), touch())}>
          {t("idle.stay")}
        </Button>
      </div>
    </div>
  );
}
