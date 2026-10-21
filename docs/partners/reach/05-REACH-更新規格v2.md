# REACH 更新規格 v2：改走 HTTP、平台更名、統一紀錄規範

> 對象：REACH Office Vision 的平台串接模組（現有 `app/integrations/aivms_*.py`）。
> 本文件**取代** 04 號文件，並補充 02 號規格；兩者衝突時以本文件為準。
> 平台名稱自本版起為 **AIBOX SERVER**。REACH 定位為**自家邊緣設備**，往後所有新設備也照本規格。

## 目錄

| # | 項目 | REACH 是否要改 | 優先 |
|---|------|----------------|------|
| 1 | 平台更名、設定改名 `AIBOX_*` | 要（小） | P1 |
| 2 | 心跳、狀態、事件改走 HTTP | 要（主要工作） | **P0** |
| 3 | 心跳回應：指令與設定變更 | 要 | **P0** |
| 4 | 開機與金鑰流程（含 MAC 自動綁定） | 確認／小改 | P1 |
| 5 | 攝影機清單同步 | 確認 | P1 |
| 6 | 紀錄（事件）規範與建議新增的營運紀錄 | 要（小） | P1 |
| 7 | 心跳內容：模型回報必填 | 確認 | P1 |
| 8 | 時間 | 確認 | P2 |
| 9 | 安全與 HTTPS 準備 | 要（小） | P1 |
| 10 | 測試、驗收、回報 | — | — |

**重要**：平台已**移除 MQTT**，只接受 HTTP。尚未更新的 REACH 會無法回報心跳與紀錄（平台上顯示離線），
即時影像（RTSP 推流）不受影響。請優先完成第 2、3 節。設定名稱只有 REACH 自己讀，改名不影響平台。

---

## 1. 平台更名與設定改名（P1）

平台名稱改為 **AIBOX SERVER**。設定檔變數前綴由 `AIVMS_` 改為 `AIBOX_`：

```bash
# /etc/reach-ai-office-vision/office-vision.env（權限 640）
AIBOX_ENABLED=true
AIBOX_API_URL='http://192.168.0.179:8000/api/v1'   # 正式環境會改 https://，見第 9 節
AIBOX_DEVICE_ID='REACH01'
AIBOX_DEVICE_KEY='<平台提供，只顯示一次>'
AIBOX_STREAM_URL='rtsp://192.168.0.179:8554'
AIBOX_CA_FILE=                        # 新增：自簽憑證時的 CA 檔路徑，見第 9 節
AIBOX_PROVISIONING_TOKEN=             # MAC 自動綁定用（出廠設定），見第 4 節
# 其餘 02 號規格的 AIVMS_STREAM_* / AIVMS_VIDEO_ENCODER / AIVMS_SEND_* 一律改成 AIBOX_ 開頭，意義不變
# 所有 AIVMS_MQTT_* 設定刪除（平台已無 MQTT）
```

**相容規則**：

- 讀設定時先讀 `AIBOX_xxx`，沒有才讀 `AIVMS_xxx`。
- 用到舊名時，啟動時記一行 warning：「請改用 `AIBOX_xxx`」。
- 舊名至少支援到下一個大版本。
- 平台「連線資訊」從現在起輸出 `AIBOX_*`，可直接貼上。

以下可以不改：

- 模組檔名（`aivms_bridge.py` 等）可以維持，改成 `aibox_*` 也可以，平台不在意。
- 畫面、log 中出現的「AIVMS」請改成「AIBOX SERVER」。
- 心跳的 `agent_version` 格式維持 `reach-office-vision/<版本>`，每次發版都要更新版本號，平台據此判斷各台是否已更新。

## 2. 心跳、狀態、事件改走 HTTP（P0）

### 2.1 為什麼

目前所有設備共用一組 MQTT 帳密，外流就能冒充任何一台設備。改用 HTTP 後：

- 每台只用自己的裝置金鑰（`X-Device-Key`），外流只影響那一台，平台按「更換金鑰」即可作廢。
- REACH 不再需要 MQTT 帳密，也不用連 1883 埠。
- 平台會直接回應錯誤原因。用 MQTT 送錯時，平台只能默默丟棄。

**只改「怎麼送」，JSON 內容與 02 號規格相同。** 影像推流（RTSP / SRT）與快照上傳都不變。

### 2.2 對照表

