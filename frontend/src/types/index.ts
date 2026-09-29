// Mirrors backend Pydantic schemas (backend/app/schemas)

export type UUID = string;
export type Role = "admin" | "operator" | "viewer";
export type DeviceStatus = "pending" | "online" | "offline";
export type CameraStatus = "unknown" | "online" | "offline" | "error";

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

export interface Camera {
  id: UUID;
  edge_device_id: UUID;
  edge_device_name: string | null;
  edge_device_status: DeviceStatus | null;
  site_id: UUID | null;
  site_name: string | null;
  name: string;
  rtsp_url_masked: string;
  has_credentials: boolean;
  onvif_url: string | null;
  stream_id: string;
  enabled: boolean;
  ai_enabled: boolean;
  ai_model_id: UUID | null;
  ai_model_name: string | null;
  status: CameraStatus;
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
}

export interface StreamInfo {
  camera_id: UUID;
  stream_id: string;
  webrtc_url: string;
  hls_url: string;
  token: string;
  expires_in: number;
}

// ---- realtime ----
export type RealtimeType = "detection.created" | "device.heartbeat" | "device.status" | "camera.status";

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
  status: CameraStatus;
  error: string | null;
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
