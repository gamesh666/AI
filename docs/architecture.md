# AI 智慧影像監控與邊緣運算管理平台 — MVP 架構設計

本文件是 MVP Framework 的設計基準。程式碼依照本文件產生；後續擴充請先更新本文件。

> **v2 更新**：影像架構已改為「Edge 完成 YOLO 辨識後，將畫上 BBox / Label / Confidence / Track ID 的
> H.264 影像主動 Push 到中央 MediaMTX」。影像管線、Detection 資料流、多攝影機架構與 Edge → Server
> 串流策略請見 **[`video-architecture.md`](video-architecture.md)**；本文件其餘章節（DB / API / MQTT）已同步更新。

---

## 1. Architecture Design

### 1.1 設計原則

| 原則 | 做法 |
|------|------|
| AI 推論只在邊緣 | Edge Agent 在本地跑 YOLO，中央只收「結果 (JSON) + 快照」，不收原始影像做推論 |
| 控制面 / 資料面分離 | REST = 管理與設定（控制面）；MQTT = 遙測與事件（資料面）；MediaMTX = 影像（媒體面） |
| 無狀態 Backend | Backend 不保存連線狀態，WebSocket fan-out 走 Redis Pub/Sub，因此可以任意水平擴充 |
| Broker 可替換 | Backend/Edge 只依賴 `MessageBroker` 介面與標準 MQTT 3.1.1/5；Mosquitto → EMQX 只需改連線設定 |
| 契約集中 | MQTT Topic 與 Payload 定義在 `shared/`，Backend 與 Edge Agent 共用同一份 Python 套件 |
| Secret 不落地 | 所有密碼、JWT secret、加密金鑰全部來自環境變數；RTSP 帳密以 Fernet 加密儲存且永不回傳前端 |

### 1.2 系統元件圖

```
                               ┌───────────────────────────── Central Platform ─────────────────────────────┐
                               │                                                                             │
 ┌──────────── Site A ───────┐ │   ┌───────────┐  REST / WS   ┌──────────────────────┐                      │
 │ IP Cam ─RTSP─┐            │ │   │ Frontend  │◄────────────►│ Backend (FastAPI) xN │──► PostgreSQL        │
 │ IP Cam ─RTSP─┤            │ │   │ Next.js   │              │  ├─ REST API         │                      │
 │ IP Cam ─RTSP─┤            │ │   └─────┬─────┘              │  ├─ MQTT consumer ◄──┼──┐                   │
 │              ▼            │ │         │ WebRTC(WHEP)/HLS   │  ├─ WS gateway ◄─────┼──┼─ Redis Pub/Sub    │
 │  ┌──────────────────────┐ │ │         ▼                    │  └─ Device monitor   │  │  (+ cache/lock)   │
 │  │ Edge Agent (Python)  │ │ │   ┌───────────┐  auth hook   └──────────┬───────────┘  │                   │
 │  │  ├─ RTSP reader(CV2) │─┼─┼──►│ MediaMTX  │─────────────────────────┘              │                   │
 │  │  ├─ YOLO + overlay   │ │ │   └───────────┘  (H.264 annotated, RTSP/SRT push)      │                   │
 │  │  ├─ H.264 encoder    │ │ │   ┌───────────┐                                        │                   │
 │  │  ├─ MQTT client      │─┼─┼──►│ Mosquitto │────────────────────────────────────────┘                   │
 │  │  └─ REST client      │─┼─┼──►│ / EMQX    │  events / heartbeat / status                              │
 │  └──────────────────────┘ │ │   └───────────┘                                                            │
 └───────────────────────────┘ │   ┌───────────┐  presigned PUT (snapshot)                                  │
                               │   │  MinIO    │◄──── Edge Agent                                            │
                               │   └───────────┘────► Frontend (presigned GET)                              │
                               └────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 主要資料流

**(a) Detection Event（即時，無 polling）**
```
Edge YOLO → (presigned PUT) MinIO snapshot
          → MQTT edge/{device}/cameras/{camera}/events  (QoS 1)
          → Backend MQTT consumer ($share/backend/... 共享訂閱，多實例負載平衡)
          → PostgreSQL (ON CONFLICT DO NOTHING → 冪等)
          → Redis PUBLISH ws:broadcast
          → 每個 Backend 實例的 WS gateway → 瀏覽器
```

**(b) Heartbeat（每 10 秒）**
```
Edge → MQTT edge/{device}/heartbeat → Backend → 更新 edge_devices (last_seen/metrics, status=online)
                                             → Redis cache device:{uuid}:heartbeat (TTL)
                                             → WS push device.heartbeat
