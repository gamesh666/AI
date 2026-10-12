# REACH 修改規格：心跳、狀態、事件改走 HTTP（停用 MQTT）

> 對象：REACH Office Vision 的 `aivms_bridge` 模組（[02 號規格](02-REACH-需新增功能規格.md) 第 1 節）。
> 範圍：只改「**怎麼送**」，**送什麼（JSON 內容）完全不變**。影像推流、攝影機同步、快照上傳都不用改。

## 0. 為什麼要改

目前所有 Edge 共用同一組 MQTT 帳密。這組帳密只要外流，任何人都能冒充 REACH01、REACH02 或其他任何一台設備，
送假事件、假心跳，或讓設備在平台上看起來斷線。

改成 HTTP 之後：

- 每台只用自己的**裝置金鑰**（`AIVMS_DEVICE_KEY`，現在已經在用）。
- 金鑰外流只影響那一台，平台按「更換金鑰」就能作廢。
- REACH 不再需要 MQTT 帳密，也不需要連 1883 埠。
- 平台會直接回應錯誤原因（MQTT 送錯時平台只能默默丟棄）。

**時程**：

1. 平台已經同時接受 HTTP 與 MQTT，現在就可以開始改、開始測，不影響目前運作。
2. REACH01、REACH02 都改好並確認後，平台才會停用 MQTT 共用帳號。

## 1. 改動總覽

| 項目 | 原本（02 號規格） | 改成 |
|------|-------------------|------|
| 3.1 同步攝影機清單 | HTTP `PUT /edge/cameras` | **不變** |
| 3.2 上線 / 離線 | MQTT `edge/{device}/status`（retained + Last Will） | 啟動：`POST /edge/status {"state":"online"}`；正常關閉：`{"state":"offline"}`；**沒有 Last Will**（見第 4 節） |
| 3.3 心跳 | MQTT `edge/{device}/heartbeat` | `POST /edge/heartbeat`，**要處理回應**（第 3 節） |
| 3.4 攝影機狀態 | MQTT `edge/{device}/cameras/{camera_code}/status` | `POST /edge/cameras/{camera_code}/status` |
| 3.5 即時辨識畫面 | RTSP / SRT 推流 | **不變** |
| 3.6 事件 | MQTT `edge/{device}/cameras/{camera_code}/logs` | `POST /edge/logs`（一筆或一次多筆） |
| 3.7 快照 | HTTP presign + PUT | **不變** |

- 所有請求：`{AIVMS_API_URL}` + 路徑。
- 都帶 header `X-Device-Key: <AIVMS_DEVICE_KEY>` 與 `Content-Type: application/json`。
- 錯誤一律是 `{"detail": "<原因>"}`。

### 設定（env）

```bash
AIVMS_TELEMETRY=http          # 新增：http（預設）| mqtt（舊方式，過渡期保留，可退回）
# 改成 http 後以下不再需要，平台停用 MQTT 後請從設定檔刪除：
# AIVMS_MQTT_HOST / AIVMS_MQTT_PORT / AIVMS_MQTT_USERNAME / AIVMS_MQTT_PASSWORD / AIVMS_MQTT_TLS
```

`AIVMS_TELEMETRY=mqtt` 時行為與現在完全相同，萬一 HTTP 有問題可以立即退回。

### 模組結構

`aivms_mqtt.py` 保留不動，新增 `aivms_http.py`，兩者提供相同介面，由 `AIVMS_TELEMETRY` 決定用哪一個：

```python
class Telemetry(Protocol):
    def start(self) -> None: ...                       # 送 online，啟動背景執行緒
    def stop(self) -> None: ...                        # 送 offline（最多等 3 秒），停止
    def heartbeat(self, hb: dict) -> None: ...
    def camera_status(self, code: str, status: dict) -> None: ...
    def event(self, event: dict) -> None: ...          # 放進佇列，立即返回
```

`aivms_bridge.py` 與 REACH 主程式的三個呼叫點**都不用改**。

## 2. 各端點

### 2.1 上線 / 離線

```http
POST {AIVMS_API_URL}/edge/status
X-Device-Key: <AIVMS_DEVICE_KEY>

{"state": "online", "timestamp": "2026-10-12T09:00:00+08:00"}
```

