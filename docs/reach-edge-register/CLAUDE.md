# AIVMS — REACH AI BOX 裝置註冊 API 實作規格（給 AIVMS 專案的 Claude Code）

> 版本：2026-10-12 · 提供方：REACH AI BOX 團隊
> 用途：放進 **AIVMS 中央平台專案**（例如 `docs/reach-edge-register/CLAUDE.md`，或併入專案根目錄的 `CLAUDE.md`），讓 Claude Code 依本文件實作 / 修改裝置註冊端點。
> 本文件是**介面契約**：BOX 端已依此實作。欄位名稱、HTTP 狀態碼、header 名稱都不可以自行更改；需要變更請先通知 REACH 團隊。

---

## 0. 給 Claude Code 的工作指示

1. 先找出 AIVMS 專案現有的 edge 路由（例如 `/api/v1/edge/config`、`/api/v1/edge/cameras/{code}`、`X-Device-Key` 驗證），**沿用相同的框架、資料層與錯誤格式**，不要另外起一套。
2. 依 §3 實作 / 補齊 `POST /api/v1/edge/register`，依 §4 讓 `GET /api/v1/edge/config` 一併回傳 `site_profile`。
3. 依 §5 建立或擴充資料表（使用專案既有的 migration 工具）。
4. 先寫測試（§8 的測試矩陣），再實作；完成後用 §9 的契約腳本對本機服務跑一次，全部 PASS 才算完成。
5. 任何 log、錯誤訊息、traceback 都**不可**含 provisioning token、api_key、MQTT 密碼、統編、電話。
6. 不確定的地方（現有表名、管理後台位置）先讀程式碼確認；真的無法判斷時列出假設，不要自己發明欄位名稱。

---

## 1. 背景：BOX 的綁定流程

```
REACH AI BOX（出廠已裝 platform.env，內含 AIVMS_PROVISIONING_TOKEN）
  │ 管理員在 BOX 網頁按「自動綁定（MAC）」
  ▼
POST /api/v1/edge/register   (X-Provisioning-Token, device_uuid=REACH-<MAC>, mac_address)
  ▼ 200 {api_key, device_uuid, site_id, site_profile}
BOX 寫入 device.env（DEVICE_ID / DEVICE_KEY / SITE_ID）
BOX 把 site_profile 寫入本機「場域與授權」設定
BOX 熱重載 → 以 device_uuid 當 MQTT client_id 連線 → 用 api_key（X-Device-Key）註冊攝影機、推流
```

之後 BOX 的每一個 HTTP 呼叫都帶 `X-Device-Key: <api_key>`。MQTT 用的是平台固定帳密（不是 api_key），topic 前綴是 `edge/{device_uuid}/`。

---

## 2. 名詞

| 名詞 | 說明 |
|---|---|
| provisioning token | 出廠佈建權杖，寫在 BOX 的 platform.env；只用來呼叫 `/edge/register` |
| MAC | BOX 主要網卡的 MAC，BOX 送出時固定是小寫、冒號分隔：`aa:bb:cc:dd:ee:ff` |
| 臨時 device_uuid | BOX 自己算出來的 `REACH-` + 12 碼大寫 hex（例：`REACH-AABBCCDDEEFF`） |
| device_uuid（正式） | AIVMS 指派的 Device ID（例：`REACH01`）；可以直接沿用臨時 device_uuid |
| api_key | 每台 BOX 專屬的 Device Key，等同 `/edge/config` 用的 `X-Device-Key` |
| site_profile | 業主 / 場域 / 合約資料，BOX 會寫入本機「場域與授權」頁 |

---

## 3. `POST /api/v1/edge/register`

### 3.1 Request（BOX 端已固定，不可更改）

```http
POST /api/v1/edge/register
X-Provisioning-Token: <token>
Content-Type: application/json
Accept: application/json

{
  "device_uuid": "REACH-AABBCCDDEEFF",
  "mac_address": "aa:bb:cc:dd:ee:ff"
}
```

伺服器端驗證：

