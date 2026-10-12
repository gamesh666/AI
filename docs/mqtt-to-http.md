# MQTT 共用帳號 → HTTP：停用步驟

## 為什麼要換

原本所有 Edge 共用同一組 MQTT 帳密，ACL 允許寫入 `edge/#`。拿到這組帳密就能冒充**任何一台** Edge：
偽造辨識紀錄、偽造心跳，或讓裝置看起來斷線。

HTTP 送法用的是**每台各自的裝置金鑰**（`X-Device-Key`）：

- 一把金鑰只能代表自己那一台。
- 外流時在平台按「更換金鑰」即可，不影響其他台。
- 對外可以不必再開 1883 埠。

兩種送法的 JSON 內容完全相同，規格見 [`edge-integration.md`](edge-integration.md) 第 3、4 節。

## 現在的狀態：兩種都收

| 項目 | 狀態 |
|------|------|
| HTTP 端點 `POST /api/v1/edge/heartbeat`、`/status`、`/cameras/{code}/status`、`/logs`、`/events` | 已上線 |
| MQTT 共用帳號 | **仍啟用**（`MQTT_EDGE_ENABLED=true`），現有 Edge 不受影響 |
| 平台下指令 | 只用 HTTP 的 Edge 由心跳回應帶回；其他照舊走 MQTT |
| 本平台的 edge-agent | `EDGE_TELEMETRY=auto`（預設）：平台還提供 MQTT 時走 MQTT，停用後自動改走 HTTP，不用改設定 |

## 怎麼看哪些 Edge 已經改好

網頁 **邊緣裝置** 頁：

- **通訊方式**欄位，看的是最近 5 分鐘的心跳從哪條路送來：
  - `HTTP`：已改好。
  - `MQTT（待改）`：還在用舊方式。
  - `HTTP + MQTT`：兩條都有（剛切換，或兩邊都在送）。
  - `—`：最近 5 分鐘沒有心跳。
- 表格上方的狀態列：
  - 黃色「還有 N 台透過 MQTT 傳送」：還不能停用。
  - 綠色「所有啟用中的 Edge 都已改用 HTTP」：可以停用。

## 停用 MQTT 共用帳號

前提：狀態列是綠色，而且停用中、還沒上線的裝置日後上線也會用 HTTP。

1. 在平台 VM 的 `.env` 設定：

   ```bash
   MQTT_EDGE_ENABLED=false
   ```

2. 重建 mosquitto 與 backend，讓新設定生效：

   ```bash
   docker compose up -d --force-recreate mosquitto backend
   ```

3. 檢查：

   ```bash
   docker compose logs mosquitto | grep MQTT_EDGE_ENABLED
   # → MQTT_EDGE_ENABLED=false: shared edge account disabled, edges must use HTTP
   ```

   - 舊帳密應該連不上（`not authorised`）。
   - 邊緣裝置頁的狀態列變成「MQTT 共用帳號：已停用」，所有 Edge 仍顯示在線。

4. 換掉舊密碼，避免日後誤開時舊密碼仍有效：產生新的 `MQTT_EDGE_PASSWORD`，或直接刪除這一行。
   停用期間平台不會使用這組密碼。
5. 防火牆 / 路由器若有對外開放 1883，可以關掉。平台自己的 backend 仍在 Docker 內部網路使用 MQTT，不受影響。

停用之後：

- 連線資訊不再附 MQTT 帳密與 topics。
- edge-agent 的設定也會告訴 Edge `mqtt_enabled: false`。
- 即使有人拿舊帳密連進 broker（例如忘了重建 mosquitto），backend 也會忽略來自 Edge 的 MQTT 訊息。

## 要退回的話

`.env` 改回 `MQTT_EDGE_ENABLED=true`（`MQTT_EDGE_PASSWORD` 要有值），再執行一次步驟 2。
