# AI 智慧影像監控與邊緣運算管理平台 (AI VMS) — MVP Framework

一個可執行、模組化、可水平擴充的 MVP：多個地點的 **Edge Device** 就近連接各自網段內的 RTSP/ONVIF 攝影機，
在本地以 **YOLO** 推論，然後把兩種資料**主動推送**回中央平台：

1. **Detection metadata**（JSON，MQTT）→ 資料庫 → 搜尋 / 統計 / 告警 / WebSocket 即時推播
2. **AI 標註影像**（畫上 BBox / Label / Confidence / Track ID 的 H.264 串流，RTSP 或 SRT push）→ MediaMTX → 瀏覽器 WebRTC（HLS fallback）

> 設計文件：[`docs/architecture.md`](docs/architecture.md)（架構、資料庫、API、MQTT）、
> [`docs/video-architecture.md`](docs/video-architecture.md)（影像管線、多攝影機、Edge → Server 串流策略）。

---

## 1. Architecture

```
 Site (xN)                                   Central platform
┌───────────────────────────┐     ┌──────────────────────────────────────────────────────────┐
│ IP Cam ─RTSP─┐            │     │  Frontend (Next.js) ◄──REST/WS──► Backend (FastAPI) xN   │
│ IP Cam ─RTSP─┤            │     │        │  WebRTC/HLS              │   │   │    │          │
│              ▼            │     │        ▼                          │   │   │    ▼          │
│  Edge Agent (Python)      │     │    MediaMTX ◄──auth hook──────────┘   │   │  PostgreSQL   │
│   ├ capture → YOLO (local)│─H.264 annotated, RTSP/SRT push (outgoing)─►  │   │               │
│   ├ overlay → H.264 encode│     │                                       │   └► Redis        │
│   ├ MQTT (events/heartbeat)─────────►  Mosquitto / EMQX ───────────────┘      (pub/sub,    │
│   └ REST (register/config)│     │                                            cache, lock)  │
│   └ presigned PUT snapshot ─────────►  MinIO (snapshots)                                   │
└───────────────────────────┘     └──────────────────────────────────────────────────────────┘
```

| 資料流 | 路徑 |
|--------|------|
| **偵測事件（無 polling）** | Edge YOLO → MQTT `edge/{device}/cameras/{camera}/events` → Backend（共享訂閱）→ PostgreSQL → Redis Pub/Sub → WebSocket → 瀏覽器 |
| **Heartbeat（10 秒）** | Edge → MQTT `edge/{device}/heartbeat` → Backend 更新狀態/指標 → WebSocket；逾時 30 秒由 monitor 標記 offline；MQTT LWT 即時標記斷線 |
| **影像** | Camera → Edge capture → YOLO → overlay（BBox/Label/Conf/Track ID）→ H.264（NVENC / libx264）→ RTSP/SRT push → MediaMTX `ai/{site}/{device}/{camera}` → 瀏覽器 WebRTC（WHEP），失敗自動改 HLS |
| **攝影機健康** | Edge → MQTT `edge/{device}/cameras/{camera}/status`（RTSP / AI / stream 狀態、input / inference / output FPS）→ Backend → WebSocket |
| **快照** | Edge 向 Backend 取得 presigned URL → 直接 PUT 到 MinIO；前端以 presigned GET 顯示 |

**關鍵設計**

- **AI 推論只在 Edge**：中央平台不做推論；收到的是 metadata 與已標註好的影像串流。
- **Camera IP 不出 Site**：中央以 `site / device / camera` ID 管理攝影機，所有連線都由 Edge 對外建立（NAT / Firewall / 重疊網段都可運作）。
- **每支攝影機獨立 pipeline**：capture / inference / render / publish 分屬不同 worker，以有界 queue（丟最舊 frame）串接；任一支攝影機或串流故障不影響其他攝影機與 AI 推論。
- **Backend 無狀態 → 水平擴充**：MQTT 使用 `$share/backend/...` 共享訂閱分流、WebSocket 透過 Redis Pub/Sub 跨實例廣播、背景工作以 Redis lock 保證單一執行、migration 以 PostgreSQL advisory lock 序列化。
- **Broker 可替換**：程式只依賴 `backend/app/messaging/base.py::MessageBroker` 介面與標準 MQTT；換 EMQX 只需改 `MQTT_HOST/PORT/USERNAME/PASSWORD`。
- **契約集中**：MQTT topic 與 payload 定義在 `shared/python/aivms_shared`，Backend 與 Edge Agent 共用；`shared/schemas/*.json` 為自動產生的 JSON Schema。
- **安全**：JWT access + refresh（rotation、重用偵測）、RBAC（admin / operator / viewer）、RTSP 帳密 Fernet 加密且永不回傳前端、串流以短效 stream token 經 MediaMTX auth hook 驗證、所有 secret 皆來自環境變數。