| 項目 | 規則 | 失敗回應 |
|---|---|---|
| `X-Provisioning-Token` | 必須存在、有效、未撤銷、未過期；以常數時間比較（例：`hmac.compare_digest`）；資料庫只存 hash | 401 |
| `mac_address` | 正規化（去掉 `:` `-` `.`、轉小寫）後必須是 12 碼 hex；拒絕全 0、multicast（第一個 byte 的最低位元為 1）、廣播位址 | 422 |
| `device_uuid` | 必須等於 `"REACH-" + MAC 的 12 碼大寫 hex`；不一致回 422 | 422 |
| Body | 其他未知欄位直接忽略 | — |

BOX 的逾時是 **6 秒**，端點必須在 6 秒內回應（不要在這個請求裡同步做任何耗時工作）。

### 3.2 處理邏輯（冪等）

以**正規化後的 MAC** 為唯一鍵：

| 情況 | 行為 | HTTP |
|---|---|---|
| MAC 從未註冊過 | 建立 device：指派正式 device_uuid（依 AIVMS 編碼規則，例如 `REACH01`；沒有規則就直接用臨時 device_uuid），產生 api_key，綁定到該 token 所屬的業主 / 場域（§3.4） | 200 |
| MAC 已註冊、而且是同一個 token 範圍（同業主 / 批次），**BOX 重灌或重新綁定** | **回傳同一個 device_uuid**；api_key 依 §3.3 處理 | 200 |
| MAC 已註冊在**其他業主 / 其他 token 範圍** | 不建立、不洩漏既有資料 | 409 |
| 該 device 已被管理員停用 / 除役 | 不回 key | 403 |
| token 已達註冊台數上限（如果有設定配額） | | 429 或 403（擇一並在回應的 `detail` 說明） |

### 3.3 api_key 規則

- 至少 32 bytes 隨機（例：`secrets.token_urlsafe(32)`），字元只能有 `[A-Za-z0-9_-]`，長度 **16~128**（BOX 有驗證這個格式）。
- 資料庫只存 hash（例：SHA-256 或 argon2），明文只在這次回應出現一次。
- 重新註冊（§3.2 第二列）時：**輪替**，產生新 key、讓舊 key 失效，然後回傳新 key。原因是只存 hash 就無法回傳舊 key；而 BOX 每次綁定都會覆寫 device.env，輪替不會造成問題。
- 每次發放 / 輪替都寫一筆稽核紀錄（§5.3）。

### 3.4 token 與業主的關係

建議由 token 決定新裝置要歸屬哪個業主 / 場域：

- token 建立時關聯 `owner_id`（必填）與 `site_id`（選填）。
- 註冊時 device 自動歸到該 owner / site；沒有 site 時 `site_id` 回空字串，`site_profile` 只填業主層的欄位。
- 如果 AIVMS 目前的 token 不分業主（全平台共用一把），請在 §10 註明，並讓新 device 進入「待指派」狀態；`site_profile` 回 `null`。

### 3.5 Response 200

