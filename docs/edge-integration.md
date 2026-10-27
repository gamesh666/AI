# Edge 串接規格（平台只接收、只顯示）

平台**不做任何辨識**。每台 Edge 自己拉攝影機、自己跑 AI（YOLO、離席判斷、安全帽、任何模型都可以），
然後把兩樣東西送到平台：

| 送什麼 | 怎麼送 | 平台做什麼 |
|--------|--------|------------|
| **辨識結果 / LOG**（任何內容） | HTTP POST JSON | 存進 PostgreSQL、即時推到網頁、可篩選搜尋 |
| **即時辨識畫面**（已畫好框的影像） | H.264 RTSP（或 SRT）推到 MediaMTX | 瀏覽器用 WebRTC 播放，失敗自動改 HLS |
| 裝置 / 攝影機健康狀態 | HTTP POST JSON | 顯示在線 / 離線、FPS、串流狀態 |

所有連線都由 Edge **主動連出**。上線只需要業主的**佈建權杖**；註冊時平台自動發給每台自己的裝置金鑰（header `X-Device-Key`），由 Edge 保存，人不用經手，外流也只影響那一台。

平台不解讀 `event_type` 與 `data` 的內容，所以 Edge 之後改辨識項目，平台**不用改程式**。

可直接執行的參考實作：[`examples/edge-http/generic_edge.py`](../examples/edge-http/generic_edge.py)
（只用 Python 標準函式庫 + ffmpeg）。

---

## 0. 上線：只用佈建權杖

裝置**只能**用業主的佈建權杖自動註冊建立，平台網頁沒有手動新增裝置，也不會顯示或更換任何金鑰。

1. 管理員在「業主」頁替業主產生**佈建權杖**（只顯示一次），把兩行設定放進 AI BOX 出廠設定：

   ```bash
   AIBOX_API_URL=http://<平台IP>:8000
   AIBOX_PROVISIONING_TOKEN=aivms_pt_...
   ```

2. AI BOX 以 MAC 呼叫 `POST /api/v1/edge/register`（header `X-Provisioning-Token`），平台回傳：
   - `device_uuid`：平台編的裝置 ID（例如 `REACH01`）；
   - `api_key`：這台的裝置金鑰，**由 AI BOX 自己存起來**，之後所有呼叫都帶 `X-Device-Key: <api_key>`，
     RTSP / SRT 推流密碼也是它（帳號 = 裝置 ID）；
   - `site_id`、`site_profile`：業主 / 場域 / 合約資料。
3. 接著 `GET /api/v1/edge/config` 取得其餘所有設定（推流位址、HTTP 端點、心跳間隔、攝影機）。

金鑰遺失或要換新：AI BOX 再用**有效的**權杖註冊一次即可（同一個 MAC 沿用原 ID，舊金鑰立刻失效）。
權杖撤銷 5 分鐘後會從平台刪除；已註冊的裝置不受影響，但之後要重新註冊就需要新的權杖。

完整契約：[`docs/reach-edge-register/CLAUDE.md`](reach-edge-register/CLAUDE.md)，交付說明：
[`docs/reach-edge-register/DELIVERY.md`](reach-edge-register/DELIVERY.md)。

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

## 4c. 出勤事件報表（平台下單、Edge 產生 PDF）

平台「邊緣裝置 → 產生報表」的資料**全部來自 Edge 自己的資料庫**，PDF 也由 Edge 用自己的匯出功能產生，
平台只負責下單、收檔、提供下載。平台不連進 Edge：訂單放在心跳回應裡。

**① 送報表選項**（啟動時、員工 / 部門 / 工位有變動時；平台的下拉選單用它）

```http
PUT /api/v1/edge/report-options
X-Device-Key: ...

{"employees":   [{"id": "A001", "name": "王小明", "department": "業務部", "seat": "S01"}],
 "departments": [{"value": "業務部", "label": "業務部"}],
 "seats":       [{"value": "S01", "label": "S01 窗邊"}],
 "events":      [{"value": "away", "label": "離席"}],
 "statuses":    [{"value": "returned", "label": "已回座"}, {"value": "auto_closed", "label": "未確認回座"}]}
```