| 項目 | 原本（MQTT） | 改成（HTTP） |
|------|--------------|--------------|
| 上線 / 離線 | `edge/{device}/status`（retained + Last Will） | `POST /edge/status`，見 2.4 |
| 心跳（10 秒） | `edge/{device}/heartbeat` | `POST /edge/heartbeat`，**要處理回應**（第 3 節） |
| 攝影機狀態（5 秒） | `edge/{device}/cameras/{code}/status` | `POST /edge/cameras/{code}/status` |
| 事件 / 紀錄 | `edge/{device}/cameras/{code}/logs` | `POST /edge/logs`（一筆或一次最多 100 筆） |
| 平台下指令、設定變更 | MQTT 推送 | 心跳回應帶回（第 3 節） |

- 網址：`{AIBOX_API_URL}` + 路徑。
- 每個請求帶 `X-Device-Key: <AIBOX_DEVICE_KEY>` 與 `Content-Type: application/json`。
- 錯誤一律 `{"detail": "<原因>"}`。
- `device_uuid` / `device_id` 可以省略，平台以金鑰判斷是哪一台；有填就必須等於自己的 ID，否則 `403`。

### 2.3 模組結構

新增 `aibox_http.py`（或 `aivms_http.py`）取代 `aivms_mqtt.py`，提供相同介面：

```python
class Telemetry(Protocol):
    def start(self) -> None: ...                       # 送 online，啟動背景執行緒
    def stop(self) -> None: ...                        # 送 offline（最多等 3 秒），停止
    def heartbeat(self, hb: dict) -> None: ...
    def camera_status(self, code: str, status: dict) -> None: ...
    def event(self, event: dict) -> None: ...          # 只放進佇列，立即返回
```

REACH 主程式的呼叫點不用改。`aivms_mqtt.py` 與 paho-mqtt 依賴可以移除。

### 2.4 上線 / 離線

```http
POST {AIBOX_API_URL}/edge/status

{"state": "online", "timestamp": "2026-10-13T09:00:00+08:00"}
```

- 回 `204`。
- 啟動時送 `online`。
- 正常關閉時送 `offline`，最多等 3 秒。

突然斷電沒有 Last Will 也沒關係：平台在心跳停止 30 秒後會自動判定離線並記錄。

### 2.5 心跳

```http
POST {AIBOX_API_URL}/edge/heartbeat

{"timestamp": "...", "cpu_usage": 35.2, "memory_usage": 61.0, "gpu_usage": 42.0, "temperature": 63.0,
 "agent_version": "reach-office-vision/2.1.0", "hostname": "reach-office", "ip_address": "192.168.0.50",
 "gpu_name": "NVIDIA RTX A2000", "gpu_memory": 6144, "models": [ ...見第 7 節... ]}
```

- **30 秒沒收到就判定離線**，所以心跳必須在獨立執行緒送，不能被推論或推流卡住。
- 回應見第 3 節。

### 2.6 攝影機狀態

```http
POST {AIBOX_API_URL}/edge/cameras/bimer-back-left/status

{"rtsp_status": "online", "ai_status": "running", "stream_status": "streaming",
 "input_fps": 15, "inference_fps": 5, "output_fps": 15, "resolution": "1280x720", "timestamp": "..."}
```

- 回 `204`。
- 回 `404` 表示平台沒有這支攝影機，請重新同步攝影機清單（第 5 節）。

### 2.7 事件 / 紀錄

```http
POST {AIBOX_API_URL}/edge/logs

{"event_id": "leave-20261013-S01-3", "camera_id": "bimer-back-left", "event_type": "office.leave",
 "severity": "warning", "status": "open", "message": "S01 離席", "data": {...}, "snapshot_key": "..."}
```

- 一筆：回 `200 {"event_id", "camera_id"}`。
- 多筆：傳陣列，一次最多 100 筆，一律回 `200 {"accepted": [...], "rejected": [{"index", "detail"}]}`，某一筆被拒不影響其他筆。
- 攝影機代碼放在 `camera_id`。
- 同一個 `event_id` 再送一次 = 更新該筆（例如 `open` → `returned`），不會重複計算。

### 2.8 可靠性（取代 02 號規格 8.4 節）

- 所有 HTTP 呼叫都在背景執行緒，REACH 主流程只放進佇列。
- 逾時：連線 5 秒、讀取 10 秒。
- **事件**：
  - 失敗（連不上、逾時、5xx）留在本地佇列，按 1/2/5/10/30 秒退避重試。
  - 恢復後以多筆方式補送，每批最多 100 筆，依發生順序。
  - 佇列上限 1000 則，滿了丟最舊並記 warning。
