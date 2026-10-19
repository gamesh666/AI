import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const styles: Record<Variant, string> = {
  primary: "border border-accent bg-accent text-on-accent hover:bg-accent-hi",
  secondary: "border border-line2 bg-panel text-ink hover:bg-panel2",
  danger: "border border-bad bg-bad text-on-accent hover:opacity-90",
  ghost: "border border-transparent text-ink2 hover:bg-panel2",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-item px-3 py-1.5 text-[13px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}
