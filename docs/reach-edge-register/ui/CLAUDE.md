# CLAUDE.md — AIVMS 後台 UI 風格規範（對齊 REACH AI BOX）

> 給 AIVMS server 後台的 Claude Code 讀。目標：AIVMS 後台的外觀與 REACH AI BOX（`http://192.168.0.19:8920/`）
> 一致，同樣支援「**Claude 色調**（暖白、預設）」與「**科技風**（深海軍藍）」兩套主題切換。
>
> 來源（真實值，非目測）：REACH AI BOX `web/index.html` 內嵌 `:root`、`web/assets/overview.css`（2026-10-14 版）。
> 規範有疑義時以這兩個檔案為準；不要自己發明新色。
> 本文件只管外觀；裝置註冊 API 契約見同目錄上層的 [`../CLAUDE.md`](../CLAUDE.md)。

---

## 0. 硬性規則（MUST）

1. **所有顏色只能用 CSS 變數**（`var(--xxx)`）。元件 CSS 內不得寫死 hex，例外只有本文件 §4「狀態色板」列出的固定值。
2. **兩套主題用同一份 DOM**，只靠 `<html data-theme="claude|tech">` 切換。不得為兩套主題寫兩份 HTML。
3. 預設主題 = Claude 色調（不設 `data-theme` 或 `data-theme="claude"`）。
4. 主題選擇存 `localStorage['reach.theme']`（與 AI BOX 同 key）；必須在 `<head>` 內、樣式之前套用，避免科技風重整時閃白（§6）。
5. 字型、圓角、陰影、間距用 §3 的數值；數字一律 `font-variant-numeric: tabular-nums`。
6. 版面要能在 375px 手機寬度下無水平捲軸（§7 斷點）。
7. 若 AIVMS 已有前端框架，**用 CSS 變數覆寫該框架的主題**，不要另外引入新 UI 框架。AI BOX 本身是純 CSS + 原生 JS + 內嵌 SVG sprite icon。

---

## 1. 設計語言摘要

| 面向 | Claude 色調（預設） | 科技風 |
|---|---|---|
| 感覺 | 暖白紙感、陶土橘強調色、柔和陰影 | 深海軍藍、青色（cyan）發光、網格底紋 |
| 底色 | `#F5F2EC` 米白 | `#06101F` 近黑藍 |
| 卡片 | `#FFFCF8` + 1px 暖灰邊 | `#0B1A31` + 半透明藍邊 |
| 強調色 | 陶土 `#C66A49` / `#B85B3D` | 青 `#29C5F6` / `#5AD3FA` |
| 數值色 | 陶土橘（`--blue-hi`） | 青色 |
| 核心面板 | 與一般卡片同為暖白，重點面板帶橘色微光 | 海軍藍漸層 + 青色外發光 `.glow` |

> ⚠️ 歷史命名：變數 `--blue` 在 Claude 色調下其實是**陶土橘**。沿用此名稱以保持與 AI BOX 一致，不要改名。

---

## 2. 色彩 Token（直接複製）

