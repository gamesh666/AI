"use client";

import { StatusBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { pct } from "@/lib/format";
import type { EdgeDevice } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function DeviceStatusList({ devices }: { devices: EdgeDevice[] }) {
  const { t, formatRelative } = useI18n();
  return (
    <Card className="p-0">
      <div className="border-b border-slate-700/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">{t("dashboard.edgeDevices")}</h2>
      </div>
      <ul className="max-h-[420px] divide-y divide-slate-800 overflow-y-auto">
        {devices.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-500">{t("dashboard.noDevices")}</li>}
        {devices.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{d.name}</div>
              <div className="truncate text-xs text-slate-500">
                {d.site_name ?? t("common.noSite")} · {d.device_uuid} · {t("dashboard.seen", { time: formatRelative(d.last_seen) })}
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span title="CPU">CPU {pct(d.cpu_usage)}</span>
              <span title={t("devices.memory")}>MEM {pct(d.memory_usage)}</span>
              <span title="GPU">GPU {pct(d.gpu_usage)}</span>
              <StatusBadge status={d.status} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
