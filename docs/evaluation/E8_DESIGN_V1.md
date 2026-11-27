# E8 設計與預登 v1：Agent 與規則公平對照（資訊逐級、交接點決策、一鍵 Colab）

> 狀態：**設計稿，待協調者確認（D415 第 1 級）**。確認前不寫程式、不打包、不跑推論。
> Issue：[#780](https://github.com/Polalalabear/amidst/issues/780)（本文件涵蓋 W1；W3、W4 的規格也寫在這裡）。決策：D416、D417（#93）。前因：#767 協調者分析（https://github.com/Polalalabear/amidst/issues/767#issuecomment-7224614486）。
> 作者：Claude Opus 5.5（E8 子 session），2026-11-28。身分一律 `UNCONFIRMED`；實體可通行性 `UNKNOWN`。本機模型零 API 費用；GPT 組由 Codex 另做（#781），獨立複核在 #782。

## 0. 目的與前因

研究問題：**Agent 能否加快切換鏡頭的決策，並在複雜情況下優於規則 B1。** E5、E6（P2 `NOT_SUPPORTED`）、E7 都是規則贏。但 E7 給本機模型 laya 的輸入比 B1 和 API Agent 少很多（D416）：

- 沒有「目標是紅色」、上一個位置、地面座標、鏡頭連通，也沒有圖片（5,223 筆請求的 `image_paths` 全空）。
- laya 從不回答 `NOT_VISIBLE`，72%（laya_text）／65%（laya_typed）選清單第一個候選。快照正確率約等於「永遠選第一個」（2,058 比 2,037／5,120），還輸給「選第一個紅色」（2,516）。
- 多錯的秒數八成是錯鏡頭（laya_text 比 B1 多 261.2 s，其中 207.0 s）。

**設計時另外查到的根因（本文件新發現，§2.6）**：laya 是 ModernBERT 編碼器加決策頭，不是生成式模型，輸入有硬上限。root 版（laya_text）`max_len=512`、`head_max_len=192`；typed 版 `max_len=1024`、`head_max_len=256`（HF `convaiinnovations/laya` @`246177e5`，`rl_agent_config.json`）。`rl_common.build_sequence` 先放題目與選項，選項總長超過 `head_max_len` 時**把每個選項平均截短**，題目只剩剩餘空間；state 從右邊截斷。E7 的選項文字是 `camera CAM_W1 detection D1 box [...] score 0.52`，決策點中位數有 6 個候選（最多 22 個，§2.1），加上 3 個非選人選項後，每個選項大約只剩 10–20 個 token，框和分數常常被截掉。laya 看到的選項幾乎只差在鏡頭名稱，於是照位置猜。E8 的選項格式必須針對這個上限重新設計，見 §2.5–§2.6。

E8 要回答三件事：

1. 公平條件下（Agent 拿到不少於 B1 的資訊），本機模型的單點判斷能否勝過簡單規則；
2. 哪一種資料讓 Agent 變好（資訊逐級增加），以及候選順序造成多大的位置偏差；
3. 讓 B1 負責追人、Agent 只在交接點介入時，完整追蹤會不會比 B1 差，以及能不能更早切對鏡頭。

## 1. 資料來源（凍結輸入，全部已存在）

| 項目 | 路徑（LOCAL 相對 `local/evidence/`，repo 相對 repo 根） | SHA-256 |
| --- | --- | --- |
| E3 決策點（38 個，9 段） | `e3-652-20261122/CORPUS.json` `cases[].decision_points` | `930e85fe…c50d` |
| E3 決策點（30 個 REAPPEAR，7 段） | `e3-reappearances-20261122/CORPUS.json` | `6954dcb4…f7c9` |
| E6 決策點（48 個，12 段，`actual_decision_points`） | `e6-formal-20261127/e6_scenarios_frozen_v1.json`（＝`configs/evaluation/e6_scenarios_frozen_v1.json`） | `5bab2766…b338` |
| B1 b-log（E3） | `f4-658-20261122/runs-final-9/<case>/B1.k1.json`、`runs-final-665/<case>/B1.k1.json` | 各檔逐一記入打包收據 |
| B1 b-log（E6） | `e6-formal-run-20261127/b1/<case>/B1.k1.json` | 樹雜湊 `90920606…cb7e5cc`（E6 執行紀錄 R0.1） |
| 凍結偵測與 RGB | E3：`e3-652-20261122`、`e3-reappearances-20261122`；E6：`e6-formal-det-20261127`（`indexes/`、`rgb/`、`*.replay1.wire.json`），由 `e3_f4_run.load_case` 讀取並驗 SHA | 載入時逐檔驗證 |
| 相機目錄 | `local/data/live-assets-20261115/cameras.catalog.json` | `3eba8572…`（與 B1 b-log 的 `camera_catalog_sha256` 相同） |
| 場景脈絡 | `e3_f4_run.live_scene_context`（`scene_context.build`，含 D346 靜態幾何） | `3072cc5a…`（與 B1 b-log 的 `scene_context_sha256` 相同；序列化 19,589 字元） |
| 評分器 | `src/amidst/evaluation/e3_scoring.py` | `acacce39…7d08`（釘選，不改） |
| E7 逐 tick 請求 | `e7-colab-pack-pertick-20261127/requests/e3_16_segments.jsonl` | `8568e4fa…8dee` |
| E7 逐 tick laya 答案 | `e7-run-pertick-20261127/e7-outputs-pertick/…` | `2e23f37a…b3cb`（#767 分析） |
| laya 權重與程式 | HF `convaiinnovations/laya` @`246177e5cb70334c9831c0730864a93c836aac8f`；root＝laya_text，`typed-decisions/`＝laya_typed；3 個審核過的 `.py` 以 SHA 驗證（`e7_decider_eval.LAYA_AUDITED_PY_SHA256`） | 同左 |
| Qwen | `Qwen/Qwen2.5-VL-3B-Instruct`、`Qwen/Qwen2.5-VL-7B-Instruct` | `hf_revision` 打包時釘成 40 字元 commit（目前 `UNKNOWN`） |

設計期統計（0 推論、0 付費、不讀 GT）：LOCAL `e8-design-20261128/`。`e8_design_dpstats.py` SHA-256 `a56fb30e…a550`，輸出 `e0871687…09c0`；`e8_design_trigger_estimate.py` `b39a35ed…b616704`，輸出 `96fd0b86…d985`。

## 2. 第一部分：單點對照（開迴路）

### 2.1 題目

| 資料集 | 段數 | 決策點 | 既有分層標籤 |
| --- | ---: | ---: | --- |
| E3（F4 #658 凍結語料） | 16 | 68 | 決策點 `type`（16 種，見 CORPUS；REAPPEAR 33 個）、段的 `family`（A–D） |
| E6（正式 12 段） | 12 | 48 | 決策點 `type`（24 種）、`gt_regime`（VISIBLE 43、FULL_BLIND 5，由 GT 決定，只在 Mac 分層）、`family_id` |
| 合計 | 28 | **116** | 沒有標籤的情境一律寫 `UNKNOWN`，不新造標籤 |

設計期量到的 E3 68 點（`e8_design_dpstats.out.txt`）：

- 每點候選數：中位數 6、p90 12、最大 22；紅色候選中位數 4、最大 18。
- B1 上一個估計位置 4 m 內的紅色框：0 個 14 點、1 個 18 點、≥2 個 36 點。
- B1 在 T−1 的狀態：TRACKING 且看得到 52 點、TRACKING 但 lost_ticks>0 9 點、LOST 7 點。
- E6 的同樣統計要在打包時才算（需要從 RGB 判色），目前 `UNKNOWN`。

### 2.2 凍結 B1 狀態

每個決策點的時間記為 T（`decision_points[].tick`）。從 B1 b-log 取兩列：

- **T−1 列**（給 Agent 的狀態）：`state`、`active_cam`、`est_xy`、`lost_ticks`。距上次看到的時間記為 `lost_ticks × 0.2 s`；b-log 沒有 `t_seen`，這是唯一可從 b-log 推出的版本。
- **T 列**（KEEP 的實際內容和 B1 組的答案）：B1 在 T 實際顯示的 `active_cam` 與 `box`。
- **參考裁切**（只給 L4）：B1 第一次 `ACQUIRE` 事件那個 tick 的 active camera 框，從凍結 RGB 裁切（同 `service_decider` 的 `crop_jpeg`）。

T−1 與 T 都只來自 B1 輸出，不含 GT。

### 2.3 答案空間

| 答案 | 意義 | 解析成的「實際顯示」 |
| --- | --- | --- |
| `KEEP` | 維持 B1 目前的目標 | B1 T 列的 `box` 對到 T 的候選，變成 SELECT 該候選；`box` 為空就等於 NOT_VISIBLE |
| `SELECT` ＋選項代號 | 選一個候選（鏡頭＋框） | 該選項的代表框（§2.4） |
| `NOT_VISIBLE` | 所有鏡頭都看不到目標 | 不顯示 |

**判分只看實際顯示**（§2.9），所以 B1 組（永遠 KEEP）的單點分數就是 B1 在 T 的顯示。打包時檢查每個 B1 T 列的 `box` 都能對到某個候選成員，或者本來就是空的（驗證點 V3）。格式錯誤或沒有有效答案一律算錯（同 E6 預登 §3.2）。

### 2.4 候選與選項

- **候選**：T 時刻所有鏡頭的 person 偵測，門檻與 B1 相同（score ≥ 0.15，CAM_ENTRY ≥ 0.05），任何顏色都算。`detection_id` 是每台鏡頭的 D1…Dn（同 E7 `candidates_for_tick`），顏色來自 `e3_f4_run.load_case`（HSV，`color_weak=0.2`）。
- **跨鏡頭合併**（L0c 以上）：不同鏡頭的框投影到地面後相距 < 1.5 m，就合成一個選項（同一個人被多台鏡頭拍到）。同一台鏡頭的兩個框絕不合併。代表框取框高最大的成員（同 `Tracker.update` 的換鏡規則），顏色取成員的聯集。投影失敗的框不合併，距離標 `?`。合併只用相機標定，不用 GT；L0c 到 L4 的選項集合完全相同，各級之間只差顯示的資訊。L0 不合併（照 E7 原樣）。
- **選項代號**：依當次順序給 A、B、C…；`KEEP`、`NOT_VISIBLE` 固定放在最後。
- **三種順序**（量位置偏差）：
  - `p0`：標準順序（相機擷取順序，再依 D 編號，同 E7）；
  - `p1`：`p0` 反轉；
  - `p2`：`random.Random(f"20261128|{request_base_id}")` 打亂。
  - 只打亂候選，KEEP 和 NOT_VISIBLE 不動。標籤表以 (鏡頭, D 編號) 表示，不受順序影響。

### 2.5 資訊逐級增加（累加）

| 級 | 新增資訊 | 給誰 |
| --- | --- | --- |
| **L0** | E7 現況，逐位元組照 E7 請求（`build_e7_colab_pack.variable_text` ＋ `build_laya_state_and_questions`／`assemble_ao_prompt`）。答案對應：`UNCERTAIN`、`STILL_HERE_OCCLUDED` → KEEP；`OWN_BOX` → 在 Colab 記 `NEEDS_MAC_SCORING`（算錯，回 Mac 以 GT 框補判，同 E7） | 全部模型 |
| **L0c**（新增的格式對照） | 資訊與 L0 相同（鏡頭、分數、框），改用 E8 精簡格式與合併後的選項集合 | 全部模型 |
| **L1** | 「目標穿紅色」寫在題目裡；每個選項標顏色；VLM 另附 `gate_of` 的顏色閘門結果（當資訊用） | 全部模型 |
| **L2** | 上一個可靠位置：B1 T−1 的鏡頭、地面座標、距上次看到幾秒、追蹤狀態；每個選項到該位置的地面距離（m） | 全部模型 |
| **L3** | 鏡頭連通與屬性：從 `scene_context`（SHA `3072cc5a…`）推出的精簡摘要。每個選項標出它的鏡頭和上一個鏡頭的關係：`same`／`adj`（graph v3 有 transition）／`ovl`（`overlap_iou` ≥ 0.05）／`other`。state 列出上一個鏡頭的相鄰鏡頭、重疊鏡頭，以及上一個位置到各鏡頭地面覆蓋區的距離（同 B2 的 F2 空間排序） | 全部模型 |
| **L4** | 參考裁切（B1 第一次 ACQUIRE）＋ T 時刻各鏡頭畫面（框上標選項代號，同 `service_decider._jpeg`） | 只給 VLM（Qwen） |
| **L3F**（探索性） | L3 改成完整 `scene_context` JSON（同 API Agent 的 `prefix_text`），不用摘要 | 只給 Qwen-7B |

**為什麼加 L0c**：L0 → L1 同時改了格式和資訊。L0c 把格式效果（含合併）單獨量出來，之後的 L1−L0c、L2−L1、L3−L2、L4−L3 才是單純的資訊效果。這是相對 brief 的**增項**，請協調者確認。

**為什麼 L3 用摘要**：完整 `scene_context` 約 19.6k 字元，laya 的 512／1024 token 根本放不下。所有模型的 L3 都用同一份摘要，模型之間才能比較；完整版只在 L3F 探索。

### 2.6 laya 的放法（state 與選項文字）

laya 的輸入順序是 `[CLS] 題目 [SEP] [MASK]選項1 [MASK]選項2 … [SEP] state [SEP]`。限制（§0）：選項區（題目＋選項）≤ `head_max_len`（192／256），全部 ≤ `max_len`（512／1024），state 從右邊截斷。所以 E8 的規則是：

- **題目放最關鍵、而且最短的一句**：L0c「Which option is the tracked person now?」；L1 起「Which option is the red-clothed tracked person now?」。
- **選項只放判斷用的欄位，最重要的放最前面**，每個選項目標 ≤ 10 token：

  | 級 | 候選選項文字範例 | KEEP | NOT_VISIBLE |
  | --- | --- | --- | --- |
  | L0c | `A: W1 .52` | `KEEP: keep current target` | `NOT_VISIBLE: not visible in any camera` |
  | L1 | `A: red W1 .52` | 同上 | 同上 |
  | L2 | `A: red 1.2m W1 .52` | `KEEP: keep tracker target W1` | 同上 |
  | L3 | `A: red 1.2m W1 same .52` | 同上 | 同上 |

  鏡頭名稱去掉 `CAM_` 前綴，代號對照表放在 state。
- **state 是有順序的 JSON，重要的在前**（被截斷時先丟後面）：
  1. L1 起：`target`（紅色衣服，tracker 色彩標籤）；
  2. L2 起：`last`（例：`W1 (12.8,1.9) 0.4s ago, tracker TRACKING lost 2`）；
  3. `options`（每個選項一行：鏡頭、D 編號、分數、框；L2 起加上地面座標與距離，L3 起加上鏡頭關係）；
  4. L3 起：`graph`（上一個鏡頭的相鄰鏡頭、重疊鏡頭、到各鏡頭覆蓋區的距離）；
  5. `now_s`。
- **截斷稽核**：notebook 在推論前用 laya 自己的 tokenizer 算每筆請求的選項與 state 長度，記下「選項被平均截短」和「state 被截斷」的比例（分模型、分級）。這是要報告的共變量，不是停止條件（驗證點 V6）。

### 2.7 VLM（Qwen）的放法：重用 `agent_service`

- **系統文字**：沿用 `agent_service.SYSTEM_TEXT` 的身分、規則閘門和棄權條款，答案格式改成 E8 的 `{"answer":"SELECT"|"KEEP"|"NOT_VISIBLE","option":"A"|null,"confidence":"low"|"medium"|"high"}`。L0 例外，用 E7 的 `AO_SYSTEM_PROMPT`／`assemble_ao_prompt` 原樣。輸出很短，所以 `max_new_tokens=48`（L0 照 E7 用 256）。
- **追蹤層**：用 `agent_service.track_layer` 的文字；L1 起寫色彩標籤，L4 再附參考裁切。
- **變動層**：每個選項一行，欄位與 laya 的 state `options` 相同。用 `agent_service.Candidate` 加 `gate_of` 產生 `rule_eligible`／`gate`（L1 起才有顏色閘門）。L2 起附 `rule_answer`（`state`、`active_cam`、`lost_ticks`，同 `service_decider.build_input`），L3 起附鏡頭摘要。
- 生成方式：貪婪解碼（`do_sample=False`），同 E7 的 `build_qwen_vl_inference_fn`；回應用新的 `parse_e8_answer` 驗證。

### 2.8 組別與請求量（第一部分）

每一格是 116 點 × 3 種順序 = 348 筆請求。

| 組 | 級 | 請求數 | 備註 |
| --- | --- | ---: | --- |
| B1（自己的下一步＝KEEP） | — | 0（直接讀 B1 T 列） | 與順序無關 |
| FIRST（選第一個候選） | L0c 選項集合 | 0（Colab 直接算） | 跟順序有關，3 種順序都算 |
| FIRST_RED（選第一個紅色，沒有紅色就 NOT_VISIBLE） | L1 | 0 | 同上 |
| RANDOM（候選加 NOT_VISIBLE 均勻抽一個，seed `20261128\|request_id`） | L0c | 0 | 另報理論期望值 |
| NEAREST_RED（離 B1 T−1 估計位置最近的紅色，不設門檻；沒有估計位置或沒有紅色就 NOT_VISIBLE） | L2 | 0 | 與順序無關 |
| laya_text、laya_typed | L0、L0c、L1、L2、L3 | 各 1,740 | GPU 約 40 ms／筆（#767） |
| Qwen2.5-VL-3B | L0、L0c、L1–L4 | 2,088 | |
| Qwen2.5-VL-7B | L0、L0c、L1–L4、L3F | 2,436 | A100 建議；L4 GPU（24 GB）bf16 也放得下，較慢 |

每點的主分數是 **3 種順序的多數決**（≥ 2 種對才算對），另報 3 種順序的平均正確率。

### 2.9 判分（單點；沿用 E6 預登 §3.2 真值表，以 T 的快照判定）

| T 時刻 GT 情境（只在 Mac 算） | 標籤（上 Colab，D385 白名單欄位） | 對 |
| --- | --- | --- |
| 目標可見，且有候選打到 GT 身體框（`judge_box` primary） | `SELECT`＋`expected_camera_ids`＋`expected_detection_ids`（cam → D 編號） | 實際顯示的代表框 (cam, D) 在命中集合裡 |
| 目標可見，但沒有候選打到（偵測漏掉，`DETECTOR_MISS`） | `UNCERTAIN`＋可見鏡頭 | 沒有答案算對。所有組都錯，不影響配對檢定；另報「安全答案率」（NOT_VISIBLE 或沒有顯示） |
| 目標不可見（在場或離場） | `NOT_VISIBLE` | 實際顯示為空 |

標籤由 `build_e7_colab_pack.expected_for_tick` 產生（Mac，讀 `gt-boxes/<case>.a-log.json`），經 `write_colab_answer_table` 寫入，只含白名單欄位。合併選項以代表框判分，不以「任一成員命中」判分（較嚴，與閉迴路實際顯示一致）。

## 3. 第二部分：完整追蹤（閉迴路，交接點決策）

### 3.1 架構

- 用 `live_mode.server.State._infer_tracking` 的既有決策器掛點（`self.decider.step(...)`），新寫 `E8HandoffDecider`，介面與 `ServiceLiveDecider` 相同。B1 每個 tick 照常追人，決策器只在觸發點建請求、問模型、套用答案。
- 重播驅動沿用 `e3_f4_run.replay` 的流程：同一組 CONFIG（gate 4 m、score .15／.05、relock disabled、target red）、同一套 b-log 列格式。輸入改成打包好的逐 tick 偵測（已含 HSV 顏色欄位，Mac 先用 `load_case` 算好）。Colab 上不讀 RGB（L4 例外，見 §3.5）。
- **B1 重現閘門**：不掛決策器時，Colab 和 Mac 重播出來的 28 段 b-log `rows[].tracking` 必須和凍結的 B1 b-log 完全一致，否則停（驗證點 V1）。

### 3.2 觸發點（寫死）

在 tick t，B1 更新之後檢查下列條件，依序取第一個成立的：

| 代碼 | 條件 | 最短間隔 |
| --- | --- | --- |
| `LOST` | B1 `lost_ticks` 首次 ≥ 2（0.4 s；同 `ServiceLiveDecider.lost_ticks_before_ask=2`） | 之後仍 lost 就每 1.0 s 再問一次（`LOST_RECHECK`） |
| `SWITCH` | 本 tick 有 B1 的 `SWITCH` 或 `REACQUIRE` 事件 | — |
| `AMBIGUOUS` | B1 為 TRACKING 且 `lost_ticks=0`，T−1 估計位置 4 m 內有 ≥ 2 個紅色候選，且其中兩個地面距離 ≥ 1.5 m（不同的人） | 同一段歧義持續時每 2.0 s 最多問一次 |

- 全域最短間隔 1.0 s（5 tick）；`ACQUIRE` 之前不問。
- 設計期估計：只算 LOST＋SWITCH、間隔 1 s，28 段 7,058 tick 共 377 個觸發點（`e8_design_trigger_estimate.out.txt`）。AMBIGUOUS 的數量要打包後才知道，`UNKNOWN`。上限是每秒 1 次，約 1,411 次。

### 3.3 請求與套用

- **請求**：與第一部分同一個建構函式。state 是觸發 tick 時 B1 更新**前**的狀態（決策器每 tick 結束時記下），KEEP 是 B1 在 t 的顯示。只用 `p0` 順序。
- **套用**：
  - `KEEP`：不動。
  - `SELECT`：重設追蹤器（`est`＝該選項地面座標、`active`＝代表框的鏡頭、`state=TRACKING`、`lost=0`、`last_seen`、`t_seen`），做法同 `ServiceLiveDecider` 的單次修正；之後由 B1 繼續追。
  - `NOT_VISIBLE`：追蹤器設成 LOST（保留 `est`），之後 5 tick（1.0 s）不顯示；到期後若仍符合 `LOST` 條件就再問。
  - 無效回答：當作 KEEP，記 `fallback_reason`。

### 3.4 延遲

- **主分析 `ZERO_LATENCY`**：答案在觸發 tick 當下生效（量決策品質，與 E5 AO 零延遲對照一致）。
- **次要分析 `MEASURED`**：答案在第一個滿足 `(t'−t)×0.2 s > 實測延遲` 的 tick 生效，框用 `e3_f4_run.chain_box`（IoU ≥ 0.3）從 t 串到 t'，串不起來記 `EXPIRED`、不套用（同 E5 A3）。延遲是 Colab GPU 上的實測值，GPU 型號記在硬體紀錄裡。

### 3.5 組別（第二部分）

| 組 | 觸發點的決定者 | 用途 |
| --- | --- | --- |
| B1 | 無 | 重現閘門與對照 |
| B1+FIRST_RED | 規則：p0 第一個紅色 | 觸發機制本身的底線 |
| B1+NEAREST_RED | 規則：離 T−1 估計位置最近的紅色 | 同上 |
| B1+laya_text@k\*、B1+laya_typed@k\*、B1+qwen3b@k\*、B1+qwen7b@k\* | 各模型在第一部分最好的**文字級** k\*（L0c–L3） | 每個模型一組 |
| **SELECTED** | 上面四組中，第一部分多數決正確率最高的 (模型, 級)；同分時依序比 3 種順序的平均正確率、較低的級、模型順序 laya_text < laya_typed < qwen3b < qwen7b | 主要假設 H2 |
| SELECTED＋MEASURED | 同上，延遲照實測 | 次要分析 |

選組規則在 notebook 裡自動執行，用的是第一部分 Colab 上的標籤表分數。這只決定「哪一組當主要組」，不進任何推論輸入。另外四組全部都跑，所以選組不會讓任何一組沒有資料。

**L4 是否進第二部分（待協調者決定，§8 Q1）**：閉迴路的觸發 tick 事先不知道，L4 需要所有 tick 的畫面。E3＋E6 的 RGB 約 1.5 GB（450＋670＋381 MB），打包後 zip 約多 1.5 GB。我建議第二部分只用文字級（≤ L3），pack 維持約 0.1–0.2 GB；如果第一部分 L4 明顯最好，再補一個只含畫面的第二包。

### 3.6 評分（只在 Mac）

- Colab 輸出每組每段一份 b-log（`e3-f4.b-log.v1` 格式，`arm` 填組名，`calls` 記每次觸發的請求 SHA、答案、延遲、是否套用）。
- Mac 端：
  - E3 段用 `e3_f4_score.run_scores`（評分器 `acacce39…`）；
  - E6 段用 E6 正式評分的同一條路（`e6_verdict_run` 的 `full_track_dp_correct`，依 `gt_regime`）。
- 指標：
  - 錯人秒（再拆成錯鏡頭與鏡頭對、人錯，用 `metrics` 的 `wrong_camera_s`）、失聯秒、盲區誤鎖秒、跟對率（主準則與 IoU 保守準則都報）；
  - 決策點正確數（E3 68 點、E6 48 點，各用自己的預登規則）；
  - **提早切對秒數**：對每個在 T 可見的決策點，算 B1 和該組在 [T, T+3 s] 內第一個 CORRECT tick 的時間，3 s 內沒有就記 3.2 s（設限）。提早量＝B1 時間 − 該組時間，正值代表 Agent 較早。依既有 `type` 分層報告。

## 4. GT 隔離（D417 折衷）

1. 第一部分：Colab 只拿到標籤表 `scoring_only/answer_table.json`（D385 白名單：`request_id`、`case_id`、`tick`、`expected_answer`、`expected_camera_ids`、`expected_detection_ids`），經 `write_colab_answer_table` 寫入；不含框、座標、可見表或 `gt_regime`。依 `type`、`gt_regime` 分層只在 Mac 以 `request_id` 合併。
2. 第二部分：Colab 沒有任何 GT。評分只在 Mac。
3. 打包閘門：`verify_colab_pack_pre_upload` 必須通過（不得有 `gt/`、`a-log.json`、`.blend`）。每個請求、逐 tick 偵測檔、B1 狀態檔都要通過 `_scan_forbidden_gt_fields`。另外掃描是否出現 `gt-boxes`、`a-log` 字串，任何一項失敗就刪掉整包。
4. 推論端模組（`e8_requests.py`、`e8_handoff.py`）不得 import `e3_scoring` 或 `e7_scoring_bridge`，用測試檢查。
5. B1 狀態、顏色、地面投影、`scene_context` 都只來自 b-log、RGB、標定與設定（DEVELOPMENT_RULES 允許的推論輸入）。

## 5. 預登

### 5.1 判定用語

判定只用 `SUPPORTED`（成立）／`NOT_SUPPORTED`（不成立）／`INCONCLUSIVE`（無法判斷）／`EXPLORATORY`，同 E6。「無法判斷」不等於「沒有差異」。

### 5.2 主要假設（一個 Holm 家族，m = 5，單尾 α = 0.05）

| 代號 | 假設 | 比較 |
| --- | --- | --- |
| H1a | laya_typed@L2 單點正確率 > FIRST_RED | 第一部分，多數決 |
| H1b | laya_typed@L3 > FIRST_RED | 同上 |
| H1c | qwen7b@L2 > FIRST_RED | 同上 |
| H1d | qwen7b@L3 > FIRST_RED | 同上 |
| H2 | B1＋SELECTED（`ZERO_LATENCY`）的完整追蹤不比 B1 差 | 第二部分，交集－聯集檢定（IUT）三個元件同時成立：跟對率差 ≥ −0.05（合併）；錯人秒差總和 ≤ +14.0 s（28 段，平均每段 +0.5 s）；盲區誤鎖秒差總和 ≤ +5.0 s（同 E6 C4） |

- 選 laya_typed 和 qwen7b 當主要比較，因為它們是兩個家族中較強的版本（typed README 0.766 對 0.362；7B > 3B）。laya_text、qwen3b 列為次要。
- **統計方法**：
  - 獨立單位是段（M = 28；同段的決策點有相關）。
  - H1：每段算「受測組正確數 − FIRST_RED 正確數」，做單尾配對 sign-flip。M > 12，所以用 `random.Random(20261128)` 翻轉 10,000 次（`e6_verdict.sign_flip_p`）。附段的群集 bootstrap 95% CI（B = 10,000）。點層級的精確 McNemar 只當描述。
  - H2：每個元件先把差值平移容許值，再做單尾 sign-flip，p_H2 取三個元件的最大值；另附 bootstrap CI 上界。
  - Holm 用 `e6_verdict` 的同一套。
- **敏感度**：以劇本家族為單位（E3 A–D 4 個＋E6 12 個，M = 16）重算一次，只報告，不改判定。

### 5.3 次要假設（一個 Holm 家族，m = 13，雙尾 α = 0.05）

- S1（7 項）：資訊增量。laya_typed 與 qwen7b 各自的 L1−L0c、L2−L1、L3−L2；qwen7b 另加 L4−L3。
- S2（4 項）：模型對同級資訊的規則底線。laya_typed、qwen7b 在 L2、L3 對 NEAREST_RED。
- S3（1 項）：SELECTED 的錯人秒低於 B1（優越性）。
- S4（1 項）：SELECTED 相對 B1 提早切對秒數的中位數 > 0（段層級 sign-flip，用段平均）。

### 5.4 探索性（不做多重校正，只報估計值與 CI）

- laya_text、qwen3b 的所有比較；L0 是否重現 E7（同一 tick 的答案一致率）；格式效果 L0c−L0；L3F−L3。
- 位置偏差：每級、每種順序「選第 1 個候選」的比例；3 種順序答案一致率；正確率在順序之間的變異。
- 依 `type`、`family`、`gt_regime`、候選數（≤ 8／> 8）、laya 截斷與否分層。
- laya 信心門檻敏感度（低於門檻改 KEEP），與 W2 的離線分析對照。
- `MEASURED` 延遲版；B1＋FIRST_RED／NEAREST_RED 閉迴路；錯鏡頭與鏡頭對、人錯的拆分；DETECTOR_MISS 點的安全答案率。
- N 小的分層（例如 E6 FULL_BLIND n=5、E3 每種 type 2–3 點）一律只當探索。

### 5.5 事先定義的結論

每個模型、每一級都套同一套規則，「資訊」指同一級以下的欄位。

| 結論 | 條件 |
| --- | --- |
| **Agent 有幫助** | H2 `SUPPORTED`，且 H1a–H1d 至少一項 `SUPPORTED`。若 S3 也成立，寫「交接點 Agent 降低錯人秒」；若 S4 成立，寫「較早切對鏡頭」 |
| **資訊不足** | 某一級 k：模型@k 與 NEAREST_RED 沒有顯著差異（S2 調整後 p ≥ 0.05，差距 < 5 個百分點），而且「任一組答對」的比例（所有模型、所有級、所有底線的聯集）在可回答點（排除 DETECTOR_MISS）低於 0.80。意思是給定的資訊下，沒有任何策略能把剩下的點分開 |
| **模型太小（或用不上資訊）** | NEAREST_RED（只用 L2 資訊）在 L2 或 L3 顯著優於該模型（S2 方向對規則有利），或者同一級 qwen7b − qwen3b ≥ +10 個百分點；而且該模型在 L2／L3 選第 1 個候選的比例仍 > 50%。意思是資訊夠一條簡單規則用，模型卻沒有用上 |
| **無法判斷** | 以上都不成立 |

### 5.6 有效性閘門（結果解讀前必須全部通過）

| 代號 | 檢查 | 失敗時 |
| --- | --- | --- |
| G1 | B1 重現 28/28 段（V1） | 停，不出第二部分數字 |
| G2 | GT 掃描與打包閘門 PASS（V4） | 刪包重做 |
| G3 | KEEP 對應率 100%（V3） | 停 |
| G4 | 每格（模型 × 級）格式退回率 ≤ 20% | 該格標 `FORMAT_INVALID`，照算錯並報告，但不能用來支持 H1 |
| G5 | 標籤表的 116 個 `request_id` 都對得到請求 | 停 |

## 6. Colab 包規格

### 6.1 目錄（`e8-colab-pack.zip`，旁邊附 `.zip.sha256`）

```
requests/part1_<level>.jsonl          每筆＝(dp, level, perm)：E8 結構化請求＋laya 的 state/questions＋VLM messages 文字
part1/frames/<case>/<cam>/<tick>_<perm>.png  L4 畫面（框上標代號，Mac 預先畫好）
part1/ref/<case>.png                  參考裁切
part2/ticks/<case>.jsonl              每 tick 的偵測（bbox、score、HSV 顏色欄位），沒有 GT
part2/b1_frozen/<case>.json           凍結的 B1 b-log（重現閘門的期望值）
part2/scene_context.json、cameras.catalog.json、camera_graph_v3.json
scoring_only/answer_table.json        第一部分的標籤表（D385 白名單）
PACK_INFO.json、MANIFEST.sha256
```

預估大小：不含第二部分畫面時約 0.1–0.2 GB（第一部分 L4 圖約 116×3×≤8 張，每張 320×180）。含第二部分畫面約多 1.5 GB（§8 Q1）。

### 6.2 Notebook（`notebooks/e8_colab_eval.ipynb`，沿用 E7 結構）

| 格 | 內容 |
| --- | --- |
| 0 | 說明：版本、放檔位置、執行時間、要回傳的檔 |
| 1 | 設定：`PINNED_GIT_COMMIT`、模型與 `hf_revision`、`SMOKE_MODE`、`RUN_PART1`／`RUN_PART2` |
| 1B | 掛 Drive，clone 並 checkout 釘選的 commit |
| 2 | 安裝釘選套件，檢查記憶體與硬碟版本一致（`e7_colab_runtime.assert_runtime_consistent`） |
| 3 | 硬體紀錄（`collect_hardware_provenance`） |
| 4 | 解 zip，驗 `.zip.sha256` 與 MANIFEST（任何不符就停） |
| 5 | 閘門：GT 掃描、G5、laya 截斷稽核（V6） |
| 6 | 第一部分推論：依 (模型, 級, 順序) 分組，每組完成就寫 checkpoint；fingerprint 相同就跳過 |
| 7 | 第一部分評分（唯一可以讀標籤表的格）：表、圖、選組 |
| 8 | 第二部分：B1 重現閘門（G1），再跑各閉迴路組，每組每段寫 checkpoint |
| 9 | 打包輸出：`e8-run-<日期>.zip`（輸出、checkpoint、`RUN_NOTES.json`、硬體、偏離紀錄） |

Colab 上直接產生的第一部分輸出：

- 總表：各組 × 各級的多數決正確率與 3 種順序的平均；
- 主要假設 H1a–d 的 p 值與 CI；
- 三張圖：資訊階梯折線圖、位置偏差長條圖、各組錯誤類型堆疊圖。

分層表要在 Mac 產生，因為分層標籤不上 Colab。

### 6.3 預估執行時間（估計值，實測記在 RUN_NOTES）

| 項目 | A100 | L4 GPU |
| --- | --- | --- |
| 安裝＋下載模型（laya 2 個、Qwen 3B＋7B） | 約 15 min | 約 15 min |
| 第一部分 laya（3,480 筆，約 40 ms／筆） | 約 3 min | 約 5 min |
| 第一部分 Qwen-3B（2,088 筆，估 0.6–1.0 s／筆） | 約 25–35 min | 約 45–60 min |
| 第一部分 Qwen-7B（2,436 筆，估 0.8–1.5 s／筆） | 約 35–60 min | 約 70–110 min |
| 第二部分（B1 重放＋2 個規則組＋4 個模型組＋1 個 MEASURED；每組觸發數估 400–1,400） | 約 30–60 min | 約 60–100 min |
| **合計** | **約 2–2.5 h** | **約 3.5–5 h** |

Qwen 每筆的時間是估計：E7 的 Qwen-3B（GPU bf16）用 E7 格式、輸出上限 256 token 時 p50 為 5.4–6.0 s；E8 輸出只有約 20 token，所以估計大幅縮短。實際以 SMOKE 之後的 Colab 前 20 筆為準，如果超過上表 2 倍，notebook 會印警告，但不會停。

### 6.4 回 Mac 一條指令

```bash
python scripts/evaluation/e8_score_run.py --run local/evidence/e8-run-<日期>/e8-run-<日期>.zip --out local/evidence/e8-run-<日期>/score
```

輸出：

- 第一部分完整表（含分層、OWN_BOX 以 GT 框補判）；
- 第二部分 28 段 × 各組指標、H2／S3／S4 判定、提早切對分佈；
- 圖（PNG）與 `E8_RESULTS_<日期>.json`／`.md`。

重現指令寫在 `docs/operations/E8_REPRO_<日期>.md`。

## 7. 檔案、測試與驗證點

### 7.1 新增或修改的檔案（全部在 `claude/feat-e8`，從 `claude/feat-e7-laya` `179bccb7` 切出）

| 檔案 | 端 | 內容 |
| --- | --- | --- |
| `src/amidst/evaluation/e8_requests.py`（新） | 推論端，純函式 | 候選合併、選項代號、3 種順序、L0–L4／L3F 組裝、laya 渲染（state, questions）、VLM 渲染（重用 `agent_service`）、`parse_e8_answer`、KEEP 解析、底線策略 |
| `src/amidst/evaluation/e8_handoff.py`（新） | 推論端 | `E8HandoffDecider`（觸發、套用、延遲）、閉迴路重播驅動（重用 `State`、`Tracker`、`chain_box`） |
| `src/amidst/evaluation/e8_score.py`（新） | 評分端 | 第一部分標籤判分、統計（重用 `e6_verdict` 的 sign-flip、bootstrap、Holm）、第二部分彙整（呼叫 `e3_f4_score.run_scores`、E6 路徑）、出圖 |
| `src/amidst/evaluation/e7_decider_eval.py`（小改） | 推論端 | laya／Qwen 推論函式加一條「直接吃 E8 已渲染輸入」的路徑；E7 原有行為與測試不變 |
| `scripts/evaluation/build_e8_colab_pack.py`（新） | Mac | 凍結 B1 狀態、逐 tick 偵測＋顏色、標籤表、L4 圖、參考裁切、MANIFEST、閘門 |
| `scripts/evaluation/e8_score_run.py`（新） | Mac | §6.4 的一條指令 |
| `notebooks/e8_colab_eval.ipynb`（新） | Colab | §6.2 |
| W2 離線腳本（`e8-offline-b` session 交付） | Mac | 收進同一個 PR |
| `tests/evaluation/test_e8_requests.py`、`test_e8_handoff.py`、`test_e8_score.py`、`test_build_e8_colab_pack.py`（新） | — | 見 7.2 |
| `docs/evaluation/E8_DESIGN_V1.md`（本文件）、`docs/operations/E8_REPRO_<日期>.md`（新） | — | 程式改動時同步更新 |

### 7.2 測試（只跑 focused 測試＋`git diff --check`）

- `test_e8_requests.py`：
  - 合併規則：同鏡頭不合、跨鏡頭 < 1.5 m 才合、代表框取最高的；
  - 3 種順序可重現，而且標籤表不受順序影響；
  - 各級欄位嚴格累加（L(k+1) 包含 L(k) 的所有欄位）；
  - L0 與 E7 的 `variable_text`、laya state/questions 逐位元組相同；
  - `parse_e8_answer` 的合法與非法輸入；
  - KEEP 解析；
  - 底線策略在手算例子上的結果。
- `test_e8_handoff.py`：
  - 觸發條件與最短間隔（假資料）；
  - SELECT／NOT_VISIBLE／無效回答的套用；
  - `MEASURED` 的 chain 與 EXPIRED；
  - 不掛決策器時 B1 重播與 `e3_f4_run.replay` 一致（用小型合成段）。
- `test_e8_score.py`：
  - 真值表三種情境；
  - 多數決；
  - H2 的 IUT（含容許值平移）；
  - Holm；
  - 選組同分規則。
- `test_build_e8_colab_pack.py`：
  - 假 GT 進不了任何請求檔；
  - 閘門失敗時整包刪除；
  - MANIFEST 正確。
- GT 隔離：`e8_requests`、`e8_handoff` 不 import 評分端模組（字串掃描）。

### 7.3 驗證點

| 代號 | 內容 | 在哪裡跑 |
| --- | --- | --- |
| V1 | B1 重現 28/28 段（`rows[].tracking` 完全相同） | Mac（打包時）＋Colab 格 8 |
| V2 | L0 請求與 E7 逐 tick 請求（`8568e4fa…`）在同一 tick 逐位元組相同（E3 的 68 點） | Mac |
| V3 | KEEP 對應率 100% | Mac |
| V4 | `verify_colab_pack_pre_upload` PASS，所有請求通過 `_scan_forbidden_gt_fields` | Mac |
| V5 | SMOKE：本機 CPU、stub 決策器、E3-A1＋E6-S01 兩段，notebook 從頭跑到尾；`e8_score_run.py` 在 SMOKE 輸出上跑完 | Mac |
| V6 | laya 截斷稽核有輸出（比例只報告，不設門檻） | Colab 格 5 |
| V7 | 探索性：E8 L0 的 laya 答案與 E7 逐 tick 答案（`2e23f37a…`）在同一請求的一致率（GPU 非位元級確定，只報告） | Mac（拿到 Colab 輸出後） |

## 8. 待協調者決定

| # | 問題 | 我的建議 |
| --- | --- | --- |
| Q1 | 第二部分要不要包含 L4（多 1.5 GB 畫面） | 先不包含：第二部分用最好的文字級，pack 約 0.1–0.2 GB。第一部分若 L4 明顯最好（L4−L3 在 S1 顯著），再補一個第二包 |
| Q2 | 新增 L0c（格式對照）與 L3F（完整 scene_context，只給 7B） | 加。L0c 是分開「格式」和「資訊」的唯一辦法；L3F 讓 L3 摘要和 API Agent 的完整版可以對照 |
| Q3 | E6 單點用 B1 凍結狀態，而 E6 預登 §3.2（#765）規定用 R-N 狀態 | E8 照 brief 用 B1 狀態。結果另外報告，**不**填入 E6 verdict 的 `single_correct`；#765 的 R-N 版維持 deferred |
| Q4 | H2 的錯人秒容許值 +14.0 s（每段 +0.5 s） | 採用；這是預登數字，執行後不能改 |
| Q5 | 主要比較對象選 laya_typed 與 qwen7b | 採用 |
| Q6 | 第二部分只用 `p0` 順序 | 採用；位置偏差在第一部分量 |

## 9. 每個數字的出處

| 數字 | 出處 |
| --- | --- |
| E7：laya_text 多錯 261.2 s、錯鏡頭 207.0 s；72%／65% 選第一個；2,058／2,037／2,516（／5,120）；`image_paths` 全空 | #767 協調者留言；LOCAL `e7-run-pertick-20261127/analysis/claude_coord_recheck_20261128.json` `00dd4f31…a000` |
| laya `max_len` 512／1024、`head_max_len` 192／256；截斷規則 | HF `convaiinnovations/laya` @`246177e5` 的 `rl_agent_config.json`、`typed-decisions/rl_agent_config.json`、`rl_common.py`（SHA `8d83611d…`，與 `LAYA_AUDITED_PY_SHA256` 相同）、`rl_agent_api.py`（`be3b4681…`） |
| 68＝38＋30；E3 type 分佈 | 兩份 E3 `CORPUS.json`（§1 SHA） |
| 48（VISIBLE 43、FULL_BLIND 5）；E6 type 24 種 | `e6_scenarios_frozen_v1.json` `5bab2766…`；E6 執行紀錄 R0 |
| 候選中位數 6、p90 12、最大 22；紅色中位數 4；4 m 內紅色分佈；B1 狀態 52／9／7 | LOCAL `e8-design-20261128/e8_design_dpstats.out.txt` `e0871687…` |
| 觸發估計 377（28 段，7,058 tick） | LOCAL `e8-design-20261128/e8_design_trigger_estimate.out.txt` `96fd0b86…` |
| scene_context 19,589 字元，SHA `3072cc5a…` | `e3_f4_run.live_scene_context`（本 session 在 `179bccb7` 上執行）；與 B1 b-log 欄位相同 |
| RGB 450＋670＋381 MB；E7 pack 115 MB | `du -sh`（本 session） |
| Qwen p50 5.4–6.0 s（E7 格式） | `767_replay_design.md` §2（協調者共享筆記，E7 GPU bf16 實測） |
| laya GPU 約 40 ms／筆 | #767、D416 |
| H2 容許值 +0.05／+5.0 s | E6 預登 §4（C2、C4）；+14.0 s 是本文件新定，待 Q4 確認 |
