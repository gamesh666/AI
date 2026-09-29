import type { Camera, CameraStatusMessage } from "@/types";

/** Merge a realtime `camera.status` push into a camera row. */
export function applyCameraStatus(camera: Camera, msg: CameraStatusMessage): Camera {
  if (camera.id !== msg.camera_id) return camera;
  return {
    ...camera,
    status: msg.status,
    stream_status: msg.stream_status,
    ai_status: msg.ai_status,
    last_frame_at: msg.last_frame_at ?? camera.last_frame_at,
    runtime_stats: msg.runtime_stats ?? camera.runtime_stats,
  };
}
