import clsx from "clsx";

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
    <span className={clsx("inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1", tones[tone])}>
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  online: "green",
  offline: "red",
  error: "red",
  pending: "yellow",
  unknown: "gray",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const s = status ?? "unknown";
  return <Badge tone={STATUS_TONE[s] ?? "gray"}>{s}</Badge>;
}