回 `204`。每次送整份（覆蓋上一次），上限 2 MB。

**② 心跳回應收到 `generate_report`**

```json
{"command_id": "…", "command": "generate_report", "params": {
  "report_id": "6f1c…", "kind": "attendance", "format": "pdf",
  "filters": {"employee_id": "A001", "department": null, "seat": null,
              "period": "yesterday", "start_date": "2026-10-26", "end_date": "2026-10-26",
              "event": null, "status": null, "attendance_status": "late_confirmed",
              "vlm": null, "review": null, "face": null},
  "upload": {"method": "PUT", "path": "/edge/reports/6f1c…/file", "content_type": "application/pdf", "max_bytes": 20971520},
  "status": {"method": "POST", "path": "/edge/reports/6f1c…/status"}}}
```

- `null` = 全部。`start_date` / `end_date` 以 Edge 當地日期為準，**照給的日期產生**（`period` 只是使用者按的快捷鍵）。
- `employee_id`、`department`、`seat`、`event`、`status` 是 ① 送來的 `id` / `value`。
- 固定代碼：

| 欄位 | 代碼 |
|---|---|
| `attendance_status` | `on_time` 準時到班、`late_pending_review` 遲到候選、`late_confirmed` 遲到已確認、`late_rejected` 遲到已駁回、`identity_conflict` 身分不一致、`not_arrived` 尚未到班、`normal_departure` 正常下班、`early_leave_pending_review` 早退候選、`early_leave_confirmed` 早退已確認、`early_leave_rejected` 早退已駁回、`not_judged` 尚未判定、`unverifiable` 無法確認 |
| `vlm` | `supported` 影像支持、`not_supported` 影像不支持、`undetermined` 無法判定、`model_unavailable` 模型無法使用、`disabled` 未啟用 |
| `review` | `pending` 待確認、`confirmed` 已確認、`rejected` 已駁回、`not_required` 不需審核 |
| `face` | `matched` 人臉相符、`unverified` 未驗證／不符 |

**③ 回報進度（選用）與上傳 PDF**

```http
POST /api/v1/edge/reports/{report_id}/status      {"state": "generating"}
POST /api/v1/edge/reports/{report_id}/status      {"state": "failed", "message": "查無資料庫連線"}

PUT  /api/v1/edge/reports/{report_id}/file
X-Device-Key: ...
Content-Type: application/pdf

<PDF 檔本身，≤ 20 MB>
```

上傳成功回 `200` 與報表資料（`status: "ready"`），平台網頁就出現「下載 PDF」。
別台裝置的 `report_id` 一律 `404`；不是 PDF 回 `422`；超過大小回 `413`。15 分鐘內沒完成，平台顯示「裝置未回應」
（之後仍可上傳）。裝置離線時訂單留在佇列（24 小時），連線後的心跳就會收到。

## 5. 驗證

```bash
# 在可以連到平台的機器上
EDGE_API_URL=http://<平台IP>:8000/api/v1 EDGE_PROVISIONING_TOKEN=aivms_pt_... EDGE_MAC=02:00:00:00:00:01 \
EDGE_CAMERAS="bimer-entrance-right:BIMer 大門右側,bimer-back-left:BIMer 後左" \
python examples/edge-http/generic_edge.py
```

網頁上應看到：邊緣裝置 `REACH01` 在線、兩支攝影機在「即時監看」有畫面、
「Edge 紀錄」頁持續出現新紀錄，`office.leave` 會從 `open` 變成 `returned`。

## 已知限制

- Edge 突然斷電時，平台在心跳停止 30 秒後判定離線並記錄斷線；正常關機時送 `{"state":"offline"}` 會立即顯示。
- 平台下的指令要等下一次心跳（最多 10 秒）才會送到。
- LOG 目前永久保存；量大時需要加保存天數或分區。
