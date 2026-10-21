# Edge 串接規格（平台只接收、只顯示）

平台**不做任何辨識**。每台 Edge 自己拉攝影機、自己跑 AI（YOLO、離席判斷、安全帽、任何模型都可以），
然後把兩樣東西送到平台：

| 送什麼 | 怎麼送 | 平台做什麼 |
|--------|--------|------------|
| **辨識結果 / LOG**（任何內容） | HTTP POST JSON | 存進 PostgreSQL、即時推到網頁、可篩選搜尋 |
| **即時辨識畫面**（已畫好框的影像） | H.264 RTSP（或 SRT）推到 MediaMTX | 瀏覽器用 WebRTC 播放，失敗自動改 HLS |
| 裝置 / 攝影機健康狀態 | HTTP POST JSON | 顯示在線 / 離線、FPS、串流狀態 |

所有連線都由 Edge **主動連出**，每台只用自己的**裝置金鑰**（header `X-Device-Key`），外流也只影響那一台。

平台不解讀 `event_type` 與 `data` 的內容，所以 Edge 之後改辨識項目，平台**不用改程式**。

可直接執行的參考實作：[`examples/edge-http/generic_edge.py`](../examples/edge-http/generic_edge.py)
（只用 Python 標準函式庫 + ffmpeg）。

---

## 0. 在平台上建立 Edge（一次）

管理員在網頁 **邊緣裝置 → + 新增裝置**，填裝置 ID（例如 `REACH01`）並選場域，
畫面會跳出 **裝置連線資訊**：API 金鑰（只顯示這一次）＋整份可直接貼上的設定（`AIBOX_*` env 格式，含 HTTP 端點、
推流位址、需要開通的連線），按「複製全部」或「下載 .env」交給 Edge 端即可。

之後要再傳一次：admin 在裝置列按 **連線資訊**（金鑰欄會是 `<DEVICE_KEY>`，金鑰遺失請按「更換金鑰」）。

Edge 端需要的設定：

| 設定 | 範例 | 來源 |
|------|------|------|
| 平台 API | `http://<平台IP>:8000/api/v1` | |
| 裝置 ID | `REACH01` | 上一步 |
| 裝置 API 金鑰 | `EDGE_DEVICE_KEY` | 上一步（只顯示一次） |

所有 REST 呼叫都帶 header `X-Device-Key: <API 金鑰>`。

### 0b. 自動註冊（REACH AI BOX 等出廠設備）

管理員在「業主」頁替業主產生**佈建權杖**（只顯示一次）放進設備出廠設定；設備以 MAC 呼叫
`POST /api/v1/edge/register` 自動註冊、取得 device_uuid 與金鑰，並帶回業主 / 場域 / 合約資料（`site_profile`）。
完整契約：[`docs/reach-edge-register/CLAUDE.md`](reach-edge-register/CLAUDE.md)，交付說明：
[`docs/reach-edge-register/DELIVERY.md`](reach-edge-register/DELIVERY.md)。

已經手動建立的裝置：在裝置的「編輯」填入設備 MAC（並選業主），設備自動綁定時就會沿用原本的 ID，不會重複建立。

## 1. 宣告攝影機（Edge 自己管理來源）

**建議：同步完整清單**（Edge 啟動時、攝影機有增減時呼叫一次）

```http
PUT /api/v1/edge/cameras
X-Device-Key: ...
Content-Type: application/json

{"cameras": [{"code": "bimer-entrance-right", "name": "BIMer 大門右側"},
             {"code": "bimer-back-left", "name": "BIMer 後左"}]}
```

回應：

```json
{ "cameras": [ { "camera_id": "bimer-entrance-right", "stream_path": "ai/bimer-office/REACH01/bimer-entrance-right", ... } ],
  "added": [], "restored": [], "missing": ["old-cam"] }
```

- 清單裡有、平台沒有 → 自動新增（`added`）。
- 平台上有、但這次清單沒有的 **Edge 自管攝影機** → **停用並標示「已不在 Edge 上」，不會刪除**（`missing`），歷史資料保留；
  之後清單再出現就自動恢復啟用（`restored`）。
- 每次有變動，平台會在「Edge 紀錄」寫一筆 `system.camera_sync`。
- 送空清單 `{"cameras": []}` 代表這台 Edge 目前沒有任何攝影機（全部會被停用）。

**也可以一支一支登記**（只新增 / 更新，不會停用其他攝影機）：

```http
PUT /api/v1/edge/cameras/{camera_code}
X-Device-Key: ...
Content-Type: application/json

{"name": "BIMer 後左"}
```

