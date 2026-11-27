# 協調者交接（2026-11-27 第三次）

快照時間 2026-11-27 約 20:40（+08:00）。main = `16a35980`（含 #761）；8785 pin = `5727fc9a`（未變）；下一個決策號 **D412**（D410、D411 已由文件與整理線使用；改 #93 前先查最新留言）。之後的狀態以 [#93](https://github.com/Polalalabear/amidst/issues/93)、[#674](https://github.com/Polalalabear/amidst/issues/674) 為準。新的協調對話**全程用繁體中文**（D255）。前一份：[2026-11-27 第二次交接](COORDINATOR_HANDOFF_20261127b.md)。

## 0. 先讀

1. 本文件。
2. #674 最新一則「E6 正式一次跑完 COMPLETE」。
3. #93 的 D404–D411 留言。
4. 規則：`CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`，以及 D389、D395–D397、D402–D411。

## 1. 規則（本段新增或重申）

- **架構先於程式（使用者，2026-11-27）**：寫任何東西前先確定架構與設計（資料流、介面、依賴、驗證點），最後才寫程式。子 session 的 brief 也要求先回報設計、核對後才動手。
- **D402**：E6 一次跑完，批 3 改成機械閘門；結果出來前的事後核對只看閘門紀錄、不看分數（已完成，見 §2）。
- **D404**：E6 正式上限 USD 45（明示偏離預登 §7.1）；專案累計上限 90 不變。
- **D405**：S04／S07 B1 無 ACQUIRE，所有組無種子，配對差依構造為 0；報告列為已知限制。
- **D406**：本機 DNS 失敗（errno 8、請求未送出）屬基礎設施故障，只重跑 S12 AO.k2／k3；主分析用重跑檔，**敏感度分析以原 DNS 失敗檔另算 verdict，兩者都報告**。
- **D407–D411（文件與整理線）**：重現包延後；舊交接合併進 `docs/history/`；索引拆現行／非現行；`docs/index/CLEANUP_LEDGER.md` 是整理的唯一紀錄；8 個 issue 關閉、標籤修正；#633 鏡像部分退役；#762 給 Codex（deferred）；#720 補跑 AC1–AC8。
- **派工**：只讀、幾分鐘完成的審查用 Agent 子代理（Sonnet）；寫檔或長工作開子 session；已有 context 的工作送回原 session（SendMessage）。需要使用者核准：刪除、累計超過 USD 90、UI 與決策。每個節點追加到 #674。
- **額度與交接**：五小時額度到 90% 時，用 scheduled task 在 `resetsAt` 後約 5 分鐘叫醒協調對話；context 近 80% 照 `CLAUDE.local.md` 交接。E6 已結束，不需要 keep-awake。

## 2. E6（#732）正式結果

| 項目 | 內容 |
|---|---|
| 執行 | G4 session `local_85cdc9e8-dfa6-4c1d-9053-3a9217b6c95f`，clone @ main `a25a2124`；`run_all.sh` exit 0；log LOCAL `local/evidence/e6-run-20261127-runall-4.log` |
| D402 事後核對 | 通過（前任協調對話）。VERIFY_FREEZE `feb8a19f…a1bf` 10 項 ok；BATCH3_FREEZE `2ecdeb61…95db`；舊收據 `…-superseded-71633fb8`、`…-superseded-a9418fdf` 保留 |
| 輸出 | AO 36、DEANCHOR 36、HIST_SUM 36、NO_IMAGE 36、NO_SPATIAL 36、B1 12、R-N 24 |
| 花費 | 新增 USD 32.57（K=1 3.28＋AO 6.95＋DEANCHOR/HIST_SUM 13.52＋NO_IMAGE 6.52＋NO_SPATIAL 2.30），**累計 70.74**（ApiGuard 估計）。使用者讀平台 November spend 為 40.54（E6 前）；E6 後要依 D375 對帳，請使用者再讀一次平台總額 |
| verdict | LOCAL `local/evidence/e6-formal-run-20261127/verdict/VERDICT_E6.md`。FORMAL M=12、N_dp=48 |
| P1 | DEANCHOR vs AO_ORIG：**INCONCLUSIVE**（p_h 0.750） |
| P2 | DEANCHOR_HIST_SUM vs B1：**NOT_SUPPORTED**（p_h 0.999，p_negative 0.0098） |
| full-track DP 正確率 | B1 0.708、AO_ORIG 0.375、DEANCHOR 0.354、HIST_SUM 0.375 |
| 消融（探索性，不進 Holm） | `verdict-exploratory/`：NO_IMAGE 0.438、NO_SPATIAL 0.354 |
| 報告語言 | 照預登：「無法判斷」不等於「無差異」；消融標探索性 |

