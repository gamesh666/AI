"use client";

import { useRef } from "react";

import { StatCard } from "@/components/dashboard/StatCard";
import { DeviceStatusList } from "@/components/devices/DeviceStatusList";
import { LiveEventFeed } from "@/components/events/LiveEventFeed";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useLiveDevices } from "@/hooks/useLiveDevices";
import { dashboardApi } from "@/lib/api/dashboard";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { DashboardSummary } from "@/types";

export default function DashboardPage() {
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

  const s = summary.data;
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Platform overview — updates in real time" />
      <ErrorBanner error={summary.error ?? devices.error} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Online edge devices" value={s?.online_devices} tone="good" />
        <StatCard
          label="Offline edge devices"
          value={s?.offline_devices}
          tone={s?.offline_devices ? "bad" : "default"}
          hint={s?.pending_devices ? `${s.pending_devices} pending` : undefined}
        />
        <StatCard label="Cameras" value={s?.camera_count} />
        <StatCard label="Active cameras" value={s?.active_camera_count} tone="info" />
        <StatCard label="Detections today" value={s?.events_today} tone="info" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <DeviceStatusList devices={devices.data ?? []} />
        <LiveEventFeed />
      </div>
    </>
  );
}