```css
/* ===== Claude 色調（預設）===== */
:root{
  color-scheme:light;
  --bg:#F5F2EC;--side:#F2EEE8;--panel:#FFFCF8;--panel2:#EFEAE3;--line:#E6DED5;--line2:#D8CEC2;
  --ink:#302C29;--ink2:#4A443E;--muted:#786F67;--faint:#A39B90;
  --blue:#C66A49;--blue-hi:#B85B3D;--blue-dim:#F6E3D9;          /* 主強調色（陶土橘） */
  --ok:#398568;--ok-dim:#E3F0E9;
  --warn:#C58A36;--warn-dim:#F7EDDA;
  --bad:#C75750;--bad-dim:#F8E5E2;
  --purple:#A85A3C;
  --radius:14px;
  --shadow:0 1px 2px rgba(31,30,29,.05),0 4px 14px rgba(31,30,29,.05);

  /* 兩主題共用的固定色（科技風核心面板、訊號燈） */
  --navy:#0B1B35;--navy2:#0F2547;--navy3:#132C52;
  --navy-line:rgba(88,146,214,.28);--navy-text:#EAF2FF;--navy-muted:#8FA6C6;
  --cyan:#29C5F6;--cyan-dim:rgba(41,197,246,.14);
  --sig-ok:#22C55E;--sig-warn:#F59E0B;--sig-bad:#EF4444;--sig-idle:#7C8BA3;
  --chart-ink:#87867F;--chart-grid:rgba(31,30,29,.08);
}

/* ===== 科技風 ===== */
:root[data-theme="tech"]{
  color-scheme:dark;
  --bg:#06101F;--side:#081427;--panel:#0B1A31;--panel2:#0F2340;
  --line:rgba(88,146,214,.22);--line2:rgba(88,146,214,.34);
  --ink:#EAF2FF;--ink2:#C9D8EE;--muted:#8FA6C6;--faint:#6A7F9E;
  --blue:#29C5F6;--blue-hi:#5AD3FA;--blue-dim:rgba(41,197,246,.14);
  --ok-dim:rgba(34,197,94,.14);--warn-dim:rgba(245,158,11,.14);--bad-dim:rgba(239,68,68,.14);
  --shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.35);
  --chart-ink:#8FA6C6;--chart-grid:rgba(143,166,198,.16);
}
```

### Token 用途對照

| Token | 用途 |
|---|---|
| `--bg` | 頁面底色、頂欄底色 |
| `--side` | 側邊欄底色 |
| `--panel` | 卡片 / 面板底色 |
| `--panel2` | 卡片內的次層區塊（指標格、hover、切換鈕底座） |
| `--line` / `--line2` | 一般分隔線 / 較強的邊框（pill、按鈕） |
| `--ink` / `--ink2` | 標題與主要文字 / 次要內文 |
| `--muted` / `--faint` | 說明文字、單位 / 群組標籤、頁尾 |
| `--blue` / `--blue-hi` / `--blue-dim` | 強調色：focus 外框、量表 / 數值、選中文字 / 選中底色 |
| `--ok` `--warn` `--bad`（+ `-dim`） | 狀態文字 / 狀態底色 |
| `--sig-*` | 環形圖、紅點徽章、事件色塊等「訊號燈」 |

---

## 3. 字型、尺寸、形狀

```css
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:ui-sans-serif,-apple-system,"Segoe UI","Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;
  font-size:14px;line-height:1.55;min-height:100vh}
.serif{font-family:Georgia,"Times New Roman","Noto Serif TC",serif}  /* 品牌字 */
```

| 元素 | 字級 / 字重 |
|---|---|
| 品牌標題（側欄） | 21px / 600，serif；產品名後半段（如 `AI BOX`）用 `<em>` 上 `--blue-hi`、不斜體 |
| Hero 頁標題 | 30px / 700，letter-spacing .04em（≤600px 降為 24px） |
| 區塊頁標題 `.vhead h2` | 21px / 600 |
| 核心面板標題 | 19px / 700 |
| 卡片標題 | 15px / 700 |
| KPI 大數字 | 26px / 700，tabular-nums |
| 模組指標數字 | 19px / 700，顏色 = 強調色 |
| 內文 | 13–14px |
| 說明 / meta | 11–12.5px，`--muted` |

| 形狀 | 值 |
|---|---|
| 卡片圓角 | 14px（`--radius`）；核心面板 16px；Hero 18px |
| 內層格子圓角 | 10–12px |
| 側欄項目 / 按鈕 | 9px |
| Pill / 徽章 | 999px |
| 邊框 | 一律 1px |
| 卡片間距 | 12–16px gap |
| 內容區 padding | 22px 24px 40px（手機 16px） |
| Icon | 18px 線條 icon：`fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap/linejoin:round` |

---

## 4. 狀態色板（唯一允許寫死的值）

狀態一律用 `data-state="ok|warn|bad|idle"` 屬性驅動，**不要用不同 class 名稱**。

整體狀態 pill / 模組狀態文字：

