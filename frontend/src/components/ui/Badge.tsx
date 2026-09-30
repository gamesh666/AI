"use client";

import clsx from "clsx";
import { useI18n } from "@/lib/i18n/I18nProvider";

type Tone = "green" | "red" | "yellow" | "gray" | "blue";

const tones: Record<Tone, string> = {
  green: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  red: "bg-red-500/15 text-red-300 ring-red-500/30",
  yellow: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  gray: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  blue: "bg-brand-500/15 text-brand-100 ring-brand-500/30",
};

export function Badge({ tone = "gray", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ring-1", tones[tone])}>
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

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const { tEnum } = useI18n();
  const s = status ?? "unknown";
  const text = tEnum("status", s);
  return (
    <Badge tone={STATUS_TONE[s] ?? "gray"}>
      {label ? `${label} ${text}` : text}
    </Badge>
  );
}
