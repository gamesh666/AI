# REACH 更新規格 v3：平台產生報表、只用權杖上線

> 對象：REACH Office Vision 的平台串接模組（`app/integrations/`）與報表模組（`app/profiles/office/`）。
> 本文件**補充** 05 號規格；衝突時以本文件為準。
> 端點細節同步寫在 [`docs/edge-integration.md`](../../edge-integration.md) 第 0 節與 4c 節。

## 目錄

| # | 項目 | REACH 是否要改 | 優先 |
|---|------|----------------|------|
| 1 | 只用佈建權杖上線（平台不再手動發金鑰） | 確認／小改 | P1 |
| 2 | 送報表選項 `PUT /edge/report-options` | 要 | P1 |
| 3 | 處理心跳回應的 `generate_report`，產生 PDF 並上傳 | 要（主要工作） | P1 |
| 4 | 測試、驗收、回報 | — | — |

平台這一版已上線。REACH 沒更新前：裝置照常運作，只是平台「產生報表」會顯示「裝置未回應」。

---

## 1. 只用佈建權杖上線（P1，確認／小改）

平台已**移除**「手動新增裝置」「更換金鑰」「連線資訊（含金鑰）」。往後每台 AI BOX 都只靠業主的佈建權杖上線：

```bash
# 出廠設定只需要這兩行
AIBOX_API_URL=http://<平台IP>:8000
AIBOX_PROVISIONING_TOKEN=aivms_pt_...
```

- 「自動綁定」流程不變（05 號 4.1、4.2 節）：`POST /edge/register` 取得 `device_uuid` 與 `api_key`，
  REACH 自己存進 `device.env`（權限 600）。之後的 HTTP 呼叫與 RTSP / SRT 推流照舊使用這把金鑰。
- 不再有人會把金鑰交給 REACH。設定頁若有「手動輸入平台金鑰」欄位，請改為唯讀顯示「已綁定 / 未綁定」，
  不要顯示金鑰本身。
- **權杖撤銷 5 分鐘後會從平台刪除**。已綁定的設備不受影響；但收到 `401` 想重新註冊時，若權杖已失效
  （`/edge/register` 回 `401`），請：
  - 記 error（**不印權杖、不印金鑰**），每 60 秒重試平台呼叫；
  - 畫面顯示「平台權杖已失效，請向管理員索取新權杖後重新自動綁定」；
  - 管理員給新權杖、更新 `AIBOX_PROVISIONING_TOKEN` 後按「自動綁定」即可（同業主 + 同 MAC 會拿回原本的裝置 ID）。

## 2. 送報表選項（P1）

平台的報表視窗要用 REACH 的員工、部門、工位清單做下拉選單。

```http
PUT /api/v1/edge/report-options
X-Device-Key: <AIBOX_DEVICE_KEY>
Content-Type: application/json

{"employees":   [{"id": "A001", "name": "王小明", "department": "業務部", "seat": "S01"}],
 "departments": [{"value": "業務部", "label": "業務部"}],
 "seats":       [{"value": "S01", "label": "S01 窗邊"}],
 "events":      [{"value": "away", "label": "離席"}],
 "statuses":    [{"value": "returned", "label": "已回座"}, {"value": "auto_closed", "label": "未確認回座"}]}
```

| 欄位 | 內容 | 來源（REACH） |
|---|---|---|
| `employees[].id` / `name` | 員工編號、姓名 | `office_employees`（在職者） |
| `employees[].department` / `seat` | 部門、目前工位（可為 `null`） | 員工資料、`seat_assignments` |
| `departments` / `seats` | 下拉選單的值與顯示文字 | 部門、工位資料表 |
| `events` / `statuses` | 報表畫面「事件」「狀態」選單的值與顯示文字 | `report_models.py` 的白名單 |