| 狀態 | Claude 色調：文字 / 邊框 / 底 | 科技風：文字 / 邊框 / 底 |
|---|---|---|
| ok 正常 | `#3F7A46` / `#C4D6BE` / `#EDF3EA` | `#4ADE80` / `rgba(34,197,94,.45)` / `rgba(34,197,94,.10)` |
| warn 注意 | `#9A6A1B` / `#E4CE9E` / `#F8EFDC` | `#FBBF4C` / `rgba(245,158,11,.5)` / `rgba(245,158,11,.10)` |
| bad 異常 | `#A03A2E` / `#E0B3AC` / `#F6E4E1` | `#F87171` / `rgba(239,68,68,.5)` / `rgba(239,68,68,.10)` |
| idle 待命 | `var(--muted)` | `var(--sig-idle)` |

服務 / 攝影機狀態小標 `.svc-pill`（線上 / 離線）：

| | Claude 色調 | 科技風 |
|---|---|---|
| on | `#15803D` / `#9ED9B1` / `#E6F6EC` | `#4ADE80` / `rgba(74,222,128,.4)` / `rgba(34,197,94,.12)` |
| warn | `#C2620E` / `#F3C48E` / `#FDF0E1` | `#FBBF4C` / `rgba(245,158,11,.4)` / `rgba(245,158,11,.12)` |
| off | `#C53030` / `#F1B0AB` / `#FDECEA` | `#F87171` / `rgba(239,68,68,.4)` / `rgba(239,68,68,.12)` |

科技風狀態點加發光：`box-shadow:0 0 8px currentColor`；Claude 色調**不加發光**（`box-shadow:none`）。

KPI 圓形 icon 底色（Claude 色調；科技風統一 `background:rgba(255,255,255,.06)`，icon 色不變）：

| class | 底 / icon |
|---|---|
| `.green` | `var(--ok-dim)` / `var(--ok)` |
| `.orange` | `#FDEBDC` / `#EA7A2E` |
| `.red` | `#FDE4E1` / `#E5484D` |
| `.blue` | `#FBE4D6` / `#B85C3F` |
| `.sky` | `#FBEFE3` / `#D98A3F` |
| `.amber` | `#FDEEDC` / `#E8862A` |

事件徽章（清單左側日期方塊，34px、圓角 9px、白字）：預設 `#E8A33C`；嚴重（如 `long_away`）= `--sig-bad`；恢復（如 `returned`）= `--ok`。

---

## 5. 版面骨架與元件

### 5.1 App 殼層

```
┌──────────┬───────────────────────────────────────────────────────────────┐
│ Sidebar  │ Topbar 54px（sticky）：主題切換 | 連線 pill | … | 場域 | 時鐘 | 🔔 | ☀ | 使用者+角色 │
│ 220px    ├───────────────────────────────────────────────────────────────┤
│ sticky   │ Content（padding 22/24/40）                                    │
│ --side   │   Hero（頁標題 + 關鍵資訊列 + 右側設定卡）                      │
│          │   KPI × 6                                                      │
│ 品牌     │   核心雙面板（系統狀態 | 運算 / 硬體狀態）                       │
│ 導覽     │   底部雙卡（裝置 / 攝影機清單 | 近期事件）                       │
│ 系統設定 │                                                                │
│ 登出     │                                                                │
│ 版本頁尾 │                                                                │
└──────────┴───────────────────────────────────────────────────────────────┘
```

- `.shell{display:flex}`；`.sidebar{flex:0 0 220px;position:sticky;top:0;height:100vh;overflow-y:auto;background:var(--side);border-right:1px solid var(--line);padding:18px 12px 14px}`
- 側欄項目：`padding:9px 12px;border-radius:9px;font-size:13.5px;color:var(--ink2)`；hover → `background:var(--panel)`；
  **選中** → `background:var(--blue-dim);border:1px solid #EBC3AE;color:var(--blue-hi);font-weight:600`
  （科技風邊框改 `rgba(41,197,246,.4)`）。右側可放計數 badge（11px muted）。
