import { Icon, type IconName } from "@/components/ui/Icon";

export type KpiColor = "green" | "orange" | "red" | "blue" | "sky" | "amber";

/**
 * KPI tile (§5.4): round icon + label + big number with a small unit / note.
 * With `ring`, the icon becomes a conic progress ring (e.g. cameras running 3/5).
 */
export function StatCard({
  label,
  value,
  small,
  icon,
  color = "blue",
  ring,
}: {
  label: string;
  value: number | string | null | undefined;
  small?: string;
  icon: IconName;
  color?: KpiColor;
  ring?: { pct: number; state?: "ok" | "warn" | "bad" };
}) {
  return (
    <div className="kpi">
      {ring ? (
        <span
          className="kpi-ic kpi-ring"
          data-state={ring.state}
          style={{ "--pct": Math.round(ring.pct) } as React.CSSProperties}
        >
          <span>
            <Icon name={icon} />
          </span>
        </span>
      ) : (
        <span className={`kpi-ic ${color}`}>
          <Icon name={icon} size={22} />
        </span>
      )}
      <div className="min-w-0">
        <div className="kpi-k">{label}</div>
        <div className="kpi-v truncate">
          <b className={ring ? "!text-ok" : undefined}>{value ?? "--"}</b>
          {small && !ring && <small>{small}</small>}
        </div>
        {small && ring && <div className="truncate text-[11.5px] text-muted">{small}</div>}
      </div>
    </div>
  );
}
