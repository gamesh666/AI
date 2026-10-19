"use client";

import { StatusBadge } from "@/components/ui/Badge";
import { SectionCard } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { pct } from "@/lib/format";
import type { EdgeDevice } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Device list row (§5.7): icon tile, name, ID / last seen, model + load, status pill on the right. */
export function DeviceStatusList({ devices }: { devices: EdgeDevice[] }) {
  const { t, formatRelative } = useI18n();
  const online = devices.filter((d) => d.status === "online").length;
  return (
    <SectionCard
      title={t("dashboard.edgeDevices")}
      meta={`${devices.length} · ${t("dashboard.mOnline")} ${online} · ${t("status.offline")} ${devices.length - online}`}
    >
      <ul className="row-dashed max-h-[420px] overflow-y-auto">
        {devices.length === 0 && <li className="py-8 text-center text-[13px] text-muted">{t("dashboard.noDevices")}</li>}
        {devices.map((d) => (
          <li key={d.id} className="flex items-center gap-3 py-2.5">
            <span className="thumb-empty inline-flex h-10 w-14 shrink-0 items-center justify-center rounded-[10px] text-accent-hi">
              <Icon name="devices" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-bold text-ink">{d.name}</div>
              <div className="truncate text-xs text-muted">
                {d.device_uuid} · {d.site_name ?? t("common.noSite")} · {t("dashboard.seen", { time: formatRelative(d.last_seen) })}
              </div>
              <div className="truncate text-xs text-muted">
                {d.reported_models?.length ? `${d.reported_models.map((m) => m.name).join(", ")} · ` : ""}
                CPU {pct(d.cpu_usage)} · MEM {pct(d.memory_usage)}
                {d.gpu_usage != null && ` · GPU ${pct(d.gpu_usage)}`}
              </div>
            </div>
            <StatusBadge status={d.status} />
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
