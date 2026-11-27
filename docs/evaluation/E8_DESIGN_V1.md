# E8 設計與預登 v1.1：Agent 與規則公平對照（資訊逐級、交接點決策、一鍵 Colab）

> 狀態：**設計稿 v1.1，待協調者確認（D415 第 1 級）**。確認前不寫程式、不打包、不跑推論。
> v1.1 相對 v1（`d4cebd12`）的改動：照協調者轉達的使用者硬規則「既有程式、文件、issue 先盤點並沿用」（#780 盤點留言 https://github.com/Polalalabear/amidst/issues/780#issuecomment-7225122349），新增 §1.2「沿用與修改清單」。第一部分改成擴充 #765：凍結快照用 R-N 前一 tick，判分用 `e6_verdict.single_dp_correct`，統計單位改為家族。所有程式改動都放進既有的 E7／E6 檔案，作為新增模式。
> Issue：[#780](https://github.com/Polalalabear/amidst/issues/780)（W1；W3、W4 的規格也寫在這裡）。決策：D416、D417（#93）。前因：#767 協調者分析，實作階段會整理進 repo，成為 `docs/evaluation/E7_LAYA_ANALYSIS_20261128.md`。
> 作者：Claude Opus 5.5（E8 子 session），2026-11-28。身分一律 `UNCONFIRMED`；實體可通行性 `UNKNOWN`。本機模型零 API 費用；GPT 組由 Codex 擴充 `e6_arms_run.py` 另做（#781），獨立複核在 #782。

## 0. 目的與前因

研究問題：**Agent 能否加快切換鏡頭的決策，並在複雜情況下優於規則 B1。** E5、E6（P2 `NOT_SUPPORTED`）、E7 都是規則贏。但 E7 給 laya 的輸入比 B1 和 API Agent 都少（D416）：

- 沒有「目標是紅色」、上一個位置、地面座標、鏡頭連通和圖片（5,223 筆請求的 `image_paths` 全空）。
- laya 從不回答 `NOT_VISIBLE`，72%（laya_text）／65%（laya_typed）選清單第一個候選。
- 快照正確率約等於「永遠選第一個」（2,058 比 2,037／5,120），還輸給「選第一個紅色」（2,516）。
- 多錯的秒數八成是錯鏡頭（laya_text 比 B1 多 261.2 s，其中 207.0 s 是錯鏡頭）。

**設計時另外查到的根因（§2.6）**：laya 是 ModernBERT 編碼器加決策頭，輸入長度有硬上限：

- root 版（laya_text）：`max_len=512`、`head_max_len=192`；typed 版：`max_len=1024`、`head_max_len=256`（HF `convaiinnovations/laya` @`246177e5`，`rl_agent_config.json`）。
- `rl_common.build_sequence` 先放題目和選項；選項總長超過 `head_max_len` 時，**每個選項會被平均截短**，題目只剩下剩餘的空間，state 則從右邊截斷。
- E7 的選項文字是 `camera CAM_W1 detection D1 box [...] score 0.52`。決策點的候選數中位數 6、最多 22，加上 3 個非選人選項後，每個選項只剩約 10–20 個 token，框和分數常常被截掉。
- 結果是 laya 看到的選項幾乎只差在鏡頭名稱。所以 E8 的選項格式要針對這個上限重新設計。

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
| R-N 輸出（第一部分快照來源） | E3：`e6-rn-old16-20261127/<case>/RN_{U,N}.json`；E6：`e6-formal-run-20261127/rn/<case>/RN_{U,N}.json` | E6 `rn/` 樹雜湊 `e4da4b6d…`（E6 執行紀錄 R0.1）；E3 的打包時記入收據 |
| B1 b-log | E3：`f4-658-20261122/runs-final-{9,665}/<case>/B1.k1.json`；E6：`e6-formal-run-20261127/b1/<case>/B1.k1.json` | E6 `b1/` 樹雜湊 `90920606…cb7e5cc` |
| 凍結偵測與 RGB | E3：`e3-652-20261122`、`e3-reappearances-20261122`；E6：`e6-formal-det-20261127`（`e6_rule_neutral.observations`／`e3_f4_run.load_case` 讀取時驗 SHA） | 逐檔驗證 |
| 相機目錄 | `local/data/live-assets-20261115/cameras.catalog.json` | `3eba8572…`（與 B1、R-N 紀錄的值相同） |
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

### 1.2 沿用與修改清單（硬規則：先沿用，不另做一套）

**不能改的檔案。** 下列檔案的 SHA 被 E6 凍結收據釘住（`e6_select_arm.PROMPT_FILES`），`e6_arms_run --paid` 會比對這些 SHA，所以 **E8 只 import，不改**：

- `src/amidst/live_mode/aopen/arms.py`
- `src/amidst/live_mode/aopen/decider.py`
- `configs/evaluation/e6_arms_v1.json`
- `docs/evaluation/E6_PREREGISTRATION_DRAFT.md`

`scripts/evaluation/e6_rule_neutral.py` 也不改：R-N 輸出記了它的 `code_sha256`，`E6_RN_FROZEN_20261124.md` 是協定文件。`e3_scoring.py` 同樣不改。

| 既有檔 | E8 的用法 | 為什麼不另開新檔 |
| --- | --- | --- |
| `scripts/evaluation/e6_rule_neutral.py`＋`docs/evaluation/E6_RN_FROZEN_20261124.md` | **只 import**：`observations`、`seed_from_b1`、`RuleNeutral`。第一部分的快照就是 R-N（RN_U）在 T−1 的狀態（#765／E6 預登 §3.2）；R-N 在 T 的規則答案當作底線組 | #765 已規定快照用 R-N；重播出來要和凍結的 RN_U rows 逐列相同（V1） |
| `src/amidst/evaluation/e6_verdict.py` | **只 import**：`single_dp_correct`（判分）、`sign_flip_p`／`sign_flip_p_two_sided`、bootstrap、Holm、`majority`、`MIN_DP`／`MIN_FAMILIES` 門檻 | E6 的判分與統計已經寫好、也測過 |
| `scripts/evaluation/e6_verdict_run.py` | **改**：加 `--single <e8 單點結果>`，填入 E6 12 段的 `single_correct`（目前寫死 None），輸出 `single_dp_acc` 與 McNemar；完整追蹤的判定不變 | #765 要補的就是這一段 |
| `scripts/evaluation/build_e7_colab_pack.py` | **改**：加 `--e8` 模式，產生 R-N 快照、L0–L4／L3F 請求、3 種順序、標籤表（沿用 `expected_for_tick`＋`write_colab_answer_table`）、第二部分逐 tick 偵測、L4 圖 | 同一套打包與閘門（`verify_colab_pack_pre_upload`）已有 GT 隔離與 MANIFEST |
| `src/amidst/evaluation/e7_decider_eval.py` | **改**：加 E8 模式，包括結構化請求 `e8_level_request_v1`、選項合併與代號、laya 的精簡渲染（state, questions）、Qwen 的渲染、`parse_e8_answer`、底線策略；laya／Qwen 推論函式加「直接吃已渲染輸入」的入口。E7 原有行為與測試不變 | 推論端的 laya／Qwen 載入、稽核、硬體紀錄都在這個檔裡 |
| `src/amidst/q1q5/agent_service.py`、`src/amidst/q1q5/scene_context.py`、`src/amidst/live_mode/aopen/decider.py`、`src/amidst/live_mode/aopen/arms.py` | **只 import**：`Candidate`、`gate_of`、`variable_text` 的行格式、`track_layer`；`sx.build`／`serialize`／`sha256_of`；`AOpenDecider.build_input` 的 AO_STATE 欄位（`tracking`、`neutral_status`）；`arms.reference_text`（顏色查詢句；文字級用 `NO_IMAGE` 措辭）、`arms.strip_spatial`（L0–L2 不給空間資訊時用）、`arms.static_prefix`（L3F 的完整場景前綴） | 和 API Agent、E6 arms 同格式，#781 的 GPT 組可以直接共用 |
| `src/amidst/evaluation/e7_colab_runtime.py` | **改**：checkpoint 的 fingerprint 加上 (level, perm)；E8 的 run notes 欄位 | 同一套續跑機制 |
| `src/amidst/evaluation/e7_scoring_bridge.py` | **改**：加 E8 單點判分。標籤 → `gt_regime` 對照後呼叫 `e6_verdict.single_dp_correct`；3 種順序多數決；Colab 上的表與圖 | Colab 上唯一可以讀標籤表的模組（D385） |
| `src/amidst/evaluation/e7_replay.py` | **改**：加 `E8HandoffDecider`（B1 的 `State.decider` 掛點，觸發、套用、延遲）和閉迴路驅動（沿用 `e3_f4_run.replay` 的流程與 `chain_box`） | 已經是「重播驅動加 AO 機制」的模組 |
| `scripts/evaluation/e7_replay_run.py` | **改**：加 `--e8` 模式。Mac 端以 `e3_f4_score.run_scores`（E3）和 `e6_verdict_run` 的路徑（E6）為第二部分評分；第一部分做分層 | Mac 一條指令重現 |
| `notebooks/e7_colab_decider_eval.ipynb` | **改**：加 `EXPERIMENT="E8"` 模式，格子結構不變（§6.2） | 一鍵 Run All、MANIFEST、checkpoint、硬體紀錄都已有 |
| `docs/evaluation/E7_COLAB_UPLOAD_PACK_SPEC_V1.md` | **改**：加 E8 包的章節 | 規格文件和程式同步 |
| `scripts/evaluation/generate_unified_analysis.py`＋`configs/evaluation/unified_analysis_schema_v1.json` | **改**：加選填的 `e8` 區段（schema 頂層 `additionalProperties:false`，所以要加一個選填屬性；舊輸入不受影響） | 報告管線的唯一入口（#734） |
| `report/figures/build_figures.py`、`FIGURES.md`、`manifest.json` | **改**：加 E8 圖（資訊階梯、位置偏差、閉迴路錯誤拆分、提早切對分佈） | 同一條出圖管線 |
| 既有測試：`test_build_e7_colab_pack.py`、`test_e7_decider_eval.py`、`test_e7_colab_runtime.py`、`test_e7_replay.py`、`test_e6_verdict_run.py`、`test_aol_zero_latency_and_unified_analysis.py`、`tests/report/test_report_skeleton.py` | **加測試案例**，不另開測試檔 | 測試和被改的模組放在一起 |
| `scripts/evaluation/e6_arms_run.py` | 不改（#781 由 Codex 擴充）。E8 包裡的 `e8_level_request_v1` JSONL 就是共用輸入（§2.7） | 分工：GPT 組在 #781 |

**新增的檔案只有三份文件**：本文件、`docs/evaluation/E7_LAYA_ANALYSIS_20261128.md`（協調者要求把 LOCAL 分析收進 repo）、`docs/operations/E8_REPRO_<日期>.md`（重現指令，AGENTS.md 規定交接文件要進 repo）。W2 離線腳本（`e8-offline-b` session）若是新檔，收進 PR 時會說明為什麼不能放進既有檔。

**Issue 對應**：第一部分的本機模型組完成 #765 的本機部分（GPT 部分見 #781，兩者都完成後再關 #765）；E7 分析補記到 #727，並連到 #767；本 issue 是 #732（E6 正式執行）的下一輪，範圍不重疊。

## 2. 第一部分：單點對照（開迴路，擴充 #765）

### 2.1 題目

| 資料集 | 段數 | 家族 | 決策點 | 既有分層標籤 |
| --- | ---: | ---: | ---: | --- |
| E3（F4 #658 凍結語料） | 16 | 4（A–D） | 68 | 決策點 `type`（16 種；REAPPEAR 33 個） |
| E6（正式 12 段） | 12 | 12 | 48 | `type`（24 種）、`gt_regime`（VISIBLE 43、FULL_BLIND 5；只在 Mac 分層） |
| 合計 | 28 | 16 | **116** | 沒有標籤的情境寫 `UNKNOWN`，不新造標籤 |

設計期量到的 E3 68 點（`e8_design_dpstats.out.txt`；以 B1 的 T−1 狀態算，R-N 版打包時重算）：

- 每點的候選數：中位數 6、p90 12、最大 22。
- 紅色候選數：中位數 4、最大 18。
- 估計位置 4 m 內的紅色框：0 個的 14 點、1 個的 18 點、≥2 個的 36 點。
- E6 的同樣統計要在打包時才算，目前 `UNKNOWN`。

### 2.2 凍結快照（照 E6 預登 §3.2 與 `E6_RN_FROZEN`）

每個決策點的時間記為 T。打包器（Mac）用 `e6_rule_neutral.observations`＋`seed_from_b1`＋`RuleNeutral`，從 B1 的第一次 ACQUIRE 種子重播 RN_U 到 T−1，並檢查每一列都和凍結的 `RN_U.json` rows 相同（V1）。快照欄位只用 §3.2 規定的那幾個：

- `last_known_cam`、`last_known_xy`、`last_known_tick`（`RuleNeutral.last_xy`／`last_xy_tick`，以及當時的 active cam）、`lost_ticks`、`last_box_xyxy`、`neutral_status`；
- T 時刻的凍結偵測（含 HSV 顏色）；
- T 時刻的 RGB（只給 L4）；
- 種子參考裁切（B1 第一次 ACQUIRE 的框，用 `advisor.crop_jpeg` 裁切）。

E6 預登 §3.2 禁止的欄位一律不放，也不放任何 GT 欄位。B1 沒有 ACQUIRE 的段（D405 `NO_B1_ACQUIRE`）沒有快照，那些點記 `NO_SEED`，所有組都算錯，照 E6 的慣例。

### 2.3 答案空間與「實際顯示」

| 答案 | 意義 | 解析成的實際顯示 |
| --- | --- | --- |
| `KEEP` | 維持 R-N 目前的目標（等於 AO 的 UNCERTAIN） | 從 T−1 狀態只做 `NeutralTracker` 在 T 的延續（不套用新答案）；有框就是該框，沒有就不顯示 |
| `SELECT`＋選項代號 | 選一個候選 | 該選項的代表框 |
| `NOT_VISIBLE` | 所有鏡頭都看不到 | 不顯示 |

判分（§2.9）用 `e6_verdict.single_dp_correct(gt_regime_T, answer, hit_gt=...)`。對照方式：

- 實際顯示是一個框 → `answer='SELECT'`，`hit_gt`＝該框命中標籤；
- 回答 `NOT_VISIBLE` → `'NOT_VISIBLE'`；
- KEEP 但沒有顯示 → `'UNCERTAIN'`（真離場時必須明講 NOT_VISIBLE，這比較嚴）；
- 格式錯誤 → `None`，算錯。

### 2.4 候選與選項

- **候選**：T 時刻所有 person 偵測（score ≥ 0.15，CAM_ENTRY ≥ 0.05，任何顏色），`detection_id` 依各鏡頭編成 D1…Dn（同 E7 的 `candidates_for_tick` 和 `AOpenDecider.build_input`）。
- **跨鏡頭合併**（L0c 以上）：不同鏡頭的框投影到地面後相距 < 1.5 m，就合成一個選項；同一台鏡頭的框絕不合併。代表框取框高最大的成員（同 `Tracker.update` 的換鏡規則），顏色取聯集，投影失敗的框不合併。L0c 到 L4 的選項集合完全相同；L0 照 E7 原樣，不合併。
- **代號**：依當次順序給 A、B、C…；`KEEP`、`NOT_VISIBLE` 固定排在最後。
- **3 種順序**：
  - `p0`：標準順序，相機的凍結順序，再依 D 編號；
  - `p1`：`p0` 反轉；
  - `p2`：`random.Random(f"20261128|{request_base_id}")` 打亂。
  - 只打亂候選。標籤以 (鏡頭, D) 表示，不受順序影響。

### 2.5 資訊逐級增加（累加）

| 級 | 新增資訊 | 給誰 |
| --- | --- | --- |
| **L0** | E7 現況，逐位元組照 E7 的請求（`build_e7_colab_pack.variable_text` 加上 `build_laya_state_and_questions`／`assemble_ao_prompt`）。答案對照：`UNCERTAIN`、`STILL_HERE_OCCLUDED` → KEEP；`OWN_BOX` → Colab 記 `NEEDS_MAC_SCORING`，回 Mac 用 GT 框補判（同 E7） | 全部模型 |
| **L0c**（格式對照） | 資訊與 L0 相同（鏡頭、分數、框），改用 E8 精簡格式與合併後的選項 | 全部模型 |
| **L1** | 顏色查詢句（`arms.reference_text('red', 'NO_IMAGE')`）＋每個選項的顏色；VLM 另外附 `gate_of` 的顏色閘門（只當資訊） | 全部模型 |
| **L2** | R-N 快照的上一個可靠位置：鏡頭、地面座標、距今幾秒、`neutral_status`（同 AO_STATE）；每個選項到該位置的地面距離（m） | 全部模型 |
| **L3** | 鏡頭連通的精簡摘要（從 `scene_context` `3072cc5a…` 推出）：每個選項的鏡頭相對上一個鏡頭是 `same`、`adj`（graph v3 有 transition）、`ovl`（`overlap_iou` ≥ 0.05）還是 `other`；state 另列相鄰鏡頭、重疊鏡頭，以及上一個位置到各鏡頭地面覆蓋區的距離（同 B2／F2 的空間排序） | 全部模型 |
| **L4** | 種子參考裁切＋T 時刻各鏡頭畫面，框上標選項代號（`service_decider._jpeg` 畫框） | 只給 VLM |
| **L3F**（探索性） | L3 改成完整 `scene_context`（`arms.static_prefix` 的場景前綴，同 E6 arms 與 API Agent） | 只給 Qwen-7B |

- L0c 用來把格式效果（含合併）單獨量出來，這樣 L1−L0c、L2−L1、L3−L2、L4−L3 才是單純的資訊效果。這是相對 brief 的**增項**。
- L3 用摘要，因為完整 `scene_context` 約 19.6k 字元，laya 根本放不下；為了讓各模型能比較，全部模型都用同一份摘要。

### 2.6 laya 的放法

laya 的輸入順序是：

```
[CLS] 題目 [SEP] [MASK]選項1 [MASK]選項2 … [SEP] state [SEP]
```

選項區（題目＋選項）≤ `head_max_len`（192／256），全部 ≤ `max_len`（512／1024），state 從右邊截斷。因此：

- **題目只放一句短句**：L0c 是「Which option is the tracked person now?」；L1 起是「Which option is the red-clothed tracked person now?」。
- **選項文字最重要的放前面**，每個選項目標 ≤ 10 個 token：

  | 級 | 候選 | KEEP | NOT_VISIBLE |
  | --- | --- | --- | --- |
  | L0c | `A: W1 .52` | `KEEP: keep current target` | `NOT_VISIBLE: not visible in any camera` |
  | L1 | `A: red W1 .52` | 同上 | 同上 |
  | L2 | `A: red 1.2m W1 .52` | `KEEP: keep current target W1` | 同上 |
  | L3 | `A: red 1.2m W1 same .52` | 同上 | 同上 |

- **state 是有順序的 JSON，被截斷時先丟後面的**：
  1. `target`（L1 起）
  2. `last`（L2 起，例如 `W1 (12.8,1.9) 0.4s ago, FOLLOWING`）
  3. `options`（每個選項一行，L2 起加地面座標與距離，L3 起加鏡頭關係）
  4. `graph`（L3 起）
  5. `now_s`
- **截斷稽核**：notebook 推論前用 laya 自己的 tokenizer 計算每筆請求，記錄「選項被平均截短」和「state 被截斷」的比例（分模型、分級）。這是要報告的共變量，不是停止條件（V6）。

### 2.7 共用的結構化請求與 VLM 渲染

- 打包器為每筆 (dp, level, perm) 寫一列 **`e8_level_request_v1`**（JSONL）。欄位：`request_id`、`case_id`、`tick`、`level`、`perm`、`options[]`（代號、成員 (cam, D, box, score, colors, ground_xy)、代表框）、`snapshot`（§2.2 的欄位，依級別遮蔽）、`scene_summary`（L3）、`image_refs`（L4）。laya、Qwen 和 #781 的 GPT 組都從這份檔渲染，資訊相同，只是格式不同。
- Qwen 的渲染：
  - 系統文字沿用 `agent_service.SYSTEM_TEXT` 的身分、閘門與棄權條款，答案格式換成 E8 的 `{"answer":"SELECT"|"KEEP"|"NOT_VISIBLE","option":"A"|null,"confidence":"low"|"medium"|"high"}`，`max_new_tokens=48`。L0 例外，用 E7 原樣，256 token。
  - 追蹤層用 `track_layer` 的文字（L4 附參考裁切）。
  - 每個選項一行，用 `agent_service.variable_text` 的行格式（`Candidate`＋`gate_of`）；L2 起附 AO_STATE（`tracking`、`neutral_status`）。
  - 貪婪解碼，沿用 `build_qwen_vl_inference_fn`。

### 2.8 組別（每格 116 點 × 3 種順序 = 348 筆請求）

| 組 | 資訊 | 請求數 | 說明 |
| --- | --- | ---: | --- |
| B1（B1 在 T 實際顯示） | 參考 | 0 | 不受快照影響，和完整追蹤的 B1 對照 |
| RN_U、RN_N（R-N 規則在 T 的答案：紅色、投影有效、離 `last_known_xy` ≤ 4 m 中最近的一個；沒有就 UNCERTAIN／NOT_VISIBLE） | L2 | 0 | #765 的「規則轉接層」。重播 RuleNeutral，在 T 強制一次提問取得答案，不改 `e6_rule_neutral.py` |
| FIRST（第一個候選）、FIRST_RED（第一個紅色，沒有就 NOT_VISIBLE） | L0c／L1 | 0 | 3 種順序都算 |
| RANDOM（從候選和 NOT_VISIBLE 中均勻抽，seed `20261128\|request_id`） | — | 0 | 另報理論期望值 |
| laya_text、laya_typed | L0、L0c、L1、L2、L3 | 各 1,740 | GPU 約 40 ms／筆 |
| Qwen2.5-VL-3B | L0、L0c、L1–L4 | 2,088 | |
| Qwen2.5-VL-7B | L0、L0c、L1–L4、L3F | 2,436 | 建議 A100；L4 GPU bf16 也放得下 |

每點的主分數是 **3 種順序的多數決**（≥ 2 種對才算對），另報 3 種順序的平均。v1 的 NEAREST_RED（不設門檻）已拿掉，改用 RN_N：它是 #765 既有的規則，也只用 L2 的資訊。

### 2.9 判分

- 標籤由 `build_e7_colab_pack.expected_for_tick` 產生（Mac 讀 `gt-boxes/<case>.a-log.json`，`judge_box` primary），透過 `write_colab_answer_table` 寫入，只含 D385 白名單欄位。
- Colab 上把標籤對到 `gt_regime_T`：`SELECT`／`UNCERTAIN`（偵測漏掉）→ `VISIBLE`；`NOT_VISIBLE` → `FULL_BLIND`。
- Colab 無法分辨 `TRUE_DEPARTURE`，所以 Colab 的數字是暫定；Mac 用 GT 的 `present` 判出 T 的三種情境，以 Mac 的結果為準。
- 判分呼叫 `single_dp_correct`。偵測漏掉的點（VISIBLE 但沒有候選命中）所有組都錯，不影響配對檢定；另報這些點的「安全答案率」。
- 合併選項用代表框判分。

## 3. 第二部分：完整追蹤（閉迴路，交接點決策）

### 3.1 架構

- `e7_replay.E8HandoffDecider` 掛在 `live_mode.server.State._infer_tracking` 既有的 `self.decider.step(...)` 上，介面同 `ServiceLiveDecider`：B1 每個 tick 照常追人，決策器只在觸發點建請求、問模型、套用答案。
- 驅動沿用 `e3_f4_run.replay` 的流程與 CONFIG（gate 4 m、score .15／.05、relock 關、target red），b-log 格式也相同（`e3-f4.b-log.v1`）。
- 輸入是打包好的逐 tick 偵測，已含 HSV 顏色（Mac 端先用 `load_case`／`observations` 算好）。
- **B1 重現閘門**：不掛決策器時，28 段的 `rows[].tracking` 必須和凍結的 B1 b-log 完全相同（V2）。
- 請求和第一部分用同一個 `e8_level_request_v1` 建構函式，但快照來源換成 B1：`active_cam`、`est_xy`、`lost_ticks`、T 的顯示。

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
- 順序只用 `p0`。

### 3.4 延遲

- **主分析 `ZERO_LATENCY`**：答案在觸發 tick 當下生效。
- **次要分析 `MEASURED`**：答案在第一個滿足 `(t'−t)×0.2 s > 實測延遲` 的 tick 生效，框用 `chain_box`（IoU ≥ 0.3）從 t 串到 t'；串不起來就記 `EXPIRED`、不套用（同 E5 A3／E7 replay）。

### 3.5 組別

| 組 | 觸發點由誰決定 |
| --- | --- |
| B1 | 無（重現閘門與對照） |
| B1+FIRST_RED、B1+RN（R-N 規則：4 m 內最近的紅色） | 規則底線 |
| B1+laya_text@k\*、B1+laya_typed@k\*、B1+qwen3b@k\*、B1+qwen7b@k\* | 各模型在第一部分最好的**文字級** k\*（L0c–L3） |
| **SELECTED**（主要假設 H2） | 上面四組中第一部分多數決最高者。同分時依序比：3 種順序的平均正確率、較低的級、模型順序 laya_text < laya_typed < qwen3b < qwen7b |
| SELECTED＋MEASURED | 次要分析 |

選組在 notebook 裡自動執行。它只決定哪一組是主要組，不會進任何推論輸入；四組全部都跑。L4 是否進第二部分見 §8 Q1：E3＋E6 的 RGB 約 1.5 GB，建議第二部分先只用文字級。

### 3.6 評分（只在 Mac）

- E3 段用 `e3_f4_score.run_scores`（評分器 `acacce39…`），E6 段用 `e6_verdict_run` 的路徑（`full_track_dp_correct` 依 `gt_regime`）。另外照 E6 格式對 SELECTED 對 B1 跑 `verdict_e6`，只當次要參考。
- 指標：
  - 錯人秒，拆成錯鏡頭（`wrong_camera_s`）和鏡頭對但人錯；
  - 失聯秒、盲區誤鎖秒、跟對率（主準則與 IoU 保守準則）；
  - 決策點正確數；
  - **提早切對秒數**：對 T 時目標可見的點，比較 B1 和各組在 [T, T+3 s] 內第一個 CORRECT tick 的時間，3 s 內沒有就記 3.2 s。提早量＝B1 − 該組，依既有 `type` 分層。

## 4. GT 隔離（D417 折衷）

1. 第一部分在 Colab 只拿到 `scoring_only/answer_table.json`（D385 白名單），由 `write_colab_answer_table` 寫入。`type`、`gt_regime` 的分層只在 Mac，用 `request_id` 合併。
2. 第二部分在 Colab 沒有任何 GT；評分只在 Mac。
3. 打包閘門：`verify_colab_pack_pre_upload` 必須通過。所有請求、快照、逐 tick 偵測都要通過 `_scan_forbidden_gt_fields`；另外掃描 `gt-boxes`、`a-log` 字串，並套用 `arms.reject_forbidden`（E6 推論端的黑名單）。任何一項失敗就刪掉整包。
4. 推論端的 E8 程式（`e7_decider_eval`、`e7_replay` 的 E8 部分）不得 import `e3_scoring`、`e7_scoring_bridge` 或 `e6_verdict`，由測試檢查。
5. 快照、顏色、投影、`scene_context` 只來自 R-N／B1 紀錄、RGB、標定與設定。

## 5. 預登

### 5.1 判定用語

用 `SUPPORTED`、`NOT_SUPPORTED`、`INCONCLUSIVE`、`EXPLORATORY`（同 E6）。「無法判斷」不等於「沒有差異」。門檻沿用 `e6_verdict`：N_dp ≥ 40 且 M ≥ 8，否則 `EXPLORATORY`。E8 是 N_dp = 116、M = 16。

### 5.2 主要假設（Holm，m = 5，單尾 α = 0.05）

| 代號 | 假設 |
| --- | --- |
| H1a | laya_typed@L2 的單點正確率（多數決）> FIRST_RED |
| H1b | laya_typed@L3 > FIRST_RED |
| H1c | qwen7b@L2 > FIRST_RED |
| H1d | qwen7b@L3 > FIRST_RED |
| H2 | B1+SELECTED（ZERO_LATENCY）的完整追蹤不比 B1 差。交集－聯集檢定：跟對率差 ≥ −0.05（同 E6 C2）、錯人秒差總和 ≤ +14.0 s（28 段，每段平均 +0.5 s）、盲區誤鎖秒差總和 ≤ +5.0 s（同 E6 C4） |

統計方法：

- **獨立單位是劇本家族**（沿用 `e6_verdict`：E3 A–D 共 4 個、E6 12 個，M = 16），同家族先合併。
- H1：家族層級配對差值做單尾 sign-flip。M > 12，所以用 `random.Random(20261128)` 翻轉 10,000 次（`e6_verdict.sign_flip_p`）。附家族群集 bootstrap 95% CI（B = 10,000）。點層級的精確 McNemar 只當描述。
- H2：每個元件先平移容許值，再做單尾 sign-flip，p 取三者最大值。
- Holm 用 `e6_verdict` 的同一套。
- **敏感度**：以段為單位（M = 28）重算，只報告。

### 5.3 次要假設（Holm，m = 13，雙尾 α = 0.05）

- S1（7 項）：laya_typed、qwen7b 的 L1−L0c、L2−L1、L3−L2，加上 qwen7b 的 L4−L3。
- S2（4 項）：laya_typed、qwen7b 在 L2、L3 對 RN_N（同級資訊的規則）。
- S3：SELECTED 的錯人秒低於 B1。
- S4：SELECTED 提早切對秒數的中位數 > 0。

### 5.4 探索性（不做多重校正）

- laya_text、qwen3b；L0 與 E7 的一致率；L0c−L0；L3F−L3。
- 位置偏差：每級、每種順序選第 1 個候選的比例；3 種順序間的一致率。
- 依 `type`、`family`、`gt_regime`、候選數、截斷與否分層；N 小的分層（如 E6 FULL_BLIND n=5）只當探索。
- laya 信心門檻（和 W2 對照）；MEASURED；規則底線的閉迴路組；錯鏡頭拆分；偵測漏掉點的安全答案率；E6 格式的 `verdict_e6`。

### 5.5 事先定義的結論

| 結論 | 條件 |
| --- | --- |
| **Agent 有幫助** | H2 `SUPPORTED`，且 H1a–d 至少一項 `SUPPORTED`。S3 成立時加「降低錯人秒」，S4 成立時加「較早切對鏡頭」 |
| **資訊不足** | 在某一級 k：模型@k 與 RN_N 差異不顯著（S2 調整後 p ≥ 0.05，且差距 < 5 個百分點），而且所有模型、所有級、所有底線的「任一答對」聯集，在可回答的點（排除偵測漏掉）上 < 0.80 |
| **模型太小（或用不上資訊）** | RN_N 在 L2 或 L3 顯著優於該模型（S2 方向偏向規則），或同一級 qwen7b − qwen3b ≥ +10 個百分點；而且該模型在 L2／L3 選第 1 個候選的比例仍 > 50% |
| **無法判斷** | 以上都不成立 |

### 5.6 有效性閘門

| 代號 | 檢查 | 失敗時 |
| --- | --- | --- |
| G1 | R-N 重播和凍結 RN_U 逐列相同（V1），B1 重現 28/28（V2） | 停 |
| G2 | GT 掃描與打包閘門 PASS（V5） | 刪包重做 |
| G3 | KEEP 解析 100% 成功（V4） | 停 |
| G4 | 每格（模型 × 級）的格式退回率 ≤ 20% | 標 `FORMAT_INVALID`，照算錯，但不能用來支持 H1 |
| G5 | 標籤表的 116 個 `request_id` 都對得到請求 | 停 |

## 6. Colab 包與 notebook（擴充 E7 那套）

### 6.1 包（`build_e7_colab_pack.py --e8`，產出 `e8-colab-pack.zip` 加 `.zip.sha256`）

```
requests/e8_part1.jsonl            e8_level_request_v1（每筆 = dp × level × perm；laya／VLM 在 Colab 渲染）
part1/frames/<case>/<cam>/<tick>_<perm>.png   L4 畫面（框上標代號，Mac 先畫好）
part1/ref/<case>.png               種子參考裁切
part2/ticks/<case>.jsonl           逐 tick 偵測（bbox、score、HSV 顏色），不含 GT
part2/b1_frozen/<case>.json        凍結 B1 b-log（重現閘門的期望值）
part2/scene_context.json、cameras.catalog.json、camera_graph_v3.json
scoring_only/answer_table.json     第一部分的標籤表
PACK_INFO.json、MANIFEST.sha256
```

不含第二部分的畫面時，預估約 0.1–0.2 GB。規格會同步寫進 `E7_COLAB_UPLOAD_PACK_SPEC_V1.md` 的 E8 章節。

### 6.2 Notebook（`notebooks/e7_colab_decider_eval.ipynb` 加 `EXPERIMENT="E8"`，格子結構不變）

| 格 | E8 模式 |
| --- | --- |
| 0、1、1B、2、3、4 | 同 E7：說明、設定、clone 釘選 commit、安裝並檢查版本一致、硬體紀錄、解 zip 並驗 MANIFEST |
| 5 | 載入 `e8_part1.jsonl`；GT 掃描；G5；laya 截斷稽核 |
| 6 | 第一部分推論，以 (模型, 級, 順序) 為一組寫 checkpoint，可續跑 |
| 7 | 第一部分評分（唯一可以讀標籤表的格）：總表、H1a–d、3 張圖、選組 |
| 8 | 第二部分：先跑 B1 重現閘門，再跑各閉迴路組，每組每段寫 checkpoint |
| 9 | 打包 `e8-run-<日期>.zip`（輸出、checkpoint、`RUN_NOTES.json`、偏離） |

### 6.3 預估執行時間（估計值；實測記在 RUN_NOTES）

| 項目 | A100 | L4 GPU |
| --- | --- | --- |
| 安裝與下載模型 | 約 15 min | 約 15 min |
| 第一部分 laya（3,480 筆，約 40 ms／筆） | 約 3 min | 約 5 min |
| 第一部分 Qwen-3B（2,088 筆，估 0.6–1.0 s／筆） | 約 25–35 min | 約 45–60 min |
| 第一部分 Qwen-7B（2,436 筆，估 0.8–1.5 s／筆） | 約 35–60 min | 約 70–110 min |
| 第二部分（3 個規則組＋4 個模型組＋1 個 MEASURED） | 約 30–60 min | 約 60–100 min |
| **合計** | **約 2–2.5 h** | **約 3.5–5 h** |

E7 的 Qwen-3B（GPU bf16、E7 格式、輸出上限 256 token）p50 是 5.4–6.0 s；E8 的輸出只有約 20 個 token，所以估得比較短。若 Colab 實測超過估計 2 倍，只印警告，不停止。

### 6.4 回 Mac 一條指令

```bash
python scripts/evaluation/e7_replay_run.py --e8 --run local/evidence/e8-run-<日期>/e8-run-<日期>.zip --out local/evidence/e8-run-<日期>/score
```

這條指令會：

- 用 GT 補判 OWN_BOX、判出 TRUE_DEPARTURE，產生第一部分分層表；
- 產生第二部分 28 段 × 各組的指標，以及 H2、S3、S4；
- 呼叫 `e6_verdict_run.py --single` 填 E6 的 `single_correct`（#765）；
- 經 `generate_unified_analysis.py`（`e8` 區段）與 `report/figures/build_figures.py` 出圖；
- 輸出 `E8_RESULTS_<日期>.json` 和 `.md`。

重現指令寫在 `docs/operations/E8_REPRO_<日期>.md`。

## 7. 測試與驗證點

### 7.1 Focused 測試（只跑這些，加上 `git diff --check`）

| 測試檔 | 測什麼 |
| --- | --- |
| `test_build_e7_colab_pack.py` | `--e8`：快照欄位只有 §2.2 規定的那些；假 GT 進不了任何請求；閘門失敗時整包刪除；3 種順序可重現；標籤表不受順序影響 |
| `test_e7_decider_eval.py` | 合併規則；各級欄位嚴格累加；L0 與 E7 逐位元組相同；laya 渲染的 token 結構（用假 tokenizer）；`parse_e8_answer`；KEEP 解析；底線策略（含 RN 在 T 的強制提問）；E7 的舊測試全部照舊通過 |
| `test_e7_colab_runtime.py` | fingerprint 含 (level, perm)；續跑 |
| `test_e7_replay.py` | 觸發條件與間隔；SELECT／NOT_VISIBLE／無效回答的套用；MEASURED 的 chain 與 EXPIRED；不掛決策器時和 `e3_f4_run.replay` 一致 |
| `test_e6_verdict_run.py` | `--single` 填入 `single_correct`；完整追蹤的判定不變 |
| `test_aol_zero_latency_and_unified_analysis.py`、`tests/report/test_report_skeleton.py` | `e8` 選填區段；沒有 E8 的舊輸入照舊；新圖在 headless 下可產生 |
| GT 隔離 | E8 的推論端程式碼不 import 評分端模組（字串掃描） |

### 7.2 驗證點

| 代號 | 內容 | 在哪裡跑 |
| --- | --- | --- |
| V1 | R-N 重播和凍結 `RN_U.json` 逐列相同（28 段，到最後一個決策點為止） | Mac |
| V2 | B1 重現 28/28 段 | Mac＋Colab 第 8 格 |
| V3 | L0 請求和 E7 逐 tick 請求（`8568e4fa…`）在同一 tick 逐位元組相同（E3 68 點） | Mac |
| V4 | KEEP 解析 100% 成功 | Mac |
| V5 | `verify_colab_pack_pre_upload` PASS；所有請求通過 `_scan_forbidden_gt_fields` 和 `arms.reject_forbidden` | Mac |
| V6 | laya 截斷稽核有產出 | Colab 第 5 格 |
| V7 | SMOKE：本機 CPU、stub 決策器、E3-A1＋E6-S01，跑完整個 notebook，再跑完 Mac 一條指令 | Mac |
| V8 | 探索：E8 的 L0 laya 答案和 E7 逐 tick 答案（`2e23f37a…`）的一致率 | Mac |

## 8. 待協調者決定

| # | 問題 | 建議 |
| --- | --- | --- |
| Q1 | 第二部分要不要包含 L4（多約 1.5 GB 畫面） | 先不要。如果第一部分 L4 明顯最好（S1 的 L4−L3 顯著），再補第二包 |
| Q2 | 新增 L0c、L3F | 加 |
| Q3 | 第一部分的快照改用 R-N（v1 用的是 B1）；第二部分照 brief 用 B1 底座 | 照 #765 用 R-N。這樣 E6 的 `single_correct` 填得進去，也和 #781 的 GPT 組同一底座；兩部分的底座不同會寫進限制 |
| Q4 | H2 錯人秒的容許值 +14.0 s | 採用（預登後不再改） |
| Q5 | 主要比較對象是 laya_typed 和 qwen7b | 採用 |
| Q6 | 第二部分只用 `p0` 順序 | 採用 |
| Q7 | 分支起點：`claude/feat-e8` 現在在 `d4cebd12`（從 `179bccb7` 切出）。#769 修好後，用**合併 commit** 把修正後的 `origin/claude/feat-e7-laya` 併進來（不 rebase、不 force） | 採用；開始實作前先確認 #769 CI 已綠 |

## 9. 每個數字的出處

| 數字 | 出處 |
| --- | --- |
| E7：多錯 261.2 s、其中錯鏡頭 207.0 s；72%／65%；2,058／2,037／2,516（／5,120）；`image_paths` 全空 | #767 協調者留言；LOCAL `e7-run-pertick-20261127/analysis/claude_coord_recheck_20261128.json` `00dd4f31…a000`（實作時整理成 `E7_LAYA_ANALYSIS_20261128.md`） |
| laya 512／1024、192／256；截斷規則 | HF `convaiinnovations/laya` @`246177e5` 的 `rl_agent_config.json`、`typed-decisions/rl_agent_config.json`、`rl_common.py`（`8d83611d…`，等於審核值）、`rl_agent_api.py`（`be3b4681…`） |
| 68＝38＋30；E3 type；E3 家族 A–D | 兩份 E3 `CORPUS.json` |
| 48（VISIBLE 43、FULL_BLIND 5）；E6 type 24 種；E6 家族 12 個 | `e6_scenarios_frozen_v1.json` `5bab2766…`；E6 執行紀錄 R0 |
| 候選 6／12／22；紅色中位數 4；4 m 內的紅色分佈 | LOCAL `e8-design-20261128/e8_design_dpstats.out.txt` `e0871687…` |
| 觸發估計 377（28 段、7,058 tick） | LOCAL `e8-design-20261128/e8_design_trigger_estimate.out.txt` `96fd0b86…` |
| scene_context 19,589 字元、`3072cc5a…` | `e3_f4_run.live_scene_context`（本 session 在 `179bccb7` 上執行），與 B1 b-log 欄位相同 |
| 釘選檔案（arms.py、decider.py、e6_arms_v1.json、E6 預登） | `scripts/evaluation/e6_select_arm.py` 的 `PROMPT_FILES` |
| RGB 450＋670＋381 MB；E7 包 115 MB | `du -sh`（本 session） |
| Qwen p50 5.4–6.0 s（E7 格式） | 協調者共享筆記 `767_replay_design.md` §2 |
| laya GPU 約 40 ms／筆 | #767、D416 |
| H2 容許值 0.05／5.0 s | E6 預登 §4（C2、C4）；+14.0 s 是本文件新定（Q4） |