- **心跳、攝影機狀態**：失敗不重送，下一次自然會送新的。
- **每次從斷線恢復**（第一個成功的心跳）後，重送所有目前 `open` 的事件一次。

### 2.9 錯誤處理（取代 02 號規格第 10 節的 MQTT 部分）

| 回應 | 處理 |
|------|------|
| `401` | 金鑰錯誤或已被更換，見第 4 節 |
| `403` | 設備在平台被停用 / 除役，或填了別台的 ID：記 error，每 60 秒重試，不要重新註冊 |
| `404`（攝影機狀態） | 重新 `PUT /edge/cameras` |
| `413` | 超過 256 KB：多筆改小批；單筆縮小 `data` |
| `422` | 內容不合格式：記 warning（含 `detail`）並丟棄該筆，**不可原封不動重送** |
| 連不上 / 逾時 / `5xx` | 退避重試（2.8） |

## 3. 心跳回應：一定要處理（P0）

```json
{
  "config_version": 1791800049,
  "commands": [{"command_id": "d9e75f7f-...", "command": "reload_config", "params": {}, "issued_at": "..."}],
  "mqtt_enabled": false,
  "server_time": "2026-10-13T01:14:09Z"
}
```

| 欄位 | REACH 要做的事 |
|------|----------------|
| `config_version` | 記住這個值。下一次的值不同，就重新 `GET /edge/config` 並套用（第 4.3 節）。第一次收到只記下來 |
| `commands` | 依序執行，每個指令只送一次。不認得的記 info 後略過，不可拋例外 |
| `mqtt_enabled` | 固定 `false`，可忽略 |
| `server_time` | 與本機時間差超過 60 秒時記 warning（第 8 節） |

目前的指令：

| 指令 | 動作 |
|------|------|
| `reload_config` | 重新 `GET /edge/config` 並套用 |
| `ping` | 立即送一次所有攝影機狀態 |
| `restart_camera`（`params.camera_id` = 攝影機代碼） | 重啟該攝影機的拉流與推流 |

## 4. 開機與金鑰流程（P1，確認／小改）

### 4.1 開機順序

1. **讀設定**。沒有 `AIBOX_DEVICE_KEY` 時：
   - 有 `AIBOX_PROVISIONING_TOKEN`：等管理員按「自動綁定」（現有 `auto-bind` 流程）。
   - 都沒有：模組不啟動，記 info。
2. `GET /edge/config`：取得攝影機推流路徑、`site_profile`、`heartbeat_interval_seconds`。
3. `PUT /edge/cameras`：送完整攝影機清單（第 5 節）。
4. `POST /edge/status {"state":"online"}`。
5. 啟動心跳、攝影機狀態、推流、事件佇列。

### 4.2 金鑰

- **`/edge/register` 每呼叫一次，金鑰就換一把，舊的立即失效。**
  - 只在「自動綁定」或收到 `401` 時呼叫，**不可每次開機都註冊**。
  - 拿到新金鑰後：
    1. 先寫入暫存檔再改名覆蓋 `device.env`（避免寫一半斷電），權限 600。
    2. 重新載入設定。
    3. **重啟所有推流**，因為推流密碼就是金鑰。
- 收到 `401`：
  - 有 `AIBOX_PROVISIONING_TOKEN`：以 MAC 重新註冊一次（同業主權杖 + 同 MAC 會拿回同一個裝置 ID）。
  - 沒有權杖，或重新註冊也失敗：記 error（**不印金鑰**），每 60 秒重試，畫面顯示「平台金鑰失效，請聯絡管理員」。
- 收到 `403`：設備被停用，**不要**重新註冊，每 60 秒重試即可。

### 4.3 設定與 site_profile

`GET /edge/config` 中 REACH 需要使用的欄位：

| 欄位 | 用途 |
|------|------|
| `cameras[].camera_id` / `stream_path` | 每支攝影機要推流的路徑（以平台回傳為準，不要自己組） |
| `site_id` / `site_profile` | 業主、場域、合約資料，照 register 契約 §3.6 存進 REACH 的場域設定 |
| `heartbeat_interval_seconds` | 心跳間隔（目前 10） |

