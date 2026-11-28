# 協調者交接 2026-11-28b

> 寫入者：協調對話 `local_a56c5d92`（Claude Opus 5.5），接手 `COORDINATOR_HANDOFF_20261128.md`。main @`f18304d7`。**新的協調對話全程用繁體中文回覆**（D255）。
> 下一個決策號：**D421**。決策記在 #93，更新紀錄 append 到 #674。
> 交接原因：context 84%（規則 D420：80% 交接）。每週額度 92%，2026-11-29 20:00 +08 重置；五小時額度 13%。

## 0. 先讀
1. 本文件。
2. #93 的 D418–D420。
3. #780 的審查與更正留言（7225284455 作廢的 R-N 版、7225302386 以 B1 為準）、PR #785 的 Sonnet 審查（7231670655）與 Opus 裁定（7231700799）。
4. #781 的設計審查（7231948793）。
5. 擱置清單：`side-session-notes/local_41de51ce-…/PARKED_FOR_USER.md`（共享筆記，非 repo）。

## 1. 本輪決策與合併
- **D418** 開放認領只開 demo 前台（#771、#772）。**D419** AC7 接受 B-05 雜湊差異（#773 關閉，AC7 條文已入 #783）。**D420** AGENTS.md「開工前先分析、以程式碼為準、改程式同步文件」，CLAUDE.md「context 80% 交接、五小時額度 95% 排程叫醒、待使用者看的先擱著去認領工作」（#784 `9f03cfc4`）。
- 合併：#777 `0374f762`、#769 `e17a0787`（#766–#768 關）、#783 `dea59531`、#784 `9f03cfc4`、#787 `9745382b`（#771 目標框＋#772 審核側欄＋唯讀端點 `q_track_boxes`，追蹤回應雜湊不變）、#786 `f18304d7`（Codex #770 時鐘解析）。
- E8 設計：第一部分**用 B1 凍結狀態**（不是 R-N），#765 維持 deferred；「優於規則」需 S2 顯著偏向 Agent；§6.3 L0 時間重估與 4 h 規則。

## 2. 所有工作（依類型）

### 2.1 研究：E8（最優先）
| 項目 | 預計產出 | 進度 | 卡點 |
|---|---|---|---|
| PR #785 E8（`claude/feat-e8`） | 合併進 main | Sonnet NEEDS_CHANGES（只有 Mac 評分端），Opus 已裁定 O1–O3；e8-main（`local_13219d3d`）在修 M1／O2／O3／N1／N2＋**OWN_BOX 鍵含模型**（Codex 在 #781 發現） | 修完由 785-e8-review（`local_8140d5c9`）確認 → CI 綠 → 問使用者合併 |
| **Colab OOM（緊急）** | 能在 L4（22 GB）跑完 | 使用者用 L4 跑，cell 6 載 qwen7b 時 OOM：`free(fn)` 沒清全域 `raw/fn/ask` 與模型 cache，3B 沒釋放。已告訴使用者第一輪設 `RUN_MODELS=["laya_text","laya_typed","qwen3b"]` 重啟後 Run All | e8-main 修釋放（盡量只改 notebook、保住 pin `62981f08`）、評估 7B 在 22 GB L4 級能否放下、確認兩輪同 OUTPUT_DIR 合併與 Mac 評分；修好後把第二輪（只跑 qwen7b）步驟給使用者。兩輪＋L4 GPU 記偏離 |
| E8 Mac 評分與報告 | E8 報告、圖、#780 結論 | 等 Colab 兩輪 zip | 使用者把 `e8-run-*.zip` 放 `~/amidst/local/evidence/e8-run-<日期>/` |
| #781 GPT 組（Codex） | 第一部分探索性補充 | 設計 APPROVE 附 5 條件（PR #788） | 等 #785 合併 |
| #782 E8 獨立複核（Codex） | #780 留言 | blocked | 等 E8 結果 |

### 2.2 8785 demo 與 LIVE
| 項目 | 進度 | 卡點 |
|---|---|---|
| 8785 換 pin（含 #787、#786） | 未做 | 使用者：等 E8 跑完；換前要重跑 gate（AC1–AC8），使用者核准 |
| #790 Codex 藍衣接回驗證（測試） | Sonnet APPROVE | 使用者要 Codex 先補 3 小問題（puppeteer-core 依賴、「red only」註解）再合併 |
| #789 adaptive 漏掃 CAM_ENTRY | 新 issue | Codex 先分析貼設計 |
| #786 後續小問題 | 契約補句、ERRORS 對照、PR 說明 | Codex 新小 PR |
| #675 Agent 選項接線 | blocked | 等 E8 結論 |
| #735、#676、#589 | 開著 | Codex |

### 2.3 報告（Neon 輔助）
- #734／#776 E6 數字回填與海報版面（Neon 進行中）；E8 段等數字；#479 LaTeX 等 E8。#727 建議關閉或改「E8 延遲」（未決）。

### 2.4 流程
- PROGRESS 補 #784–#790（下次批次）。給 Codex 的第二批派工文字已給使用者（#790 小問題、#786 小問題、#789 設計、#781 等 #785）。

## 3. 使用者要審查或按卡的事
1. Colab 第一輪（laya＋3B）進行中；第二輪等 e8-main 的步驟。
2. #785 合併（修完確認後）；#790 合併（Codex 補完後）。
3. 8785 換 pin（E8 跑完後，重跑 gate）。

## 4. 子 session
- e8-main `local_13219d3d`（E8 實作，非本對話所開，結束時不會自動通知，需用 list_events 查）。
- 785-e8-review `local_8140d5c9`、codex-786-790-review `local_ffa57474`、787-sonnet `local_d11e19fe`、d418-d419-post `local_94fae0e8`（Haiku，GitHub 雜務可續用）。
