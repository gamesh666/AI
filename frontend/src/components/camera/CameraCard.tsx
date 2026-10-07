"use client";

import clsx from "clsx";

import { LivePlayer } from "@/components/camera/LivePlayer";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { Camera } from "@/types";

const DOT: Record<string, string> = {
  online: "bg-emerald-400",
  streaming: "bg-emerald-400",
  running: "bg-emerald-400",
  connecting: "bg-amber-400",
  loading: "bg-amber-400",
  offline: "bg-red-400",
  error: "bg-red-400",
};

function Dot({ status, label }: { status: string; label: string }) {
  const { tEnum } = useI18n();
  return (
    <span className="inline-flex items-center gap-1" title={`${label}: ${tEnum("status", status)}`}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", DOT[status] ?? "bg-slate-500")} />
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
}

/** One tile = the whole video; name and health are overlaid so the picture uses all the space. */
export function CameraCard({ camera }: { camera: Camera }) {
  const { t } = useI18n();
  const playable = camera.enabled && camera.stream_enabled && camera.annotated_stream_enabled;
  const deviceOnline = camera.edge_device_status === "online";
  const r = camera.runtime_stats ?? {};
  return (
    <div className="relative min-h-0 min-w-0 overflow-hidden rounded-md border border-slate-700/60 bg-black">
      {playable ? (
        <LivePlayer cameraId={camera.id} streamType="ai" fill />
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-slate-500">
          {t("monitor.streamingDisabled")}
        </div>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent px-2 pb-1.5 pt-5">
        <div className="flex items-end justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-xs font-medium text-white sm:text-sm" title={camera.name}>
              {camera.name}
            </div>
            <div className="hidden truncate text-[11px] text-slate-300 sm:block">
              {camera.site_name ?? "—"} · {camera.edge_device_name ?? "—"}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 text-[10px] text-slate-200">
            <Dot status={deviceOnline ? camera.status : "offline"} label="RTSP" />
            <Dot status={camera.ai_enabled ? (deviceOnline ? camera.ai_status : "offline") : "disabled"} label="AI" />
            <Dot status={deviceOnline ? camera.stream_status : "offline"} label={t("health.stream")} />
            {deviceOnline && r.output_fps !== undefined && (
              <span className="hidden tabular-nums md:inline">{r.output_fps.toFixed(0)} fps</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
