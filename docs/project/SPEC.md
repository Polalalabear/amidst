# SPEC：查找與追蹤的功能規格

返回 [README](README.md)。需求背景見 [PRD.md](PRD.md)，架構見 [SYSTEM_ARCH.md](SYSTEM_ARCH.md)。

> **本文件的地位**：這是對外說明用的規格摘要，**不是**介面契約。欄位名稱、錯誤碼與驗收測試以核心契約 `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md` 為準（見 [§8](#8-介面契約)）。本文件的規則來自 [D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) 與現有契約；契約還沒定的地方寫 **待補**。

## 1. case1 查找

### 1.1 輸入

| 欄位 | 必填 | 型式 | 說明 |
| --- | --- | --- | --- |
| 時間範圍 | **是** | 選單（開始、結束），台灣時間 | 經宣告時鐘換成來源時間（[§4](#4-宣告時鐘台灣時間)） |
| 地點 | 否 | 選單：區域 | 區域 ID 來自 region_graph，例如 r004 的 OUT_W、VEST_W、CORR_W、CORNER、CORR_N、R101、R102 |
| 特徵 | 否 | 選單：物件類別（＋人物顏色） | 類別來自 `configs/q1q5/class_alias_v1.json`@`796cc17` 的 80 個 COCO 標籤（status `PROPOSED`）；顏色只能用在 `person` |

D126：「先用選單。」自然語言輸入（Q3）不在 D126 的核心範圍內。

### 1.2 驗證規則

| # | 規則 | 違反時 |
| --- | --- | --- |
| V1 | 時間範圍必填 | 前端擋下，不送出 |
| V2 | 地點與特徵至少填一個 | 前端擋下，不送出 |
| V3 | 結束不得早於開始；不得跨午夜 | `TIME_EXPRESSION_INVALID`（`Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §3.2） |
| V4 | 選定 run 沒有宣告時鐘 | `CLOCK_MAPPING_MISSING`，不猜日期（同上 §3.2） |
| V5 | 時間範圍只有一部分有資料 | `PARTIAL`，列出沒涵蓋的時段；完全沒交集回 `OUT_OF_RANGE`（同上 §3.3） |
| V6 | 類別不在別名表 | `UNSUPPORTED_CLASS`；顏色用在非 person 回 `UNSUPPORTED_CONDITION`（同上 §6.1） |

V1、V2 是 D126 的新規則；在核心契約裡的錯誤碼名稱 **UNKNOWN**。

### 1.3 輸出

- 時間範圍內拍到目標的**鏡頭畫面**（每台鏡頭的命中片段與代表畫面）。
- **只給地點**：回傳 camera_graph `covered_regions` 涵蓋該區域的鏡頭在該時段的畫面。這只是「哪台鏡頭看得到那個區域」，**不代表**目標在那裡（`Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §6.1 `region_ids` 列）。
- **只給特徵**：回傳 RT-DETR COCO 偵測索引在該時段有命中的鏡頭。
- **兩者都給**：先用地點篩鏡頭，再用特徵篩命中。
- 沒有命中的鏡頭列為「沒有命中」，畫面寫「不代表目標不存在」（#397 §E.2.2）。
- 身分一律 `UNCONFIRMED`。

## 2. case2 追蹤

### 2.1 輸入

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| 特徵 | **是** | 選單；目前 Q2 linker 只支援人物（D126「可作為基石的既有資料」） |
| 地點 | 否 | 縮小起點搜尋範圍 |
| 時間 | 否 | **空著代表現在**（目前播放位置）。預錄或合成資料的「現在」怎麼定義：**待補**（看核心契約） |
| 顯示方式 | 是（有預設） | 單畫面／多畫面 |

### 2.2 輸出

| 狀態 | 單畫面 | 多畫面 |
| --- | --- | --- |
| 有鏡頭看到目標 | 一直播該鏡頭；目標離開後換到另一個看得到的鏡頭 | 顯示所有找到目標的鏡頭，目前追蹤所在鏡頭加框、標「目前畫面」（#408） |
| 沒有鏡頭看到目標（盲區） | 顯示俯視圖與物理預測曲線，標 `INFERRED` | 同左 |
| 完全跟丟 | 停止切換，明確顯示跟丟 | 同左 |

「完全跟丟」的判定條件（逾時、輪數）：**待補**。現有 Q2／Q5 狀態機的上限參數（W＝6 s、R＝1 s、`session_max_research_rounds`＝6）見 #397 §E.3.1 與 `Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §8.6、§11；核心契約是否沿用 **UNKNOWN**。

### 2.3 單畫面切鏡

- 切鏡決策只能來自系統推論：候選鏡頭由兩層圖與 D28 決定性排序產生，Agent 不排序、不增刪候選（`docs/DEVELOPMENT_RULES.md`@`796cc17` 第 63 行，D64）。
- 不得用劇本、情境卡、GT、渲染軌跡、可見性或深度模擬切鏡（[D124-1](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)）。
- 圖未核准時 fail-closed：B-05a live 停在 A＋GAP、不切鏡；B-05b 預錄在 5.15 s 切到 B（[D113](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6575688787)）。

### 2.4 盲區：俯視圖與物理預測曲線

- 俯視圖：**實線＝已觀測**（依時間軸上已發生的 ON_CAMERA 段連接鏡頭）；**虛線＝物理預測**，從最後鏡頭畫到候選鏡頭，旁標名次、時間窗與信心；圖例寫「虛線＝物理預測（示意，非實際路徑）」（`docs/contracts/DEMO_UI_SUPPORT_V1.md`@`796cc17` §7.1，PROPOSED）。
- 物理預測模組 `src/amidst/q1q5/physical_prediction.py`@`796cc17` 是純函式：用目標最後一段的偵測框估影像平面方向，排序出口與候選鏡頭，推算時間窗。**方向是影像平面方向，不是地板座標；時間窗是參數推算，不是量測**（契約 §6.5）。
- 信心分級 `UNKNOWN`／`LOW`／`MEDIUM`／`HIGH`；r004 v3／v3_1 圖是 DRAFT，所以永遠不會出 `HIGH`（契約 §6.2）。
- 回放時只能用 `≤ t` 的資料，往回拖要移除 t 之後才出現的線（契約 §7.2）。
- **目前狀態**：路由 `q_physical_prediction` 列在 `UNAVAILABLE_POST_ROUTES`，回 503 `Q_RESOURCE_UNAVAILABLE`（`src/amidst/q1q5/api.py`@`796cc17` 第 24、329 行），前端先用 SYNTHETIC 示意（`frontend/workbench-v2/fixtures/track-map/synthetic.json`@`796cc17`）。

## 3. 證據狀態

每個畫面元素都要標出它屬於哪一種，四種不能混用（[`AGENTS.md`@`796cc17`](https://github.com/Polalalabear/amidst/blob/796cc176cd40bedbfe701b95192d3c8679755aa9/AGENTS.md) Shared rules）：

| 狀態 | 意思 | 例子 |
| --- | --- | --- |
| `OBSERVED` | 從來源畫面的偵測直接得到 | A 鏡頭有框；B-05b 4.25 s B 的證據 `MATCH_STRONG` |
| `INFERRED` | 由系統依規則或圖推出來的 | 切鏡決策；盲區時的物理預測曲線（D126） |
| `MISSING` | 應該有、卻沒有的資料 | 沒有 RGB 的鏡頭顯示 MISSING 虛線框，不重複畫面湊格數（#397 §E.2.2） |
| `UNKNOWN` | 系統不知道 | 暫失後的位置；物理通行；未宣告的時鐘 |

另有兩個固定不變的標示：身分一律 `UNCONFIRMED`；物理通行與碰撞一律 `UNKNOWN`（`DEMO_UI_SUPPORT_V1.md`@`796cc17` §7.1 第 6 點）。

## 4. 宣告時鐘（台灣時間）

- Blender 畫面沒有真實拍攝時刻。每個 run 有一份宣告的展示時鐘 `clock_mapping`：`mapping_kind=DECLARED_DEMO_CLOCK`、`timezone=Asia/Taipei`、`rate=1`（`Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §3.1）。
- 換算：`wall = wall_origin + (source_us − t0_us)`。UI 要顯示「展示時鐘」，不得寫成實際拍攝時間。
- 現有宣告：

| run | 檔案 | wall_origin | 長度 |
| --- | --- | --- | --- |
| A4-1 `ctrl-lcorr-s1-a4-5fps-v1-r004` | `configs/q1q5/clocks/r004_a4_v1.json`@`796cc17` | 2026-11-01T14:00:00+08:00 | 50 s |
| B4-1 | `configs/q1q5/clocks/r004_b4_v1.json`@`796cc17` | 2026-11-01T14:10:00+08:00（#397 §E.3.1） | 42 s |
| P1 事件 | 該 run 的 `clock_mapping` | 2026-11-01 13:00 +08:00（#408 描述） | 8 s |

- 畫格標籤（#408）：第一行 `<鏡頭> · 2026-11-01 14:00:12.40（UTC+8）`，系統模式第二行 `+12.40 s · DECLARED_DEMO_CLOCK`。找不到宣告就顯示 `UNKNOWN`，不假設日期，不用牆鐘、GT 或渲染時間（[D124-5](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)）。
- 同一事件的所有鏡頭共用一個 run 與 clock；不同 run 的牆鐘重疊不代表是同一段時間，不得跨 run 串接人物（契約 §3.1）。

## 5. 倍速規則

- 提供 1×／1.5×／2×（[D125-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251)）。
- D126-4：只要前端顯示變快就好；實際達不到設定值時，**自動降到能達到的速度**，並在播放列顯示實際倍速。
- 實作（#408 第四批）：播放列小字「設定 2× · 實際 1.4×」。解碼跟不上時播放等影格就緒才前進、不跳格；實際倍速在停滯時下降，跳轉或暫停時重新量測。
- 標籤與演示時間**只由來源時間決定**，倍速不影響時間標示（#408 `speed.test.mjs`、`viewer.test.mjs`）。
- 已知限制：B-05b 錄製受解碼限制，設定 2× 時實際只約 0.2×，但演示時間與來源時間無漂移（#408 第三批實測）。

## 6. 畫面模式摘要

| 模式 | 用在 | 規則 |
| --- | --- | --- |
| 查看 | 所有事件 | 所有畫面一次顯示（#408） |
| 查找 | case1 | [§1](#1-case1-查找) |
| 追蹤：單畫面 | case2 | [§2.3](#23-單畫面切鏡) |
| 追蹤：多畫面 | case2 | [§2.2](#22-輸出) |
| 盲區 | case2 | [§2.4](#24-盲區俯視圖與物理預測曲線) |
| 系統／單純 | 疊加在上面任一模式 | 單純模式只留畫面與演示時間；證據不足時右上角顯示「證據不足」（運行手冊 §10@`796cc17`） |

尚未支援的事件照實標示：A4-1／B4-1 的追蹤顯示「追蹤結果尚未產生 · UNKNOWN」，查找顯示「查找尚未支援（需 #118 索引）· UNKNOWN」（#408）。

## 7. 輸出共通規則

- 每個結果帶 source／run／clock／hash。
- 「查無結果」只能對有資料、而且已推論的時段成立（`Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §3.3）。
- 同一正規化請求的輸出 hash 必須相同（同上 §6.1 `origin` 列）。

## 8. 介面契約

| 契約 | 狀態 | 和兩個核心的關係 |
| --- | --- | --- |
| **`docs/contracts/Q_CORE_SEARCH_TRACK_V1.md`**（新核心契約） | PROPOSED，分支 `claude/core-search-track-contract`（[D126-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045)）。**UNKNOWN**：本文件撰寫時該分支不在 GitHub 上，讀不到內容 | case1、case2 的欄位、錯誤碼與驗收測試以此為準 |
| `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` | 已核准事項依對應章節生效（D65～D82）；現行版在 `codex/q1q5-staging`（[`AGENTS.md`](https://github.com/Polalalabear/amidst/blob/796cc176cd40bedbfe701b95192d3c8679755aa9/AGENTS.md)） | 時間對應 §3、偵測索引 §4、兩層圖 §5、Q1 §6、Q2／Q5 §8、GT 隔離 §9 |
| `docs/contracts/DEMO_UI_SUPPORT_V1.md`@`796cc17` | PROPOSED | 鏡頭圖 API §2、物理預測 §6、俯視圖 UI §7 |
| `docs/contracts/Q1Q5_RESPONSE_V2_D92_20261027.md`@`796cc17` | D92 response v2 | Q2 回應格式 |
| `docs/contracts/Q1Q5_D86_G4_RECEIPT_PROPOSAL_20261027.md`@`796cc17` | PROPOSED | G4 圖核准收據 |
| `docs/contracts/OFFICE_*`@`796cc17`（4 份） | 舊 Office 線，DRAFT／歷史 | 不描述 Q1–Q5，僅供參考 |
| `docs/contracts/schemas/`、`examples/`@`796cc17` | — | JSON schema 與範例 |
