# E8 設計與預登 v1.2：Agent 與規則公平對照（資訊逐級、交接點決策、一鍵 Colab）

> 狀態：**v1 已核准（#780 審查留言 https://github.com/Polalalabear/amidst/issues/780#issuecomment-7225171977，APPROVE，Q1–Q6 照建議），實作中**。本文件隨程式同步更新。
> v1.2 相對 v1（`d4cebd12`，核准版）與 v1.1（`9abb3f5f`）的改動：
> - **撤回 v1.1 的 R-N 快照**。v1.1 依「先沿用」硬規則把第一部分改成擴充 #765（R-N 快照），但這推翻了已核准的 Q3（B1 快照；E6 單點另報、不填 E6 判定；#765 的 R-N 版維持延後；「E8 完成 #765 本機部分」作廢）。v1.2 回到 B1 快照與 NEAREST_RED 底線。
> - 沿用規則改照必改 1 的做法：**新模組只 import 既有函式，不複製**；§1.2 逐一列出每個新模組 import 了哪些既有函式，以及為什麼開新檔而不改舊檔（E7 notebook 與包要能原樣重現）。另有測試掃描重複定義（§7.1）。
> - 必改 3：Qwen L0 的時間重估（§6.3），以及 A100 超過 4 h 時把 Qwen L0 減為只跑 `p0` 的規則。
> - 統計單位採家族（M = 16，同 E6）；以段（M = 28，v1 的做法）為敏感度。這是相對核准版 v1 的改動，協調者不同意就改回。
> - §5.4 加入第二部分的決策點正確數；H2 的結論措辭為「不比規則差」。
>
> Issue：[#780](https://github.com/Polalalabear/amidst/issues/780)（W1；W3、W4 的規格也寫在這裡）。決策：D416、D417（#93）。前因：#767 協調者分析，整理在 `docs/evaluation/E7_LAYA_ANALYSIS_20261128.md`。
> 作者：Claude Opus 5.5（E8 子 session），2026-11-28。身分一律 `UNCONFIRMED`；實體可通行性 `UNKNOWN`。本機模型零 API 費用；GPT 組由 Codex 擴充 `e6_arms_run.py` 另做（#781），獨立複核在 #782。

## 0. 目的與前因

研究問題：**Agent 能否加快切換鏡頭的決策，並在複雜情況下優於規則 B1。** E5、E6（P2 `NOT_SUPPORTED`）、E7 都是規則贏。但 E7 給 laya 的輸入比 B1 和 API Agent 都少（D416）：

- 沒有「目標是紅色」、上一個位置、地面座標、鏡頭連通和圖片（5,223 筆請求的 `image_paths` 全空）。
- laya 從不回答 `NOT_VISIBLE`，72%（laya_text）／65%（laya_typed）選清單第一個候選。
- 快照正確率約等於「永遠選第一個」（2,058 比 2,037／5,120），還輸給「選第一個紅色」（2,516）。
- 多錯的秒數八成是錯鏡頭（laya_text 比 B1 多 261.2 s，其中 207.0 s 是錯鏡頭）。

**設計時另外查到的根因（§2.6；已留言 #767）**：laya 是 ModernBERT 編碼器加決策頭，輸入長度有硬上限：

- root 版（laya_text）：`max_len=512`、`head_max_len=192`；typed 版：`max_len=1024`、`head_max_len=256`（HF `convaiinnovations/laya` @`246177e5`，`rl_agent_config.json`）。
- `rl_common.build_sequence` 先放題目和選項；選項總長超過 `head_max_len` 時，**每個選項會被平均截短**，題目只剩下剩餘的空間，state 則從右邊截斷。
- E7 的選項文字是 `camera CAM_W1 detection D1 box [...] score 0.52`。決策點的候選數中位數 6、最多 22，加上 3 個非選人選項後，每個選項只剩約 10–20 個 token，框和分數常常被截掉。
- 結果是 laya 看到的選項幾乎只差在鏡頭名稱。所以 E8 的選項格式要針對這個上限重新設計。E7 每筆請求的實際截斷率目前 `UNKNOWN`，由 E8 notebook 量（V6）。

E8 要回答三件事：

1. 公平條件下（Agent 拿到不少於規則的資訊），本機模型的單點判斷能不能勝過簡單規則。
2. 哪一種資料讓 Agent 變好（資訊逐級增加），以及候選順序造成多大的位置偏差。
3. B1 負責追人、Agent 只在交接點介入時，完整追蹤會不會比 B1 差，能不能更早切對鏡頭。

## 1. 資料來源與沿用清單

### 1.1 凍結輸入（全部已存在）

| 項目 | 路徑（LOCAL 相對 `local/evidence/`；repo 相對 repo 根） | SHA-256 |
| --- | --- | --- |
| E3 決策點（38 個，9 段） | `e3-652-20261122/CORPUS.json` | `930e85fe…c50d` |
| E3 決策點（30 個 REAPPEAR，7 段） | `e3-reappearances-20261122/CORPUS.json` | `6954dcb4…f7c9` |
| E6 決策點（48 個，12 段，`actual_decision_points`） | `configs/evaluation/e6_scenarios_frozen_v1.json` | `5bab2766…b338` |
| B1 b-log（兩部分的快照來源） | E3：`f4-658-20261122/runs-final-{9,665}/<case>/B1.k1.json`；E6：`e6-formal-run-20261127/b1/<case>/B1.k1.json` | E6 `b1/` 樹雜湊 `90920606…cb7e5cc`；E3 的打包時逐檔記入 `PACK_INFO.json` |
| 凍結偵測與 RGB | E3：`e3-652-20261122`、`e3-reappearances-20261122`；E6：`e6-formal-det-20261127`（`e3_f4_run.load_case` 讀取時驗 SHA） | 逐檔驗證 |
| 相機目錄 | `local/data/live-assets-20261115/cameras.catalog.json` | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`（與 B1 紀錄的值相同） |
| 場景脈絡 | `e3_f4_run.live_scene_context` | `3072cc5a…`（與 B1 b-log 相同；序列化後 19,589 字元） |
| 評分器 | `src/amidst/evaluation/e3_scoring.py` | `acacce39…7d08`（釘選，不改） |
| E7 逐 tick 請求／laya 答案 | `e7-colab-pack-pertick-20261127/requests/e3_16_segments.jsonl`／`e7-run-pertick-20261127/e7-outputs-pertick/` | `8568e4fa…8dee`／`2e23f37a…b3cb` |
| laya | HF `convaiinnovations/laya` @`246177e5cb70334c9831c0730864a93c836aac8f`（root＝laya_text，`typed-decisions/`＝laya_typed；3 個審核過的 `.py` 驗 SHA） | 同左 |
| Qwen | `Qwen/Qwen2.5-VL-3B-Instruct`、`Qwen/Qwen2.5-VL-7B-Instruct` | `hf_revision` 打包時釘成 40 字元 commit（目前 `UNKNOWN`） |

設計期統計（0 推論、0 付費、不讀 GT）放在 LOCAL `e8-design-20261128/`：

| 檔案 | SHA-256 |
| --- | --- |
| `e8_design_dpstats.py` | `a56fb30e…a550` |
| 其輸出 | `e0871687…09c0` |
| `e8_design_trigger_estimate.py` | `b39a35ed…6704` |
| 其輸出 | `96fd0b86…d985` |

### 1.2 沿用與修改（必改 1：只 import，不複製）

**不能改的檔案。** 下列檔案的 SHA 被 E6 凍結收據釘住（`e6_select_arm.PROMPT_FILES`），`e6_arms_run --paid` 會比對，所以 E8 只 import：`src/amidst/live_mode/aopen/arms.py`、`src/amidst/live_mode/aopen/decider.py`、`configs/evaluation/e6_arms_v1.json`、`docs/evaluation/E6_PREREGISTRATION_DRAFT.md`。`e3_scoring.py`（釘選 `acacce39…`）、`e6_rule_neutral.py`（R-N 輸出記了 `code_sha256`）、`e3_f4_run.py`（b-log 記了它的 SHA）也不改。

**為什麼開新檔而不改 E7 的檔案。** E7 的 notebook 釘在 code commit `a3c7e90d`，E7 包（`e7-colab-pack-pertick-20261127`）與其 MANIFEST 要能原樣重現；#769 也正在修改 `e7_replay`／`e7_decider_eval`。E8 的邏輯放進新模組，就不會改到 E7 的行為與 SHA，也不會和 #769 的修正衝突。新模組只 import 既有函式；`tests/evaluation/test_e8_requests.py::test_no_duplicate_definitions` 用 AST 檢查新模組沒有重新定義下列既有模組中的公開名稱。

| 新模組 | import 的既有函式（不複製） | 新寫的部分 |
| --- | --- | --- |
| `src/amidst/evaluation/e8_requests.py`（推論端；已完成） | `e7_decider_eval.DeciderRequest`、`assemble_ao_prompt`、`build_laya_state_and_questions`（L0 逐位元組照 E7）；`arms.reference_text`（L1 起的顏色查詢句）；`agent_service.Candidate`、`gate_of`（VLM 的閘門資訊）；`scene_context.sha256_of`、`serialize`（L3F）；`e3_f4_run.poly_dist`（覆蓋區距離） | 跨鏡頭合併、代號、3 種順序、依級遮蔽的 `e8_level_request_v1`、laya 精簡渲染、VLM 渲染、`parse_e8_answer`、KEEP 解析、底線策略 |
| `scripts/evaluation/build_e8_colab_pack.py`（Mac；已完成） | `e3_f4_run.load_case`、`live_scene_context`、`CONFIG`；`build_e7_colab_pack.candidates_for_tick`、`variable_text`、`expected_for_tick`、`write_manifest`；`e7_scoring_bridge.write_colab_answer_table`、`_scan_forbidden_gt_fields`、`verify_colab_pack_pre_upload`；`arms.reject_forbidden`；`live_mode.tracker.Projector.ground`（地面投影，同 B1） | B1 快照抽取、KEEP 顯示對到候選、第二部分逐 tick 偵測、L4 畫面 |
| `src/amidst/evaluation/e8_score.py`（Colab 評分格與 Mac；已完成） | `e6_verdict.single_dp_correct`、`full_track_dp_correct`、`sign_flip_p`、`sign_flip_p_two_sided`、`mcnemar_exact_p`、`majority`、`MIN_DP`、`MIN_FAMILIES`、`TAU_BLIND_S`，以及 H2 用的 `_group_family_units`、`_diffs`、`_shifted`；`agent_eval_scoring.metrics.holm_bonferroni`（一般 Holm；`e6_verdict._holm` 只做 2 個假設）、`cluster_bootstrap_ci`（家族群集 bootstrap）；`e3_f4_score.run_scores`（第二部分，Mac） | 3 種順序多數決、H1／S 檢定的組裝、+14.0 s 錯人秒容許值、選組、位置偏差、RANDOM 期望值、S3／S4、提早切對、§5.5 結論、`unified_section` |
| `src/amidst/evaluation/e8_handoff.py`（推論端；已完成） | `e3_f4_run.replay`、`chain_box`、`CONFIG`（B1 重現與閉迴路）；`live_mode.server.State` 的 `decider.step` 掛點；`e8_requests` | 觸發、套用、延遲 |
| `src/amidst/evaluation/e8_colab_run.py`（推論端；notebook 逐格呼叫） | `e7_colab_runtime.load_group_checkpoint`、`save_group_checkpoint`；`e8_requests`；`e8_handoff` | 分組、§6.3 的 4 h 規則（`projected_hours`）、可續跑的組、第二部分各組、SMOKE 替身 |
| `scripts/evaluation/e8_score_run.py`（Mac 一條指令；已完成） | `e8_score`、`e3_f4_score.run_scores`、`generate_unified_analysis`、`report/figures/build_figures.py` | CLI：讀 run zip、用 GT 補判 OWN_BOX（鍵為（模型, 級, 順序, request_id），`e8_score.own_box_key`）與 TRUE_DEPARTURE、讀 `RUN_NOTES.json` 寫偏離（含 GPU）、輸出結果與 `unified_e8_section.json` |
| `notebooks/e8_colab_eval.ipynb`（已完成） | E7 notebook 的格子結構、`e7_colab_runtime` 的 checkpoint、`e7_decider_eval.collect_hardware_provenance`、`resolve_hf_provenance`、`verify_manifest_sha256`、`build_laya_native_inference_fn`、`build_qwen_vl_inference_fn` | E8 的設定與流程 |

**小幅、只增不改的修改**（既有行為與測試不變）：

- `e7_decider_eval.py`：laya／Qwen 推論函式加「直接吃已渲染輸入」的入口 `.raw`／`.agent`（原本 `_infer` 只吃 `DeciderRequest`）。這是本 PR 唯一改到的 E7 檔案，只做加法：把 Qwen 的生成步驟抽成 `_generate`，`_infer` 改呼叫它，行為不變（N2，#785 審查）。E7 notebook 釘在 `a3c7e90d`，clone 的是那個 commit 的程式，所以 E7 的包、MANIFEST 與結果不受影響。
- `scripts/evaluation/generate_unified_analysis.py`＋`configs/evaluation/unified_analysis_schema_v1.json`：加選填的 `e8` 區段（schema 頂層 `additionalProperties:false`）。
- `report/figures/build_figures.py`、`FIGURES.md`：加 E8 圖 fig4–fig7（資訊階梯、位置偏差、閉迴路錯誤拆分、提早切對分佈），只在輸入有 `e8` 區段時才畫；`report/figures/manifest.json` 是 sample 輸入的產物，沒有 `e8`，所以不變。
- `docs/evaluation/E7_COLAB_UPLOAD_PACK_SPEC_V1.md`：加 E8 包的章節。

**新增文件**：本文件、`docs/evaluation/E7_LAYA_ANALYSIS_20261128.md`、`docs/operations/E8_REPRO_<日期>.md`。W2 離線腳本收在 `scripts/evaluation/e8_w2_offline_baselines.py`（`e8-offline-b` session 寫成，只改路徑），結果寫在 E7 分析文件 §4。

**Issue 對應**：E8 不填 E6 的 `single_correct`；#765 的 R-N 版維持延後（核准的 Q3）。E7 分析補記到 #727 並連到 #767；本 issue 是 #732（E6 正式執行）的下一輪，範圍不重疊。

## 2. 第一部分：單點對照（開迴路）

### 2.1 題目

| 資料集 | 段數 | 家族 | 決策點 | 既有分層標籤 |
| --- | ---: | ---: | ---: | --- |
| E3（F4 #658 凍結語料） | 16 | 4（A–D） | 68 | 決策點 `type`（16 種；REAPPEAR 33 個） |
| E6（正式 12 段） | 12 | 12 | 48 | `type`（24 種）、`gt_regime`（VISIBLE 43、FULL_BLIND 5；只在 Mac 分層） |
| 合計 | 28 | 16 | **116** | 沒有標籤的情境寫 `UNKNOWN`，不新造標籤 |

設計期量到的 E3 68 點（`e8_design_dpstats.out.txt`，B1 的 T−1 狀態）：

- 每點的候選數：中位數 6、p90 12、最大 22。
- 紅色候選數：中位數 4、最大 18。
- 估計位置 4 m 內的紅色框：0 個的 14 點、1 個的 18 點、≥2 個的 36 點。
- B1 在 T−1 的狀態：TRACKING 且看得到 52 點、TRACKING 但 lost 9 點、LOST 7 點。
- E6 的同樣統計要在打包時才算，目前 `UNKNOWN`。

### 2.2 凍結快照（B1 在 T−1）

每個決策點的時間記為 T。打包器直接從凍結的 B1 b-log 取 T−1 那一列（不重播），快照欄位只有（`e8_requests.snapshot_of`）：

- `state`、`active_cam`、`est_xy`、`lost_ticks`，以及 `seen_ago_s = lost_ticks × 0.2`；
- T 時刻的凍結偵測（含 HSV 顏色）；
- T 時刻的 RGB（只給 L4）；
- 種子參考裁切（B1 第一次 ACQUIRE 的框，用 `advisor.crop_jpeg` 裁切）。

公平前提：Agent 拿到的資訊不少於 B1 在 T 做決定時有的（B1 的 T−1 狀態加 T 的偵測）。不放任何 GT 欄位。B1 沒有 ACQUIRE 的段沒有快照，那些點記 `NO_SEED`，所有組都算錯。

### 2.3 答案空間與「實際顯示」

| 答案 | 意義 | 解析成的實際顯示（`e8_requests.display_of`） |
| --- | --- | --- |
| `KEEP` | 維持 B1 目前的目標 | B1 在 T 實際顯示的框（`keep_display`，打包時把 B1 框對到 T 的候選）；B1 在 T 沒有顯示就不顯示 |
| `SELECT`＋選項代號 | 選一個候選 | 該選項的代表框 |
| `NOT_VISIBLE` | 所有鏡頭都看不到 | 不顯示 |

- `keep_display` 只用來解析 KEEP，不進任何渲染文字。B1 的框在 b-log 沒有四捨五入，而 `candidates_for_tick` 會取到小數 1 位，所以打包時先在原始偵測中比對（`dets[active_cam]` 第 i 個框等於 B1 框 → `D{i+1}`），對不到就停（G3）。
- 判分（§2.9）用 `e6_verdict.single_dp_correct(gt_regime_T, answer, hit_gt=...)`：實際顯示是框 → `'SELECT'`，`hit_gt`＝該框命中標籤；回答 `NOT_VISIBLE` → `'NOT_VISIBLE'`；KEEP 但沒有顯示 → `'UNCERTAIN'`；格式錯誤 → `None`，算錯。

### 2.4 候選與選項

- **候選**：T 時刻所有 person 偵測（score ≥ 0.15，CAM_ENTRY ≥ 0.05，任何顏色），`detection_id` 依各鏡頭編成 D1…Dn（`build_e7_colab_pack.candidates_for_tick`）。
- **跨鏡頭合併**（L0c 以上，`merge_options`）：不同鏡頭的框投影到地面（`Projector.ground(cam, (x0+x1)/2, y1, 320, 180)`）後相距 < 1.5 m，就合成一個選項；同一台鏡頭的框絕不合併。代表框取框高最大的成員（同 `Tracker.update` 的換鏡規則），顏色取聯集，投影失敗的框不合併。選項顯示的 `score` 是代表框（框高最大的成員）的偵測分數，可能低於同一人在另一台鏡頭的分數（N1）；它不是「這個人可信度低」的訊號，報告引用時要註明。L0c 到 L4 的選項集合完全相同；L0 照 E7 原樣，不合併。
- **代號**：依當次順序給 A、B、C…；`KEEP`、`NOT_VISIBLE` 固定排在最後。
- **3 種順序**（`permute`）：`p0` 標準順序（相機的凍結順序，再依 D 編號）；`p1` 反轉；`p2` 用 `random.Random(f"20261128|{base_id}")` 打亂。只打亂候選；標籤以 (鏡頭, D) 表示，不受順序影響。

### 2.5 資訊逐級增加（累加；請求依級遮蔽，不帶高一級的欄位）

| 級 | 新增資訊 | 給誰 |
| --- | --- | --- |
| **L0** | E7 現況，逐位元組照 E7 的請求（`variable_text` 加上 `build_laya_state_and_questions`／`assemble_ao_prompt`）。答案對照（`from_e7_parsed`）：`UNCERTAIN`、`STILL_HERE_OCCLUDED` → KEEP；`OWN_BOX` → Colab 記 `NEEDS_MAC_SCORING`，回 Mac 用 GT 框補判（同 E7） | 全部模型 |
| **L0c**（格式對照） | 資訊與 L0 相同（鏡頭、分數、框），改用 E8 精簡格式與合併後的選項 | 全部模型 |
| **L1** | 顏色查詢句（`arms.reference_text('red', 'NO_IMAGE')`）＋每個選項的顏色；VLM 另外附 `gate_of` 的閘門（只當資訊） | 全部模型 |
| **L2** | B1 快照：上一個鏡頭、估計位置、距今幾秒、B1 狀態；每個選項的地面座標與到估計位置的距離（m） | 全部模型 |
| **L3** | 鏡頭連通摘要（`scene_relations`，從 `scene_context` `3072cc5a…` 推出）：每個選項的鏡頭相對上一個鏡頭是 `same`、`adj`（graph v3 有 transition）、`ovl`（`overlap_iou` ≥ 0.05）還是 `other`；另列相鄰鏡頭、重疊鏡頭，以及估計位置到各鏡頭地面覆蓋區的距離（同 B2／F2 的空間排序） | 全部模型 |
| **L4** | L3＋種子參考裁切＋T 時刻各鏡頭畫面，框上標選項代號（`service_decider._jpeg` 畫框；先把 320×180 放大 3 倍到 960×540，否則 26×14 的代號標籤會蓋住遠處的人） | 只給 VLM |
| **L3F**（探索性） | L3 的摘要換成完整 `scene_context`（序列化後附 SHA，渲染時比對） | 只給 Qwen-7B |

- L0c 用來把格式效果（含合併）單獨量出來，這樣 L1−L0c、L2−L1、L3−L2、L4−L3 才是單純的資訊效果。
- L3 用摘要，因為完整 `scene_context` 約 19.6k 字元，laya 放不下；為了讓各模型能比較，全部模型都用同一份摘要。

### 2.6 laya 的放法

laya 的輸入順序是 `[CLS] 題目 [SEP] [MASK]選項1 [MASK]選項2 … [SEP] state [SEP]`。選項區（題目＋選項）≤ `head_max_len`（192／256），全部 ≤ `max_len`（512／1024），state 從右邊截斷。因此（`render_laya`）：

- **題目只放一句短句**：L0c 是「Which option is the tracked person now?」；L1 起是「Which option is the red-clothed tracked person now?」。
- **選項文字最重要的放前面**，每個選項目標 ≤ 10 個 token：

  | 級 | 候選 | KEEP | NOT_VISIBLE |
  | --- | --- | --- | --- |
  | L0c | `A: W1 .52` | `KEEP: keep current target` | `NOT_VISIBLE: not visible in any camera` |
  | L1 | `A: red W1 .52` | 同上 | 同上 |
  | L2 | `A: red 1.2m W1 .52` | `KEEP: keep current target W1` | 同上 |
  | L3 | `A: red 1.2m W1 same .52` | 同上 | 同上 |

- **state 是有順序的 JSON，被截斷時先丟後面的**：`target`（L1 起）、`last`（L2 起，例如 `W1 (12.8,1.9) 0.4s ago, TRACKING`）、`options`（每個選項一行：鏡頭、D、分數、框；L1 起加顏色，L2 起加地面座標與距離，L3 起加鏡頭關係，合併的列出其他成員）、`graph`（L3 起）、`now_s`。
- **截斷稽核**：notebook 推論前用 laya 自己的 tokenizer 計算每筆請求，記錄「選項被平均截短」和「state 被截斷」的比例（分模型、分級）。這是要報告的共變量，不是停止條件（V6）。

### 2.7 共用的結構化請求與 VLM 渲染

- 打包器為每筆 (dp, level, perm) 寫一列 **`e8_level_request_v1`**（JSONL，`build_request`）。共有欄位：`request_id`（`<case>|t<tick>|<level>|<perm>`）、`base_id`、`case_id`、`dataset_group`、`tick`、`now_s`、`level`、`perm`、`camera_ids`、`keep_display`、`identity`。L0 另帶 `e7`（E7 的 `variable_text`、`candidates`、`camera_ids`）；其他級帶 `options[]`（`key`、`camera_id`、`detection_id`、`box`、`score`、`members`；L1 起 `colors`；L2 起 `ground_xy`、`distance_m`；L3 起 `relation`），以及 `target_color`（L1 起）、`snapshot`（L2 起）、`scene_summary`（L3 起）、`scene_context_sha256`（L3F）、`image_refs`（L4）。laya、Qwen 和 #781 的 GPT 組都從這份檔渲染，資訊相同，只是格式不同。
- Qwen 的渲染（`render_vlm`）：
  - 系統文字是 `e8_requests.VLM_SYSTEM`：保留 `agent_service.SYSTEM_TEXT` 的身分不可確認、閘門只是資訊、偏好棄權等條款，答案格式換成 E8 的 `{"answer":"SELECT"|"KEEP"|"NOT_VISIBLE","option":"A"|null,"confidence":"low"|"medium"|"high"}`，`max_new_tokens=48`。L0 例外，用 E7 原樣，256 token。
  - 每個選項一行（鏡頭、D、分數、框；依級加顏色、座標、距離、關係），L1 起附 `gate_of` 的 `rule_eligible` 與原因；L2 起附 `TRACKER_STATE`（B1 快照）；L3 起附 `CAMERA_RELATIONS`。
  - 貪婪解碼，沿用 `build_qwen_vl_inference_fn`。答案由 `parse_e8_answer` 解析，不重試。

### 2.8 組別（每格 116 點 × 3 種順序 = 348 筆請求）

| 組 | 資訊 | 請求數 | 說明 |
| --- | --- | ---: | --- |
| B1（＝KEEP，B1 在 T 實際顯示） | 參考 | 0 | 和完整追蹤的 B1 對照 |
| FIRST（第一個候選）、RANDOM（候選和 NOT_VISIBLE 中均勻抽，seed `20261128\|request_id`） | L0c | 0 | 3 種順序都算；RANDOM 另報理論期望值 |
| FIRST_RED（第一個紅色，沒有就 NOT_VISIBLE） | L1 | 0 | 3 種順序都算 |
| NEAREST_RED（離 B1 估計位置最近的紅色，不設門檻；沒有就 NOT_VISIBLE） | L2 | 0 | 同級資訊的規則 |
| laya_text、laya_typed | L0、L0c、L1、L2、L3 | 各 1,740 | GPU 約 40 ms／筆 |
| Qwen2.5-VL-3B | L0、L0c、L1–L4 | 2,088 | |
| Qwen2.5-VL-7B | L0、L0c、L1–L4、L3F | 2,436 | 建議 A100 |

底線策略在 `e8_requests.baseline_answer`。每點的主分數是 **3 種順序的多數決**（≥ 2 種對才算對），另報 3 種順序的平均。

### 2.9 判分

- 標籤由 `build_e7_colab_pack.expected_for_tick` 產生（Mac 讀 `gt-boxes/<case>.a-log.json`，`judge_box` primary），透過 `write_colab_answer_table` 寫入，只含 D385 白名單欄位。
- Colab 上把標籤對到 `gt_regime_T`：`SELECT`／`UNCERTAIN`（偵測漏掉）→ `VISIBLE`；`NOT_VISIBLE` → `FULL_BLIND`。Colab 無法分辨 `TRUE_DEPARTURE`，所以 Colab 的數字是暫定；Mac 用 GT 的 `present` 判出 T 的三種情境，以 Mac 的結果為準。
- 判分呼叫 `single_dp_correct`。偵測漏掉的點（VISIBLE 但沒有候選命中）所有組都錯，不影響配對檢定；另報這些點的「安全答案率」。合併選項用代表框判分。
- E6 的 48 點單點結果另外報告，不填入 E6 判定（核准的 Q3）。

## 3. 第二部分：完整追蹤（閉迴路，交接點決策）

### 3.1 架構

- `e8_handoff` 的決策器掛在 `live_mode.server.State._infer_tracking` 既有的 `self.decider.step(...)` 上，介面同 `ServiceLiveDecider`：B1 每個 tick 照常追人，決策器只在觸發點建請求、問模型、套用答案。
- 驅動沿用 `e3_f4_run.replay` 的流程與 CONFIG（gate 4 m、score .15／.05、relock 關、target red），b-log 格式也相同（`e3-f4.b-log.v1`）。
- 輸入是打包好的逐 tick 偵測，已含 HSV 顏色（Mac 端先用 `load_case` 算好）。
- **B1 重現閘門**：不掛決策器時，28 段的 `rows[].tracking` 必須和凍結的 B1 b-log 完全相同（V2）。
- 請求和第一部分用同一個 `build_request`，快照來自當下的 B1 狀態。只用文字級（核准的 Q1：第二部分不含 L4）。

### 3.2 觸發點（寫死）

B1 在 tick t 更新後，依序取第一個成立的條件：

| 代碼 | 條件 | 間隔 |
| --- | --- | --- |
| `LOST` | B1 的 `lost_ticks` 第一次 ≥ 2（0.4 s；同 `ServiceLiveDecider.lost_ticks_before_ask=2`） | 之後仍然 lost 就每 1.0 s 再問一次 |
| `SWITCH` | 這個 tick 有 B1 的 `SWITCH` 或 `REACQUIRE` 事件 | — |
| `AMBIGUOUS` | B1 為 TRACKING、`lost_ticks=0`，且 T−1 估計位置 4 m 內有 ≥ 2 個紅色候選、其中兩個的地面距離 ≥ 1.5 m | 持續時每 2.0 s 最多問一次 |

- 全域最短間隔 1.0 s；`ACQUIRE` 之前不問。
- 設計期估計：只算 LOST＋SWITCH 時，28 段共 7,058 tick、377 個觸發點。AMBIGUOUS 的數量 `UNKNOWN`；全部觸發的上限約 1,411 個。

### 3.3 套用

- `KEEP`：不動。
- `SELECT`：重設追蹤器（`est`、`active`、`state=TRACKING`、`lost=0`、`last_seen`、`t_seen`），同 `ServiceLiveDecider` 的單次修正，之後由 B1 繼續追。
- `NOT_VISIBLE`：追蹤器設成 LOST（保留 `est`），1.0 s 內不顯示；到期後若仍符合 LOST 條件就再問。
- 無效回答：當成 KEEP，記錄 `fallback_reason`。
- 順序只用 `p0`（核准的 Q6）。

### 3.4 延遲

- **主分析 `ZERO_LATENCY`**：答案在觸發 tick 當下生效。
- **次要分析 `MEASURED`**：答案在第一個滿足 `(t'−t)×0.2 s > 實測延遲` 的 tick 生效，框用 `chain_box`（IoU ≥ 0.3）從 t 串到 t'；串不起來就記 `EXPIRED`、不套用（同 E5 A3／E7 replay）。

### 3.5 組別

| 組 | 觸發點由誰決定 |
| --- | --- |
| B1 | 無（重現閘門與對照） |
| B1+FIRST_RED、B1+NEAREST_RED | 規則底線 |
| B1+laya_text@k\*、B1+laya_typed@k\*、B1+qwen3b@k\*、B1+qwen7b@k\* | 各模型在第一部分最好的**文字級** k\*（L0c–L3） |
| **SELECTED**（主要假設 H2） | 上面四組中第一部分多數決最高者。同分時依序比：3 種順序的平均正確率、較低的級、模型順序 laya_text < laya_typed < qwen3b < qwen7b |
| SELECTED＋MEASURED | 次要分析 |

選組在 notebook 裡自動執行。它只決定哪一組是主要組，不會進任何推論輸入；四組全部都跑。

### 3.6 評分（只在 Mac）

- E3 段用 `e3_f4_score.run_scores`（評分器 `acacce39…`），E6 段用 `e6_verdict.full_track_dp_correct`（依 `gt_regime`）。另外照 E6 格式對 SELECTED 對 B1 跑 `verdict_e6`，只當次要參考。
- 指標：錯人秒（拆成錯鏡頭 `wrong_camera_s` 和鏡頭對但人錯）、失聯秒、盲區誤鎖秒、跟對率（主準則與 IoU 保守準則）、決策點正確數、**提早切對秒數**（對 T 時目標可見的點，比較 B1 和各組在 [T, T+3 s] 內第一個 CORRECT tick 的時間，3 s 內沒有就記 3.2 s；提早量＝B1 − 該組，依既有 `type` 分層）。

## 4. GT 隔離（D417 折衷）

1. 第一部分在 Colab 只拿到 `scoring_only/answer_table.json`（D385 白名單），由 `write_colab_answer_table` 寫入。`type`、`gt_regime` 的分層只在 Mac，用 `request_id` 合併。
2. 第二部分在 Colab 沒有任何 GT；評分只在 Mac。
3. 打包閘門：`verify_colab_pack_pre_upload` 必須通過。所有請求、快照、逐 tick 偵測都要通過 `_scan_forbidden_gt_fields`；另外掃描 `gt-boxes`、`a-log` 字串，並套用 `arms.reject_forbidden`。任何一項失敗就刪掉整包。
4. 推論端的 E8 程式（`e8_requests`、`e8_handoff`）不得 import `e3_scoring`、`e7_scoring_bridge`、`e6_verdict` 或 `e8_score`，由測試檢查。
5. 快照、顏色、投影、`scene_context` 只來自 B1 紀錄、RGB、標定與設定。

## 5. 預登

### 5.1 判定用語

用 `SUPPORTED`、`NOT_SUPPORTED`、`INCONCLUSIVE`、`EXPLORATORY`（同 E6）。`SUPPORTED`＝Holm 拒絕虛無假設；`NOT_SUPPORTED`＝反方向單尾檢定 p ≤ α／m（Bonferroni）；其餘為 `INCONCLUSIVE`（`e8_score.status_of`）。「無法判斷」不等於「沒有差異」。門檻沿用 `e6_verdict`：N_dp ≥ 40 且 M ≥ 8，否則 `EXPLORATORY`。E8 是 N_dp = 116、M = 16。

### 5.2 主要假設（Holm，m = 5，單尾 α = 0.05）

| 代號 | 假設 |
| --- | --- |
| H1a | laya_typed@L2 的單點正確率（多數決）> FIRST_RED |
| H1b | laya_typed@L3 > FIRST_RED |
| H1c | qwen7b@L2 > FIRST_RED |
| H1d | qwen7b@L3 > FIRST_RED |
| H2 | B1+SELECTED（ZERO_LATENCY）的完整追蹤不比規則 B1 差。交集－聯集檢定：跟對率差 ≥ −0.05（同 E6 C2）、錯人秒差總和 ≤ +14.0 s（28 段，每段平均 +0.5 s；核准的 Q4）、盲區誤鎖秒差總和 ≤ +5.0 s（同 E6 C4） |

統計方法：

- **獨立單位是劇本家族**（沿用 `e6_verdict`：E3 A–D 共 4 個、E6 12 個，M = 16），同家族先合併。
- H1：家族層級配對差值（各家族的多數決正確率差）做單尾 sign-flip。M > 12，所以用種子 20261128 翻轉 10,000 次（`e6_verdict.sign_flip_p(seed=20261128)`）。附家族群集 bootstrap 95% CI（`cluster_bootstrap_ci`，B = 10,000，種子 20261128）。點層級的精確 McNemar 只當描述。
- H2：每個元件先平移容許值，再做單尾 sign-flip，p 取三者最大值。
- Holm 用 `agent_eval_scoring.metrics.holm_bonferroni`（一般 m；`e6_verdict._holm` 寫死 2 個假設）。H2 的家族單位與容許值平移沿用 `e6_verdict._group_family_units`、`_diffs`、`_shifted`（跟對率 +0.05、盲區誤鎖 5.0 s／M），錯人秒的容許值是 14.0 s／M。
- **敏感度**：以段為單位（M = 28，核准版 v1 的做法）重算，只報告。

### 5.3 次要假設（Holm，m = 13，雙尾 α = 0.05）

- S1（7 項）：laya_typed、qwen7b 的 L1−L0c、L2−L1、L3−L2，加上 qwen7b 的 L4−L3。
- S2（4 項）：laya_typed、qwen7b 在 L2、L3 對 NEAREST_RED（同級資訊的規則）。
- S3：SELECTED 的錯人秒低於 B1。
- S4：SELECTED 提早切對秒數的中位數 > 0。

### 5.4 探索性（不做多重校正）

- laya_text、qwen3b；L0 與 E7 的一致率；L0c−L0；L3F−L3。
- 位置偏差：每級、每種順序選第 1 個候選的比例；3 種順序間的一致率。
- 依 `type`、`family`、`gt_regime`、候選數、截斷與否分層；N 小的分層（如 E6 FULL_BLIND n=5）只當探索。
- **第二部分的決策點正確數**：各組在 116 個決策點上用 `full_track_dp_correct` 判的正確數，和第一部分的單點結果並列。
- laya 信心門檻（和 W2 對照）；MEASURED；規則底線的閉迴路組；錯鏡頭拆分；偵測漏掉點的安全答案率；E6 格式的 `verdict_e6`；E6 48 點的單點結果。

### 5.5 事先定義的結論

| 結論 | 條件 |
| --- | --- |
| **Agent 優於規則** | H2 `SUPPORTED`，H1a–d 至少一項 `SUPPORTED`，**且** S2（對同級資訊的規則 NEAREST_RED，即 4 m 內最近的紅色）在 L2 或 L3 至少一項 Holm 調整後顯著偏向 Agent。S3 成立時加「降低錯人秒」，S4 成立時加「較早切對鏡頭」 |
| **超過顏色啟發法，閉迴路不劣於 B1** | H2 `SUPPORTED`，H1a–d 至少一項 `SUPPORTED`，但 S2 沒有一項顯著偏向 Agent。H1 的對照是 FIRST_RED，所以 H1 成立只能寫「超過顏色啟發法」，不能寫「優於規則」 |
| **閉迴路不劣於 B1，但單點沒有更好** | H2 `SUPPORTED`，H1a–d 都不 `SUPPORTED` |
| **資訊不足** | 在某一級 k：模型@k 與 NEAREST_RED 差異不顯著（S2 調整後 p ≥ 0.05，且差距 < 5 個百分點），而且所有模型、所有級、所有底線的「任一答對」聯集，在可回答的點（排除偵測漏掉）上 < 0.80 |
| **模型太小（或用不上資訊）** | NEAREST_RED 在 L2 或 L3 顯著優於該模型（S2 方向偏向規則），或同一級 qwen7b − qwen3b ≥ +10 個百分點；而且該模型在 L2／L3 選第 1 個候選的比例仍 > 50% |
| **無法判斷** | 以上都不成立 |

### 5.6 有效性閘門

| 代號 | 檢查 | 失敗時 |
| --- | --- | --- |
| G1 | 116 個決策點都在 B1 b-log 找得到 T−1 與 T 的列（V1），B1 重現 28/28（V2） | 停 |
| G2 | GT 掃描與打包閘門 PASS（V5） | 刪包重做 |
| G3 | KEEP 解析 100% 成功：B1 在 T 有顯示時都對得到候選（V4） | 停 |
| G4 | 每格（模型 × 級）的格式退回率 ≤ 20% | 標 `FORMAT_INVALID`，照算錯，但不能用來支持 H1 |
| G5 | 標籤表的 116 個 base id 都對得到請求 | 停 |
| G6 | Mac 用 GT 分群重選的 SELECTED（模型, 級）有第二部分結果（#785 O2，採 A） | `e8_score_run.py` 以狀態 3 結束，結果 JSON 與 md 頂端寫 `SELECTED_GROUP_MISSING` 並列出缺的組；照 `E8_REPRO_20261128.md` §2.1 在 Colab 補跑後重評。不改用暫定組（那等於事後改預登） |

### 5.7 限制（#785 審查 O1、O3，N1）

- **第二部分的組別由第一部分的暫定分數挑選（O1）。** Colab 第 7 格只讀標籤表（D417 折衷：只有答案編號、沒有框），用它暫定每個模型的 k* 與 SELECTED，決定第二部分跑哪些組。標籤只影響「跑哪一組」，不進任何請求。Mac 用 GT 分群重選；兩者不同時由 G6 擋下。
- **選組偏差（O3）。** SELECTED 是在同一批決策點上依第一部分準確率挑出，再用來檢定第二部分的 H2，因此偏向通過 H2。H2 在主族 Holm 只算一次、S3 在次族，方向也不同（非劣性對優越性），所以不另加校正。但結果會列出四個模型組各自的第二部分指標與 H2／S3／S4（未校正，標為敏感度，`sensitivity_model_groups`），結論只依 SELECTED。
- **合併選項的分數（N1）**：見 §2.4。

## 6. Colab 包與 notebook

### 6.1 包（`scripts/evaluation/build_e8_colab_pack.py`，產出 `e8-colab-pack.zip` 加 `.zip.sha256`）

```
requests/e8_part1.jsonl            e8_level_request_v1（每筆 = dp × level × perm；laya／VLM 在 Colab 渲染）
part1/frames/<case>/<tick>/<cam>_<perm>.jpg   L4 畫面（框上標代號，Mac 先畫好）
part1/ref/<case>.jpg               種子參考裁切
part2/ticks/<case>.jsonl           逐 tick 偵測（bbox、score、HSV 顏色、地面座標），不含 GT
part2/b1_frozen/<case>.json        凍結 B1 b-log（重現閘門的期望值）
part2/scene_context.json、cameras.catalog.json
scoring_only/answer_table.json     第一部分的標籤表
PACK_INFO.json、MANIFEST.sha256
```

不含第二部分的畫面，預估約 0.1–0.2 GB。規格同步寫進 `E7_COLAB_UPLOAD_PACK_SPEC_V1.md` 的 E8 章節。

### 6.2 Notebook（`notebooks/e8_colab_eval.ipynb`，格子結構同 E7）

| 格 | 內容 |
| --- | --- |
| 0、1、1B、2、3、4 | 同 E7：說明、設定（模型與 HF revision 釘選：laya `246177e5…`、Qwen-3B `66285546d2b821cf421d4f5eb2576359d3770cd3`、Qwen-7B `cc594898137f460bfe9f0759e9844b3ce807cfb5`）、clone 釘選 commit、安裝並檢查版本一致、硬體紀錄、解 zip 並驗 MANIFEST |
| 5 | `e8_colab_run.load_pack`（G5）；每筆請求過 `arms.reject_forbidden` |
| 6 | 第一部分推論（`run_group`），以 (模型, 級, 順序) 為一組寫 checkpoint，可續跑；只跑本輪的模型（`RUN_MODELS`），一次只有一個模型在 GPU 上（`with_backend`，§6.3.1）；每個 Qwen 模型先量前 20 筆的時間，本輪剩下的工作預估超過 4 h 就套 §6.3 規則；laya 每筆記錄附截斷稽核 `laya_truncation`（V6） |
| 7 | 第一部分評分（唯一可以讀標籤表的格）：總表、H1a–d、圖、選組；選組讀所有輪的第一部分 checkpoint |
| 8 | 第二部分：先跑 B1 重現閘門（`b1_gate`，任一段失敗就停），再跑 FIRST_RED、NEAREST_RED、本輪各模型在選定級，最後選定模型的 MEASURED；每組寫一個 checkpoint（`run_part2_group`），已有 checkpoint 的組不載入模型 |
| 9 | 打包 `e8-run-<日期>-<RUN_LABEL>.zip`（輸出、所有輪的 checkpoint、`RUN_NOTES.json` 與前幾輪的 `RUN_NOTES_<輪>.json`、`e8_l0_rule.json`、偏離、`memory_log`） |

### 6.3 預估執行時間（必改 3 重估；實測記在 RUN_NOTES）

E7 的 Qwen-3B 用 E7 格式（輸出上限 256 token），p50 是 5.4–6.0 s／筆。Qwen 的時間主要花在生成 token，所以 L0 照 E7 估；其他級的輸出約 20 token。7B 估為 3B 的 1.4–1.6 倍（A100）。

| 項目 | 筆數 | 估計每筆 | A100 |
| --- | ---: | --- | --- |
| 安裝與下載模型 | — | — | 約 15 min |
| laya 兩版（全部級） | 3,480 | 約 40 ms | 約 3 min |
| Qwen-3B L0 | 348 | 5–6 s | 約 30–35 min |
| Qwen-3B L0c–L3 | 1,392 | 0.6–1.0 s | 約 15–25 min |
| Qwen-3B L4（多張圖） | 348 | 2–3 s | 約 12–17 min |
| Qwen-7B L0 | 348 | 8–9 s | 約 45–55 min |
| Qwen-7B L0c–L3 | 1,392 | 1.0–1.5 s | 約 25–35 min |
| Qwen-7B L4、L3F（長輸入） | 696 | 2.5–3.5 s | 約 30–40 min |
| 第二部分（2 個規則組＋4 個模型組＋1 個 MEASURED） | 約 400–1,400 次觸發／組 | 同上 | 約 45–75 min |
| **合計** | | | **約 3.7–4.9 h** |

**4 h 規則（預登）**：notebook 第 6 格量完每個 Qwen 模型的前 20 筆後，用實測中位數重算整本的預估時間。A100 上預估超過 4 h，就把 Qwen 的 L0 減為只跑 `p0`（3B、7B 各少 232 筆，約省 50–60 min），寫進 `RUN_NOTES.json` 的偏離。Qwen L0 不在主要假設內，所以這樣減不影響 H1／H2；L0 的順序偏差只用 laya 量。依目前估計，這條規則很可能會觸發。SMOKE 後在本機也會記錄 stub 的時間，但 CPU 時間不能代表 GPU。**GPU 不是 A100 時**（例如 L4），照常執行，4 h 規則用這張 GPU 的實測時間判斷；`RUN_NOTES.json` 記下 GPU 型號，`e8_score_run.py` 把它寫進結果的 `run_deviations`。

### 6.3.1 GPU 記憶體與分輪（L4，2026-11-28）

2026-11-28 使用者在 Colab L4（22 GB）上跑，第 6 格量完 Qwen-3B、載入 7B 時 OOM。原因是舊版 notebook 的 `free(fn)` 只刪掉函式裡的區域名稱，模組層級的 `raw`、`fn`、`ask`、`audit` 和 builder closure 裡的 `cache`（processor、模型）都還留著 3B。

**釋放**（只改 notebook，pin `62981f08` 不變）：
- 每個模型只在 `with_backend(cfg, phase, work)` 裡載入；模組層級不留任何指向模型的名稱。
- 用完由 `release_backend` 清掉 `model_caches(fn)` 找到的 `cache` dict（`build_qwen_vl_inference_fn` 的 processor 與 `(processor, model, device)`；laya 的 API 模組與 RLAgent），再 `gc.collect()`、`torch.cuda.empty_cache()`。
- 釋放後 `torch.cuda.memory_allocated` 超過 `MEM_RELEASE_MAX_GIB`（1 GiB）就停下。每次的峰值和釋放後的用量記進 `RUN_NOTES.memory_log`。
- OOM 的例外在 `except` 區塊外才清快取，這樣 traceback 裡的張量已經放掉。
- `tests/evaluation/test_e8_notebook_memory.py` 用真的 builder closure 測這一段（§7.1）。

**7B 在 22 GB 上的估計**（transformers 4.53.3、bf16）：
- 權重：8.29B 參數，約 15.4 GiB。
- 文字級（L0–L3）：一張參考圖加少量文字，活化值不到 1 GiB，預估峰值約 16.5 GiB，放得下。
- L4：一筆請求有 8 張圖（7 張 960×540 的畫格加參考裁切），合計約 18.3k 個視覺 patch。Qwen2.5-VL 的視覺注意力對所有圖的 patch 建一個完整的 4D mask，約 1.3 GiB。
  - SDPA 用 memory-efficient kernel 時，峰值約 17–18 GiB，放得下。
  - 退回 math kernel 時，注意力分數本身就約 10.7 GiB，會 OOM。
  - 用哪個 kernel 由執行期決定，所以 L4 **不確定**。
- L3F：一張參考圖加完整的 `scene_context` 文字，輸入比 L3 長，但沒有多張圖，預估放得下。為了保險也列入退路。

**退路（預先寫定，不臨時改設計）**：
- `OOM_FALLBACK_LEVELS = ("L4", "L3F")`。在這兩級 OOM 時，該模型的該級本輪跳過，記偏離 `[<輪>] OOM on <GPU>: <模型> <級> skipped`，列在 `RUN_NOTES.oom_skipped`。
- 可以用 A100 另跑一輪補上：同一個 `OUTPUT_DIR`，`RUN_MODELS = ["qwen7b"]`。
- 沒補上的話，S1（qwen7b L4−L3）記為 MISSING，評分列在 `part1_missing_groups`。H1 用 L2／L3，選組只在有紀錄的級之間選，所以都不受影響。
- 在其他級或載入時 OOM，notebook 停下，回報協調者。

**分輪**（REPRO §1.1）：
- 同一個 `OUTPUT_DIR` 可以分幾輪跑，每輪設不同的 `RUN_LABEL`，例如 L4 上第一輪跑 laya 兩版和 3B，第二輪跑 7B。
- fingerprint 各輪相同，checkpoint 檔名不重疊，所以各輪互相續跑、不互擋。
- 4 h 規則每輪只算本輪的模型和還沒做的組，依模型記在 `e8_l0_rule.json`，之後各輪沿用。
- 第 7 格的選組讀所有輪的 checkpoint；Mac 端照 G6 用全部模型重選。
- `e8_score_run.py --run` 可以給幾個 zip，同名的 checkpoint 以後面的為準；只給最後一輪的 zip 也得到相同結果。

### 6.3.2 第二部分的投影算術（B1 閘門在 Colab 停下，2026-11-28）

2026-11-28 使用者在 Colab 跑到第 8 格時，B1 重現閘門（G1／V2）停下：28 段裡只有 3 段一致。

**根因**：`tracker.Projector.ground` 用 numpy 的 `M[:3, :3] @ d_cam` 把畫面上的腳點投到地面。這個 3×3 乘法走平台的 BLAS，各平台的加總順序和 FMA 用法不同。B1 b-log 是在 Mac（arm64）上凍結的，Colab 是 x86_64，兩邊的 `est_xy` 會差在最後一個位元，而閘門逐欄完全比對 `tracking`。

**在 Mac 上重現**（完整 pack）：
- 只把這一步的加總順序反過來（或改成 x86 BLAS 式的 FMA 累加），數學不變，閘門就從 28/28 掉到 2/28。
- 過的那 2 段是 E6-S04、E6-S07，兩段全程都是 `NEEDS_PICK`、沒有 `est_xy`，正好對上 Colab 通過的那幾段。
- 照從左到右的順序用純 Python 浮點數算，閘門 28/28，而且 34,247 次投影和 Mac numpy 的結果逐位元相同。

**修正**（只改 notebook，pin `62981f08` 不變；不跳過、不放寬閘門）：
- 第 8 格在跑閘門前，把 `tracker.Projector.ground` 換成 `ground_ieee`：數學相同，加總順序固定為從左到右，全用 Python 浮點數。IEEE-754 在每種 CPU 上對它的結果都相同。
- 用 Rosetta 跑 x86_64 的 CPython，抽 685 次投影，結果和 arm64 逐位元相同。
- 閘門和第二部分的每一組都用這個算術；第一部分不做投影（請求在打包時已算好），所以不受影響。
- 換用的事記成偏離，寫在 `RUN_DEVIATIONS`，並在 `RUN_NOTES.projector_arithmetic` 記 `ieee_left_to_right`。
- 測試：`tests/evaluation/test_e8_notebook_projector.py`。

**算不算 G1 的偏離**：G1 本身照預登執行，28/28 完全一致，標準沒有改。這是「環境差異導致重現失敗，以 notebook 固定算術修正」，要在結果的偏離裡寫明：換用的事、根因，以及 Mac 上的等價證據（第一次在 Colab 停下的紀錄也保留）。

### 6.4 回 Mac 一條指令

```bash
python scripts/evaluation/e8_score_run.py --run local/evidence/e8-run-<日期>/e8-run-<日期>.zip \
  --pack local/evidence/e8-pack-20261128/pack --mac-index local/evidence/e8-pack-20261128/mac_index.json \
  --out local/evidence/e8-run-<日期>/score --unified
```

`--mac-index` 是打包時寫在包外的決策點索引，只在 Mac。這條指令會：用 GT 補判 OWN_BOX、判出 TRUE_DEPARTURE，產生第一部分分層表；產生第二部分 28 段 × 各組的指標，以及 H2、S3、S4；經 `generate_unified_analysis.py`（`e8` 區段）與 `report/figures/build_figures.py` 出圖；輸出 `E8_RESULTS_<日期>.json` 和 `.md`。重現指令寫在 `docs/operations/E8_REPRO_<日期>.md`。

## 7. 測試與驗證點

### 7.1 Focused 測試（只跑這些，加上 `git diff --check`）

| 測試檔 | 測什麼 |
| --- | --- |
| `tests/evaluation/test_e8_requests.py`（11 項） | 合併規則；3 種順序；各級欄位嚴格遮蔽；L0 與 E7 渲染相同；laya 選項文字；`parse_e8_answer`；KEEP 解析；底線策略；模型接合與截斷；**重複定義掃描**（必改 1，含 `e8_colab_run`、`e8_score_run`） |
| `tests/evaluation/test_build_e8_colab_pack.py`（6 項） | 快照欄位只有 §2.2 規定的那些；KEEP 對到候選；假 GT 進不了任何請求；閘門失敗時整包刪除；3 種順序可重現；標籤表不受順序影響 |
| `tests/evaluation/test_e8_score.py`（7 項） | 判分真值表；多數決與底線組；H1 的家族配對與狀態；選組與同分規則；H2 的容許值；提早切對、§5.5 結論、union answerable、`unified_section`；兩個模型對同一 request_id 答 OWN_BOX 時各自保留 |
| `tests/evaluation/test_e8_score_run.py`（6 項） | Mac 評分：SELECTED 缺第二部分結果時列出缺的（模型, 級, 延遲）並以狀態 3 結束、md 頂端警告與補跑指示（G6）；四個模型組的敏感度表；「限制」段；OWN_BOX 補判以模型區分；`RUN_NOTES` 的 GPU 偏離依輪分開；兩輪的 checkpoint 合併後不重複計算，缺的第一部分組列出 |
| `tests/evaluation/test_e8_notebook_projector.py`（3 項） | 第 8 格的 `ground_ieee` 和 `tracker.Projector.ground` 數學相同，且逐位元等於固定順序的參考算式；換用在 `b1_gate` 之前並記成偏離；`b1_reproduced` 仍逐位元比對（差 1 ulp 就失敗） |
| `tests/evaluation/test_e8_notebook_memory.py`（5 項） | notebook 第 6 格的 `with_backend`／`release_backend`：Qwen 與 laya builder `cache` 裡的模型在用完後被釋放（weakref 失效），工作丟例外時也釋放；provenance 不受影響；釋放後 GPU 仍佔用超過上限就停下；模組層級沒有 `raw`／`fn`／`ask`／`audit` |
| `tests/evaluation/test_e8_colab_run.py`（3 項） | 分組與 Qwen L0 只跑 p0 的規則；`projected_hours`；checkpoint 續跑與指紋不同時重跑；SMOKE 替身可解析 |
| `tests/evaluation/test_e8_handoff.py`（5 項） | 觸發條件與間隔；SELECT／NOT_VISIBLE／無效回答的套用；MEASURED 的 chain 與 EXPIRED；不掛決策器時和 `e3_f4_run.replay` 一致 |
| `test_e7_decider_eval.py`（加案例） | 已渲染輸入的入口；E7 的舊測試全部照舊通過 |
| `test_aol_zero_latency_and_unified_analysis.py`、`tests/report/test_report_skeleton.py`（加案例） | `e8` 選填區段；沒有 E8 的舊輸入照舊；新圖在 headless 下可產生 |
| GT 隔離 | E8 推論端程式碼（`e8_requests`、`e8_handoff`、`e8_colab_run`）不 import 評分端模組（AST 掃描） |

### 7.2 驗證點

| 代號 | 內容 | 在哪裡跑 |
| --- | --- | --- |
| V1 | 116 個決策點的 B1 T−1 與 T 列都存在 | Mac |
| V2 | B1 重現 28/28 段 | Mac＋Colab 第 8 格 |
| V3 | L0 請求和 E7 逐 tick 請求（`8568e4fa…`）在同一 tick 逐位元組相同（E3 68 點） | Mac |
| V4 | KEEP 解析 100% 成功 | Mac |
| V5 | `verify_colab_pack_pre_upload` PASS；所有請求通過 `_scan_forbidden_gt_fields` 和 `arms.reject_forbidden` | Mac |
| V6 | laya 截斷稽核有產出 | Colab 第 6 格 |
| V7 | SMOKE：本機 CPU、stub 決策器、E3-A1＋E6-S01，跑完整個 notebook，再跑完 Mac 一條指令 | Mac |
| V8 | 探索：E8 的 L0 laya 答案和 E7 逐 tick 答案（`2e23f37a…`）的一致率 | Mac |

## 8. 決定紀錄與分支狀態

| # | 問題 | 決定（#780 審查留言 7225171977） |
| --- | --- | --- |
| Q1 | 第二部分要不要包含 L4 | 不要 |
| Q2 | 新增 L0c、L3F | 加 |
| Q3 | 第一部分的快照 | B1 凍結狀態；E6 單點另報，不填 E6 判定；#765 的 R-N 版延後 |
| Q4 | H2 錯人秒的容許值 | +14.0 s（預登後不再改） |
| Q5 | 主要比較對象 | laya_typed、qwen7b |
| Q6 | 第二部分的順序 | 只用 `p0` |

**分支狀態**：`claude/feat-e8` 從 `179bccb7`（`claude/feat-e7-laya`）切出。#769 已合併進 main（merge commit `e17a0787`，程式 `cd41eaa1`），`claude/feat-e7-laya` 已刪除；本分支以合併 commit `e1e83ef0` 併入 #769 的修正後 head `e3e1dc02`（經 `refs/pull/769/head`，內容等於 main 上的 #769），沒有 rebase 或 force。之後要跟上 main 時同樣用合併 commit。

## 9. 每個數字的出處

| 數字 | 出處 |
| --- | --- |
| E7：多錯 261.2 s、其中錯鏡頭 207.0 s；72%／65%；2,058／2,037／2,516（／5,120）；`image_paths` 全空 | `docs/evaluation/E7_LAYA_ANALYSIS_20261128.md`；#767 協調者留言 |
| laya 512／1024、192／256；截斷規則 | HF `convaiinnovations/laya` @`246177e5` 的 `rl_agent_config.json`、`typed-decisions/rl_agent_config.json`、`rl_common.py`（`8d83611d…`，等於審核值）、`rl_agent_api.py`（`be3b4681…`）；#767 留言 7225282921 |
| 68＝38＋30；E3 type；E3 家族 A–D | 兩份 E3 `CORPUS.json` |
| 48（VISIBLE 43、FULL_BLIND 5）；E6 type 24 種；E6 家族 12 個 | `e6_scenarios_frozen_v1.json` `5bab2766…`；E6 執行紀錄 R0 |
| 候選 6／12／22；紅色中位數 4；4 m 內的紅色分佈；B1 T−1 狀態 52／9／7 | LOCAL `e8-design-20261128/e8_design_dpstats.out.txt` `e0871687…` |
| 觸發估計 377（28 段、7,058 tick） | LOCAL `e8-design-20261128/e8_design_trigger_estimate.out.txt` `96fd0b86…` |
| scene_context 19,589 字元、`3072cc5a…` | `e3_f4_run.live_scene_context`（本 session 在 `179bccb7` 上執行），與 B1 b-log 欄位相同 |
| 釘選檔案（arms.py、decider.py、e6_arms_v1.json、E6 預登） | `scripts/evaluation/e6_select_arm.py` 的 `PROMPT_FILES` |
| Qwen p50 5.4–6.0 s（E7 格式） | 協調者共享筆記 `767_replay_design.md` §2 |
| Qwen-7B 為 3B 的 1.4–1.6 倍、L4／L3F 每筆 2–3.5 s | 估計值，本文件新定；實測後寫入 RUN_NOTES |
| laya GPU 約 40 ms／筆 | #767、D416 |
| H2 容許值 0.05／5.0 s | E6 預登 §4（C2、C4）；+14.0 s 是本文件新定（Q4） |
