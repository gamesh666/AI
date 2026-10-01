# REACH 需新增功能規格：AIVMS 平台串接模組（aivms_bridge）

> 對象：REACH AI Office Vision System 開發者（含 Claude Code）
> 背景與分工：見 `01-AIVMS-平台說明與串接訴求.md`
> 本文件是**新增**功能的開發與驗收規格，不改變 `CLAUDE_SPEC.md` 既有的任何行為。

---

## 0. 原則（必須遵守）

1. **只新增、不改壞**：不得改變 REACH 既有 RTSP / YOLO / ROI / 離席狀態機 / Dashboard / 日報的行為與結果。
2. **可關閉**：`AIVMS_ENABLED=false`（預設）時模組完全不啟動，REACH 行為與現在一模一樣。
3. **故障隔離**：平台斷線、推流失敗、HTTP 錯誤都**不得**阻塞或拖慢 REACH 的主流程。
   - 與主流程之間一律用**有上限的佇列**，滿了就**丟最舊的**，絕不等待。
   - 所有網路動作在獨立執行緒，例外要被攔下並記 log，不可讓 REACH 程序結束。
4. **不洩漏機密**：攝影機 RTSP 帳密**不送給平台**；裝置金鑰、MQTT 密碼只放 env 檔，
   不寫入程式、Git、log、前端。log 中的 URL 必須遮蔽帳密。
5. 符合 REACH 既有規範：Linux / Python 3.12+、UTF-8、`pathlib.Path`、type hints、`logging`。

## 1. 模組位置與結構（建議）

```text
app/integrations/
├─ __init__.py
├─ aivms_bridge.py        # 對外入口：AivmsBridge（start/stop/publish_frame/report_event/report_camera_status）
├─ aivms_config.py        # 讀 env，產生設定物件
├─ aivms_mqtt.py          # MQTT 連線、LWT、心跳、狀態、事件
├─ aivms_video.py         # 每支攝影機一個推流執行緒（ffmpeg）
└─ aivms_payloads.py      # REACH 資料 → 平台 JSON 的轉換（純函式，方便測試）
tests/integrations/       # 對應單元測試
```

REACH 主程式只需要在三個地方各加一行呼叫（其餘全部在模組內）：

| 呼叫點 | 呼叫 | 說明 |
|--------|------|------|
| 啟動 / 關閉 | `bridge.start()` / `bridge.stop()` | 在 `app/main.py` lifespan |
| 每張**已畫框**畫面產生後（就是給 MJPEG / latest.jpg 的那張） | `bridge.publish_frame(camera_id, frame_bgr)` | 只放進佇列，立即返回 |
| 正式離席事件狀態改變時（寫入 `office_leave_events` 之後） | `bridge.report_event(event)` | 只放進佇列，立即返回 |
| 攝影機 / AI 狀態（可由 bridge 每 5 秒主動讀取 runtime） | `bridge.report_camera_status(...)` | 見第 6 節 |

## 2. 設定（env）

放在 `/etc/reach-ai-office-vision/office-vision.env`（權限 640，與既有設定相同）。

```bash
AIVMS_ENABLED=true
AIVMS_API_URL='http://<平台IP>:8000/api/v1'
AIVMS_DEVICE_ID='REACH01'
AIVMS_DEVICE_KEY='<平台提供，只顯示一次>'
AIVMS_MQTT_HOST='<平台IP>'
AIVMS_MQTT_PORT=1883
AIVMS_MQTT_USERNAME='<平台提供>'
AIVMS_MQTT_PASSWORD='<平台提供>'
AIVMS_MQTT_TLS=false
AIVMS_STREAM_URL='rtsp://<平台IP>:8554'      # 跨網際網路可改 srt://<平台IP>:8890
AIVMS_STREAM_FPS=15
AIVMS_STREAM_WIDTH=1280                       # 0 = 維持原始解析度；高度依比例
AIVMS_STREAM_BITRATE=2M
AIVMS_VIDEO_ENCODER=auto                      # auto | h264_nvenc | libx264（auto：有 NVENC 用 NVENC，否則 libx264）
AIVMS_SEND_EMPLOYEE_NAME=false                # 是否在事件中附員工姓名（個資，預設不送）
AIVMS_SEND_SNAPSHOT=true
```

