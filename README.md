# AI 智慧影像監控與邊緣運算管理平台 (AI VMS) — MVP Framework

一個可執行、模組化、可水平擴充的 MVP：多個地點的 **Edge Device** 在本地以 **YOLO** 推論 RTSP/ONVIF 攝影機影像，
只把**辨識結果 + 快照**送回中央平台；中央平台提供即時影像（WebRTC / HLS）、即時事件推播與設備/攝影機/模型管理。

> 完整設計（架構、資料庫、API、MQTT、串流）請見 [`docs/architecture.md`](docs/architecture.md)。

---

## 1. Architecture

```
 Site (xN)                                   Central platform
┌───────────────────────────┐     ┌──────────────────────────────────────────────────────────┐
│ IP Cam ─RTSP─┐            │     │  Frontend (Next.js) ◄──REST/WS──► Backend (FastAPI) xN   │
│ IP Cam ─RTSP─┤            │     │        │  WebRTC/HLS              │   │   │    │          │
│              ▼            │     │        ▼                          │   │   │    ▼          │
│  Edge Agent (Python)      │     │    MediaMTX ◄──auth hook──────────┘   │   │  PostgreSQL   │
│   ├ OpenCV → YOLO (local) │─RTSP publish─►                               │   │               │
│   ├ FFmpeg relay (-c copy)│     │                                       │   └► Redis        │
│   ├ MQTT (events/heartbeat)─────────►  Mosquitto / EMQX ───────────────┘      (pub/sub,    │
│   └ REST (register/config)│     │                                            cache, lock)  │
│   └ presigned PUT snapshot ─────────►  MinIO (snapshots)                                   │
└───────────────────────────┘     └──────────────────────────────────────────────────────────┘
```

| 資料流 | 路徑 |
|--------|------|
| **偵測事件（無 polling）** | Edge YOLO → MQTT `edge/{device}/cameras/{camera}/events` → Backend（共享訂閱）→ PostgreSQL → Redis Pub/Sub → WebSocket → 瀏覽器 |
| **Heartbeat（10 秒）** | Edge → MQTT `edge/{device}/heartbeat` → Backend 更新狀態/指標 → WebSocket；逾時 30 秒由 monitor 標記 offline；MQTT LWT 即時標記斷線 |
| **影像** | Camera → Edge FFmpeg（不重編碼）→ MediaMTX → 瀏覽器 WebRTC（WHEP），失敗自動改 HLS |
| **快照** | Edge 向 Backend 取得 presigned URL → 直接 PUT 到 MinIO；前端以 presigned GET 顯示 |

**關鍵設計**

- **AI 推論只在 Edge**：中央平台不接收原始影像做推論，只收 JSON 結果與快照。
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
│       ├── core/           Agent 生命週期、device key 儲存
│       ├── api_client/     Backend REST client
│       ├── messaging/      MQTT client（LWT、自動重連、離線佇列）、publisher、command handler
│       ├── telemetry/      系統指標（CPU/MEM/GPU/溫度）、heartbeat
│       ├── camera/         RTSP/合成影像來源、FFmpeg relay、worker、manager
│       ├── inference/      Detector 介面、MockDetector、YoloDetector（stub）、factory
│       ├── pipeline/       取樣 → 推論 → 過濾 → 節流 → 快照 → 發佈
│       └── storage/        快照上傳（presigned PUT）
├── shared/
│   ├── python/aivms_shared/  topics.py、payloads.py（Backend/Edge 共用契約）
│   └── schemas/              自動產生的 JSON Schema
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

需求：Docker 24+、Docker Compose v2.20+（支援 `include`）。

```bash
# 1) 產生 .env（所有 secret 自動隨機產生）
./scripts/generate-secrets.sh > .env
#    或：cp .env.example .env 並手動替換所有 change-me

# 2) 啟動 Frontend, Backend, PostgreSQL, Redis, Mosquitto, MediaMTX, MinIO
docker compose up -d

# 3) （可選）加上 demo edge agent：合成攝影機畫面 + mock detector，完整跑通事件與串流
docker compose --profile edge up -d

docker compose ps
```

| 服務 | URL |
|------|-----|
| Frontend | http://localhost:3000 （帳號 `admin`，密碼為 `.env` 的 `INITIAL_ADMIN_PASSWORD`） |
| Backend API / Swagger | http://localhost:8000/docs |
| MediaMTX WebRTC / HLS | http://localhost:8889 / http://localhost:8888 |
| MinIO API / Console | http://localhost:9000 / http://127.0.0.1:9001 |
| MQTT | localhost:1883 |

Backend 啟動時會自動執行 `alembic upgrade head` 與 seed（初始 admin、預設 `yolov8n` 模型；`SEED_DEMO_DATA=true` 時另建 Demo Site / `edge-demo-001` / 兩支 `mock://` 攝影機）。

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
   並把 `.env` 的 `MQTT_PUBLIC_HOST`、`MEDIAMTX_RTSP_PUBLISH_URL`、`MINIO_EDGE_URL` 設成 Edge 可連到的位址；
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
pip install -r edge-agent/requirements-dev.txt -e shared/python
./scripts/dev-edge.sh edge-dev-001          # 需要 PATH 上有 ffmpeg 才會推流
cd edge-agent && pytest && ruff check .

