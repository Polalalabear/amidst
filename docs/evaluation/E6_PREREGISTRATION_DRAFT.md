# E6 預先登記草稿與新劇本規格（去錨定／結構化歷史／摘要，D377）

- **狀態**：草稿（第 1 批送審，尚未凍結；須經 Codex 互審與 Claude 第 1 批審查合併後，方由 #721 依合併版實作）。
- **依據**：D377（[#93 留言 7134281394](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7134281394)）；E6 計畫 `docs/evaluation/E6_PLAN_20261124.md`（PR #722，`claude/docs-handoff-20261124b`）；`docs/evaluation/E5_PREREGISTRATION_20261123.md`；`docs/operations/E5_REPORT_20261123.md`；`docs/operations/F4_E3_REPORT_658.md`；[#684 2026-11-24 兩則事後檢查留言](https://github.com/Polalalabear/amidst/issues/684#issuecomment-7133185638)（**均為事後描述、未預登、未第二人核對，不改 E3／E5 判定**）。
- **硬性邊界**：
  - 身分一律 `UNCONFIRMED`；「對」只表示顯示框或估計位置落在 GT 目標上。
  - GT、渲染軌跡、visibility、depth、劇本關鍵影格**只進評分端**，嚴禁進入推論、排序、提示或選組輸入。
  - 原 E3（H1／H2／H4 不成立）與 E5（H8a／H8b／H8d 不成立、H8c 無法判斷）之正式判定與 `src/amidst/evaluation/e3_scoring.py`（SHA-256 `acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08`）**完全不改動**；E6 另寫獨立判定函式 `verdict_e6`。
  - 任何付費呼叫、外傳影格、換 pin、複製 3D 資產與刪檔皆不在本草稿授權內，須另行經使用者核准並先執行 `ApiGuard` dry-run。
  - **不得偷看新資料輸出**：正式 12 段之決策點與 GT 須在錄製後、任何組別執行前釘 SHA；批 3 凍結選組設定前，嚴禁評分或檢視正式 12 段任何組的輸出。

---

## 0. 背景、與 E3／E5 的關係及凍結時點

1. **為何需要 E6**：
   - E3（`F4_E3_REPORT_658.md`:9–12）與 E5（`E5_REPORT_20261123.md`:13–16）在舊 16 段困難劇本上，無論依附規則整合（A2 錯人秒差 +129.8 s [36.2, 218.5]）或完全開放 A-open（AO 錯人秒差 +129.1 s [55.2, 193.1]、盲區誤鎖秒差 +65.5 s [39.7, 91.3]）皆判不成立。
   - #684 2026-11-24 兩則事後檢查留言（**事後描述、未預登、未第二人核對**，[留言 7133185638](https://github.com/Polalalabear/amidst/issues/684#issuecomment-7133185638)、[留言 7133303522](https://github.com/Polalalabear/amidst/issues/684#issuecomment-7133303522)）觀察到三項線索：(a) 舊 16 段僅源於 2 個開頭家族（A4 系 7 段、B4 系 9 段，其中 B4 系 7 段共用 14–21 s 開頭）；(b) 錯誤高度集中在相似人物同時可見或目標不可見時；(c) AO 跟錯狀態下多數維持同一錯人（K=3 合計 254 次維持同一錯人 vs 34 次換回目標），若歷史將未驗證的自我回答當成事實，可能放大錨定。
   - 上述 #684 觀察僅用於提出 E6 假設與新劇本設計，**不得引用為正式結論**；去錨定、結構化歷史與短摘要是否改善追蹤，必須在**完全分離的 12 段新劇本**上以預先登記的統計檢定驗證。
2. **四批審查與凍結時點（D377）**：
   - **批 1（本文件）**：#717（舊 16 段逐事件答案表與 R-N）、#718（本預登與 12 段劇本規格）、#719、#720、#722 合併後，方得啟動 #721 實作。
   - **批 2**：#721 實作、離線測試、dry-run；新 12 段錄製並凍結 `case.json` 與 GT sidecar SHA-256（寫回 `configs/evaluation/e6_scenarios_spec_v1.json` 並通過 `check_e6_data_separation.py`）。經使用者同意外傳與付費後，始得跑 **3 段診斷資料**。
   - **批 3（凍結閘門）**：依 §2.2 寫死之選組規則在 3 段診斷資料上選出並凍結單一 Agent 組（`SELECTED_AGENT`）及全部 prompt／參數 SHA。批 3 審查通過並經使用者同意後，始得執行並評分 **正式 12 段**。
   - **批 4**：正式 12 段評分、報告與（若預算允許）條件消融／模擬即時 K=1。
   - **本文件第 3、4、5 節（指標、檢定、Holm、容許值、選組規則、資料分離）於批 1 合併後即鎖定**；任何看過診斷或正式分數後的改動皆視為偏離，須依 E3 §9 雙版報告且正式判定只採凍結版。

---

## 1. 假設

所有差值一律定義為 $\Delta = \text{Agent} - \text{Reference}$（錯人秒與盲區誤鎖秒越低越好；跟對率與決策點正確率越高越好）。

### 1.1 主要假設（2 個，整體套用 Holm 校正）

| 編號 | 比較組別 | 研究問題 |
| --- | --- | --- |
| **P1** | `DEANCHOR` vs `AO_ORIG` | 去錨定設計（將歷史分開 `SELF_ANSWER_UNVERIFIED` 與 `SYSTEM_OBSERVED`，且每次比對原始參考截圖）相較於原 E5 `AO_ORIG`，在正式 12 段上能否顯著降低錯人秒、不劣化跟對率、提高固定決策點正確率、且盲區誤鎖秒差不超過容許值？ |
| **P2** | `SELECTED_AGENT` vs `B1` | 於 3 段診斷資料上依 §2.2 預先選定並凍結的單一 Agent 組，在正式 12 段上能否優於現有規則系統 `B1`（核心目的）？ |

- 若 **P2** 判「不成立」或「無法判斷」，報告**必須**照實寫明：「改良後仍未證實優於現有規則」。
- P1 與 P2 皆以正式 12 段（$M$ 個獨立劇本家族、$N_{\text{dp}} \ge 40$ 個固定決策點）判定，絕不使用舊 16 段或 3 段診斷資料作為判定樣本。

### 1.2 次要假設與機制分析（不納入 P1／P2 Holm 校正，單獨標明「次要／探索性」）

| 編號 | 比較組別 | 目的與解讀限制 |
| --- | --- | --- |
| **S1（歷史效果）** | `DEANCHOR_HIST` vs `DEANCHOR` | 檢視加入腳本維護之結構化歷史（區分 `SELF_ANSWER_UNVERIFIED` 與 `SYSTEM_OBSERVED`）的邊際效果 |
| **S2（摘要效果）** | `DEANCHOR_HIST_SUM` vs `DEANCHOR_HIST` | 檢視加入帶來源引用短摘要的邊際效果 |
| **S3（共同底座機制）** | Agent 各組 vs `R-N` | 在共同中性追蹤器底座上比較決策品質；**結論只能寫「在中性追蹤器底座上」，勝過 R-N 不得宣稱優於現有規則 B1** |
| **S4（去錨定機制）** | `DEANCHOR` vs `AO_ORIG` | 觀察「跟錯狀態下維持同一錯人比例」（`same_wrong_persistence_rate`）、失聯／不顯示秒、重新出現點 top-1／top-3 |
| **S5（較嚴盲區準則）** | P1、P2 各自比較 | 沿用 E5 H8b（`E5_PREREGISTRATION_20261123.md`:94–98）之較嚴次要判定：盲區誤鎖秒差校正區間整個 $< 0$ |
| **S6（條件消融與延遲）** | 僅針對凍結後之 `SELECTED_AGENT` | **預算允許才做**：(a) 無影像 `NO_IMAGE`、(b) 無空間資訊 `NO_SPATIAL`、(c) 模擬即時 `SIMLIVE_K1`（K=1，與延遲 0 離線版並列；真 LIVE 不做）。**嚴禁看完正式結果再挑組消融** |

---

## 2. 分組、R-N 對照與先選後測（Select-then-Test）

### 2.1 實驗組別

| 組別代碼 | 說明 | 參數／資源設定 | 參與階段 |
| --- | --- | --- | --- |
| **B1**（必留） | 現有規則基線（LIVE 路徑：RT-DETR＋HSV＋規則閘門，預設參數；確定性程式，零模型費用） | 固定與 E3 相同參數，**不得於看到新資料後改參數** | 診斷（已有紀錄）＋正式 12 段（必跑） |
| **R-N**（次要） | 規則決策＋中性追蹤器（E6_PLAN「R-N 規格」：同種子 tick、POLL 2.0 s、LOST_EARLY 1.0 s、NeutralTracker IoU 0.3／滑行 2 tick／遮擋 10 tick、無合格候選主版 `UNCERTAIN`、敏感度版 `NOT_VISIBLE`） | 確定性程式，零模型費用；不得於看到新資料後改參數 | 診斷＋正式 12 段（機制對照） |
| **AO_ORIG** | 目前 E5 A-open（`gpt-6.1-terra`、poll 2.0 s、min_interval 1.0 s、呼叫上限 $\lceil T / 2.0 \times 1.5 \rceil$、中性追蹤器、`E5_EXTRA` 提示） | 與 E5 相同（`E5_PREREGISTRATION_20261123.md`:56–64） | 診斷（已有紀錄）＋正式 12 段（P1 對照組，K=3） |
| **DEANCHOR** | 去錨定 A-open：提示與輸入結構明確標示前次答案為 `SELF_ANSWER_UNVERIFIED`，不把前次追蹤框當成真值；每次提問必附原始種子參考截圖並要求獨立比對 | 同 AO_ORIG 資源上限；**一次只改去錨定因素** | 診斷（K=1）＋正式 12 段（P1 受測組，K=3） |
| **DEANCHOR_HIST** | `DEANCHOR`＋腳本維護之結構化歷史（嚴格分開 `SYSTEM_OBSERVED` 與 `SELF_ANSWER_UNVERIFIED` 欄位） | 同上；一次只疊加結構化歷史 | 診斷（K=1）；若被選中或預算允許則進正式 12 段 |
| **DEANCHOR_HIST_SUM** | `DEANCHOR_HIST`＋Agent 產出帶來源引用（tick／camera／detection_id）之短摘要 | 同上；一次只疊加短摘要 | 診斷（K=1）；若被選中或預算允許則進正式 12 段 |

### 2.2 先選後測：開發資料選組規則（寫死，批 3 凍結）

3 段診斷資料樣本極小，選組結果高度不穩定，**不得將診斷資料上的表現差解讀為勝負**。選組規則如下：

1. **候選池**：`{DEANCHOR, DEANCHOR_HIST, DEANCHOR_HIST_SUM}`。
2. **硬篩選（資格閘門）**：於 3 段診斷資料上，須同時滿足格式退回率 $\le 20\%$、provider 錯誤率 $\le 10\%$、GT 隔離違規 $= 0$。若三組皆未通過，中止並修復實作，不得進入批 3。
3. **確定性排序（逐層比較，平手取較簡單組）**：
   - **第 1 順位**：3 段合計**錯人秒**最低者勝。若兩組差距 $\le 1.0\text{ s}$，視為平手，進入第 2 順位。
   - **第 2 順位**：3 段合計**盲區誤鎖秒**最低者勝。若差距 $\le 1.0\text{ s}$，視為平手，進入第 3 順位。
   - **第 3 順位**：3 段平均**跟對率**最高者勝。若差距 $\le 0.01$，視為平手，進入第 4 順位。
   - **第 4 順位（平手取較簡單的組）**：依複雜度由簡至繁優先順序 **`DEANCHOR` > `DEANCHOR_HIST` > `DEANCHOR_HIST_SUM`** 選定。
4. **凍結**：選出單一組作為 `SELECTED_AGENT`，將其程式碼 commit SHA、prompt 檔案 SHA-256、參數 JSON 與 dry-run 估費寫入批 3 凍結紀錄；批 3 審查通過後，方得啟動正式 12 段實驗。若 `SELECTED_AGENT` 恰好為 `DEANCHOR`，則正式 12 段僅須跑 `AO_ORIG` 與 `DEANCHOR`（加零付費 `B1`、`R-N`），可節省正式預算；若 `SELECTED_AGENT` 為 `DEANCHOR_HIST` 或 `DEANCHOR_HIST_SUM`，正式 12 段須跑 `AO_ORIG`、`DEANCHOR`（支撐 P1）與 `SELECTED_AGENT`（支撐 P2），三組合計費用須控制在正式上限 USD 32 內（以 dry-run 為準）。

---

## 3. 指標與固定決策點單次配對

### 3.1 完整追蹤指標（沿用 `e3_scoring.py` 單 tick 定義）

- 框判定主準則：框中心在 GT 身體框內或 $\text{IoU} \ge 0.3$；IoU 保守準則（$\text{IoU} \ge 0.3$）必另報穩健性（同 `E5_PREREGISTRATION_20261123.md`:79）。
- **錯人秒**（`wrong_person_s`）：GT 可見時顯示錯人或錯鏡頭之總秒數（5 Hz，每 tick 0.2 s）。
- **跟對率**（`follow_rate`）：`CORRECT_ticks / GT_visible_ticks`。
- **盲區誤鎖秒**（`blind_false_lock_s`）：目標於全 8 台鏡頭皆不可見（GT blind）時，系統仍顯示鎖定他人的總秒數。
- **失聯／不顯示秒**（`lost_s`）：GT 可見時系統未顯示目標之總秒數，**必另報**，避免靠大幅提高不顯示時間壓低錯人秒。
- **固定決策點正確率（完整追蹤，`full_track_dp_acc`，為 §4.2 元件 C3 之唯一主終點）**：對每個凍結固定決策點 $t_{\text{dp}}$（評估窗 $[t_{\text{dp}}, t_{\text{dp}} + 3.0\text{ s}]$），依錄製後由 Chrome GT 凍結之 `gt_regime` 採用下表判分（Agent 組 K=3 逐點取多數決，B1／R-N 為 K=1 確定性輸出）。API 錯誤、逾時或格式退回一律計為錯誤，不排除於分母之外。

### 3.2 固定決策點單次配對（`single_dp_acc`，獨立次要診斷，不併入 C3）

- E3／E5 中，AO 的提問時點由其自身追蹤狀態決定，與規則並非配對設計（#684 2026-11-24 留言 7133185638，未預登、未核對）。
- E6 正式 12 段增設**單次決策配對驗收**（與完整追蹤分開報告，**不併入 C3 主判定**）：
  1. **決策點與 K 值寫死**：沿用批 2 由 Chrome GT 凍結並釘 SHA 之同一批唯一決策點（$N_{\text{dp}} \ge 40$），規則轉接層與各 Agent 組皆固定跑 **K=1** 單次回答（零重試）。
  2. **共用先驗快照生成方式寫死**：在每個固定決策點 $t_{\text{dp}}$，所有組別讀取**同一份確定性凍結快照**——由 `R-N` 主版本（`UNCERTAIN` 變體）在 $t_{\text{dp}}$ 前一 tick 產出之中性追蹤狀態（僅含 `last_known_cam`、`last_known_xy`、`lost_ticks`、`last_box_xyxy`、`frozen_detections_at_t_dp`、`frozen_rgb_at_t_dp`、`seed_reference_crop`，**嚴禁包含任何 GT 欄位**）。
  3. **完整判分真值表（完整追蹤與單次配對共用三種 GT 情境；`e3_scoring.py` 本體不改）**：

| `gt_regime`（由 Chrome GT 決定） | 完整追蹤窗 $[t_{\text{dp}}, t_{\text{dp}} + 3.0\text{ s}]$（**C3 主終點**） | 單次配對回答（於 $t_{\text{dp}}$，**次要診斷**） |
| --- | --- | --- |
| **`VISIBLE`**（窗內至少 1 tick 目標可見；單次配對為 $t_{\text{dp}}$ 可見） | **對**：窗內至少 1 個 `CORRECT` tick（主準則：框中心在 GT 身體框內或 $\text{IoU} \ge 0.3$）**且** 0 個錯人／錯鏡頭 tick；否則 **錯**（同 E3／E5） | **對**：`SELECT` 或 `OWN_BOX` 且鏡頭在 `gt_visible` 並命中 GT 目標框；**錯**：`NOT_VISIBLE`、`UNCERTAIN`、`STILL_HERE_OCCLUDED`、選錯框／錯鏡頭或錯誤退回 |
| **`FULL_BLIND`**（窗內全部 tick 目標全鏡不可見但仍在場，如 `E6-S04-DP2`、`E6-S05-DP1`） | **對**：整個 3.0 s 窗內 **0 個盲區誤鎖 tick**（未鎖定任何干擾者或錯人；`LOST`／`NOT_VISIBLE`／不顯示皆算正確棄權）；任 1 個盲區誤鎖 tick 即 **錯** | **對**：`NOT_VISIBLE` 或 `UNCERTAIN`（且未輸出目標框）；**錯**：`SELECT`、`OWN_BOX`、`STILL_HERE_OCCLUDED` 或錯誤退回 |
| **`TRUE_DEPARTURE`**（窗內全部 tick `gt_present == False` 且 `gt_visible == ∅`，如 `E6-S11-DP3`、`E6-S11-DP4`） | **對**：整個 3.0 s 窗內 **0 個顯示追蹤 tick**（不鎖定任何人或空框）；否則 **錯** | **對**：`NOT_VISIBLE`；**錯**：`SELECT`、`OWN_BOX`、`STILL_HERE_OCCLUDED`、`UNCERTAIN`（真離場須明確棄權）或錯誤退回 |

  4. **分母與分層報告**：全部凍結唯一決策點皆計入總分母（API 錯誤／逾時／格式退回算錯，不排除）；報告另分層列出 `VISIBLE` 與 `FULL_BLIND + TRUE_DEPARTURE` 各自正確率。

---

## 4. 統計方法、Holm 校正、容許值與可偵測效果大小（寫死）

> **規則**：`src/amidst/evaluation/e3_scoring.py` 的 `verdict_h1`（SHA-256 `acacce39…`）與 E3／E5 既有判定**完全不改**。E6 另於 `src/amidst/evaluation/e6_verdict.py`（#721 實作）寫新判定函式 `verdict_e6`。

### 4.1 獨立統計單位與樣本門檻

- **獨立單位**：以**劇本家族（`family_id`）**為獨立單位。若有多段屬同一家族，必須先將同家族各段合併（錯人秒與盲區誤鎖秒加總；跟對率與決策點正確率按分母加權彙整）為單一統計單位，令合併後有效獨立單位數為 $M$。
- **最低門檻**：
  - 總固定決策點數 $N_{\text{dp}} \ge 40$（本規格規劃 48 點，留 8 點緩衝）。
  - 有效獨立家族數 $M \ge 8$（本規格規劃 $M = 12$）。
  - **任一門檻未達標（$N_{\text{dp}} < 40$ 或 $M < 8$）即強制標為「探索性（`EXPLORATORY`）」，絕不降低門檻。**
  - $N_{\text{dp}} \ge 40$ 僅是最低點數門檻，**不代表決策點彼此獨立**；同段內決策點相關性由家族層級重抽／翻轉處理。

### 4.2 四個單尾元件與交集－聯集檢定（IUT）

對每個主要假設 $h \in \{\text{P1}, \text{P2}\}$ 定義家族層級配對差值向量（$j = 1, \dots, M$，差值 $=$ 受測組 $-$ 對照組），由四個單尾元件構成連言（Intersection-Union Test）：

| 元件 | 指標 | 成立方向（對立假設 $H_{1,c}$） | 門檻／容許值 | 說明 |
| --- | --- | --- | --- | --- |
| C1 | 錯人秒差 $\Delta\text{WP}_j$ | $\sum_j \Delta\text{WP}_j < 0$ | $0$ | Agent 錯人秒更少 |
| C2 | 跟對率差 $\Delta\text{Follow}_j$ | $\overline{\Delta\text{Follow}} > -0.05$ | $-0.05$ | 非劣性邊界，沿用 E3／E5 `FOLLOW_MARGIN = 0.05` |
| C3 | 固定決策點正確率差 $\Delta\text{DP}_j$ | $\theta_{\Delta\text{DP}} > 0$ | $0$ | 採 §3.1 完整追蹤 3.0 s 窗正確率（`full_track_dp_acc`，K=3 多數決，依 §3.2 三情境真值表判分）並以家族彙整；單次配對與 McNemar 只另報 |
| C4 | 盲區誤鎖秒差 $\Delta\text{BlindFL}_j$ | $\theta_{\Delta\text{BlindFL}} \le +5.0/M\text{ s}$ | $\tau_{\text{blind}} = +5.0\text{ s}$ | 12 段合計（等價每家族平均 $\le +5.0/M\text{ s}$） |

- **盲區誤鎖容許值 $\tau_{\text{blind}} = +5.0\text{ s}$（12 段合計）之預先理由**：
  1. 防止 Agent 僅靠在盲區放寬鎖定（或只靠少顯示目標）來換取可見期錯人秒下降。在 E5 中 AO 盲區誤鎖秒比 B1 多出 $+65.5\text{ s}$ [39.7, 91.3]（`E5_REPORT_20261123.md`:14），本容許值將惡化上限收緊至 E5 惡化量的 $7.6\%$ 以下。
  2. 中性追蹤器具有 2 tick（$0.4\text{ s}$）滑行機制（`E5_PREREGISTRATION_20261123.md`:50），跨 12 段（每段 1–2 次盲區進出）僅滑行尾差即可能貢獻約 $0.4\text{ s} \times 12 = 4.8\text{ s}$。設定 $+5.0\text{ s}$（每段平均約 $+0.42\text{ s}$，佔總預期盲區 ~90 s 的 ~5.5%）可容納中性追蹤器固有滑行尾差，同時嚴格擋下實質盲區誤鎖惡化。
  3. 沿用 E5 H8b 的「盲區誤鎖秒差校正區間整個 $< 0$」保留為較嚴次要判定（S5）。

### 4.3 估計量、虛無假設、元件檢定、抽樣數與種子（全部寫死）

1. **估計量（Estimand）與虛無假設（明確限定 sign-flip 適用條件）**：
   - 對各元件建構平移後的獨立家族配對差值 $x_j$（$j = 1, \dots, M$，正值代表有利於 Agent）：
     - C1：$x_j = -\Delta\text{WP}_j$
     - C2：$x_j = \Delta\text{Follow}_j - (-0.05)$
     - C3：$x_j = \Delta\text{DP}_j$（採 §3.1 完整追蹤 `full_track_dp_acc` 之家族彙整差）
     - C4：$x_j = (5.0 / M) - \Delta\text{BlindFL}_j$
   - **主檢定估計量與虛無假設**：主檢定針對家族層級對稱位置偏移 $\theta_c$（中心對稱點／Hodges-Lehmann 偽中位數），檢定**符號不變（對稱）虛無假設**：
     $$H_{0,c}: x_j \overset{d}{=} -x_j \quad (\text{各獨立家族平移差值在 } 0 \text{ 兩側對稱分布})$$
     （依據 Hemerik & Goeman 2018 *Exact testing with random permutations* 與 SciPy `permutation_test` 配對樣本之 null-invariance 定義）。
   - **適用邊界（照實揭露）**：枚舉 $2^M$ 符號翻轉的有限樣本精確第一類錯誤控制**僅在 $H_{0,c}$ 對稱條件成立時保證**；若真實家族差值分布呈現嚴重偏態（例如少數極端負值搭配多數小正值使算術平均為 0），符號翻轉與百分位 bootstrap 皆**不保證**算術平均差的精確型一錯誤控制。
2. **元件 $p$ 值（家族層級配對符號翻轉檢定）與偏態敏感度護欄**：
   - 檢定統計量：$T(s) = \sum_{j=1}^M s_j x_j$（其中 $s_j \in \{-1, +1\}$），觀測值 $T_{\text{obs}} = \sum_{j=1}^M x_j$。
   - **當 $M \le 12$（本實驗 $M=12$）**：枚舉全部 $2^M = 4096$ 種符號組合（無蒙地卡羅誤差，最小可達 $p = 1/4096 \approx 0.000244$）：
     $$p_c = \frac{\#\{s \in \{-1,+1\}^M : T(s) \ge T_{\text{obs}}\}}{2^M}$$
   - **當 $M > 12$**：使用 Python 標準庫 `random.Random(20261124)` 進行 **`n_perm = 10000`** 次隨機符號翻轉，$p_c = (1 + \#\{T_{\text{perm}} \ge T_{\text{obs}}\}) / (10000 + 1)$。
   - **強制偏態與平均目標伴隨檢查（預先登記於 `verdict_e6`）**：每個元件均同步計算並報告 (a) 樣本偏態係數 $\text{skew}(x_1, \dots, x_M)$、(b) 家族層級單尾配對 $t$ 檢定 $p_c^{(t)}$（$df = M - 1$，算術平均目標）、(c) 精確單尾符號檢定 $p_c^{(\text{sign})}$（中位數目標，無對稱假設）。若任一關鍵元件滿足 $|\text{skew}(x)| > 1.0$ 且配對 $t$ 檢定在對應 Holm 門檻下與符號翻轉判定不一致，`verdict_e6` **必須**輸出 `SKEW_SENSITIVITY_FLAG` 並並列報告兩者，禁止在嚴重偏態下宣稱算術平均差具精確型一錯誤控制。
   - **IUT 彙整**：因四個元件必須同時成立，假設 $h$ 的單尾 $p$ 值為：
     $$p_h = \max(p_{h,\text{C1}},\, p_{h,\text{C2}},\, p_{h,\text{C3}},\, p_{h,\text{C4}})$$
     （依交集－聯集檢定理論，不須再除以 4）。
3. **同步校正區間（家族層級群集重抽，Family-level Cluster Bootstrap）**：
   - 群集單位：劇本家族 $j = 1, \dots, M$（有放回抽出 $M$ 個家族）；百分位 bootstrap 區間為漸近近似，重偏態下不當成有限樣本精確界。
   - **抽樣數**：`B = 10000`。
   - **固定種子**：`seed = 20261124`（使用 Python 標準庫 `random.Random(20261124)`，與 `e3_scoring.py` 零外部套件慣例一致）。
   - **區間水準與 Holm 同步**：
     - 對應 Holm 第一步 $\alpha_1 = 0.0125$（單尾）：報告 **雙側 97.5% CI**（百分位 `[1.25%, 98.75%]`），使單側上／下界對齊 $0.0125$。
     - 對應 Holm 第二步 $\alpha_2 = 0.025$（單尾）：報告 **雙側 95.0% CI**（百分位 `[2.5%, 97.5%]`），使單側上／下界對齊 $0.025$。
     - **嚴禁拿原始未校正的 95% 區間或 $p < 0.05$ 宣稱已通過 Holm 第一步校正。**

### 4.4 Holm 兩階段判定規則（含反方向判定）

- **正向（「成立」，`SUPPORTED`）**：將 $p_{\text{P1}}, p_{\text{P2}}$ 排序為 $p_{(1)} \le p_{(2)}$，整體單尾 $\alpha = 0.025$：
  1. 若 $p_{(1)} \le 0.0125$ 且該假設四元件在 97.5% 校正區間皆滿足成立邊界（C1 上界 $< 0$、C2 下界 $> -0.05$、C3 下界 $> 0$、C4 上界 $\le +5.0\text{ s}$），則假設 $(1)$ 判 **成立**；否則第一步未過，**P1 與 P2 皆不得判成立**。
  2. 僅在第一步通過時：若 $p_{(2)} \le 0.025$ 且四元件在 95.0% 校正區間皆滿足成立邊界，則假設 $(2)$ 判 **成立**。
- **反方向（「不成立」，`NOT_SUPPORTED`）**：與 E3／E5 相同，任一元件顯著劣化即構成反方向證據。對每個假設 $h \in \{\text{P1}, \text{P2}\}$，計算四個反方向單尾符號翻轉 $p$ 值（C1：$\Delta\text{WP} > 0$；C2：$\Delta\text{Follow} < -0.05$；C3：$\Delta\text{DP} < 0$；C4：$\Delta\text{BlindFL} > +5.0\text{ s}$），取 $p_h^{\text{neg}} = \min(1.0,\, 4 \cdot \min_c p_{h,c}^{\text{neg}})$（因反方向為聯集檢定，故先對 4 元件做 Bonferroni 校正），再對 $p_{\text{P1}}^{\text{neg}}, p_{\text{P2}}^{\text{neg}}$ 套用同一套 Holm（第一步 $\le 0.0125$、第二步 $\le 0.025$）。通過反方向 Holm 者判 **不成立**。
- **無法判斷（`INCONCLUSIVE`）**：既未通過正向 Holm、亦未通過反方向 Holm（含區間跨 0 或邊界者），一律判「**無法判斷**」。
- **探索性（`EXPLORATORY`）**：若 $N_{\text{dp}} < 40$ 或 $M < 8$，強制輸出 `EXPLORATORY`（另附 `would_be` 欄位供參考，不當正式結論）。

### 4.5 可偵測效果大小（MDE）分析

不得只靠雙尾符號檢定（獨立無平手下 10/12 之雙尾 $p = 0.0386$，仍大於雙側 $\alpha_1 = 0.025$）。以配對常態近似（$M = 12$ 獨立家族、$df = 11$、檢定力 $1 - \beta = 0.80$）計算最小可偵測配對標準化效果量 $d_z = \mu_\Delta / \sigma_\Delta$：

| 檢定步驟 | 單尾顯著水準 $\alpha$ | 臨界值 $t_{1-\alpha, 11}$ | 80% 檢定力 MDE（$d_z$） | 實務解讀（粗估段間 SD $\approx 8\text{–}10\text{ s}$） |
| --- | --- | --- | --- | --- |
| Holm 第 1 步 | $0.0125$ | $2.593$ | **$d_z \approx 1.00$** | 12 段合計錯人秒需減少約 **96–120 s**（每段 8–10 s），屬大效果量 |
| Holm 第 2 步 | $0.0250$ | $2.201$ | **$d_z \approx 0.90$** | 12 段合計錯人秒需減少約 **86–108 s**（每段 7.2–9.0 s） |

若去錨定帶來的實際改善為中等效果量（$d_z \approx 0.5$，每段約 4–5 s），$M=12$ 的檢定力低於 40%，很可能落入「無法判斷」；屆時報告須照實陳述檢定力限制，不得將「無法判斷」解讀為「無差異」。

---

## 5. 資料嚴格分離、SHA 清單與自動檢查

1. **三組資料邊界**：
   - **舊 16 段（`old_e3_cases`）**：`E3-A1..D2`（9 段，來源 `configs/evaluation/e3_live_cases_v1.json`）＋`E3-B3..C6`（7 段，來源 `configs/evaluation/e3_reappearances_v1.json`），全數屬於兩個舊開頭家族：`E3_OLD_FAMILY_A4`（起點 `[-10, -0.4]`，7 段）與 `E3_OLD_FAMILY_B4`（起點 `[4, 1]`，9 段）。**不得作為 E6 正式判定資料。**
   - **3 段診斷資料（`diagnostic_cases`）**：預設由舊 16 段中挑選 **`E3-A1`、`E3-B1`、`E3-C1`**（涵蓋相似干擾、長盲區、多出口三類，且 B1 與 AO 已有執行紀錄可節省診斷費用）。**嚴禁出現在正式 12 段內，且不得與正式 12 段共用任何家族。**
   - **正式 12 段（`formal_cases`）**：`E6-S01` 至 `E6-S12`，分屬 12 個全新家族 `E6-F01` 至 `E6-F12`，12 個起點座標與鏡頭開頭皆互不相同，且**零重用**舊 16 段的 `E3_OLD_FAMILY_A4`、`E3_OLD_FAMILY_B4` 或舊起點座標 `[-10, -0.4]`、`[4, 1]`。
2. **SHA 清單與自動檢查**：
   - 機器可讀清單：`configs/evaluation/e6_scenarios_spec_v1.json`（已填入舊 16 段與 3 段診斷之完整 `case_sha256`、`gt_sha256`；正式 12 段錄製凍結後由批 2 填入 SHA）。
   - 自動檢查腳本：`scripts/evaluation/check_e6_data_separation.py`（單元測試：`tests/evaluation/test_e6_data_separation.py`），區分兩種模式：
     - **`--mode draft`（批 1 預登前）**：驗證舊 16 段／診斷 3 段 SHA 與 base catalog 逐位元一致、唯一 DP ID 與同段唯一有限時間戳在片長內（唯一點數 $\ge 40$）、有效家族 $\ge 8$、零重用舊家族／舊起點；即使在草稿模式，凡標為 `FROZEN` 卻缺 SHA 一律 `FAIL`。
     - **`--mode formal [--artifact-root <dir>]`（批 2 錄製凍結閘門）**：強制要求全部 12 段皆為 `actual_gt_status == "FROZEN"`、具備完整唯一 64-hex `case_sha256`／`gt_sha256`（若給 `--artifact-root` 則實算磁碟檔 SHA-256 核對）、具備唯一且可評分之凍結 `actual_decision_points`（含 `tick`、`t_actual_s`、`gt_regime`，總數 $\ge 40$），且與舊 16 段、診斷 3 段在 ID／家族／起點／SHA 全面不相交。任一項不符即回傳非零退出碼 `FAIL`。

---

## 6. 新劇本規格（12 段 × 約 30 s）

- **錄製環境**：LIVE WebGL 引擎（原 N6 GLB，不動原始 3D 資產，Blender render = 0），**8 台鏡頭**（`CAM_BRANCH`、`CAM_ENTRY`、`CAM_EXT_CAR`、`CAM_EXT_CLEAR`、`CAM_R101_IN`、`CAM_W1`、`CAM_W2`、`CAM_WIDE`）、**5 Hz**（tick 200 ms）、**320×180**。
- **解析度不列入變因**（延後處理）。
- **相似人物設計**：前 6 段（`E6-S01`–`E6-S06`）**有外觀相似人物**（穿同色紅上衣干擾者，來源皆為新時序路線）；後 6 段（`E6-S07`–`E6-S12`）**無外觀相似人物**（僅非同色路人或單一目標）。
- **劇本計畫欄 vs 實際錄製 GT 欄分開**：下表所列時間點、事件與固定決策點（共 48 點）皆為**劇本計畫欄**；實際 timestamp、可見鏡頭集合與 `case_sha256`／`gt_sha256` 須於批 2 Chrome 錄製完成後由 GT 凍結腳本填寫（目前全數為 `PENDING_RECORDING`）。

| 段 ID | 劇本家族 | 開頭區域／鏡頭 | 計畫起點 $(x, y)$ | 相似人物／來源 | 計畫秒數 | 路線意圖與預期事件（劇本計畫欄） | 計畫固定決策點（4 點／段） | 實際錄製 GT 欄 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `E6-S01` | `E6-F01` | `OUT_W` / `CAM_EXT_CAR` | `[-13.2, -1.2]` | 有 / 新紅衣 `VEST_CROSS` | 30 s | 戶外南側進入→前廳盲區 4.0 s→西廊與紅衣交錯→進 R101 門口 | 6.0 s 重現、13.0 s 交錯、20.0 s 分離、25.5 s 切鏡 | `PENDING_RECORDING` |
| `E6-S02` | `E6-F02` | `OUT_W` / `CAM_EXT_CLEAR` | `[-12.5, 4.2]` | 有 / 新紅衣 `CORR_W_MEET` | 32 s | 戶外北側進前廳→西廊與紅衣並行分離→盲區 5.0 s→`CAM_W2` 重現 | 7.5 s 切鏡、14.0 s 並行分離、21.5 s 重現、27.0 s 同框保持 | `PENDING_RECORDING` |
| `E6-S03` | `E6-F03` | `R101` / `CAM_R101_IN` | `[2.2, -3.2]` | 有 / 新紅衣 `PORTAL_SWAP` | 30 s | R101 室內出發→門洞盲區 4.5 s（紅衣留在走廊）→東行進轉角 | 6.5 s 離門盲區、12.0 s 帶干擾重現、19.0 s 交錯、25.0 s 轉角切鏡 | `PENDING_RECORDING` |
| `E6-S04` | `E6-F04` | `CORR_W` / `CAM_W1` | `[-3.0, 1.4]` | 有 / 新紅衣 `COUNTERFLOW` | 31 s | 西廊中段出發→與紅衣對向交錯→進 R101 盲區 5.5 s（紅衣可見）→西返 | 6.0 s 交錯、13.0 s 盲區棄權、19.5 s 重現、26.0 s 穩定追蹤 | `PENDING_RECORDING` |
| `E6-S05` | `E6-F05` | `CORNER` / `CAM_BRANCH` | `[12.2, 1.2]` | 有 / 新紅衣 `SCREEN_LOOP` | 32 s | 轉角西側→屏風遮擋盲區 4.5 s（紅衣經 `CAM_WIDE`）→北廊重現交錯 | 7.0 s 遮擋盲區、13.5 s 分支重現、20.5 s 交錯、26.5 s 分離接回 | `PENDING_RECORDING` |
| `E6-S06` | `E6-F06` | `CORR_N` / `CAM_WIDE` | `[16.4, 9.2]` | 有 / 新紅衣 `NORTH_EXIT` | 30 s | 北廊深處南行→經紅衣交錯→屏風盲區 4.0 s→轉入 `CAM_BRANCH`→西廊 | 5.5 s 交錯、12.5 s 重現、19.0 s 切鏡、25.0 s 離開／維持 | `PENDING_RECORDING` |
| `E6-S07` | `E6-F07` | `VEST_W` / `CAM_ENTRY` | `[-7.2, 0.2]` | 無 / `NONE` | 30 s | 前廳出發→長盲區 6.0 s→西廊遇非紅衣路人→R101 門洞 | 8.0 s 重現、14.5 s 切鏡、20.5 s 異色交錯、25.5 s 門洞接回 | `PENDING_RECORDING` |
| `E6-S08` | `E6-F08` | `CORR_W` / `CAM_W2` | `[8.4, 0.6]` | 無 / `NONE` | 30 s | 西廊東段出發→轉角盲區 5.0 s→`CAM_BRANCH` 重現→北行進 `CAM_WIDE` | 7.0 s 重現、13.5 s 切鏡、20.0 s 遮擋重現、25.5 s 穩定追蹤 | `PENDING_RECORDING` |
| `E6-S09` | `E6-F09` | `CORR_N` / `CAM_WIDE` | `[16.2, 4.8]` | 無 / `NONE` | 31 s | 北廊中段→`OBSTACLE_SCREEN_N` 盲區 5.5 s→南返 `CAM_BRANCH`→`CAM_W2` | 7.5 s 遮擋重現、14.0 s 分支切鏡、20.5 s 重現、26.0 s 穩定追蹤 | `PENDING_RECORDING` |
| `E6-S10` | `E6-F10` | `R101` / `CAM_R101_IN` | `[0.8, -4.6]` | 無 / `NONE` | 30 s | R101 深處出門→西廊 `CAM_W1`→前廳盲區 4.5 s→戶外 `CAM_EXT_CAR` | 6.5 s 出門切鏡、13.0 s 走廊切鏡、19.5 s 盲區重現、25.5 s 戶外接回 | `PENDING_RECORDING` |
| `E6-S11` | `E6-F11` | `CORNER` / `CAM_BRANCH` | `[14.2, 1.8]` | 無 / `NONE` | 30 s | 轉角東側→`OBSTACLE_SCREEN_CORNER_N` 盲區 6.0 s→北端真離開（不在 $\ge 6\text{ s}$） | 7.5 s 重現、14.0 s 切鏡、20.0 s 真離開棄權、25.0 s 離場維持棄權 | `PENDING_RECORDING` |
| `E6-S12` | `E6-F12` | `CORR_W` / `CAM_W1` | `[0.5, 0.9]` | 無 / `NONE` | 30 s | 西廊中段進 R101 盲區 4.5 s→`CAM_R101_IN` 重現→東出 `CAM_W2`→盲區 3.5 s→`CAM_BRANCH` | 6.5 s 室內重現、13.0 s 出門切鏡、19.5 s 轉角重現、25.5 s 分支接回 | `PENDING_RECORDING` |

- **有效獨立單位數**：12 段分屬 12 個獨立劇本家族（$M = 12 \ge 8$）；計畫總長 366 s，計畫固定決策點 48 個（$\ge 40$）。若錄製後因場景可行走性微調導致任何兩段共用起點或家族，必須在批 2 凍結前合併其 `family_id` 並重跑 `check_e6_data_separation.py`。

---

## 7. 預算與停止條件

### 7.1 預算上限（不含 gate 補跑；D375／D377）

- **累計基準**：USD `38.17`（使用者讀的 API platform 總額，D375，對帳檔 `local/evidence/api-usage/RECONCILIATION_20261124.json`，SHA-256 `a1bb6e9dabb1bce1eebef8934a294dec4c196a12c2722b93752aa86fb43c4635`）＋之後新帳本列；專案總上限 **USD 90.00**。
- **診斷階段上限**：**USD 10.00**（3 段診斷 × 候選改良組，以 `ApiGuard` dry-run 為準；`B1` 與 `AO_ORIG` 沿用舊紀錄零付費）。
- **正式階段上限**：**USD 32.00**（12 段 × 約 30 s = 366 s，約舊 16 段 1044.6 s 的 35%；以 E5 平均 USD 0.01035／次推估，單組 K=3 約 550–650 次呼叫、約 USD 6–8，三組上限預估約 USD 18–24，留有餘裕以 dry-run 為準）。
- **條件項（S6 消融與模擬即時 K=1）**：僅在正式 12 段結束後、重讀累計且剩餘額度（不含 gate 補跑預留）足以涵蓋 dry-run 估價時執行；不足則標「預算不足、未執行」，不縮減 K 或段數。

### 7.2 停止條件（觸發即停）

1. **資料分離檢查失敗**：`python scripts/evaluation/check_e6_data_separation.py` 回傳非零退出碼，禁止開始任何錄製凍結或付費執行。
2. **GT 隔離違規**：任何請求、提示、摘要、歷史欄位或執行日誌出現 GT 鍵名（`gt_visible`、`gt_boxes`、`actors` 世界座標、depth、visibility），立即停止並作廢受影響執行。
3. **試跑格式退回率 > 20%**：1 段試跑（K=1，不進判定）格式退回 > 20% 時，先修提示／解析，禁止啟動診斷或正式付費執行。
4. **provider 錯誤率 > 10%**：任一段任一次執行 provider 錯誤 > 10%，依 D352 記為缺漏資料、不排除不重跑；若觸發 `CALL_BUDGET_EXHAUSTED` 則整組重跑並保留舊檔。
5. **預算閘門**：`ApiGuard` 觸及單批上限（診斷 10／正式 32）或專案累計達 USD 90，立即停止並回報使用者。
6. **未經授權之動作**：在未取得使用者明確同意前，禁止外傳影格、付費呼叫、換 pin、修改或複製 3D 資產。

---

## 8. 驗收清單（供 #721 實作與批 2／批 3 核對）

- [ ] **評分端獨立函式**：新增 `src/amidst/evaluation/e6_verdict.py`（實作 `verdict_e6`、精確 $2^M$ 符號翻轉、家族群集 bootstrap `B=10000, seed=20261124`、IUT＋Holm $\alpha=0.025$ 雙向判定）；驗證 `src/amidst/evaluation/e3_scoring.py` SHA-256 維持 `acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08` 不變。
- [ ] **GT 隔離測試**：既有架構測試確認 `src/amidst/q1q5/**` 與 `src/amidst/live_mode/**` 不 import `amidst.evaluation`；新增測試驗證去錨定歷史／摘要序列化器拒絕任何 GT 鍵名（422／`ValueError`）。
- [ ] **重播一致性**：新 12 段經未改動之 LIVE A 頁於 Chrome 完整錄製並重播 2 次（共 3 次），邏輯狀態與擷取序列完全相符；8 台鏡頭完整網格、5 Hz 時鐘對齊與 PNG／偵測索引 SHA 全部通過驗證。
- [ ] **凍結順序與自動化檢查**：
  1. 批 2 先凍結 12 段 `case.json` 與 `gt-boxes/*.a-log.json` SHA-256 至 `configs/evaluation/e6_scenarios_spec_v1.json`，並通過 `python scripts/evaluation/check_e6_data_separation.py`。
  2. 再產生共用凍結 PNG 與 RT-DETR 偵測索引（各組共用同一份，絕不各自重偵測）。
  3. 批 3 依 §2.2 寫死規則凍結 `SELECTED_AGENT` 設定與 SHA，審查通過後方得評分正式 12 段。

---

## 9. 數字引用對照表（檔案:行號）

所有行號指 `main` @ `10a1384c9676875f92d3d9bf12c9f849f8bdfeba`。

| 引用內容 | 來源（檔案:行號） | 性質 |
| --- | --- | --- |
| E3 H1 錯人秒差 A2 − B1 = +129.8 s [36.2, 218.5]，不成立 | `docs/operations/F4_E3_REPORT_658.md`:9 | 正式已判定 |
| E3 H2／H4 不成立；H3 只做描述；H5 本次未判定 | `docs/operations/F4_E3_REPORT_658.md`:11–14 | 正式已判定 |
| E5 評分器 `e3_scoring.py` SHA-256 `acacce39…` 不改；IoU 保守準則另報 | `docs/evaluation/E5_PREREGISTRATION_20261123.md`:77–79 | 正式預登 |
| E5 中性追蹤器（IoU $\ge 0.3$、滑行 2 tick = 0.4 s、OCCLUDED 10 tick = 2.0 s） | `docs/evaluation/E5_PREREGISTRATION_20261123.md`:50–52 | 正式預登 |
| E5 資源限制（poll 2.0 s、min_interval 1.0 s、呼叫上限公式、`gpt-6.1-terra`） | `docs/evaluation/E5_PREREGISTRATION_20261123.md`:56–64 | 正式預登 |
| E5 H8b 盲區誤鎖秒差區間整個 $< 0$ | `docs/evaluation/E5_PREREGISTRATION_20261123.md`:94–98 | 正式預登 |
| E5 H8a 錯人秒差 +129.1 s [55.2, 193.1]、不成立 | `docs/operations/E5_REPORT_20261123.md`:13 | 正式已判定 |
| E5 H8b 盲區誤鎖秒差 +65.5 s [39.7, 91.3]、不成立 | `docs/operations/E5_REPORT_20261123.md`:14 | 正式已判定 |
| E5 H8c 無法判斷；H8d（AO-L，K=1）不成立 | `docs/operations/E5_REPORT_20261123.md`:15–16 | 正式已判定 |
| E5 AO 平均每次呼叫帳本上界 USD 0.01035（1848 次合計 19.132） | `docs/operations/E5_REPORT_20261123.md`:60 | 正式報告 |
| 舊 16 段重複開頭（B4 系 7 段共用 14–21 s、A4 系 7 段共用 21–25 s）；AO 提問非配對設計 | [#684 留言 7133185638](https://github.com/Polalalabear/amidst/issues/684#issuecomment-7133185638)（2026-11-24） | **事後描述、未預登、未第二人核對** |
| AO 跟錯狀態下維持同一錯人 254 次 vs 換回目標 34 次（K=3 合計） | [#684 留言 7133303522](https://github.com/Polalalabear/amidst/issues/684#issuecomment-7133303522)（2026-11-24） | **事後描述、未預登、未第二人核對** |
| 對帳基準 USD 38.17（D375）；`RECONCILIATION_20261124.json` SHA-256 `a1bb6e9d…` | PR #722 (`claude/docs-handoff-20261124b`) 與 [#93 D377](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7134281394) | 協調者紀錄（LOCAL 對帳檔，不可由 repo 重建） |