---

## 2. Repository structure

```
.
├── backend/            FastAPI 服務
│   ├── app/
│   │   ├── core/           config、security (JWT/bcrypt)、crypto (Fernet)、redis、enums、exceptions
│   │   ├── db/             SQLAlchemy engine/session、Base
│   │   ├── models/         ORM：user, site, edge_device, camera, ai_model, detection_event
│   │   ├── schemas/        Pydantic DTO（每個 domain 一個檔）
│   │   ├── repositories/   資料存取層
│   │   ├── services/       商業邏輯（auth, device, camera, event, stream, storage, edge…）
│   │   ├── api/            deps（DI/RBAC/device auth）+ v1/ 每個資源一個 router
│   │   ├── messaging/      MessageBroker 介面、MQTT 實作、topic handlers、publisher
│   │   ├── realtime/       WebSocket endpoint、connection manager、Redis broadcaster
│   │   ├── workers/        device offline monitor
│   │   └── cli/seed.py     初始 admin / 預設模型 / demo 資料
│   ├── alembic/        migrations
│   └── tests/
├── frontend/           Next.js 15 + React 19 + TypeScript + Tailwind
│   └── src/
│       ├── app/            login/ 與 (console)/{dashboard,monitor,events,devices,cameras,sites,models,users}
│       ├── components/     layout/ ui/ dashboard/ camera/ events/ devices/ sites/ models/ users/
│       ├── hooks/          useAsync, useMutation, useLiveDevices
│       ├── lib/            api/（每個資源一個檔）auth/ realtime/ streaming/（WHEP、HLS）
│       └── types/
├── edge-agent/         邊緣代理
│   └── agent/
│       ├── core/           Agent 生命週期、backoff、有界 frame queue、supervised worker、device key 儲存
│       ├── api_client/     Backend REST client
│       ├── messaging/      mqtt.py（LWT、自動重連、離線佇列）、publisher、command handler
│       ├── telemetry/      系統指標（CPU/MEM/GPU/溫度）、heartbeat
│       ├── config/         settings.py（EDGE_* env / YAML）、models.py（Server 下發的 camera 設定）
│       ├── camera/         capture.py（decoder + 重連）、pipeline.py（每支 camera 一個）、manager.py、synthetic.py
│       ├── ai/             detector.py、mock_detector.py、yolo_detector.py、tracking.py、inference_worker.py、processor.py
│       ├── video/          overlay.py、encoder.py（VideoEncoder：FFmpeg / NVENC / GStreamer）、render_worker.py
│       ├── streaming/      publisher.py（StreamPublisher）、rtsp_publisher.py、srt_publisher.py、publish_worker.py、passthrough.py
│       ├── monitoring/     health.py（每支 camera 的 fps 與狀態）
│       └── storage/        快照上傳（presigned PUT）
├── shared/
│   ├── python/aivms_shared/  topics.py、payloads.py（Backend/Edge 共用契約）
│   └── schemas/              自動產生的 JSON Schema
├── docker-compose.demo.yml  profile "demo"：fake cameras、模擬 camera LAN、2 台模擬 edge、demo seeder
├── simulation/         Development / Simulation Mode 程式碼（production 不依賴）
│   ├── fake-camera/              FFmpeg test pattern / loop mp4 → RTSP
│   ├── edge/Dockerfile           production edge agent + simulation plugin
│   └── python/aivms_sim/         edge plugin（MockDetector、file:// / mock:// source、模擬 GPU）、demo seeder
├── infra/
│   ├── docker-compose.yml    完整 stack
│   ├── mosquitto/            設定、ACL 範本、由 env 產生密碼檔的 entrypoint
│   ├── mediamtx/             mediamtx.yml（HTTP auth → Backend）
│   └── postgres/init/
├── scripts/            generate-secrets.sh、gen_schemas.py、dev-backend.sh、dev-edge.sh
├── docs/architecture.md
├── docker-compose.yml  入口（include infra/docker-compose.yml）
└── .env.example
```