缺少必要設定時：記一行 warning 並**停用模組**，REACH 照常啟動。

## 3. 通訊總覽

| # | 動作 | 方式 | 時機 |
|---|------|------|------|
| 3.1 | 登記攝影機 | HTTP `PUT /edge/cameras/{camera_code}` | 啟動時，每支攝影機一次 |
| 3.2 | 上線 / 離線狀態 | MQTT `edge/{device}/status`（retained + Last Will） | 連線時 / 斷線時 |
| 3.3 | 心跳 | MQTT `edge/{device}/heartbeat` | 每 10 秒 |
| 3.4 | 攝影機狀態 | MQTT `edge/{device}/cameras/{camera_code}/status` | 每 5 秒 |
| 3.5 | 即時辨識畫面 | H.264 RTSP（或 SRT）推流 | 持續 |
| 3.6 | 事件 | MQTT `edge/{device}/cameras/{camera_code}/logs` | 事件狀態改變時 |
| 3.7 | 快照（選用） | HTTP presign + PUT | 事件成立時 |

- `{device}` = `AIVMS_DEVICE_ID`（例 `REACH01`）
- `{camera_code}` = REACH 的 `camera_id`：`bimer-entrance-right`、`bimer-back-left`
- 所有 HTTP 呼叫都帶 header：`X-Device-Key: <AIVMS_DEVICE_KEY>`
- 所有時間用 **ISO 8601 且帶時區**，例如 `2026-09-29T09:15:10+08:00`

## 4. 登記攝影機（3.1）

```http
PUT {AIVMS_API_URL}/edge/cameras/bimer-back-left
X-Device-Key: ...
Content-Type: application/json

{"name": "BIMer 後左攝影機"}
```

回應（節錄）：

```json
{ "camera_id": "bimer-back-left", "name": "BIMer 後左攝影機",
  "stream_path": "ai/<site>/REACH01/bimer-back-left", "rtsp_url": null }
```

- **推流路徑一律使用回應中的 `stream_path`，不要自己組。**
- 可重複呼叫（冪等）。失敗時以 1/2/5/10/30 秒退避重試，期間該攝影機不推流。
- 不要送攝影機 RTSP 位址；`rtsp_url: null` 代表來源由 REACH 自己管理，這是正確的。

## 5. 上線狀態與心跳（3.2、3.3）

MQTT 連線前設定 **Last Will**（retained、QoS 1）：

```json
// topic: edge/REACH01/status
{"device_uuid": "REACH01", "state": "offline"}
```

連線成功（含每次重連）後立即送（retained、QoS 1）：

```json
{"device_uuid": "REACH01", "state": "online", "timestamp": "2026-09-29T09:00:00+08:00"}
```

正常關閉時先送 `offline` 再斷線。

心跳每 10 秒一次（QoS 0），**30 秒沒收到平台會判定離線**：

```json
// topic: edge/REACH01/heartbeat
{
  "device_uuid": "REACH01",
  "timestamp": "2026-09-29T09:00:10+08:00",
  "cpu_usage": 35.2,
  "memory_usage": 61.0,
  "gpu_usage": 42.0,
  "gpu_memory_usage": 30.5,
  "temperature": 63.0,
  "agent_version": "reach-office-vision/2.0.0",
  "hostname": "reach-office",
  "ip_address": "192.168.0.50",
  "gpu_name": "NVIDIA RTX A2000",
  "gpu_memory": 6144
}
```

必填：`device_uuid`、`cpu_usage`、`memory_usage`（0~100）、`agent_version`。GPU 欄位可用 `nvidia-smi` 取得，取不到就省略。

## 6. 攝影機狀態（3.4）

每 5 秒、每支攝影機一則（QoS 0）：

```json
// topic: edge/REACH01/cameras/bimer-back-left/status
{
  "camera_id": "bimer-back-left",
  "timestamp": "2026-09-29T09:00:05+08:00",
  "rtsp_status": "online",
  "ai_status": "running",
  "stream_status": "streaming",
  "input_fps": 25.0,
  "inference_fps": 8.0,
  "output_fps": 15.0,
  "resolution": "1920x1080",
  "last_frame_at": "2026-09-29T09:00:05+08:00",
  "dropped_frames": 0,
  "error": null
}
```