**偏離列表**：DC1、DC3（TRUE_DEPARTURE n=0）、DC7、S12 tail_s 1.0、D400、D402、D404（正式上限 45）、D405（S04／S07 無種子）、D406（S12 AO.k2 DNS 失敗；原檔 LOCAL `local/evidence/e6-formal-run-20261127/ao_orig-aside-infra/E6-S12/AO.k2.infra-dns-failed-20261127.json`）、新空帳本 `e6-run-ledger-20261127`、D403 消融探索性。Stage 3（#672）因 #676 未關被擋（預期）。

## 3. 待辦（依序）

1. **D406 敏感度 verdict**（零費用）：送回 G4。把正式輸入樹複製到新資料夾，把 S12 `AO.k2.json` 換成 DNS 失敗原檔，用同一個 `e6_verdict_run.py`／`verdict_e6` 跑出 `verdict-sensitivity-d406/`，回報 P1／P2 是否改變。
2. **single-point paired 診斷 n=0**（VERDICT 內四組皆 n=0）：先查是設計上不產生還是接線遺漏（只讀，Sonnet 子代理）。結果寫進紀錄；若是 bug 另開 issue，不影響 C3 主終點。
3. **結果 PR [#754](https://github.com/Polalalabear/amidst/pull/754)**（Draft，分支 `claude/feat-exp-run`，骨架由文件線寫好，結果欄位 UNKNOWN）：回填數字、各輸出 MANIFEST SHA-256、完整收據 SHA、S1／S2 寫法（DEANCHOR_HIST 未進正式組）、敏感度與 single-point 結果。派 G4 或新 Opus 子 session 寫（先回報設計），協調對話審；Sonnet 子代理審後 CI 綠合併。
4. 回填 #741（留言）、#732、#721、#742、#93 的 FEAT-EXP-RUN 列（#93 本文同步可請文件線對話 `local_a2f7e1a2-2c2b-4991-b4ff-1ad7f2fb5bfa`）。
5. 接著：#734 報告的 E6／E7 數字（Neon 或另開 PR）；#675 Agent 預設設定——E6 最佳組不支持 Agent 優於規則，需與使用者討論預設。

## 4. E7（#727）

- 使用者正在 Colab 跑 notebook（pin `594268b96c7b49bd92c6ed62668402e11720e1f0`；qwen_vl、laya_text、laya_typed；diffusion_vlm 跳過）。
- 使用者會把輸出下載到 `~/amidst/local/evidence/e7-outputs-20261127/` 後通知；之後做 E7 分析（Cell 7 標 Needs Mac Scoring 的列在 Mac 補分），回填 #727。
- laya session `local_835b3a82-a602-4967-bbcf-6b5c113a4339`（已完成，有 E7 程式 context，可送回修 bug）。

## 5. 其他工作

- 8785 pin `5727fc9a` 未變。#720 換 pin 後 AC1–AC8 由子 session ac720-acceptance 補跑（D411）。
- #735 剩 #675（等 E6 結論討論）、#566／#574（blocked，等 R2 #589）。
- #733、#728、#740 deferred（D407）。#762 Codex B-05／r005 8CAM deferred（D411）。
- 全專案大整理（D408 第 6 點）等 E6 結果、E7、報告完成後再做；盤點在 `docs/index/CLEANUP_LEDGER.md` §3。

## 6. Session

- 前任協調對話 `local_2a4a26d2-946e-4a1f-90fd-eb1cba1c5103`：交接後可封存。
- G4 `local_85cdc9e8-dfa6-4c1d-9053-3a9217b6c95f`：做完 D406 敏感度後可封存；之後改報給新協調對話。
- 文件與整理線 `local_a2f7e1a2-2c2b-4991-b4ff-1ad7f2fb5bfa`：最上層獨立運作。
- E7 laya `local_835b3a82-a602-4967-bbcf-6b5c113a4339`：已完成，可送回。

## 7. 本段教訓

- 正式付費執行前的閘門要把上限當成可預登的參數；這次上限 32 被 dry-run 擋下，改上限屬明示偏離，要重新凍結收據並保留舊收據。
- 種子規則若讓某段完全不啟動，要在輸出裡留完整紀錄（`seed_status`），而不是讓程式拋例外。
- 用戶端網路故障與 provider 錯誤要分開記錄，事前定義哪一類可以重跑。
