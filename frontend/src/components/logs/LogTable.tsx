"use client";

import { useState } from "react";

import { SeverityBadge } from "@/components/logs/SeverityBadge";
import { SnapshotWithBoxes } from "@/components/logs/SnapshotWithBoxes";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Modal } from "@/components/ui/Modal";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { describeLog, logSource } from "@/lib/logText";
import type { EdgeLog } from "@/types";

export function LogTable({ logs, loading }: { logs: EdgeLog[]; loading?: boolean }) {
  const { t, formatDateTime, formatDuration } = useI18n();
  const text = (l: EdgeLog) => describeLog(l, t, formatDuration);
  const [open, setOpen] = useState<EdgeLog | null>(null);
  const [viewing, setViewing] = useState<EdgeLog | null>(null);
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
          <code className="text-xs text-accent-hi">{l.event_type}</code>
          {l.status && <span className="ml-1.5 text-xs text-muted">[{l.status}]</span>}
        </span>
      ),
    },
    {
      key: "message",
      header: t("logs.message"),
      className: "max-w-md",
      render: (l) => (
        <button className="block max-w-md truncate text-left hover:underline" onClick={() => setOpen(l)}>
          {text(l) || <span className="text-muted">{t("logs.viewData")}</span>}
        </button>
      ),
    },
    {
      key: "source",
      header: t("logs.source"),
      render: (l) => {
        const src = logSource(l, t);
        return (
          <div>
            <div>{src.primary}</div>
            <div className="text-xs text-muted">{src.secondary}</div>
          </div>
        );
      },
    },
    {
      key: "snapshot",
      header: t("events.snapshot"),
      render: (l) =>
        l.snapshot_url ? (
          <button
            onClick={() => setViewing(l)}
            className="block overflow-hidden rounded-[10px] border border-line hover:border-accent"
            title={t("logs.viewSnapshot")}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={l.snapshot_url} alt="" className="block aspect-[16/10] w-32 object-cover" loading="lazy" />
          </button>
        ) : null,
    },
  ];

  return (
    <>
      <DataTable columns={columns} rows={logs} loading={loading} empty={t("logs.empty")} />
      <Modal
        open={!!viewing}
        wide="xl"
        title={viewing ? `${viewing.camera_name ?? viewing.camera_code ?? viewing.event_type} · ${formatDateTime(viewing.occurred_at)}` : ""}
        onClose={() => setViewing(null)}
      >
        {viewing && (
          <div className="space-y-2">
            <SnapshotWithBoxes log={viewing} height={480} />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
              <span className="truncate">
                <code className="text-accent-hi">{viewing.event_type}</code> {text(viewing)}
              </span>
              <span className="flex shrink-0 gap-3">
                <button className="hover:text-ink hover:underline" onClick={() => { setOpen(viewing); setViewing(null); }}>
                  {t("logs.details")}
                </button>
                <a className="hover:text-ink hover:underline" href={viewing.snapshot_url ?? "#"} target="_blank" rel="noreferrer">
                  {t("logs.openOriginal")}
                </a>
              </span>
            </div>
          </div>
        )}
      </Modal>
      <Modal open={!!current} title={current ? current.event_type : ""} onClose={() => setOpen(null)}>
        {current && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={current.severity} />
              {current.status && <span className="text-muted">[{current.status}]</span>}
              <span className="text-muted">{formatDateTime(current.occurred_at)}</span>
            </div>
            {text(current) && <p className="whitespace-pre-wrap">{text(current)}</p>}
            <SnapshotWithBoxes log={current} />
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
              <dt className="text-muted">{t("logs.eventId")}</dt>
              <dd className="break-all font-mono">{current.event_id}</dd>
              <dt className="text-muted">{t("common.edgeDevice")}</dt>
              <dd>{current.edge_device_id ? (current.edge_device_name ?? current.edge_device_uuid) : t("syslog.platform")}</dd>
              <dt className="text-muted">{t("common.camera")}</dt>
              <dd>{current.camera_name ?? current.camera_code ?? "--"}</dd>
              <dt className="text-muted">{t("logs.updated")}</dt>
              <dd>{formatDateTime(current.updated_at)}</dd>
            </dl>
            <pre className="max-h-80 overflow-auto rounded bg-panel2 p-2 text-xs text-ink2">
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
