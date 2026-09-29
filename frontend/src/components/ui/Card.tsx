import clsx from "clsx";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={clsx("rounded-lg border border-slate-700/60 bg-surface-800 p-4", className)}>{children}</div>;
}
