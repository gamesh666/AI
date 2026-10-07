# 第三方 Edge 串接規格（平台只接收、只顯示）

平台**不做任何辨識**。每台 Edge 自己拉攝影機、自己跑 AI（YOLO、離席判斷、安全帽、任何模型都可以），
然後把兩樣東西送到平台：

| 送什麼 | 怎麼送 | 平台做什麼 |
|--------|--------|------------|
| **辨識結果 / LOG**（任何內容） | MQTT JSON | 存進 PostgreSQL、即時推到網頁、可篩選搜尋 |
| **即時辨識畫面**（已畫好框的影像） | H.264 RTSP（或 SRT）推到 MediaMTX | 瀏覽器用 WebRTC 播放，失敗自動改 HLS |
| 裝置 / 攝影機健康狀態（建議） | MQTT JSON | 顯示在線 / 離線、FPS、串流狀態 |

平台不解讀 `event_type` 與 `data` 的內容，所以 Edge 之後改辨識項目，平台**不用改程式**。

可直接執行的參考實作：[`examples/third-party-edge/generic_edge.py`](../examples/third-party-edge/generic_edge.py)
（只用 JSON + paho-mqtt + ffmpeg，不依賴本平台的 edge-agent）。

---

## 0. 在平台上建立 Edge（一次）

管理員在網頁 **邊緣裝置 → + 新增裝置**，填裝置 ID（例如 `REACH01`）並選場域，
畫面會跳出 **裝置連線資訊**：API 金鑰（只顯示這一次）＋整份可直接貼上的設定（env 格式，含 MQTT 帳密、
推流位址、topics、需要開通的連線），按「複製全部」或「下載 .env」交給 Edge 端即可。
上方可切換「第三方 Edge」（`AIVMS_*`）與「AIVMS edge-agent」（`EDGE_*`）兩種格式。

之後要再傳一次：admin 在裝置列按 **連線資訊**（金鑰欄會是 `<DEVICE_KEY>`，金鑰遺失請按「更換金鑰」）。
MQTT 密碼只顯示給 admin；operator 建立裝置時該欄會提示向管理員索取。

Edge 端需要的設定：

| 設定 | 範例 | 來源 |
|------|------|------|
| 平台 API | `http://<平台IP>:8000/api/v1` | |
| 裝置 ID | `REACH01` | 上一步 |
| 裝置 API 金鑰 | `EDGE_DEVICE_KEY` | 上一步（只顯示一次） |
| MQTT 帳密 | `.env` 的 `MQTT_EDGE_USERNAME` / `MQTT_EDGE_PASSWORD` | 平台管理員 |

所有 REST 呼叫都帶 header `X-Device-Key: <API 金鑰>`。

## 1. 宣告攝影機（Edge 自己管理來源）

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

也可以由管理員在網頁「攝影機」頁新增，RTSP URL 留空即可。

## 2. 即時辨識畫面

把**已經畫好框**的畫面編成 H.264 推到：

```
rtsp://<裝置ID>:<API金鑰>@<平台IP>:8554/<stream_path>
```

- 帳號 = 裝置 ID、密碼 = API 金鑰；平台只允許 Edge 推到**自己的**攝影機路徑。
- 建議：H.264、yuv420p、GOP = 2 秒、不含 B-frame（`-tune zerolatency`），720p 約 1~2 Mbps。
- 跨網際網路可改用 SRT：`srt://<平台IP>:8890?streamid=publish:<stream_path>:<裝置ID>:<API金鑰>`。
- **不要**把影像用 MQTT / Base64 / WebSocket 傳。

OpenCV 範例（把每張畫好框的 frame 丟給 ffmpeg）：

```python
ff = subprocess.Popen(["ffmpeg", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", "15", "-i", "-",
                       "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
                       "-g", "30", "-f", "rtsp", "-rtsp_transport", "tcp", target_url], stdin=subprocess.PIPE)
ff.stdin.write(annotated_frame.tobytes())   # 每一張
```

## 3. 辨識結果 / LOG

**Topic**：`edge/{裝置ID}/cameras/{camera_code}/logs`（跟某支攝影機有關）
或 `edge/{裝置ID}/logs`（整台 Edge 的事）。QoS 1。

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
| `device_id` | ✅ | 必須與 topic 中的裝置 ID 相同 |
| `event_type` | ✅ | 自訂，英數與 `. _ : -`，最多 64 字。例如 `office.leave`、`ppe.no_helmet` |
| `event_id` | | 自訂唯一 ID（英數與 `. _ : -`，≤ 64 字）；不給則自動產生 |
| `camera_id` | | 攝影機代碼；用 camera topic 時可省略 |
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

`system.connection` 與 `system.platform` 是平台自己寫的連線紀錄（斷線 / 恢復、平台啟動 / 停止），
Edge 送這兩種類型會被丟棄；其他 `system.*`（例如 `system.camera_offline`）可以正常使用。

整則 MQTT 訊息上限 256 KB；格式錯誤、裝置 ID 不符、未註冊的裝置會被丟棄並記在平台 log。

### 快照上傳（選用）

```http
POST /api/v1/edge/snapshots/presign
X-Device-Key: ...
{"camera_code": "bimer-back-left"}
```

回應 `{ "object_key": "...", "upload_url": "...", "expires_in": 300 }`，
對 `upload_url` 做 HTTP `PUT`（`Content-Type: image/jpeg`），再把 `object_key` 放進 LOG 的 `snapshot_key`。

## 4. 健康狀態（建議）

| Topic | 頻率 | 內容 |
|-------|------|------|
| `edge/{裝置ID}/heartbeat` | 每 10 秒 | `{"device_uuid","cpu_usage","memory_usage","agent_version", ...}`；30 秒沒收到視為離線 |
| `edge/{裝置ID}/status` | 連線時、retained，並設為 MQTT Last Will | `{"device_uuid","state":"online"}` / `"offline"` |
| `edge/{裝置ID}/cameras/{code}/status` | 每 5 秒 | `{"camera_id","rtsp_status","ai_status","stream_status","input_fps","inference_fps","output_fps","resolution"}` |

完整欄位見 [`shared/python/aivms_shared/payloads.py`](../shared/python/aivms_shared/payloads.py)，
Python Edge 也可以直接 `pip install` 這個套件使用同一份資料模型。

## 5. 驗證

```bash
# 在可以連到平台的機器上
EDGE_API_URL=http://<平台IP>:8000/api/v1 EDGE_DEVICE_ID=REACH01 EDGE_DEVICE_KEY=... \
EDGE_MQTT_USERNAME=... EDGE_MQTT_PASSWORD=... \
EDGE_CAMERAS="bimer-entrance-right:BIMer 大門右側,bimer-back-left:BIMer 後左" \
python examples/third-party-edge/generic_edge.py
```

網頁上應看到：邊緣裝置 `REACH01` 在線、兩支攝影機在「即時監看」有畫面、
「Edge 紀錄」頁持續出現新紀錄，`office.leave` 會從 `open` 變成 `returned`。

## 已知限制

- MQTT 目前所有 Edge 共用一組帳密（ACL 允許寫 `edge/#`）。平台會檢查 payload 與 topic 的裝置 ID 一致，
  但無法防止持有這組帳密的程式冒充其他 Edge。正式上線、串接外部廠商前，建議改為**每台 Edge 各自的 MQTT 帳密**
  （例如換 EMQX 並用 HTTP 認證對接平台的裝置金鑰）。
- LOG 目前永久保存；量大時需要加保存天數或分區。
