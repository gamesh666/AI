"use client";

import { useI18n } from "@/lib/i18n/I18nProvider";

/** Status pill driven by data-state (colors in globals.css §4); `blue` = accent / info. */
type Tone = "green" | "red" | "yellow" | "gray" | "blue";

const STATE: Record<Tone, string> = { green: "ok", red: "bad", yellow: "warn", gray: "idle", blue: "info" };

export function Badge({ tone = "gray", dot = false, children }: { tone?: Tone; dot?: boolean; children: React.ReactNode }) {
  return (
    <span className="pill" data-state={STATE[tone]}>
      {dot && <span className="state-dot" />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  online: "green",
  streaming: "green",
  running: "green",
  offline: "red",
  error: "red",
  pending: "yellow",
  connecting: "yellow",
  loading: "yellow",
  unknown: "gray",
  idle: "gray",
  disabled: "gray",
};

/** Online / offline style labels use the service pill (§4 .svc-pill) with a status dot. */
export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const { tEnum } = useI18n();
  const s = status ?? "unknown";
  const text = tEnum("status", s);
  return (
    <span className="svc-pill" data-state={STATE[STATUS_TONE[s] ?? "gray"]}>
      <span className="state-dot" />
      {label ? `${label} ${text}` : text}
    </span>
  );
}
