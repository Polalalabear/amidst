# 工作台 v2 設計（受控場景 Demo）

日期：2026-10-18（Asia/Taipei）

狀態：**設計第 3 版。使用者已決定 Q1–Q10（D43）並新增 D45、D46；可以開始 V2-1、V2-2（§6.6）。**本文不改任何程式檔，也不宣告任何檢查點通過。

| 版本 | Commit | 內容 |
| --- | --- | --- |
| 1 | `3fadccc` | 初稿：並排 2D／3D、淺色預設＋暗室 |
| 1.1 | `8d78094` | 改接 player-grid #71 @ `2627b89` |
| 2 | `55b1ae1` | 依使用者看完 mockup 的意見改：Scientific Investigation Console 風格、只有深色、2D／3D 切換、時間與速度在畫面正下方、漢堡側欄（§0.1） |
| 3 | 本版 | 記錄 D43；加入 D44（約束區間）、D45（估計誤差要明確標出）、D46（3D 只顯示 2D 重現）；V2-1、V2-2 任務卡（§0.2、§6.6） |

- 可操作 mockup（SYNTHETIC，非真實資料）：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>，Version 3（私人 Artifact，需要擁有者分享才能給別人看）。第 3 版原始檔放在 `docs/agents/assets/workbench-v2-mockup-v3.html`，供 V2-2 移植 fixture generator（§6.6）。
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
| 受控場景契約 v1.1 草案（D44） | `claude/controlled-scene-a` @ `4bfb546`（#65）：§3.12 `track_height_estimate`、§6.3.1 `composed_ground`、CS-Q15。**草案，等 Codex 確認**；本文的欄位名都照它，改名時只改 `uncertainty.mjs`（§6.1） |
| 規則 | `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md` |

### 0.1 第 2 版的使用者意見（由協調者轉達，引號內是原話）

> 「風格：Scientific Investigation Console
> 系統顏色先固定深色即可，不用切換。
> 2D 3D 顯示使用切換。目前2D 同步畫面過小。速度相關調整應在相對應畫面最下方（使用者要不下滑就能調整時間、速度 同時看到畫面變化）。
> 左側改成類似 burgerbar 透過點擊選擇是否常駐顯示或是縮放，以利於畫面查看或對照資訊。」

| # | 意見 | 本版的處理 | 位置 |
| --- | --- | --- | --- |
| U1 | Scientific Investigation Console | 外框改成儀器控制台：單色石墨、等寬讀數、量測標尺、座標讀數、角落定位框；證據仍是唯一的色相 | §5 |
| U2 | 只有深色，不用切換 | 移除主題切換，只維護一套深色 token。Q2 關閉 | §5.1、§7 |
| U3 | 2D／3D 切換；2D 太小 | 同一主要區域在 2D 與 3D 間切換（`V` 鍵或分段鈕），時間與選取保留；2D 格放大到 1440×900 下 4 格每格 491×276 px（第 1 版約 284×160）。Q3 關閉 | §4.1、§4.3 |
| U4 | 時間、速度在畫面正下方，不用捲動 | 播放、步進、速度、時間讀數、時間軸固定在主要區域正下方（2D、3D 共用一條），1440×900 下整頁不捲動 | §4.1 |
| U5 | 左側漢堡選單，可常駐或縮放 | 48 px 圖示列＋300 px 面板，三種狀態：常駐（主畫面讓位）、浮動（蓋在主畫面上，主畫面寬度不變）、收合（只剩圖示列，主畫面最寬） | §4.2 |

和原話可能不同的解讀列在 §7.1。

### 0.2 第 3 版的使用者決定（由協調者轉達，引號內是原話）

| 決定 | 內容 | 落在本文 |
| --- | --- | --- |
| **D43** | Q1、Q4–Q10 全部照建議；§7.1 的解讀一併接受 | §7 |
| **D44** | 契約 v1.1（A 包起草中）：接地區間納入遮擋邊界、軌跡身高（只在同一條 local track 內）、速度界；每一格 payload 帶上用到的條件與不確定度（區間長度 m 或 polygon 面積 m²） | §3、§5.3、§6.1、§6.6 |
| **D45** | 「估計誤差要明確標出（文件內和demo時都要說）」 | §4.3、§4.5、§5.3.1、§6.6 |
| **D46** | 3D 人物只顯示從 2D 重現的結果，鏡頭看得到的區段也一樣；永遠不讀 GT，也不做 GT 對照圖層 | §1、§2、§5.5 |

盤點方式：只用 `git show <ref>:<path>` 讀 `frontend/workbench/` 與 `src/amidst/workbench/service.py` 的靜態資產段落。沒有啟動服務，沒有讀 GT、影像或影片。

## 1. 設計原則

1. **只有證據有顏色。** 外框、按鈕、選取、文字都是單色石墨。畫面上出現色相，就代表一個 evidence state。這樣一眼就能分辨「這是資料」還是「這是介面」。
2. **每個 evidence state 至少有三種編碼：** 顏色、線型或填法、文字碼。色盲、灰階列印或投影偏色時，靠線型和文字碼仍然分得出來。
3. **推論永遠不比觀測「實」。** 觀測是實線、實色；推論是空心、短虛線或半透明；假設是長虛線加範圍帶。推論可以畫得比較顯眼（例如約束區間是主圖層），但不會畫成實心實線，也不會比觀測更亮。
4. **沒有證據就什麼都不畫。** MISSING、UNKNOWN 不在 3D 畫位置，只在時間軸與側欄說明原因。盲區不畫位置，只畫範圍帶與路徑束。
5. **身分永遠是 UNCONFIRMED。** 圖例列常駐「身分 UNCONFIRMED」。曲線不用人名、不用 actor 色、不用「同一人」字樣；兩條局部軌跡之間只有「假設」。
6. **一個畫面，三種模式。** 不再有多頁導覽與身份入口。瀏覽、查找、Demo 共用同一個主要區域與時間軸，模式只換側欄內容與格子排序。
7. **畫面優先。** 主要區域盡量給影像；控制放在影像正下方，資訊放在可收合的側欄。看畫面時不用捲動，也不用在畫面之間來回找控制項。
8. **估計誤差要看得到（D45）。** 每個重現或推論的幾何旁邊都有不確定度讀數與用到的條件；資料缺不確定度時不畫、報錯，不默默省略。
9. **3D 只有重現（D46）。** 3D 的人物、區間、曲線全部由 2D 影像推得；看得到的區段也是重現，不是軌跡回放；沒有 GT 圖層。

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
| F8 | 2D／3D 同步（共用 timestamp，2D 與 3D 二選一切換） | `app.mjs` `workspaceDisplay()`、`view.setTimestamp` | 是 | **同一主要區域切換 2D／3D**（U3，取代第 1 版的並排）；切換保留時間與選取；3D 有子畫面。共用一個時鐘 store |
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
| F19 | 接地估計顯示（POINT／SEGMENT、腳點像素帶、`raw_*` 不畫） | `ground-estimate.mjs` | 是 | 3D 人物圖層改以 v1.1 草案的 `composed_ground`（約束區間，推論）為主；原 `ground_estimate` 是可切換的「單格投影（追溯）」細線。重用 `groundEstimatePlan(s)`、`basisLabel`、`segmentLabel`、`unknownLabel`（schema 相同：區間觀測 v1 §3） |
| F20 | 跨鏡頭多解還原面板（D18 候選排名、速度曲線） | `cross-camera.mjs`、`blender-motion.mjs` | 否 | **捨棄（X6）**。綁 D18 端點與舊 timeline；新 Demo 用 `curve_layer` 的 `candidate_ref`、`association`。速度曲線不在新 Demo |
| F21 | 物理人工確認（門／走廊／碰撞篩選、人工判定） | `physical-review*.mjs` | 否 | **捨棄（X7）**。屬舊 Office；新場景的物理結果只以 `physical_verdict` 與檢查結果徽章呈現 |
| F22 | 分時畫面牆（8／12／16 格診斷）與 C5 建議檢視 | `app.mjs` frame wall、`frameQueryPanel()` | 否 | **捨棄（X8）**。契約 §6.2：C5 建議影格不是同步影片。新 Demo 用候選鏡頭查詢＋同步格取代 |
| F23 | 語意查詢表單（地點、鏡頭、行為、label 預設） | `app.mjs` `guidanceSelection`、`semantic_presets` | 否 | **捨棄（X9）**，由查找模式（地面選區、時間範圍、模板）取代 |
| F24 | 放大來源影像 | `app.mjs` `frame-enlarge` | 是 | 1 格模式即放大；格子雙擊切到 1 格並釘選該鏡頭 |
| F25 | 圖例（觀測／候選推論／缺漏、K4 五色圖例、有資料／無資料） | `app.mjs` `markerLegendItems`；`blind-hypothesis.mjs` `LEGEND_ITEMS` | 是 | 底部常駐圖例（§5.3），每項附線型樣本與契約代碼 |
| F26 | 標註版本提示（標註 v<n> 已發布、結果未重跑） | `app.mjs` `sourceVersion` | 否 | **捨棄（X10）**。新場景用 `scene_version`、`map_sha256` 等 pin，顯示在「來源與隔離」 |
| F27 | 歷史診斷人形（DISPLAY_ONLY） | `app.mjs`、`scene.mjs` | 否 | 不做。契約：長區間不在中點放人形，不出現球狀替身 |
| F28 | GT 軌跡回放、GT 對照圖層、評估區的 GT 顯示 | `app.mjs` test 頁「獨立評估區」 | 否 | **不做（D46，使用者決定）**。v2 沒有任何 GT 圖層或回放；凍結後評估另案，不放在 v2 |

