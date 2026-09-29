"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/ui/DataTable";
import { Modal } from "@/components/ui/Modal";
import { formatDateTime } from "@/lib/format";
import type { DetectionEvent } from "@/types";

export function EventTable({ events, loading }: { events: DetectionEvent[]; loading?: boolean }) {
  const [preview, setPreview] = useState<DetectionEvent | null>(null);

  const columns: Column<DetectionEvent>[] = [
    {
      key: "snapshot",
      header: "Snapshot",
      render: (e) =>
        e.snapshot_url ? (
          <button onClick={() => setPreview(e)}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={e.snapshot_url} alt={e.class_name} className="h-12 w-20 rounded object-cover" loading="lazy" />
          </button>
        ) : (
          <div className="h-12 w-20 rounded bg-surface-700" />
        ),
    },
    {
      key: "camera",
      header: "Camera",
      render: (e) => (
        <div>
          <div>{e.camera_name ?? e.camera_id}</div>
          <div className="text-xs text-slate-500">
            {e.site_name ?? "—"} · {e.edge_device_name ?? "—"}
          </div>
        </div>
      ),
    },
    { key: "class", header: "Detection class", render: (e) => <span className="font-medium text-brand-400">{e.class_name}</span> },
    {
      key: "confidence",
      header: "Confidence",
      render: (e) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 rounded bg-surface-600">
            <div className="h-1.5 rounded bg-brand-500" style={{ width: `${e.confidence * 100}%` }} />
          </div>
          <span className="tabular-nums">{(e.confidence * 100).toFixed(1)}%</span>
        </div>
      ),
    },
    { key: "time", header: "Detection time", render: (e) => formatDateTime(e.detected_at) },
  ];

  return (
    <>
      <DataTable columns={columns} rows={events} loading={loading} empty="No detection events match the filters" />
      <Modal open={!!preview} title={preview ? `${preview.class_name} · ${preview.camera_name}` : ""} onClose={() => setPreview(null)}>
        {preview?.snapshot_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview.snapshot_url} alt="" className="w-full rounded" />
        )}
        <pre className="mt-3 overflow-x-auto rounded bg-surface-900 p-2 text-xs text-slate-400">
          {JSON.stringify({ bbox: preview?.bbox, metadata: preview?.metadata }, null, 2)}
        </pre>
      </Modal>
    </>
  );
}
