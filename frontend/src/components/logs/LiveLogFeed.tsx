"use client";

import { useState } from "react";

import { SeverityBadge } from "@/components/logs/SeverityBadge";
import { SectionCard } from "@/components/ui/Card";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { describeLog, logSource, sourcePath } from "@/lib/logText";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { EdgeLog } from "@/types";

/** Event badge (§4): warning / error = bad, a "returned" / "resolved" update = ok, info = default amber. */
function badgeState(l: EdgeLog): string | undefined {
  if (l.status === "returned" || l.status === "resolved" || l.status === "online") return "ok";
  if (l.severity === "error" || l.severity === "critical") return "bad";
  if (l.severity === "debug") return "idle";
  return undefined;
}

/** Latest logs from every edge, pushed over WebSocket (updates replace the row in place). */
export function LiveLogFeed({ limit = 20 }: { limit?: number }) {
  const { t, formatDateTime, formatDuration } = useI18n();
  const [logs, setLogs] = useState<EdgeLog[]>([]);

  useRealtime<EdgeLog>("log.created", (log) => setLogs((prev) => [log, ...prev].slice(0, limit)));
  useRealtime<EdgeLog>("log.updated", (log) =>
    setLogs((prev) => (prev.some((l) => l.id === log.id) ? prev.map((l) => (l.id === log.id ? log : l)) : prev)),
  );

  return (
    <SectionCard title={t("logs.live")} meta={t("dashboard.realtime")}>
      <ul className="row-dashed max-h-[420px] overflow-y-auto">
        {logs.length === 0 && <li className="py-8 text-center text-[13px] text-muted">{t("dashboard.waiting")}</li>}
        {logs.map((l) => {
          const d = new Date(l.occurred_at);
          return (
            <li key={l.id} className="flex items-center gap-3 py-2">
              <span className="event-badge" data-state={badgeState(l)}>
                <span>{String(d.getMonth() + 1).padStart(2, "0")}</span>
                <span className="mt-0.5">{String(d.getDate()).padStart(2, "0")}</span>
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] text-ink">
                  <code className="text-xs text-accent-hi">{l.event_type}</code>
                  {l.status && <span className="ml-1 text-xs text-muted">[{l.status}]</span>}{" "}
                  {describeLog(l, t, formatDuration)}
                </div>
                <div className="truncate text-xs text-muted">
                  {l.edge_device_id
                    ? sourcePath(l.site_name, l.edge_device_name ?? l.edge_device_uuid, l.camera_name ?? l.camera_code)
                    : logSource(l, t).primary}{" "}
                  · {formatDateTime(l.occurred_at)}
                </div>
              </div>
              <SeverityBadge severity={l.severity} />
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
}
