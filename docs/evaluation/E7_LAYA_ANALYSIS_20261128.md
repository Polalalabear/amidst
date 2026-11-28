# E7 laya 分析：為什麼不如預期（2026-11-28）

> 來源：協調者核對 LOCAL `e7-run-pertick-20261127/analysis/claude_coord_analysis_20261128.md`（SHA-256 `957b47559a481bb20e9e7016717401af0f6e4c02b7406599a3c52ec093e5f2d4`），同內容貼在 [#767 留言 7224614486](https://github.com/Polalalabear/amidst/issues/767#issuecomment-7224614486)；D416 補記見 [#767 留言 7225067592](https://github.com/Polalalabear/amidst/issues/767#issuecomment-7225067592)。本文件把它收進 repo（E8 #780 的前因），§4 新增 E8 W2 離線合成基準。身分一律 `UNCONFIRMED`。

## 0. 結論

- laya **不進 LIVE demo，demo 只用規則 B1**（D416）。
- 40 ms 延遲不是問題。問題在 E7 的**題目設計**：laya 每次只拿到各鏡頭偵測框的平面清單，不知道目標是紅色，也不知道上一刻在哪。結果它幾乎只挑清單第一個候選。
- 「跟錯人」大多不是同一畫面裡的紅衣人太像，而是**整台鏡頭選錯**。
- **E7 不是 Agent 與規則的公平比較**（D416）。B1 和 E5 API Agent 都有、laya 請求卻沒有的資訊：
  - 目標是紅色：B1 見 `tracker.py:130`；API 端是 `agent_service` 的 `COLOUR_NO_MATCH`。
  - 上一個位置與地面座標：B1 用 4 m 門檻；API 端是 `AO_STATE` 的 est_xy。
  - 鏡頭連通：API 端有 scene_context。
  - 參考圖和畫面。
- E7 包本來就是「無狀態快照」，用來量本機模型的速度和單點判斷，所以它只說明一件事：**沒有目標資訊時，模型只能照位置猜**。公平比較改由 E8（#780，D417）處理，設計見 [E8_DESIGN_V1.md](E8_DESIGN_V1.md)。

所有數字都在 `claude/feat-e7-laya`@`179bccb7` 上重跑重播算出，評分器是釘選的 `e3_scoring.py`（`acacce39…7d08`），沒有引用 Codex 的數字。總計和 #767 第二部分一致（375.2／323.8／8／12）。

## 1. 錯誤秒數拆分（E3 16 段，可見 825.6 s）

| 組 | 錯鏡頭 s | 鏡頭對、人錯 s | 合計錯人 s | 失聯 s | 盲區誤鎖 s | 跟對率 | DP |
|---|---:|---:|---:|---:|---:|---:|---:|
| B1 規則 | 73.8 | 40.2 | 114.0 | 85.0 | 109.4 | 0.759 | 28/68 |
| AOL（GPT，約 4.8 s 延遲） | 91.0 | 19.2 | 110.2 | 510.6 | 31.8 | 0.248 | 6/68 |
| laya_text | 280.8 | 94.4 | 375.2 | 43.6 | 169.0 | 0.493 | 8/68 |
| laya_typed | 254.0 | 69.8 | 323.8 | 55.4 | 180.8 | 0.541 | 12/68 |

laya_text 比 B1 多錯 261.2 s，其中 207.0 s（79%）是錯鏡頭；laya_typed 多錯 209.8 s，其中 180.2 s（86%）是錯鏡頭。

## 2. 三個問題

**(1) 規則和模型為什麼差這麼多？** 兩者的輸入一樣是凍結的偵測框，但決策方式不同。

- **B1**（`src/amidst/live_mode/tracker.py:128-160`，設定在 `scripts/evaluation/e3_f4_run.py:40`）每個 tick 做三件事：
  1. 只保留紅色候選。
  2. 投影到地面。
  3. 選離上一個估計位置 4 m 內最近的候選；沒有就判定看不到。

  所以 B1 內建三個先驗：目標是紅色、人不會瞬移、沒有就不選。
- **laya** 每次都從平面清單重新挑一個（`src/amidst/evaluation/e7_decider_eval.py:627-705`），提示只說「選出最可能是追蹤目標的候選」。
  - 選項文字只有鏡頭、編號、框和分數，沒有顏色（`:681`）。顏色只出現在 context 裡（`scripts/evaluation/build_e7_colab_pack.py:74`），沒有任何地方說要找紅色。
  - 請求也沒有上一個位置、地面座標或鏡頭連通。
  - 5,223 筆逐 tick 請求的 `image_paths` 全是空的。
- **實測（快照判定）**：

  | 指標 | laya_text | laya_typed | 只選清單第一個 | 只選第一個紅色候選 |
  | --- | ---: | ---: | ---: | ---: |
  | SELECT 選到清單第 1 個候選 | 72%（3,632/5,043） | 65%（3,330/5,116） | — | — |
  | 正確數（共 5,120） | 2,058 | 2,161 | 2,037 | 2,516 |

  laya_text 的正確數幾乎等於「只選清單第一個」；「只選第一個紅色候選」比兩版 laya 都好。

**(2) AOL 加了延遲，錯人秒數為什麼接近規則？** 因為它大部分時間什麼都沒顯示，不是因為它判得好。

- GPT 的答案約 4.8 s 後才到。`chain_box`（`src/amidst/live_mode/aopen/neutral.py:18-26`）要把發問當時的框沿每個 tick 的偵測串到生效那一刻。
- 中途斷掉就記 `EXPIRED`，答案不套用（`src/amidst/live_mode/aopen/decider.py:204-209`）。186 次呼叫中有 98 次 EXPIRED，只有 72 次套用。
- 評分器把「目標看得見但沒顯示」記為 `LOST`，不算錯人（`src/amidst/evaluation/e3_scoring.py:101-106`）。所以 AOL 有 510.6 s 失聯，跟對率只有 0.248，DP 只有 6/68。

**(3) 同樣是結構化輸入，laya 為什麼更差？** 因為它的輸入其實比 B1 和 E5 AO 都少。

- **沒有「紅色」條件**：目標就在候選裡、laya 卻選了非紅色候選的情況有 631 筆（laya_text 快照）。
- **沒有空間連續性**：B1 的 4 m 門檻正是擋住跳到別台鏡頭的關卡，所以 laya 的錯誤主要是錯鏡頭。
- **不會棄權**：
  - 5,223 筆中 NOT_VISIBLE 和 `STILL_HERE_OCCLUDED` 都是 0 次。
  - UNCERTAIN 有 180／107 次，其中 103 次是沒有任何候選的 tick。
  - 目標在所有鏡頭都看不見的快照有 994 個，laya 在 982／993 個裡選了人，盲區誤鎖因此高於 B1。
- **套用時已經選錯**：
  - 以發問當刻判定已套用的選人答案，laya_text 只有 231/522 正確（錯鏡頭 141、目標不可見 106、同鏡錯人 44）；typed 是 248/530。
  - 答案下一個 tick 就生效（40 ms），之後 `NeutralTracker` 每個 tick 用 IoU≥0.3 續追（`neutral.py:59-84`）。錯的框會一直延續到下一次發問（POLL 2 s，LOST_EARLY 1 s；`decider.py:251-254`）。
- **顏色只解釋一部分**：
  - 5,223 個快照中有 4,817 個有 ≥2 個紅色候選，因為 HSV 判色把多數人都標成紅色。
  - 真的選錯人的 1,918 筆（laya_text）裡，有 1,286 筆兩邊都是紅色，這部分光靠顏色分不開；其餘 631 筆是 laya 根本沒用上顏色。

## 3. Codex 六項主張核對

| 主張 | 核對結果 |
|---|---|
| 多出的錯誤約八成來自錯鏡頭 | **成立**（79%／86%，重算） |
| 請求沒有目標條件、初始參照、上一個可靠位置、鏡頭連通；`image_paths` 全空 | **成立**（程式碼與 5,223 筆資料） |
| laya 從不棄權、沒回答過 NOT_VISIBLE | **大致成立**：NOT_VISIBLE 和 OCCLUDED 都是 0 次，但 UNCERTAIN 有 180／107 次，多數在沒有候選的 tick；UNCERTAIN 只是維持原目標 |
| 每 2 秒問一次，錯選被 `NeutralTracker` 延續 | **成立**；另外，5,223 筆逐 tick 答案只用到 601／602 筆（約 11.5%） |
| 沒選中候選時自動填清單前三台鏡頭 | **程式碼成立**（`e7_decider_eval.py:725`），但**不影響錯人秒數**：排名只影響下一次的候選排序（重播時略過）和 top-k 計分，不影響追蹤 |
| AOL 錯人秒接近 B1，是因為有 510.6 s 失聯 | **成立**；機制是 98／186 次 EXPIRED |

Codex 沒提到、但影響最大的一項是**位置偏差**：72%／65% 選清單第一個候選，準確度和「永遠選第一個」相同。E8 因此加了三種選項順序（p0／p1／p2）和 FIRST、RANDOM、FIRST_RED、NEAREST_RED 底線組。

## 4. E8 W2：閉迴路合成答案基準（離線，0 推論、0 付費）

用 E7 全段重播（`scripts/evaluation/e7_replay_run.py`，`chain_start='snapshot'`），逐 tick 用合成答案替換模型答案，延遲固定 40 ms，評分器同 §1。腳本是 `scripts/evaluation/e8_w2_offline_baselines.py`，由 session `e8-offline-b` 寫成，收進本 PR 時只改了路徑：`amidst.paths`、不用絕對路徑、repo 根目錄自動推得。

| 組 | 跟對率 | 合計錯人 s | 盲區誤鎖 s | DP |
|---|---:|---:|---:|---:|
| B1 規則 | 0.759 | 114.0 | 109.4 | 28/68 |
| 永遠選清單第一個（`a_first`） | 0.494 | 370.2 | 171.2 | 13/68 |
| 永遠選第一個紅色（`b_first_red`） | 0.611 | 278.6 | 175.6 | 13/68 |
| 隨機（3 個種子平均） | 0.440 | 428.8 | 187.3 | 5.7/68 |
| laya_text（原答案，40 ms） | 0.493 | 375.2 | 169.0 | 8/68 |
| laya_typed（原答案，40 ms） | 0.541 | 323.8 | 180.8 | 12/68 |

- **閉迴路印證位置偏差**：laya_text 的跟對率 0.493 和「永遠選第一個」的 0.494 幾乎相同，錯人秒數也相近（375.2 對 370.2 s）。
- 信心門檻組（`d_*_tau*`，τ＝0.5–0.9，低於門檻改答 UNCERTAIN 或 NOT_VISIBLE）的門檻是在同一批 16 段上挑的，只算**探索**。它們的錯人秒數下降，但跟對率也一起掉到 0.01–0.30，沒有任何一組同時贏過 B1。
- `ref_*_orig_latency`（用記錄下來的 laya 延遲）和 40 ms 版本數字相同，確認延遲不是原因。

## 5. 證據（LOCAL，相對 `local/evidence/`）

| 檔案 | SHA-256 | 可否重建 |
| --- | --- | --- |
| `e7-run-pertick-20261127/analysis/claude_coord_analysis_20261128.md` | `957b47559a481bb20e9e7016717401af0f6e4c02b7406599a3c52ec093e5f2d4` | 文字紀錄 |
| `e7-run-pertick-20261127/analysis/claude_coord_recheck_20261128.json` | `00dd4f31cf3519e6103277a52233984771e010f32787d10ea7a18d766da67000` | 用下列兩支腳本和同一批輸入重建 |
| `e7-run-pertick-20261127/analysis/claude_coord_analyze_laya_20261128.py` | `7dd17bb8835395a2bf2ced799017426072f0ffad87d0d873de2e551b49cbc14e` | 腳本（LOCAL，不進 repo） |
| `e7-run-pertick-20261127/analysis/claude_coord_first_bias_20261128.py` | `382297cac938c5be008dc7a011b7ed17904d6d25c77092240b905daea7a592b1` | 腳本（LOCAL，不進 repo） |
| `e7-run-pertick-20261127/e7-outputs-pertick/e7-run-20261127/e7_raw_comparisons.json`（逐 tick 答案） | `2e23f37a3d879c7c4962c56051c70a6e3300bdf9993de469bc1cdd6ea798b3cb` | Colab 輸出，不可重建（GPU 答案非逐位元相同） |
| `e7-colab-pack-pertick-20261127/requests/e3_16_segments.jsonl`（逐 tick 請求） | `8568e4fa26c168d537f8de7ec29001f94cc5d99f4fd5fd9906e38f186cc28dee` | `build_e7_colab_pack.py` 重建 |
| `e8-offline-b-20261128/e8_w2_offline_baselines.json`（§4） | `7cd069bcf065da71c2e72fcfe580a9caa7c6243c68932fd7a82979aa76a79878` | `python scripts/evaluation/e8_w2_offline_baselines.py <out.json>` |

B1 和 AOL 的 b-log 分別在 `f4-658-20261122/runs-final-{9,665}` 和 `e5-aol-20261124/runs-{9,665}`。
