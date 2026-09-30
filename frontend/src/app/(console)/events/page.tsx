"use client";

import { useState } from "react";

import { EMPTY_FILTERS, EventFilters, type EventFilterValues } from "@/components/events/EventFilters";
import { EventTable } from "@/components/events/EventTable";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Checkbox } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { camerasApi } from "@/lib/api/cameras";
import { devicesApi } from "@/lib/api/devices";
import { eventsApi, type EventQuery } from "@/lib/api/events";
import { sitesApi } from "@/lib/api/sites";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { DetectionEvent } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const PAGE_SIZE = 50;

function toQuery(f: EventFilterValues, page: number): EventQuery {
  const q: EventQuery = { page, page_size: PAGE_SIZE };
  if (f.start) q.start = new Date(`${f.start}T00:00:00`).toISOString();
  if (f.end) {
    const end = new Date(`${f.end}T00:00:00`);
    end.setDate(end.getDate() + 1); // inclusive end date
    q.end = end.toISOString();
  }
  if (f.site_id) q.site_id = f.site_id;
  if (f.camera_id) q.camera_id = f.camera_id;
  if (f.edge_device_id) q.edge_device_id = f.edge_device_id;
  if (f.class_name) q.class_name = f.class_name;
  if (f.min_confidence) q.min_confidence = Number(f.min_confidence) / 100;
  return q;
}

function matches(ev: DetectionEvent, f: EventFilterValues): boolean {
  return (
    !f.end &&
    (!f.site_id || ev.site_id === f.site_id) &&
    (!f.camera_id || ev.camera_id === f.camera_id) &&
    (!f.edge_device_id || ev.edge_device_id === f.edge_device_id) &&
    (!f.class_name || ev.class_name === f.class_name) &&
    (!f.min_confidence || ev.confidence * 100 >= Number(f.min_confidence))
  );
}

export default function EventsPage() {
  const { t } = useI18n();
  const [filters, setFilters] = useState<EventFilterValues>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [live, setLive] = useState(true);

  const sites = useAsync(async () => (await sitesApi.list()).items);
  const devices = useAsync(async () => (await devicesApi.list()).items);
  const cameras = useAsync(async () => (await camerasApi.list()).items);
  const classes = useAsync(eventsApi.classes);
  const events = useAsync(() => eventsApi.list(toQuery(filters, page)), [filters, page]);

  // realtime: prepend new matching events on the first page
  useRealtime<DetectionEvent>("detection.created", (ev) => {
    if (!live || page !== 1 || !matches(ev, filters)) return;
    events.setData((prev) =>
      prev ? { ...prev, total: prev.total + 1, items: [ev, ...prev.items].slice(0, PAGE_SIZE) } : prev,
    );
  });

  const total = events.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title={t("nav.events")}
        subtitle={t("events.subtitle", { n: total })}
        actions={<Checkbox label={t("events.liveUpdates")} checked={live} onChange={(e) => setLive(e.target.checked)} />}
      />
      <EventFilters
        value={filters}
        onChange={(v) => (setFilters(v), setPage(1))}
        onReset={() => (setFilters(EMPTY_FILTERS), setPage(1))}
        sites={sites.data ?? []}
        devices={devices.data ?? []}
        cameras={cameras.data ?? []}
        classes={classes.data ?? []}
      />
      <ErrorBanner error={events.error} />
      <EventTable events={events.data?.items ?? []} loading={events.loading} />
      <div className="mt-4 flex items-center justify-center gap-3 text-sm">
        <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          {t("common.prev")}
        </Button>
        <span className="text-slate-400">
          {t("common.page", { page, pages })}
        </span>
        <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>
          {t("common.next")}
        </Button>
      </div>
    </>
  );
}
