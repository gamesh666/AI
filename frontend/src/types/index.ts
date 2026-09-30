// Mirrors backend Pydantic schemas (backend/app/schemas)

export type UUID = string;
export type Role = "admin" | "operator" | "viewer";
export type DeviceStatus = "pending" | "online" | "offline";
export type CameraStatus = "unknown" | "connecting" | "online" | "offline" | "error";
export type StreamStatus = "offline" | "connecting" | "streaming" | "error";
export type AiStatus = "idle" | "disabled" | "loading" | "running" | "error";
export type StreamType = "ai" | "original";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: UUID;
  username: string;
  email: string | null;
  full_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface Site {
  id: UUID;
  name: string;
  code: string;
  address: string | null;
  description: string | null;
  created_at: string;
  device_count: number;
}

export interface EdgeDevice {
  id: UUID;
  device_uuid: string;
  name: string;
  site_id: UUID | null;
  site_name: string | null;
  hostname: string | null;
  ip_address: string | null;
  status: DeviceStatus;
  last_seen: string | null;
  agent_version: string | null;
  gpu_name: string | null;
  gpu_memory: number | null;
  cpu_usage: number | null;
  memory_usage: number | null;
  gpu_usage: number | null;
  gpu_memory_usage: number | null;
  temperature: number | null;
  camera_count: number;
  created_at: string;
}

export interface EdgeDeviceWithKey extends EdgeDevice {
  api_key: string;
}

export interface CameraRuntimeStats {
  input_fps?: number;
  inference_fps?: number;
  output_fps?: number;
  resolution?: string | null;
  dropped_frames?: number;
  error?: string | null;
  reported_at?: string;
}

/** No camera address / RTSP URL / credentials ever reach the browser. */
export interface Camera {
  id: UUID;
  code: string;
  edge_device_id: UUID;
  edge_device_uuid: string | null;
  edge_device_name: string | null;
  edge_device_status: DeviceStatus | null;
  site_id: UUID | null;
  site_code: string | null;
  site_name: string | null;
  name: string;
  source_configured: boolean;
  has_credentials: boolean;
  enabled: boolean;
  ai_enabled: boolean;
  stream_enabled: boolean;
  annotated_stream_enabled: boolean;
  original_stream_enabled: boolean;
  ai_model_id: UUID | null;
  ai_model_name: string | null;
  stream_path: string;
  resolution: string | null;
  stream_fps: number;
  inference_fps: number;
  bitrate: string;
  gop_size: number;
  status: CameraStatus;
  stream_status: StreamStatus;
  ai_status: AiStatus;
  last_frame_at: string | null;
  runtime_stats: CameraRuntimeStats;
  created_at: string;
}

export interface AIModel {
  id: UUID;
  name: string;
  version: string;
  model_type: string;
  labels: string[];
  model_path: string;
  description: string | null;
  created_at: string;
}

export interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface DetectionEvent {
  id: UUID;
  event_group_id: UUID;
  camera_id: UUID;
  camera_name: string | null;
  edge_device_id: UUID;
  edge_device_name: string | null;
  site_id: UUID | null;
  site_name: string | null;
  ai_model_id: UUID | null;
  ai_model_name: string | null;
  track_id: number | null;
  class_name: string;
  confidence: number;
  bbox: BBox;
  detected_at: string;
  snapshot_url: string | null;
  metadata: Record<string, unknown>;
}

export interface DashboardSummary {
  online_devices: number;
  offline_devices: number;
  pending_devices: number;
  camera_count: number;
  active_camera_count: number;
  events_today: number;
  logs_today: number;
}

export type LogSeverity = "debug" | "info" | "warning" | "error" | "critical";

/** Anything an edge reports. The platform does not interpret event_type / data. */
export interface EdgeLog {
  id: UUID;
  event_id: string;
  edge_device_id: UUID;
  edge_device_uuid: string | null;
  edge_device_name: string | null;
  site_id: UUID | null;
  site_name: string | null;
  camera_id: UUID | null;
  camera_code: string | null;
  camera_name: string | null;
  event_type: string;
  severity: LogSeverity;
  status: string | null;
  message: string | null;
  data: Record<string, unknown>;
  detections: {
    track_id?: number | null;
    class_id?: number;
    class_name: string;
    confidence: number;
    bbox: BBox;
    attributes?: Record<string, unknown>;
  }[];
  frame: { width: number; height: number } | null;
  snapshot_url: string | null;
  occurred_at: string;
  updated_at: string;
}

export interface StreamInfo {
  camera_id: UUID;
  camera_code: string;
  status: StreamStatus;
  stream_type: StreamType;
  webrtc_url: string;
  hls_url: string;
  token: string;
  expires_in: number;
}

// ---- realtime ----
export type RealtimeType =
  | "detection.created"
  | "device.heartbeat"
  | "device.status"
  | "camera.status"
  | "log.created"
  | "log.updated";

export interface RealtimeMessage<T = Record<string, unknown>> {
  type: RealtimeType;
  data: T;
  ts: string;
}

export interface DeviceStatusMessage {
  device_id: UUID;
  device_uuid: string;
  status: DeviceStatus;
  last_seen?: string | null;
}

export interface CameraStatusMessage {
  device_id: UUID;
  camera_id: UUID;
  camera_code: string;
  status: CameraStatus;
  stream_status: StreamStatus;
  ai_status: AiStatus;
  last_frame_at: string | null;
  runtime_stats: CameraRuntimeStats;
}

export interface HeartbeatMessage {
  device_id: UUID;
  device_uuid: string;
  timestamp: string;
  cpu_usage: number;
  memory_usage: number;
  gpu_usage: number | null;
  gpu_memory_usage: number | null;
  temperature: number | null;
  agent_version: string;
}