**D46：**3D 的人物、區間、曲線都是由 2D 影像重現的推論。鏡頭看得到的區段也一樣：畫的是 `composed_ground`（或單格投影），不是軌跡回放，也沒有「真實位置」可以對照。要對照時，用 3D 子畫面（同一時間的 RGB 影格，即觀測）對 3D 重現（推論），兩者的時間都是同一個 sample。

## 3. 新需求與 v2 位置

| 新需求 | 依據 | v2 位置與規則 |
| --- | --- | --- |
| 候選鏡頭查詢，排序依 D28 | 契約 §6.1 | 查找模式側欄。每列：名次、`camera_id`、相交等級徽章（● 相交／◐ 通路／○ 不相交／? 未知，四種外框不同）、重疊 m²、附帶證據一行（「感知 NOT_EVALUATED，偵測張數 null，不影響排序」）。上方整體狀態 `READY`／`PARTIAL`／`UNKNOWN` 與原因。下方固定寫排序依據。`UNKNOWN` 不寫成不相交 |
| 1／2／4／8 格同步播放 | 契約 §6.2、CS-Q13；UX §3 | 主要區域標題列的格數切換，並顯示每格實際像素（§4.1）。候選集合與格數分開；不足留空格「無更多候選」，不複製補位；超過用分頁；釘選只改版面 |
| 查找模式：地面選區、時間範圍、模板；不用 Agent | 契約 §6.1；UX §2、§4 | 選 `AREA_*` 或在 3D 地面點多邊形；時間半開區間；模板「經過」「進出」。送出後格子依排序重排、時間跳到開始、範圍外變暗。「返回查找前」恢復原排列與時間，查詢保留可再進入 |
| 3D 人物以區間為主 | 契約 §6.3；UX §5.1 | SEGMENT＝實線段加兩端短刻度（├──┤）；長度 ≤ `HUMANOID_DISPLAY_MAX_INTERVAL_M`（待約定）時加半透明「人形範圍」掃掠體；更長只畫線段。POINT＝地面短十字。不放實心人形、不放球 |
| 曲線：實線、短虛線緞帶、物理曲線用虛線 | 契約 §6.4；UX §5.2 | 單筆橫向區間是實線；跨 sample 的連接一律是短虛線緞帶（兩條邊＋淡填）；盲區假設是長虛線＋範圍帶。「物理曲線用虛線」本文解讀為「任何跨 sample 的路徑都是虛線」（Q5） |
| 影格之間的狀態規則 | 契約 §2.2 | 見 §4.4 |
| 接地區間的組成條件（D44） | 契約 v1.1 草案 §6.3.1 | 3D 人物圖層畫 `composed_ground`（`INFERRED_CONSTRAINED`，草案名）；條件 `prior`、`track_height`、`occlusion_near`、`lowest_visible_far`、`speed` 在讀數與 inspector 列出 |
| 估計誤差明確標出（D45） | 使用者決定 | 3D 讀數（§5.3.1）、inspector「誤差來源」、Demo 每步旁白（§4.3）；缺欄位＝完整性錯誤（§4.5） |
| 3D 只顯示 2D 重現（D46） | 使用者決定 | §2 F28、§5.5；子畫面是觀測對照 |
| evidence state 圖例 | UX §7 | 底部常駐，§5.3 |
| 新 Demo 步驟組 | UX §8 | §4.3 |

## 4. 資訊架構與版面

### 4.1 結構

只有一個工作區。進入就是瀏覽模式，載入目前場景的第一個事件。

