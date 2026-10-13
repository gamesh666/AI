# 交付清單：AIBOX SERVER → REACH（回覆 `CLAUDE.md` §10）

> 對應契約：`docs/reach-edge-register/CLAUDE.md`（2026-10-12 版）
> 實作：`backend/app/services/provisioning.py`、`backend/app/services/site_profile.py`、`backend/app/api/v1/edge.py`

| 項目 | 回覆 |
|---|---|
| `POST /api/v1/edge/register` 環境與 base URL | 測試環境：`http://192.168.0.179:8000`（經 Tailscale 子網路由，傳輸由 WireGuard 加密；**內網測試環境，HTTP**）。正式對外環境改 HTTPS 後另行通知 |
| `GET /api/v1/edge/config` 加入 `site_profile` | ✅ 已加入，並新增 `site_id`（場域 ID；無場域時為 `""`）。原有欄位不變。另提供選配 `GET /api/v1/edge/site-profile` |
| device_uuid 編碼規則 | 依佈建權杖設定的前綴流水號：預設 `REACH01`、`REACH02`…（超過 99 為 `REACH100`）。管理員事先在平台填好 MAC 的裝置（預先綁定），註冊時沿用該裝置原本的 ID。指派後不變 |
| token 範圍 | **依業主**，可另外指定場域。同業主的權杖可重新綁定同一台；其他業主的權杖對已註冊 MAC 回 409 |
| 配額超過 | **403**，`detail` 說明「已達此佈建權杖的註冊台數上限」。429 只用於速率限制 |
| site_profile 第一階段未提供的欄位 | **無**，15 個欄位都支援。管理員沒填的欄位會**省略**（不會送 `""`）。`site_name` 有場域時為場域名稱、只有業主時為業主名稱；`host_code` = device_uuid；`site_code` = site_id |
| §9 契約腳本結果 | 見下方，**20/20 PASS** |
| 測試用 provisioning token | 另以安全管道提供（不寫在文件或 git） |

## 補充說明

- **錯誤格式**：一律 `{"detail": "<說明>"}`（含 422）。所有 `/api/v1/edge/*` 回應都帶 `Cache-Control: no-store`。
- **速率限制**：同一來源 IP + 權杖每分鐘 10 次；同一 IP 連續 5 次 401 → 封鎖 15 分鐘（期間回 429）。
- **停用 / 除役**：裝置被停用或除役後，`/edge/register` 回 403，且該裝置的 `X-Device-Key` 呼叫也回 403、推流被拒、MQTT 心跳與紀錄不再處理。
- **重新註冊**：同業主權杖 + 同 MAC → 同一個 device_uuid、新 api_key、舊 key 立即失效（401）。
- **稽核**：registered / re_registered / key_rotated / rejected_401 / rejected_403 / rejected_409，含時間、來源 IP、權杖前綴、MAC，不含任何金鑰或權杖。
- **MQTT**：仍使用平台固定帳密（不是 api_key），topic 前綴 `edge/{device_uuid}/`。
- 不帶 `mac_address` 的舊註冊方式只供 edge-agent 使用，無法接管已依 MAC / 業主佈建的裝置。

## §9 契約腳本輸出（測試環境，2026-10-12）

```text
PASS  1 新 MAC 註冊 200                   
PASS  14 回應 < 6 秒                      
PASS  1 api_key 格式                     
PASS  1 device_uuid 不為空                
PASS  10 register site_profile 規則      
PASS  9 api_key 可打 /edge/config        
PASS  9 device_uuid 一致                 
PASS  9 /edge/config 有 site_profile 鍵  
PASS  9 /edge/config site_profile 規則   
PASS  2/12 重新註冊（大寫、- 分隔）200            
PASS  2 device_uuid 不變                 
PASS  2 舊 key 失效                       
PASS  3 他業主 token -> 409               
PASS  4 缺 token -> 401                 
PASS  4 錯 token -> 401                 
PASS  5 全 0 MAC -> 422                 
PASS  5 multicast MAC -> 422           
PASS  5 MAC 格式錯 -> 422                 
PASS  6 device_uuid 不一致 -> 422         
PASS  13 回應不含 token                    

20/20 passed  (測試裝置 device_uuid=<測試裝置>，請在後台除役)
```

另有自動化整合測試涵蓋 §8 全部 14 項（含契約腳本未測的 3 他業主 409、7 停用 403、8 配額、11 無合約資料時省略欄位、
13 log 不含機密、速率限制、預先綁定），`backend/tests/integration/test_register_contract.py`：18/18 PASS。
