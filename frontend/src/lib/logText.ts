import type { MessageKey } from "@/lib/i18n/messages";
import type { EdgeLog } from "@/types";

type T = (key: MessageKey, vars?: Record<string, string | number>) => string;

/** Human text for records the platform writes itself (system.*); edge logs use their own message. */
export function describeLog(log: EdgeLog, t: T, duration: (s: number) => string): string | null {
  const d = log.data as Record<string, unknown>;
  const secs = typeof d.duration_seconds === "number" ? d.duration_seconds : null;
  if (log.event_type === "system.connection") {
    if (log.status === "recovered") return t("syslog.recovered", { d: secs !== null ? duration(secs) : "—" });
    return t(d.reason === "heartbeat_timeout" ? "syslog.offlineTimeout" : "syslog.offlineReported");
  }
  if (log.event_type === "system.platform") {
    if (log.status === "stopped") return t("syslog.platformStopped");
    const down = typeof d.downtime_seconds === "number" ? duration(d.downtime_seconds) : null;
    const base = d.unclean_shutdown ? t("syslog.platformStartedUnclean") : t("syslog.platformStarted");
    return down ? `${base} ${t("syslog.downtime", { d: down })}` : base;
  }
  return log.message;
}

/** Device / camera shown for a log; platform-level records have no device. */
export function logSource(log: EdgeLog, t: T): { primary: string; secondary: string } {
  if (!log.edge_device_id) return { primary: t("syslog.platform"), secondary: "—" };
  return {
    primary: log.camera_name ?? log.camera_code ?? log.edge_device_name ?? log.edge_device_uuid ?? "—",
    secondary: `${log.site_name ?? "—"} · ${log.edge_device_name ?? log.edge_device_uuid}`,
  };
}