---

## 3. How to start

需求：Docker 24+、Docker Compose v2.24+（支援 `include`）。
在 VM 上部署、從其他電腦操作：請看 **[`docs/deploy-vm.md`](docs/deploy-vm.md)**（含常見問題與 `scripts/doctor.sh`）。

```bash
# 1) 產生 .env（所有 secret 自動隨機產生）
./scripts/generate-secrets.sh > .env
#    或：cp .env.example .env 並手動替換所有 change-me

# 2) 啟動 Frontend, Backend, PostgreSQL, Redis, Mosquitto, MediaMTX, MinIO
docker compose up -d

# 3) 沒有實體設備時：完整 Demo / Simulation 環境
#    4 台 fake camera（FFmpeg → RTSP）+ 2 台模擬 edge（EDGE001 / EDGE002）+ MockDetector + demo 資料
docker compose --profile demo up -d

docker compose ps
```

| 服務 | URL |
|------|-----|
| Frontend | http://localhost:3000 （帳號 `admin`，密碼為 `.env` 的 `INITIAL_ADMIN_PASSWORD`） |
| Backend API / Swagger | http://localhost:8000/docs |
| MediaMTX WebRTC / HLS | http://localhost:8889 / http://localhost:8888 |
| MinIO API / Console | http://localhost:9000 / http://127.0.0.1:9001 |
| MQTT | localhost:1883 |

Backend 啟動時會自動執行 `alembic upgrade head` 與 seed（初始 admin、預設 `yolov8n` 模型）。

### Development / Simulation Mode（無 IP Camera、無 GPU、無 Edge 硬體）

`docker compose --profile demo up -d` 約一分鐘後，Frontend 即可看到 2 個 Site、2 台 Edge Device、
4 台 Camera 的 AI 標註即時影像、Detection Event、裝置狀態與攝影機健康狀態。

| Demo 元件 | 模擬 | 接上真實設備時 |
|-----------|------|---------------|
| `fake-camera01..04` | FFmpeg test pattern / loop mp4 → H.264 RTSP（1920x1080@30） | IP Camera（在 UI 改 RTSP URL） |
| `edge01` / `edge02` | **Production edge agent** + simulation plugin（EDGE001 / EDGE002） | 同一個 agent 跑在 edge 硬體上 |
| MockDetector | 每隔數秒產生 person / car / truck / excavator，格式與 YOLO 完全相同 | `DETECTOR_TYPE=yolo` |
| 模擬 GPU telemetry | heartbeat 中的 GPU 使用率 / 溫度 | `EDGE_METRICS_PROVIDER=system` |
| `demo-seed` | 透過公開 REST API 建立 Site / Device / Camera | 管理者在 UI 建立 |

所有模擬程式碼都在 `simulation/`，Production 程式碼與映像檔不依賴它（有測試強制檢查）。
Backend、Frontend、MQTT、Database、Streaming 架構完全不需修改。詳見 **[`simulation/README.md`](simulation/README.md)**。

**接上真實的 Edge Device**