- 回應 `204`（無內容）。
- `bridge.start()` 時送 `online`。
- `bridge.stop()` 時送 `offline`，最多等 3 秒，送不出去就放棄。

### 2.2 心跳（每 10 秒）

```http
POST {AIVMS_API_URL}/edge/heartbeat
X-Device-Key: <AIVMS_DEVICE_KEY>

{ ...與 02 號規格第 5 節相同的心跳 JSON... }
```

- `device_uuid` 可以省略，平台以金鑰判斷是哪一台。若有填，必須等於 `AIVMS_DEVICE_ID`，否則回 `403`。
- **30 秒沒收到心跳，平台判定離線**，所以心跳要在獨立執行緒送，不能被推論或推流卡住。
- 回應見第 3 節。

### 2.3 攝影機狀態（每 5 秒，每支攝影機一次）

```http
POST {AIVMS_API_URL}/edge/cameras/bimer-back-left/status
X-Device-Key: <AIVMS_DEVICE_KEY>

{"rtsp_status": "online", "ai_status": "running", "stream_status": "streaming",
 "input_fps": 15, "inference_fps": 5, "output_fps": 15, "resolution": "1280x720",
 "timestamp": "2026-10-12T09:00:05+08:00"}
```

- 內容與 02 號規格第 6 節相同，`camera_id` 可省略（以網址為準）。
- 回應 `204`。
- 回 `404` = 平台上沒有這支攝影機，請重新執行攝影機同步（`PUT /edge/cameras`）。

### 2.4 事件

一筆：

```http
POST {AIVMS_API_URL}/edge/logs
X-Device-Key: <AIVMS_DEVICE_KEY>

{"event_id": "leave-20261012-S01-3", "camera_id": "bimer-back-left", "event_type": "office.leave",
 "severity": "warning", "status": "open", "message": "S01 離席", "data": {...}, "snapshot_key": "..."}
```

→ `200 {"event_id": "leave-20261012-S01-3", "camera_id": "bimer-back-left"}`

多筆（斷線後補送時使用，一次最多 100 筆）：

```http
POST {AIVMS_API_URL}/edge/logs

[ {...}, {...}, {...} ]
```

→ 一律回 `200`，例如：

```json
{"accepted": [{"event_id": "...", "camera_id": "..."}],
 "rejected": [{"index": 2, "detail": "invalid log: event_type: ..."}]}
```

- 事件 JSON 與 02 號規格第 8 節**完全相同**，只是 `device_id` 可以省略。
- 攝影機代碼放在 `camera_id`，因為網址裡沒有攝影機。
- 同一個 `event_id` 再送一次 = 更新該事件，例如 `open` → `returned`，不會重複計算。

## 3. 心跳回應：一定要處理

MQTT 時平台會主動推指令與設定變更給 REACH；HTTP 沒辦法主動推，所以改放在**心跳回應**裡：

```json
{
  "config_version": 1791800049,
  "commands": [
    {"command_id": "d9e75f7f-...", "command": "reload_config", "params": {}, "issued_at": "2026-10-12T01:14:08Z"}
  ],
  "mqtt_enabled": true,
  "server_time": "2026-10-12T01:14:09Z"
}
```

| 欄位 | REACH 要做的事 |
|------|----------------|
| `config_version` | 記住這個值。**下一次心跳的值不同**，就重新 `GET /edge/config`（平台上改了攝影機名稱、場域等），並套用 `site_profile`。第一次收到只記下來，不用重抓 |
| `commands` | 依序執行，每個指令平台只送一次。`reload_config`：同上，重抓設定。`ping`：立即送一次所有攝影機狀態。`restart_camera`（`params.camera_id`）：重啟該攝影機的推流。不認得的指令記 info 後略過 |
| `mqtt_enabled` | `false` = 平台已停用 MQTT。若 `AIVMS_TELEMETRY=mqtt`，記 error 提醒改設定 |
| `server_time` | 與本機時間差超過 60 秒時記 warning（事件時間會不準） |

指令處理要在 bridge 的執行緒內完成，不可阻擋 REACH 主流程。

## 4. 可靠性（取代 02 號規格 8.4 節）