- **時機**：模組啟動時送一次；員工、部門、工位、白名單有變動時再送。每次送**整份**（覆蓋上一次）。
- 回 `204` 成功。上限：員工 5,000、工位 2,000、部門 500、事件／狀態各 50，整份 ≤ 2 MB。
- 失敗（網路、5xx）照 05 號 2.8 節重試；`422` 表示格式錯，記 warning，不重送同一份。

## 3. 產生報表（P1，主要工作）

### 3.1 流程

```text
平台管理員按「產生 PDF」
  → 平台把 generate_report 放進這台的心跳回應（平台不連進 REACH）
  → REACH 用自己的報表程式產生「出勤與事件報表」PDF
  → REACH PUT 上傳 PDF → 平台網頁出現「下載 PDF」
```

只做**出勤事件報表**、只做 **PDF**；不做 AI 辨識報表、Word、Excel、Email。

### 3.2 心跳回應裡的指令

```json
{"command_id": "…", "command": "generate_report", "params": {
  "report_id": "6f1c0b9e-…",
  "kind": "attendance",
  "format": "pdf",
  "filters": {"employee_id": "A001", "department": null, "seat": null,
              "period": "yesterday", "start_date": "2026-10-26", "end_date": "2026-10-26",
              "event": null, "status": null, "attendance_status": "late_confirmed",
              "vlm": null, "review": null, "face": null},
  "upload": {"method": "PUT", "path": "/edge/reports/6f1c0b9e-…/file",
             "content_type": "application/pdf", "max_bytes": 20971520},
  "status": {"method": "POST", "path": "/edge/reports/6f1c0b9e-…/status"}}}
```

`upload.path`、`status.path` 都是相對於 `AIBOX_API_URL` + `/api/v1`，請**照給的路徑呼叫**，不要自己組。

### 3.3 篩選條件對照

`null` = 全部。對照 REACH 報表畫面（`web/assets/reports.js`）的篩選欄位：

| 平台欄位 | REACH 欄位 | 值 |
|---|---|---|
| `employee_id` | 員工 | 第 2 節送的 `employees[].id` |
| `department` | 部門 | 第 2 節送的 `departments[].value` |
| `seat` | 工位 | 第 2 節送的 `seats[].value` |
| `start_date` / `end_date` | 起始、結束日期 | `YYYY-MM-DD`，REACH 當地日期；**照給的日期產生**，最長 366 天 |
| `period` | 期間 | `yesterday` / `last_week` / `last_month` / `last_year` / `custom`，**只供參考**（日期已由平台算好） |
| `event` / `status` | 事件、狀態 | 第 2 節送的 `events[].value` / `statuses[].value` |
| `attendance_status` | 出勤狀態 | `on_time` 準時到班、`late_pending_review` 遲到候選（待審核）、`late_confirmed` 遲到已確認、`late_rejected` 遲到已駁回、`identity_conflict` 身分不一致（待審核）、`not_arrived` 尚未到班、`normal_departure` 正常下班、`early_leave_pending_review` 早退候選（待審核）、`early_leave_confirmed` 早退已確認、`early_leave_rejected` 早退已駁回、`not_judged` 尚未判定、`unverifiable` 無法確認 |
| `vlm` | VLM 確認 | `supported` 影像支持、`not_supported` 影像不支持、`undetermined` 無法判定、`model_unavailable` 模型無法使用、`disabled` 未啟用 |
| `review` | 人工審核 | `pending` 待確認、`confirmed` 已確認、`rejected` 已駁回、`not_required` 不需審核 |
| `face` | 人臉驗證 | `matched` 人臉相符、`unverified` 未驗證／不符 |

`attendance_status` 的代碼與 REACH `office_attendance_daily` 的到班／下班狀態相同。
其餘代碼若和 REACH 內部值不同，請在模組內對照；遇到不認識的值：回報 `failed`（3.5 節），訊息寫明哪個欄位。

### 3.4 產生 PDF

