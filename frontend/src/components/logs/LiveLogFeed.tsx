"use client";

import { useState } from "react";

import { SeverityBadge } from "@/components/logs/SeverityBadge";
import { Card } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { EdgeLog } from "@/types";

/** Latest logs from every edge, pushed over WebSocket (updates replace the row in place). */
export function LiveLogFeed({ limit = 20 }: { limit?: number }) {
  const { t, formatDateTime } = useI18n();
  const [logs, setLogs] = useState<EdgeLog[]>([]);

  useRealtime<EdgeLog>("log.created", (log) => setLogs((prev) => [log, ...prev].slice(0, limit)));
  useRealtime<EdgeLog>("log.updated", (log) =>
    setLogs((prev) => (prev.some((l) => l.id === log.id) ? prev.map((l) => (l.id === log.id ? log : l)) : prev)),
  );

  return (
    <Card className="p-0">
      <div className="flex items-center justify-between border-b border-slate-700/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">{t("logs.live")}</h2>
        <span className="text-xs text-slate-500">{t("dashboard.realtime")}</span>
      </div>
      <ul className="max-h-[420px] divide-y divide-slate-800 overflow-y-auto">
        {logs.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-500">{t("dashboard.waiting")}</li>}
        {logs.map((l) => (
          <li key={l.id} className="flex items-center gap-3 px-4 py-2">
            <SeverityBadge severity={l.severity} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">
                <code className="text-xs text-brand-400">{l.event_type}</code>
                {l.status && <span className="ml-1 text-xs text-slate-400">[{l.status}]</span>}{" "}
                {l.message}
              </div>
              <div className="truncate text-xs text-slate-500">
                {l.camera_name ?? l.camera_code ?? "—"} · {l.edge_device_name ?? l.edge_device_uuid} ·{" "}
                {formatDateTime(l.occurred_at)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
