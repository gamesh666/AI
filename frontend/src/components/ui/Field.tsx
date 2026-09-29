import clsx from "clsx";
import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";

const control =
  "w-full rounded-md border border-slate-600 bg-surface-900 px-2.5 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-brand-500 focus:outline-none";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(control, className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={clsx(control, className)} {...props}>
      {children}
    </select>
  );
}

export function Checkbox({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-200">
      <input type="checkbox" className="h-4 w-4 accent-brand-500" {...props} />
      {label}
    </label>
  );
}
