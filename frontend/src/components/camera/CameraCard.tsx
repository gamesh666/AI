"use client";

import { CameraHealth } from "@/components/camera/CameraHealth";
import { LivePlayer } from "@/components/camera/LivePlayer";
import { Badge } from "@/components/ui/Badge";
import type { Camera } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function CameraCard({ camera }: { camera: Camera }) {
  const playable = camera.enabled && camera.stream_enabled && camera.annotated_stream_enabled;
  const { t } = useI18n();
  return (
    <div className="overflow-hidden rounded-lg border border-slate-700/60 bg-surface-800">
      {playable ? (
        <LivePlayer cameraId={camera.id} streamType="ai" />
      ) : (
        <div className="flex aspect-video items-center justify-center bg-black text-xs text-slate-500">
          {t("monitor.streamingDisabled")}
        </div>
      )}
      <div className="space-y-1.5 px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium" title={camera.name}>
            {camera.name} <span className="text-xs text-slate-500">({camera.code})</span>
          </span>
          <Badge tone={camera.ai_enabled ? "blue" : "gray"}>
            AI {camera.ai_enabled ? (camera.ai_model_name ?? t("monitor.aiOn")) : t("monitor.aiOff")}
          </Badge>
        </div>
        <div className="truncate text-xs text-slate-400">
          {camera.site_name ?? "—"} · {camera.edge_device_name ?? "—"}
        </div>
        <CameraHealth camera={camera} />
      </div>
    </div>
  );
}
