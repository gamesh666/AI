# 在 Ubuntu 24.04 VM 上架設可操作的平台（Demo 模式）

目標：在沒有實體 Camera / Edge / GPU 的 VM 上，從**另一台電腦的瀏覽器**操作完整平台。

## 0. 已知問題與原因

| 現象 | 根因 | 處理 |
|------|------|------|
| `POST /cameras` HTTP 500（Site、Device 能建，Camera 建不了） | `.env` 的 `CREDENTIAL_ENCRYPTION_KEY=change-me-fernet-key` 不是合法 Fernet key。建立 Camera 時要加密 RTSP 密碼 → `ValueError: Fernet key must be 32 url-safe base64-encoded bytes`。Site / Device 不加密，所以正常 | 用 `./scripts/generate-secrets.sh` 產生 `.env`。Backend 現在遇到無效 key 會**直接拒絕啟動並說明原因**，不再等到建 Camera 才 500 |
| demo-seed `401 invalid username or password` | 初始 admin 只在第一次建立；之後改 `INITIAL_ADMIN_PASSWORD` 不會更新既有密碼 | `docker compose exec backend python -m app.cli.set_password admin` 重設密碼，或清空資料重來（見步驟 3） |
| demo build context 跑到 repo 外面 | demo compose 檔用 `-f` 載入時，相對路徑以 repo 根目錄解析；用 `include` 載入時以檔案所在目錄解析，兩種方式結果不同 | demo 檔已移到 repo 根目錄 `docker-compose.demo.yml`，路徑一律以 repo 根目錄為準，兩種載入方式都正確。**請直接用** `docker compose --profile demo up -d` |
| 從別台電腦開網頁登入失敗 / 影片不出來 | `NEXT_PUBLIC_API_URL`、MediaMTX、MinIO 的公開網址預設是 `localhost`，對你的電腦來說 localhost 不是 VM | `./scripts/set-public-host.sh <VM IP>` |

**不需要重灌 VM**：以上都是設定檔與 repo 狀態問題，不是作業系統問題。

## 1. Docker（若尚未安裝官方版）

Ubuntu 內建的 `docker.io` / `docker-compose`（v1）或 snap 版本可能太舊。請使用 Docker 官方 apt 套件（需要 Compose ≥ 2.24）：

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER   # 重新登入後生效
docker compose version          # >= 2.24
```

## 2. 讓 repo 回到乾淨狀態

```bash
cd /opt/ai-monitor
cp .env ~/ai-monitor.env.backup            # 先備份（內含密碼，勿外傳）
git stash list; git status                 # 看看有哪些本機修改
git stash                                  # 暫存本機修改（例如手改過的 compose 路徑）
git fetch origin
git checkout claude/ai-video-surveillance-mvp-mbcpyc
git pull
```

## 3. 產生新的 `.env` 並重設資料

資料庫目前只有 demo 資料（1 admin / 1 site / 1 device / 0 camera），清掉重來最單純：

```bash
./scripts/generate-secrets.sh > .env       # 全部密碼重新隨機產生，含合法 Fernet key
./scripts/set-public-host.sh               # 自動偵測 VM IP；或 ./scripts/set-public-host.sh 192.168.x.x
grep INITIAL_ADMIN_PASSWORD .env           # 登入密碼

docker compose --profile demo down -v      # 清掉舊 volume（舊密碼 / 舊 key 的資料）
```

> 若想保留資料：只換 `CREDENTIAL_ENCRYPTION_KEY`（目前 0 台 camera，沒有被舊 key 加密的資料），
> 其他密碼保持原值，admin 密碼用 `python -m app.cli.set_password admin` 重設。

VM 規格較小（< 4 核 / < 8 GB）時，在 `.env` 降低假攝影機負載：

```env
SIM_CAMERA_WIDTH=1280
SIM_CAMERA_HEIGHT=720
SIM_CAMERA_FPS=15
```

## 4. 檢查並啟動

```bash
./scripts/doctor.sh                        # 0 failure 才繼續
docker compose --profile demo up -d --build
docker compose --profile demo ps           # 等約 1–2 分鐘
docker compose logs demo-seed              # 應看到 "demo topology ready: 2 sites, 2 edge devices, 4 cameras"
```

## 5. 防火牆（若 VM 有開 ufw）

```bash
sudo ufw allow 3000,8000,8888,8889,9000/tcp
sudo ufw allow 8189/udp                    # WebRTC；沒開時會自動改用 HLS
```

VirtualBox / VMware 請用 **Bridged** 或 **Host-only** 網卡，讓你的電腦能直接連到 VM IP。
若只能用 NAT，需把上述 port 轉發到本機，並以 `./scripts/set-public-host.sh localhost` 設定。

## 6. 使用

瀏覽器開 `http://<VM IP>:3000`，帳號 `admin`，密碼為 `.env` 的 `INITIAL_ADMIN_PASSWORD`。
介面語言可在右上角「登出」旁（登入頁右上角）切換：繁體中文 / 简体中文 / English，會記在瀏覽器中。

| 頁面 | 內容 |
|------|------|
| Dashboard | 2 台 Edge 在線、4 台 Camera、今日偵測數、即時偵測（WebSocket） |
| Sites / Edge Devices / Cameras / AI Models / Users | 真實 CRUD（PostgreSQL） |
| Camera Monitor | 1x1 / 2x2 / 3x3 / 4x4，AI 標註影像（WebRTC，失敗自動 HLS） |
| Detection Events | 篩選、快照、即時新增 |

所有資料都走真實路徑：fake camera → 模擬 Edge（production edge agent + MockDetector）→ MQTT / MediaMTX → Backend → 瀏覽器。
沒有任何「前端假資料」，因此之後換成真實 Camera / YOLO / Edge 時畫面與 API 都不用改。

## 7. 疑難排解

| 狀況 | 指令 |
|------|------|
| 整體檢查 | `./scripts/doctor.sh` |
| Backend 錯誤 | `docker compose logs backend --tail 100` |
| Camera 沒畫面 | `docker compose logs edge01 --tail 50`、`docker compose logs sim-rtsp --tail 20` |
| 忘記 admin 密碼 | `docker compose exec backend python -m app.cli.set_password admin` |
| 重跑 demo 資料 | `docker compose --profile demo up demo-seed`（可重複執行，不會重複建立） |
| 全部重來 | `docker compose --profile demo down -v && docker compose --profile demo up -d --build` |