- 所有 HTTP 呼叫在 bridge 的背景執行緒送，REACH 主流程只把資料放進佇列，立即返回，與現在相同。
- **事件**：
  - 送失敗（連線失敗、逾時、5xx）就留在本地佇列，按 1/2/5/10/30 秒退避重試。
  - 恢復連線後用「多筆」一次補送（每批最多 100 筆）。
  - 佇列上限 1000 則，滿了丟最舊並記 warning，與現在相同。
- **心跳、攝影機狀態**：送失敗不重送，下一次自然會送新的。
- **4xx 不要原封不動重送**（內容有問題，重送也一樣會被拒），記 warning（含 `detail`）後丟棄。
  例外：`401` 每 60 秒重試，`404` 先重新同步攝影機。
- **每次從斷線恢復後**（第一個成功的心跳），重送所有目前 `open` 的事件一次，與現在相同。
- **逾時**：連線 5 秒、讀取 10 秒。
- **沒有 Last Will**：REACH 突然斷電或斷網時，平台會在心跳停止 30 秒後自動判定離線並記錄斷線，REACH 不用做任何事。

## 5. 錯誤處理（取代 02 號規格第 10 節的 MQTT 列）

| 狀況 | 處理 |
|------|------|
| `401` | 裝置金鑰錯誤或已更換：記 error（**不印金鑰**），每 60 秒重試 |
| `403` | 裝置在平台被停用，或 `device_uuid` / `device_id` 填了別台：記 error，每 60 秒重試 |
| `404`（攝影機狀態） | 攝影機未登記：重新 `PUT /edge/cameras` |
| `413` | 單次請求超過 256 KB：多筆時改成分批送；單筆時縮小 `data` |
| `422` | 內容不合格式：記 warning（含 `detail`），丟棄該筆 |
| 連線失敗 / 逾時 / `5xx` | 退避重試（第 4 節） |

## 6. 測試要求（新增）

- [ ] `AIVMS_TELEMETRY=http` 時不會建立任何 MQTT 連線（程式不需要 MQTT 帳密也能啟動）
- [ ] `AIVMS_TELEMETRY=mqtt` 時行為與改版前完全相同
- [ ] 心跳回應 `config_version` 改變時會重抓 `/edge/config`；第一次不重抓
- [ ] `commands` 內的 `reload_config`、`ping` 會被執行；未知指令不會造成例外
- [ ] 平台關閉期間產生的事件，在平台恢復後以多筆方式補送，順序正確
- [ ] 收到 `422` 的事件不會無限重送
- [ ] 背景執行緒卡住（平台無回應）時，REACH 主流程的 FPS 不受影響
- [ ] log 中不會出現 `AIVMS_DEVICE_KEY`

## 7. 驗收（REACH01、REACH02 各做一次）

1. 設定 `AIVMS_TELEMETRY=http`，**刪除**設定檔中的 `AIVMS_MQTT_*`，重啟 REACH。
2. 平台 **邊緣裝置** 頁：
   - 該設備「在線」。
   - **通訊方式**顯示 `HTTP`。剛切換的 5 分鐘內會顯示 `HTTP + MQTT`，屬正常。
   - CPU、模型欄位有資料。
3. **即時監看**：兩支（REACH02 為一支）攝影機都有畫面。
4. 製造一次離席：**Edge 紀錄**出現 `office.leave` `open`，回座後同一筆變成 `returned`。
5. 平台上把一支攝影機改名，10 秒內 REACH 的 log 出現「重新抓取設定」。
6. 拔網路線 1 分鐘再接回：
   - 平台顯示斷線，並記錄斷線多久。
   - 斷線期間的事件在恢復後補上。
7. 正常停止 REACH 服務：平台立即顯示離線，不必等 30 秒。

兩台都通過後通知平台方，平台會停用 MQTT 共用帳號；之後 REACH 設定檔不得再有 `AIVMS_MQTT_*`。

## 8. 參考實作

- [`examples/third-party-edge/generic_edge.py`](../../../examples/third-party-edge/generic_edge.py) 的 `HttpTelemetry` 類別：
  - 只用 Python 標準函式庫。
  - 示範心跳回應處理、`config_version` 重抓、事件更新。
- 平台完整規格：[`docs/edge-integration.md`](../../edge-integration.md) 第 3、4 節。
