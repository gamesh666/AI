# AIBOX SERVER

AI 智慧影像監控與邊緣運算管理平台。現場的 AI BOX（例如 REACH）自己辨識，把**已畫框的影像**和**辨識紀錄**送到這裡；
平台負責接收、保存、顯示，本身不做辨識。

```text
 現場（只連出）                                   AIBOX SERVER（一台 Linux VM，Docker Compose）
 ┌───────────────────────┐   HTTP + 裝置金鑰     ┌──────────────────────────────────────────┐
 │ 攝影機 → AI BOX        │ ───────────────────►  │ API :8000 ── PostgreSQL（裝置、紀錄）      │
 │ （自己辨識、畫框）      │   RTSP 已畫框影像     │ MediaMTX :8554 / :8889 / :8888（影像）     │
 │                       │ ───────────────────►  │ MinIO :9000（快照）   Redis（即時推播）     │
 └───────────────────────┘   快照 JPEG           │ 網頁 :3000 ◄── 管理者瀏覽器                 │
                             ───────────────────► └──────────────────────────────────────────┘
```

## 安裝

在一台乾淨的 Ubuntu 虛擬機上：

```bash
git clone https://github.com/gamesh666/AI.git /opt/ai-monitor
cd /opt/ai-monitor
./scripts/install.sh
```

完整步驟（安裝 Docker、防火牆、接 AI BOX、備份、搬家）：
**[docs/AIBOX-SERVER-建置SOP.md](docs/AIBOX-SERVER-建置SOP.md)**（圖解版：[docs/AIBOX-SERVER-圖解SOP.md](docs/AIBOX-SERVER-圖解SOP.md)）

| 常用指令（在 `/opt/ai-monitor`） | 用途 |
|---|---|
| `git pull && ./scripts/install.sh` | 更新 |
| `./scripts/install.sh <新IP>` | VM 的 IP 改了 |
| `./scripts/backup.sh` / `./scripts/restore.sh <資料夾>` | 備份 / 還原、搬家 |
| `./scripts/doctor.sh` | 健康檢查 |

## 功能

- **總覽**：在線裝置、攝影機、今日斷線與紀錄、邊緣裝置運算狀態。
- **即時監看**：各攝影機已畫框的即時影像（WebRTC，失敗自動改 HLS）。
- **Edge 紀錄**：所有辨識結果與系統紀錄（斷線 / 恢復、攝影機增減），可篩選，快照可放大。
- **業主 / 場域 / 邊緣裝置**：合約資料、佈建權杖（AI BOX 以 MAC 自動註冊）、裝置金鑰、稽核。
- **AI 模型**：各裝置回報正在使用的模型與版本。
- 介面：繁中 / 簡中 / 英文，Claude 色調 / 科技風兩種主題，10 分鐘無操作自動登出。

## 邊緣裝置怎麼接

全部是 HTTP，每台用自己的裝置金鑰（`X-Device-Key`）：

| 動作 | 端點 |
|---|---|
| 自動註冊（MAC + 業主佈建權杖） | `POST /api/v1/edge/register` |
| 取設定（攝影機推流路徑、場域資料） | `GET /api/v1/edge/config` |
| 同步攝影機清單 | `PUT /api/v1/edge/cameras` |
| 心跳（每 10 秒，回應帶指令與設定版本） | `POST /api/v1/edge/heartbeat` |
| 攝影機狀態 | `POST /api/v1/edge/cameras/{code}/status` |
| 辨識紀錄（一筆或一次 100 筆） | `POST /api/v1/edge/logs` |
| 上線 / 離線 | `POST /api/v1/edge/status` |
| 快照上傳網址 | `POST /api/v1/edge/snapshots/presign` |
| 已畫框影像 | `rtsp://<裝置ID>:<金鑰>@<平台IP>:8554/<stream_path>` |

規格：[docs/edge-integration.md](docs/edge-integration.md)。可執行範例：[examples/edge-http/](examples/edge-http/)。
REACH 專用文件：[docs/partners/reach/](docs/partners/reach/)。

## 專案結構

```text
backend/     FastAPI + SQLAlchemy（Alembic migrations），API 與即時推播
frontend/    Next.js 網頁
shared/      邊緣裝置送來的 JSON 格式（Pydantic，schemas/ 為對應的 JSON Schema）
infra/       docker-compose、MediaMTX、PostgreSQL 設定
scripts/     install / backup / restore / doctor / set-public-host
examples/    參考用的邊緣程式（HTTP）
docs/        建置 SOP、串接規格、REACH 文件
```

## 開發

```bash
docker compose up -d postgres redis minio mediamtx   # 只開基礎服務
./scripts/dev-backend.sh                             # 後端（熱重載）
cd frontend && npm install && npm run dev            # 前端
cd backend && pytest                                 # 後端測試
```

`.env` 內含所有密碼，**不可**提交到 Git（這個 repo 是公開的）。
