# Annotated Video Streaming — 架構設計（v2）

> 本文件取代 v1 中「Edge 以 `-c copy` 轉送原始影像」的串流設計。
> v2 的主串流是 **Edge 在本地完成 YOLO 辨識後，畫上 Bounding Box / Label / Confidence / Track ID 的即時影像**，
> 以 H.264 編碼後由 Edge **主動 Push** 到中央 MediaMTX，瀏覽器以 WebRTC（HLS fallback）播放。
> Detection metadata 仍走 MQTT → Backend → PostgreSQL → WebSocket，與影像**完全分離**。

---

## 1. System Architecture

```
 ┌──────────────── Site A (private network 192.168.1.0/24) ────────────────┐
 │  Camera A 192.168.1.101 ─┐                                               │
 │  Camera B 192.168.1.102 ─┼─RTSP (LAN only)─►  Edge Device edge01         │
 └──────────────────────────┼───────────────────── │ ───────────────────────┘
 ┌──────────── Site B (10.0.10.0/24, 也可以是 192.168.1.0/24) ─────────────┐
 │  Camera C 10.0.10.33 ────┴─RTSP (LAN only)─►  Edge Device edge05         │
 └──────────────────────────────────────────────── │ ───────────────────────┘
                                                    │  只有 OUTGOING 連線（NAT / Firewall 友善）
                 ┌──────────────────────────────────┼─────────────────────────────────────┐
                 │ ① RTSP(TCP) / SRT push  annotated H.264  →  MediaMTX :8554 / :8890     │
                 │ ② MQTT  metadata / heartbeat / status    →  Mosquitto/EMQX :1883       │
                 │ ③ HTTPS register / config / presign      →  Backend :8000              │
                 │ ④ HTTPS presigned PUT snapshot           →  MinIO :9000                │
                 └──────────────────────────────────┼─────────────────────────────────────┘
 ┌──────────────────────────── Central Platform ────┼─────────────────────────────────────┐
 │                                                   ▼                                     │
 │  MediaMTX ──auth hook──► Backend (FastAPI xN) ──► PostgreSQL                            │
 │     │ WebRTC(WHEP) / HLS        │   │  └────────► Redis (Pub/Sub, cache, lock)          │
 │     ▼                           │   └ MQTT consumer ($share)                            │
 │  Browser ◄──── REST / WebSocket ┘                                                       │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 設計原則

| 原則 | 做法 |
|------|------|
| Camera IP 是 Edge 的內部資訊 | Central Server 只用 `site_id / edge_device_id / camera_id` 管理。兩個 Site 都有 `192.168.1.101` 也沒關係 |
| Central 永遠不連 Edge / Camera | Edge 主動建立所有 outgoing 連線（RTSP/SRT push、MQTT、HTTPS） |
| 影像與 metadata 分離 | 影像 = H.264 串流（MediaMTX）；metadata = MQTT → DB（可搜尋、統計、告警、報表） |
| 不用 JPEG/Base64 傳影像 | MQTT / WebSocket 只傳 JSON；影像一律走真正的 video streaming |
| 故障隔離 | 每支 Camera 一個獨立 Pipeline；Pipeline 內 capture / inference / render / publish 各自一個 worker |
| 記憶體有界 | 所有 queue 都有上限，滿了就丟最舊的 frame |

### Stream 命名（不使用 Camera IP）

| 身分 | 例 | 來源 |
|------|----|------|
| `site_id`（code） | `site01` | `sites.code` |
| `device_id` | `edge01` | `edge_devices.device_uuid` |
| `camera_id`（code） | `cam01` | `cameras.code`（同一台 Edge 內唯一） |

| 用途 | MediaMTX path |
|------|---------------|
| AI 辨識影像（預設） | `ai/{site}/{device}/{camera}` → `ai/site01/edge01/cam01` |
| 原始影像（可選） | `original/{site}/{device}/{camera}` → `original/site01/edge01/cam01` |

邏輯 ID `site/site01/device/edge01/camera/cam01` 與 path 一一對應；path 存在 `cameras.stream_path`，由 Backend 產生並下發給 Edge。

---

## 2. Video Data Flow

```
Camera RTSP ──► CaptureWorker ──► FrameQueue(inference, max=1, drop-oldest) ──► InferenceWorker
 (decoder,          │                                                             │ detector.detect()
  auto-reconnect)   │                                                             │ tracker.update()
                    │                                                             ▼
                    │                                                        DetectionStore (latest result)
                    │                                                             │
                    └──► FrameQueue(render, max=2, drop-oldest) ──► RenderWorker ◄┘  @ stream_fps
                                                                        │ OverlayRenderer:
                                                                        │ bbox + "Person 95% #123"
                                                                        ▼
                                                        FrameQueue(annotated, max=3, drop-oldest)
                                                                        │
                                                                        ▼
                                                    PublishWorker ─► StreamPublisher.publish(frame)
                                                                        │  VideoEncoder (FFmpeg)
                                                                        │  h264_nvenc | libx264
                                                                        ▼
                                          rtsp://MEDIA:8554/ai/site01/edge01/cam01   (RTSP TCP)
                                          srt://MEDIA:8890?streamid=publish:ai/...   (SRT)
                                                                        │
                                                                        ▼
                                              MediaMTX ──► WebRTC (WHEP) ──► Browser
                                                       └─► HLS (fallback)