1. 在 Frontend → *Edge Devices* 建立裝置（或讓 agent 以 `EDGE_PROVISIONING_TOKEN` 自行註冊）。
2. 在 *Cameras* 新增攝影機，RTSP URL 可含帳密（`rtsp://user:pass@ip:554/...`），系統會拆出並加密儲存。
3. 在 Edge 主機上：
   ```bash
   docker build -f edge-agent/Dockerfile -t aivms/edge-agent .
   docker run -d --name aivms-edge --restart unless-stopped \
     -e EDGE_DEVICE_UUID=edge-001 \
     -e EDGE_API_URL=http://<server>:8000/api/v1 \
     -e EDGE_PROVISIONING_TOKEN=<token> \
     -e EDGE_MQTT_USERNAME=edge -e EDGE_MQTT_PASSWORD=<mqtt-edge-password> \
     -v aivms-edge:/var/lib/aivms-edge aivms/edge-agent
   ```
   並把 `.env` 的 `MQTT_PUBLIC_HOST`、`MEDIAMTX_RTSP_PUBLISH_URL`（或 `MEDIAMTX_SRT_PUBLISH_URL` + `EDGE_STREAM_PROTOCOL=srt`，跨 Internet 建議）、`MINIO_EDGE_URL` 設成 Edge 可連到的位址；
   Edge 只需要**對外**連得到中央的 8000 / 1883 / 8554（或 8890/udp）/ 9000，中央不需要連到 Edge 或攝影機。
   NVIDIA GPU：以 CUDA base image 建置並安裝 `requirements-yolo.txt`，`EDGE_VIDEO_ENCODER=auto` 會自動使用 `h264_nvenc`。
   瀏覽器不在本機時設定 `MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS`、`MEDIAMTX_*_PUBLIC_URL`、`MINIO_PUBLIC_URL`、`NEXT_PUBLIC_API_URL`、`CORS_ORIGINS`。

**水平擴充 Backend**：移除 backend 的固定 port 對外映射、在前面放 LB（nginx/Traefik），`docker compose up -d --scale backend=3`。

---

## 4. Development environment

```bash
# 只啟動基礎設施
docker compose up -d postgres redis mosquitto mediamtx minio

# Backend（Python 3.12）
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt -e shared/python
./scripts/dev-backend.sh                    # alembic + seed + uvicorn --reload
cd backend && pytest && ruff check .

# Frontend（Node 22）
cd frontend && npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
npm run typecheck && npm run build

# Edge agent
pip install -r edge-agent/requirements-dev.txt -e shared/python -e simulation/python
./scripts/dev-edge.sh edge-dev-001          # 需要 PATH 上有 ffmpeg 才會推流
cd edge-agent && pytest && ruff check .     # production tests（不含任何 mock）
cd simulation && pytest                     # production pipeline + simulation plugin

# 產生新的 migration
cd backend && alembic revision --autogenerate -m "describe change"

# 修改 shared payload 後重產 JSON Schema
python scripts/gen_schemas.py
```

**使用 YOLO**：安裝 `edge-agent/requirements-yolo.txt`、在 AI Models 設定 `model_path`（.pt / .onnx / .engine），並設定 `EDGE_DETECTOR=yolo`
（`agent/ai/yolo_detector.py`，Ultralytics）。其他推論後端只要實作 `Detector` 介面並註冊到 `agent/ai/factory.py`；
ByteTrack / BoT-SORT 實作 `agent/ai/tracking.py::Tracker` 即可替換內建的 `IoUTracker`。

---

## 5. API endpoints

Base `/api/v1`，互動文件：`/docs`。管理 API 以 `Authorization: Bearer <access_token>`；Edge API 以 `X-Device-Key`。

| Method | Path | Role | 說明 |
|--------|------|------|------|
| GET | `/health`, `/health/ready` | — | liveness / readiness（DB、Redis、MQTT） |
| POST | `/auth/login` · `/auth/refresh` · `/auth/logout` | — / user | JWT + refresh token rotation |
| GET | `/auth/me` | user | 目前使用者 |
| CRUD | `/users` | admin | 使用者管理 |
| CRUD | `/sites` | viewer 讀 / operator 寫 | 地點 |
| CRUD | `/devices` | viewer / operator | Edge Device（建立時回傳一次性 `api_key`） |
| POST | `/devices/{id}/rotate-key` | admin | 重新產生 device key |
| POST | `/devices/{id}/commands` | operator | 經 MQTT 下發 `reload_config` / `restart_camera` / `ping` |
| CRUD | `/cameras` | viewer / operator | RTSP 帳密只寫不讀（回傳 `rtsp_url_masked`、`has_credentials`） |
| CRUD | `/ai-models` | viewer / operator | AI 模型 |
| GET | `/events` | viewer | 篩選 `start,end,site_id,camera_id,edge_device_id,class_name,min_confidence,max_confidence`，分頁 |
| GET | `/events/classes`, `/events/{id}` | viewer | |
| DELETE | `/events/{id}` | admin | |
| GET | `/dashboard/summary?since=` | viewer | online/offline devices、camera / active camera、今日事件數 |
| GET | `/cameras/{camera_id}/stream?type=ai\|original` | viewer | `{camera_id, status, stream_type, webrtc_url, hls_url, token, expires_in}`，不含任何攝影機位址 |
| POST | `/streams/mediamtx/auth` | MediaMTX | MediaMTX HTTP auth hook（RTSP/SRT publish：device key + 擁有該 path；read：綁定 path 的 stream token） |
| POST | `/edge/register` | `X-Provisioning-Token` | Edge 註冊 → device key |
| GET | `/edge/config` | `X-Device-Key` | 攝影機（含解密後 RTSP URL）、模型、MQTT / 串流設定 |
| POST | `/edge/snapshots/presign` | `X-Device-Key` | MinIO presigned PUT URL |
| WS | `/ws?token=<access_token>[&types=...]` | user | 即時推播 `detection.created`, `device.heartbeat`, `device.status`, `camera.status` |