```json
{
  "api_key": "Q2x5c2Q3a0VfZXhhbXBsZV9rZXlfbm90X3JlYWw",
  "device_uuid": "REACH01",
  "site_id": "SITE-0001",
  "site_profile": {
    "site_name": "範例科技 台北辦公室",
    "profile": "office",
    "site_code": "SITE-0001",
    "host_code": "REACH01",
    "license_code": "LIC-2026-0001",
    "license_until": "2027-10-31",
    "contract_no": "CT-2026-0001",
    "term_years": 3,
    "transaction_type": "lease",
    "company_name": "範例科技股份有限公司",
    "company_address": "台北市範例區範例路 1 號",
    "company_phone": "02-0000-0000",
    "tax_id": "12345678",
    "contact_name": "王小明",
    "contact_phone": "0900-000-000"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `api_key` | ✓ | 見 §3.3 |
| `device_uuid` | ✓ | 正式 Device ID；BOX 會用它當 MQTT client_id 與 topic 前綴，**指派後不可再變更** |
| `site_id` | | 場域 ID，沒有就回 `""` |
| `site_profile` | | 見 §3.6；沒有資料時回 `null` 或省略 |

回應 header 加上 `Cache-Control: no-store`。

### 3.6 `site_profile` 欄位（鍵名固定，BOX 直接存）

BOX 會對每個欄位做驗證，**格式不符的整筆 site_profile 會被 BOX 略過**（綁定本身仍會成功）。請在伺服器端用同一套規則先驗證：

| 鍵 | 型別 | 規則 | 對應 BOX 畫面 |
|---|---|---|---|
| `site_name` | string | ≤128 字 | 業主 / 場域名稱 |
| `profile` | string | `office` / `construction` / `factory` / `security` | 場域 Profile |
| `site_code` | string | ≤128 字；建議等於 `site_id` | 場域編號 |
| `host_code` | string | ≤128 字；建議等於 `device_uuid` | 主機編號 |
| `license_code` | string | ≤128 字 | 授權編號 |
| `license_until` | string | `YYYY-MM-DD`；可為 `""` | 授權期限（BOX 會自行算出 active / expiring / expired） |
| `contract_no` | string | ≤128 字 | 合約單號 |
| `term_years` | int \| null | 0~99 的整數（不可以是 bool、不可以是字串） | 使用年限 |
| `transaction_type` | string | `""` / `buyout`（賣斷）/ `lease`（承租） | 交易方式 |
| `company_name` | string | ≤128 字 | 公司行號 |
| `company_address` | string | ≤256 字 | 公司地址 |
| `company_phone` | string | 符合 `^[0-9+()#\- ]{0,32}$` | 公司電話 |
| `tax_id` | string | `""` 或 8 位數字 | 統編 |
| `contact_name` | string | ≤128 字 | 聯絡人 |
| `contact_phone` | string | 同公司電話 | 聯絡電話 |

規則：
- **只能送上表的鍵**，不要加其他欄位（例如 `owner_id`、`created_at`）。
- 沒有資料的欄位：**省略或給 `null`**，BOX 會保留本機原值。給 `""` 代表「清空」，只在確定要清空時才這樣送。
- 不要送 `license_status`，BOX 會自己算。

### 3.7 錯誤回應格式

所有錯誤都用 `{"detail": "<可以顯示給現場人員看的中文或英文說明>"}`，不含任何 token、key、內部 ID、SQL 或 stack trace。

| HTTP | 時機 | BOX 顯示給使用者的訊息 |
|---|---|---|
| 401 | token 缺少、無效、撤銷、過期 | 佈建權杖被 AIVMS 拒絕 |
| 403 | device 已停用 / 超過配額 | AIVMS 平台回應 HTTP 403 |
| 409 | MAC 屬於其他業主 | 此 MAC 已被其他裝置註冊 |
| 422 | MAC / device_uuid 格式錯 | AIVMS 平台回應 HTTP 422 |
| 429 | 速率限制 | AIVMS 平台回應 HTTP 429 |

### 3.8 速率限制

以來源 IP + token 為鍵，例如每分鐘 10 次；401 連續失敗 5 次就暫停該 IP 15 分鐘。避免有人暴力猜 token。

---

## 4. `GET /api/v1/edge/config`（既有端點，擴充）

BOX 手動貼 Device Key 綁定時會呼叫這個端點。請在現有回應中**加上** `site_profile`（格式與 §3.6 相同）。既有的欄位（`device_uuid`、`site_id`、`mqtt`、`streaming`）**一律不變**：

```json
{
  "device_uuid": "REACH01",
  "site_id": "SITE-0001",
  "mqtt": { "host": "...", "port": 1883, "tls": false },
  "streaming": { "protocol": "rtsp", "rtsp_publish_url": "rtsp://..." },
  "site_profile": { "...": "同 §3.6" }
}
```

（選配）`GET /api/v1/edge/site-profile`（`X-Device-Key`）→ 只回 `{"site_profile": {...}}`，給 BOX 的「重新同步業主資料」按鈕使用。

---

## 5. 資料模型（建議；依 AIVMS 現有 schema 調整命名）

### 5.1 `provisioning_tokens`

| 欄位 | 說明 |
|---|---|
| id | PK |
| token_hash | 唯一；只存 hash |
| token_prefix | 前 8 碼，給管理後台辨識用 |
| owner_id | FK → 業主 |
| site_id | 選填 FK → 場域 |
| max_devices | 選填，配額 |
| expires_at / revoked_at | 到期 / 撤銷時間 |
| created_by / created_at | |

### 5.2 `edge_devices`（若已存在就擴充）

| 欄位 | 說明 |
|---|---|
| device_uuid | PK 或唯一鍵；指派後不可變 |
| mac_address | **唯一**；存正規化後的小寫冒號格式 |
| api_key_hash | |
| owner_id / site_id | |
| provisioning_token_id | 是哪一把 token 註冊的 |
| status | `active` / `disabled` / `retired` |
| registered_at / last_registered_at / last_seen_at | |

### 5.3 `edge_device_audit`

紀錄 `registered` / `re_registered` / `key_rotated` / `rejected_409` / `rejected_401`，含時間、來源 IP、token_prefix、device_uuid；**不含**任何 key 明文。

### 5.4 site_profile 來源

由 owner（業主）+ site（場域）+ 合約 / 授權資料組合而成。若 AIVMS 現在還沒有合約 / 授權欄位，第一階段先送已經有的欄位，其餘省略，並在 §10 註明。

---

## 6. 管理後台（AIVMS 端）

- 業主 / 場域頁：產生 provisioning token（明文只顯示一次）、設定配額與到期日、撤銷。
- 裝置列表：顯示 device_uuid、MAC、業主、場域、狀態、最後上線時間；可以停用、除役、手動輪替 api_key。
- 業主 / 合約資料的編輯畫面：欄位依 §3.6，驗證規則也和 §3.6 相同。

---

## 7. 安全要求

- token 與 api_key 只存 hash，並以常數時間比較。
- 不可把 token、api_key、統編、電話寫進 log；log 中的 MAC 可以保留（它是裝置識別，不是秘密）。
- 409 回應**不可**透露 MAC 目前屬於哪個業主。
- `/edge/register` 正式環境只接受 HTTPS；內網測試環境可以用 HTTP，但要在設定裡明確標示。
- 回應 header 加 `Cache-Control: no-store`。

---

## 8. 測試矩陣（必須全部自動化）

| # | 情境 | 預期 |
|---|---|---|
| 1 | 有效 token + 新 MAC | 200；api_key 格式合法；device_uuid 不為空；DB 只存 hash |
| 2 | 同 token + 同 MAC 再註冊一次 | 200；**同一個 device_uuid**；新 api_key；舊 key 打 `/edge/config` 回 401 |
| 3 | 不同業主的 token + 已註冊的 MAC | 409；`detail` 不含業主名稱 |
| 4 | 缺 token / 錯 token / 撤銷 / 過期 | 401 |
| 5 | MAC 格式錯、全 0、multicast | 422 |
| 6 | device_uuid 和 MAC 不一致 | 422 |
| 7 | device 已停用 | 403 |
| 8 | 超過配額 | 429 或 403 |
| 9 | 回傳的 api_key 打 `GET /edge/config` | 200；`device_uuid` 一致；有 `site_profile` |
| 10 | site_profile 的每個欄位 | 符合 §3.6 規則（`tax_id` 8 碼、`term_years` 是 int、日期格式） |
| 11 | 業主沒有合約資料 | 未建檔的欄位省略或為 null，不是 `""` |
| 12 | MAC 大小寫 / 分隔符號不同（`AA-BB-..`） | 視為同一台 |
| 13 | log / 錯誤訊息 | 搜尋不到 token、api_key 明文 |
| 14 | 回應時間 | < 6 秒（建議 < 1 秒） |

---

## 9. 契約驗證腳本

存成 `scripts/reach_register_contract.py`（只用 Python 標準庫）。對 AIVMS 測試環境執行，全部 PASS 才能交付給 REACH 測試。

```python
#!/usr/bin/env python3
"""REACH AI BOX <-> AIVMS /edge/register 契約驗證。

用法：
  AIVMS_API_URL=http://127.0.0.1:8000 \
  REACH_TEST_TOKEN=<有效 token> \
  REACH_OTHER_TOKEN=<另一業主的 token，選填> \
  python scripts/reach_register_contract.py
token 只從環境變數讀，絕不印出。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = os.environ["AIVMS_API_URL"].rstrip("/").removesuffix("/api/v1")
TOKEN = os.environ["REACH_TEST_TOKEN"]
OTHER = os.environ.get("REACH_OTHER_TOKEN", "")
KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{16,128}$")
PHONE_RE = re.compile(r"^[0-9+()#\- ]{0,32}$")
PROFILES = {"office", "construction", "factory", "security"}
SITE_KEYS = {
    "site_name", "profile", "site_code", "host_code", "license_code", "license_until",
    "contract_no", "term_years", "transaction_type", "company_name", "company_address",
    "company_phone", "tax_id", "contact_name", "contact_phone",
}
results: list[tuple[str, bool, str]] = []


def call(method: str, path: str, headers: dict, body: dict | None = None) -> tuple[int, dict, float]:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(f"{API}{path}", data=data, method=method,
                  headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    start = time.monotonic()
    try:
        with urlopen(req, timeout=6) as resp:
            return resp.status, json.loads(resp.read() or b"{}"), time.monotonic() - start
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except ValueError:
            payload = {}
        return exc.code, payload, time.monotonic() - start


def check(name: str, ok: bool, note: str = "") -> None:
    results.append((name, ok, note))


def random_mac() -> str:
    first = (secrets.randbits(8) & 0xFC) | 0x02  # 本地管理、unicast，不會撞到實體網卡
    rest = [secrets.randbits(8) for _ in range(5)]
    return ":".join(f"{b:02x}" for b in [first, *rest])


def uuid_of(mac: str) -> str:
    return "REACH-" + re.sub(r"[:\-.]", "", mac).upper()


def register(mac: str, token: str, device_uuid: str | None = None):
    headers = {"X-Provisioning-Token": token} if token else {}
    return call("POST", "/api/v1/edge/register", headers,
                {"device_uuid": device_uuid or uuid_of(mac), "mac_address": mac})


def validate_site_profile(sp) -> str:
    """回傳錯誤說明；空字串代表通過。規則同 BOX 端 app/site_settings.py。"""
    if sp is None:
        return ""
    if not isinstance(sp, dict):
        return "site_profile 不是 object"
    extra = set(sp) - SITE_KEYS
    if extra:
        return f"多餘鍵 {sorted(extra)}"
    v = {k: x for k, x in sp.items() if x is not None}
    if "term_years" in v and (isinstance(v["term_years"], bool) or not isinstance(v["term_years"], int)
                              or not 0 <= v["term_years"] <= 99):
        return "term_years 必須是 0~99 的整數"
    for k in SITE_KEYS - {"term_years"}:
        if k in v and not isinstance(v[k], str):
            return f"{k} 必須是字串"
        limit = 256 if k == "company_address" else 128
        if len(v.get(k, "")) > limit:
            return f"{k} 超過 {limit} 字"
    if "profile" in v and v["profile"] not in PROFILES:
        return "profile 不合法"
    if v.get("license_until") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v["license_until"]):
        return "license_until 必須是 YYYY-MM-DD"
    if v.get("transaction_type", "") not in ("", "buyout", "lease"):
        return "transaction_type 不合法"
    if v.get("tax_id") and not re.fullmatch(r"\d{8}", v["tax_id"]):
        return "tax_id 必須是 8 位數字"
    for k in ("company_phone", "contact_phone"):
        if k in v and not PHONE_RE.fullmatch(v[k]):
            return f"{k} 格式錯"
    return ""


def main() -> int:
    mac = random_mac()

    status, body, elapsed = register(mac, TOKEN)
    check("1 新 MAC 註冊 200", status == 200, f"HTTP {status}")
    check("14 回應 < 6 秒", elapsed < 6, f"{elapsed:.2f}s")
    key1 = str(body.get("api_key", ""))
    dev1 = str(body.get("device_uuid", ""))
    check("1 api_key 格式", bool(KEY_RE.fullmatch(key1)))
    check("1 device_uuid 不為空", bool(dev1))
    err = validate_site_profile(body.get("site_profile"))
    check("10 register site_profile 規則", not err, err)

    status, cfg, _ = call("GET", "/api/v1/edge/config", {"X-Device-Key": key1})
    check("9 api_key 可打 /edge/config", status == 200, f"HTTP {status}")
    check("9 device_uuid 一致", cfg.get("device_uuid") == dev1)
    check("9 /edge/config 有 site_profile 鍵", "site_profile" in cfg)
    err = validate_site_profile(cfg.get("site_profile"))
    check("9 /edge/config site_profile 規則", not err, err)

    status, body2, _ = register(mac.upper().replace(":", "-"), TOKEN, uuid_of(mac))
    check("2/12 重新註冊（大寫、- 分隔）200", status == 200, f"HTTP {status}")
    check("2 device_uuid 不變", body2.get("device_uuid") == dev1)
    key2 = str(body2.get("api_key", ""))
    if key2 and key2 != key1:
        status, _, _ = call("GET", "/api/v1/edge/config", {"X-Device-Key": key1})
        check("2 舊 key 失效", status == 401, f"HTTP {status}")

    if OTHER:
        status, _, _ = register(mac, OTHER)
        check("3 他業主 token -> 409", status == 409, f"HTTP {status}")

    check("4 缺 token -> 401", register(random_mac(), "")[0] == 401)
    check("4 錯 token -> 401", register(random_mac(), "invalid-" + secrets.token_hex(8))[0] == 401)
    check("5 全 0 MAC -> 422", register("00:00:00:00:00:00", TOKEN)[0] == 422)
    check("5 multicast MAC -> 422", register("01:00:5e:00:00:01", TOKEN)[0] == 422)
    check("5 MAC 格式錯 -> 422", register("not-a-mac", TOKEN, "REACH-XYZ")[0] == 422)
    check("6 device_uuid 不一致 -> 422", register(random_mac(), TOKEN, "REACH-000000000001")[0] == 422)

    raw = json.dumps([body, body2, cfg], ensure_ascii=False)
    check("13 回應不含 token", TOKEN not in raw)

    width = max(len(n) for n, _, _ in results)
    failed = 0
    for name, ok, note in results:
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else note}")
    print(f"\n{len(results) - failed}/{len(results)} passed  (測試裝置 device_uuid={dev1}，請在後台除役)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

> 腳本會建立測試裝置（MAC 是本地管理位址，不會和實體網卡衝突）。跑完請在後台除役，或只在測試環境執行。

---

## 10. 交付清單（AIVMS → REACH）

請在完成後回填並交給 REACH 團隊：

- [ ] `POST /api/v1/edge/register` 已上線的環境與 base URL
- [ ] `GET /api/v1/edge/config` 已加入 `site_profile`
- [ ] device_uuid 編碼規則（例：`REACH01` 流水號，或沿用 `REACH-<MAC>`）
- [ ] token 範圍：依業主 / 依場域 / 全平台共用（擇一）
- [ ] 配額超過時回 429 還是 403
- [ ] site_profile 第一階段**沒有**提供的欄位清單
- [ ] §9 契約腳本執行結果（全部 PASS 的輸出）
- [ ] 測試用 provisioning token（**另外安全傳送**，不要寫在文件或 git 裡）

---

## 11. REACH BOX 端的對應實作（參考，AIVMS 不需修改）

| BOX 檔案 | 用途 |
|---|---|
| `app/integrations/aivms_bootstrap.py` | `claim_by_mac()` 送出 §3.1 的請求；`normalize_mac` / `device_uuid_from_mac` |
| `app/api/aivms_admin.py` | `/api/admin/aivms/auto-bind`；把 401/409/503 對應成畫面訊息 |
| `app/site_settings.py` | `validate_site_settings()`：§3.6 規則的來源 |
| `app/integrations/aivms_mqtt.py` | MQTT `edge/{device_uuid}/status` / `heartbeat` / `cameras/{code}/status` / `logs` |