- `camera_code`：英數、`-`、`_`，2~32 字，例如 `bimer-back-left`。同一台 Edge 內唯一。
- 可重複呼叫（不存在就建立，存在就更新名稱）。
- 攝影機的 RTSP 位址與帳密**完全不用給平台**，平台上會顯示「來源由 Edge 管理」。
- 回應裡的 `stream_path`（例如 `ai/bimer-office/REACH01/bimer-back-left`）就是影像要推的路徑。

## 2. 即時辨識畫面

把**已經畫好框**的畫面編成 H.264 推到：

```
rtsp://<裝置ID>:<API金鑰>@<平台IP>:8554/<stream_path>
```

- 帳號 = 裝置 ID、密碼 = API 金鑰；平台只允許 Edge 推到**自己的**攝影機路徑。
- 建議：H.264、yuv420p、GOP = 2 秒、不含 B-frame（`-tune zerolatency`），720p 約 1~2 Mbps。
- 跨網際網路可改用 SRT：`srt://<平台IP>:8890?streamid=publish:<stream_path>:<裝置ID>:<API金鑰>`。
- **不要**把影像用 Base64 / WebSocket / HTTP 一張張傳。

OpenCV 範例（把每張畫好框的 frame 丟給 ffmpeg）：

```python
ff = subprocess.Popen(["ffmpeg", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", "15", "-i", "-",
                       "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
                       "-g", "30", "-f", "rtsp", "-rtsp_transport", "tcp", target_url], stdin=subprocess.PIPE)
ff.stdin.write(annotated_frame.tobytes())   # 每一張
```

## 3. 辨識結果 / LOG

```http
POST /api/v1/edge/logs
X-Device-Key: <裝置金鑰>
Content-Type: application/json

{ ...一筆 LOG... }            或   [ {...}, {...} ]   （一次最多 100 筆）
```

- 一筆：成功回 `200 {"event_id": "...", "camera_id": "..."}`；失敗回 4xx `{"detail": "原因"}`，**不要原封不動重送**。
- 多筆：一律回 `200 {"accepted": [{"event_id", "camera_id"}], "rejected": [{"index", "detail"}]}`，
  某一筆被拒不影響其他筆。適合斷線後補送累積的紀錄。
- `device_id` 可以不填（由金鑰決定）；有填就必須和金鑰的裝置相同，否則 `403`。
- 跟攝影機有關的紀錄把攝影機代碼放在 `camera_id`。
- 平台無法連線（逾時、5xx）時請在 Edge 端暫存，恢復後再送（同一個 `event_id` 重送不會重複）。

一筆 LOG 的內容：

```json
{
  "event_id": "leave-20260930-S01-3",
  "device_id": "REACH01",
  "camera_id": "bimer-back-left",
  "timestamp": "2026-09-30T09:15:10+08:00",
  "event_type": "office.leave",
  "severity": "warning",
  "status": "open",
  "message": "S01 王小明 離席",
  "data": { "seat_id": "S01", "employee_id": "E001", "leave_time": "09:15:10", "confirmed_at": "09:15:13" },
  "detections": [
    { "class_id": 0, "class_name": "person", "confidence": 0.91, "track_id": 17,
      "bbox": { "x1": 320, "y1": 180, "x2": 560, "y2": 540 } }
  ],
  "frame": { "width": 1280, "height": 720 },
  "snapshot_key": "2026/09/30/REACH01/<camera-uuid>/<id>.jpg"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `device_id` | | 不填 = 金鑰的裝置；有填就必須相同 |
| `event_type` | ✅ | 自訂，英數與 `. _ : -`，最多 64 字。例如 `office.leave`、`ppe.no_helmet` |
| `event_id` | | 自訂唯一 ID（英數與 `. _ : -`，≤ 64 字）；不給則自動產生 |
| `camera_id` | | 攝影機代碼（跟某支攝影機有關的紀錄才填） |
| `timestamp` | | 事件發生時間（ISO 8601，建議帶時區）；不給 = 收到時間 |
| `severity` | | `debug` / `info`（預設）/ `warning` / `error` / `critical` |
| `status` | | 自訂狀態，≤ 32 字，例如 `open`、`returned` |
| `message` | | 給人看的一行文字，≤ 1000 字 |
| `data` | | **任意 JSON**（≤ 64 KB），平台原樣保存與顯示 |
| `detections` | | 框（像素座標，搭配 `frame`；或 0~1 正規化座標、不送 `frame`），會畫在快照上 |
| `snapshot_key` | | 見下方快照上傳 |

**更新同一筆事件**：用相同 `event_id` 再送一次。只會覆蓋這次有送的欄位，`data` 會合併，
第一次的 `timestamp` 保留。例如離席時送 `status: "open"`，回座時再送：

```json
{ "event_id": "leave-20260930-S01-3", "device_id": "REACH01", "event_type": "office.leave",
  "status": "returned", "severity": "info", "data": { "return_time": "09:20:31", "away_seconds": 321 } }