Device monitor (Redis lock 保證只有一個實例執行) → last_seen 超過 30 秒 → status=offline → WS push
```

**(c) 影像**
```
IP Camera ─RTSP→ Edge (capture → YOLO → overlay → H.264) ─RTSP/SRT push→ MediaMTX path ai/{site}/{device}/{camera}
Browser ─WHEP (WebRTC)→ MediaMTX   （失敗時）─HLS→ MediaMTX
MediaMTX 每次 publish/read 都呼叫 Backend /api/v1/streams/mediamtx/auth 驗證
```
攝影機多半在 NAT 後面，所以由 Edge **主動推流**到中央，中央不需要能連到攝影機。

**(d) Edge 生命週期**
```
1. POST /api/v1/edge/register  (provisioning token) → 取得 device_uuid + device API key（只顯示一次）
2. GET  /api/v1/edge/config    (X-Device-Key)       → 攝影機清單（含解密後的 RTSP URL）、模型、MQTT/stream 設定
3. MQTT 連線，LWT = edge/{device}/status {"state":"offline"}
4. 每 10 秒 heartbeat；攝影機狀態變化時送 status
5. 接收 server/{device}/command、server/{device}/config（例如 reload_config）
```

### 1.4 水平擴充策略

| 元件 | 擴充方式 |
|------|---------|
| Backend | 無狀態；`docker compose up --scale backend=N` + LB。MQTT 使用 shared subscription `$share/backend/...`，WS 走 Redis Pub/Sub |
| MQTT | Mosquitto 單機（MVP）→ EMQX cluster（替換連線設定即可） |
| MediaMTX | 依 stream_path（site / device）分片到多台 MediaMTX；`/cameras/{id}/stream` 回傳的 URL 由 Backend 決定，前端不寫死 |
| PostgreSQL | detection_events 依 `detected_at` 建索引；未來可改 TimescaleDB / 依月份 partition |
| MinIO | 分散式模式；bucket `snapshots`，物件 key 以 `{yyyy}/{mm}/{dd}/{device}/{camera}/{uuid}.jpg` 分散 |
| Edge | 每台 Edge 獨立；每支攝影機一個 pipeline thread |

### 1.5 安全設計

- **JWT**：Access token（預設 15 分鐘）+ Refresh token（預設 7 天，DB 只存 hash，使用時輪替 rotation，可撤銷）
- **RBAC**：`admin`（全部）/ `operator`（管理 Site/Device/Camera/Model/Event）/ `viewer`（唯讀）
- **Edge 身分**：Provisioning token 註冊 → 個別 device API key（DB 只存 SHA-256）
- **RTSP 帳密**：寫入時從 URL 拆出並以 Fernet（`CREDENTIAL_ENCRYPTION_KEY`）加密；API 回應僅有 `rtsp_url_masked` 與 `has_credentials`
- **串流授權**：前端向 Backend 取得短效 stream token（JWT, scope=stream, 綁定 path），MediaMTX 透過 HTTP auth hook 驗證
- **MQTT**：帳密由環境變數產生 Mosquitto password file，關閉匿名登入；ACL 限制 Edge 只能寫 `edge/#`、讀 `server/#`

---

## 2. Directory Structure

