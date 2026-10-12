"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Input } from "@/components/ui/Field";
import { useAsync } from "@/hooks/useAsync";
import { modelsApi } from "@/lib/api/models";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { ModelUsage } from "@/types";

/** What each edge reports running right now: which model, which version, on which edge and cameras. */
export function ModelsInUse() {
  const { t, formatRelative } = useI18n();
  const data = useAsync(modelsApi.inUse);
  const [q, setQ] = useState("");

  // heartbeats carry the model list: refresh at most every 15 s while the page is open
  const [last, setLast] = useState(0);
  useRealtime("device.heartbeat", () => {
    if (Date.now() - last > 15_000) {
      setLast(Date.now());
      data.reload();
    }
  });

  const models = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const all = data.data?.models ?? [];
    if (!needle) return all;
    return all.filter(
      (m) =>
        `${m.name} ${m.version ?? ""} ${m.type ?? ""} ${m.task ?? ""}`.toLowerCase().includes(needle) ||
        m.devices.some(
          (d) =>
            `${d.device_name} ${d.device_uuid} ${d.site_name ?? ""}`.toLowerCase().includes(needle) ||
            d.cameras.some((c) => `${c.code} ${c.name ?? ""}`.toLowerCase().includes(needle)),
        ),
    );
  }, [data.data, q]);

  const silent = data.data?.not_reporting ?? [];
  const deviceCount = new Set((data.data?.models ?? []).flatMap((m) => m.devices.map((d) => d.device_id))).size;

  return (
    <div className="space-y-4">
      <ErrorBanner error={data.error} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-400">
          {t("models.inUseSummary", { models: data.data?.models.length ?? 0, devices: deviceCount })}
        </p>
        <Input className="!w-64" placeholder={t("models.searchHint")} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {data.loading && !data.data && <p className="text-sm text-slate-500">{t("common.loading")}</p>}
      {data.data && models.length === 0 && (
        <Card className="text-center text-sm text-slate-500">{t("models.noneReported")}</Card>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        {models.map((m) => (
          <ModelCard key={`${m.name}|${m.version ?? ""}`} model={m} formatRelative={formatRelative} />
        ))}
      </div>

      {silent.length > 0 && (
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-slate-300">{t("models.notReporting", { n: silent.length })}</h3>
          <p className="mb-3 text-xs text-slate-500">{t("models.notReportingHint")}</p>
          <div className="flex flex-wrap gap-2">
            {silent.map((d) => (
              <span key={d.device_id} className="inline-flex items-center gap-1.5 rounded bg-surface-700 px-2 py-1 text-xs">
                {d.device_name} <span className="text-slate-500">{d.device_uuid}</span>
                <StatusBadge status={d.status} />
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function ModelCard({ model: m, formatRelative }: { model: ModelUsage; formatRelative: (iso: string | null) => string }) {
  const { t } = useI18n();
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold text-white">{m.name}</span>
            {m.version && <Badge tone="blue">{m.version}</Badge>}
            {m.type && <Badge>{m.type}</Badge>}
          </div>
          {m.task && <div className="mt-0.5 text-sm text-slate-400">{m.task}</div>}
        </div>
        <div className="text-right text-xs text-slate-400">
          {t("models.usage", { devices: m.devices.length, cameras: m.camera_count })}
        </div>
      </div>

      {m.other_versions.length > 0 && (
        <div className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-200">
          {t("models.otherVersions", { versions: m.other_versions.join(", ") })}
        </div>
      )}

      <ul className="divide-y divide-slate-800 rounded border border-slate-700/60">
        {m.devices.map((d) => (
          <li key={d.device_id} className="space-y-1 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link href="/devices" className="text-sm font-medium hover:underline">
                {d.device_name} <span className="text-xs text-slate-500">{d.device_uuid}</span>
              </Link>
              <span className="flex items-center gap-2 text-xs text-slate-500">
                {d.site_name ?? t("common.noSite")} · {t("models.reported", { time: formatRelative(d.reported_at) })}
                <StatusBadge status={d.status} />
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {d.cameras.length === 0 && <span className="text-xs text-slate-500">{t("models.allCameras")}</span>}
              {d.cameras.map((c) => (
                <span
                  key={c.code}
                  className="rounded bg-surface-700 px-1.5 py-0.5 text-xs text-slate-200"
                  title={c.camera_id ? c.code : t("models.unknownCamera")}
                >
                  {c.name ?? c.code}
                  {!c.camera_id && " ⚠"}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>

      {m.labels.length > 0 && (
        <div className="text-xs text-slate-500" title={m.labels.join(", ")}>
          {t("models.labels")}: {m.labels.slice(0, 12).join(", ")}
          {m.labels.length > 12 && ` +${m.labels.length - 12}`}
        </div>
      )}
    </Card>
  );
}