- **直接使用現有的 `report_export.py` PDF 匯出**（ReportLab，A4 橫向），版面與 REACH 網頁「PDF」按鈕產生的檔案**完全相同**：
  標題區、業主／場域、員工、工位／部門、統計期間、產生時間、摘要表、「排班與出勤」表、事件明細表、頁首頁尾。
- 權限範圍視同 REACH **管理員**（可查全部員工）。
- 查無資料也要產生 PDF（事件表顯示「無事件」），不要回報失敗。
- 在背景執行，**不可卡住心跳**；同時間只做一份，其餘排隊。
- 寫一筆 `report_history`，產生者記為 `AIBOX SERVER`。
- 檔名不重要（平台會命名為 `attendance_<員工或 all>_<起>_<迄>.pdf`）。

### 3.5 回報進度與上傳

```http
POST /api/v1/edge/reports/{report_id}/status          開始產生時（選用）
{"state": "generating"}

POST /api/v1/edge/reports/{report_id}/status          失敗時（必要）
{"state": "failed", "message": "資料庫連線失敗"}       message ≤ 512 字，不可含密碼、權杖、金鑰

PUT  /api/v1/edge/reports/{report_id}/file            完成時
X-Device-Key: <AIBOX_DEVICE_KEY>
Content-Type: application/pdf

<PDF 檔本身>
```

| 平台回應 | 意思 | REACH 要做 |
|---|---|---|
| `200`（上傳）／`204`（狀態） | 成功 | 結束 |
| `404` | 不是這台的報表，或已被刪除 | 放棄，記 warning |
| `409` | 這份已上傳過 | 放棄 |
| `413` | 超過 20 MB | 回報 `failed`，訊息「檔案超過 20 MB，請縮小員工或期間範圍」 |
| `422` | 內容不是 PDF／格式錯 | 記 error，回報 `failed` |
| `401` / `403` | 金鑰問題 | 照 05 號 4.2 節 |
| 網路錯誤、`5xx` | 平台暫時不能用 | 重試 3 次（10、30、60 秒），仍失敗就放棄 |

- 平台 15 分鐘內沒收到檔案會顯示「裝置未回應」，之後收到仍會接受。
- 指令只會送一次：REACH 若在產生途中重啟，該份報表就放棄（不用補做），使用者可再按一次。

## 4. 測試、驗收、回報

### 4.1 自動化測試（REACH 端）

- 篩選條件對照：每個代碼都轉成正確的 REACH 查詢條件；不認識的值回報 `failed`。
- 產生的 PDF 與 REACH 網頁「PDF」按鈕用同樣條件產生的檔案內容一致（頁數、摘要數字、事件筆數）。
- 上傳重試：模擬 `5xx` 後成功、`404` 不重試、`413` 回報失敗。
- 心跳不被報表卡住：產生 1 年、全部員工的報表期間，心跳仍每 10 秒送出。

### 4.2 驗收（REACH01、REACH02 各做一次）

| # | 操作（平台） | 預期 |
|---|---|---|
| 1 | 「邊緣裝置」→ 該台「產生報表」 | 員工、部門、工位下拉選單有 REACH 的資料 |
| 2 | 選「昨日」、全部 →「產生 PDF」 | 約 10–30 秒後「完成」，下載的 PDF 與 REACH 網頁用同條件匯出的一致 |
| 3 | 選一位員工、「上月」 | 只有該員工、該月份 |
| 4 | 出勤狀態選「遲到已確認」 | 只含符合的資料 |
| 5 | 選沒有資料的日期 | 仍有 PDF，事件表顯示「無事件」 |
| 6 | 拔掉 REACH 網路 → 產生 → 1 分鐘後接回 | 接回後完成 |
| 7 | 在 REACH 新增一位員工 | 1 分鐘內平台的員工選單出現此人 |

### 4.3 完成後請回報

- REACH 版本號、修改的檔案清單。
- 4.1 測試結果、4.2 每一項的結果（附下載的 PDF 檔名）。
- 3.3 節有對照不到的代碼請列出，平台會配合調整。