- 群組標籤（如「系統設定」）：11px / 600 / `--faint` / letter-spacing .06em。
- 登出按鈕（側欄底部、全寬）：Claude 色調 `--blue-dim` 底 + `#EBC7B6` 邊 + `--blue-hi` 字；
  科技風改紅色系 `background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.4);color:#FCA5A5`。
- 側欄頁尾：版本號、平台名、主機 IP，11px `--faint`，上方 1px `--line`。
- 頂欄：`height:54px;background:var(--bg);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;padding:0 22px`。
  連線 pill：999px 圓角、`--line2` 邊、`--panel` 底、8px 綠點（`--ok` + `0 0 6px` 光暈）。
  使用者頭像：30px 圓、`linear-gradient(135deg,#E8A37A,#C4633C)`；角色 pill 用 `--blue-dim` / `--blue-hi`。

### 5.2 主題切換鈕（必備，放頂欄最左）

```html
<div class="theme-switch" role="group" aria-label="介面色調">
  <button type="button" data-theme-btn="claude" class="active">☀ Claude 色調</button>
  <button type="button" data-theme-btn="tech">☾ 科技風</button>
</div>
```
```css
.theme-switch{display:inline-flex;gap:4px;padding:3px;border-radius:12px;background:var(--panel2);border:1px solid var(--line)}
.theme-switch button{display:inline-flex;align-items:center;gap:6px;border:0;background:transparent;color:var(--muted);
  font:inherit;font-size:13px;font-weight:600;padding:6px 12px;border-radius:9px;cursor:pointer;transition:background .15s,color .15s}
.theme-switch button.active{background:var(--panel);color:var(--blue-hi);box-shadow:var(--shadow)}
.theme-switch button:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
```

### 5.3 一般卡片

```css
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);min-width:0;overflow:hidden}
.card-head{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 16px 8px}
.card-head h3{margin:0;font-size:15px;font-weight:700;color:var(--ink)}
.card-head .meta{font-size:12px;color:var(--muted)}   /* 例：「共 6 台 · 線上 3 · 離線 3」 */
```
清單列分隔用 `1px dashed var(--line)`，最後一列無線。表格列分隔用 `1px solid var(--line)`。

### 5.4 KPI 卡（一排 6 張）

```css
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}
.kpi{display:flex;align-items:center;gap:14px;padding:14px 16px;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;box-shadow:var(--shadow);min-width:0}
.kpi-ic{width:46px;height:46px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0}
.kpi-k{font-size:12.5px;color:var(--muted);white-space:nowrap}
.kpi-v b{font-size:26px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1.1}
.kpi-v small{font-size:11.5px;color:var(--muted)}
```
比例型 KPI（如「攝影機上線數 3/5」）的 icon 改用 conic-gradient 環，數值用 `--ok` 色：
```css
.kpi-ring{--pct:0;background:conic-gradient(var(--ring,var(--ok)) calc(var(--pct)*1%),var(--ok-dim) 0)}
.kpi-ring[data-state="warn"]{--ring:var(--sig-warn)}.kpi-ring[data-state="bad"]{--ring:var(--sig-bad)}
.kpi-ring>span{width:36px;height:36px;border-radius:50%;background:var(--panel);display:inline-flex;align-items:center;justify-content:center}
```

### 5.5 核心面板（兩主題差異最大的元件）

- 科技風：
  `.navy-panel{background:linear-gradient(160deg,var(--navy2),var(--navy) 60%);border:1px solid var(--navy-line);border-radius:16px;color:var(--navy-text);box-shadow:0 10px 28px rgba(9,23,49,.22)}`
  重點面板加 `.glow`：`border-color:rgba(41,197,246,.55);box-shadow:0 0 0 1px rgba(41,197,246,.25),0 0 26px rgba(41,197,246,.18),0 10px 28px rgba(9,23,49,.25)`
- Claude 色調（`:root:not([data-theme="tech"])` 覆寫）：與一般卡片相同（`--panel` 底、`--line` 邊、`--shadow`）；
  `.glow` 改 `border-color:#EBC7B6;box-shadow:0 0 0 1px #F3DCCF,0 0 22px rgba(217,119,87,.10),var(--shadow)`。