```
project-root/
├── backend/                     # FastAPI 中央服務
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                 # DB migrations
│   │   ├── env.py
│   │   └── versions/0001_initial.py
│   ├── scripts/entrypoint.sh    # migrate → seed → uvicorn
│   ├── tests/
│   └── app/
│       ├── main.py              # app factory + lifespan
│       ├── core/                # config, security(JWT/密碼), crypto(Fernet), logging, enums
│       ├── db/                  # engine/session, declarative base
│       ├── models/              # SQLAlchemy ORM（一個 domain 一個檔）
│       ├── schemas/             # Pydantic DTO（一個 domain 一個檔）
│       ├── repositories/        # 資料存取（CRUD base + domain queries）
│       ├── services/            # 商業邏輯（auth, device, camera, event, stream, storage…）
│       ├── api/
│       │   ├── deps.py          # DI：DB session、current user、RBAC、device auth
│       │   ├── router.py
│       │   └── v1/              # 一個資源一個 router
│       ├── messaging/           # MessageBroker 介面、MQTT 實作、topic handlers
│       ├── realtime/            # WebSocket connection manager + Redis Pub/Sub bridge
│       ├── workers/             # 背景工作（device offline monitor）
│       └── cli/                 # seed admin 等管理指令
├── frontend/                    # Next.js 15 + React 19 + TS + Tailwind
│   ├── Dockerfile
│   └── src/
│       ├── app/                 # App Router pages
│       │   ├── login/
│       │   └── (console)/       # 需登入的頁面：dashboard, monitor, events, devices, cameras, sites, models, users
│       ├── components/          # layout/, ui/, dashboard/, camera/, events/, devices/
│       ├── lib/
│       │   ├── api/             # REST client（一個資源一個檔）
│       │   ├── auth/            # AuthContext, token storage
│       │   ├── realtime/        # WebSocket provider/hook
│       │   └── streaming/       # WHEP(WebRTC) / HLS player 邏輯
│       └── types/
├── edge-agent/                  # 邊緣代理
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.example.yaml
│   ├── tests/
│   └── agent/
│       ├── main.py
│       ├── config.py
│       ├── core/                # Agent orchestrator, credential store
│       ├── api_client/          # Backend REST client
│       ├── messaging/           # MQTT client, publisher, command handler
│       ├── telemetry/           # system metrics (CPU/MEM/GPU/溫度), heartbeat loop
│       ├── config/              # settings (env/YAML) + server config models
│       ├── camera/              # capture (decoder + reconnect), pipeline, manager, synthetic source
│       ├── ai/                  # Detector 介面 + registry, YOLO detector, tracking, inference worker, event processor
│       ├── video/               # overlay renderer, VideoEncoder (FFmpeg/NVENC/GStreamer), render worker
│       ├── streaming/           # StreamPublisher (RTSP / SRT), publish worker, original passthrough
│       ├── monitoring/          # per-camera health (fps, rtsp/ai/stream status)
│       └── storage/             # snapshot uploader (presigned PUT)
├── shared/
│   ├── python/aivms_shared/     # 共用：MQTT topics、payload models（Backend/Edge 共用）
│   └── schemas/                 # 由 Pydantic 產生的 JSON Schema（給其他語言/文件使用）
├── simulation/                  # Development / Simulation Mode（見 simulation/README.md；production 不依賴）
├── infra/
│   ├── docker-compose.yml
│   ├── mosquitto/               # mosquitto.conf, acl, entrypoint（由 env 產生密碼檔）
│   ├── mediamtx/mediamtx.yml
│   └── postgres/init/           # 初始化 SQL（extensions）
├── scripts/                     # dev 工具：gen secrets, gen schemas, 建立 demo 資料
├── docs/                        # 本文件、API、MQTT 說明
├── docker-compose.yml           # 根目錄入口（include infra/docker-compose.yml）
├── .env.example
└── README.md
```

---

## 3. Database Design

所有主鍵使用 UUID（分散式環境下 Edge/多實例可安全產生 ID）。時間一律 `timestamptz` (UTC)。

```
users ─┐
       └─< refresh_tokens

sites ─< edge_devices ─< cameras >─ ai_models
                  │          │
                  └────< detection_events >── ai_models
```

### users
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid PK | |
| username | varchar(64) unique | |
| email | varchar(255) unique null | |
| full_name | varchar(128) null | |
| hashed_password | varchar(255) | bcrypt |
| role | enum(admin, operator, viewer) | RBAC |
| is_active | bool | |
| created_at / updated_at | timestamptz | |

### refresh_tokens
| id uuid PK | user_id FK | token_hash (sha256, unique) | expires_at | revoked_at null | created_at |

### sites
| id uuid PK | name varchar(128) unique | **code varchar(32) unique**（stream path 用，例 `site01`） | address varchar(255) | description text | created_at / updated_at |

### edge_devices
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid PK | |
| device_uuid | varchar(64) unique | MQTT/Edge 使用的識別碼，例如 `edge-001` |
| name | varchar(128) | |
| site_id | FK sites null | |
| hostname / ip_address | varchar | |
| status | enum(pending, online, offline) | |
| last_seen | timestamptz | |
| agent_version | varchar(32) | |
| gpu_name | varchar(128) | |
| gpu_memory | int (MB) | GPU 總記憶體 |
| cpu_usage / memory_usage | float (%) | 最新 heartbeat |
| gpu_usage / gpu_memory_usage / temperature | float | **擴充欄位**：heartbeat 需要 |
| api_key_hash | varchar(128) | **擴充欄位**：device 認證 |
| created_at / updated_at | timestamptz | |