| 欄位 | 允許值 | 對應 REACH |
|------|--------|-----------|
| `rtsp_status` | `connecting` / `online` / `offline` / `error` | CameraStream：重連中 / 有新影格 / 停止 / 連續失敗 |
| `ai_status` | `disabled` / `loading` / `running` / `error` | YOLO 未啟用 / 載入模型中 / 推論中 / 推論失敗 |
| `stream_status` | `offline` / `connecting` / `streaming` / `error` | 本模組推流狀態 |
| `error` | 字串或 `null` | 最近一次錯誤摘要（**不得含帳密**） |

## 7. 即時辨識畫面（3.5）

**內容**：就是 REACH 給 MJPEG / `latest.jpg` 的那張**已畫框、已畫 ROI** 的畫面。

**推流目標**：

```text
RTSP：rtsp://<AIVMS_DEVICE_ID>:<AIVMS_DEVICE_KEY>@<平台IP>:8554/<stream_path>
SRT ：srt://<平台IP>:8890?streamid=publish:<stream_path>:<AIVMS_DEVICE_ID>:<AIVMS_DEVICE_KEY>&pkt_size=1316
```

帳號、金鑰需 URL encode。log 中只能印出遮蔽後的網址（例如 `rtsp://***@host:8554/<stream_path>`）。

**實作要求**：

1. 每支攝影機一個推流執行緒，與推論執行緒分開。
2. `publish_frame()` 只把影格放進**容量 2 的佇列，滿了丟最舊的**，立即返回。
3. 推流執行緒依 `AIVMS_STREAM_FPS` 取最新影格送給 ffmpeg；沒有新影格時重送上一張，維持固定 FPS。
4. 依 `AIVMS_STREAM_WIDTH` 縮放（等比例，寬高取偶數）。
5. ffmpeg 參數參考：

```bash
ffmpeg -loglevel warning -f rawvideo -pix_fmt bgr24 -s {W}x{H} -r {FPS} -i - -an \
  -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p \
  -g {FPS*2} -bf 0 -b:v {BITRATE} -maxrate {BITRATE} -bufsize {BITRATE} \
  -f rtsp -rtsp_transport tcp "{TARGET}"
# NVENC：-c:v h264_nvenc -preset p4 -tune ll -bf 0；無法啟動時自動退回 libx264
```

6. ffmpeg 結束或寫入失敗：視為斷線，依 **1 / 2 / 5 / 10 / 30 秒**退避重連；穩定 30 秒後退避歸零。
7. 影格尺寸改變時重啟 ffmpeg。
8. **不得**把影像用 MQTT、Base64、WebSocket 傳給平台。

## 8. 事件（3.6）

### 8.1 送哪些事件

| 時機（REACH 狀態機） | `event_type` | `status` | `severity` |
|----------------------|--------------|----------|------------|
| 達到 `AWAY`（≥ 3 秒確認，`daily_count += 1`） | `office.leave` | `open` | `warning` |
| `RETURNED`（回座確認） | `office.leave` | `returned` | `info` |
| 跨過下班 / 午休規則自動結束 | `office.leave` | `auto_closed` | `info` |
| 事件被取消 | `office.leave` | `cancelled` | `info` |

- **Candidate 狀態（`FRONT_LEAVE_CANDIDATE`、`AWAY_CANDIDATE`、`RETURN_CANDIDATE`）不送**，只送正式事件。
- 其他 REACH 想回報的內容也可以送，`event_type` 自訂即可，平台不需修改，例如：
  - `office.phone`：座位 ROI 出現手機
  - `system.camera_offline` / `system.camera_online`：攝影機斷線 / 恢復（`camera_id` 填該攝影機）

### 8.2 事件格式

同一個離席事件的所有狀態，**都用同一個 `event_id`（= REACH 的 `event_uuid`）**。
平台收到相同 `event_id` 會**更新**同一筆：只覆蓋這次有送的欄位，`data` 會合併，第一次的 `timestamp` 保留。

**離席成立**（`AWAY`）：

