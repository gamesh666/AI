"use client";

import { useRef } from "react";

import { CorePanels } from "@/components/dashboard/CorePanels";
import { StatCard } from "@/components/dashboard/StatCard";
import { DeviceStatusList } from "@/components/devices/DeviceStatusList";
import { LiveLogFeed } from "@/components/logs/LiveLogFeed";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useAsync } from "@/hooks/useAsync";
import { useLiveDevices } from "@/hooks/useLiveDevices";
import { API_BASE } from "@/lib/config";
import { dashboardApi } from "@/lib/api/dashboard";
import { devicesApi } from "@/lib/api/devices";
import { sitesApi } from "@/lib/api/sites";
import { useRealtime, useRealtimeStatus } from "@/lib/realtime/RealtimeProvider";
import type { DashboardSummary, EdgeLog } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

function HeroFact({ icon, label, value }: { icon: IconName; label: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="hero-fact-ic">
        <Icon name={icon} />
      </span>
      <div className="min-w-0">
        <div className="text-[11px] text-muted">{label}</div>
        <div className="truncate text-sm font-semibold text-ink">{value}</div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
  const summary = useAsync(dashboardApi.summary);
  const devices = useLiveDevices();
  const sites = useAsync(async () => (await sitesApi.list()).total);
  const flags = useAsync(() => devicesApi.telemetrySettings());
  const connected = useRealtimeStatus();
  const reloadTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // counts that depend on joins are re-fetched (debounced) when state changes are pushed
  const scheduleReload = () => {
    clearTimeout(reloadTimer.current);
    reloadTimer.current = setTimeout(summary.reload, 1000);
  };
  useRealtime("device.status", scheduleReload);
  useRealtime("camera.status", scheduleReload);
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
  const list = devices.data ?? [];
  const active = list.filter((d) => d.admin_state === "active");
  const online = active.filter((d) => d.status === "online").length;
  const onlineRate = active.length ? Math.round((online / active.length) * 100) : null;
  const onHttp = active.filter((d) => d.telemetry_transport === "http").length;
  const camPct = s && s.camera_count ? (s.active_camera_count / s.camera_count) * 100 : 0;
  const camState = !s || !s.camera_count ? undefined : camPct === 100 ? "ok" : camPct === 0 ? "bad" : "warn";

  return (
    <div className="space-y-4">
      <ErrorBanner error={summary.error ?? devices.error} />

      <section className="hero">
        <div className="relative flex flex-col justify-between gap-5 p-6">
          <div>
            <h1>{t("nav.dashboard")}</h1>
            <p className="m-0 mt-1.5 text-sm text-ink2">{t("dashboard.heroLead")}</p>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <HeroFact icon="sites" label={t("dashboard.factSites")} value={sites.data ?? "--"} />
            <HeroFact icon="devices" label={t("dashboard.factDevices")} value={active.length} />
            <HeroFact icon="online" label={t("dashboard.factOnlineRate")} value={onlineRate == null ? "--" : `${onlineRate}%`} />
            <HeroFact icon="link" label={t("dashboard.factHttp")} value={`${onHttp} / ${active.length}`} />
          </div>
        </div>
        <div className="hero-card text-[13px]">
          <div className="mb-2 font-bold text-ink">{t("dashboard.platform")}</div>
          <dl className="m-0 space-y-1.5">
            <div className="flex justify-between gap-2">
              <dt className="text-muted">{t("dashboard.platformApi")}</dt>
              <dd className="m-0 truncate font-semibold text-ink" title={API_BASE}>{API_BASE.replace(/^https?:\/\//, "")}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted">{t("dashboard.platformRealtime")}</dt>
              <dd className="m-0">
                <span className="svc-pill" data-state={connected ? "ok" : "warn"}>
                  <span className="state-dot" />
                  {connected ? t("topbar.live") : t("topbar.reconnecting")}
                </span>
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted">{t("dashboard.platformMqtt")}</dt>
              <dd className="m-0">
                {flags.data ? (
                  <span className={flags.data.mqtt_edge_enabled ? "hint-pill" : "svc-pill"} data-state="ok">
                    {t(flags.data.mqtt_edge_enabled ? "dashboard.mqttOn" : "dashboard.mqttOff")}
                  </span>
                ) : (
                  "--"
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="kpis">
        <StatCard icon="online" color="green" label={t("dashboard.onlineDevices")} value={s?.online_devices} />
        <StatCard
          icon="offline"
          color="red"
          label={t("dashboard.offlineDevices")}
          value={s?.offline_devices}
          small={s?.pending_devices ? t("dashboard.pending", { n: s.pending_devices }) : undefined}
        />
        <StatCard icon="cameras" color="blue" label={t("common.cameras")} value={s?.camera_count} />
        <StatCard
          icon="cameras"
          label={t("dashboard.activeCameras")}
          value={s ? `${s.active_camera_count}/${s.camera_count}` : undefined}
          small={s && s.camera_count ? t("kpi.onlineRate", { p: Math.round(camPct) }) : undefined}
          ring={{ pct: camPct, state: camState }}
        />
        <StatCard icon="disconnect" color="orange" label={t("dashboard.disconnectsToday")} value={s?.disconnects_today} />
        <StatCard icon="logs" color="sky" label={t("dashboard.logsToday")} value={s?.logs_today} />
      </div>

      <CorePanels summary={s} devices={list} connected={connected} mqttEnabled={flags.data?.mqtt_edge_enabled ?? null} />

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(max(320px, 42%), 100%), 1fr))" }}>
        <DeviceStatusList devices={list} />
        <LiveLogFeed />
      </div>
    </div>
  );
}
