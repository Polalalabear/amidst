# Q1–Q5 產品規格（現行）

- 日期：2026-10-27。依據：[D91](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434355675) 第 2 項、計畫 [#263](https://github.com/Polalalabear/amidst/issues/263)。
- 本文取代已封存的 [PRD](PRD.md)、[SYSTEM_DESIGN](SYSTEM_DESIGN.md)、[ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)、[DATA_SCHEMA](DATA_SCHEMA.md)、[INTERFACES](INTERFACES.md) 對目前專案的導覽作用。封存索引見 [#264](https://github.com/Polalalabear/amidst/pull/264)（`docs/archive/ARCHIVE_20261027.md`，[@`3d012ff`](https://github.com/Polalalabear/amidst/blob/3d012ff995bf12db2e9442e6304fdecc6cb04fb2/docs/archive/ARCHIVE_20261027.md)，未合併）。
- **本文不新增規範。**每項敘述都只轉述既有決策（[#93](https://github.com/Polalalabear/amidst/issues/93) 的 D 編號）、契約與計畫，並附來源；查不到的寫 `UNKNOWN`。本文與來源不一致時，以來源為準。
- 規則以 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) 為準，本文不改它。
- 即時狀態以 [#93](https://github.com/Polalalabear/amidst/issues/93) 與 [進度導覽](../operations/Q1Q5_PROGRESS.md) 為準；本文只寫範圍、組成與介面。

**契約版本。**現行契約在 staging：`codex/q1q5-staging` @ `c1d9cbd` 的 [`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`](https://github.com/Polalalabear/amidst/blob/c1d9cbda51872de839a9c61a5b3b70ae8ff4e0f1/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)（檔案 SHA-256 `b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`，最後修改 commit `b507641`，[#237](https://github.com/Polalalabear/amidst/pull/237)）。mainline 的 [副本](../contracts/Q1_Q2_FIRST_DEMO_V1.md) 停在 `3873ff2`，不手改（[#263](https://github.com/Polalalabear/amidst/issues/263)「現行」一節）。下文的「契約 §x」都指 staging 版。

---

## 1. 產品目標與範圍

### 1.1 Q1–Q5

首要目標是 Q1–Q5，其餘先擺著（D63 修訂，[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6286156319)；摘要見契約 §0.2）：

| 編號 | 內容（D63 修訂原文的意思） | 契約章節 |
| --- | --- | --- |
| Q1 | 依某個條件調出相機 | §6 |
| Q2 | 找畫面中某個人 | §8（§8.5–§8.7） |
| Q3 | 盡可能理解使用者語意（自然語言 → 結構化查詢） | §7 |
| Q4 | 模型以自己的辨識判斷任意鏡頭 2D 畫面是否含目標 | §8.3 |
| Q5 | 目標離開鏡頭時，模型以現有資訊判斷是否切鏡，以維持追蹤 | §8.1、§8.4、§8.6 |

使用者要驗收的 Demo：使用者能選取或查看目標，畫面會跟著切到目標所在的鏡頭；驗收標準 AC1–AC8 見 [驗收計畫 §1](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)。驗收分兩階段：P1 工程預驗收與 P2 正式 baseline 驗收（D76，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396442549)；[驗收計畫 §2](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。

### 1.2 權限邊界（摘自契約 §1）

- 人物的出現、位置與跨鏡頭串接只從 safe RGB 的偵測結果推得；跨鏡頭結果是條件相符的候選串接，`identity_verdict` 一律 `UNCONFIRMED`（契約 §1；D63 (d)）。
- 「沒有偵測」不等於「不在畫面」或「已離開」（契約 §1）。
- 兩層圖只表示「依配置可能連通」，不是人體通行或碰撞認證；核准範圍以外的通行性一律 `UNKNOWN`（契約 §1）。
- Agent 與 LLM 只能經契約 §7、§8.4 的 typed tools 讀資料（契約 §1）。
- 第一版只用本機 Ollama 的 Qwen，不串接外部模型 API（契約 §1）。
- Agent 切鏡是 Q1–Q5 主線的規則例外（D64，[#86 留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727)；規則條文見 [DEVELOPMENT_RULES 第 63 行的 D64 條](DEVELOPMENT_RULES.md)，規則 PR [#125](https://github.com/Polalalabear/amidst/pull/125)）。

### 1.3 第一版不做

- 契約 §1：同色干擾、ByteTrack／OSNet／ReID、跨鏡頭身分確認、3D 重現與接地、魚眼／PTZ、GT 對照、研究級評估。
- D63 (a)：3D 重現線暫停保留，不關、不刪（契約 §0.2）。
- D63 修訂 (e)：第一版不放同色干擾人物，也不列同色歧義的完成條件（契約 §0.2）。
- D64：Q4 第一版只用 RT-DETR＋HSV，不用 VLM（契約 §13 Q-08）。
- [驗收計畫 §5](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)：OpenAI API（baseline 完成後當比較組，需先另做決定）、CAM_WIDE 100°（D76，第一版維持 90°）、新 HSV 提案 #158（D75，之後當比較組）。
- D77：r004 重疊區延後到 Q5 穩定後（[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6397771396)）；D90 第 2 項把重疊接手放進第二版（[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212)）。
- D72：`main` 暫不更新（[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6393392053)）。

---

## 2. 系統組成與資料流

Q1–Q5 專用的 pipeline 圖：`UNKNOWN`（未找到）。[OFFICE_PIPELINE_MAP](../engineering/OFFICE_PIPELINE_MAP.md) 是 Office 線的文件，依 [#263](https://github.com/Polalalabear/amidst/issues/263) 歸為歷史，不描述 Q1–Q5。以下依契約章節整理資料流：

```
r004 safe RGB（hash 驗證）
  └─(離線，RT-DETR＋HSV)→ 偵測索引（§4）
核准的 scene_static／校正／靜態可見範圍
  └─(Codex 產生、Claude 檢查、使用者核准)→ 兩層圖（§5.2 Region、§5.3 Camera Transition）
時鐘宣告 → 時間對應（§3）

使用者中文句 ─→ Q3 解析（§7，規則或 LLM）─→ 結構化查詢
                                          ├→ Q1 依條件找相機（§6，讀偵測索引）
                                          └→ Q2 起點（§8.5）
Q2 同鏡頭 IoU 連接（§8.2）─失聯→ Q5 狀態機（§8.6）
   候選鏡頭＝兩層圖＋D28 決定性排序（§5.4）
   RULE_ONLY／AGENT_SEQUENTIAL（§8.1）；Agent 經 typed tools（§8.4）讀 Q4 證據（§8.3）
   ─→ Q2 回應與逐步紀錄、journal（§8.7、§8.2）
輸出凍結 ─→ 評估端（§9、§9.1；D79 決策窗）
```

| 元件 | 要點 | 來源 |
| --- | --- | --- |
| 偵測索引 | 一律離線，查詢不補推論；RT-DETR 權重 SHA-256 `3ba8b5c9…66f0`、不另做 NMS | 契約 §4、§13 Q-07／Q-14 |
| 兩層圖 | Codex 產生、Claude 獨立檢查、使用者核准；圖與出口在事件渲染前凍結 | 契約 §5.1、§13 Q-15；D68、D74 |
| 候選鏡頭排序 | 兩層圖＋D28 三個原鍵，決定性；Agent 不排序、不增刪 | 契約 §5.4、§13 Q-03；D64 |
| Q5 兩種模式 | `RULE_ONLY`、`AGENT_SEQUENTIAL`；超過上限由決定性規則兜底，兜底接手整段 session | 契約 §8.1、§8.6；D71、D73 |
| 參數 | D65／D67 初值，依帶 hash 的 parameter_set 生效 | 契約 §11；D65、D67 |
| 儲存 | 第一版不用 PG；版本化 JSON＋JSONL／manifest（優先）或 SQLite；薄 provider 直連 Ollama | 契約 §10、§13 Q-13 |
| GT 隔離 | 人物設定、事件腳本、GT 軌跡／mask／visibility／depth 不進索引、圖、查詢、Agent 或 prompt | 契約 §9；[DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) |
| 評估 | Q2／Q5 輸出先凍結，評估端再讀獨立 hash-pinned 劇本，以逐事件決策窗評分 | 契約 §9；D71、D73、D75、D79；[Q5 決策窗](../evaluation/Q5_DECISION_WINDOW_D79.md) |

---

## 3. 資料 schema 一覽

所有 schema 定義在契約；本表只列名稱、版本與章節。`schema_version` 命名規則見契約 §2.2，共通回應欄位見契約 §2.3。

| Schema | 現行版本 | 契約章節 | 備註 |
| --- | --- | --- | --- |
| 偵測索引 manifest／逐格紀錄 | `q-demo.detection-index.v1` | §4.2、§4.3 | |
| 時間對應 | `q-demo.clock-mapping.v1` | §3.1 | |
| Region Connectivity Graph | `q-demo.region-graph.v1` | §5.2 | |
| Camera Transition Graph | `q-demo.camera-transition-graph.v1` | §5.3 | |
| r004 tracking scope | `q-demo.r004-tracking-scope.v3` | §5.1 附近（第 447 行） | D81 |
| Q1 請求／回應 | `q-demo.q1-request.v1`／`q-demo.q1-response.v1` | §6.1、§6.3 | D92 決定升 v2（見下） |
| 支援類別表 | `q-demo.supported-classes.v1` | §6.2、§14 | |
| Q3 解析請求／回應 | `q-demo.q3-parse-request.v1`／`q-demo.q3-parse-response.v1` | §7.1、§7.4 | D92 決定升 v2（見下） |
| Q3 LLM 輸出 | `q-demo.q3-llm-output.v1` | §7.1 | |
| 同鏡頭 link 紀錄（journal） | `q-demo.link-record.v2`（v1 只供已錄製版本重播） | §8.2 | D69、D78 |
| 候選證據 | `q-demo.candidate-evidence.v1` | §8.3、§8.4 | |
| Agent 決策 | `q-demo.agent-decision.v2`（v1 只供明確版本化的歷史重播） | §8.4 | D73 |
| Q2 請求／回應 | `q-demo.q2-request.v1`／`q-demo.q2-response.v1` | §8.5、§8.7 | D82；D92 決定升 v2（見下） |
| 決策紀錄 | `q-demo.decision-record.v1` | §8.7 | |
| session job | `q-demo.session-job.v1` | §8.7 附近（第 1089 行） | D82、D85 |
| 參數組 | `q-demo.parameter-set.v1` | §11 | |

**D92 的回應 v2 方向**（[D92 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)，#260-B 定案）：Q1／Q2／Q3 回應升 v2；`resolved_scope` 只加一個必填鍵 `time_range_source`，不加 `time_range_reason`；v1 錄製原樣重播；不改 D80 query preimage。staging 契約 @ `c1d9cbd` 與 [#260](https://github.com/Polalalabear/amidst/pull/260) @ `eed1bdb` 都還沒有 `time_range_source` 條文；v2 的 schema 名稱與哪個 PR 寫入契約：`UNKNOWN`。此方向源自 D86 第 2 項「沒寫時間時預設整段已選 run，並標明使用整段範圍」（[D86](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417558930)）。

---

## 4. 介面

### 4.1 後端 API

- 契約本身不定 HTTP 路徑；它定 schema 與 typed tools。路徑由 staging 的 [`src/amidst/q1q5/api.py`](https://github.com/Polalalabear/amidst/blob/c1d9cbda51872de839a9c61a5b3b70ae8ff4e0f1/src/amidst/q1q5/api.py) 實作，檔頭說明它是「既有同源工作台的 Q 線 route adapter」，路徑前綴 `/api/`。
- 在該檔讀到的 action：`q_bootstrap`、`q_frames`、`q_media_grant`、`q1_camera_search`、`q3_parse`、`q2_seed_candidates`、`q2_select_seed`、`q2_start_session`、`q2_poll_session`、`q2_stop_session`、`q2_artifact`、`q_manual_seed`、`q_record_response`、`q_recorded_response`。各 action 的正式介面文件：`UNKNOWN`（未找到）。
- stop 之後 API poll 的內層 Q2 回應是 `PARTIAL`＋`USER_STOPPED`，job 狀態另記 `STOPPED`（D82、D85，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416508414)）。
- 啟動方式（P1 工程預驗收）：可攜包 `./start.command`，或 `python3 -S app/scripts/start_q1q5_p1.py --bundle .`（staging [`docs/operations/Q1Q5_P1_START.md`](https://github.com/Polalalabear/amidst/blob/c1d9cbda51872de839a9c61a5b3b70ae8ff4e0f1/docs/operations/Q1Q5_P1_START.md)）。本機測試設定見 [Q1Q5_LOCAL_TEST_SETUP](../operations/Q1Q5_LOCAL_TEST_SETUP.md)。

### 4.2 前端 workbench

- Q1–Q5 畫面在 [`frontend/workbench-v2/`](../../frontend/workbench-v2/)；D63 (a)：workbench-v2 外框照常沿用（契約 §0.2）。畫面設計見 [WORKBENCH_V2_Q1Q5_DESIGN](../agents/WORKBENCH_V2_Q1Q5_DESIGN.md)。
- Demo 模式與審核模式（`?mode=review`）：審核模式顯示每一步的決策來源、候選、證據與 fallback 原因；Demo 模式不顯示內部判斷（D71；[驗收計畫 AC6](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。
- D86 第 3 項：Q1 結果牆放大並排、點命中不換掉整面牆、追蹤預設單一連續畫面、前端顯示 Q3 判成「找」或「追」（[D86](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417558930)）。
- 手動改選時由使用者在前端決定是否重啟 Agent（D73；[驗收計畫 CX-1](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。
- 畫面只做桌面版：`UNKNOWN`（無 D 編號；只見於協調者慣例，見 #263 的 10-27 交接項目）。

### 4.3 Agent 與 fallback

- 候選集合與排序由決定性模組產生；Agent 只在合法 top-k 內依序取偵測與顏色證據、決定是否切鏡；有輪數與時間上限，超過或失敗由決定性規則兜底；記錄 prompt、模型 digest、決策來源與 fallback 原因（D63 修訂、D64；[DEVELOPMENT_RULES D64 條](DEVELOPMENT_RULES.md)；契約 §0.3）。
- typed tools 與 `q-demo.agent-decision.v2`：契約 §8.4。Agent 不能掃描檔案、跑任意 SQL 或 shell，也不能產生新的鏡頭、區域或觀測 ID（契約 §1）。
- 預算：D65 原核准值與 D67 六項初值，見契約 §11（[D65](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432)、[D67](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288)）。D73 維持 D65 預算（契約 §0.1）。
- 兜底接手整段 session；fallback 時間只觀察（D71，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6308081801)）。
- Q3：規則語法先擴充當第一版 baseline，LLM 解析路徑保留（D86 第 1 項）；只有「紅色的人」「那個人」而沒有追蹤動詞時依查找規則判 Q1（D92 第 2 項，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)）。Q3 失敗與兜底見契約 §7.3。
- recorded replay：不連模型也能重播（[驗收計畫 AC1、AC7](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。

---

## 5. Line 1／Line 2 的範圍與里程碑

兩條線由 [D87](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959) 決定；工作分配見兩條線計畫 [#252](https://github.com/Polalalabear/amidst/pull/252)（`docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`，[@`0bce595`](https://github.com/Polalalabear/amidst/blob/0bce595e595e5e1e8c331ae58baf4c0dd335c7a8/docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md)，未合併）。Line 2 不得改 Line 1 已核定範圍（D87；D90 結尾）。

### 5.1 Line 1：第一版 r004 baseline

- 範圍：圖 v3 既有 8 台鏡頭與轉移、G4 範圍不變（D87 第 1、3 項）。工作分配見 [驗收計畫 §4](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)。
- 事件：A4-1 50 s、B4-1 42 s，各 1 個 Q2 場次（D89，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857)；情境卡 [#253](https://github.com/Polalalabear/amidst/pull/253)，未合併）。D92 第 1 項調整室外端與計分事件（8 → 6 或 5），長度、時鐘、評分器與 D79 不動。
- 評分範圍：SWITCH 空檔 ≤ 5.2 s、RETURN 暫失 < 1.8 s、每窗恰好一個已執行動作（D87 第 3 項；D90 第 1 項；[Q5 決策窗](../evaluation/Q5_DECISION_WINDOW_D79.md)）。
- catalog 凍結 `3eba8572…`，與 G4 脫鉤；8 台 `static_validity` 維持 `NOT_EVALUATED`（D84，[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416451756)）。
- 關鍵路徑：[驗收計畫 §3](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)。

| 順序 | 里程碑（兩條線計畫 §5） | 日期 |
| --- | --- | --- |
| 1 | Codex 完成審查回覆 | UNKNOWN |
| 2 | #238、#240、#228 合併；yyin 包打包 | UNKNOWN |
| 3 | 使用者核定情境卡；Codex 重發時鐘、重錄三包 | UNKNOWN |
| 4 | yyin 三題回來；G4 收據；使用者 G4 | UNKNOWN |
| 5 | CX-7 渲染；索引；CX-8 正式 baseline | UNKNOWN |
| 6 | P2 評估與驗收；Demo 腳本 | UNKNOWN |

兩條線計畫寫成時，第 3 項的「使用者核定情境卡」已由 D89 完成；其他項目的即時狀態見 [#93](https://github.com/Polalalabear/amidst/issues/93)。

### 5.2 Line 2：複雜場景

- 範圍：現行評分器與規則處理不了的情況：一窗多次 RETURN、長時間 LOST、D77 重疊接手、新鏡頭與新路線、較長多鏡頭行走（D87 第 1 項；傘狀 issue [#251](https://github.com/Polalalabear/amidst/issues/251)）。
- 長時間 LOST 由評估端分類，產品端不加狀態；重疊接手要先失聯、進入 SEARCHING 才可切（D90 第 1、2 項）。
- 第二版範圍分兩批（暫定）：第一批不需新場景，第二批需新場景版本、磁碟與渲染授權（D90 第 4 項）。

| 順序 | 里程碑（兩條線計畫 §5） | 日期 |
| --- | --- | --- |
| 1 | L2-7 使用者決策（已由 D90 處理，第 4 項仍暫定） | UNKNOWN |
| 2 | L2-1 評分規則草案；L2-2 情境卡 v2 規格；L2-4 診斷 | UNKNOWN |
| 3 | L2-5 契約提案；L2-3 長時間軸 | UNKNOWN |
| 4 | L2-6 工程小場景（需磁碟與授權）驗證 L2-4／L2-5 | UNKNOWN |
| 5 | 使用者決定哪些情境進第二版 | UNKNOWN |

---

## 6. 決策索引摘要

完整原文在 [#93](https://github.com/Polalalabear/amidst/issues/93)；契約已採用的決定見契約 §0.1、§14。每項一行，摘自決策標題或原文。

| D | 摘要 | 連結 |
| --- | --- | --- |
| D63 | Q1／Q2 主線、r004 另存、HSV 顏色訊號、身分 `UNCONFIRMED` | [#65](https://github.com/Polalalabear/amidst/pull/65)、契約 §0.2 |
| D63 修訂 | Q1–Q5 定義、Agent 輪詢 top-k 與兜底、不做同色干擾、權重下載授權 | [#65](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884) |
| D64 | Q1–Q5 Agent 切鏡規則例外；第一版只用 RT-DETR＋HSV | [#86](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727) |
| D65 | 原核准 SHA 與 5 fps 參數初值 | [#88](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432) |
| D66 | `UNKNOWN`（未找到原文） | UNKNOWN |
| D67 | 規則例外、預算、r004 建檔、finalization、Codex 合併與疊分支 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) |
| D68 | 組員任務、A／B1 試標、r004 提案核定；圖與出口在渲染前凍結 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292617734) |
| D69 | 契約 §14 第 5–8 項採 (a) | [#135](https://github.com/Polalalabear/amidst/pull/135#issuecomment-6292679461) |
| D70 | Codex 自審 staging、Q1–Q5 工程初步全通、授權 r004 渲染 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6307788539) |
| D71 | 契約改版核准方式、兜底定位、出口區域、評估方式、r004 顏色 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6308081801) |
| D72 | `main` 暫不更新 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6393392053) |
| D73 | 契約 §14 待決項的正式選擇 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6395972547) |
| D74 | r004 圖凍結、G4 範圍與 CAM_ENTRY | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396154980) |
| D75 | 正式索引 HSV、人工答案轉換、Q5 決策窗、舊 PR 整理 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396184028) |
| D76 | 廣角、Q3 題組、組員包格式、Qwen 延遲量測、兩階段驗收 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396442549) |
| D77 | r004 重疊區延後到 Q5 穩定後 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6397771396) |
| D78 | 兩段 journal＋取消 token；600 ms 內框中心平移重新取得 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6398428243) |
| D79 | Q5 逐事件決策窗、多次 RETURN、NO_SWITCH 收緊、A4-c | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6398981572) |
| D80 | yyin Q1／Q3 出題包的規則；query_binding 由評估端計算 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757) |
| D81 | 圖 v3 與 G4 的前置；Q2 只追蹤 scope 內鏡頭 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399202935) |
| D82 | 使用者 stop 之後 Q2 為 `PARTIAL`／`USER_STOPPED` | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6407458748) |
| D83 | P1 回交表人工閱讀，不進正式指標 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6415107757) |
| D84 | catalog 凍結與 G4 脫鉤，原樣凍結 `3eba8572…` | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416451756) |
| D85 | stop 後 API poll 回 PARTIAL；#231 合併條件 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416508414) |
| D86 | Q3 追蹤語法、缺時間預設整段 run、workbench 呈現缺口 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417558930) |
| D87 | 開第二條線、先寫情境卡、寫入 session 上限 3 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959) |
| D88 | 本機清理安全項；#240、#228 修衝突 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422147844) |
| D89 | 情境卡 v1：A4-1 50 s＋B4-1 42 s | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857) |
| D90 | L2-7：LOST 期限、重疊接手、磁碟、第二版範圍 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212)、[第 3 題](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423763378) |
| D91 | 文件封存、specs 歸歷史並重寫本規格、10-27 交接、進度導覽批次補 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434355675) |
| D92 | r004 情境卡調整、#260-A／C；#260-B 回應升 v2 | [#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)、[補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506) |