```

### Workers（每支 Camera 各一組 thread）

| Worker | 速率 | 失敗時 |
|--------|------|--------|
| **CaptureWorker** | 相機原生 FPS（例 30） | 自動 reconnect，backoff 1→2→5→10→30 s；`rtsp_status=offline/connecting` |
| **InferenceWorker** | `inference_fps`（例 5） | 例外只影響該次推論；模型載入失敗 → `ai_status=error` 並以 backoff 重試；**影像照樣串流** |
| **RenderWorker** | `stream_fps`（例 25），固定節拍 | 沒有新 frame 就重複上一張（讓 encoder 拿到固定 FPS） |
| **PublishWorker** | 跟隨 annotated queue | Publisher 斷線 → 丟 frame 並以 backoff reconnect；**AI inference 不停** |

### AI FPS 與 Streaming FPS 分離

```
Camera 30 FPS ─► Capture ─► Render/Stream 25 FPS（每張都畫框）
                        └─► Inference 5 FPS（只取最新一張）
```
兩次推論之間的 frame：
- **Option A（MVP 預設）**：沿用 `DetectionStore` 最新結果（`detection_hold_seconds` 內有效，過期就不畫）。
- **Option B（已預留）**：`Tracker.predict()` 以 tracker 狀態推估 bbox。`ai/tracking.py` 定義 `Tracker` 介面，MVP 內建 `IoUTracker`（提供穩定 `track_id`），可替換為 **ByteTrack / BoT-SORT**。

### Video Encoding

| 設定 | 預設 | 說明 |
|------|------|------|
| `video_codec` | `h264` | WebRTC / HLS 相容性最佳 |
| `encoder` | `auto` | `auto` → 偵測到 NVIDIA + `h264_nvenc` 就用 NVENC，否則 `libx264`（`ultrafast` + `zerolatency`，無 B-frame） |
| `width` × `height` | 來源解析度 | 設定後 render 階段縮放 |
| `stream_fps` | 25 | |
| `inference_fps` | 5 | |
| `bitrate` | `2M` | |
| `gop_size` | 50（= 2 s @ 25fps） | 影響 WebRTC 首畫面時間 |

`VideoEncoder` 介面 → `FFmpegEncoder`（MVP）、`NVENCEncoder`（強制 h264_nvenc）、`GStreamerEncoder`（預留）。

---

## 3. Detection Data Flow

```
InferenceWorker ─► DetectionProcessor ─► (bounded queue, drop if full) ─► EventDispatcher thread
                    · min_confidence 過濾                                   · annotated snapshot JPEG
                    · 新 track_id → 事件                                     · presigned PUT → MinIO
                    · 無 tracker 時 per-class cooldown                       · MQTT QoS1
                                                                              edge/{device}/cameras/{camera}/events
                                                                                      │
                                           Backend MQTT consumer ($share/backend/...) ◄┘
                                           · 驗證 topic ↔ payload、camera 屬於 device
                                           · INSERT … ON CONFLICT DO NOTHING (event_id, index)
                                           · PostgreSQL（可搜尋 / 統計 / 報表 / 告警）
                                           · Redis Pub/Sub → WebSocket → Browser
```

Metadata schema（v2）：
```json
{
  "event_id": "uuid",
  "device_id": "edge01",
  "camera_id": "cam01",
  "timestamp": "ISO8601",
  "model": "yolov8n",
  "frame": { "width": 1920, "height": 1080 },
  "snapshot_key": "2026/01/01/edge01/<camera uuid>/<uuid>.jpg",
  "detections": [
    { "track_id": 123, "class_id": 0, "class_name": "person", "confidence": 0.96,
      "bbox": { "x1": 300, "y1": 200, "x2": 600, "y2": 900 }, "attributes": {} }
  ]
}
```
影像串流上的 overlay 只是「給人看」；**唯一可查詢的資料來源是 metadata**。

---

## 4. Multi-Camera Architecture

```
EdgeAgent
 ├─ BackendClient (REST)      ├─ EdgeMQTTClient (LWT, reconnect, offline queue)
 ├─ HeartbeatReporter (10 s)  └─ HealthReporter (per camera status, 10 s + on change)
 └─ CameraManager
     ├─ CameraPipeline(cam01) ─ Capture │ Inference │ Render │ Publish │ (Passthrough original/)
     ├─ CameraPipeline(cam02) ─ …
     ├─ CameraPipeline(cam03) ─ …
     └─ CameraPipeline(camNN)          ← 1 / 4 / 8 / 16+ 支