---

## 6. MQTT topics

| Topic | 方向 | QoS | Retain | Payload |
|-------|------|-----|--------|---------|
| `edge/{device_id}/heartbeat` | Edge → Server | 0 | – | `Heartbeat`（每 10 秒） |
| `edge/{device_id}/status` | Edge → Server | 1 | ✓ | `DeviceStatus`（online / offline；LWT = offline） |
| `edge/{device_id}/events` | Edge → Server | 1 | – | `DetectionEvent`（裝置層級） |
| `edge/{device_id}/cameras/{camera_id}/events` | Edge → Server | 1 | – | `DetectionEvent`（主要路徑） |
| `edge/{device_id}/cameras/{camera_id}/status` | Edge → Server | 0 | – | `CameraRuntimeStatus`（RTSP / AI / stream 狀態與 FPS；每 10 秒 + 狀態變化時） |
| `server/{device_id}/command` | Server → Edge | 1 | – | `Command` |
| `server/{device_id}/config` | Server → Edge | 1 | ✓ | `ConfigChanged`（只通知，設定經 REST 拉取，RTSP 帳密不經過 broker） |

`device_id` = `edge_devices.device_uuid`（例 `edge01`），`camera_id` = `cameras.code`（例 `cam01`）。Schema：`shared/schemas/*.schema.json`。
影像**不經過** MQTT / WebSocket，只走 H.264 串流。

Detection event：
```json
{
  "event_id": "uuid", "device_id": "edge01", "camera_id": "cam01",
  "timestamp": "2026-01-01T00:00:00Z", "model": "yolov8n",
  "frame": { "width": 1920, "height": 1080 },
  "snapshot_key": "2026/01/01/edge01/<camera uuid>/<uuid>.jpg",
  "detections": [
    { "track_id": 123, "class_id": 0, "class_name": "person", "confidence": 0.96,
      "bbox": { "x1": 300, "y1": 200, "x2": 600, "y2": 900 }, "attributes": {} }
  ]
}
```
Heartbeat：`device_uuid, timestamp, cpu_usage, memory_usage, gpu_usage, gpu_memory_usage, temperature, agent_version`（另可帶 hostname、ip_address、gpu_name、gpu_memory）。

Backend 以 `(event_id, detection_index)` 唯一鍵做冪等寫入（QoS 1 重送不會重複），並驗證 topic 的 device/camera 與 payload 一致、攝影機屬於該 device、快照 key 屬於該 device。

---

## 7. Environment variables

全部定義於 [`.env.example`](.env.example)。`./scripts/generate-secrets.sh > .env` 會替換所有 secret。