```json
// topic: edge/REACH01/cameras/bimer-back-left/logs   （QoS 1）
{
  "event_id": "3f0c2b1e-8a5d-4c1e-9b7a-2d4f6e8a1c3b",
  "device_id": "REACH01",
  "camera_id": "bimer-back-left",
  "timestamp": "2026-09-29T09:15:10+08:00",
  "event_type": "office.leave",
  "severity": "warning",
  "status": "open",
  "message": "S01 離席（今日第 3 次）",
  "data": {
    "event_date": "2026-09-29",
    "seat_id": "S01",
    "employee_id": "E001",
    "daily_sequence": 3,
    "session": "morning",
    "leave_time": "2026-09-29T09:15:10+08:00",
    "confirmed_at": "2026-09-29T09:15:13+08:00",
    "front_camera_id": "bimer-entrance-right",
    "rear_camera_id": "bimer-back-left"
  },
  "detections": [
    { "class_id": 0, "class_name": "person", "confidence": 0.91, "track_id": 17,
      "bbox": { "x1": 320, "y1": 180, "x2": 560, "y2": 540 } }
  ],
  "frame": { "width": 1920, "height": 1080 },
  "snapshot_key": "<見第 9 節，選用>"
}
```

**回座**：

```json
{
  "event_id": "3f0c2b1e-8a5d-4c1e-9b7a-2d4f6e8a1c3b",
  "device_id": "REACH01",
  "camera_id": "bimer-back-left",
  "event_type": "office.leave",
  "severity": "info",
  "status": "returned",
  "message": "S01 回座，離席 00:05:21",
  "data": {
    "return_time": "2026-09-29T09:20:31+08:00",
    "away_seconds": 321
  }
}
```

### 8.3 欄位規則

| 欄位 | 規則 |
|------|------|
| `event_id` | 必填。英數與 `. _ : -`，≤ 64 字。使用 `event_uuid` |
| `device_id` | 必填。必須等於 topic 中的裝置 ID |
| `camera_id` | 填**確認該事件的攝影機**（建議後置 `bimer-back-left`）；兩支都要記錄時放在 `data` |
| `timestamp` | **= `leave_time`（第一次離開時間），不是 `confirmed_at`**，與 REACH 規格第 10 節一致 |
| `event_type` | 英數與 `. _ : -`，≤ 64 字 |
| `severity` | `debug` / `info` / `warning` / `error` / `critical` |
| `status` | ≤ 32 字 |
| `message` | 給人看的一行文字，≤ 1000 字 |
| `data` | 任意 JSON，≤ 64 KB。`away_seconds` 依 REACH 規格只算有效工作時間 |
| `detections` | 選用。`bbox` 為像素座標，需同時送 `frame`；若用 0~1 正規化座標則不送 `frame` |
| 員工姓名 | 只有 `AIVMS_SEND_EMPLOYEE_NAME=true` 時才放進 `data.employee_name` |

整則訊息 ≤ 256 KB。

### 8.4 可靠性

- QoS 1。平台以 `event_id` 去重，重送不會重複計算。
- MQTT 斷線期間的事件放在本地佇列（上限 1000 則，滿了丟最舊並記 warning），重連後依序補送。
- **每次（重）連線成功後，重送所有目前 `open` 的事件**一次，確保平台狀態與 REACH 一致。

## 9. 快照（3.7，選用）

事件成立（`open`）時附一張已畫框的 JPEG：

```http
POST {AIVMS_API_URL}/edge/snapshots/presign
X-Device-Key: ...
Content-Type: application/json

{"camera_code": "bimer-back-left"}
```

回應：

```json
{"object_key": "2026/09/29/REACH01/.../xxxx.jpg", "upload_url": "http://...", "expires_in": 300}
```

對 `upload_url` 做 `PUT`（`Content-Type: image/jpeg`，body 為 JPEG bytes），成功後把 `object_key` 填入事件的 `snapshot_key`。

- 快照上傳失敗**不可**阻擋事件送出：直接送不含 `snapshot_key` 的事件。
- 上傳在 bridge 的執行緒內進行，不得在 REACH 主流程中等待。

## 10. 錯誤處理

