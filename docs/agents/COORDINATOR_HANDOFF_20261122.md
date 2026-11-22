# 協調者交接（2026-11-22）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> 快照時間：2026-11-22（台北時間）。現行決策與狀態以釘選任務板 [#93](https://github.com/Polalalabear/amidst/issues/93) 為準，本文件只是快照；上一份交接是 `docs/agents/COORDINATOR_HANDOFF_20261118.md`。

## 1. 一句話現況

研究核心是證明「真正呼叫模型、看圖、知道空間資訊的 Agent，在複雜情況下的鏡頭切換決策勝過規則演算法（RT-DETR＋HSV＋規則閘門）」。

- 已完成的實驗（D325 更正、看圖先導、W1、W2）都只在簡單場景 A4-1、B4-1：離線有增益，即時增益 0（延遲約 4.3 s），**H1 還沒有數據**。
- 2026-11-22 定了三天計畫（到 11-25），依序做 F1 評分器→F2 空間圖→F3 H6→F4 E3 實驗→F5 論文。Claude 一次只開一個大 feature；Codex 同時做困難劇本 #652。

## 2. 目前狀態

| 項目 | 狀態 |
| --- | --- |
| main 最新 | `802bc24fbb24d8c779c3e4a00ebb452855ba63a6`（#653 merge） |
| 近期 merge | #648 W2 `8290f190`；#653 D342 文件同步 `802bc24f`；#655 G7 ApiGuard `4f665d55`；#617 LIVE 錄製重播 `1742ed06`；#608 relock R1 `cfbfe4e9` |
| 8785 demo | pin `b98fac2a`（`local/demo-pin.json`，2026-11-18 核准）。網址 http://127.0.0.1:8785/workbench-v2/ 。在 `~/amidst` 執行 `./start_445_demo.command --port 8785` 啟動。**磁碟低於 8 GiB 時，程式內建的保護會擋下啟動**（`DISK_BELOW_8_GIB`）。2026-11-22 已重新啟動。 |
| 8791 LIVE | `local/runtime/live-main` @ `4f665d55`，PID 75703，網址 http://127.0.0.1:8791/ ，啟動腳本 `local/runtime/start_live_8791.sh`，沒有 pin。 |
| 磁碟 | 約 10 GiB 可用（`df -k` 計算）。第三個寫入 session 開工前需要 ≥ 9 GiB，剩 5 GiB 就停。 |
| 花費 | OpenAI 累計約 USD 22.4（ApiGuard 帳本，非 DENIED）。上限 USD 100，累計到 USD 90 之前不用問（D344）。 |

## 3. 所有工作（依類型）

### 3.1 即時模式（LIVE，8791）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| #608 relock R1 | 失聯後重新找回目標的狀態機 | 已合併 `cfbfe4e9`。門檻 `t_short_s`、`tau_app`、`margin_app` 仍是 UNKNOWN，預設關閉，只列候選給人確認 | 自動選人要等 E3 量測門檻；#588 保持開啟 |
| #617 LIVE 錄製重播 | `live-ab.case.v1` 確定性案例 | 已合併 `1742ed06`。輸入側重播確定，偵測器和 Agent 的輸出不保證；schema 狀態是 PROPOSED | E3 開跑前要改成正式狀態並釘 SHA（由 #652 處理） |
| #633 LIVE 改成 workbench-v2 風格，第二段 | operator.mjs、server.py 部分的樣式統一 | 第一段已合併（#634）；#617 已合併，第二段可以開工 | 不在三天計畫內，排在 F5 之後 |
| LIVE 看不到鏡頭 | 使用者回報：人物移動時，場景裡看不到現有攝像頭 | 已併入 F2 #656 | 等 F1 完成 |
| #589 CX-L6b R2 後台接線 | 重新取得目標的後台接線＋排程驗收 | blocked | 等 relock 門檻量測（E3） |
| #574 CX-L5g A/B 整合驗收 | A/B 雙畫面整合與 handoff 文件 | blocked | 等 #589 |