| 變數 | 說明 |
|------|------|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | PostgreSQL |
| `REDIS_PASSWORD` | Redis `requirepass` |
| `JWT_SECRET_KEY` | JWT 簽章金鑰 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token 期限（預設 15 分 / 7 天） |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key，加密 RTSP 密碼 |
| `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` / `INITIAL_ADMIN_EMAIL` | 第一個 admin（僅在沒有 admin 時建立） |
| `EDGE_PROVISIONING_TOKEN` | Edge 自行註冊用的共享密鑰 |
| `MQTT_BACKEND_USERNAME` / `MQTT_BACKEND_PASSWORD` | Backend 的 MQTT 帳號 |
| `MQTT_EDGE_USERNAME` / `MQTT_EDGE_PASSWORD` | Edge 的 MQTT 帳號 |
| `MQTT_SHARED_GROUP` | Backend 共享訂閱群組 |
| `MQTT_PUBLIC_HOST` | 回傳給遠端 Edge 的 broker 位址 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO 帳密 |
| `MINIO_BUCKET_SNAPSHOTS` | 快照 bucket |
| `MINIO_PUBLIC_URL` / `MINIO_EDGE_URL` | 瀏覽器下載 / Edge 上傳用的 MinIO 位址（presigned URL 綁定 host） |
| `MINIO_IMAGE` | MinIO 映像（預設 `alpine/minio`，可改 `quay.io/minio/minio:<tag>`） |
| `MEDIAMTX_WEBRTC_PUBLIC_URL` / `MEDIAMTX_HLS_PUBLIC_URL` | 瀏覽器播放位址 |
| `MEDIAMTX_RTSP_PUBLISH_URL` / `MEDIAMTX_SRT_PUBLISH_URL` | 遠端 Edge 推送標註影像的位址（RTSP：LAN/VPN；SRT：跨 Internet） |
| `EDGE_STREAM_PROTOCOL` | 下發給 Edge 的預設推流協定 `rtsp` \| `srt` |
| `MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS` | WebRTC ICE 對外 IP / hostname |
| `NEXT_PUBLIC_API_URL` | 前端呼叫的 Backend 位址（build-time） |
| `CORS_ORIGINS` | 允許的前端來源（逗號分隔） |
| `SIM_*` / `FAKE_CAMERA0N_*` / `DEMO_*` | 僅 Demo / Simulation 環境使用（見 `simulation/README.md`）；Production 不需要 |

Edge agent 使用 `EDGE_*` 前綴（見 `edge-agent/agent/config.py` 與 `edge-agent/config.example.yaml`）：
`EDGE_DEVICE_UUID, EDGE_API_URL, EDGE_PROVISIONING_TOKEN | EDGE_DEVICE_KEY, DETECTOR_TYPE (= EDGE_DETECTOR, 預設 yolo), EDGE_DETECTOR_FALLBACK, EDGE_PLUGINS, EDGE_MQTT_HOST/PORT/USERNAME/PASSWORD/TLS, EDGE_STREAM_PROTOCOL, EDGE_RTSP_PUBLISH_URL, EDGE_SRT_PUBLISH_URL, EDGE_VIDEO_ENCODER, EDGE_DETECTOR, EDGE_TRACKER, EDGE_MIN_CONFIDENCE, EDGE_DETECTION_HOLD_SECONDS, EDGE_*_QUEUE_SIZE …`
（每支攝影機的 resolution / stream_fps / inference_fps / bitrate / gop_size 由中央 Camera 設定下發。）

---

## 8. MVP 範圍與後續

| 已完成 | 下一步建議 |
|--------|-----------|
| 完整 domain model + Alembic migration | 事件保存期限 / TimescaleDB 或分區表 |
| JWT + refresh rotation + RBAC | refresh token 改用 httpOnly cookie；SSO/OIDC |
| MQTT ingest（冪等、共享訂閱）、WebSocket 推播 | EMQX + 每台裝置獨立 MQTT 帳號（HTTP auth / ACL） |
| Edge：註冊、設定同步、heartbeat、LWT、指令、快照 | ByteTrack / BoT-SORT、Option B（tracker 預測兩次推論間的 bbox） |
| 每支攝影機獨立 pipeline、有界 queue、supervised workers、backoff 重連 | 多攝影機共用 GPU 的 batched inference service |
| YOLO（Ultralytics）+ Mock detector、IoU tracker、overlay | GStreamer / NVDEC 解碼、GStreamerEncoder、WebRTC (WHIP) publisher |
| H.264（NVENC 自動偵測 / libx264）、RTSP + SRT push、每支攝影機健康狀態 | RTSPS / SRT passphrase / mTLS、每裝置 MQTT 帳號（EMQX） |
| WebRTC 優先 + HLS fallback、以 path 綁定的串流授權 | 事件 clip（MediaMTX record → MinIO）、TURN server、ONVIF 探索 / PTZ |

> 攝影機只會被 Edge 開一條 RTSP 連線（標註影像由同一條解碼後產生）；只有啟用 `original_stream_enabled`（原始影像 passthrough）時才會多開一條。
