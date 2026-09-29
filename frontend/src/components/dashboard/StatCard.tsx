import clsx from "clsx";

export function StatCard({
  label,
  value,
  tone = "default",
  hint,
}: {
  label: string;
  value: number | string | null | undefined;
  tone?: "default" | "good" | "bad" | "info";
  hint?: string;
}) {
  const color = {
    default: "text-white",
    good: "text-emerald-300",
    bad: "text-red-300",
    info: "text-brand-400",
  }[tone];
  return (
    <div className="rounded-lg border border-slate-700/60 bg-surface-800 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={clsx("mt-1 text-3xl font-semibold tabular-nums", color)}>{value ?? "—"}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}