```text
┌ SYNTHETIC 條 24 px（只在資料是 fixture 時出現；斜紋單色）──────────────────────────────────────┐
├ 頂欄 44 px：AMIDST │ 場景▾ │ 事件 [A][B1] │ run_id │ … │ 模式 [瀏覽][查找][Demo] │ 舊版             │
├────┬──────────────┬─────────────────────────────────────────────────────────────────────────┤
│ ≡  │ 面板 300 px    │ 主要區域標題 32 px：[2D 同步畫面][3D 空間]  格數 [1][2][4][8]  每格 W×H px  分頁 │
│ 查找│ （常駐／浮動／收合）├─────────────────────────────────────────────────────────────────────────┤
│ Demo│ ・模式面板     │                                                                         │
│ 證據│ ・證據         │       主要區域：2D 同步格  或  3D 空間（切換，`V` 鍵）                       │
│ 圖層│ ・圖層         │       2D：格子以 16:9 最大化排滿；3D：子畫面顯示第 1 格鏡頭                    │
│ 來源│ ・來源與隔離   │                                                                         │
│    │              ├─────────────────────────────────────────────────────────────────────────┤
│ 48 │              │ 時間列 112 px：t／總長 │ 速度 [0.5×][1×][2×] │ ▶ ◀0.2 ▶0.2 │ 影格 #、sample_age │ 軌道 │
├────┴──────────────┴─────────────────────────────────────────────────────────────────────────┤
│ 圖例 28 px：觀測 ├──┤  推論 ┄┄  假設 ╌╌＋帶  MISSING ╱╱  UNKNOWN ⋯?   SYNTHETIC      身分 UNCONFIRMED │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **主要區域**一次只顯示 2D 或 3D。切換時保留時間游標、選取、釘選、查詢與格數；3D 視角在切回時保留。
- **時間列**緊貼在主要區域正下方，2D 與 3D 共用。播放、步進、速度、時間讀數和軌道都在這一條；1440×900 下整頁不捲動（固定高度：SYNTHETIC 條 24＋頂欄 44＋主要區域標題 32＋時間列 112＋圖例 28 px，其餘都給主要區域，約 660 px 高）。
- **3D 子畫面**：在 3D 時，右下角顯示第 1 格的鏡頭（釘選的、點擊回溯暫時釘選的，或排第 1 的），可關閉。點擊回溯在 3D 不自動切到 2D：子畫面會換成支持影格並框出 bbox，側欄另有「在 2D 查看此影格」。
- **圖例列**永遠在畫面底部，不能收起。

**2D 格子尺寸**（影像區 16:9；每格另有 22 px 標頭、18 px 底列、2 px 邊框；格距 6 px；主要區域內距 8 px）：

| 格數 | 排列 | 1440×900、側欄收合 | 1440×900、側欄常駐 | 第 1 版（並排，估算） |
| --- | --- | --- | --- | --- |
| 1 | 1×1 | 1068×601 | 1044×587 | 約 574×323 |
| 2 | 2×1 | 669×376 | 519×292 | 約 574×323（上下堆疊，超出高度需捲動） |
| 4 | 2×2 | 491×276 | **491×276（mockup 實測）** | 約 284×160 |
| 8 | 4×2 | 331×186 | 256×144 | 約 139×78 |

- 算法：`w = min((W − 6(c−1))/c, ((H − 6(r−1))/r − 42) × 16/9)`，取整數；W、H 是主要區域扣掉內距後的寬高（收合時 1344×643，常駐時 1044×643）。
- 只有「4 格、常駐」是在 mockup 中以 1440×900 實測（標題列顯示的值）；其他是同一公式算出，未逐一截圖。第 1 版的值是由第 1 版 CSS 估算。
- 浮動狀態的格子尺寸與收合相同（面板蓋在上面，不改寬度）。

### 4.2 側欄（漢堡選單）與斷點

| 狀態 | 進入方式 | 主要區域 | 適合 |
| --- | --- | --- | --- |
| 常駐 | 面板標題的「常駐」；`[` 鍵在常駐與收合間切換 | 讓出 348 px（圖示列 48＋面板 300） | 對照證據、操作查找或 Demo |
| 浮動 | 收合時點 ≡ 或任一圖示；面板標題的「浮動」 | 寬度不變，面板蓋在左側並有陰影 | 偶爾查一下資訊 |
| 收合 | 面板標題的「收合」；浮動時點主要區域或按 Esc | 只讓出 48 px 圖示列，最寬 | 看畫面 |

- 圖示列：≡（展開／收合）、查找、Demo、證據、圖層、來源。點「查找」「Demo」同時切換模式；點「證據」「圖層」「來源」打開面板並捲到該段。有選取時「證據」圖示有一個墨色小點。
- 使用者選的常駐或收合會記在瀏覽器本機（`localStorage`，讀不到就預設常駐）；浮動不記。
- 浮動面板打開時，點主要區域會關掉面板，同時那次點擊照常生效（例如點 3D 區間）。

| 寬度 | 版面 |
| --- | --- |
| ≥ 760 px | 圖示列｜面板（依狀態）｜主要區域＋時間列 |
| < 760 px | 圖示列改成頂部一列；面板在主要區域上方展開；8 格改 2×4；時間列改上下兩段 |

Demo 的目標是 1440×900 以上的桌面或投影；窄版只保證不破版。

### 4.3 模式

| 模式 | 進入 | 側欄 | 格子順序 | 3D 額外圖層 | 離開 |
| --- | --- | --- | --- | --- | --- |
| 瀏覽 | 預設；或從查找切回 | 證據、圖層、來源 | 目錄預設順序（與任何查詢無關） | — | — |
| 查找 | 頂欄或圖示列「查找」 | 查詢表單、候選清單、證據、來源 | 送出後依 `recommended_camera_ids` | 目標多邊形（單色斜線）、候選足跡（點線外框） | 「返回查找前」恢復排列與時間；切回瀏覽時查詢保留，可「再次進入上次查詢」 |
| Demo | 頂欄或圖示列「Demo」 | 步驟清單（1–7）、目前步驟說明、驗收按鈕、匯出 | 依步驟 | 依步驟 | 切到其他模式 |

**Demo 步驟組（取代 D24，UX §8）：**

| 鍵 | 事件 | 主要區域 | 畫面 | 旁白（D45；數字由當下資料填入，以下是 mockup 的 SYNTHETIC 值） |
| --- | --- | --- | --- | --- |
| 1 | A | 2D | 瀏覽、4 格同步播放；A 只有 3 台，第 4 格「無更多候選」 | 看到的是觀測：2D 格子就是 RGB 影格本身。這一步沒有位置估計，誤差：不適用。 |
| 2 | A | 2D | 查 `AREA_R101_FRONT`、0–10 s、經過；W2、W1 在前，R102「不相交」 | 候選排序是推論：依名義地面足跡相交與重疊面積，偵測數不列入。誤差來源是名義地面視野（未驗證）；排序不是機率。 |
| 3 | A | 3D | 停在影格之間，說明琥珀色內插刻度（只在合法局部軌跡內）；點區間，子畫面換成支持影格 | 3D 的區間都是從 2D 重現的推論（約束區間），看得到的區段也是重現，不是軌跡回放。琥珀刻度是影格間內插。誤差：區間半長 ±0.04–0.31 m（設計估計），來源是腳點像素帶、身高先驗或軌跡身高、速度界。 |
| 4 | B1 | 2D | 進出查詢 8–20 s，候選重排；`PARTIAL` | 候選重排是推論；R102 的可見範圍索引缺失，整體 PARTIAL。誤差來源同步驟 2。 |
| 5 | B1 | 3D | 轉角盲區：範圍帶與路徑束，不畫位置；時間在盲區時只加亮切片 | 盲區沒有位置，只有假設範圍帶。大小用切片面積表示，盲區內約 0.06–10.94 m²；來源是速度上限 2.0 m/s（設定，未約定）與負證據。設計估計。 |
| 6 | B1 | 3D | N1 再出現：假設可達，身分 UNCONFIRMED；兩人沒被連成一條 | N1 再出現的區間是重現推論，誤差 ±（N1 區間半長範圍）m（設計估計）；和前段只是「假設可達」，身分 UNCONFIRMED，兩個人沒有被連成一條。 |
| 7 | B1 | 2D | 切 8 格：後 4 格空，不補位 | 格數只改版面，不改證據；空格不是缺漏。誤差：不適用。 |

- **旁白**同時出現在 Demo 面板與主要區域底部的字幕條；講者照念即可。
- 輸出凍結並以 GT 評估之前，旁白只能說「設計估計」，不能說「準確度」「誤差 x%」或任何經驗證的數字。凍結後若要改說實測誤差，要另開檢查點。
- 旁白的數字由當下 payload 計算（例如該事件所有約束區間半長的最小–最大值、盲區切片面積的範圍），不寫死在步驟檔。

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
| 缺不確定度欄位（D45） | 整個圖層所屬的 run | **不顯示** | **不顯示** | 停用 | 阻擋式面板：`PAYLOAD_INCOMPLETE · UNCERTAINTY_FIELD_MISSING`、哪一筆缺哪個欄位。不默默省略讀數，也不畫沒有不確定度的區間。比照完整性錯誤處理 |

## 5. 視覺規範

方向：**Scientific Investigation Console**（使用者指定，U1）。本文的解讀是「冷靜、精確、資訊密度高的調查儀器」，不是科幻 HUD：

- 外框是深石墨單色；狀態用文字碼、外框樣式與符號表示，不用發光、霓虹或漸層。
- 讀數一律等寬字：時間 `12.47 s / 20 s`、影格 `#062`、`sample_age +0.07 s`、座標 `x 16.20 · y 3.68 · z 0.00 m`。
- 量測家具：3D 有 5 m 比例尺、世界軸（+X、+Y）、游標下的地面座標與所屬區域 ID（未標地面寫 UNKNOWN）；主要區域有角落定位框；格子標題列寫實際像素尺寸。
- 3D 是深色建築平面模型：牆剖切、細網格。證據是唯一的彩色墨水。

### 5.1 色彩 token（只有深色）

只維護一套深色 token（U2）；`color-scheme: dark`，沒有淺色變體，也沒有主題切換。

| token | 用途 | 值 |
| --- | --- | --- |
| `--bg` | 頁面底 | `#0A0D10` |
| `--panel`／`--panel-2`／`--panel-3` | 面板、3D 底／次層／選中列 | `#11151A`／`#161B21`／`#1D232A` |
| `--ink` | 主文字、主要按鈕、按下狀態 | `#DCE3E9` |
| `--ink-2`／`--ink-3` | 次文字／說明、量測家具 | `#9BA6B0`／`#66717B` |
| `--rule`／`--rule-2` | 規線 | `#262D35`／`#1A2026` |
| `--well`／`--well-2` | 主要區域底／格子底 | `#05070A`／`#0C1014` |
| `--sel` | 選取光暈、選中格外框 | `#F4F7F9` |
| `--obs` | 觀測 | `#8CCBFF` |
| `--int` | 推論（內插、方向） | `#E39B2F` |
| `--hyp` | 假設（盲區、日後預測） | `#CC6FAE` |
| `--miss` | MISSING 斜紋 | `#6C747C` |
| `--unk` | UNKNOWN 點線 | `#AEB7BF` |
| `--floor`／`--floor-room` | 3D 走廊／房間地面 | `#151A20`／`#10151A` |
| `--wall-side`／`--wall-cap` | 牆側面／剖切面 | `#2B333B`／`#8C97A1` |
| `--err`／`--err-soft` | 完整性錯誤面板 | `#F08C8C`／`#2C1517` |

- 三個證據色取自 Okabe–Ito 的藍、橙、紅紫，再調明度。深色底上明度排序是觀測（最亮）> 推論 > 假設，灰階下仍分得開；最亮的永遠是觀測，符合原則 3。
- 色盲時：deuteranopia／protanopia 下觀測與假設都偏藍灰，所以兩者另以明度（最亮對中等）與線型（實線對長虛線＋範圍帶）區分；推論在三種色盲下都偏黃，另有短虛線。MISSING（斜紋）、UNKNOWN（點線框＋?）、SYNTHETIC（斜紋條＋反白字，只用墨色）不靠顏色。
- 錯誤色只用在完整性錯誤面板，不出現在任何證據圖層上。
- **實作前的檢查**：每個 token 對都要過一次色盲模擬（protanopia、deuteranopia、tritanopia）與灰階截圖，並確認文字對比 ≥ 4.5:1。這列入 V2-1 的驗收（§6.6）。本版 mockup 尚未做這項檢查。

### 5.2 字體與尺寸

| 角色 | 字體 | 用法 |
| --- | --- | --- |
| UI 內文 | IBM Plex Sans ＋ Noto Sans TC | 13 px／1.45 |
| 標籤、區塊標題 | IBM Plex Sans Condensed 600 | 11–12 px，大寫，字距 .06–.08em |
| ID、時間、hash、數字、所有讀數 | IBM Plex Mono | 10–22 px（時間讀數 22 px），`tabular-nums` |

- 字級：10／11／12／13／16／22 px，不另加。
- 間距：4 px 基準（4、8、12、16、24）。
- 圓角：控制項 2 px；只有浮動提示 6 px；格子、面板 0。
- 陰影：只用在浮動側欄（`12px 0 32px rgba(0,0,0,.55)`）。其他面板之間用規線分隔，不用卡片陰影。
- 按下狀態：反白（`--ink` 底、`--bg` 字）；圖示列的目前項目是左側 2 px 墨線。
- 字型檔要本機打包（`frontend/workbench-v2/fonts/`，OFL 授權），不從外部 CDN 載入；本機展示不依賴網路。授權檔一併放入。

### 5.3 Evidence state 編碼

| 狀態（契約代碼） | 文字碼 | 3D | 2D | 時間軸 | 符號 |
| --- | --- | --- | --- | --- | --- |
| 觀測 `PROJECTED_OBSERVATION` | OBS 觀測 | 「單格投影（追溯）」：`--obs` 1.5 px 細實線，畫在約束區間中央；可關閉 | bbox 實線框，左上角實底標籤「觀測 c0」 | 實心色塊（腳看得到的影格） | ├──┤ |
| 推論 `INFERRED_CONSTRAINED`（v1.1 草案名） | INC 約束區間 | `--int` **空心**條（外 4.5–7 px、內留底色）＋兩端短刻度；旁邊有不確定度讀數（§5.3.1）；短區間加人形範圍 | 無 | 空心框（腳看不到、只有約束區間的影格） | ├══┤ |
| 推論 `INFERRED_INTERPOLATION` | INT 推論 | `--int` 短虛線（3–3）緞帶：兩條邊＋16% 淡填；方向箭頭也是短虛線 | 無 | 兩條短虛線 | ┄┄ |
| 假設 `INFERRED_HYPOTHESIS` | HYP 假設 | `--hyp` 長虛線（10–6）路徑束；範圍帶包絡 13%、當下切片 34%；第 2 名以後路徑 55% 不透明 | 盲區時負證據角標（玫紅虛線框） | 淡填＋長虛線 | ╌╌＋帶 |
| `MISSING` | MISS | 不畫 | 灰色斜紋整格 | 斜紋 | ╱╱ |
| `UNKNOWN` | UNK | 不畫 | 點線框「?」；接地 UNKNOWN 時 bbox 改點線 | 點線框 | ⋯? |
| 接地品質 `FLAGGED` | — | 單格投影改為觀測色**空心**細線（外 3 px、內 1.2 px 底色），**不加虛線**（D43） | 側欄寫「接地點不可靠（原因）」 | 不變 | — |

- 選取一律是單色光暈（`--sel`），不改變證據色，也不加粗成看起來更確定。
- 名次、可達性等「合理程度」只用順序與不透明度表示，不顯示百分比，也不寫「機率」。
- 「人形範圍」是沿約束區間掃過的半透明體（13% 填、35% 外框），標示「身體可能占的範圍」，不是位置。
- 約束區間與內插緞帶同屬推論（琥珀色系），用「空心條」對「短虛線緞帶」與文字碼 INC／INT 區分。

#### 5.3.1 不確定度讀數（D45）

| 對象 | 讀數 | 例 | 何時顯示 |
| --- | --- | --- | --- |
| 約束區間 | `±` 區間半長（m）＋用到的條件 | `±0.27 m（先驗）`、`±0.11 m（軌跡身高＋速度界）`、`±0.12 m（腳點像素帶＋速度界）` | 當下 sample 的每個區間，以及被選取的區間 |
| POLYGON 窄帶 | 面積（m²）＋條件 | `0.41 m²（先驗＋遮擋邊界）` | 同上 |
| 內插刻度 | `±` 兩端半長的較大者 | `t = 5.10 s（內插）±0.28 m` | 播放頭在兩個 sample 之間、且有合法連接時 |
| 盲區假設切片 | 切片面積（m²）＋來源 | `面積 9.25 m²（速度上限＋負證據；不是位置）` | 播放頭在盲區內 |

- 讀數用 `--int` 等寬字、帶外框的小標籤，貼在幾何旁；圖例有「±m 不確定度：區間半長（條件）· m² 切片面積 · 設計估計」。
- `±` 一律是「這個範圍的半寬」，不是標準差，也不是信賴區間；inspector 另外列區間全長。
- 條件名稱固定：先驗、軌跡身高、遮擋邊界、最低可見點（只在 inspector 列，讀數不列，因為它通常不收緊）、速度界；腳看得到時加「腳點像素帶」。
- inspector 對每一個推論列「誤差來源」：單格投影的區間、每個用到的條件與數值、每個沒用到的條件與原因、校正誤差（未評估時寫 UNKNOWN）、同步誤差 `clock_error_s`，最後一行固定寫「設計估計：輸出凍結前沒有以 GT 驗證」。
- 不確定度不能讓推論看起來更確定：不畫「最可能點」、不收成中點、不用漸層暗示機率。

### 5.4 SYNTHETIC 與 FIXTURE

| 標示 | 什麼時候 | 樣式 |
| --- | --- | --- |
| SYNTHETIC 條 | 本 session 的資料來源不是凍結的真實渲染（fixture 模式、設計 mockup） | 頁面最上方整條單色斜紋，等寬字「SYNTHETIC」＋說明；不能關閉 |
| FIXTURE 角標＋浮水印 | 單一鏡頭或影格來自 UI fixture（例如測分頁的假鏡頭） | 格子右下虛線框「FIXTURE」＋斜向淡浮水印 |
| 3D 角標 | 3D 圖層來自 fixture | 左上虛線框「SYNTHETIC · FIXTURE」；子畫面右下另有「SYNTHETIC」 |

都只用墨色，不用任何證據色。真實與 fixture 不放在同一個畫面（UX §7）。

### 5.5 3D 場景

| 項目 | 規範 |
| --- | --- |
| 投影 | 正交。預設斜視（仰角約 53°）；「俯視」一鍵切換。拖曳繞 Z 軸旋轉與調仰角，滾輪縮放；切換事件或視角時自動置中縮放 |
| 地面 | 走廊 `--floor`、房間 `--floor-room`（深色）；1 m 細網格、5 m 加深。無貼圖 |
| 牆 | 擠出 0.15 m 厚，**顯示高度剖切在 1.2 m**（不是實際牆高；標示在 3D 標題列），側面依朝向做 Lambert 明暗，頂面是實心「剖切面」色。不投影子 |
| 光線 | 一盞固定方向光（西北上方 45°）＋環境光；只影響牆側面。證據圖層不受光（flat、unlit），永遠畫在牆之上 |
| 門 | 開口處點線 |
| 鏡頭 | 墨色小三角形視錐符號＋點線落地線＋`W1` 類短 ID。不畫完整視錐（不代表可見性） |
| 量測家具 | 左下 5 m 比例尺（與螢幕水平對齊）、原點的 +X／+Y 軸、游標地面座標讀數；都用 `--ink-2`／`--ink-3` |
| 子畫面 | 右上，寬 min(300 px, 42%)；標題「觀測（RGB）· 第 1 格」。內容就是 2D 格子的同一個 view，不另開資料來源。用途是對照：子畫面是觀測，3D 是重現（D46） |
| 人物圖層（D46） | 只畫由 2D 重現的 `composed_ground` 與單格投影；看得到的區段也是重現，不是軌跡回放；沒有 GT 圖層。3D 標題的提示文字固定寫這一句 |
| 文字 | 房間、走廊名稱用窄字體小字，墨色 3 |
| 圖層順序（下到上） | 地面 → 網格 → 查詢目標（單色斜線）→ 候選足跡（點線）→ 牆與門 → 鏡頭 → 假設範圍帶 → 假設路徑 → 推論緞帶 → 人形範圍 → 約束區間 → 單格投影細線 → 時間刻度 → 不確定度讀數 → 選取光暈 |
| 抬高 | 證據層依序 z = 0.02／0.03／0.04／0.05／0.06 m，避免 z-fighting |
| 實作 | three.js（沿用 `/vendor/three.module.js`）。線寬需要大於 1 px，使用 `Line2`／`LineMaterial`（three 的 `examples/jsm/lines`，需服務白名單，§6.4）。虛線圖樣以螢幕像素定義，縮放時不變 |

### 5.6 2D 疊圖

- bbox：觀測色實線 3 px；接地 UNKNOWN 時改點線。左上實底標籤。
- 選取：`--sel` 外光暈＋加粗，同時格子外框變成 `--sel`。
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
| `index.html` | 外框 | 版面骨架（§4.1 固定高度）、importmap（`three`）、字型 |
| `style.css` | 外框 | §5 的深色 token（只有一套）與元件樣式 |
| `tokens.mjs` | 純 | evidence state 編碼表（色 token 名、線型、文字碼、符號），供 2D、3D、時間軸、圖例共用 |
| `store.mjs` | 純 | 單一 state＋reducer：模式機、主要區域 2D／3D、側欄三種狀態、查詢前後狀態、釘選、選取、Demo 步驟套用、整數毫秒時鐘 |
| `layout.mjs` | 純 | 格子尺寸公式（§4.1）：`fitTiles({size, width, height, narrow})` → 每格寬高與排列；主要區域與時間列的固定高度常數 |
| `shell-view.mjs` | DOM | 頂欄、圖示列與面板三種狀態、主要區域切換、子畫面容器、時間列位置；`localStorage` 只存側欄常駐或收合 |
| `clock.mjs` | 純＋薄 DOM | `frameIndexAt(t_ms,fps)`、步進、播放迴圈（rAF） |
| `api.mjs` | 純 | 五個端點的請求建構、回應驗證（schema、scope、`gt_read:false`、`identity_verdict`、`agent_used:false`）、fail closed、epoch 丟棄過期回應；fixture 模式讀 `fixtures/*.json`；person-layer 的不確定度驗證呼叫 `uncertainty.mjs` |
| `uncertainty.mjs` | 純 | D44／D45：`composed_ground` 與 `track_height_estimate` 的欄位名常數（照 v1.1 草案 @ `4bfb546`，改名只改這裡）、`validateUncertainty`、`readoutText`（§5.3.1 的格式）、`errorSources`（inspector 的誤差來源清單）、條件中文名 |
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
| R9 | person-layer 每一筆都帶 `composed_ground`（D44，v1.1 草案 §6.3.1），READY 時必有 `geometry.length_m` 或 `polygon_area_m2`，以及 `constraints_used`／`constraints_unavailable`；假設切片帶 `area_m2`。缺的話 v2 整個圖層 fail closed | D45 |
| R8 | 服務測試：白名單外路徑（例如 `/workbench/app.mjs`、`/workbench-v2/../`、symlink）一律 404／403 | 不把目錄當靜態根 |

### 6.5 測試策略

- **node 單元測試**（`node --test frontend/workbench-v2/*.test.mjs`）：
  - `store`：模式機（瀏覽→查找→返回→再進入）、釘選與暫時釘選、Demo 套用、時鐘邊界（`t_ms = 0`、sample 上、sample 之間、`duration − 1`、`OUT_OF_RANGE`）。
  - `store`／`layout`：切換 2D／3D 不改時間、選取、釘選、查詢；側欄三種狀態的轉換（≡、常駐、浮動、收合、Esc、點主要區域）；格子公式在 1440×900 下得到 §4.1 表中的值。
  - `plan-layers`：內插刻度只在同一軌跡兩端有效時出現；跨 MISSING、UNKNOWN、不同軌跡都不出現；盲區切片維持 `INFERRED_HYPOTHESIS`；`HUMANOID` 門檻前後；`FLAGGED` 不移動位置；`raw_*` 不進繪製清單。
  - `timeline-model`：每列區段、點擊命中與優先序。
  - `query`：半開區間、`UNKNOWN` 不轉不相交、`null` 不轉 0、排序依據只用 D28 三鍵。
  - `uncertainty`：fixture 全部通過；刪掉任一 READY 的 `length_m`（且沒有 `polygon_area_m2`）→ `UNCERTAINTY_FIELD_MISSING`；缺 `constraints_used` → 錯誤；未知條件 kind → 錯誤（契約名稱固定五種）；`readoutText` 對 §5.3.1 四個例子輸出一致；`errorSources` 最後一行固定是「設計估計」。
  - `api`：fail closed（schema 不符、`gt_read` 不是 false、scope 不符、完整性錯誤）→ 不回傳任何可畫資料；過期 epoch 丟棄。
  - `inspector`：§6.5 五種 relation 的跳轉規則與距離相等時的穩定排序。
  - `demo`：MOCK／SYNTHETIC 下 PASS 記成 UNKNOWN；匯出紀錄 hash 穩定。
  - 重用檢查：v2 只 import §6.2 列出的舊 export（測試讀 import 陳述式比對白名單），且不 import `app.mjs`、`scene.mjs`。
- **瀏覽器驗收**（Sonnet／medium，先用 fixture 模式，Codex 端點完成後再用真實 run）：
  1. 1440×900，側欄常駐與收合各一輪截圖；核對整頁不捲動、時間列在主要區域正下方、§4.1 的格子尺寸。
  2. 跑完 Demo 1–7 步，每步截圖並對照 §4.3。
  3. 1／2／4／8 切換與 11 台 fixture 分頁；空格不補位。
  4. 停在 sample 上、sample 之間、MISSING、盲區、OUT_OF_RANGE 五個時間點，核對 2D 角標與 3D 刻度。
  5. 點觀測、緞帶、範圍帶、MISSING 段，核對跳轉與側欄。
  6. 載入中、請求失敗、完整性錯誤三種狀態（fixture 注入）。
  7. 色盲模擬（Chrome DevTools Rendering → Emulate vision deficiencies）與灰階截圖，確認五種狀態分得開。
  8. 舊版 `/` 仍可開、行為不變（D35）。
  9. 在 2D 與 3D 之間切換，時間、選取、釘選不變；3D 點擊回溯後子畫面換成支持影格。
- 每個實作任務只跑自己的測試與 `git diff --check`（AGENTS.md）。

### 6.6 任務拆分

建議模型依 CLAUDE.md 表：前端實作 Sonnet／medium，複雜 3D Sonnet／high。同一組檔案一次只有一個寫入者。`app.mjs` 只由 V2-1 建立並預先掛上所有 view 的空殼，之後各任務只改自己的檔案；最後由 V2-9 做整合接線。

| 任務 | 檔案集合 | 依賴 | 模型／effort |
| --- | --- | --- | --- |
| V2-0 | `player-grid.mjs`＋測試＋5 份 fixture | Draft PR #71 @ `2627b89`（另一 session）；等審查 | — |
| V2-1 外框與 token | `index.html`、`style.css`、`tokens.mjs`、`store.mjs`、`clock.mjs`、`layout.mjs`、`shell-view.mjs`、`app.mjs`（含各 view 空殼掛載）、`fonts/`、對應測試（含側欄三狀態、2D／3D 切換、時間列位置） | 本設計核准 | Sonnet／medium |
| V2-2 API、不確定度與 fixture | `api.mjs`、`uncertainty.mjs`、`fixtures/`（不含 #71 的 `synced_frames_*`）、`fixtures/generate_v2_fixtures.mjs`、測試；涵蓋 D44、D45 的欄位（見下方任務卡） | 本設計核准；可與 V2-1 並行 | Sonnet／medium |
| V2-3 2D 格 | `grid-view.mjs`＋測試（依 §6.3 銜接 #71：結構鍵、就地換 `src`、`onPin: null`、外框標頭與 bbox 疊圖） | V2-0（#71）、V2-1、V2-2 | Sonnet／medium |
| V2-4 3D 平面圖 | `plan-layers.mjs`、`plan-view.mjs`＋測試（含約束區間與單格投影兩層、§5.3.1 的不確定度讀數、內插刻度的 ±、切片面積、比例尺、軸、座標讀數、子畫面掛點；D46 提示文字） | V2-1、V2-2；需 R3 | Sonnet／high |
| V2-5 時間軸 | `timeline-model.mjs`、`timeline-view.mjs`＋測試 | V2-1、V2-2 | Sonnet／medium |
| V2-6 查找模式 | `query.mjs`＋測試（3D 地面點多邊形用 V2-4 提供的 `unproject` API） | V2-2、V2-4 | Sonnet／medium |
| V2-7 證據與點擊回溯 | `inspector.mjs`＋測試（含每一個推論的「誤差來源」清單，呼叫 `uncertainty.errorSources`） | V2-2、V2-3、V2-4 | Sonnet／medium |
| V2-8 Demo 模式 | `demo.mjs`、`demo-steps.controlled.json`＋測試（含每步旁白與字幕條；數字由 payload 計算；凍結前只說「設計估計」） | V2-1；步驟內容依 V2-3～V2-7 | Sonnet／medium |
| V2-9 整合接線 | `app.mjs` | V2-1～V2-8 | Sonnet／medium |
| V2-10 瀏覽器驗收 | 不改檔；截圖與結果紀錄 | V2-9、Codex R1–R3、R6 | Sonnet／medium |
| V2-11 獨立審查 | 不改檔 | 每個 PR | Opus／high（小 PR 用 medium） |
| Codex | `service.py` R1–R3、R5、R6、R8；launcher R7；端點 R4 | R1–R3 可與 V2-1 並行 | 使用者決定 |

#### V2-1 任務卡：外框、token、store、時鐘（Sonnet／medium）

- **目標**：做出 §4 的外框骨架，能在瀏覽器打開、切模式、切 2D／3D、切側欄三種狀態、操作時間列；畫面內容（格子、3D、時間軸繪製、面板內容）先是空殼。
- **分支**：`claude/workbench-v2-shell`，base 是整合分支 `claude/office-demo-visualization` 的當下 head（開工前 `git fetch` 確認；本文寫作時是 `f481fe0`）。
- **新增檔案**（都在 `frontend/workbench-v2/`；不碰 #71 的 `player-grid*`、`fixtures/synced_frames_*`）：
  - `index.html`、`style.css`：§4.1 的固定高度（24／44／32／112／28 px）、§4.2 的圖示列 48 px＋面板 300 px、§5.1 的深色 token（只有一套）、§5.2 字體尺寸。字型先用系統字型堆疊；`fonts/` 打包另開小任務（授權檔要一起放）。
  - `tokens.mjs`：§5.3 的編碼表（六種狀態：OBS、INC、INT、HYP、MISS、UNK，加 SYNTHETIC），每項含 token 名、線型、文字碼、符號、圖例文字；另含「±m 不確定度」圖例項。
  - `store.mjs`：單一 state＋純 reducer。至少有 `mode`（browse／find／demo）、`main`（2d／3d）、`rail`（pinned／overlay／rail）、`tMs`（整數毫秒）、`playing`、`speed`（0.5／1／2）、`selection`、`pin`、`tempPin`、`query`、`preQuery`、`demoStep`、`grid`（先放 `null`，由 V2-3 接 #71）。切 `main` 不得改其他欄位。
  - `clock.mjs`：`frameIndexAt(tMs, fps)` 用整數運算；半開區間 `[0, duration_s)`，上限 `duration_s × 1000 − 1`；步進對齊 sample grid；rAF 播放迴圈。
  - `layout.mjs`：§4.1 的 `fitTiles({size, width, height, narrow})`。
  - `shell-view.mjs`：頂欄、圖示列與面板三狀態（≡、常駐／浮動／收合分段鈕、`[`、Esc、浮動時點主要區域會關閉但點擊照常生效）、主要區域標題列（2D／3D 分段鈕、`V` 鍵、格數按鈕、每格像素讀數）、時間列（播放、步進、速度、時間讀數與 `sample_age`）、圖例列（由 `tokens.mjs` 產生）、SYNTHETIC 條、字幕條與阻擋面板的容器。`localStorage` 只存 `rail` 的 pinned／rail，包在 try/catch。
  - `app.mjs`：建立 store、掛載 shell；為 `grid-view.mjs`、`plan-view.mjs`、`timeline-view.mjs`、`inspector.mjs`、`query.mjs`、`demo.mjs` 建立只有 `export function mount(){}` 的空殼檔，讓後續任務各自填。
  - 測試：`tokens.test.mjs`、`store.test.mjs`、`clock.test.mjs`、`layout.test.mjs`（`layout` 要在 1344×643 與 1044×643 得到 §4.1 表中的八個值）。
- **不做**：任何 API 呼叫、2D 格子內容、3D 繪製、時間軸軌道繪製、面板內容、Demo 邏輯。
- **不改**：`frontend/workbench/**`、#71 的檔案、`service.py`、launcher、任何資產。
- **驗收**：`node --test frontend/workbench-v2/{tokens,store,clock,layout}.test.mjs` 全過；`git diff --check`；在 1440×900 用任一靜態伺服器打開 `index.html`（只為看版面，不接後端）截一張圖，確認整頁不捲動、時間列在主要區域正下方。
- **紀錄**：PR 描述與 issue 留言用 AGENTS.md 的「實際產出」範本；Draft PR，base 為整合分支，不合併。

#### V2-2 任務卡：API、不確定度驗證、SYNTHETIC fixture（Sonnet／medium）

- **目標**：v2 讀資料的唯一入口，以及 D44、D45 需要的欄位驗證與文字；附可重現的 SYNTHETIC fixture，讓 V2-3～V2-8 在 Codex 端點完成前就能開發。
- **分支**：`claude/workbench-v2-api`，base 同 V2-1；與 V2-1 檔案不重疊，可並行。
- **新增檔案**（`frontend/workbench-v2/`）：
  - `api.mjs`：五個端點（契約 §6.1–§6.5）的請求建構與回應驗證。驗證失敗一律 fail closed，回 `{ok:false, error:{code, message, ref?}}`，不回任何可畫資料。至少檢查：`schema_version`、`resolved_scope` 與目前 run／clock 相符、`provenance.gt_read === false`、`identity_verdict === "UNCONFIRMED"`、`agent_used === false`、完整性錯誤形狀（暫用 #71 fixture 的 `{"error":{"error_class":"DataIntegrityError","reason":…}}`，也接受 `error.code`；R5）。過期請求用 epoch 丟棄。`fixture` 模式從 `./fixtures/` 讀檔並在結果標 `data_origin: "SYNTHETIC_FIXTURE"`。同步影格只提供原始的 `syncedFrames(request)`（送出與接收 JSON）；請求建構與 display model 由 V2-3 用 #71 的 `buildSyncedFramesRequest`／`toDisplayModel` 組合。V2-2 不 import `player-grid.mjs`（#71 尚未合併進整合分支），也不複製它的程式。
  - `uncertainty.mjs`：
    - 欄位名常數，照契約 v1.1 草案 @ `4bfb546` §3.12、§6.3.1：`composed_ground`、`status`、`evidence_state`（`INFERRED_CONSTRAINED`）、`foot_status`、`geometry.{kind, near_m, far_m, length_m, polygon_m, polygon_area_m2}`、`constraints_used[].{kind, source_ref, source_sha256, values}`、`constraints_unavailable[].{kind, reason}`、`track_height_estimate.{status, height_m, uncertainty.{lower_m, upper_m}, temporal_scope, n_support_frames}`。草案改名時只改這裡。
    - `validateUncertainty(personLayer)`：每一筆 READY 的 `composed_ground` 必須有有限的 `geometry.length_m` 或 `polygon_area_m2`，且有兩個條件陣列；條件 `kind` 只能是 `prior`、`track_height`、`occlusion_near`、`lowest_visible_far`、`speed`。不符回 `{code: "UNCERTAINTY_FIELD_MISSING" | "UNKNOWN_CONSTRAINT_KIND" | …, estimate_ref, field}`。
    - `readoutText(estimate)`：§5.3.1 的格式（`±半長 m（條件＋條件）`；腳看得到時加「腳點像素帶」；不列 `lowest_visible_far`；POLYGON 用面積）。
    - `errorSources(estimate)`：§5.3.1 的清單，最後一行固定「設計估計：輸出凍結前沒有以 GT 驗證」。
    - `connectorUncertainty(a, b)`：兩端半長的較大者（內插沒有獨立欄位，§9）。
  - `fixtures/generate_v2_fixtures.mjs`：以 node 執行、輸出確定的 JSON。移植 `docs/agents/assets/workbench-v2-mockup-v3.html` 的 SYNTHETIC generator（場景、四台鏡頭、事件 A／B1、局部軌跡、`composed_ground`、K1 範圍帶與負證據）；**UI 端程式不得 import generator**。
  - `fixtures/`：`candidate_cameras_{A,B1}.json`、`person_layer_{A,B1}.json`、`curve_layer_{A,B1}.json`、`evidence_lookup_B1_*.json`、`blind_hypothesis_B1.json`，以及刻意壞掉的 `person_layer_missing_uncertainty.json`、`person_layer_gt_read_true.json`。每份最上層有 `"SYNTHETIC"` 說明與 `data_origin: "SYNTHETIC_FIXTURE"`；所有數值都是 SYNTHETIC。不得寫入或覆寫 #71 的 `synced_frames_*.json`。
  - 測試：`api.test.mjs`、`uncertainty.test.mjs`（§6.5 列的情況），以及「重新執行 generator 得到相同的檔案 hash」。
- **不做**：任何 DOM、繪製、服務端程式。
- **不改**：同 V2-1。
- **驗收**：`node --test frontend/workbench-v2/{api,uncertainty}.test.mjs` 全過；`node frontend/workbench-v2/fixtures/generate_v2_fixtures.mjs --check` 與已提交檔案一致；`git diff --check`。
- **紀錄**：同 V2-1。另列出 fixture 檔清單與每份 SHA-256。


並行建議：V2-1 與 V2-2 同時；之後 V2-3、V2-4、V2-5 三個同時（檔案不重疊）；再來 V2-6、V2-7、V2-8；最後 V2-9、V2-10。依記憶中的限制，同時寫入的 session 最多 2 個，各自在 scratchpad clone 裡做。

### 6.7 AGENTS.md「primary UI」那一句

D35 已決定「新版驗收後再另外改」。建議在 v2 驗收檢查點核准後，把：

> Use `frontend/workbench/` as the primary UI.

改成：

> Use `frontend/workbench-v2/` as the primary UI for the controlled-scene demo. `frontend/workbench/` stays unchanged as the fallback UI and for legacy Office runs (D35); do not delete or restyle it.

同時要一起核對的地方：`CLAUDE.md` 對 Claude 職責的描述（「all workbench visualization」不需改）、`docs/operations/CLAUDE_INITIAL_HANDOFF.md` 與 `docs/agents/OFFICE_DEMO_SCRIPT.md` 中指向舊工作台的操作步驟（本次未讀，列為 UNKNOWN）。

## 7. 需要使用者決定的題目

Q2、Q3 已依使用者第 2 版意見關閉。Q1、Q4–Q10 由 **D43** 決定：全部照建議，§7.1 的解讀一併接受。

| 題 | 狀態 | 問題 | 建議 | 風險 | 代價 |
| --- | --- | --- | --- | --- | --- |
| Q1 | **已決定（D43）** | §2 的捨棄項 X1–X10 是否全部核准（v2 不做，舊版保留）？可以逐項改成「v2 也要」 | **全部核准** | Demo 中要看舊 Office 功能時得切到舊版（頂欄有入口） | 每保留一項，多一個 Sonnet 任務（約 0.5–1 天）；X6、X7 還要等新場景有對應契約 |
| Q2 | **已關閉（U2）** | 預設主題 | 使用者：「系統顏色先固定深色即可，不用切換」→ 只有深色 | — | 只維護一套 token |
| Q3 | **已關閉（U3）** | 2D 與 3D 的關係 | 使用者：「2D 3D 顯示使用切換」→ 同一主要區域切換，保留時間與選取 | 失去同時對照 → 以 3D 子畫面補（見 Q9） | — |
| Q4 | **已決定（D43）** | 接地品質 FLAGGED 的 3D 樣式 | **空心實線，不加虛線**（舊版是空心＋虛線） | 新舊版樣式不同 | 只在 v2 覆寫樣式；狀態判斷仍重用 `contactQualityStyle` |
| Q5 | **已決定（D43）** | 「物理曲線用虛線」的解讀 | **任何跨 sample 的路徑都是短虛線緞帶；K8c 物理可達只用檢查結果徽章，不另畫一條線** | 若使用者原意是另一種「物理路徑」圖層，要再加一種線型 | 若要另畫：多一種線型（建議點劃線、石墨色），再做一次色盲檢查 |
| Q6 | **已決定（D43）** | Demo 步驟組 | **採 §4.3 七步，取代 D24**；每步指定 2D 或 3D | 步驟 3、6 依賴 Codex 的局部軌跡（CS-Q10）；沒有時這兩步是 UNAVAILABLE | 無額外成本 |
| Q7 | **已決定（D43）** | SYNTHETIC 與 FIXTURE 的用詞 | **兩個都用**：整個資料來源是 fixture 時頂部 SYNTHETIC 條；單一鏡頭／影格是 UI fixture 時格子角標 FIXTURE | 兩個詞可能讓人以為是兩種東西 | 文案說明一次即可 |
| Q8 | **已決定（D43）** | 實作派工 | **照 §6.6，先開 V2-1、V2-2 兩個 session** | V2-4（3D）若 R3 未到，Line2 無法載入 → 先用 1 px 線寫邏輯 | 依 CLAUDE.md 表選模型 |
| Q9 | **已決定（D43）** | 3D 子畫面（右下角顯示第 1 格鏡頭）要不要保留 | **保留，預設開啟，可關** | 蓋住 3D 右下角一小塊 | V2-4 多一個掛點；子畫面用同一個 2D view，不另開資料 |
| Q10 | **已決定（D43）** | 側欄要不要有第三種狀態「浮動」 | **保留**：常駐、浮動、收合三種 | 三種狀態比兩種多一點學習成本 | 只有 `shell-view.mjs` 的狀態機 |

**第 3 版新增的使用者決定：**

| 決定 | 使用者原話或內容 | 本文的處理 |
| --- | --- | --- |
| D45 | 「估計誤差要明確標出（文件內和demo時都要說）」 | §5.3.1 讀數與誤差來源；§4.3 每步旁白與字幕條；§4.5 缺欄位＝阻擋錯誤；§6.6 V2-2、V2-4、V2-7、V2-8 |
| D46 | 3D 人物只顯示從 2D 重現的結果，看得到的區段也一樣；不讀 GT、不做 GT 對照圖層 | §1 原則 9、§2 F28、§5.5 人物圖層與子畫面 |
| D44 | 接地區間納入遮擋邊界、軌跡身高、速度界；每格帶條件與不確定度 | 欄位照契約 v1.1 草案 @ `4bfb546`；§5.3 新增 INC；§6.1 `uncertainty.mjs` |

### 7.1 解讀與使用者原話可能不同的地方（第 2 版，已由 D43 接受）

1. **Scientific Investigation Console**：解讀成冷靜的科學儀器（單色外框、等寬讀數、比例尺、座標讀數、角落定位框），**不是**發光的科幻 HUD。若使用者要的是更強烈的控制台感（例如霓虹、掃描線），要另外說明。
2. **「是否常駐顯示或是縮放」**：做成三種狀態。「常駐」＝面板常開並讓出寬度；「縮放」解讀成「收合成圖示列」；另外加了「浮動」（面板暫時蓋在畫面上、不改寬度），這一項是我加的（Q10）。
3. **「速度相關調整應在相對應畫面最下方」**：2D 和 3D 共用同一條時間列，放在主要區域正下方；因為兩者是切換的，同一位置就是「對應畫面」的最下方。沒有做成每個畫面各一條。
4. **2D 放大的程度**：以「主要區域盡量給畫面」為準，4 格從約 284×160 放大到 491×276 px（1440×900）。若要更大，只能縮小時間列或圖例列。
5. **3D 子畫面**：使用者沒有要求；是為了彌補「切換後無法同時對照」而加的（Q9）。
6. **點擊回溯不自動切到 2D**：在 3D 點證據時，留在 3D，子畫面換成支持影格；要看大圖按「在 2D 查看此影格」。Demo 步驟則會依步驟自動切換 2D／3D。
7. **模式切換同時出現在頂欄和圖示列**：頂欄保留「瀏覽／查找／Demo」，圖示列的「查找」「Demo」是同一個動作的捷徑。

### 7.2 第 3 版的解讀（請確認）

1. **讀數格式**：使用者例子有「±0.27 m（先驗）」與「0.22 m（軌跡身高）」兩種寫法。本文統一成「±半長 m（條件）」，全長只在 inspector 顯示。若要改成全長，只改 `readoutText`。
2. **約束區間是推論**：照 v1.1 草案，`composed_ground` 的 evidence state 是推論（`INFERRED_CONSTRAINED`），所以 3D 的主圖層從第 1 版的「觀測色實線」改成「琥珀空心條」；原 `ground_estimate`（觀測）改為細線追溯層。這和 UX 草圖 §5.1 不同；草案本身也寫明前端畫法待 Codex 確認後修訂。
3. **缺不確定度＝整個 run 阻擋**：使用者說「顯示為完整性錯誤」，本文比照完整性錯誤，整個 run 停止顯示。也可以只阻擋 person／curve 圖層、保留 2D 影格；若要這樣，只改 §4.5 一列。
4. **Demo 旁白**：每一步一句，同時放在面板與字幕條。數字由 payload 計算；凍結前只說「設計估計」。
5. **mockup 的軌跡身高用 CAUSAL**：為了在同一場景同時展示「先驗」與「軌跡身高」，mockup 只用當格以前的影格估身高；草案建議 `WHOLE_TRACK`，等 Codex 確認（CS-Q15）。正式版照契約。

## 8. Mockup 說明

- 網址：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>（私人），目前是 Version 3（Version 1、2 是前兩版，同一網址的版本紀錄）。頁面最上方有 SYNTHETIC 條與「設計 mockup 第 3 版，非真實資料」。原始檔：`docs/agents/assets/workbench-v2-mockup-v3.html`。
- 第 3 版新增：3D 約束區間（琥珀空心條）與單格投影細線兩層、不確定度讀數、內插刻度的 ±、切片面積的來源；inspector 的「誤差來源」；Demo 每步旁白與字幕條；圖例的「±m」說明；「狀態示範 → 缺不確定度欄位」會跑真的驗證函式並顯示阻擋面板；3D 提示文字寫 D46。fixture 的 `composed_ground`、`track_height_estimate` 欄位照契約 v1.1 草案，數值都是 SYNTHETIC。
- 可以操作：事件 A／B1、瀏覽／查找／Demo、2D／3D 切換（`V`）、側欄常駐／浮動／收合（≡、`[`、Esc）、1／2／4／8 格（標題列顯示每格像素）、時間列上的播放與拖曳時間、步進、速度、3D 子畫面、3D 游標座標讀數、在 3D 地面畫多邊形查詢、點 3D 區間／緞帶／範圍帶、點 2D 框、點時間軸曲線列、釘選、11 台 fixture 分頁、Demo 數字鍵 1–7 與匯出紀錄、「狀態示範」切換載入中／請求失敗／完整性錯誤。
- 資料：頁內的 generator 只用來產生 SYNTHETIC payload（形狀照契約 §6）；UI 程式只讀 payload，不讀 generator 的人物與路線，和正式系統與 GT 的邊界相同。
- 和正式設計的差異（mockup 的簡化）：
  - 3D 用自寫的 canvas 正交投影，不是 three.js；材質、光線、圖層順序照 §5.5。
  - 2D 影格是簡化的針孔投影示意圖，不是渲染。
  - 字型從 Google Fonts 載入（Artifact 限制）；正式版本機打包。
  - 候選鏡頭的「可見範圍索引」用契約 §5.1 的名義地面視野；盲區負證據改用「人站在這格會不會被偵測」的靜態可偵測性。兩者不一致，正好說明契約 §5.1「地面看不到不能證明人看不到」的問題。
  - fixture 會出現的現象：事件 A 的第 0 張沒有任何鏡頭偵測到人；W1 前幾張與 W2、N1 近端的腳出框，單格投影是 UNKNOWN，但約束區間由身高先驗或軌跡身高給出（D44）。這是照契約 §5.1 的名義鏡頭位置算出來的，對應 §5.2「近端出框風險」，不是 bug。
  - 曲線列中「只有約束區間、沒有單格投影」的時段，在契約 §6.4 沒有對應的 kind；mockup 由 person-layer 推導（`UI_CONSTRAINED_SPAN`；全部條件失效時是 `UI_UNKNOWN_SPAN`），見 §9。
  - 2D 格子在 mockup 裡用頁內的簡化邏輯排版，沒有 import #71；格子狀態（READY／MISSING／OUT_OF_RANGE／UNKNOWN）、空格「無更多候選」、釘選只改版面、分頁，這些語意都和 #71 的 `pageView`／`toDisplayModel` 一致。正式版改用 #71。

## 9. 契約與介面待釐清（UNKNOWN）

1. **曲線的 UNKNOWN 段**（第 3 版更新：見第 10 點）：§6.4 的 segment kind 只有 OBSERVED、INFERRED_CONNECTOR、BLIND_HYPOTHESIS、MISSING_GAP。一條局部軌跡中「有偵測但接地 UNKNOWN」的時段沒有 kind。建議契約加 `UNKNOWN_GAP`（`evidence_state: UNKNOWN`、`reason`），點擊回 `NO_SUPPORT`。
2. **負證據影格清單的欄位**：§6.5 說盲區假設要「列出兩端觀測與負證據影格」，但回應範例沒有欄位。需要 `negative_evidence[]: {camera_id, frame_ref, timestamp_s, state: NO_DETECTION|DETECTION_PRESENT, used}`。
3. **完整性錯誤的回應形狀**（R5）：#71 已用假設形狀寫 fixture，契約仍未定義。
4. **假設回應的 schema**：是否沿用 `workbench.blind-hypothesis.v1`（§6.2）。
5. **同步影格的 media URL 形式**（R4）。
6. **size=1＋釘選的翻頁行為**：#71 列為 UNKNOWN；本設計同意它的實作（釘選鏡頭在第 1 頁，其餘依序翻頁），等使用者確認。
7. `HUMANOID_DISPLAY_MAX_INTERVAL_M` 與所有門檻：CS-Q9 OPEN；mockup 用 0.6 m 只是示意。
8. `docs/operations/CLAUDE_INITIAL_HANDOFF.md`、`docs/agents/OFFICE_DEMO_SCRIPT.md` 中指向舊工作台的段落：本次未讀。
9. **`INFERRED_CONSTRAINED` 這個名稱**與 `composed_ground` 全部欄位：v1.1 草案，等 Codex 確認（CS-Q15）。
10. **曲線圖層與約束區間**：§6.4 的 OBSERVED 段是單格投影的序列；只有 `composed_ground` 的時段要用什麼 kind、連接緞帶要用哪一種幾何，契約沒寫。mockup 用 `composed_ground` 畫緞帶。
11. **內插與盲區的不確定度欄位**：內插沒有自己的欄位（v2 取兩端較大者）；盲區切片只有 `area_m2`。是否要在契約加明確欄位，待 Codex 回覆。

## 10. 實際產出 / Actual output

- Model / effort: Claude Opus 5.5（`claude-opus-5-5`）／ high
- PR / commits: [#72](https://github.com/Polalalabear/amidst/pull/72)：`3fadccc`（第 1 版）→ `8d78094`（接 #71）→ `55b1ae1`（第 2 版）→ 本版（第 3 版，SHA 見 PR 留言）。沒有 rebase
- Files changed: `docs/agents/WORKBENCH_V2_DESIGN_20261018.md`；`docs/agents/assets/workbench-v2-mockup-v3.html`（第 3 版 mockup 原始檔，供 V2-2 移植 generator）
- Commands run and results:
  - 唯讀盤點：`git show origin/claude/office-demo-visualization:<path>`、`git show 2643771:<path>`、`git show 2627b89:frontend/workbench-v2/<path>`（#71）、`git show 4bfb546:docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`（v1.1 草案 §3.12、§6.3.1）。
  - 第 3 版 mockup：`node --check` 通過；fixture generator 在 node 執行一次：事件 A 56 筆估計、`composed_ground` READY 56 筆，半長 ±0.04–0.31 m；B1 124 筆、READY 124 筆，半長 ±0.04–0.31 m；條件組合在兩個事件都出現「腳點像素帶（＋速度界）」「先驗＋最低可見點（＋速度界）」「軌跡身高＋最低可見點（＋速度界）」；盲區 8.8–13.6 s、25 個切片皆非空（0.06–10.94 m²）。
  - 內建瀏覽器 1440×900 預覽一次（Demo 第 3 步，3D）：無 console 錯誤；約束區間、不確定度讀數、內插刻度的 ±、子畫面（右上）、字幕條旁白都有畫出。
- Artifacts:
  - mockup Artifact：<https://claude.ai/artifact/WRndShxKd4V5BKFFinPj7h>（Version 3）
  - 第 3 版原始檔：`docs/agents/assets/workbench-v2-mockup-v3.html`，113,777 bytes，SHA-256 `7d18fd379515bd6108d6b5894d0f42926d3e47221b1bc51966f0c6e2069fca7b`
  - 第 2 版原始檔：LOCAL，99,818 bytes，SHA-256 `c1bb95519543b643bdf21fb659b559ebf35ef92b4028af0dad37fb793fcb3e1e`；第 1 版：LOCAL，91,398 bytes，SHA-256 `e1b3bf8ece8ba36ed9fc04a778dafb9e8e2495e1891fe2771f7e21fb8aa713e4`
- Verified: 矩陣的模組與 export 名稱對照整合分支 @ `f481fe0`；`app.mjs:1515` 會在 import 時啟動；§6.3 對照 #71 @ `2627b89`；D44 欄位名對照契約 v1.1 草案 @ `4bfb546`；4 格常駐的格子尺寸在 mockup 實測（第 2 版）。
- Not verified: 第 3 版只截了一張 3D 圖；「缺不確定度欄位」阻擋面板、inspector 誤差來源、2D 畫面、側欄收合與浮動沒有截圖；色盲模擬與窄螢幕沒有實際檢查（列入 V2-1、V2-10）；v1.1 是草案，欄位名可能改；沒有跑任何測試（未改程式）。
- Deviations, UNKNOWN items and follow-ups: §7.2 列 5 點第 3 版解讀；§9 共 11 項待釐清；V2-1、V2-2 任務卡在 §6.6。