### cameras
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid PK | |
| edge_device_id | FK edge_devices | |
| name | varchar(128) | |
| rtsp_url | varchar(512) | **不含帳密** |
| rtsp_username | varchar(128) null | **擴充**：明文帳號（不回傳前端） |
| rtsp_password_encrypted | text null | **擴充**：Fernet 加密 |
| onvif_url | varchar(512) null | **擴充**：ONVIF device service |
| code | varchar(32) | camera ID（同一 Edge 內唯一，例 `cam01`；MQTT 的 camera_id） |
| stream_path | varchar(255) unique | `ai/{site}/{device}/{camera}`（原始影像：`original/…`） |
| stream_enabled / annotated_stream_enabled / original_stream_enabled | bool | 串流開關 |
| resolution / stream_fps / inference_fps / video_codec / bitrate / gop_size | | 編碼與推論設定 |
| stream_status | enum(offline, connecting, streaming, error) | Edge 回報 |
| ai_status / last_frame_at / runtime_stats | | Edge 回報（fps、解析度、drop 數、錯誤） |
| enabled / ai_enabled | bool | |
| ai_model_id | FK ai_models null | **擴充**：此攝影機使用的模型 |
| status | enum(unknown, online, offline, error) | **擴充**：Edge 回報 |
| created_at / updated_at | timestamptz | |

### ai_models
| id uuid PK | name varchar(128) | version varchar(32) | model_type varchar(32)（yolov8/yolo11/…） | labels jsonb (list[str]) | model_path varchar(512) | description | created_at | **unique(name, version)** |

### detection_events
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | uuid PK | |
| event_group_id | uuid | MQTT payload 的 `event_id`（一則訊息可含多個 detection） |
| detection_index | int | 在 detections 陣列的位置；`unique(event_group_id, detection_index)` 保證 QoS1 重送冪等 |
| camera_id | FK cameras | |
| edge_device_id | FK edge_devices | |
| ai_model_id | FK ai_models null | |
| class_name | varchar(64) | |
| confidence | float | |
| bbox | jsonb `{x1,y1,x2,y2}` | |
| detected_at | timestamptz | |
| snapshot_url | varchar(512) null | MinIO object key（API 回應時轉為 presigned GET URL） |
| metadata | jsonb | class_id、frame size…等 |
| created_at | timestamptz | |

索引：`(detected_at DESC)`、`(camera_id, detected_at DESC)`、`(edge_device_id, detected_at DESC)`、`(class_name)`。

---

## 4. API Design

Base path `/api/v1`。管理 API 使用 `Authorization: Bearer <access_token>`；Edge API 使用 `X-Device-Key`。
列表 API 一律回傳 `{ items, total, page, page_size }`。

| Method | Path | 權限 | 說明 |
|--------|------|------|------|
| GET | `/health` `/health/ready` | public | liveness / readiness |
| POST | `/auth/login` | public | 帳密登入 → access + refresh |
| POST | `/auth/refresh` | public | refresh token 輪替 |
| POST | `/auth/logout` | user | 撤銷 refresh token |
| GET | `/auth/me` | user | 目前使用者 |
| GET/POST | `/users` | admin | 使用者列表 / 新增 |
| GET/PATCH/DELETE | `/users/{id}` | admin | |
| GET | `/sites` | viewer+ | |
| POST/PATCH/DELETE | `/sites[/{id}]` | operator+ | |
| GET | `/devices` | viewer+ | 篩選 site_id, status |
| POST | `/devices` | operator+ | 預先建立 device（回傳一次性 API key） |
| GET/PATCH/DELETE | `/devices/{id}` | viewer+/operator+ | |
| POST | `/devices/{id}/rotate-key` | admin | 重新產生 device key |
| POST | `/devices/{id}/commands` | operator+ | 透過 MQTT 下發 command |
| GET | `/cameras` | viewer+ | 篩選 site_id, edge_device_id, enabled |
| POST/PATCH/DELETE | `/cameras[/{id}]` | operator+ | RTSP 帳密只寫不讀 |
| GET | `/ai-models` | viewer+ | |
| POST/PATCH/DELETE | `/ai-models[/{id}]` | operator+ | |
| GET | `/events` | viewer+ | 篩選 start, end, site_id, camera_id, edge_device_id, class_name, min_confidence |
| GET | `/events/{id}` | viewer+ | |
| DELETE | `/events/{id}` | admin | |
| GET | `/dashboard/summary` | viewer+ | online/offline devices, camera count, active cameras, events today |
| GET | `/cameras/{camera_id}/stream?type=ai\|original` | viewer+ | 回傳 WebRTC(WHEP) / HLS URL + 短效 stream token（不含任何 camera 位址） |
| POST | `/streams/mediamtx/auth` | MediaMTX | MediaMTX HTTP auth hook |
| POST | `/edge/register` | provisioning token | Edge 註冊 |
| GET | `/edge/config` | device key | 攝影機（含 RTSP 帳密）、模型、MQTT topics |
| POST | `/edge/snapshots/presign` | device key | 取得 MinIO presigned PUT URL |
| WS | `/ws?token=<access_token>` | user | 即時推播 |