| 狀況 | 處理 |
|------|------|
| HTTP 401 | 裝置金鑰錯誤：記 error（不印金鑰），每 60 秒重試 |
| HTTP 404（presign） | 攝影機未登記：重新執行第 4 節登記 |
| HTTP 5xx / 連線失敗 | 1/2/5/10/30 秒退避重試 |
| MQTT 連不上 / 斷線 | paho 自動重連；事件進本地佇列（第 8.4 節） |
| ffmpeg 啟動失敗 / 中斷 | 退避重連；連續失敗時 `stream_status: error` 並附錯誤摘要 |
| 推流被拒（401） | 檢查 `stream_path` 與金鑰；不要改用其他路徑 |

## 11. 測試要求

**單元測試**（不需連平台）：

- [ ] REACH 離席事件 → 平台 JSON 的轉換（`open` / `returned` / `auto_closed` / `cancelled`）
- [ ] `timestamp` = `leave_time`，不是 `confirmed_at`
- [ ] `AIVMS_SEND_EMPLOYEE_NAME=false` 時 payload 不含姓名
- [ ] URL 遮蔽：log 字串不含金鑰、密碼
- [ ] 佇列滿時丟最舊、`publish_frame()` / `report_event()` 不阻塞
- [ ] 退避序列為 1, 2, 5, 10, 30, 30…
- [ ] `AIVMS_ENABLED=false` 或缺設定時模組不啟動、不拋例外

**整合測試**（連平台測試環境）：見下一節驗收清單。

## 12. 驗收清單

### 連線

- [ ] 啟用後平台「邊緣裝置」看到 `REACH01` **在線**，CPU / 記憶體 / GPU 有數值
- [ ] 停止 REACH 服務後 30 秒內平台顯示**離線**；重啟後恢復在線
- [ ] 平台「攝影機」看到 `bimer-entrance-right`、`bimer-back-left`，顯示「來源由 Edge 管理」

### 即時畫面

- [ ] 平台「即時監看」兩支攝影機都有**畫框後**的畫面，延遲 < 3 秒（WebRTC）
- [ ] 拔掉平台網路 1 分鐘再恢復：畫面自動恢復，REACH 本身畫面與辨識不受影響
- [ ] 攝影機狀態顯示 RTSP / AI / 串流狀態與 FPS

### 事件

- [ ] 離席 ≥ 3 秒：平台「Edge 紀錄」出現 `office.leave [open]`，`timestamp` = 第一次離開時間
- [ ] 回座：**同一筆**變成 `[returned]`，`data` 同時有 `leave_time` 與 `return_time`、`away_seconds`
- [ ] 離席 < 3 秒：平台**不**出現事件
- [ ] 午休跨界：與 REACH 自己的紀錄一致，不重複
- [ ] 平台事件數 = REACH `office_leave_events` 同期筆數
- [ ] 平台斷線期間發生的事件，恢復後補到平台且不重複
- [ ] （若啟用快照）事件可看到快照且框位置正確

### 不影響 REACH

- [ ] `AIVMS_ENABLED=false` 時 REACH 行為、效能與現在相同
- [ ] 平台完全斷線時，REACH 的 RTSP、YOLO、Dashboard、事件、日報全部正常
- [ ] REACH 的 log、Git、前端 API 中查不到裝置金鑰、MQTT 密碼、攝影機帳密

## 13. 建議開發順序

1. 設定讀取 + 開關（`aivms_config.py`），預設關閉
2. MQTT 連線、LWT、心跳、攝影機狀態
3. 攝影機登記 + 推流（先一支攝影機、libx264）
4. 事件轉換與送出（含斷線補送）
5. 快照（選用）
6. NVENC、SRT（選用）
7. 單元測試 + 依第 12 節與我方一起驗收

## 附錄 A：參考實作

我方可提供可執行的參考程式 `generic_edge.py`（純 JSON + paho-mqtt + ffmpeg），
包含登記、心跳、狀態、推流、事件（含同一 `event_id` 更新）與快照上傳的完整流程，已實測可串接平台。

## 附錄 B：JSON Schema

| 內容 | Schema 檔 |
|------|-----------|
| 事件 | `edge_log.schema.json` |
| 心跳 | `heartbeat.schema.json` |
| 上線狀態 | `device_status.schema.json` |
| 攝影機狀態 | `camera_status.schema.json` |

（由我方一併提供；未列出的欄位平台會忽略。）
