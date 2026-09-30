"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { DetectionEvent } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Pure push: new detections arrive over WebSocket, no polling. */
export function LiveEventFeed({ limit = 20, cameraId }: { limit?: number; cameraId?: string }) {
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const { t, formatDateTime } = useI18n();

  useRealtime<DetectionEvent>("detection.created", (ev) => {
    if (cameraId && ev.camera_id !== cameraId) return;
    setEvents((prev) => [ev, ...prev].slice(0, limit));
  });

  return (
    <Card className="p-0">
      <div className="flex items-center justify-between border-b border-slate-700/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">{t("dashboard.liveDetections")}</h2>
        <span className="text-xs text-slate-500">{t("dashboard.realtime")}</span>
      </div>
      <ul className="max-h-[420px] divide-y divide-slate-800 overflow-y-auto">
        {events.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-500">{t("dashboard.waiting")}</li>}
        {events.map((ev) => (
          <li key={ev.id} className="flex items-center gap-3 px-4 py-2">
            {ev.snapshot_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={ev.snapshot_url} alt="" className="h-10 w-16 rounded object-cover" />
            ) : (
              <div className="h-10 w-16 rounded bg-surface-700" />
            )}
            <div className="min-w-0 flex-1">
              <div className="text-sm">
                <span className="font-medium text-brand-400">{ev.class_name}</span>{" "}
                <span className="text-slate-400">{(ev.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="truncate text-xs text-slate-500">
                {ev.camera_name} · {ev.site_name ?? "—"} · {formatDateTime(ev.detected_at)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
