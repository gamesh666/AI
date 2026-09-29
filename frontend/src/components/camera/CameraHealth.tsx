import { StatusBadge } from "@/components/ui/Badge";
import type { Camera } from "@/types";

/** RTSP input / AI / annotated stream status + measured FPS as reported by the edge. */
export function CameraHealth({ camera, compact = false }: { camera: Camera; compact?: boolean }) {
  const deviceOnline = camera.edge_device_status === "online";
  const r = camera.runtime_stats ?? {};
  const fps = (v?: number) => (v === undefined ? "—" : v.toFixed(0));
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
      <StatusBadge status={deviceOnline ? camera.status : "offline"} label="RTSP" />
      <StatusBadge status={camera.ai_enabled ? (deviceOnline ? camera.ai_status : "offline") : "disabled"} label="AI" />
      <StatusBadge status={deviceOnline ? camera.stream_status : "offline"} label="Stream" />
      {!compact && deviceOnline && (
        <span className="tabular-nums" title="input / inference / output fps">
          {fps(r.input_fps)}/{fps(r.inference_fps)}/{fps(r.output_fps)} fps
          {r.resolution ? ` · ${r.resolution}` : ""}
        </span>
      )}
    </div>
  );
}
