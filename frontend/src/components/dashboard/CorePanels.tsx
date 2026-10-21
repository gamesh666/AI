"use client";

import clsx from "clsx";

import { Icon, type IconName } from "@/components/ui/Icon";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { MessageKey } from "@/lib/i18n/messages";
import type { DashboardSummary, EdgeDevice } from "@/types";

type State = "ok" | "warn" | "bad" | "idle";

interface Module {
  key: string;
  icon: IconName;
  title: MessageKey;
  state: State;
  metrics: [MessageKey, string | number][];
}

const STATE_KEY: Record<State, MessageKey> = { ok: "state.ok", warn: "state.warn", bad: "state.bad", idle: "state.idle" };

function avg(values: (number | null | undefined)[]): number | null {
  const v = values.filter((x): x is number => typeof x === "number");
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

function Gauge({ label, value, unit = "%", max = 100, warnAt }: {
  label: string; value: number | null; unit?: string; max?: number; warnAt: number;
}) {
  const state = value == null ? undefined : value >= warnAt ? "warn" : undefined;
  return (
    <div className="min-w-0 text-center">
      <div
        className="gauge"
        data-state={state}
        style={{ "--pct": value == null ? 0 : Math.min(100, (value / max) * 100) } as React.CSSProperties}
      >
        <span>{value == null ? "--" : `${value.toFixed(0)}${unit}`}</span>
      </div>
      <div className="core-muted mt-1.5 text-xs">{label}</div>
    </div>
  );
}

/** The two core panels (§5.5): system modules | compute of online edges. */
export function CorePanels({
  summary,
  devices,
  connected,
}: {
  summary: DashboardSummary | null;
  devices: EdgeDevice[];
  connected: boolean;
}) {
  const { t } = useI18n();
  const active = devices.filter((d) => d.admin_state === "active");
  const online = active.filter((d) => d.status === "online");
  const s = summary;

  const modules: Module[] = [
    {
      key: "devices", icon: "devices", title: "dashboard.modDevices",
      state: active.length === 0 ? "idle" : online.length === active.length ? "ok" : online.length === 0 ? "bad" : "warn",
      metrics: [["dashboard.mOnline", online.length], ["dashboard.mTotal", active.length]],
    },
    {
      key: "cameras", icon: "cameras", title: "dashboard.modCameras",
      state: !s || s.camera_count === 0 ? "idle" : s.active_camera_count === s.camera_count ? "ok" : s.active_camera_count === 0 ? "bad" : "warn",
      metrics: [["dashboard.mActive", s?.active_camera_count ?? "--"], ["dashboard.mTotal", s?.camera_count ?? "--"]],
    },
    {
      key: "realtime", icon: "pulse", title: "dashboard.modRealtime",
      state: connected ? "ok" : "warn",
      metrics: [["dashboard.mState", t(connected ? "state.ok" : "state.warn")], ["dashboard.mDevices", online.length]],
    },
    {
      key: "outages", icon: "disconnect", title: "dashboard.modOutages",
      state: !s ? "idle" : s.disconnects_today === 0 ? "ok" : "warn",
      metrics: [["dashboard.mToday", s?.disconnects_today ?? "--"], ["dashboard.mDevices", active.filter((d) => d.disconnects_24h > 0).length]],
    },
    {
      key: "logs", icon: "logs", title: "dashboard.modLogs",
      state: !s ? "idle" : "ok",
      metrics: [["dashboard.mToday", s?.logs_today ?? "--"], ["dashboard.mDevices", online.length]],
    },
  ];
  const warn = modules.filter((m) => m.state === "warn").length;
  const bad = modules.filter((m) => m.state === "bad").length;
  const overall: State = bad ? "bad" : warn ? "warn" : "ok";
  const overallText = bad ? t("dashboard.nBad", { n: bad }) : warn ? t("dashboard.nWarn", { n: warn }) : t("dashboard.allOk");

  const hottest = online.reduce<EdgeDevice | null>((a, d) => ((d.temperature ?? -1) > (a?.temperature ?? -1) ? d : a), null);
  const busiest = online.reduce<EdgeDevice | null>((a, d) => ((d.cpu_usage ?? -1) > (a?.cpu_usage ?? -1) ? d : a), null);
  const facts: [MessageKey, string][] = [
    ["dashboard.hottest", hottest?.temperature != null ? `${hottest.name} · ${hottest.temperature.toFixed(0)}°C` : "--"],
    ["dashboard.busiest", busiest?.cpu_usage != null ? `${busiest.name} · ${busiest.cpu_usage.toFixed(0)}%` : "--"],
    ["dashboard.gpus", `${online.filter((d) => d.gpu_name).length} / ${online.length}`],
    ["dashboard.agents", String(new Set(online.map((d) => d.agent_version).filter(Boolean)).size || "--")],
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="core-panel glow p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3>{t("dashboard.systemStatus")}</h3>
          <span className="pill" data-state={overall}>
            <span className="state-dot" />
            {overallText}
          </span>
        </div>
        <div className="bus-mods">
          {modules.map((m) => (
            <div key={m.key} className="bus-mod" data-state={m.state}>
              <div className="flex items-center gap-2">
                <span className="mod-ic">
                  <Icon name={m.icon} size={22} />
                </span>
                <span className="min-w-0 flex-1 truncate text-[15px] font-bold">{t(m.title)}</span>
                <span className="pill shrink-0 !border-0 !bg-transparent !px-0" data-state={m.state}>
                  <span className="state-dot" />
                  {t(STATE_KEY[m.state])}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-2 text-center">
                {m.metrics.map(([k, v], i) => (
                  <div key={k + i} className={clsx("min-w-0", i === 1 && "border-l")} style={{ borderColor: "var(--mod-line)" }}>
                    <div className="mod-num truncate">{v}</div>
                    <div className="core-muted text-xs">{t(k)}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="core-panel p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3>{t("dashboard.compute")}</h3>
          <span className="core-muted text-xs">{t("dashboard.computeMeta", { n: online.length })}</span>
        </div>
        <div className="gauges">
          <Gauge label="CPU" value={avg(online.map((d) => d.cpu_usage))} warnAt={85} />
          <Gauge label="GPU" value={avg(online.map((d) => d.gpu_usage))} warnAt={90} />
          <Gauge label={t("dashboard.memory")} value={avg(online.map((d) => d.memory_usage))} warnAt={85} />
          <Gauge label={t("dashboard.temperature")} value={avg(online.map((d) => d.temperature))} unit="°" warnAt={80} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2.5 md:grid-cols-4">
          {facts.map(([k, v]) => (
            <div key={k} className="hw-fact">
              <div className="k">{t(k)}</div>
              <div className="v" title={v}>{v}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