- 標題列右側放整體狀態 pill `.overall[data-state]`（例：「● 2 項需注意」），配色見 §4。
- **模組格 `.bus-mod`**（3 欄 × N 列，gap 10px）：標題列 = 22px icon（強調色）+ 名稱 15px/700 + 右側「● 正常」；
  下方兩格指標以 1px 中線分隔、置中，數字 19px/700 強調色、標籤 12px。
  科技風底 `rgba(8,20,40,.55)` + `rgba(41,197,246,.35)` 邊；Claude 色調底 `--panel2` + `--line` 邊。
  `data-state="warn|bad"` 時邊框換成 §4 對應邊框色。
- **環形量表 `.gauge`**（CPU / GPU / RAM / 溫度，一排 4 個）：84px 外環、66px 內圓，
  `background:conic-gradient(var(--g) calc(var(--pct)*1%), <軌道色> 0)`，內圓字 17px/700。
  科技風 `--g:var(--cyan)`、軌道 `rgba(88,146,214,.18)`、內圓 `--navy`；
  Claude 色調 `--g:var(--blue)`、軌道 `#E6DED5`、內圓 `--panel`。超門檻 `data-state="warn"` → `--sig-warn`。
- 資訊格 `.hw-fact`（一排 5 格）、網路格 `.net-cell`（一排 4 格）：圓角 10px、小標 11–11.5px muted、值 13–13.5px/600；
  一律 `white-space:nowrap;overflow:hidden;text-overflow:ellipsis`。

### 5.6 Hero（每頁頂部標題區）

- 版型：`display:grid;grid-template-columns:minmax(0,1fr) 250px;min-height:168px;border-radius:18px;overflow:hidden`。
- 左：頁標題（30px/700）+ 一行說明（14px）+ 底部一排「36px 圓角 icon 方塊 + 小標 11px + 值 14px/600」的關鍵資訊。
- 右：設定卡（margin 14px、圓角 14px）：科技風 `rgba(7,17,35,.55)` + `backdrop-filter:blur(6px)`；Claude 色調 `rgba(255,255,255,.75)`。
- 背景：
  - 科技風 `radial-gradient(120% 140% at 78% 0%,rgba(41,197,246,.22),transparent 55%), linear-gradient(115deg,#091731 0%,#0E2850 52%,#12305C 100%)`
  - Claude 色調 `radial-gradient(120% 140% at 78% 0%,rgba(217,119,87,.12),transparent 55%), linear-gradient(115deg,#FFFDF9 0%,#FAF3E6 55%,#F5EADA 100%)`，加 `1px solid #EAE2D0` 邊
- `::before` 疊 28px 網格線並往右漸顯：`mask-image:linear-gradient(90deg,transparent 35%,#000 75%)`；
  網格色 Claude 色調 `rgba(31,30,29,.05)`、科技風 `rgba(88,146,214,.12)`。
- 右側可放插圖（AI BOX 是一棟 SVG 建築），Claude 色調用暖杏色系 `#FFFFFF → #F8E3CF`、科技風用海軍藍。
- 「待設定」類提示 pill：Claude 色調 `#F8EFDC` 底 / `#E4CE9E` 邊 / `#9A6A1B` 字；科技風 `rgba(245,158,11,.12)` / `.4` / `#FBBF4C`。

### 5.7 裝置 / 攝影機清單列

縮圖 128px（`aspect-ratio:16/10`、圓角 10px）+ 名稱 14px/700 + ID / 最後更新 12px muted + 「模型 / 延遲」meta + 右側 `.svc-pill`。
縮圖左上角狀態標 `.cam-live`：`--ok` 底白字「● 在線」；離線改 `--sig-bad` 底「● 離線」。
無影像佔位：Claude 色調 `linear-gradient(135deg,#FBEFE3,#F0DCC3)`。清單 `max-height:250px;overflow-y:auto`。

### 5.8 圖表

Canvas / SVG 圖表的軸字與格線讀 `--chart-ink`、`--chart-grid`，切主題時重繪。
線條顏色沿用狀態色與強調色，不要使用圖表庫的預設色盤。