### 3.2 WP5 與 Agent 決策

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [F1 #660](https://github.com/Polalalabear/amidst/issues/660) 統一 GT 評分器、重算凍結結果、E3 預先登記 | 單一評分模組（中心點準則和 IoU ≥ 0.3 都輸出；錯人、定位不準、失聯、錯鏡頭分開計；分母一律用 GT 可見時間）；D325、先導、W1、W2 的新舊數字對照；`docs/evaluation/E3_PREREGISTRATION_20261122.md` | **執行中**，session `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`（Opus high），分支 `claude/feat-e3-scorer` | 等它開 PR 並回報 |
| [F2 #656](https://github.com/Polalalabear/amidst/issues/656) E3 空間圖 | 用牆面裁切鏡頭覆蓋範圍（場景幾何＋鏡頭位置／FOV），寫進 `scene_context`；LIVE 畫面和小地圖顯示鏡頭、FOV、盲區 | blocked | 等 F1 合併（一次一個 feature） |
| [F3 #657](https://github.com/Polalalabear/amidst/issues/657) H6 統一決策路徑 | 8785 和 LIVE 的 Agent 模式真正接管；拿掉 C1–C5、C7、X1 的提前阻擋；用決策紀錄證明 Agent 的答案被採用。**#645 第二步和 #646 W3 都併入這裡** | blocked | 等 F2 |
| [F4 #658](https://github.com/Polalalabear/amidst/issues/658) E3 實驗 | B1、B2、A1、A2、A3 × 困難劇本 × K=3；A3 先在重播上依實測延遲模擬即時，再跑一小段真的 LIVE | blocked | 等 F1–F3 和 Codex #652 |
| #623 預錄 est_xy＋B4-1 8CAM | 系統估計位置顯示 | **暫緩**。Opus 三點裁決已通過，但 8CAM 的 est_xy 永遠是 UNKNOWN，workbench-v2 也沒畫出來，只在 API 回傳裡 | 三天內不處理；之後由 Codex 補齊再合併 |

### 3.3 研究紀錄與報告

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 論文版報告（Claude Docs） | https://claude.ai/artifact/B7oycBdnYfkeK1U1JiPWSL ，rev 52 | 已完成 H1–H6、更正章節、W1/W2 的段落（W2 措辭採用 #648 Opus 裁決） | E3 結果出來後由 F5 更新 |
| 交付資料夾 | `local/evidence/final-package-20261120/`（LOCAL，不打包 zip，使用者直接看資料夾）：diagrams、specs、data、figures、screenshots、report | 已完成。論文 PDF `report/amidst_paper_20261120.pdf` 27 頁，SHA-256 `12e048b1f48d25c6d25f25b1e64e3b9a1c729cd054f26754c78fa1ed5d99f3fb`；`MANIFEST.sha256` SHA-256 `9f1edca8db45c4b75335934f755180354b675368e923197b70803077f15515a4` | F5 定稿時更新 |
| 舊 zip | `local/evidence/amidst_final_package_20261120.zip`，SHA-256 `00bbd700212a6b006d4bbaecc94ad1cc27d0acb6b85a70c99d2e3c707d81c0d8` | 使用者改成看資料夾後就不再使用；保留，未刪 | 要刪需使用者同意 |
| [F5 #659](https://github.com/Polalalabear/amidst/issues/659) 論文與交付資料夾定稿 | 加入 E3 結果的論文、資料夾、圖表 | blocked | 等 F4 |

### 3.4 8785 demo

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 8785 Agent 模式真正接管 | 見 F3 | — | F3 |
| 8785 pin 更新 | 新 pin，包含 F3 | 現在是 `b98fac2a` | F3 合併後跑 gate，再由使用者核准 |

### 3.5 流程與整理

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 更新測試文件 | 測試文件和現況一致 | 未開始 | **使用者確認所有更新無誤之後，第一件事就是這個**（使用者 2026-11-20 指示） |
| D319 第二輪檢索 | `docs/index/` 更新 | 未開始 | 排在三天計畫之後 |
| PROGRESS | `docs/operations/Q1Q5_PROGRESS.md` | 已更新到 #655（D342） | #656–#660 由協調者在下一批補上 |

### 3.6 Codex 與 Argon 的任務

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [#652](https://github.com/Polalalabear/amidst/issues/652) CX-E3 困難劇本 | 4 類：A 相似衣著交錯、B 3–10 秒長盲區、C 多出口（含目標落在前 3 候選之外）、D 遮擋和真正離開。至少 8 段、約 40 個複雜決策點，錄成正式的 `live-ab.case.v1` 並釘 SHA | ready，派給 Codex；期限 2026-11-23 結束前 | 等 Codex 交件。Blender 渲染免問，但要回填 issue 和 PR |
| #623 | 見 3.2 | 暫緩 | — |
| W4（複雜場景渲染） | — | 還沒開 issue，內容已由 #652 涵蓋 | 若 #652 需要 Blender 新場景，由 Codex 在 #652 內處理 |
| Argon | — | 目前沒有派工 | — |

## 4. 決策 D336–D344 摘要（下一個是 **D345**）

- **D336**：新協調者接手的第一批派工（#624、#628 等）。
- **D337**：LIVE 全面改成 workbench-v2 風格，分兩段做（#633）。
- **D338**：依 D319 第一輪檢索更新規格、文件與索引（#631／#632，已合併 `7ef1426b`）。
- **D339**：OpenAI 預算 USD 50 內不用問（已由 D344 取代）；#637 結論只限於覆核架構。
- **D340**：放寬 Agent 模式（取代 D64、D128）。Agent 可以看畫面、選任何偵測框（含低分和非人物類別），也可以回答「被遮住」「看不到」「下一台鏡頭」。場景資訊（鏡頭關係、可行走連通、FOV、覆蓋範圍）是必要輸入，只能來自設定檔和標定資料。規則閘門在 Agent 模式下只當資訊。GT 隔離、ApiGuard、身分 UNCONFIRMED、付費核准仍然是硬限制。補充：請求分三層，場景資訊做成固定前綴並使用提示快取。H6：Agent 和規則在所有模式都要能切換。
- **D341**：依 D340 和 H1–H6 重整工作清單（W1 #644、W2 #645、W3 #646）。
- **D342**：#648 合併後的全面文件同步（#653，`802bc24f`）。
- **D343**：#655、#617、#608 合併；#623 三點裁決（est_xy 只用於顯示，稱「速度上限可達半徑」；estimate 是附加欄位，不在 contract B 範圍內；接受 scripts→live_mode.Projector 的依賴）；E3 的三個事實（LIVE 有 8 台鏡頭含 CAM_ENTRY；相似衣色多人片段 5 段；輸入側重播確定）。
- **D344**：預算 USD 100，到 90 前不用問；Blender 渲染免問，但要回填 issue 和 PR；Claude 一次只開一個大 feature；三天計畫；#623 暫緩。

## 5. 假設 H1–H6 的證據現況

| 假設 | 現況 |
| --- | --- |
| H1 複雜情況下切換決策勝過規則 | **尚無數據**（A4-1、B4-1 太簡單，規則本來就不會錯人）。由 E3（F4）驗證 |
| H2 增益來自看圖 | 有條件成立：不給圖時，跟對率掉到 0.55–0.65 |
| H3 閘門當資訊而不是硬擋 | D340 已落實在 W2 程式；系統路徑由 F3 處理 |
| H4 主動找鏡頭時用空間資訊 | 只有描述性訊號：B4-1 前 3 名 37/40 對 9/40，但前 1、前 2 名都只有 8/40，低於隨機；差異全部在第 3 順位。**不支持 H4**。F2 修正覆蓋範圍後再驗 |
| H5 辨識勝過 RT-DETR＋HSV | 有條件成立：在 RT-DETR 漏掉、誤分類、目標遠或被擋的情況下成立。整體 F1 0.955（mean）對 0.957（多數決） |
| H6 所有模式都能切換 | 前提條件，由 F3 處理 |

另外：在中心點準則下，W2「沒有變差」成立；改用 IoU ≥ 0.3，B4-1 跟對率是 0.761、錯人 6.3 s。即時模式下所有看圖組都和規則一樣，增益 0（p50 延遲 4.3 s）。

## 6. 三天計畫（到 2026-11-25）與暫緩清單

- **Day 1**：F1 評分器、重算凍結結果、預先登記；Codex #652 困難劇本。
- **Day 2**：F2 空間圖 → F3 H6（一次一個）；F4 跑 B1、B2、A1、A2，A3 先模擬即時。
- **Day 3**：補跑、錯誤案例分析、F5 論文與資料夾、8785 pin（使用者核准）。
- 時間不夠時，先犧牲 A3 的真即時部分；不降低成立門檻，樣本不足就標為探索性結果。
- **暫緩**：更換 RT-DETR、ByteTrack／OSNet、大量比較不同 LLM、完整 3D 追蹤、完整外觀記憶、TLA+、真實世界資料集、UI 美化、#623 畫面補齊、#633 第二段。

## 7. 流程規則重點

- Claude 一次只開一個大 feature（一個寫入 session），做完才開下一個（D344）。寫檔一律在 scratchpad 的精簡 clone 裡做，用完刪除；`~/amidst` 不能改、不能切分支、不能 commit、不能 fetch。
- 審查：每個程式 PR 由 Sonnet medium 做正式審查；complex code 或有決策點的交給 Opus，只看被標出的點。
- 審過且 CI 綠就直接用 merge commit 合併並刪分支（D305）。UI 和 pin 先給使用者看截圖。
- 合併如果被權限分類器擋下，就給使用者一條 `gh pr merge <n> --merge --delete-branch --repo Polalalabear/amidst` 指令自己跑（每條指令只給一次）。
- Blender 渲染免問，但要把渲染內容、張數或時長、產物路徑和 SHA-256 回填到 issue 和 PR（D344）。
- 付費呼叫一律先經 ApiGuard dry-run 並記帳；累計到 USD 90 前不用問。
- 被 session 事件喚醒的回合不能開新 session，只能用提案卡，或用 SendMessage 交給已經有脈絡的 session。
- 決策同步到 #93（D 編號接續）；每項工作都要有 issue 和 PR；瀏覽器測試一律無頭。
- 使用者確認更新無誤後，**第一件事是更新測試文件**。

## 8. 新協調者要讀的文件

1. 本文件，以及 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文和 D336–D344 的留言。
2. `docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md`（H1–H6、§4 的衝突清單 C1–C8、X1）。
3. `docs/evaluation/W2_ACTIVE_AGENT_20261120.md`，以及 [#648 Opus 裁決](https://github.com/Polalalabear/amidst/pull/648#issuecomment-7029512103)（論文可引用的措辭）。
4. `docs/specs/DEVELOPMENT_RULES.md`、`docs/specs/Q1Q5_PRODUCT_SPEC.md`（D340、H6、資料流）。
5. F1 完成後：`docs/evaluation/E3_PREREGISTRATION_20261122.md`。
6. `docs/operations/Q1Q5_PROGRESS.md`。

## 9. 第一件事

1. 讀 F1（[#660](https://github.com/Polalalabear/amidst/issues/660)，session `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`）的回報。
2. 審 F1 的 PR：Sonnet 做正式審查；評分器屬於 complex code，交給 Opus 看預先登記的成立門檻。通過且 CI 綠就合併。
3. 開 F2 #656（一次一個 feature）。同時追 Codex #652 的交件。
