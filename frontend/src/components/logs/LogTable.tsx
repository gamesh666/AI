"use client";

import { useState } from "react";

import { SeverityBadge } from "@/components/logs/SeverityBadge";
import { SnapshotWithBoxes } from "@/components/logs/SnapshotWithBoxes";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Modal } from "@/components/ui/Modal";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { EdgeLog } from "@/types";

export function LogTable({ logs, loading }: { logs: EdgeLog[]; loading?: boolean }) {
  const { t, formatDateTime } = useI18n();
  const [open, setOpen] = useState<EdgeLog | null>(null);
  // keep the dialog in sync when the open log is updated live
  const current = open ? (logs.find((l) => l.id === open.id) ?? open) : null;

  const columns: Column<EdgeLog>[] = [
    { key: "time", header: t("logs.time"), render: (l) => formatDateTime(l.occurred_at) },
    { key: "severity", header: t("logs.severity"), render: (l) => <SeverityBadge severity={l.severity} /> },
    {
      key: "type",
      header: t("logs.type"),
      render: (l) => (
        <span>
          <code className="text-xs text-brand-400">{l.event_type}</code>
          {l.status && <span className="ml-1.5 text-xs text-slate-400">[{l.status}]</span>}
        </span>
      ),
    },
    {
      key: "message",
      header: t("logs.message"),
      className: "max-w-md",
      render: (l) => (
        <button className="block max-w-md truncate text-left hover:underline" onClick={() => setOpen(l)}>
          {l.message || <span className="text-slate-500">{t("logs.viewData")}</span>}
        </button>
      ),
    },
    {
      key: "source",
      header: t("logs.source"),
      render: (l) => (
        <div>
          <div>{l.camera_name ?? l.camera_code ?? "—"}</div>
          <div className="text-xs text-slate-500">
            {l.site_name ?? "—"} · {l.edge_device_name ?? l.edge_device_uuid}
          </div>
        </div>
      ),
    },
    {
      key: "snapshot",
      header: t("events.snapshot"),
      render: (l) =>
        l.snapshot_url ? (
          <button onClick={() => setOpen(l)}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={l.snapshot_url} alt="" className="h-10 w-16 rounded object-cover" loading="lazy" />
          </button>
        ) : null,
    },
  ];

  return (
    <>
      <DataTable columns={columns} rows={logs} loading={loading} empty={t("logs.empty")} />
      <Modal open={!!current} title={current ? current.event_type : ""} onClose={() => setOpen(null)}>
        {current && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={current.severity} />
              {current.status && <span className="text-slate-400">[{current.status}]</span>}
              <span className="text-slate-400">{formatDateTime(current.occurred_at)}</span>
            </div>
            {current.message && <p className="whitespace-pre-wrap">{current.message}</p>}
            <SnapshotWithBoxes log={current} />
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
              <dt className="text-slate-500">{t("logs.eventId")}</dt>
              <dd className="break-all font-mono">{current.event_id}</dd>
              <dt className="text-slate-500">{t("common.edgeDevice")}</dt>
              <dd>{current.edge_device_name ?? current.edge_device_uuid}</dd>
              <dt className="text-slate-500">{t("common.camera")}</dt>
              <dd>{current.camera_name ?? current.camera_code ?? "—"}</dd>
              <dt className="text-slate-500">{t("logs.updated")}</dt>
              <dd>{formatDateTime(current.updated_at)}</dd>
            </dl>
            <pre className="max-h-80 overflow-auto rounded bg-surface-900 p-2 text-xs text-slate-300">
              {JSON.stringify(
                current.detections.length ? { data: current.data, detections: current.detections } : current.data,
                null,
                2,
              )}
            </pre>
          </div>
        )}
      </Modal>
    </>
  );
}