畫面上的「重新同步業主資料」按鈕可改呼叫較輕量的 `GET /edge/site-profile`。

## 5. 攝影機清單同步（P1，確認）

- **啟動時**，以及**攝影機新增、刪除、改名時**，送出**完整清單**：

  ```http
  PUT {AIBOX_API_URL}/edge/cameras

  {"cameras": [{"code": "bimer-entrance-right", "name": "BIMer 大門右側"}, {"code": "bimer-back-left", "name": "BIMer 後左"}]}
  ```

- `code` 規則：英數開頭，只能有英數、`_`、`-`，2～32 字。**指派後不要再改**，改了平台會當成另一支新攝影機。
- 回應中 `cameras[].stream_path` 就是推流路徑。
- 清單中沒有的攝影機，平台會停用但保留歷史，下次列出時自動恢復。
- 攝影機帳密與 RTSP 位址**只留在 REACH**，不要送到平台。

## 6. 紀錄（事件）規範（P1）

平台已把所有辨識結果統一顯示在「**Edge 紀錄**」頁（原本的「偵測事件」頁已併入）。
為了讓不同設備的紀錄能一起篩選、統計，請遵守以下命名。

### 6.1 事件類型

| `event_type` | 何時送 | `severity` | `status` |
|--------------|--------|-----------|----------|
| `office.leave` | 離席成立 → 回座（同一個 `event_id` 更新） | 成立 `warning`，回座 `info` | `open` → `returned` |
| `edge.started`（**新增**） | REACH 服務啟動完成 | `info` | — |
| `camera.offline`（**新增**） | 某支攝影機拉流中斷超過 30 秒 | `error` | `open` → 恢復時同一個 `event_id` 改 `resolved` |
| `model.changed`（**新增**） | 載入的模型或版本改變 | `info` | — |
| 其他自訂 | 未來新功能 | 依嚴重度 | 自訂 |

- `edge.started`：`data` 放 `{"version", "models", "cameras"}`，平台可據此看出哪台重開過、跑哪一版。
- `camera.offline`：`camera_id` 放該攝影機，`data.error` 放錯誤摘要（不可含攝影機帳密）。
  `event_id` 建議用 `camoff-<camera_code>-<開始時間>`，恢復時用同一個 `event_id` 送 `status: "resolved"`、`severity: "info"`，
  並在 `data.down_seconds` 放中斷秒數。
- `model.changed`：`data` 放 `{"from": "...", "to": "..."}`。

命名規則：

- 小寫，以 `.` 分層（`領域.事件`）。
- 允許英數與 `. _ : -`，64 字以內。
- `system.connection`、`system.platform`、`system.camera_sync` 由平台自己寫，**REACH 不可使用**（會被拒）。
- 其他 `system.*` 也請避免，改用上表的名稱。

### 6.2 嚴重度

| 值 | 用在 |
|----|------|
| `debug` | 除錯用，正式環境不要送 |
| `info` | 一般紀錄、恢復 |
| `warning` | 需要有人注意的業務事件（例如離席） |
| `error` | 設備或攝影機故障 |
| `critical` | 需要立即處理（目前沒有，保留） |

### 6.3 其他

- `event_id`：同一件事從頭到尾用同一個；不同事件不可重複。
- `timestamp`：事件**發生**的時間（帶時區），不是送出的時間；補送時特別重要。
- `message`：一行給人看的中文，例如「S01 離席」。
- **快照**：`office.leave` 成立時附一張已畫框的 JPEG（`snapshot_key`，02 號規格第 9 節，流程不變）。
  上傳失敗不可阻擋事件送出。
- **個資**：員工姓名只有 `AIBOX_SEND_EMPLOYEE_NAME=true` 時才放進 `data.employee_name`（預設不送），與 02 號規格相同。
- `detections`（選填）：送框座標時平台會畫在快照上，像素座標要搭配 `frame` 寬高。

## 7. 心跳內容：模型回報（P1，確認）

心跳的 `models` 改為**必填**。平台「AI 模型」頁靠它顯示每台在用哪個模型、哪一版：

```json
"models": [
  { "name": "yolo11n", "version": "2026.09", "type": "yolo11", "task": "person / cell phone",
    "labels": ["person", "cell phone"], "cameras": ["bimer-entrance-right", "bimer-back-left"] }
]
```

- `version` 請填權重檔版本或訓練日期。
- 換模型時下一次心跳就要反映，並送一筆 `model.changed`（6.1）。