```

- **獨立 instance**：每個 `CameraPipeline` 有自己的 queue、detector、tracker、encoder、publisher、health；沒有共用可變狀態。
- **故障隔離**：每個 worker loop 包在 try/except 內；worker 意外結束會被 pipeline supervisor 重新啟動；CameraManager 以設定 fingerprint 做 diff，只重啟有變更的 camera。
- **有界資源**：每支 camera 最多 1 + 2 + 3 張 frame 在 queue 中；事件 dispatcher queue 上限 32。
- **健康狀態**：每支 camera 回報到 `edge/{device_id}/cameras/{camera_id}/status`：
  ```json
  { "camera_id": "cam01", "rtsp_status": "online", "ai_status": "running", "stream_status": "streaming",
    "input_fps": 30, "inference_fps": 5, "output_fps": 25, "resolution": "1920x1080",
    "last_frame_at": "ISO8601", "dropped_frames": 12, "error": null }
  ```
  Backend 寫入 `cameras.status / ai_status / stream_status / last_frame_at / runtime_stats` 並以 WebSocket 推 `camera.status`。
  Edge 斷線（MQTT LWT）時 Backend 將該 Edge 所有 camera 標為 `offline`。
- **GPU 擴充（未來）**：多支 camera 共用一個 GPU 時，可把 per-camera detector 換成共享的 batched inference service，`InferenceWorker` 介面不變。

---

## 5. Edge → Server Streaming Strategy

| 情境 | Protocol | URL |
|------|----------|-----|
| LAN / VPN（預設） | **RTSP over TCP push** | `rtsp://<device_uuid>:<device_key>@MEDIA:8554/ai/site01/edge01/cam01` |
| 跨 Internet、高延遲、丟包 | **SRT push**（預留，已可用） | `srt://MEDIA:8890?streamid=publish:ai/site01/edge01/cam01:<device_uuid>:<device_key>` |
| 未來 | WebRTC (WHIP) push | `WebRTCPublisher`（介面已預留） |

```
StreamPublisher (interface)          VideoEncoder (interface)
 ├─ connect()                         ├─ start(output_url, format)
 ├─ publish(frame)   ← 非阻塞重連     ├─ write(frame)
 ├─ reconnect()                        ├─ close()
 ├─ stop()                             ├─ FFmpegEncoder   (libx264 / h264_nvenc)
 ├─ RTSPPublisher  (MVP)               ├─ NVENCEncoder
 ├─ SRTPublisher   (MVP, 預留)          └─ GStreamerEncoder (預留)
 └─ WebRTCPublisher (預留)
```

- **Outgoing only**：Edge 主動連 MediaMTX；中央不需要知道 Edge 或 Camera 的私有 IP，支援 NAT / Firewall / 多 Site / 重疊網段。
- **認證**：推流帳密 = `device_uuid` / device API key（或未來的 token），MediaMTX 以 HTTP auth hook 詢問 Backend：該 device 是否擁有此 `stream_path`、該串流類型是否啟用。未來可加 RTSPS / SRT passphrase / VPN / mTLS。
- **自動重連**：`publish()` 在斷線時不阻塞，只丟棄 frame，並依 backoff（1, 2, 5, 10, 30 s，上限 30 s）嘗試重新 `connect()`。重連期間 capture 與 inference 持續運作（事件照常送出）。
- **播放**：Browser 呼叫 `GET /api/v1/cameras/{camera_id}/stream?type=ai` →
  `{ camera_id, status, stream_type, webrtc_url, hls_url, token, expires_in }`；WebRTC 優先，失敗 fallback HLS；Browser 不播放 RTSP。
- **Security**：Frontend 永遠拿不到 camera 帳密、RTSP URL、device credential，只拿到 playback URL + 短效 stream token（綁定單一 path）。

---

## 6. 資料模型 / API / MQTT 變更摘要

**sites**：新增 `code`（slug，唯一，例 `site01`）。

**cameras**：
- 新增：`code`、`stream_path`（唯一）、`stream_enabled`、`annotated_stream_enabled`、`original_stream_enabled`、`stream_status`（offline / connecting / streaming / error）、`ai_status`、`resolution`、`stream_fps`、`inference_fps`、`bitrate`、`gop_size`、`video_codec`、`last_frame_at`、`runtime_stats`。
- 移除：`stream_id`（由 `code` + `stream_path` 取代）。
- `site_id` 由 `edge_device.site_id` 推導並在 API 回傳。為避免資料不一致，不另存一份。

**detection_events**：新增 `track_id`。

**API**：
- 新增 `GET /cameras/{id}/stream?type=ai|original`（取代 `/streams/{id}`）。
- `CameraRead` 不再回傳任何 RTSP URL（只剩 `has_credentials`、`source_configured`）。
- `/edge/config` 回傳每支 camera 的串流/編碼/推論設定與 publish endpoint。

**MQTT**：新增 `edge/{device_id}/cameras/{camera_id}/status`；MQTT 中的 `camera_id` 改用 camera `code`（例 `cam01`）。

**MediaMTX**：啟用 SRT `:8890/udp`；path 允許多層（`ai/…`、`original/…`）。
