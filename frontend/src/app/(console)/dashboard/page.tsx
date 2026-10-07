"use client";

import { useRef } from "react";

import { StatCard } from "@/components/dashboard/StatCard";
import { DeviceStatusList } from "@/components/devices/DeviceStatusList";
import { LiveEventFeed } from "@/components/events/LiveEventFeed";
import { LiveLogFeed } from "@/components/logs/LiveLogFeed";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useLiveDevices } from "@/hooks/useLiveDevices";
import { dashboardApi } from "@/lib/api/dashboard";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { DashboardSummary, EdgeLog } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function DashboardPage() {
  const { t } = useI18n();
  const summary = useAsync(dashboardApi.summary);
  const devices = useLiveDevices();
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // counts that depend on joins are re-fetched (debounced) when state changes are pushed
  const scheduleReload = () => {
    clearTimeout(reloadTimer.current);
    reloadTimer.current = setTimeout(summary.reload, 1000);
  };
  useRealtime("device.status", scheduleReload);
  useRealtime("camera.status", scheduleReload);
  useRealtime("detection.created", () =>
    summary.setData((s: DashboardSummary | null) => (s ? { ...s, events_today: s.events_today + 1 } : s)),
  );
  useRealtime<EdgeLog>("log.created", (log) =>
    summary.setData((s: DashboardSummary | null) =>
      s
        ? {
            ...s,
            logs_today: s.logs_today + 1,
            disconnects_today: s.disconnects_today + (log.event_type === "system.connection" ? 1 : 0),
          }
        : s,
    ),
  );

  const s = summary.data;
  return (
    <>
      <PageHeader title={t("nav.dashboard")} subtitle={t("dashboard.subtitle")} />
      <ErrorBanner error={summary.error ?? devices.error} />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-7">
        <StatCard label={t("dashboard.onlineDevices")} value={s?.online_devices} tone="good" />
        <StatCard
          label={t("dashboard.offlineDevices")}
          value={s?.offline_devices}
          tone={s?.offline_devices ? "bad" : "default"}
          hint={s?.pending_devices ? t("dashboard.pending", { n: s.pending_devices }) : undefined}
        />
        <StatCard label={t("common.cameras")} value={s?.camera_count} />
        <StatCard label={t("dashboard.activeCameras")} value={s?.active_camera_count} tone="info" />
        <StatCard
          label={t("dashboard.disconnectsToday")}
          value={s?.disconnects_today}
          tone={s?.disconnects_today ? "bad" : "default"}
        />
        <StatCard label={t("dashboard.logsToday")} value={s?.logs_today} tone="info" />
        <StatCard label={t("dashboard.detectionsToday")} value={s?.events_today} tone="info" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <DeviceStatusList devices={devices.data ?? []} />
        <LiveLogFeed />
        <LiveEventFeed />
      </div>
    </>
  );
}