## 8. 時間（P2）

- REACH 主機必須啟用 NTP 校時（`timedatectl` 顯示 `System clock synchronized: yes`）。
- 所有時間用 ISO 8601 並帶時區，例如 `2026-10-13T09:15:10+08:00`。
- 與心跳回應的 `server_time` 差超過 60 秒時記 warning。

## 9. 安全與 HTTPS 準備（P1）

- **HTTPS**：測試環境走 Tailscale + HTTP；正式對外會改成 `https://`。
  - REACH 要能直接使用 `https://` 的 `AIBOX_API_URL`，並**驗證憑證**，不可關閉驗證。
  - 若使用自簽憑證，從 `AIBOX_CA_FILE` 讀取 CA。
  - 推流在正式環境可能改用 SRT（`srt://...:8890`），02 號規格已支援，請一併測試。
- 金鑰、佈建權杖只存在 env 檔（權限 600 / 640），**任何 log、錯誤訊息、畫面都不可出現**。
  - 例外：畫面可顯示前 4 碼供辨識。
- 設定檔**刪除**所有 `AIVMS_MQTT_*` / `AIBOX_MQTT_*`（平台已無 MQTT，舊帳密也已失效）。
- 只需要連出（REACH → 平台）：
  - API：8000，未來改 HTTPS 為 443。
  - RTSP：8554（或 SRT：8890）。
  - 快照：9000。
  - 平台不會連進 REACH。

## 10. 測試、驗收、回報

### 10.1 自動化測試（REACH 端）

- [ ] `AIBOX_*` 與舊的 `AIVMS_*` 都能讀到，兩者都有時以 `AIBOX_*` 為準，用到舊名會記 warning
- [ ] 不會建立任何 MQTT 連線，沒有 MQTT 設定也能啟動
- [ ] `config_version` 改變會重抓 `/edge/config`，第一次不重抓
- [ ] `reload_config`、`ping`、`restart_camera` 會被執行；未知指令不會拋例外
- [ ] 平台關閉期間的事件，恢復後以多筆方式依序補送；`422` 的事件不會無限重送
- [ ] `401` 且有佈建權杖時重新註冊一次，新金鑰原子寫入，推流以新金鑰重啟
- [ ] 平台無回應時，REACH 主流程 FPS 不受影響
- [ ] log 中搜尋不到金鑰、佈建權杖、MQTT 密碼、員工姓名（`AIBOX_SEND_EMPLOYEE_NAME=false` 時）

### 10.2 驗收（REACH01、REACH02 各做一次）

1. 設定改用 `AIBOX_*`，刪除 MQTT 設定，重啟 REACH。
2. 平台「邊緣裝置」頁：
   - 在線。
   - 「最後回報」每 10 秒更新。
   - CPU、模型欄位有資料。
   - 「Agent」欄顯示新版本號。
3. 「Edge 紀錄」：
   - 出現 `edge.started`。
   - 製造一次離席：`office.leave` 從 `open` 變 `returned`，快照有框。
4. 「即時監看」：每支攝影機都有畫面。
5. 拔掉一支攝影機的網路 1 分鐘：出現 `camera.offline`，恢復後同一筆變 `resolved`。
6. 平台把攝影機改名：10 秒內 REACH 重抓設定（看 REACH log）。
7. 平台按「重新載入設定」：10 秒內 REACH 執行 `reload_config`。
8. 拔 REACH 主機網路 1 分鐘再接回：
   - 平台記錄斷線與中斷時間。
   - 期間的事件在恢復後補上。
9. 正常停止 REACH 服務：平台立即顯示離線。

### 10.3 完成後請回報

- REACH 版本號與更新內容摘要
- 10.1 測試結果
- REACH01、REACH02 各自 10.2 驗收結果（可附截圖）
- 已刪除兩台設定檔中 MQTT 帳密的確認



---

**參考**

- 平台規格：[`docs/edge-integration.md`](../../edge-integration.md)
- 可執行範例：[`examples/edge-http/generic_edge.py`](../../../examples/edge-http/generic_edge.py)
  - 只用 Python 標準函式庫。
  - `HttpTelemetry` 類別示範第 2、3 節。
- 串接全貌：[`03-AIBOX-SERVER與REACH01-02串接說明.md`](03-AIBOX-SERVER與REACH01-02串接說明.md)
