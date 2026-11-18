# 即時模式重新取得（relock）契約 v1：分段門檻

- 日期：2026-11-18。狀態：**v1 草案，等 Codex 實作與量測**（尚無程式碼、無實測數字）。**範圍追加（D302 第 3 點，2026-11-18）**：不花錢備援（LLM_DECISION_V1 §0F.4 第 1 項的 T2 免費部分）併入本契約：失聯時主動接回（§2，本契約原本就是）、候選名單與連續性改用速度預測（§2.5、§3.4）、用重播驗收（§4.7、R-11～R-15）。同一個 tracker 改動、同一個 Codex 實作 issue。
- 依據：[#93](https://github.com/Polalalabear/amidst/issues/93) 的 D254-3（協調者建議「分段門檻」）、D282（使用者決定採用；#559 先合併，重鎖另案）；issue [#585](https://github.com/Polalalabear/amidst/issues/585)、[#552](https://github.com/Polalalabear/amidst/issues/552)（排程，ENTRY 重鎖轉本契約）。
- 實作：Codex（`owner:codex`，分支 `codex/feat-live-relock`）。規格：Claude（`claude/feat-live-relock`）。
- 相關文件：[LIVE_MODE_AB_V1](LIVE_MODE_AB_V1.md)（§5.4 `reselect`、§7.1 評分、§9.3 子 issue）、[LIVE_MODE_LLM_DECISION_V1](../design/LIVE_MODE_LLM_DECISION_V1.md)（§0A.5 第 4、5 項：外觀特徵、失聯時主動重新鎖定）、[#559 的 D273 報告](https://github.com/Polalalabear/amidst/blob/6843d8f36919ae29e2f0040dc8c2e38b8a041627/docs/evaluation/LIVE_DETECTION_SCHEDULE_D273_20261118.md)（@`6843d8f3`）。
- 本文只寫行為、介面和量測方法，**不含實作程式碼，也不訂門檻數字**：門檻秒數、速度、外觀距離都由重播量出來（§4）。量不出來時有明確的退回行為（§4.5），不憑感覺填。

## 0. 為什麼需要

現在的 `src/amidst/live_mode/tracker.py`（`Tracker`）只在紅衣候選落在「上次估計位置的 `gate_m`（重播用 4 m）」以內時才接回目標；超出就一直 `LOST`。D273 的實測：A4 ENTRY 再入鏡時，全開（`all`）tick 52 與 adaptive tick 62 都已查了 8 台、各有 2 個目標樣投影，但最近投影離前一個估計 **4.7596 m／4.6824 m**，超過 gate；結果是 baseline tracker 有觀測卻沒有重鎖（`BASELINE_TRACKER_NO_RELOCK`，`pass: null`）。#552 因此停在 `blocked-user`，D282 決定另開本契約。

目標：(1) 短失聯在 gate 內自動接回（現行行為，加上安全條件）；(2) 失聯久或候選在 gate 外時，放寬搜尋範圍，但**接回需要外觀確認**；(3) 多個候選都像目標時**不自動選**，標 `NEEDS_CONFIRM`；(4) **不設硬性的失聯時間上限**（D254-3）；(5) 輸入只能是鏡頭觀測。

(6) 追蹤落後目標時，不讓候選名單或連續性判斷把真正的目標排除在外（速度預測，§2.5、§3.4）；(7) 全部用重播驗收，**0 USD、不呼叫任何付費 API**。

不在範圍：身分判定（接回只代表「外觀與連續性最符合的假設」，身分仍未確認）、實體路徑／碰撞、新增 LLM 呼叫與任何付費測試（既有的 #563 開關與 `decider` 的提問、提示詞、ApiGuard 保持原樣，見 §3.3；「目標不在名單」的真模型測試是 #591，不在本契約）。

## 1. 輸入與 GT 隔離（不可變弱）

重鎖邏輯（`Tracker` 及其新增的外觀模組）只能讀：

| 允許 | 說明 |
| --- | --- |
| `dets`：每個鏡頭的偵測列表，鍵限於 `bbox`、`score`、`color`、`red_ratio`、`blue_ratio`，以及由**同一張影格像素**算出的外觀特徵（§2.4） | 即 `replay_schedule.py` 傳給 `Tracker.update` 的那幾個鍵 |
| `img_size`、`t_s`（capture 時鐘秒）、`tick` | 時間以 capture 時鐘為準，不用牆鐘 |
| 鏡頭標定（`Projector`，safe_static 的 `cameras.json`） | 只做像素→地面投影 |
| 排程結果（本 tick 實際處理了哪些鏡頭） | 只用來區分「沒看到」和「沒處理」，不含任何來自 GT 的資訊 |

**禁止**：scenario、`actor_id`／`role`／`variant`、真實位置、`gt_visible`、waypoints、玩家／操作者狀態、可見度、depth、渲染軌跡，以及「某種顏色／褲色等於某個角色」的對照表。外觀參考值只能是**系統自己在鎖定時從像素量到的目標特徵**（LLM_DECISION_V1 §0A.5 的隔離規則）。

GT 只在**所有重鎖運算完成之後**的離線評分用（`frontend/live-mode/measure/t1_analyze.mjs` 的分類規則與 AB 規格 §7.1 相同：距離 ≤ 1.5 m 才算跟對）。重播腳本的函式簽名不得收 scenario 或 GT 參數（沿用 `replay_schedule.py` 的作法：source observations only）。

## 2. 狀態機

### 2.1 狀態與子狀態

`tracking.state` 取值：`SEARCHING`、`TRACKING`、`LOST`（皆沿用）、**`NEEDS_CONFIRM`（新增）**。為了不改現有 `LOST` 事件與 `lost_after`（以 tick 計）的語意，短／長失聯用新欄位 `lost_phase` 表示，不新增 `state`：

| 欄位 | 值 | 說明 |
| --- | --- | --- |
| `lost_phase` | `null`（`TRACKING` 且本 tick 有配對）、`'short'`、`'long'` | `unseen_s = t_s − t_seen`；`unseen_s ≤ t_short_s` 為 `short`，超過為 `long`；`NEEDS_CONFIRM` 時固定為 `long` |
| `unseen_s` | 秒 | 從最後一次配對成功算起，每 tick 更新；不重置於 `NEEDS_CONFIRM` |
| `lost_ticks` | 整數 | **語意不變**：連續沒有配對的 tick 數；重鎖成功歸 0；`NEEDS_CONFIRM` 期間繼續累計。排程（§5）只讀這個欄位 |
| `confirm_candidates` | 列表，只在 `NEEDS_CONFIRM` 出現 | §3.2 |

評分端（AB §7.1）：`NEEDS_CONFIRM` 一律當**失聯**計（不是 `TRACKING`），不會被算成跟對，也不會被算成跟錯。

### 2.2 參數（集中在一個 `relock` 設定物件，測試可覆寫）

| 參數 | 預設 | 來源 |
| --- | --- | --- |
| `gate_m` | 4.0 m | 現行重播值（D254-3 的「4 m」）；不變 |
| `t_short_s` | **UNKNOWN，由 §4 量測** | §4.2 |
| `v_walk_m_s` | **UNKNOWN，由 §4 量測** | §4.3 |
| `tau_app`、`margin_app` | **UNKNOWN，由 §4 量測** | §4.4 |
| `same_m` | 1.5 m | 現行常數：不同鏡頭的候選距離 < 1.5 m 視為同一個人（沿用 `tracker.py` 的 `1.5`） |
| `ref_ticks` | 5 | 外觀參考值取最近 5 個「唯一配對」tick 的中位數；5 是實作預設，不是量測結果，允許覆寫 |

### 2.3 轉換

每 tick 先把紅衣候選依 `same_m` 聚成「人」（群），每群取最大分數那個偵測當代表；`d(c) = dist(群的 est_xy, 最後估計 est)`。

搜尋半徑：`R(u) = gate_m + v_walk_m_s · unseen_s`（**沒有時間上限、沒有另設最大半徑**；只受鏡頭投影本身的範圍限制，即現行 `Projector.ground` 的 `t ≤ 80`）。

| 目前 | 條件 | 動作 | 事件 |
| --- | --- | --- | --- |
| `TRACKING`、有群 `d ≤ gate_m` 且 `unseen_s ≤ t_short_s` 且**唯一**（沒有第二個 `d ≤ gate_m` 的群） | 短失聯、gate 內、候選唯一 | **自動接回**（現行行為），`lost_ticks=0` | `REACQUIRE`，`detail.mode='short_gate'` |
| 同上但 gate 內有 ≥ 2 群 | 短失聯、gate 內、多個候選 | 現行是選最近；**改為**走 §外觀確認（下一列），不再無聲選最近 | 見下 |
| `TRACKING` 或 `LOST`，有群在 gate 內但 `unseen_s > t_short_s`，或有群 `gate_m < d ≤ R(u)` | 長失聯，或候選在 gate 外 | **外觀確認**：對 `d ≤ R(u)` 的每群算 `d_app`（§2.4）；`d_app ≤ tau_app` 的算「通過」 | — |
| 外觀確認：恰好 1 群通過，且其他群的 `d_app ≥ 通過者 + margin_app` | 單一明確候選 | **自動接回** | `REACQUIRE`，`detail.mode='appearance'`，含 `unseen_s`、`dist_m`、`d_app` |
| 外觀確認：≥ 2 群通過，或唯一通過者與次佳差距 `< margin_app`，或 `tau_app` 為 UNKNOWN／0（不允許自動） | 不能唯一決定 | **不自動選**，`state = 'NEEDS_CONFIRM'`，est 凍結在最後估計 | `NEEDS_CONFIRM`（只在進入時發一次，之後只更新 `confirm_candidates`） |
| 外觀確認：有群在 `R(u)` 內但沒有一群通過 | 都不像目標 | **維持 `LOST`**（不接回，也不進 `NEEDS_CONFIRM`；避免對每個路人都問） | — |
| `LOST`／`NEEDS_CONFIRM`，`R(u)` 內沒有任何群 | 沒有候選 | 維持原狀態，`unseen_s` 繼續增加 | — |
| `NEEDS_CONFIRM`，候選集變成「恰好 1 群通過且與次佳差距 ≥ margin」 | 其他候選離開 | 自動接回（同 `mode='appearance'`） | `REACQUIRE` |
| `NEEDS_CONFIRM`，使用者／裁決選定其中一個 `cand_id` | 見 §3.3 | 以選定群接回，est 設為該群位置 | `REACQUIRE`，`detail.mode='confirmed'`，`detail.by='user'` 或 `'llm_hypothesis'` |
| 任一狀態，使用者改選別人（AB §5.4 `reselect`） | — | 不屬於本契約，照 AB 規格 | — |

重點：

- **`LOST` 與 `NEEDS_CONFIRM` 沒有失敗終點**：不設逾時、不自動放棄；`unseen_s` 一直累計，報表照列（§6 的失聯秒數）。
- 「候選在 gate 外」不論 `unseen_s` 多短都走外觀確認，所以 A4 ENTRY 的 4.76／4.68 m 不會落在「短失聯但超出 gate」的空洞裡。
- `ACQUIRE`（`SEARCHING` 時第一次鎖定）邏輯與 `same_m` 規則完全不變。
- `SWITCH`、`TARGET_OUT_OF_VIEW`、`LOST`（`lost_after` tick 數）事件語意不變。

### 2.4 外觀距離 `d_app`

- **參考值**：`TRACKING` 且最近 `ref_ticks` 個配對 tick 中，每個 tick 「目標所在的群」與其他群相距都 > `same_m`（沒有被別人混在一起）才取樣；參考值是這些 tick 的外觀特徵向量逐維中位數。取不到足夠樣本時參考值為 `null`，此時**所有**外觀確認結果都走 `NEEDS_CONFIRM`。
- **特徵向量**：只能由同一張影格的像素算出。起點是已有的 `red_ratio`、`blue_ratio`（`color.py` 的 `judge`）；LLM_DECISION_V1 §0A.5 第 4 項的下半身顏色（尚未做）可由 Codex 在 `color.py` 新增一個純函式加入。**加入哪些維度由 §4.4 的量測決定**：只保留在重播中能使「目標」與「同 tick 的其他人」分開的維度，每個維度要列出分離的數字；全部不能分開就如實寫「不能」（§4.5）。
- **距離**：特徵向量的 L2 距離（各維先以量測得到的尺度正規化，尺度也由 §4.4 輸出）。
- 不得用顏色名稱對角色的對照表；`d_app` 只比較「這個候選」與「系統自己的參考值」。

### 2.5 速度預測（D302，LLM_DECISION_V1 §0F.2 第 2a 項）

問題：現行以「上一個估計位置 `est`（凍結）」為圓心；追蹤器落後目標時（A4 實例落後約 3.5 m），真正的目標不在圓內。做法：圓心多一個**預測位置**。

- `pred(t) = est + v · min(unseen_s, pred_horizon_s)`；`v` 是目標自己的人物軌跡速度（`people.py` `PeopleTracker` 對該 `pid` 的 `v`，已有上限 `vmax = 2.5 m/s`），**只由鏡頭投影的估計算出**，不用 GT。目標軌跡不存在或 `v` 為零向量時，`pred = est`。
- **參考點集合 `{est, pred}`**：任何「候選到圓心的距離」改為 `min(dist(c, est), dist(c, pred))`。這適用於 §2.3 的 `d`（gate 內／外判斷與 `R(u)`）與 §3.4 的候選名單。**只放寬、不收緊**：原本 `est` 周圍的候選一律還在。
- `pred_horizon_s`：預設 **UNKNOWN，由 §4.7 量測**（掃 0、1、2、3 s，0 = 關閉）；`PeopleTracker.keep_s = 2.0 s` 是現有常數，不代表量測值。
- 設定旗標 `predict`（預設 `false`）：§4.7 驗收（R-12～R-14）通過才把預設改為 `true`，並在 PR 記錄；沒通過就保持關閉並報告，**不勉強打開**（避免 R-9 的既有行為變動）。

## 3. 事件與介面

### 3.1 事件（`tracking.events[]` 的形狀沿用 `{tick, type, cam, detail}`）

| `type` | 新／舊 | `detail` |
| --- | --- | --- |
| `REACQUIRE` | 舊（加 `detail`） | `{mode: 'short_gate'｜'appearance'｜'confirmed', unseen_s, dist_m, d_app?, by?}` |
| `NEEDS_CONFIRM` | 新 | `{unseen_s, n_candidates, reason: 'MULTIPLE_PASS'｜'LOW_MARGIN'｜'NO_APPEARANCE_REF'｜'APPEARANCE_NOT_SEPARABLE'}` |
| `ACQUIRE`、`SWITCH`、`TARGET_OUT_OF_VIEW`、`LOST` | 舊 | 不變 |

原本 `REACQUIRE` 沒有 `detail`，下游（`server.py`、`protocol.mjs` 的 nested 白名單、評分）要容許新的 `detail` 形狀；白名單更新由 §7 的 R2 與 #571／#572 處理。

### 3.2 `confirm_candidates`（只在 `NEEDS_CONFIRM`）

```
[{cand_id, cam, est_xy, bbox, dist_m, d_app, rank}]   // 依 d_app 由小到大，最多 5 個
```

`cand_id` 綁 session 與 epoch，語意和 AB §5.4 的候選表相同（不重複定義）。**不含**任何 GT 或角色資訊；`est_xy` 是系統自己從像素投影的位置。送到 B 的欄位要通過 AB §5.2 的 nested 白名單檢查，白名單新增項由 #571／#572 在其範圍內加（本契約只規定欄位內容）。

### 3.3 離開 `NEEDS_CONFIRM` 的方式

1. 自動：候選集變得唯一（§2.3 倒數第三列）。
2. 使用者在 B 選其中一個候選：走 AB §5.4 的既有 `reselect` 路徑，**不新增端點**（本契約不新增任何 HTTP 端點）。
3. 既有的 LLM 裁決（#563 開關，預設關；開時只在 `NEEDS_CONFIRM` 候選上做影像裁決）：結果只算「外觀最符合的假設」，`detail.by='llm_hypothesis'`，身分仍未確認。新增 LLM 呼叫須另外核准（ApiGuard、dry-run、使用者核准金額）；本契約的驗收**不**依賴 LLM。

### 3.4 候選名單（`LiveDecider` 的提問池，D302）

- 現行（`src/amidst/live_mode/advisor.py` 的 `LiveDecider`）：問題池是「距上一輪估計 `prev_est` 在 `gate_m` 內的人」，且至少 `lost_min_candidates`（預設 2）個才發問。
- 新：池 = 距參考點集合 `{est, pred}`（§2.5）任一點在 `gate_m` 內的人，依 `min` 距離由近到遠，**仍最多 `max_candidates`（預設 4）個**，仍至少 `lost_min_candidates` 個才發問；提問、提示詞、圖片、ApiGuard、「都不是」的回答語意**全部不變**。
- 影響範圍只在名單怎麼挑：不新增 LLM 呼叫，不新增送出的欄位（仍然是兩張 JPEG 與候選數，無座標、無角色）。
- `predict = false` 時名單與現行逐 tick 相同。

## 4. 門檻秒數怎麼量（不憑感覺填數字）

### 4.1 資料與環境

- 資料：D273 的固定 RGB 錄製（C 來源，37 檔，`.t1raw.json`；見 `local/evidence/cx552-d-20261118/MANIFEST.json`，SHA-256 `803e6e09ade8ab128f9e7387e42cf568127858832335892389aff7348f507090`，80 檔／6,482,648 bytes；C 來源子資料夾的確切路徑 UNKNOWN，由 Codex 從 MANIFEST 列出）。涵蓋 A4 與 B4。另外 D273 新實跑的 4 組（A4 58 s／B4 50 s）可作為補充，但**不與固定 RGB 的數字混算**。
- 不渲染、不呼叫付費 API、不改素材與 scenario；只讀。
- 重播只用 §1 的輸入；GT 只在重播輸出之後做評分。

### 4.2 `t_short_s`（短失聯自動接回的最長失聯時間）

1. **取 episode**：離線評分把每一段「GT 顯示目標在至少一個鏡頭可見、但 tracker 沒有 TRACKING 在目標上」的區段叫一個 episode（前面必須有一段正確的 TRACKING；首次出現前的不算）。每個 episode 記：`unseen_s`、gate 內有幾群、其中哪一群是目標、目標群離最後估計的 `dist_m`。
2. **掃描**：對 `T ∈ {1, 2, 3, 4, 6, 8, 10}` 秒重播（`--sweep-t-short`），統計「`unseen_s ≤ T` 且 gate 內自動接回」的**錯接次數**（接到別人）與**正確接回次數**。
3. **取值**：取使**錯接 = 0**的最大 `T`；若沒有任何 `T` 滿足（連 1 s 都有錯接），`t_short_s` 取 0（短失聯自動接回關閉，gate 內也走外觀確認）。報告：episode 總數 `N`、各 `T` 的錯接／正確表（含沒接上的）、A4 與 B4 分開的值。兩個場景不一致時取較小者。
4. **樣本不足**：`N < 10`，或某個 `T` 分母 < 5，該 `T` 的結論標 `UNKNOWN`，不外推；§4.5 的退回行為生效。

### 4.3 `v_walk_m_s`（搜尋半徑成長速度）

- 由**系統自己的估計**量：所有「連續兩個 `TRACKING` 配對 tick」的 `dist(est_k, est_{k−1}) / Δt_capture`，取 p95；去掉 Δt < 0.05 s 的（取樣噪音）。**不用 GT 速度**。
- 離線對照（只在評分時，不進產品）：同樣算 GT 目標速度的 p95，兩者並列，差距太大（> 30%）要在報告說明原因（投影抖動或取樣）。
- 報告 `N` 與 p50／p95／最大值。

### 4.4 `tau_app`、`margin_app` 與外觀維度

1. 對每個 episode 中目標重新入鏡的 tick，收集：目標群的 `d_app`（相對 §2.4 的參考值）與同 tick 其他群的 `d_app`。
2. 對每個候選外觀維度與組合，輸出：目標群與其他群 `d_app` 的分布（p5／p50／p95）、最大可分離邊界 `gap = min(其他群 d_app) − max(目標群 d_app)`。
3. **取值**：只在 `gap > 0` 時才允許自動：`tau_app = max(目標群 d_app)` 加上 `gap` 的一半；`margin_app = gap / 2`。`gap ≤ 0`（分布重疊，例如兩個人都穿紅衣、`red_ratio` 分不開）→ `tau_app = 0`（不允許外觀自動接回，§2.3 全部走 `NEEDS_CONFIRM`），報告寫「目前特徵不能分開」。
4. 小樣本警告同 §4.2。不得用顏色名稱對角色表來湊出分離。

### 4.5 量不出來時的退回行為（先把安全的部分做出來）

| 量測結果 | 退回 |
| --- | --- |
| `t_short_s` 為 UNKNOWN | 保持現行 gate 內自動接回（等於 `t_short_s = ∞`），但多個候選時仍走 §2.3（不再無聲選最近） |
| `v_walk_m_s` 為 UNKNOWN | `R(u)` 暫時用現行 `max_gate_m`（8.0 m），並在報告標「暫用，非量測值」；這是唯一一處暫時的上限，量到後取消 |
| `tau_app` 為 UNKNOWN 或 0 | 所有外觀確認結果走 `NEEDS_CONFIRM`，不自動接回；ENTRY 案例就會以 `NEEDS_CONFIRM`（含正確候選）收尾，這仍然符合 §6 的 R-4 |

### 4.6 重播與評分指令（Codex 在 PR 補完整參數並記錄實際輸出）

```bash
python scripts/live_mode/replay_relock.py \
  --src C=<C 來源錄製資料夾，見 MANIFEST> \
  --cameras <local/data/r004-build-v2-20261021/safe_static/cameras.json> \
  --out <新的 LOCAL 輸出資料夾> \
  --sweep-t-short 1,2,3,4,6,8,10
node frontend/live-mode/measure/t1_analyze.mjs <上一步輸出資料夾下的各 *.t1.json>   # 離線評分（可用 GT）；實際參數以 PR 為準
```

`replay_relock.py` 是新檔，輸入慣例沿用 `scripts/live_mode/replay_schedule.py`（只讀 `bbox`／`score`／`color`／`red_ratio`／`blue_ratio` 與 capture 時鐘；其餘欄位不傳進 tracker）。評分指令的確切參數：UNKNOWN，Codex 在 PR 的「Commands run」寫出實際值。輸出必須含 §4.2～§4.4 的表與 `N`，並把每份輸入的 SHA-256 記進報告。

### 4.7 速度預測與候選名單的重播驗收（不花錢）

- 資料：LOCAL 已錄好的即時模式紀錄（`local/evidence/live-mode-*`，LLM_DECISION_V1 §0F.4 第 2 項已指明；確切子資料夾 UNKNOWN，Codex 列清單與 SHA-256）與 §4.1 的固定 RGB。
- 重播器：`scripts/live_mode/replay_advisor.py`（已存在）以**替身回答**重播裁決時刻，不呼叫任何付費 API、不需金鑰；替身規則沿用 #544 修好後的版本（LLM_DECISION_V1 §0F.1 更正）。GT 只在重播之後的評分用。
- **名單遺漏率** `pool_miss`：在每個發問時刻，評分端 GT 的目標在某鏡頭看得到、且系統有一個投影在目標 1.5 m 內的紅衣候選，但該候選不在名單內，算一次遺漏。報告：遺漏次數、發問時刻總數、遺漏率；`predict` 關／開並列，`pred_horizon_s ∈ {0,1,2,3}` 掃描。
- **取值規則**：取使 `pool_miss` 最低、且滿足 R-12～R-14 的最小 `pred_horizon_s`；`pool_miss` 沒有任何下降就保持 `predict=false`。樣本不足（發問時刻 < 20，或遺漏 < 3）標 `UNKNOWN`，不外推。
- **給 #591 的副產品**：輸出一份「目標不在名單」時刻清單（`predict` 關時），含每筆的 session／tick／鏡頭，並數出題數；這是 D302 第 2 點（sol6.1、上限 USD 0.2）要的題數。本契約**不**執行該付費測試。
- 指令（Codex 在 PR 補完整參數）：

```bash
python scripts/live_mode/replay_advisor.py <參數 UNKNOWN：照該腳本現有 --help，加 --predict-horizon 0,1,2,3> --out <新的 LOCAL 輸出資料夾>
```

## 5. 與 #559 排程的介面

#559（`scheduler.py`，D273 的「近 2 秒內任一像素紅衣候選鏡頭保留」）**先合併，不為本契約修改**（D282）。介面只有一條：

- 排程讀 `tracker.active` 與 `tracker.lost`（現有簽名 `plan(active, lost, available)` 不變）。本契約保證 `lost_ticks` 語意不變（§2.1），且在 `LOST`／`NEEDS_CONFIRM` 期間持續累計，所以 `adaptive` 排程會照原本規則放寬到更多鏡頭，**不需要改 `scheduler.py`**。
- 要接回，候選必須先被處理到：`NEEDS_CONFIRM` 或長失聯時，排程不得因「省算力」把有紅衣候選的鏡頭排掉；這由 #559 既有的 `recent_red_s` 保留規則滿足，**驗收 R-6** 以 A4 ENTRY 重播確認（不改排程邏輯，只確認它夠用）。若確認不夠，另開 issue，不在本契約內改 `scheduler.py`。
- `lost_phase`／`unseen_s` 可作為日後排程參考的欄位，**本版不使用**。

## 6. 可測驗收

測試檔（Codex 可更名但要在 issue 回覆）：`tests/live_mode/test_relock.py`（純 tracker 單元）、`tests/live_mode/test_relock_replay.py`（重播腳本）；既有測試檔不得因本契約變弱。

| 編號 | 條件 |
| --- | --- |
| R-1 | **GT 隔離**：`Tracker` 與外觀模組不 import scenario、不收 GT 欄位；測試把 `actor_id`／`gt_visible`／`xy` 等欄位塞進 `dets` 後，輸出與沒塞時逐 tick 相同；`replay_relock.py` 的函式簽名沒有 scenario／GT 參數（靜態檢查＋測試） |
| R-2 | **短失聯、gate 內、唯一候選**（合成觀測，`unseen_s ≤ t_short_s`）：自動 `REACQUIRE(mode:'short_gate')`；同一情況但 gate 內有第二個候選：**不**自動選最近，進外觀確認（結果為 `appearance` 接回或 `NEEDS_CONFIRM`） |
| R-3 | **長失聯／gate 外**（合成）：候選在 `d = gate_m + 0.76 m`、`unseen_s ≤ t_short_s` 時，不走 `short_gate`，走外觀確認；`d_app ≤ tau_app` 且次佳差距 ≥ `margin_app` → `REACQUIRE(mode:'appearance')`；兩個都通過 → `NEEDS_CONFIRM`，`confirm_candidates` 長度 2、按 `d_app` 排序、**沒有自動選**；候選都不通過 → 維持 `LOST`，不進 `NEEDS_CONFIRM`；`R(u)` 外的候選被忽略 |
| R-4 | **A4 ENTRY 再入鏡案例**（D273：`all` tick 52，adaptive tick 62，最近投影 4.7596／4.6824 m）：在 R-3 的規則下，該 tick 的結果必須是以下之一：(a) `REACQUIRE` 到**正確**目標群（離線評分用 §1 的 1.5 m 規則），或 (b) `NEEDS_CONFIRM` 且 `confirm_candidates` 含正確目標群。**不得**自動接到錯的人。報告把兩個延遲**分開列**：「正確候選第一次被呈現（自動接回或 `NEEDS_CONFIRM`）的 `t_capture` − 該人再入鏡的第一個 capture」與「正確的自動接回延遲」（後者不一定有值，沒有就寫 `null`，不當成通過也不當成失敗） |
| R-5 | **錯接 = 0**：§4.1 整個重播集（A4、B4，`all` 與 `adaptive` 兩種排程）中，自動 `REACQUIRE` 接到錯誤目標群的次數 = 0；`NEEDS_CONFIRM` 次數與每次持續秒數另列，不設閘門 |
| R-6 | **不退步**：固定 RGB 上，A4 跟對 ≥ 0.705263、失聯 ≤ 0.042105 + 0.02；B4 跟對 ≥ 0.966667、失聯 ≤ 0.016667 + 0.02（D273 的 `all`／`adaptive` 相同值）；`NEEDS_CONFIRM` 依 AB §7.1 當失聯計；`protocol_violations = 0`。ENTRY 案例用 #559 的 `adaptive` 排程重播一次，確認候選有被排程處理到（§5） |
| R-7 | **無硬性上限**：合成測試讓目標失聯 600 秒後再入鏡一個外觀符合的候選：仍可接回（或 `NEEDS_CONFIRM`），不因時間而丟棄狀態；`unseen_s` 單調遞增 |
| R-8 | **退回行為**（§4.5）：`relock` 設定中各量測值為 `null` 時，行為符合表中的退回，測試覆蓋三種 `null` |
| R-9 | **既有行為不變**：既有 `tests/live_mode` 測試全數通過；`ACQUIRE`、`SWITCH`、`TARGET_OUT_OF_VIEW`、`LOST`（`lost_after`）事件在既有合成案例下與修改前逐 tick 相同；`git diff --check`、ruff、architecture guard 通過 |
| R-10 | **量測可重現**：§4.2～§4.4 的表由 `replay_relock.py` 產生，輸出含 `N`、輸入 SHA-256、指令；重跑得到相同的表（確定性，不含隨機） |
| R-11 | **預測圓心（單元，合成）**：目標以 1.2 m/s 走、投影落後 3.5 m（A4 實例量級）時，`predict=true` 的候選名單含真正目標，`predict=false` 不含；`unseen_s > pred_horizon_s` 後預測位置不再外推（停在 `horizon` 處）；目標軌跡不存在時 `pred = est` |
| R-12 | **只放寬**：任何輸入下，`predict=true` 的名單是 `predict=false` 名單的超集（受 `max_candidates` 截斷前）；`predict=false` 時名單、事件與現行逐 tick 相同（回歸測試） |
| R-13 | **重播不退步**：§4.7 的重播中，`pool_miss`（`predict` 開）≤ 關；跟錯 tick 比例與錯接數不高於關（R-5 同標準）；發問次數增加量在報告列出，且每題候選數 ≤ `max_candidates` |
| R-14 | **0 USD 且隔離**：重播不呼叫付費 API、不讀金鑰；`PeopleTracker`、`LiveDecider` 新程式不收 GT 欄位（同 R-1 的塞欄位測試）；送出的訊息欄位與現行相同（測試比對鍵集合） |
| R-15 | **清單可交接**：重播輸出「目標不在名單」時刻清單與題數（§4.7），含輸入 SHA-256 與指令，重跑相同（確定性） |

## 7. 檔案範圍、owner 與先後順序

### 7.1 檔案範圍

| 檔案 | owner | 備註 |
| --- | --- | --- |
| `src/amidst/live_mode/tracker.py` | **Codex**（本契約實作期間；Claude 不改） | 先前「Claude 正在改 tracker.py」的限制在此解除，Codex 可以改 |
| `src/amidst/live_mode/advisor.py`（**只改** `LiveDecider` 挑名單的部分，§3.4）、`src/amidst/live_mode/people.py`（只加公開的預測讀取；不改 `group()` 與其他邏輯） | Codex | D302 追加；#559 沒改這兩個檔（D273 報告），無衝突。提問／提示詞／ApiGuard 不動 |
| `src/amidst/live_mode/color.py`（新增外觀特徵純函式，如需要） | Codex | 不改 `judge` 的既有回傳 |
| 新增外觀模組（如 `src/amidst/live_mode/appearance.py`） | Codex | 純函式，無 I/O、無網路 |
| `scripts/live_mode/replay_relock.py`、`tests/live_mode/test_relock*.py` | Codex | 新檔 |
| `src/amidst/live_mode/server.py`（把 `state`／`lost_phase`／`unseen_s`／`confirm_candidates` 帶進 `tracking`） | Codex，**R2，等 #559 合併** | #559 已改 `server.py`，避免衝突 |
| `frontend/live-mode/src/protocol.mjs`（nested 白名單加 `NEEDS_CONFIRM`／`confirm_candidates`／`lost_phase`／`unseen_s`／`REACQUIRE.detail`） | #571／#572 的範圍 | 本契約只規定欄位內容 |
| `src/amidst/live_mode/scheduler.py` | **不改**（#559 的檔） | §5 |
| `llm_switch.py`、`advisor.py` 的提問／提示詞／ApiGuard 部分、`people.py` 的 `group()`、scenario、LOCAL 資產 | 不改 | 可唯讀引用 `people.py` 的分群 |

### 7.2 先後順序

1. **#559 先合併**（D282；Codex 先解 #563 衝突，轉 Ready，Claude 審查，使用者合併）。#552 的偵測率與排程驗收維持原結論；ENTRY 重鎖項轉本契約，不算排程失敗。
2. **R1（`ready`，不依賴 #559）**：純 `Tracker` 狀態機＋外觀特徵＋速度預測與候選名單（§2.5、§3.4）＋`replay_relock.py` 與 §4 量測（含 §4.7 重播）＋R-1、R-2、R-3、R-5、R-7、R-8、R-9、R-10、R-11～R-15，及 R-4／R-6 的 `all` 排程部分。理由：量測用的是固定 RGB 的 `all` 錄製，不經過 #559 的排程。
3. **R2（`blocked`：#559 合併、R1 完成）**：`server.py` 把新欄位帶進 `tracking`；R-4／R-6 用 #559 的 `adaptive` 排程重播；ENTRY 結果回貼 #552。
4. **#571（後台 `/track/*`，`blocked` 於 #559）**：與 R1 可平行；#571 在 R2 前遇到未知 `state` 一律當失聯處理（不崩潰），R2 合併後處理 `confirm_candidates` 與 `reselect`。
5. **#572（B 的 HUD 與候選疊圖）**：在 #571 與 R2 之後顯示 `NEEDS_CONFIRM` 的候選；在此之前 HUD 把 `NEEDS_CONFIRM` 顯示成「待確認／失聯」即可。
6. **#574 整合**：R2 與 #568～#573 都完成後。
7. 單一 feature 一個 PR（D216、D248）：`codex/feat-live-relock` 同一個 Draft PR，R1、R2 分階段 commit；Claude 在 R2 完成後審查。

## 8. 風險與未驗證

- **速度預測可能讓名單變大、問題變多，或讓同色旁人搶走**（範圍越大越容易，LLM_DECISION_V1 §0F.3 D244 限制）；所以預設關、驗收通過才開（§2.5、R-13）。速度只來自投影估計，抖動大時 `pred` 會偏，`vmax` 夾住上限。
- 「目標不在名單時真模型會不會答『都不是』」不在本契約，仍待 #591（sol6.1，上限 USD 0.2）。

- **本版沒有任何實測數字**。§4 的門檻、速度、`tau_app` 都是待量測；若 `gap ≤ 0`（外觀特徵分不開兩個紅衣人），外觀自動接回等於關閉，所有長失聯接回都要人確認，展示上會出現較多「待確認」，這是誠實的結果，不是失敗。
- **樣本小**：固定 RGB 只有 A4／B4 各一組，ENTRY 案例只有一個；`N` 小時結論標 `UNKNOWN`，不外推到其他場景。
- **外觀特徵可能不夠**：`red_ratio`／`blue_ratio` 是上半身衣色；兩個人上衣同色時分不開。下半身顏色目前沒有實作（LLM_DECISION_V1 §0A.5 第 4 項「沒有做」）。
- **取樣率**：tick 間隔不固定（約 2–5 fps，延遲波動），所以門檻以 capture 時鐘秒計，不以 tick 計；`lost_after` 仍是 tick 數（保留）。
- **投影誤差**：4.7596 與 4.6824 m 差 0.08 m，投影抖動可能和這個量同級，`R(u)` 不要貼著 gate 邊緣設計。
- 不證明身分，不證明物理安全；接回只是「連續性＋外觀最符合的假設」。
- D273 的 ENTRY 項在 baseline 自身為 censored（`pass: null`）；本契約的 R-4 把延遲分開列，避免把 `null` 當通過。

## 9. 實際產出 / Actual output

見 PR 描述。D302 追加的 §2.5、§3.4、§4.7 同樣沒有實測；`advisor.py` 的現行名單規則取自 main 的程式讀取（未執行）。本文件為規格，無程式碼、無新的實測數字；§0 與 §4.1 的數字全部取自 D273 報告（@`6843d8f3`）與 #568 留言，未重新執行。
