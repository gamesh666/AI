"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { EMPTY_LOG_FILTERS, LogFilters, type LogFilterValues } from "@/components/logs/LogFilters";
import { LogTable } from "@/components/logs/LogTable";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Checkbox } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { camerasApi } from "@/lib/api/cameras";
import { devicesApi } from "@/lib/api/devices";
import { logsApi, type LogQuery } from "@/lib/api/logs";
import { sitesApi } from "@/lib/api/sites";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { EdgeLog } from "@/types";

const PAGE_SIZE = 50;

function toQuery(f: LogFilterValues, page: number): LogQuery {
  const q: LogQuery = { page, page_size: PAGE_SIZE };
  if (f.start) q.start = new Date(`${f.start}T00:00:00`).toISOString();
  if (f.end) {
    const end = new Date(`${f.end}T00:00:00`);
    end.setDate(end.getDate() + 1); // inclusive end date
    q.end = end.toISOString();
  }
  for (const k of ["site_id", "edge_device_id", "camera_id", "event_type", "severity", "q"] as const) {
    if (f[k]) q[k] = f[k];
  }
  return q;
}

function matches(l: EdgeLog, f: LogFilterValues): boolean {
  return (
    !f.end &&
    !f.q &&
    (!f.site_id || l.site_id === f.site_id) &&
    (!f.edge_device_id || l.edge_device_id === f.edge_device_id) &&
    (!f.camera_id || l.camera_id === f.camera_id) &&
    (!f.event_type || l.event_type === f.event_type) &&
    (!f.severity || l.severity === f.severity)
  );
}

function filtersFrom(params: URLSearchParams): LogFilterValues {
  const initial = { ...EMPTY_LOG_FILTERS };
  for (const k of Object.keys(initial) as (keyof LogFilterValues)[]) {
    initial[k] = params.get(k) ?? "";
  }
  return initial;
}

export default function LogsPage() {
  // useSearchParams needs a Suspense boundary when the route is prerendered
  return (
    <Suspense>
      <LogsView />
    </Suspense>
  );
}

function LogsView() {
  const searchParams = useSearchParams();
  const { t } = useI18n();
  // deep links, e.g. /logs?edge_device_id=...&event_type=system.connection from the devices page
  const [filters, setFilters] = useState<LogFilterValues>(() => filtersFrom(searchParams));
  const [query, setQuery] = useState<LogFilterValues>(filters);
  const [page, setPage] = useState(1);
  const [live, setLive] = useState(true);

  // debounce typing in the search box
  useEffect(() => {
    const timer = setTimeout(() => setQuery(filters), filters.q === query.q ? 0 : 400);
    return () => clearTimeout(timer);
  }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const sites = useAsync(async () => (await sitesApi.list()).items);
  const devices = useAsync(async () => (await devicesApi.list()).items);
  const cameras = useAsync(async () => (await camerasApi.list()).items);
  const types = useAsync(logsApi.types);
  const logs = useAsync(() => logsApi.list(toQuery(query, page)), [query, page]);

  useRealtime<EdgeLog>("log.created", (log) => {
    if (!types.data?.includes(log.event_type)) types.reload();
    if (!live || page !== 1 || !matches(log, query)) return;
    logs.setData((prev) =>
      prev ? { ...prev, total: prev.total + 1, items: [log, ...prev.items].slice(0, PAGE_SIZE) } : prev,
    );
  });
  useRealtime<EdgeLog>("log.updated", (log) => {
    if (!live) return;
    logs.setData((prev) =>
      prev ? { ...prev, items: prev.items.map((l) => (l.id === log.id ? log : l)) } : prev,
    );
  });

  const total = logs.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const change = (v: LogFilterValues) => (setFilters(v), setPage(1));

  return (
    <>
      <PageHeader
        title={t("nav.logs")}
        subtitle={t("logs.subtitle", { n: total })}
        actions={<Checkbox label={t("events.liveUpdates")} checked={live} onChange={(e) => setLive(e.target.checked)} />}
      />
      <LogFilters
        value={filters}
        onChange={change}
        onReset={() => change(EMPTY_LOG_FILTERS)}
        sites={sites.data ?? []}
        devices={devices.data ?? []}
        cameras={cameras.data ?? []}
        types={types.data ?? []}
      />
      <ErrorBanner error={logs.error} />
      <LogTable logs={logs.data?.items ?? []} loading={logs.loading} />
      <div className="mt-4 flex items-center justify-center gap-3 text-sm">
        <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          {t("common.prev")}
        </Button>
        <span className="text-slate-400">{t("common.page", { page, pages })}</span>
        <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>
          {t("common.next")}
        </Button>
      </div>
    </>
  );
}