# 產生新的 migration
cd backend && alembic revision --autogenerate -m "describe change"

# 修改 shared payload 後重產 JSON Schema
python scripts/gen_schemas.py
```

**實作 YOLO**：`edge-agent/agent/inference/yolo_detector.py` 目前是 interface stub（docstring 內有實作範例）；
安裝 `edge-agent/requirements-yolo.txt`、完成 `load()/detect()`，並設定 `EDGE_DETECTOR=yolo`。新的推論後端（ONNX、TensorRT）只要實作 `Detector` 介面並註冊到 `inference/factory.py`。

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
| GET | `/streams/{camera_id}` | viewer | WebRTC(WHEP) / HLS URL + 短效 stream token |
| POST | `/streams/mediamtx/auth` | MediaMTX | MediaMTX HTTP auth hook（publish：device key；read：stream token） |
| POST | `/edge/register` | `X-Provisioning-Token` | Edge 註冊 → device key |
| GET | `/edge/config` | `X-Device-Key` | 攝影機（含解密後 RTSP URL）、模型、MQTT / 串流設定 |
| POST | `/edge/snapshots/presign` | `X-Device-Key` | MinIO presigned PUT URL |
| WS | `/ws?token=<access_token>[&types=...]` | user | 即時推播 `detection.created`, `device.heartbeat`, `device.status`, `camera.status` |

---

## 6. MQTT topics

| Topic | 方向 | QoS | Retain | Payload |
|-------|------|-----|--------|---------|
| `edge/{device_id}/heartbeat` | Edge → Server | 0 | – | `Heartbeat`（每 10 秒） |
| `edge/{device_id}/status` | Edge → Server | 1 | ✓ | `DeviceStatus`（含各攝影機狀態；LWT = offline） |
| `edge/{device_id}/events` | Edge → Server | 1 | – | `DetectionEvent`（裝置層級） |
| `edge/{device_id}/cameras/{camera_id}/events` | Edge → Server | 1 | – | `DetectionEvent`（主要路徑） |
| `server/{device_id}/command` | Server → Edge | 1 | – | `Command` |
| `server/{device_id}/config` | Server → Edge | 1 | ✓ | `ConfigChanged`（只通知，設定經 REST 拉取，RTSP 帳密不經過 broker） |

`device_id` = `edge_devices.device_uuid`，`camera_id` = `cameras.id`。Schema：`shared/schemas/*.schema.json`。

Detection event：
```json
{
  "event_id": "uuid", "device_id": "edge-001", "camera_id": "<camera uuid>",
  "timestamp": "2026-01-01T00:00:00Z", "model": "yolov8n",
  "snapshot_key": "2026/01/01/edge-001/<camera uuid>/<uuid>.jpg",
  "detections": [
    { "class_id": 0, "class_name": "person", "confidence": 0.95,
      "bbox": { "x1": 100, "y1": 120, "x2": 400, "y2": 650 } }
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
| `MEDIAMTX_RTSP_PUBLISH_URL` | 遠端 Edge 推流位址 |
| `MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS` | WebRTC ICE 對外 IP / hostname |
| `NEXT_PUBLIC_API_URL` | 前端呼叫的 Backend 位址（build-time） |
| `CORS_ORIGINS` | 允許的前端來源（逗號分隔） |
| `SEED_DEMO_DATA` / `EDGE_DEVICE_UUID` / `EDGE_DETECTOR` | Demo 資料與 demo edge agent |

Edge agent 使用 `EDGE_*` 前綴（見 `edge-agent/agent/config.py` 與 `edge-agent/config.example.yaml`）：
`EDGE_DEVICE_UUID, EDGE_API_URL, EDGE_PROVISIONING_TOKEN | EDGE_DEVICE_KEY, EDGE_MQTT_HOST/PORT/USERNAME/PASSWORD/TLS, EDGE_RTSP_PUBLISH_URL, EDGE_DETECTOR, EDGE_INFERENCE_FPS, EDGE_MIN_CONFIDENCE, EDGE_EVENT_COOLDOWN_SECONDS, EDGE_HEARTBEAT_INTERVAL_SECONDS …`

---

## 8. MVP 範圍與後續

| 已完成 | 下一步建議 |
|--------|-----------|
| 完整 domain model + Alembic migration | 事件保存期限 / TimescaleDB 或分區表 |
| JWT + refresh rotation + RBAC | refresh token 改用 httpOnly cookie；SSO/OIDC |
| MQTT ingest（冪等、共享訂閱）、WebSocket 推播 | EMQX + 每台裝置獨立 MQTT 帳號（HTTP auth / ACL） |
| Edge：註冊、設定同步、heartbeat、狀態、LWT、指令、快照 | YOLO 實作（Ultralytics / TensorRT）、推論用 sub-stream |
| WebRTC 優先 + HLS fallback、串流授權 | 事件 clip（MediaMTX record → MinIO）、TURN server |
| Mock detector 可端到端跑通 | ONVIF 探索 / PTZ、Edge OTA 更新 |

> 注意：目前 Edge 對同一支攝影機會開兩條 RTSP 連線（OpenCV 推論 + FFmpeg 轉送）。攝影機連線數受限時，可改為推論讀取 sub-stream 或從本地 MediaMTX 讀取。