下一個編號：D93（[D92 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)）。

---

## 7. 舊 specs 中仍然有效的條文

[DEVELOPMENT_RULES 第 57 行](DEVELOPMENT_RULES.md)寫：「依 PRD 保留物理硬限制、多解 Top-K 與 provenance；Phase 2 僅保留 schema／interface，Semantic Ranking 在 deterministic closed loop 完成後才考慮。Q1–Q5 主線的 Agent 切鏡例外見本節 D64 條，排序仍屬決定性模組。」

這一行引用的 PRD 條文逐條搬在下面（原文照錄，出處為 [PRD](PRD.md) 的行號，以 mainline `2675c21` 為準）。這些條文仍然有效，因為規則第 57 行仍引用它們；本文不改其內容。「Q1–Q5 對應」欄只指出契約中相關的現行條文，不重新解釋 PRD。

| # | 主題 | PRD 原文 | 出處 | Q1–Q5 對應 |
| --- | --- | --- | --- | --- |
| P-1 | 物理硬限制（責任分離） | 「**Geometry、Projection、Reachability、NavMesh Search、Travel-time Constraint 與 Collision Constraint** 必須由確定性演算法處理；Agent 或語意推論只處理已通過物理限制後仍存在的歧義、場景語意與多假設排序。」 | PRD §2，第 26 行 | 契約 §1（Agent 只經 typed tools）；D64 例外（Agent 只決定是否切到合法候選，排序仍屬決定性模組） |
| P-2 | 物理硬限制（先剪枝） | 「所有物理上不可能的候選，例如穿牆、不可達區域、超速移動、時間倒流與不合法樓層轉換，必須由 **Spatiotemporal Graph Engine** 在語意推理之前排除。」 | PRD §2，第 28 行 | 契約 §5（兩層圖只表示依配置可能連通，通行性在核准範圍外為 `UNKNOWN`） |
| P-3 | 硬限制先於排序 | 「只有通過所有 Hard Constraint 的 Candidate 才能送往後續排序或語意推論。」 | PRD §10，第 225 行 | 契約 §5.4（候選由兩層圖＋D28 決定性產生） |
| P-4 | 多解 Top-K | 「若存在多條合理路徑，系統必須保留 **Top-K Candidate Trajectories**，不能因展示方便而強迫輸出單一結果。」 | PRD §2，第 28 行 | 契約 §5.4、§8.6（合法 top-k 候選快照） |
| P-5 | Provenance | 「所有軌跡資料同時必須保有明確的 **Provenance**。`OBSERVED` 表示攝影機直接取得的 2D Evidence，`PROJECTED` 表示將直接觀測映射至 3D 後的結果，`INFERRED_GAP` 表示沒有直接觀測時由系統補全的軌跡，而 `GROUND_TRUTH` 僅存在於 Blender 模擬與 Evaluation 層。」 | PRD §2，第 30 行 | Q1–Q5 第一版不做 3D 重現與接地（契約 §1），`PROJECTED`／`INFERRED_GAP` 在第一版的對應：`UNKNOWN`；GT 隔離見契約 §9 |
| P-6 | GT 隔離 | 「`GROUND_TRUTH` 只能進入 **Evaluation 與 Debug Visualization**，禁止進入 Graph Engine、Candidate Ranking、Agent Prompt 或 Path Score。任何 Ground Truth Leakage 都視為 Benchmark Invalid。」 | PRD §16，第 361 行 | 契約 §9；[DEVELOPMENT_RULES 第 56 行](DEVELOPMENT_RULES.md) |
| P-7 | Phase 2 只保留 schema／interface | 「Phase 2 則保留原產品架構位置，但暫不進行實際開發。」及「新版只延後實作，不移除其 Interface。」 | PRD §3，第 47 行 | — |
| P-8 | Phase 2 只保留 schema／interface | 「這些模組目前只保留 **Interface 與資料 Schema**，不占用 Phase 1 的核心研發時間。」（「這些模組」指同節列出的 Detection／Tracking、ReID、Backend API、Three.js Digital Twin 等） | PRD §25，第 543–545 行 | Q1–Q5 已實作其中部分元件（如 RT-DETR 偵測、後端 API）；這是否與 P-7／P-8 衝突、是否需修規則：`UNKNOWN`（見 §8） |
| P-9 | Semantic Ranking 時機 | 「Semantic Reasoning 在 Phase 1 屬於 **Optional Research Extension**。它接收已通過 Graph Hard Pruning 的 Top-K Candidate、Time Slack 與 Semantic Regions，並提供候選之間的語意排序與說明。」 | PRD §13，第 277 行 | D64 例外：Q1–Q5 的 Agent 不做排序（契約 §0.3、§5.4） |
| P-10 | 語意推論不造機率 | 「Agent 可以說明某條路徑為何能較合理地解釋 Temporal Slack，但不能自行產生「80% 進入洗手間」這類沒有校準依據的機率。」 | PRD §13，第 287 行 | — |

