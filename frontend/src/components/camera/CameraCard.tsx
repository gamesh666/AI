"use client";

import { LivePlayer } from "@/components/camera/LivePlayer";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import type { Camera } from "@/types";

export function CameraCard({ camera }: { camera: Camera }) {
  const deviceOnline = camera.edge_device_status === "online";
  return (
    <div className="overflow-hidden rounded-lg border border-slate-700/60 bg-surface-800">
      <LivePlayer cameraId={camera.id} active={camera.enabled} />
      <div className="space-y-1 px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium" title={camera.name}>
            {camera.name}
          </span>
          <StatusBadge status={deviceOnline ? camera.status : "offline"} />
        </div>
        <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
          <span className="truncate">
            {camera.site_name ?? "—"} · {camera.edge_device_name ?? "—"}
          </span>
          <Badge tone={camera.ai_enabled ? "blue" : "gray"}>
            AI {camera.ai_enabled ? (camera.ai_model_name ?? "on") : "off"}
          </Badge>
        </div>
      </div>
    </div>
  );
}