---

## 6. 主題切換實作（照抄）

`<head>` 內、任何樣式表之前：
```html
<script>
(function () {
  try {
    var t = localStorage.getItem('reach.theme');
    if (t) document.documentElement.dataset.theme = t;
  } catch (e) { /* 無痕模式：維持 Claude 色調 */ }
})();
</script>
```

切換按鈕：
```js
const THEME_KEY = 'reach.theme';
function applyTheme(isTech) {
  document.documentElement.dataset.theme = isTech ? 'tech' : 'claude';
  try { localStorage.setItem(THEME_KEY, isTech ? 'tech' : 'claude'); } catch (e) { /* 無痕模式 */ }
  document.querySelectorAll('[data-theme-btn]').forEach(b =>
    b.classList.toggle('active', (b.dataset.themeBtn === 'tech') === isTech));
  // 有 canvas 圖表的頁面：在這裡觸發重繪
}
document.querySelectorAll('[data-theme-btn]').forEach(b =>
  b.addEventListener('click', () => applyTheme(b.dataset.themeBtn === 'tech')));
applyTheme(document.documentElement.dataset.theme === 'tech');
```

撰寫元件的慣例（與 AI BOX 相同）：
- 基底樣式用 token 寫；只有 token 表達不了的差異（發光、漸層、半透明邊）才寫主題專屬規則：
  科技風專屬用 `:root[data-theme="tech"] .xxx{…}`，Claude 色調專屬用 `:root:not([data-theme="tech"]) .xxx{…}`。
- 同一元件的兩主題規則放在一起，不要分散到不同檔案。
- `display:flex` 的元素加 `[hidden]{display:none}`，否則 `hidden` 屬性會失效（AI BOX 踩過）。

---

## 7. 響應式斷點

| 寬度 | 行為 |
|---|---|
| ≥2560px | 核心面板固定 2 欄、模組格 6 欄 |
| ≥1920px | 底部卡片固定 2 欄 |
| ≤1366px | KPI 6 → 3 欄 |
| ≤1300px | Hero 右側設定卡移到下方、插圖淡化 |
| ≤1100px | 側欄縮成 64px icon rail（隱藏文字與頁尾） |
| ≤900px | 模組格 3 → 2 欄、量表與網路格 4 → 2 欄；頂欄隱藏場域與時鐘、允許換行 |
| ≤600px | 全部單欄；KPI 1 欄；Hero 標題 24px；content padding 16px |

自適應格線用 `repeat(auto-fit, minmax(min(max(320px,42%),100%),1fr))`，避免出現窄直條卡片。
`@media (prefers-reduced-motion: reduce)` 時關閉量表與模組的 transition。

---

## 8. 文案慣例

- 介面語言：繁體中文；技術名詞保留英文（Dashboard、FPS、GPU、VRAM、Integrations）。
- 狀態用詞固定：**正常 / 注意 / 異常 / 待命**；連線：**即時連線 / 線上 / 離線 / 在線**。
- 數字與單位分開排版：大數字 + 小字單位或說明（`15.0` `即時平均`、`234 ms`、`3/5` `在線率 60%`）。
- 無資料顯示 `--`，不得顯示 `null` / `undefined` / `NaN`。

---

## 9. 完成前檢查清單

- [ ] 兩套主題都與 REACH AI BOX（`http://192.168.0.19:8920/`）同類頁面並排截圖比對過
- [ ] 元件 CSS 用 `grep -nE '#[0-9A-Fa-f]{3,8}\b'` 檢查：除 §2 token 定義與 §4 狀態值外，沒有寫死色碼
- [ ] 科技風下重整不閃白（head script 位置正確）
- [ ] 375px 寬無水平捲軸；1100px 側欄變 icon rail
- [ ] 所有數字欄位有 `tabular-nums`；長字串有 ellipsis，不撐破格子
- [ ] 按鈕與導覽項有 `:focus-visible{outline:2px solid var(--blue)}`
- [ ] 狀態皆由 `data-state` 驅動，切換主題時狀態色跟著換