PRD 其他章節（Phase 1 研究閉環、Blender GT、NavMesh、評估指標等）不在第 57 行引用範圍內，依 D91 歸為歷史。

---

## 8. UNKNOWN 與待決

| # | 項目 | 狀態 | 來源 |
| --- | --- | --- | --- |
| U-1 | Q1／Q2／Q3 回應 v2 的 schema 名稱與寫入契約的 PR | `UNKNOWN`（D92 只定方向） | [D92 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506) |
| U-2 | 契約 §14 第 32 項：D80 preimage 的執行期 binding 交接 | 待決（INCOMPLETE，不自選值） | 契約 §14-32 |
| U-3 | `exit_rule` 的 `boundary_inclusive` 值 | 待使用者決定 | 契約狀態列；[驗收計畫 §4「使用者」](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)；[Q5 決策窗 §1.4](../evaluation/Q5_DECISION_WINDOW_D79.md) |
| U-4 | G4（圖 v3 核准）與 M1（U-C8） | 待使用者；M1 留給 G4 | D89 第 4 項；D90 第 2 項 |
| U-5 | 可信 G4 核准的標準 | 已定：checkpoint issue 的核准留言＋協調者記錄的 D 決策 | D92 第 3 項 |
| U-6 | A4-c2 是否計分（EXT_CAR 的 `t_L` 靜態投影確認） | 待 Codex 確認 | D92 第 1 項 |
| U-7 | 第二版範圍的最終名單 | 暫定，等 #247 漏檢診斷與 #253 可行性 | D90 第 4 項 |
| U-8 | Line 1／Line 2 各里程碑日期 | `UNKNOWN`，待使用者核定 | 兩條線計畫 §5 |
| U-9 | D64 外部 API 例外（OpenAI 比較組） | 之後由使用者決定 | [驗收計畫 §5](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) |
| U-10 | 最後是否更新 `main` | 使用者決定 | D72；[驗收計畫 §4](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) |
| U-11 | Q1–Q5 專用 pipeline 圖 | `UNKNOWN`（未找到） | 本文 §2 |
| U-12 | 後端 API 各 action 的正式介面文件 | `UNKNOWN`（未找到；只有 staging 的 `api.py`） | 本文 §4.1 |
| U-13 | [DEVELOPMENT_RULES 第 49 行](DEVELOPMENT_RULES.md)以 `frontend/workbench/` 為主入口，Q1–Q5 畫面在 `frontend/workbench-v2/`；兩者關係是否需要規則更新 | `UNKNOWN`（本文不決定） | DEVELOPMENT_RULES 第 49 行；D63 (a) |
| U-14 | PRD P-5 的 `PROJECTED`／`INFERRED_GAP` 在第一版（不做 3D 重現）的對應 | `UNKNOWN` | 本文 §7 |
| U-15 | PRD P-7／P-8「Phase 2 只保留 interface」與 Q1–Q5 已實作偵測與 API 的關係 | `UNKNOWN`（本文不決定；需要時由使用者決定是否修規則） | 本文 §7 |
| U-16 | D66 的內容 | `UNKNOWN`（未找到原文） | 本文 §6 |
| U-17 | `R004_SCENE_CHANGE_PROPOSAL.md` 是否被 staging 的 `R004_REVIEW_V2` 取代 | `UNKNOWN` | [#263](https://github.com/Polalalabear/amidst/issues/263)「分類」 |
