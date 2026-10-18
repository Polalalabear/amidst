# 工作台 v2 設計（受控場景 Demo）

日期：2026-10-18（Asia/Taipei）

狀態：**設計草案，等使用者人工審查。審查通過前不開始實作**（D34）。本文不改任何程式檔，也不宣告任何檢查點通過。

- 可操作 mockup（SYNTHETIC，非真實資料）：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>（私人 Artifact，需要擁有者分享才能給別人看）。原始檔不進 repo，見 §10。
- 使用者原話：「用你的標準，不用基於之前的 UIUX，但要維持專案機能」「沒有很喜歡之前的畫面風格」。所以本文重做版面、互動與視覺，只保留機能、純邏輯與契約。
- 所有數字都是示意；門檻值仍是 CS-Q9「待約定」。

## 0. 依據

| 來源 | 版本 |
| --- | --- |
| 使用者決定 D34、D35 | [#69 留言](https://github.com/Polalalabear/amidst/issues/69) |
| 受控場景契約 | `docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md` @ `264377112d1859c5472a9a47dcb56c9b4b38e19e`（#65，CS-A 已核准，D32） |
| UX 草圖 | `docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md` @ `2643771` |
| 舊工作台盤點基準 | 整合分支 `claude/office-demo-visualization` @ `f481fe0e300198235bd9599ff0091fd33d0381a5`（CS-R 已推送，含 #53、K3、K4 #35 @ `7a7f93e`、K6、A5）。`origin/claude/rehearsal-20261018` @ `5a2c613` 的 `frontend/` 與它只差 `scene.mjs` 一行，所以以整合分支為準 |
| player-grid（另一個 session） | Draft PR [#71](https://github.com/Polalalabear/amidst/pull/71)，`claude/player-grid` @ `2627b89792fffc4ef4f00fb5e77764d44d7441db`：`frontend/workbench-v2/player-grid.mjs`、測試、5 份 SYNTHETIC fixture（見 §6.3）。本文不改 #71 的檔案 |
| 規則 | `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md` |

盤點方式：只用 `git show <ref>:<path>` 讀 `frontend/workbench/` 與 `src/amidst/workbench/service.py` 的靜態資產段落。沒有啟動服務，沒有讀 GT、影像或影片。

## 1. 設計原則

1. **只有證據有顏色。** 外框、按鈕、選取、文字都是單色石墨。畫面上出現色相，就代表一個 evidence state。這樣一眼就能分辨「這是資料」還是「這是介面」。
2. **每個 evidence state 至少有三種編碼：** 顏色、線型或填法、文字碼。色盲、灰階列印或投影偏色時，靠線型和文字碼仍然分得出來。
3. **推論永遠比觀測「輕」。** 觀測用實線與最深的色；推論用虛線、半透明緞帶；假設用長虛線加範圍帶。推論不會比觀測更粗、更實或更亮。
4. **沒有證據就什麼都不畫。** MISSING、UNKNOWN 不在 3D 畫位置，只在時間軸與側欄說明原因。盲區不畫位置，只畫範圍帶與路徑束。
5. **身分永遠是 UNCONFIRMED。** 圖例列常駐「身分 UNCONFIRMED」。曲線不用人名、不用 actor 色、不用「同一人」字樣；兩條局部軌跡之間只有「假設」。
6. **一個畫面，三種模式。** 不再有多頁導覽與身份入口。瀏覽、查找、Demo 共用同一組 2D、3D、時間軸，模式只換側欄內容與格子排序。

## 2. 功能保留矩陣

「需要」欄：新 Demo 是否需要。「捨棄」不刪任何舊檔：舊工作台依 D35 原樣保留，v2 頂欄提供「舊版工作台」入口。**每一項捨棄都列在 §7 的使用者決定題 Q1，使用者核准前不視為定案。**

| # | 舊功能 | 所在模組（整合分支 @ `f481fe0`） | 需要 | v2 的位置，或捨棄理由 |
| --- | --- | --- | --- | --- |
| F1 | 研究／管理身份選擇（入口頁、角色卡、切換身份） | `app.mjs` `gateway()`、`sidebar()`、`switch-role` | 否 | **捨棄（X1）**。新 Demo 只有研究視角；入口頁本來就聲明「不作為帳號驗證」，多一步沒有機能。v2 直接進入工作區 |
| F2 | 多頁導覽：主控板、共用工作區、人工審查、測試與評估、實驗展示、人物調查、執行與評測、調查與品質 | `app.mjs` `sidebar()`／`topbar()`；`investigation.mjs`、`run-study.mjs`、`phase2-suite.mjs`、`presentation.mjs`、`gallery.mjs`、`accuracy-evaluation.mjs` | 否 | **捨棄（X2）**。v2 只有一個工作區。這些頁面的機能（Agent 調查、run study、評估、標註發布）不屬於受控場景 Demo；要用時開舊版 |
| F3 | 場景預設與場景選擇器（不可用場景 disabled 並寫原因、預設場景） | `presentation-data.mjs` `sceneUsable`、`sceneOptionLabel`、`defaultSceneId`、`sceneEntryState` | 是 | 頂欄「場景▾」＋「事件 A／B1」。重用 `sceneUsable`、`sceneOptionLabel`、`defaultSceneId`。`sceneEntryState` 綁 Office 的 `demo_defaults`，v2 改讀 safe manifest 的 `sampling`、`duration_s`、`camera_ids`（CS-Q14），重寫 |
| F4 | 品質標示：接地品質 `FLAGGED`／`NOT_EVALUATED`／未知狀態 | `presentation-data.mjs` `contactQualityStyle`、`CONTACT_*_TAG`、`contactQualityReadout` | 是 | 3D 區間改為空心（§5.3）；證據側欄列原因。重用狀態判斷與文字；**樣式改為空心實線、不加虛線**，避免和推論虛線混淆（Q4） |
| F5 | 圖層可用性與控制鎖（`layer_availability` UNAVAILABLE、控制項 disabled 附原因） | `presentation-data.mjs` `layerAvailability`、`controlGate`、`unavailableNotice` | 是 | 側欄「圖層」開關；不可用時 disabled 並寫原因。重用 `layerAvailability`；`GATED_LAYERS`、`CONTROL_LAYERS` 是 Office 圖層名，v2 用新表 |
| F6 | 播放與時間軸（播放鍵、拖曳、步進 0.2／0.4 s） | `app.mjs` `timeline()`、`nextPlaybackTimestamp`、`sourcePlaybackStep` | 是 | 底部「證據時間軸」：每台鏡頭一列影格可用性，加一列曲線狀態；播放頭只在時間軸上。時鐘改為整數毫秒（§4.4） |
| F7 | 鏡頭選取與鏡頭格（自適應排版、只換 `src` 的 reconcile） | `app.mjs` `cameraTilesHTML`、`cameraTileLayout`、`reconcileCameraTiles`、`cameraSelectors()` | 是 | 由 `player-grid` 取代（1／2／4／8、分頁、釘選）。reconcile「不重建 `<img>`」的做法保留到 v2 的 grid view |
| F8 | 2D／3D 同步（共用 timestamp，2D 與 3D 二選一切換） | `app.mjs` `workspaceDisplay()`、`view.setTimestamp` | 是 | **改為並排同時顯示**（Q3）。共用一個時鐘 store |
| F9 | 盲區假設：路徑束、範圍帶、狀態與原因文字 | `blind-hypothesis.mjs`；`scene.mjs` blind layer；K4 #35 | 是 | 3D 範圍帶（包絡淡、當下切片深）＋長虛線路徑束。重用 `blindHypothesisFromResponse`、`blindHypothesisPlan`、`blindHypothesisRegionAt`、`insideBlindInterval`、`blindReasonText`；繪製重寫 |
| F10 | 禁止區（D15 policy）樣式與「進入禁止區」標籤 | `blind-hypothesis.mjs` `RESTRICTED_*` | 否 | **捨棄（X3）**。契約 §0.1：新場景不沿用 D15。舊 run 在舊版照常 |
| F11 | 負證據：NONE／BASELINE 面積比較、D21 strict／suggestion、`NO_EXCLUSION_TEXT` | `demo-mode.mjs` `reachableAreaM2`、`areaComparison`、`blindRunSummary` | 是 | 證據側欄列出「用到的負證據影格」與「整張影格有偵測、不能用」；2D 格在盲區時加註。重用 `reachableAreaM2`、`areaComparison` |
| F12 | 證據檢視與點擊回溯（A5 點 2D 框選觀測、inspector、候選證據疊圖） | `observation-selection.mjs`、`cross-camera.mjs` `candidateEvidenceSVG`、`app.mjs` `inspector()` | 是 | 側欄「證據」；點 3D 區間、緞帶、範圍帶，或點 2D 框，或點時間軸曲線列，都走 `evidence_lookup`（契約 §6.5）。回應形狀不同，流程重寫 |
| F13 | Demo 模式：數字鍵步驟、可用性判斷、MOCK 預覽、PASS 防呆、驗收紀錄匯出 | `demo-mode.mjs`、`demo-steps.office.json` | 是 | 側欄「Demo」；新步驟組 7 步（§4.3）。重用 `canonicalJSON`、`sha256Hex`、`stateHash`、`stepFromKey`、`isTypingTarget`、`RESULTS`、`DEMO_SCHEMA`。`REQUIREMENTS` 是 Office 專用（`humanoid_scene`、`blind_baseline` 等），重寫 |
| F14 | Demo 步驟組「人形（主線）／舊 run（備援）」與 D24 六步 | `demo-mode.mjs` `GROUPS`、`stepsForGroup` | 否 | **捨棄（X4）**，由 §4.3 七步取代（UX 草圖 §8）。舊步驟留在舊版 |
| F15 | 載入狀態（初始載入、每格 LOADING／ERROR／MISSING 區分、epoch 丟棄過期回應） | `app.mjs` `frameLoadState`、`tileHTML`；`presentation-data.mjs` `requestIsCurrent` | 是 | 保留語意：LOADING ≠ ERROR ≠ MISSING。重用 `requestIsCurrent` 的 epoch 模式 |
| F16 | 錯誤與完整性（inline error、toast、hash 不符 fail closed） | `app.mjs`；`player-grid.mjs` `toDisplayModel` | 是 | 完整性錯誤（`DataIntegrityError`）＝阻擋式面板蓋住 2D、3D，不顯示任何影格；請求失敗＝每格 ERROR 加重試；`aria-live` toast 保留 |
| F17 | GT 隔離的呈現（獨立評估區、「GT debug 不在此入口」、`gt_read`） | `app.mjs` test 頁 | 是 | 側欄「來源與隔離」常駐 `gt_read: false`、`agent_used: false`、`identity_verdict`、`output_sha256`。v2 首版**沒有** GT 或 EVALUATION 面板（契約 §7：凍結後的獨立面板，另案） |
| F18 | 幾何疊圖（鏡頭視錐、來源標註、`FRUSTUM_LABEL`） | `geometry.mjs` | 部分 | 3D 只畫鏡頭符號與（查找後）候選足跡細外框。重用 `projectWorldPoint`、`projectSegmentToImage`；新 `cameras.json` 要 adapter（契約 §3.7）。2D 視錐疊圖**不做（X5）**：新場景的 2D 疊圖只有 bbox |
| F19 | 接地估計顯示（POINT／SEGMENT、腳點像素帶、`raw_*` 不畫） | `ground-estimate.mjs` | 是 | 3D 人物圖層的核心。重用 `groundEstimatePlan(s)`、`basisLabel`、`segmentLabel`、`unknownLabel`（schema 相同：區間觀測 v1 §3） |
| F20 | 跨鏡頭多解還原面板（D18 候選排名、速度曲線） | `cross-camera.mjs`、`blender-motion.mjs` | 否 | **捨棄（X6）**。綁 D18 端點與舊 timeline；新 Demo 用 `curve_layer` 的 `candidate_ref`、`association`。速度曲線不在新 Demo |
| F21 | 物理人工確認（門／走廊／碰撞篩選、人工判定） | `physical-review*.mjs` | 否 | **捨棄（X7）**。屬舊 Office；新場景的物理結果只以 `physical_verdict` 與檢查結果徽章呈現 |
| F22 | 分時畫面牆（8／12／16 格診斷）與 C5 建議檢視 | `app.mjs` frame wall、`frameQueryPanel()` | 否 | **捨棄（X8）**。契約 §6.2：C5 建議影格不是同步影片。新 Demo 用候選鏡頭查詢＋同步格取代 |
| F23 | 語意查詢表單（地點、鏡頭、行為、label 預設） | `app.mjs` `guidanceSelection`、`semantic_presets` | 否 | **捨棄（X9）**，由查找模式（地面選區、時間範圍、模板）取代 |
| F24 | 放大來源影像 | `app.mjs` `frame-enlarge` | 是 | 1 格模式即放大；格子雙擊切到 1 格並釘選該鏡頭 |
| F25 | 圖例（觀測／候選推論／缺漏、K4 五色圖例、有資料／無資料） | `app.mjs` `markerLegendItems`；`blind-hypothesis.mjs` `LEGEND_ITEMS` | 是 | 底部常駐圖例（§5.3），每項附線型樣本與契約代碼 |
| F26 | 標註版本提示（標註 v<n> 已發布、結果未重跑） | `app.mjs` `sourceVersion` | 否 | **捨棄（X10）**。新場景用 `scene_version`、`map_sha256` 等 pin，顯示在「來源與隔離」 |
| F27 | 歷史診斷人形（DISPLAY_ONLY） | `app.mjs`、`scene.mjs` | 否 | 不做。契約：長區間不在中點放人形，不出現球狀替身 |

## 3. 新需求與 v2 位置

| 新需求 | 依據 | v2 位置與規則 |
| --- | --- | --- |
| 候選鏡頭查詢，排序依 D28 | 契約 §6.1 | 查找模式側欄。每列：名次、`camera_id`、相交等級徽章（● 相交／◐ 通路／○ 不相交／? 未知，四種外框不同）、重疊 m²、附帶證據一行（「感知 NOT_EVALUATED，偵測張數 null，不影響排序」）。上方整體狀態 `READY`／`PARTIAL`／`UNKNOWN` 與原因。下方固定寫排序依據。`UNKNOWN` 不寫成不相交 |
| 1／2／4／8 格同步播放 | 契約 §6.2、CS-Q13；UX §3 | 頂欄格數切換。候選集合與格數分開；不足留空格「無更多候選」，不複製補位；超過用分頁；釘選只改版面 |
| 查找模式：地面選區、時間範圍、模板；不用 Agent | 契約 §6.1；UX §2、§4 | 選 `AREA_*` 或在 3D 地面點多邊形；時間半開區間；模板「經過」「進出」。送出後格子依排序重排、時間跳到開始、範圍外變暗。「返回查找前」恢復原排列與時間，查詢保留可再進入 |
| 3D 人物以區間為主 | 契約 §6.3；UX §5.1 | SEGMENT＝實線段加兩端短刻度（├──┤）；長度 ≤ `HUMANOID_DISPLAY_MAX_INTERVAL_M`（待約定）時加半透明「人形範圍」掃掠體；更長只畫線段。POINT＝地面短十字。不放實心人形、不放球 |
| 曲線：實線、短虛線緞帶、物理曲線用虛線 | 契約 §6.4；UX §5.2 | 單筆橫向區間是實線；跨 sample 的連接一律是短虛線緞帶（兩條邊＋淡填）；盲區假設是長虛線＋範圍帶。「物理曲線用虛線」本文解讀為「任何跨 sample 的路徑都是虛線」（Q5） |
| 影格之間的狀態規則 | 契約 §2.2 | 見 §4.4 |
| evidence state 圖例 | UX §7 | 底部常駐，§5.3 |
| 新 Demo 步驟組 | UX §8 | §4.3 |

## 4. 資訊架構與版面

### 4.1 結構

只有一個工作區。進入就是瀏覽模式，載入目前場景的第一個事件。

```text
┌ SYNTHETIC 條（只在資料是 fixture 時出現；斜紋單色）──────────────────────────────────────┐
├ 頂欄：Amidst │ 場景▾ │ 事件 [A][B1] │ run_id │ 模式 [瀏覽][查找][Demo] │ 格數 [1][2][4][8] │ 主題 │ 舊版 │
├───────────────┬────────────────────────────────┬─────────────────────────────────────────┤
│ 側欄 304 px    │ 2D 同步畫面（暗色影像井）          │ 3D 空間（平面模型）                         │
│ ・模式面板      │  每格：camera_id、名次、狀態、釘選    │  牆以 1.2 m 剖切；鏡頭符號；圖層            │
│   查找／Demo    │  影格 #、timestamp_s、sample_age  │  拖曳旋轉、滾輪縮放；斜視／俯視              │
│ ・證據（點選後） │  bbox 疊圖、負證據角標              │  點區間／緞帶／範圍帶 → 證據                 │
│ ・圖層（瀏覽）   │                                │                                         │
│ ・來源與隔離    │                                │                                         │
├───────────────┴────────────────────────────────┴─────────────────────────────────────────┤
│ 時間軸：播放／步進／速度｜t、影格 #、sample_age｜每台鏡頭一列＋曲線列＋查詢範圍括號＋播放頭        │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ 圖例：觀測 ├──┤  推論 ┄┄  假設 ╌╌＋帶  MISSING ╱╱  UNKNOWN ⋯?   SYNTHETIC         身分 UNCONFIRMED │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- **側欄**放「目前要做的事」和「選到的東西是什麼」。由上到下：模式面板、證據、圖層（只在瀏覽）、來源與隔離。證據檢視固定在側欄，不用浮動卡片，避免蓋住 3D。
- **2D 與 3D 並排**（桌面 ≥ 1180 px）：2D 約 54%，3D 約 46%。8 格時每格約 150 px 寬，夠看人在哪裡；要看細節就切 1 格（Q3）。
- **時間軸**橫跨全寬，左側對齊側欄放控制與讀數，右側是軌道。
- **圖例列**永遠在畫面底部，不能收起。

### 4.2 斷點

| 寬度 | 版面 |
| --- | --- |
| ≥ 1180 px | 側欄｜2D｜3D 三欄 |
| 760–1179 px | 側欄｜（2D 上、3D 下） |
| < 760 px | 單欄：2D → 3D → 側欄；8 格改 2 欄 |

Demo 的目標是 1440×900 以上的桌面或投影；窄版只保證不破版。

### 4.3 模式

| 模式 | 進入 | 側欄 | 格子順序 | 3D 額外圖層 | 離開 |
| --- | --- | --- | --- | --- | --- |
| 瀏覽 | 預設；或從查找切回 | 證據、圖層、來源 | 目錄預設順序（與任何查詢無關） | — | — |
| 查找 | 頂欄「查找」 | 查詢表單、候選清單、證據、來源 | 送出後依 `recommended_camera_ids` | 目標多邊形（單色斜線）、候選足跡（點線外框） | 「返回查找前」恢復排列與時間；切回瀏覽時查詢保留，可「再次進入上次查詢」 |
| Demo | 頂欄「Demo」 | 步驟清單（1–7）、目前步驟說明、驗收按鈕、匯出 | 依步驟 | 依步驟 | 切到其他模式 |

**Demo 步驟組（取代 D24，UX §8）：**

| 鍵 | 事件 | 畫面 |
| --- | --- | --- |
| 1 | A | 瀏覽、4 格同步播放；A 只有 3 台，第 4 格「無更多候選」 |
| 2 | A | 查 `AREA_R101_FRONT`、0–10 s、經過；W2、W1 在前，R102「不相交」 |
| 3 | A | 停在影格之間，說明琥珀色內插刻度（只在合法局部軌跡內）；點區間跳回影格 |
| 4 | B1 | 進出查詢 8–20 s，候選重排；`PARTIAL` |
| 5 | B1 | 轉角盲區：範圍帶與路徑束，不畫位置；時間在盲區時只加亮切片 |
| 6 | B1 | N1 再出現：假設可達，身分 UNCONFIRMED；兩人沒被連成一條 |
| 7 | B1 | 切 8 格：後 4 格空，不補位 |

- 每步的可用性只看實際載入的資料；缺什麼就寫 `UNAVAILABLE` 與原因。MOCK 預覽或 SYNTHETIC 資料下按「通過」，紀錄一律是 `UNKNOWN`（沿用 K6 規則）。
- 數字鍵只在 Demo 模式生效，輸入框聚焦時不觸發（重用 `stepFromKey`、`isTypingTarget`）。

### 4.4 時間與影格之間（契約 §2.2）

- **時鐘**：單一 store 保存整數毫秒 `t_ms`。`frame_index = floor(t_ms × fps / 1000)` 用整數算，不加 epsilon。run 是半開區間，最大 `t_ms = duration_s × 1000 − 1`；超過就是 `OUT_OF_RANGE`。
- **播放頭**只在時間軸上，3D 不畫播放頭。
- **2D**：每格顯示 `timestamp_s ≤ t` 的最後一個預期 sample。角標同時寫影格號、該影格自己的 `timestamp_s` 與 `sample_age_s = t − timestamp_s`（琥珀色字，表示「這是時間差」，不是證據）。該 sample 缺檔就是 MISSING，不往前找。
- **3D**：
  - 所有觀測區間淡顯；`[t − Δ, t]`（Δ 預設 1 s）內的加深；當下 sample 的區間最粗，並加人形範圍與推論方向箭頭。
  - 播放頭剛好在 sample 上：在該區間中點畫墨色短刻度，標 `t = 12.40 s`。
  - 在兩個 sample 之間，**且**同一條局部軌跡的兩端都有效：在連接緞帶上畫琥珀色虛線刻度，標 `t = 12.47 s（內插）`。
  - 其他情況（任一端 MISSING／UNKNOWN、不同軌跡、沒有局部軌跡）：不畫刻度、不畫位置。
  - 在盲區：只加亮該時刻的假設切片（玫紅），維持 `INFERRED_HYPOTHESIS`，不改標內插。
- 播放速度 0.5／1／2×；速度不會多出觀測。

### 4.5 狀態呈現

| 狀態 | 範圍 | 2D | 3D | 時間軸 | 側欄 |
| --- | --- | --- | --- | --- | --- |
| LOADING | 一格或一層 | 掃光底「LOADING · 讀取影格中（不是 MISSING）」 | 「LOADING · 讀取圖層中」 | 不變 | — |
| ERROR（請求失敗） | 一格 | 「ERROR · 請求失敗，尚未確認是否缺漏」＋重試 | 該層不畫 | 不變 | toast |
| MISSING | 一格一 sample | 灰色斜紋「預期影格 #n 不存在」 | 不畫 | 斜紋 | 點選時 `NO_SUPPORT` |
| OUT_OF_RANGE | 一格 | 「超出 run 時間範圍」 | — | 播放頭停在終點 | — |
| UNKNOWN | 一格或一段 | 點線框「?」＋原因 | 不畫 | 點線框 | 列原因 |
| 完整性錯誤 | 整個 run | **不顯示任何格** | **不顯示** | 停用 | 阻擋式面板：錯誤碼、意思、怎麼處理；不降格成 MISSING |

## 5. 視覺規範

方向：「量測儀器台」。外框像儀器面板：石墨單色、細規線、窄字體標籤、等寬數字。3D 像建築平面模型：白模、牆剖切、細網格。證據是唯一的彩色墨水。

### 5.1 色彩 token

淺色是預設，暗室是切換（Q2）。2D 影像井在兩種主題都維持暗色，避免影像對比被外框干擾；井內的 bbox 用暗室版的觀測色。

| token | 用途 | 淺色 | 暗室 |
| --- | --- | --- | --- |
| `--bg` | 頁面底 | `#E7EAEC` | `#0F1214` |
| `--panel` | 面板、3D 底 | `#F6F7F8` | `#161A1E` |
| `--panel-2` | 次層、時間軸查詢範圍外 | `#EDF0F2` | `#1C2126` |
| `--ink` | 主文字、選取、主要按鈕 | `#13171B` | `#E5E9EC` |
| `--ink-2`／`--ink-3` | 次文字／說明 | `#48515A`／`#78818A` | `#A7B0B8`／`#727C85` |
| `--rule`／`--rule-2` | 規線 | `#C6CCD2`／`#DCE0E4` | `#2D343A`／`#232930` |
| `--well` | 2D 影像井 | `#0D1013` | `#07090B` |
| `--obs` | 觀測 | `#0B5C99` | `#79BEF2` |
| `--int` | 推論（內插、方向） | `#DE940A` | `#E6A53A` |
| `--hyp` | 假設（盲區、日後預測） | `#C3579A` | `#DB82BA` |
| `--miss` | MISSING 斜紋 | `#8A9199` | `#7B838B` |
| `--unk` | UNKNOWN 點線 | `#5C646D` | `#A3ACB4` |
| `--floor`／`--floor-room` | 3D 走廊／房間地面 | `#F5F6F4`／`#ECEEEA` | `#1A1F23`／`#15191D` |
| `--wall-side`／`--wall-cap` | 牆側面／剖切面 | `#C2C8CE`／`#2B3238` | `#3A4249`／`#BAC3CB` |
| `--err`／`--err-soft` | 完整性錯誤面板 | `#9F2328`／`#F5E1E1` | `#F19393`／`#3A1D20` |

- 三個證據色取自 Okabe–Ito 的藍、橙、紅紫，再調明度：淺色主題下明度排序是觀測（最深）< 假設 < 推論，所以灰階下也分得開。
- 錯誤色只用在完整性錯誤面板，不出現在任何證據圖層上。
- **實作前的檢查**：每個 token 對都要過一次色盲模擬（protanopia、deuteranopia、tritanopia）與灰階截圖，並確認文字對比 ≥ 4.5:1。這列入 V2-1 的驗收（§6.6）。

### 5.2 字體與尺寸

| 角色 | 字體 | 用法 |
| --- | --- | --- |
| UI 內文 | IBM Plex Sans ＋ Noto Sans TC | 13 px／1.45 |
| 標籤、區塊標題 | IBM Plex Sans Condensed 600 | 11–12 px，大寫，字距 .06–.08em |
| ID、時間、hash、數字 | IBM Plex Mono | 10–18 px，`tabular-nums` |

- 字級：10／11／12／13／16／18 px，不另加。
- 間距：4 px 基準（4、8、12、16、24）。
- 圓角：控制項 2 px；只有浮動提示 6 px；格子、面板 0。
- 陰影：只用在浮動提示（`0 8px 28px rgba(16,20,24,.18)`）。面板之間用規線分隔，不用卡片陰影。
- 字型檔要本機打包（`frontend/workbench-v2/fonts/`，OFL 授權），不從外部 CDN 載入；本機展示不依賴網路。授權檔一併放入。

### 5.3 Evidence state 編碼

| 狀態（契約代碼） | 文字碼 | 3D | 2D | 時間軸 | 符號 |
| --- | --- | --- | --- | --- | --- |
| 觀測 `PROJECTED_OBSERVATION` | OBS 觀測 | `--obs` 實線區間，兩端短刻度 ├──┤；當下 4 px、Δ 內 3 px、其他 2 px 且 28% 不透明 | bbox 實線框，左上角實底標籤「觀測 c0」 | 實心色塊 | ├──┤ |
| 推論 `INFERRED_INTERPOLATION` | INT 推論 | `--int` 短虛線（3–3）緞帶：兩條邊＋16% 淡填；方向箭頭也是短虛線 | 無 | 兩條短虛線 | ┄┄ |
| 假設 `INFERRED_HYPOTHESIS` | HYP 假設 | `--hyp` 長虛線（10–6）路徑束；範圍帶包絡 13%、當下切片 34%；第 2 名以後路徑 55% 不透明 | 盲區時負證據角標（玫紅虛線框） | 淡填＋長虛線 | ╌╌＋帶 |
| `MISSING` | MISS | 不畫 | 灰色斜紋整格 | 斜紋 | ╱╱ |
| `UNKNOWN` | UNK | 不畫 | 點線框「?」；接地 UNKNOWN 時 bbox 改點線 | 點線框 | ⋯? |
| 接地品質 `FLAGGED` | — | 觀測色**空心**實線（外 5 px 觀測色、內 2.4 px 底色），**不加虛線** | 側欄寫「接地點不可靠（原因）」 | 不變 | — |

- 選取一律是單色光暈（淺色白、暗室深色），不改變證據色，也不加粗成看起來更確定。
- 名次、可達性等「合理程度」只用順序與不透明度表示，不顯示百分比，也不寫「機率」。
- 「人形範圍」是沿區間掃過的半透明體（觀測色 13% 填、35% 外框），標示「身體可能占的範圍」，不是位置。

### 5.4 SYNTHETIC 與 FIXTURE

| 標示 | 什麼時候 | 樣式 |
| --- | --- | --- |
| SYNTHETIC 條 | 本 session 的資料來源不是凍結的真實渲染（fixture 模式、設計 mockup） | 頁面最上方整條單色斜紋，等寬字「SYNTHETIC」＋說明；不能關閉 |
| FIXTURE 角標＋浮水印 | 單一鏡頭或影格來自 UI fixture（例如測分頁的假鏡頭） | 格子右下虛線框「FIXTURE」＋斜向淡浮水印 |
| 3D 角標 | 3D 圖層來自 fixture | 左下虛線框「SYNTHETIC · FIXTURE」 |

都只用墨色，不用任何證據色。真實與 fixture 不放在同一個畫面（UX §7）。

### 5.5 3D 場景

| 項目 | 規範 |
| --- | --- |
| 投影 | 正交。預設斜視（仰角約 53°）；「俯視」一鍵切換。拖曳繞 Z 軸旋轉與調仰角，滾輪縮放；切換事件或視角時自動置中縮放 |
| 地面 | 走廊 `--floor`、房間 `--floor-room`；1 m 細網格、5 m 加深。無貼圖 |
| 牆 | 擠出 0.15 m 厚，**顯示高度剖切在 1.2 m**（不是實際牆高；標示在 3D 標題列），側面依朝向做 Lambert 明暗，頂面是實心「剖切面」色。不投影子 |
| 光線 | 一盞固定方向光（西北上方 45°）＋環境光；只影響牆側面。證據圖層不受光（flat、unlit），永遠畫在牆之上 |
| 門 | 開口處點線 |
| 鏡頭 | 墨色小三角形視錐符號＋點線落地線＋`W1` 類短 ID。不畫完整視錐（不代表可見性） |
| 文字 | 房間、走廊名稱用窄字體小字，墨色 3 |
| 圖層順序（下到上） | 地面 → 網格 → 查詢目標（單色斜線）→ 候選足跡（點線）→ 牆與門 → 鏡頭 → 假設範圍帶 → 假設路徑 → 推論緞帶 → 觀測區間與人形範圍 → 時間刻度 → 選取光暈 |
| 抬高 | 證據層依序 z = 0.02／0.03／0.04／0.05／0.06 m，避免 z-fighting |
| 實作 | three.js（沿用 `/vendor/three.module.js`）。線寬需要大於 1 px，使用 `Line2`／`LineMaterial`（three 的 `examples/jsm/lines`，需服務白名單，§6.4）。虛線圖樣以螢幕像素定義，縮放時不變 |

### 5.6 2D 疊圖

- bbox：觀測色實線 3 px；接地 UNKNOWN 時改點線。左上實底標籤。
- 選取：白色外光暈＋加粗，同時格子外框變白。
- 點擊回溯造成的「暫時釘選」：格子標頭的釘選符號變實心，側欄有「解除暫時釘選」。
- 負證據角標只在「選了盲區假設、且時間在盲區內」時出現：「未偵測（整張影格）· 負證據」或「有偵測 · 不能當排除證據」。

### 5.7 文案規則

- 「候選」「假設」「可能」只用在推論；觀測只寫「觀測」。
- 不寫「同一人」「追蹤到」「確認」。跨鏡頭只寫「假設可達」「未關聯基線」。
- 排序一律附「排序依據」一行；「排第幾」說明為「建議檢視順序，不是機率」。
- 空值寫原因，不寫 0：`frames_with_detection: null` 顯示「null（不是 0）」。

## 6. 實作計畫

### 6.1 `frontend/workbench-v2/` 模組結構

所有 `.mjs` 都是 ES module，純邏輯與 DOM 分檔；純邏輯檔不碰 `document`，可直接用 `node --test` 測。

| 檔案 | 類別 | 內容 |
| --- | --- | --- |
| `index.html` | 外框 | 版面骨架、importmap（`three`）、字型 |
| `style.css` | 外框 | §5 的 token 與元件樣式 |
| `tokens.mjs` | 純 | evidence state 編碼表（色 token 名、線型、文字碼、符號），供 2D、3D、時間軸、圖例共用 |
| `store.mjs` | 純 | 單一 state＋reducer：模式機、查詢前後狀態、釘選、選取、Demo 步驟套用、整數毫秒時鐘 |
| `clock.mjs` | 純＋薄 DOM | `frameIndexAt(t_ms,fps)`、步進、播放迴圈（rAF） |
| `api.mjs` | 純 | 五個端點的請求建構、回應驗證（schema、scope、`gt_read:false`、`identity_verdict`）、fail closed、epoch 丟棄過期回應；fixture 模式讀 `fixtures/*.json` |
| `player-grid.mjs`、`player-grid.test.mjs`、`fixtures/synced_frames_*.json` | 純（#71，另一 session） | 見 §6.3。v2 其他任務不改這些檔 |
| `grid-view.mjs` | DOM | 呼叫 #71 的 `renderGrid` 產生結構，再加上外框的標頭、角標、bbox 疊圖、負證據角標與釘選鈕；只換 `src` 的 reconcile（§6.3） |
| `plan-layers.mjs` | 純 | 由 person-layer、curve-layer、hypothesis 回應建出「繪製清單」（每項：layer、evidence_state、幾何、線型、可點 ref）。內插刻度與盲區切片的判斷都在這裡 |
| `plan-view.mjs` | DOM＋three | 3D 場景、材質、光線、相機、picking；只吃 `plan-layers` 的清單 |
| `timeline-model.mjs` | 純 | 每列的區段（READY／MISSING／UNKNOWN／OBS／INT／HYP）與點擊命中 |
| `timeline-view.mjs` | DOM | canvas 繪製與拖曳 |
| `query.mjs` | 純 | 查詢草稿驗證（半開區間、多邊形頂點、模板）、候選清單 view model |
| `inspector.mjs` | 純＋DOM | `evidence_lookup` 結果 → 側欄內容；跳轉與暫時釘選指令 |
| `demo.mjs` | 純＋DOM | 新步驟組、可用性 registry、驗收紀錄（重用舊 K6 純函式） |
| `demo-steps.controlled.json` | 資料 | 7 步 |
| `app.mjs` | 組裝 | 讀 bootstrap、建立 store、掛載各 view。**唯一**同時 import 多個 view 的檔案 |
| `fixtures/` | 資料 | SYNTHETIC payload（形狀照 §6），每份標 `data_origin: "SYNTHETIC_FIXTURE"`。`synced_frames_*.json` 屬 #71；v2 新增的檔用其他前綴（`candidate_cameras_*`、`person_layer_*`、`curve_layer_*`、`evidence_lookup_*`），不覆寫 #71 的檔 |
| `*.test.mjs` | 測試 | 每個純檔一份 |

### 6.2 重用舊工作台的純邏輯

一律相對 import（`../workbench/<file>.mjs`），**不改舊檔**。

| 舊檔 | 重用的 export | 備註 |
| --- | --- | --- |
| `presentation-data.mjs` | `contactQualityStyle`、`CONTACT_FLAG_TAG`、`CONTACT_UNEVALUATED_TAG`、`CONTACT_UNKNOWN_STATUS_TAG`、`layerAvailability`、`sceneUsable`、`sceneOptionLabel`、`defaultSceneId`、`requestIsCurrent` | 無 import，純 |
| `ground-estimate.mjs` | `groundEstimatePlan`、`groundEstimatePlans`、`BASIS_LABELS`、`basisLabel`、`segmentLabel`、`unknownLabel` | 只 import `geometry.mjs`。顏色常數不用 |
| `geometry.mjs` | `projectWorldPoint`、`projectSegmentToImage` | 只接受 `BLENDER_NEG_Z_UP_Y` 校正；新 `cameras.json` 經 adapter（Codex，契約 §3.7） |
| `blind-hypothesis.mjs` | `blindHypothesisFromResponse`、`blindHypothesisPlan`、`blindHypothesisRegionAt`、`insideBlindInterval`、`blindReasonText`、`OBSERVATION_REF_PATTERN` | 新場景的假設回應是否仍是 `workbench.blind-hypothesis.v1`：**UNKNOWN**（curve-layer 只帶 `hypothesis_response_sha256`）。不相容時 v2 寫 adapter，不改舊檔 |
| `demo-mode.mjs` | `canonicalJSON`、`sha256Hex`、`stateHash`、`stepFromKey`、`isTypingTarget`、`RESULTS`、`DEMO_SCHEMA`、`reachableAreaM2`、`areaComparison` | 會連帶載入 `blind-hypothesis.mjs`、`observation-selection.mjs`（都是純），所以三個都要白名單 |

**不能 import 的舊檔：**
- `app.mjs`：最後一行 `if(typeof document!=='undefined')bootstrap();`（`app.mjs:1515`），在瀏覽器 import 就會啟動舊工作台。它的小工具（`normalizeRange`、`nextPlaybackTimestamp`、`cameraTileLayout`）v2 自己寫，不複製整段。
- `scene.mjs`：Office 專用的 `SceneView`，綁舊 payload。v2 的 3D 重寫。
- `cross-camera.mjs`、`blender-motion.mjs`、`physical-review*.mjs`、`motion.mjs`（後者還 import `../product/timeline.mjs`）：不在新 Demo 範圍。

### 6.3 player-grid（#71）的銜接

依據：Draft PR [#71](https://github.com/Polalalabear/amidst/pull/71) @ `2627b89`，檔案在 `frontend/workbench-v2/`。v2 只 import，不改它的檔案；需要它改的地方寫成 #71 的審查意見。

**它提供的 API（`player-grid.mjs`）：**

| 分類 | export | v2 怎麼用 |
| --- | --- | --- |
| 常數 | `GRID_SIZES`、`MAX_CAMERAS_PER_REQUEST`、`SYNCED_FRAMES_SCHEMA`、`SYNCED_FRAMES_REQUEST_SCHEMA`、`TILE_STATUSES`、`EMPTY_SLOT_LABEL`、`layoutFor(size)` | 頂欄格數按鈕只列 `GRID_SIZES`；`api.mjs` 驗 schema 用同一組常數 |
| 不可變 grid state | `createGridState({candidates, size, pinned, page, fixtureIds})`、`setCandidates`、`setSize`、`withPin`、`withPage`、`pageCount`、`pageView` | `store.mjs` 只保存這個物件，所有格數、分頁、釘選都呼叫這些函式 |
| 時間 | `expectedFrame(t_s, {fps, duration_s})` → `{in_range, expected_frame_index, expected_timestamp_s, sample_age_s}` | 時間軸讀數與 3D 刻度用同一個結果；v2 不另寫選格規則 |
| 請求 | `buildSyncedFramesRequest(view, {session_ref, scene_id, run_id, t_s})` | `api.mjs` 送 `POST /api/synced_frames` 前呼叫；它會擋 0 台與超過 8 台 |
| 回應 | `toDisplayModel(view, response, {requestedTimeS})` → `{ok, tiles[], sample_age_s, page_label, layout, watermark, identity_verdict, …}` 或 `{ok:false, error, tiles:[]}` | 2D 只吃這個 model。`ok:false` 時整個 2D 換成阻擋面板，3D 也不畫（完整性錯誤，§4.5） |
| 結構 render | `renderGrid(container, model, {frameUrl, onPin})`：只輸出結構與 `data-*`（`data-grid-state`、`data-cols`、`data-rows`、`data-watermark`；每格 `data-slot`、`data-kind`、`data-state`、`data-camera-id`、`data-hatched`、`data-mark`、`data-pinned`、`data-fixture`），不寫 class 與配色 | `grid-view.mjs` 用它產生格子骨架，視覺全部由 v2 的 `style.css` 以屬性選擇器決定 |

**資料流：**

```text
store.t_ms ──► t_s = t_ms / 1000（十進位最短表示，#71 轉成精確有理數）
store.gridState ──pageView()──► view ──buildSyncedFramesRequest()──► api.syncedFrames()
                                   └────────────── toDisplayModel(view, response, {requestedTimeS: t_s}) ──► model
model ──grid-view.mjs──► renderGrid(container, model, {frameUrl: api.mediaUrl, onPin: null}) ＋ 外框裝飾
```

**銜接規則：**
- **候選與格數**：瀏覽模式 `createGridState({candidates: 目錄預設順序})`；查找送出後 `setCandidates(state, recommended_camera_ids)`，同時把送出前的 grid state 存成 `preQueryGrid`；「返回查找前」直接還原它。切 1／2／4／8 用 `setSize`（它會回到第 1 頁）。
- **釘選**：使用者釘選＝`withPin(state, id)`。點擊回溯的「暫時釘選」也是 `withPin`，store 另記 `tempPinFrom`（釘選前的 pinned 值），解除時還原；#71 只認一個 pinned，所以暫時釘選會蓋掉使用者釘選，解除時再放回。
- **UI fixture 鏡頭**：`createGridState({fixtureIds})` 傳入，`model.watermark` 是 `FIXTURE` 時 v2 加浮水印與角標（§5.4）。
- **時間**：每次 `expected_frame_index` 改變才送新請求（5 fps 時每 0.2 s 一次）；同一 sample 內移動播放頭只更新角標的 `sample_age_s`。用 `requestedTimeS` 與 `requestIsCurrent` 的 epoch 丟棄過期回應。
- **render 頻率**：`renderGrid` 每次 `replaceChildren()`，會重建 `<img>`。所以 `grid-view.mjs` 只在「結構鍵」（slots、每格 status、pinned、layout）改變時呼叫它；只有 `frame_ref` 改變時，就地換既有 `<img>` 的 `src`（沿用舊版 `reconcileCameraTiles` 的做法），避免播放時閃爍。
- **點擊**：傳 `onPin: null`。#71 的 `onPin` 綁在整格上，會和「點 bbox 選觀測」衝突；v2 在格子標頭另加釘選鈕，格內點擊交給 bbox 命中判斷。
- **標頭與角標**：#71 的 `[data-role="tag"]` 只有一位小數，v2 用 CSS 隱藏它，自己畫標頭（`camera_id`、名次、狀態、釘選）與底列（影格號、`timestamp_s` 兩位小數、`sample_age_s`）。名次用 `tile.rank`；查找時另外從候選回應取相交等級徽章。
- **bbox 與負證據**：不在 #71 範圍。`grid-view.mjs` 在每個 `data-state="READY"` 的格子上疊一層 canvas，資料來自 `person_layer` 的 `bbox_px`，並對照 `tile.frame_ref`。

**對 #71 的審查意見（不由本任務修改）：**
1. `renderGrid` 每次重建 `<img>`：建議提供就地更新，或在文件寫明「只在結構改變時呼叫」。v2 先用後者。
2. `onPin` 綁整格：建議改成只綁明確的釘選元素，或維持現狀由外框傳 `null`（v2 的做法）。
3. 完整性錯誤的回應形狀：#71 fixture 假設 `{"schema_version": …, "error": {"error_class": "DataIntegrityError", "reason": …}}`；契約未定義（R5、§9）。
4. size=1＋釘選的翻頁：#71 是「釘選鏡頭排第 1 頁，其餘依序翻頁」；本設計同意。

### 6.4 對 Codex 的需求（只列需求，不改 Codex 的檔案）

| # | 需求 | 理由 |
| --- | --- | --- |
| R1 | `service.py` 新增 v2 靜態路由：`GET /workbench-v2/` → `frontend/workbench-v2/index.html`，其他 v2 檔案用**明確白名單**（和現有 `assets` 一樣逐檔列，不提供目錄） | 舊版仍在 `/`（D35） |
| R2 | 新增 `GET /workbench/<file>.mjs`，**只**對應 §6.2 列出的舊純模組（`presentation-data`、`ground-estimate`、`geometry`、`blind-hypothesis`、`demo-mode`、`observation-selection`）。`/workbench/app.mjs`、`/workbench/scene.mjs` 不提供 | URL 與 repo 路徑同構，`../workbench/x.mjs` 在 node 測試與瀏覽器都能解析 |
| R3 | vendor 白名單加 three 的 `examples/jsm/lines/`（`Line2.js`、`LineMaterial.js`、`LineGeometry.js`、`LineSegments2.js`、`LineSegmentsGeometry.js`）與 v2 字型檔 | 1 px 以上線寬與虛線（§5.5）；本機字型 |
| R4 | 五個新端點（契約 §6，CS-Q5）照契約實作；v2 只透過它們讀資料。同步影格的 media URL 形式（`frame_ref` → token 化的影像 URL）由 Codex 定義並寫進契約 | v2 不組私有路徑 |
| R5 | 完整性錯誤的回應形狀寫進契約：HTTP 狀態碼與 body，五個端點一致。#71 的 fixture 假設 `{"schema_version":…,"error":{"error_class":"DataIntegrityError","reason":"RGB_RECORD_HASH_MISMATCH"}}`，它的 `toDisplayModel` 也接受 `error.code`；建議契約採這個形狀，免得改 #71 | player-grid 與 v2 都要 fail closed（§9） |
| R6 | fixture 模式：`/workbench-v2/fixtures/*.json` 逐檔白名單（含 #71 的 5 份 `synced_frames_*.json`）；bootstrap 回應加 `data_origin`（`SYNTHETIC_FIXTURE` 或真實 run），v2 依此顯示 SYNTHETIC 條 | 真實與 fixture 不混在同一畫面 |
| R7 | launcher（`start-office-demo.command`）：v2 驗收前維持開舊版；v2 驗收後預設開 `/workbench-v2/`，同時印出舊版入口 `/`（或 `--legacy` 旗標開舊版）。rehearsal 檢查加 v2 檔案的 `FRONTEND_MATCH` | D35「做好之後顯示以新的為主」 |
| R8 | 服務測試：白名單外路徑（例如 `/workbench/app.mjs`、`/workbench-v2/../`、symlink）一律 404／403 | 不把目錄當靜態根 |

### 6.5 測試策略

- **node 單元測試**（`node --test frontend/workbench-v2/*.test.mjs`）：
  - `store`：模式機（瀏覽→查找→返回→再進入）、釘選與暫時釘選、Demo 套用、時鐘邊界（`t_ms = 0`、sample 上、sample 之間、`duration − 1`、`OUT_OF_RANGE`）。
  - `plan-layers`：內插刻度只在同一軌跡兩端有效時出現；跨 MISSING、UNKNOWN、不同軌跡都不出現；盲區切片維持 `INFERRED_HYPOTHESIS`；`HUMANOID` 門檻前後；`FLAGGED` 不移動位置；`raw_*` 不進繪製清單。
  - `timeline-model`：每列區段、點擊命中與優先序。
  - `query`：半開區間、`UNKNOWN` 不轉不相交、`null` 不轉 0、排序依據只用 D28 三鍵。
  - `api`：fail closed（schema 不符、`gt_read` 不是 false、scope 不符、完整性錯誤）→ 不回傳任何可畫資料；過期 epoch 丟棄。
  - `inspector`：§6.5 五種 relation 的跳轉規則與距離相等時的穩定排序。
  - `demo`：MOCK／SYNTHETIC 下 PASS 記成 UNKNOWN；匯出紀錄 hash 穩定。
  - 重用檢查：v2 只 import §6.2 列出的舊 export（測試讀 import 陳述式比對白名單），且不 import `app.mjs`、`scene.mjs`。
- **瀏覽器驗收**（Sonnet／medium，先用 fixture 模式，Codex 端點完成後再用真實 run）：
  1. 1440×900、淺色與暗室各一輪截圖。
  2. 跑完 Demo 1–7 步，每步截圖並對照 §4.3。
  3. 1／2／4／8 切換與 11 台 fixture 分頁；空格不補位。
  4. 停在 sample 上、sample 之間、MISSING、盲區、OUT_OF_RANGE 五個時間點，核對 2D 角標與 3D 刻度。
  5. 點觀測、緞帶、範圍帶、MISSING 段，核對跳轉與側欄。
  6. 載入中、請求失敗、完整性錯誤三種狀態（fixture 注入）。
  7. 色盲模擬（Chrome DevTools Rendering → Emulate vision deficiencies）與灰階截圖，確認五種狀態分得開。
  8. 舊版 `/` 仍可開、行為不變（D35）。
- 每個實作任務只跑自己的測試與 `git diff --check`（AGENTS.md）。

### 6.6 任務拆分

建議模型依 CLAUDE.md 表：前端實作 Sonnet／medium，複雜 3D Sonnet／high。同一組檔案一次只有一個寫入者。`app.mjs` 只由 V2-1 建立並預先掛上所有 view 的空殼，之後各任務只改自己的檔案；最後由 V2-9 做整合接線。

| 任務 | 檔案集合 | 依賴 | 模型／effort |
| --- | --- | --- | --- |
| V2-0 | `player-grid.mjs`＋測試＋5 份 fixture | Draft PR #71 @ `2627b89`（另一 session）；等審查 | — |
| V2-1 外框與 token | `index.html`、`style.css`、`tokens.mjs`、`store.mjs`、`clock.mjs`、`app.mjs`（含各 view 空殼掛載）、`fonts/`、對應測試 | 本設計核准 | Sonnet／medium |
| V2-2 API 與 fixture | `api.mjs`、`fixtures/*.json`、`api.test.mjs` | 本設計核准；可與 V2-1 並行 | Sonnet／medium |
| V2-3 2D 格 | `grid-view.mjs`＋測試（依 §6.3 銜接 #71：結構鍵、就地換 `src`、`onPin: null`、外框標頭與 bbox 疊圖） | V2-0（#71）、V2-1、V2-2 | Sonnet／medium |
| V2-4 3D 平面圖 | `plan-layers.mjs`、`plan-view.mjs`＋測試 | V2-1、V2-2；需 R3 | Sonnet／high |
| V2-5 時間軸 | `timeline-model.mjs`、`timeline-view.mjs`＋測試 | V2-1、V2-2 | Sonnet／medium |
| V2-6 查找模式 | `query.mjs`＋測試（3D 地面點多邊形用 V2-4 提供的 `unproject` API） | V2-2、V2-4 | Sonnet／medium |
| V2-7 證據與點擊回溯 | `inspector.mjs`＋測試 | V2-2、V2-3、V2-4 | Sonnet／medium |
| V2-8 Demo 模式 | `demo.mjs`、`demo-steps.controlled.json`＋測試 | V2-1；步驟內容依 V2-3～V2-7 | Sonnet／medium |
| V2-9 整合接線 | `app.mjs` | V2-1～V2-8 | Sonnet／medium |
| V2-10 瀏覽器驗收 | 不改檔；截圖與結果紀錄 | V2-9、Codex R1–R3、R6 | Sonnet／medium |
| V2-11 獨立審查 | 不改檔 | 每個 PR | Opus／high（小 PR 用 medium） |
| Codex | `service.py` R1–R3、R5、R6、R8；launcher R7；端點 R4 | R1–R3 可與 V2-1 並行 | 使用者決定 |

並行建議：V2-1 與 V2-2 同時；之後 V2-3、V2-4、V2-5 三個同時（檔案不重疊）；再來 V2-6、V2-7、V2-8；最後 V2-9、V2-10。依記憶中的限制，同時寫入的 session 最多 2 個，各自在 scratchpad clone 裡做。

### 6.7 AGENTS.md「primary UI」那一句

D35 已決定「新版驗收後再另外改」。建議在 v2 驗收檢查點核准後，把：

> Use `frontend/workbench/` as the primary UI.

改成：

> Use `frontend/workbench-v2/` as the primary UI for the controlled-scene demo. `frontend/workbench/` stays unchanged as the fallback UI and for legacy Office runs (D35); do not delete or restyle it.

同時要一起核對的地方：`CLAUDE.md` 對 Claude 職責的描述（「all workbench visualization」不需改）、`docs/operations/CLAUDE_INITIAL_HANDOFF.md` 與 `docs/agents/OFFICE_DEMO_SCRIPT.md` 中指向舊工作台的操作步驟（本次未讀，列為 UNKNOWN）。

## 7. 需要使用者決定的題目

| 題 | 問題 | 建議 | 風險 | 代價 |
| --- | --- | --- | --- | --- |
| Q1 | §2 的捨棄項 X1–X10 是否全部核准（v2 不做，舊版保留）？可以逐項改成「v2 也要」 | **全部核准** | Demo 中要看舊 Office 功能時得切到舊版（頂欄有入口） | 每保留一項，多一個 Sonnet 任務（約 0.5–1 天）；X6、X7 還要等新場景有對應契約 |
| Q2 | 預設主題 | **淺色預設＋暗室切換**；2D 影像井兩種都暗 | 淺色在暗場投影時刺眼 → 有暗室切換 | 兩套 token 都要維護與做色盲檢查（小） |
| Q3 | 2D 與 3D 的關係 | **並排同時顯示**；窄螢幕上下堆疊 | 8 格時每格約 150 px 寬，細節不夠 → 用 1／2 格或雙擊放大 | 3D 寬度變小；需要自動置中縮放（mockup 已示範） |
| Q4 | 接地品質 FLAGGED 的 3D 樣式 | **空心實線，不加虛線**（舊版是空心＋虛線） | 新舊版樣式不同 | 只在 v2 覆寫樣式；狀態判斷仍重用 `contactQualityStyle` |
| Q5 | 「物理曲線用虛線」的解讀 | **任何跨 sample 的路徑都是短虛線緞帶；K8c 物理可達只用檢查結果徽章，不另畫一條線** | 若使用者原意是另一種「物理路徑」圖層，要再加一種線型 | 若要另畫：多一種線型（建議點劃線、石墨色），再做一次色盲檢查 |
| Q6 | Demo 步驟組 | **採 §4.3 七步，取代 D24**；舊步驟留舊版 | 步驟 3、6 依賴 Codex 的局部軌跡（CS-Q10）；沒有時這兩步是 UNAVAILABLE | 無額外成本 |
| Q7 | SYNTHETIC 與 FIXTURE 的用詞 | **兩個都用**：整個資料來源是 fixture 時頂部 SYNTHETIC 條；單一鏡頭／影格是 UI fixture 時格子角標 FIXTURE | 兩個詞可能讓人以為是兩種東西 | 文案說明一次即可 |
| Q8 | 實作派工 | **照 §6.6，先開 V2-1、V2-2 兩個 session** | V2-4（3D）若 R3 未到，Line2 無法載入 → 先用 1 px 線寫邏輯 | 依 CLAUDE.md 表選模型 |

## 8. Mockup 說明

- 網址：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>（私人）。頁面最上方有 SYNTHETIC 條與「設計 mockup，非真實資料」。
- 可以操作：事件 A／B1、瀏覽／查找／Demo、1／2／4／8 格、播放與拖曳時間、步進、速度、淺色／暗室、在 3D 地面畫多邊形查詢、點 3D 區間／緞帶／範圍帶、點 2D 框、點時間軸曲線列、釘選、11 台 fixture 分頁、Demo 數字鍵 1–7 與匯出紀錄、「狀態示範」切換載入中／請求失敗／完整性錯誤。
- 資料：頁內的 generator 只用來產生 SYNTHETIC payload（形狀照契約 §6）；UI 程式只讀 payload，不讀 generator 的人物與路線，和正式系統與 GT 的邊界相同。
- 和正式設計的差異（mockup 的簡化）：
  - 3D 用自寫的 canvas 正交投影，不是 three.js；材質、光線、圖層順序照 §5.5。
  - 2D 影格是簡化的針孔投影示意圖，不是渲染。
  - 字型從 Google Fonts 載入（Artifact 限制）；正式版本機打包。
  - 候選鏡頭的「可見範圍索引」用契約 §5.1 的名義地面視野；盲區負證據改用「人站在這格會不會被偵測」的靜態可偵測性。兩者不一致，正好說明契約 §5.1「地面看不到不能證明人看不到」的問題。
  - fixture 會出現的現象：事件 A 的第 0 張沒有任何鏡頭偵測到人，W1 前幾張與 W2、N1 近端的接地是 UNKNOWN（腳出框）。這是照契約 §5.1 的名義鏡頭位置算出來的，對應 §5.2「近端出框風險」，不是 bug。
  - 曲線列的 UNKNOWN 段在契約 §6.4 沒有對應的 kind；mockup 由 person-layer 推導（標 `UI_UNKNOWN_SPAN`），見 §9。
  - 2D 格子在 mockup 裡用頁內的簡化邏輯排版，沒有 import #71；格子狀態（READY／MISSING／OUT_OF_RANGE／UNKNOWN）、空格「無更多候選」、釘選只改版面、分頁，這些語意都和 #71 的 `pageView`／`toDisplayModel` 一致。正式版改用 #71。

## 9. 契約與介面待釐清（UNKNOWN）

1. **曲線的 UNKNOWN 段**：§6.4 的 segment kind 只有 OBSERVED、INFERRED_CONNECTOR、BLIND_HYPOTHESIS、MISSING_GAP。一條局部軌跡中「有偵測但接地 UNKNOWN」的時段沒有 kind。建議契約加 `UNKNOWN_GAP`（`evidence_state: UNKNOWN`、`reason`），點擊回 `NO_SUPPORT`。
2. **負證據影格清單的欄位**：§6.5 說盲區假設要「列出兩端觀測與負證據影格」，但回應範例沒有欄位。需要 `negative_evidence[]: {camera_id, frame_ref, timestamp_s, state: NO_DETECTION|DETECTION_PRESENT, used}`。
3. **完整性錯誤的回應形狀**（R5）：#71 已用假設形狀寫 fixture，契約仍未定義。
4. **假設回應的 schema**：是否沿用 `workbench.blind-hypothesis.v1`（§6.2）。
5. **同步影格的 media URL 形式**（R4）。
6. **size=1＋釘選的翻頁行為**：#71 列為 UNKNOWN；本設計同意它的實作（釘選鏡頭在第 1 頁，其餘依序翻頁），等使用者確認。
7. `HUMANOID_DISPLAY_MAX_INTERVAL_M` 與所有門檻：CS-Q9 OPEN；mockup 用 0.6 m 只是示意。
8. `docs/operations/CLAUDE_INITIAL_HANDOFF.md`、`docs/agents/OFFICE_DEMO_SCRIPT.md` 中指向舊工作台的段落：本次未讀。

## 10. 實際產出 / Actual output

- Model / effort: Claude Opus 5.5（`claude-opus-5-5`）／ high
- PR / commits: 見 PR 描述（本文提交時尚未知 SHA）
- Files changed: `docs/agents/WORKBENCH_V2_DESIGN_20261018.md`（本文，新檔）
- Commands run and results:
  - `git show origin/claude/office-demo-visualization:<path>`（`frontend/workbench/*`、`src/amidst/workbench/service.py` 靜態資產段落）與 `git show 2643771:<path>`（契約、UX 草圖）、`git show 2627b89:frontend/workbench-v2/<path>`（#71 的 player-grid 與 fixture）：唯讀盤點。
  - mockup 腳本：`node --check`（通過）；fixture generator 在 node 執行一次（事件 A 56 筆估計／48 筆接地 READY、B1 124／107；候選排序 A：W2 7.2 m²、W1 6.0 m²、R102 不相交，`READY`；B1：W2、W1、N1 不相交、R102 未知，`PARTIAL`；B1 盲區 8.8–13.6 s、25 個切片皆非空）。
  - 本機預覽一次（內建瀏覽器，1440×900 暗色）：無 console 錯誤；看到 3D 縮放偏小後改為自動置中縮放，改後未再截圖。
- Artifacts:
  - mockup Artifact：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>（Version 1）
  - mockup 原始檔：LOCAL scratchpad `mockup/workbench-v2-mockup.html`，91,398 bytes，SHA-256 `e1b3bf8ece8ba36ed9fc04a778dafb9e8e2495e1891fe2771f7e21fb8aa713e4`；不進 repo
- Verified: 矩陣中每個模組與 export 名稱都以 `git show` 對照整合分支 @ `f481fe0`；`app.mjs:1515` 會在 import 時啟動；服務靜態資產為逐檔白名單、舊版掛在 `/`；欄位名稱對照契約 @ `2643771`。
- Not verified: 沒有實作、沒有跑舊工作台測試（不需要，未改程式）；mockup 改自動縮放之後沒有再截圖；淺色主題、窄螢幕與色盲模擬沒有實際檢查（列入 V2-1、V2-10）；`OFFICE_DEMO_SCRIPT.md`、`CLAUDE_INITIAL_HANDOFF.md` 未讀。
- Deviations, UNKNOWN items and follow-ups: §7 Q1–Q8 等使用者決定；§9 八項待釐清；§6.3 列了 4 點對 #71 的審查意見（不由本任務修改）。