```

`system.connection`、`system.platform`、`system.camera_sync` 是平台自己寫的紀錄（斷線 / 恢復、平台啟動 / 停止、攝影機清單變動），
Edge 送這三種類型會被丟棄；其他 `system.*`（例如 `system.camera_offline`）可以正常使用。

一次請求上限 256 KB。格式不對會直接回 `422 {"detail": "原因"}`。

### 快照上傳（選用）

```http
POST /api/v1/edge/snapshots/presign
X-Device-Key: ...
{"camera_code": "bimer-back-left"}
```

回應 `{ "object_key": "...", "upload_url": "...", "expires_in": 300 }`，
對 `upload_url` 做 HTTP `PUT`（`Content-Type: image/jpeg`），再把 `object_key` 放進 LOG 的 `snapshot_key`。

## 4. 健康狀態（建議）

都帶 `X-Device-Key`：

| 端點 | 頻率 | 內容 |
|------|------|------|
| `POST /api/v1/edge/heartbeat` | 每 10 秒 | `{"cpu_usage","memory_usage","agent_version", "models": [...], ...}`（`device_uuid` 可省略）；30 秒沒收到視為離線。回應見 4b |
| `POST /api/v1/edge/cameras/{code}/status` | 每 5 秒 | `{"rtsp_status","ai_status","stream_status","input_fps","inference_fps","output_fps","resolution"}`；未登記的攝影機回 `404` |
| `POST /api/v1/edge/status` | 正常關機時 | `{"state":"offline"}`，平台立即顯示離線（不送也會在 30 秒後判定離線） |

### 4b. 心跳回應：平台要告訴 Edge 的事

平台要給 Edge 的指令與設定變更，放在**心跳的回應**裡：

```json
{
  "config_version": 1791800049,
  "commands": [
    { "command_id": "d9e75f7f-...", "command": "reload_config", "params": {}, "issued_at": "2026-10-12T10:14:08Z" }
  ],
  "mqtt_enabled": false,
  "server_time": "2026-10-12T10:14:09Z"
}
```

| 欄位 | Edge 要做的事 |
|------|---------------|
| `config_version` | 跟上一次回應的值不同 → 重新 `GET /api/v1/edge/config`（平台上改了攝影機名稱、場域等）。第一次收到只記下來 |
| `commands` | 依序執行（`reload_config` / `restart_camera` / `ping`），每個指令只會送一次；不認得的指令略過 |
| `mqtt_enabled` | 固定 `false`（舊欄位，可忽略） |
| `server_time` | 可用來檢查 Edge 時鐘是否偏差 |

**回報正在使用的模型**（建議）：心跳加上 `models`，平台「AI 模型」頁會列出每個模型在哪些 Edge、哪些攝影機使用，
並標出同一模型在不同 Edge 版本不一致的情況：

```json
"models": [
  { "name": "yolo11n", "version": "2026.09", "type": "yolo11", "task": "person / cell phone",
    "labels": ["person", "cell phone"], "cameras": ["bimer-entrance-right", "bimer-back-left"] }
]
```

`name` 必填，其餘選填。`cameras` 為使用此模型的攝影機代碼；只有一個模型且不填 `cameras` 時視為全部攝影機都用它。
不送 `models` = 沿用上次回報；送 `[]` = 目前沒有模型在跑。

完整欄位見 [`shared/python/aivms_shared/payloads.py`](../shared/python/aivms_shared/payloads.py)，
Python Edge 也可以直接 `pip install` 這個套件使用同一份資料模型。

## 5. 驗證

```bash
# 在可以連到平台的機器上
EDGE_API_URL=http://<平台IP>:8000/api/v1 EDGE_DEVICE_ID=REACH01 EDGE_DEVICE_KEY=... \
EDGE_CAMERAS="bimer-entrance-right:BIMer 大門右側,bimer-back-left:BIMer 後左" \
python examples/edge-http/generic_edge.py
```

網頁上應看到：邊緣裝置 `REACH01` 在線、兩支攝影機在「即時監看」有畫面、
「Edge 紀錄」頁持續出現新紀錄，`office.leave` 會從 `open` 變成 `returned`。

## 已知限制

- Edge 突然斷電時，平台在心跳停止 30 秒後判定離線並記錄斷線；正常關機時送 `{"state":"offline"}` 會立即顯示。
- 平台下的指令要等下一次心跳（最多 10 秒）才會送到。
- LOG 目前永久保存；量大時需要加保存天數或分區。