WebSocket 訊息格式：
```json
{ "type": "detection.created | device.heartbeat | device.status | camera.status", "data": { ... }, "ts": "ISO8601" }
```

---

## 5. MQTT Design

| Topic | 方向 | QoS | Retain | 說明 |
|-------|------|-----|--------|------|
| `edge/{device_id}/heartbeat` | Edge → Server | 0 | no | 每 10 秒 |
| `edge/{device_id}/status` | Edge → Server | 1 | yes | online/offline（LWT）+ 攝影機狀態 |
| `edge/{device_id}/events` | Edge → Server | 1 | no | 裝置層級事件 / 未指定攝影機的偵測 |
| `edge/{device_id}/cameras/{camera_id}/events` | Edge → Server | 1 | no | YOLO 偵測事件（主要路徑） |
| `edge/{device_id}/cameras/{camera_id}/status` | Edge → Server | 0 | no | 每支 camera 的 RTSP / AI / stream 健康狀態 |
| `server/{device_id}/command` | Server → Edge | 1 | no | `reload_config`、`restart_camera`、`snapshot`… |
| `server/{device_id}/config` | Server → Edge | 1 | yes | 設定變更通知（Edge 收到後呼叫 REST 拉最新設定） |

- `{device_id}` = `edge_devices.device_uuid`；`{camera_id}` = `cameras.code`（例 `cam01`）。
- Backend 訂閱使用 shared subscription：`$share/{MQTT_SHARED_GROUP}/edge/+/heartbeat` 等，N 個 backend 實例自動分流。Mosquitto 2.x 與 EMQX 皆支援。
- Edge 使用 LWT（Last Will）在 `edge/{device_id}/status` 發布 `{"state":"offline"}`，斷線即時反應。
- 設定檔內容**不**經 MQTT 傳送（避免 RTSP 帳密出現在 broker），`server/{id}/config` 只通知版本，Edge 透過 HTTPS REST 拉取。

Payloads（完整 schema 見 `shared/schemas/*.json`）：

```json
// heartbeat
{ "device_uuid": "edge-001", "timestamp": "2026-01-01T00:00:00Z", "cpu_usage": 12.5, "memory_usage": 40.1,
  "gpu_usage": 30.0, "gpu_memory_usage": 22.0, "temperature": 55.0, "agent_version": "0.1.0" }

// device status (retained; MQTT Last Will = offline)
{ "device_uuid": "edge01", "timestamp": "...", "state": "online" }

// camera status  edge/{device}/cameras/{camera}/status
{ "camera_id": "cam01", "rtsp_status": "online", "ai_status": "running", "stream_status": "streaming",
  "input_fps": 30, "inference_fps": 5, "output_fps": 25, "resolution": "1920x1080",
  "last_frame_at": "ISO8601", "dropped_frames": 12, "error": null }

// detection event  edge/{device}/cameras/{camera}/events
{ "event_id": "uuid", "device_id": "edge01", "camera_id": "cam01", "timestamp": "...", "model": "yolov8n",
  "frame": { "width": 1920, "height": 1080 },
  "snapshot_key": "2026/01/01/edge01/<camera uuid>/<uuid>.jpg",
  "detections": [ { "track_id": 123, "class_id": 0, "class_name": "person", "confidence": 0.95,
                    "bbox": { "x1": 100, "y1": 120, "x2": 400, "y2": 650 }, "attributes": {} } ] }

// command
{ "command_id": "uuid", "command": "reload_config", "params": {}, "issued_at": "..." }
```

**替換為 EMQX**：`MQTT_HOST/MQTT_PORT/MQTT_USERNAME/MQTT_PASSWORD` 指向 EMQX 即可；程式只依賴 `app/messaging/base.py::MessageBroker` 介面，若未來要換成 Kafka 等非 MQTT 系統，新增一個實作即可。

---

## 6. Streaming Design

v2 串流設計（AI annotated H.264、Edge 主動 push、RTSP/SRT、多攝影機 pipeline、自動重連）
見 **[`video-architecture.md`](video-architecture.md)**。
