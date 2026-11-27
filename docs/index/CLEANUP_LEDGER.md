# 整理總帳（盤點／刪除／搬移／更新／新增）

> **唯一紀錄**（D409，使用者 2026-11-27）：專案整理的盤點、刪除、搬移、更新、新增，全部記在這一份文件，不另開 SWEEP 或盤點檔。以後要整理，或遇到「某個檔案、分支、資產去哪了」這類相依問題，**先查本檔再動手**，不要重新翻 repo、issue 或 `local/`。
>
> - **怎麼用**：找舊路徑看 §1（對照表）；查做過什麼看 §2（執行紀錄）；查還沒做的看 §3（目前盤點）和 §4（待辦）。
> - **怎麼寫**：每次整理做完，在 §2 最上面加一列，寫日期、決策、PR／commit、做了什麼、證據。搬移或刪除了路徑，同時在 §1 補對照。盤點結果更新到 §3，做掉的待辦從 §4 移到 §2。只追加、不改寫舊列；舊列有錯，在後面補一列「更正」。
> - **規則**：刪除分支、檔案或資產都要使用者明確授權，並由使用者在自己的終端機執行（AGENTS.md）；存有證據的分支保留；有 authority pin 的檔案不搬，必要時重新登記 pin。
> - 2026-11-27 以前的檢索紀錄 [`SWEEP_D319_PASS1_20261119.md`](SWEEP_D319_PASS1_20261119.md) 保留原樣，結果摘要列在 §2。

## 1. 路徑對照（舊位置 → 現在位置）

| 舊路徑 | 現在位置 | 動作 | 依據 |
| --- | --- | --- | --- |
| `docs/agents/COORDINATOR_HANDOFF_<日期>.md`（20261025、20261026、20261115、20261116、20261117、20261118、20261122、20261123、20261123b、20261123c、20261124、20261124b、20261126、20261127，共 14 份） | [`docs/history/COORDINATOR_HANDOFFS_20261025_20261127.md`](../history/COORDINATOR_HANDOFFS_20261025_20261127.md) 的 `#h<日期>` 段落（全文） | 合併後刪除原檔 | D408，[#757](https://github.com/Polalalabear/amidst/pull/757) `ba7f74f6` |
| `docs/agents/COORDINATOR_HANDOFF_20261027.md` | 原位（authority pin A5），只把連到 10-25、10-26 的連結改指向合併文件，pin 已重新登記 | 更新 | D408，#757 |
| `docs/agents/{OFFICE_DEMO_MVP,OFFICE_DEMO_PLAN_20261101,OFFICE_DEMO_SCRIPT,OFFICE_DEMO_TASKS,K1_BLOCKERS_DECISION_20261016}.md` | `docs/archive/office/` 同名 | 搬移 | D408，#757 |
| `screenshots/d128_w_a5_*.png`（3 張） | `docs/history/screenshots/` 同名 | 搬移 | D408，#757 |
| `docs/index/CODE_DOC_MAP.md` §3（其他套件）、§4（D319 處理結果） | [`docs/index/CODE_DOC_MAP_INACTIVE.md`](CODE_DOC_MAP_INACTIVE.md) | 拆出 | D408，#757 |
| `local/` 下 D394 清單的項目（uv 快取、pytest 暫存、PR 預覽 checkout、e3 preflight v1／v2、D115 原始 run、r004 八鏡頭原始 PNG、第一版 baseline 原錄製、demo-owned 舊驗證截圖、D133 proxy、P1 clean-room、office-canonical、舊 PR／relock 證據） | **已永久刪除**，文件裡引用的 SHA 收據已經核對不到原檔 | 刪除 | D394；清單 LOCAL `local/evidence/local-necessity-20261127/`，腳本 `local/evidence/delete-20261127/delete.sh`（SHA-256 `e835eac9…6dfe`） |

D91 時期（2026-10-27）的封存是**原地加檔頭、不搬**，清單在 [`docs/archive/ARCHIVE_20261027.md`](../archive/ARCHIVE_20261027.md) §1–§6；D408 的搬移也記在同一份的 §7。

## 2. 執行紀錄（新的在上）

| 日期 | 決策 | PR／commit | 動作 | 內容與證據 |
| --- | --- | --- | --- | --- |
| 2026-11-27 | D409 | 本 PR | 新增 | 建立本總帳；§3 是全專案大整理的盤點（只讀，main `ba7f74f6`） |
| 2026-11-27 | D408（使用者指示） | — （GitHub 標籤） | 更新 | 已關閉 issue 移除狀態標籤：`in-progress` 17 個（#577–#660）、`ready` 46 個、`blocked` 25 個、`needs-auth` 1 個；複查後四種都是 0 個。#742 的 `in-progress` 在同一天先移除 |
| 2026-11-27 | D408 | [#757](https://github.com/Polalalabear/amidst/pull/757) `ba7f74f6`（issue #756） | 刪除＋搬移＋新增＋更新 | 刪 14 份舊交接（全文已併入合併文件）；搬 5 份 Office 文件、3 張截圖；新增 `COORDINATOR_HANDOFFS_20261025_20261127.md`、`CODE_DOC_MAP_INACTIVE.md`；`docs/README.md`、`CODE_DOC_MAP.md` 只留現行導覽；`ARCHIVE_20261027.md` 加 §7 對照；CLAUDE.md、20261027 交接的 pin 重新登記 |
| 2026-11-27 | D407 | [#755](https://github.com/Polalalabear/amidst/pull/755) `84dbbc44` | 更新 | 交接指向改為 20261127b（CLAUDE.md、AGENTS.md、`docs/README.md`）；`Q1Q5_PROGRESS.md` 補到 #755；CODE_DOC_MAP 加 E6／E7、報告、重現包；pin 登記 |
| 2026-11-27 | D407 | — （#93 本文） | 更新 | 工作清單同步；`real-e2e.mjs` 多畫面格數列關閉（已由 #709 `579b431a` 與 #700 gate r3–r5 涵蓋） |
| 2026-11-27 | D394 | — （本機） | 刪除 | `local/` 約 8 GB，使用者執行 `delete.sh`，清單見 §1 最後一列；之後的 #729 盤點（LOCAL `local/evidence/cl-inventory-729-20261127/`）結論是剩下的可刪項目只有約 9.6 MB |
| 2026-11-19 | D319／D338 | [#632](https://github.com/Polalalabear/amidst/pull/632) `7ef1426b` | 盤點＋更新 | 第一輪檢索 `SWEEP_D319_PASS1_20261119.md`；處理結果見 `CODE_DOC_MAP_INACTIVE.md`（原 CODE_DOC_MAP §4） |
| 2026-10-27 | D91 | #263 | 封存（原地） | 91 份歷史文件加「已封存」檔頭，清單在 `ARCHIVE_20261027.md` |

## 3. 目前盤點（D409；2026-11-27，main `ba7f74f6`）

依據 #93 D408 第 6 點：目前的大工作（E6 結果、E7、報告）**完成後**才開始大整理，GitHub 和本機要一起更新。本節只盤點、不執行；數字取自 2026-11-27 的 `gh`、`git ls-files` 和 `du`。執行時照 §3.6 的順序做，做完一項就移到 §2。

### 3.1 GitHub issue（開著的 29 個）

#### 3.1.1 工作已合併、issue 還開著（可關閉候選）

| Issue | 已完成於 | 建議 |
| --- | --- | --- |
| #717 E6-1 答案表重算 | #723 `e202110b` | 留言指向 #723 後關閉 |
| #718 E6 預登草稿 | #726 `017dd61a` | 同上；另外移除錯掛的 `ready`＋`in-progress` |
| #719 F5 論文／README 收尾 | #724 `88102b91` | 同上 |
| #720 8785 收尾 | #725 `018e1a5c`、#714 `5727fc9a`、#700 gate r5 | 同上 |
| #700 換 pin gate | gate r5 全 PASS，pin `5727fc9a`（2026-11-27） | 同上 |
| #710 前台 3D | #714 `5727fc9a` | 同上 |
| #612 est_xy | #623 `f8b1a454`；3D 顯示由 #714 完成 | 確認 #605 需求已涵蓋後關閉 |
| #594 8CAM run | #623；8CAM wall 在 gate r3–r5 都是 PASS | 確認「B-05／r005-8CAM 來源 UNKNOWN」已由 #686 收據解決後關閉 |
| #633 LIVE 改成 workbench-v2 風格 | #705 `21d6f4c5`、#739 `a3311bcb`（LIVE 樣式收尾） | 確認還有沒有剩餘項目 |
| #659 F5 論文定稿 | D386：併入 #734 | 以「superseded，併入 #734」關閉 |
| #729 `local/` 盤點工具 | #738 `a90a7884`；Mac 端由 `cl-inventory-729-20261127` 代跑 | 關閉；後續問題已拆成 #740 |
| #721 E6-2 實作 | #743 `7dbb4ede`、#746 `037477d3` | **等 E6 結果 PR 合併**，由 E6 協調對話回填後關閉 |

#### 3.1.2 等主線（E6／E7）
- #732（FEAT-EXP-RUN，執行中）、#734／#730（報告）、#727（E7，使用者在 Colab 跑）、#675（LIVE Agent 預設設定，等 E6 選組）、#735（FEAT-LIVE-FINISH，只剩 #675）。

#### 3.1.3 延後或 blocked
- D407 延後：#733、#728、#740（重現包）。
- blocked：#566、#574（等 R2 #589）、#589、#672（等 #676）。
- 開著但沒有狀態標籤：#676（LIVE bug）。

#### 3.1.4 常設
- #93（任務板）、#674（更新紀錄）、#479（報告 epic）。#479 和 #734 的範圍重疊，大整理時決定是否把 #479 併進 #734。

#### 3.1.5 開著的 issue 上不一致的標籤
- `ready` 和 `in-progress` 同時掛著：#718、#733、#734。
- `owner:codex`，但實際由 Claude 代做：#732（D396）。
- `needs-claude-review` 和 `review:claude` 重複：#594、#612。
- 舊標籤 `pull:ready`：#479。
- `blocked-user`（#675）和 `blocked` 並存，兩種寫法要統一。

### 3.2 PR
開著的只有 #754（E6 結果紀錄骨架，Draft，等 E6 協調對話回填）。不需要整理。

### 3.3 遠端分支（27 支）與 tag

| 類別 | 分支 | 建議 |
| --- | --- | --- |
| 已全部合併（main 上沒有缺的 commit，PR 皆 MERGED） | `claude/docs-handoff-20261123`、`claude/feat-ci-live`、`claude/feat-demo-fixes`、`claude/feat-e3`、`claude/feat-e3-run`、`claude/feat-e5`、`claude/feat-f5-paper`、`codex/feat-apiguard-cache`、`codex/feat-e3-figures`、`codex/feat-f4-recompute`、`codex/feat-h6-8cam`、`codex/feat-live-agent`、`codex/feat-live-fixes`、`codex/feat-live-style`、`codex/feat-support-data`、`codex/feat-workbench-8cam`、`codex/fix-live-state-fixture`（17 支） | 刪除候選（D249：已合併的直接刪，不另打 tag）。由使用者執行刪除 |
| 比 main 多 1 個 commit | `claude/docs-handoff-20261124`：`c37a0cc4`，在 #712 合併 44 秒後才推上去，只改了 `COORDINATOR_HANDOFF_20261124.md`。這份交接已在 #757 併入 `docs/history/COORDINATOR_HANDOFFS_20261025_20261127.md`，**這個 commit 的內容不在 main 上** | 先決定要不要把 `c37a0cc4` 的差異補進合併文件的 20261124 段落，之後再刪分支 |
| 存有證據，保留 | `claude/feat-e4`（3 個 commit：E4 預登、實作、停止紀錄；D388 決定保留）、`archive/amidst-claude-wip-20261109`、`archive/finalization-uncommitted-20261109`、`archive/canonical-uncommitted-20261109`、`archive/local/codex/controlled-scene-real-v2-2a`、`archive/local/phase1/physical-policy-approval` | 保留；或改打 `archive/*` tag 後刪分支（要使用者決定） |
| 進行中 | `claude/feat-exp-run`（#754） | 等 E6 結果 PR |
| 固定 | `main`、`mainline/q1q5`（凍結在 `8c741451`） | 保留 |

tag 共 47 個（`archive/*`），保留。

### 3.4 本機 `local/`（12 GB；磁碟剩 16 GiB）

| 資料夾 | 大小 | 說明 |
| --- | ---: | --- |
| `local/data` | 6.0 GB | 最大的幾項：`demo-owned-v1` 2.6 GB（8785 demo）、`r004-4actor-natural-walk-eightcam-20261114` 1.8 GB（8CAM）、`r004-cx7r-20261104-01a19f8b` 1.0 GB、`q1q5-dynamic-baseline-v1_20261025` 442 MB、`live-assets-20261115` 71 MB（8791／8785 的 3D 資產） |
| `local/evidence` | 5.1 GB（187 項） | 最大的幾項：`neon-datapack-20261126` 1.6 GB（E7／報告的資料來源）、`e3-reappearances-20261122` 947 MB、`e3-652-20261122` 651 MB、`e6-formal-det-20261127` 504 MB、`coordinator-20261109` 126 MB、`e6-formal-20261127` 118 MB、`e7-colab-pack-20261127` 115 MB、`gate-pin-*` 4 份共約 209 MB |
| `local/runtime` | 238 MB | `live-main` 是 8791 的執行目錄，不能動 |
| `local/manifests`、`archive`、`logs` | 57 MB、69 MB、0.1 MB | 有引用（見 #729 盤點） |

- 既有盤點：LOCAL `local/evidence/cl-inventory-729-20261127/`（`inventory.json`、`DELETE_LIST.md`、`deletable_candidates_xref.json`）。那次的結論是 77 個可刪候選裡有 59 個其實有被引用，最確定可刪的只有 9 項、約 9.6 MB；D394 已經清過一次。
- 大整理時建議：
  1. E6 結果 PR 合併後，先用 `scripts/inventory_local_assets.py` 重新盤點一次，再做 GitHub 引用反查，流程照 cl-inventory-729。
  2. E6 的所有輸出（`e6-*`）、E7 的上傳包、`neon-datapack`、gate r5 都要保留。舊的 gate 資料夾（`gate-pin-20261123`、`gate-pin-20261124-r3`、`gate-pin-20261127`）是壓縮封存的候選，前提是確認文件引用的 SHA 都還能查到。
  3. 刪除流程照 CLAUDE.md：Haiku 盤點 → Sonnet 逐項技術核對 → Opus 讀原始證據後決定 → 使用者執行刪除。

### 3.5 repo 內的文件與資料夾

- `git ls-files`：tests 681、docs 654、data 505、src 424、scripts 342、frontend 304、configs 138、human_review 95、report 16、notebooks 3。
- `docs/**/*.md` 依引用分類：「現行」表示被 history／archive／SWEEP／PROGRESS／provenance 以外的檔案引用；「封存檔頭」表示前 600 字內有已封存、已被取代或放棄的字樣。

| 資料夾 | 現行 | 無現行引用 | 已有封存檔頭 |
| --- | ---: | ---: | ---: |
| `docs/engineering` | 31 | **37** | 50 |
| `docs/operations` | 58 | 7 | 23 |
| `docs/evaluation` | 48 | 3 | 2 |
| `docs/specs` | 5 | 0 | 10 |
| `docs/research` | 1 | 0 | 12 |
| `docs/contracts` | 12 | 0 | 4 |
| `docs/history` | 11 | 6 | 0 |
| 其他（agents 7、design 4、index 5、paper 1、report 1、archive 6、根目錄 5） | — | — | — |

- **無現行引用的 47 份**（不含 history）是封存搬移的主要候選：
  - `docs/engineering`：`ARCHITECTURE_GUARD_20261102`、`CQ27T_HANDOFF_PACK_CHECKER_20261029`、`CQ27_YYIN_MAIN_PACK_20261029`、`CQ28_YYIN_REVIEW_PACK_20261030`、`CQ37_LONG_TIMELINE_20261030`、`CQ42T_DEMO_CHECKERS_20261031`、`CX7T_EVENT_BUNDLE_CHECKER_20261029`、`CX8T_BASELINE_FREEZE_CHECKER_20261029`、`D127_412_ARGON_411_REVIEW_20261104`、`D127_413_SPEED_INCREMENT_REVIEW_20261104`、`D127_418_STATIC_PREVIEW_V2_20261105`、`D127_418_STATIC_SCENE_20261105`、`D127_420_ARGON_411_SPLIT_MAPPING_20261104`、`D129_457_R005_GRAPH_LOADER`、`D129_464_R005_DETECTION_PROBE`、`D78_ENGINEERING_RECEIPT`、`FEAT1_BASELINE_INTEGRATION_20261102`、`LIVE_FAR_TARGET_619_20261119`、`P1_REPORTED_GAP_DIAGNOSIS_20261027`、`Q1Q5_AB_GAP_REVIEW`、`Q1Q5_BASELINE_ACCEPTANCE`、`Q1Q5_BASELINE_INTEGRATION`、`Q1Q5_EVENT_MODES_EXPERIMENT`、`Q1Q5_LINKED_ACCEPTANCE`、`Q1Q5_MERGED_REVIEW_NOTES_20261027`、`Q1Q5_PLAYBACK_CONTINUITY`、`Q1Q5_RESPONSE_V2_CONSUMER_COMPATIBILITY`、`Q1Q5_REVIEW_403_DIAGNOSIS_20261103`、`Q1Q5_REVIEW_CLOSEOUT`、`Q1Q5_REVIEW_FIXES_20261026`、`Q1Q5_SCOPE_PINS_RC4_20261027`、`R004_A4B4_SCRIPT_FREEZE_20261029`、`R004_A4_1_SCRIPT_DRAFT_20261027`、`R004_B4_1_SCRIPT_DRAFT_20261027`、`R004_BUILD_RECEIPT`、`R004_GRAPH_CHECK`、`R004_RUN_CLOCK_DECLARATIONS_20261026`。
  - `docs/operations`：`CODEX_W_SUPPORT_20261124`、`ISSUES_AND_FIXES_20261115`、`LOCAL_FOLDER_FINALIZE_20261115`、`LOCAL_LAYOUT_D171`、`Q1Q5_QUERY_ALIAS_458_HANDOFF`、`Q1Q5_RC3_RERECORD`、`YYIN_S2_V0_PILOT_20261102`。
  - `docs/evaluation`：`LIVE_OUTDOOR_COVERAGE_GAP_630_20261120`、`Q4_PRESENCE_EVAL_V1`、`live_mode_adjudication_20261116/COLAB_REPORT`。
  - 限制：只用檔名比對，沒有逐份讀內容。同名 JSON 收據、authority pin 和 CI 檢查的引用，都要在搬之前逐份核對（照 D408 的做法：`git grep -F`、pin、連結檢查）。
- 已有封存檔頭的 101 份（engineering 50、operations 23、specs 10、research 12、contracts 4、evaluation 2）：D91 規定原地加檔頭。大整理時可以照 D408 的做法搬到 `docs/archive/<領域>/`，附舊路徑對照表；有 authority pin 的不搬。
- `data/`（505 檔、95 MB：finalization 196、engineering 167、scene_audit 66、reports 32、mock 30）和 `human_review/`（95 檔、3.6 MB）：都是 Phase 1／2 時期的東西，但 `src/` 和 `tests/` 還有引用（例如 `src/amidst/reviewed_input_hydration.py`），要先做程式層級的引用審查，屬於程式整併，不是單純搬文件。
- `docs/` 根目錄的 3 個符號連結和 `PHASE1_*` 兩個檔案都有程式或資料引用，不動。
- 大整理收尾時要一起更新：`docs/operations/Q1Q5_PROGRESS.md` 補列、`docs/index/CODE_DOC_MAP.md` 與 `CODE_DOC_MAP_INACTIVE.md`、`docs/README.md`、`docs/archive/ARCHIVE_20261027.md` 的對照表。

### 3.6 建議執行順序（大工作完成後）

1. **觸發條件**：E6 結果 PR（#754）合併、#732 回填完成、E7 分析完成、#734 報告數字補上。
2. **GitHub**（Haiku 執行、協調者核對）：關閉 §3.1.1 的 issue，每個都留言寫明在哪裡完成；修正 §3.1.5 的標籤；#93 工作清單改為只列現行工作。
3. **分支**：協調者寫好一條刪除指令（17 支已合併分支），使用者執行；`claude/docs-handoff-20261124` 先處理 `c37a0cc4`；archive 類的分支由使用者決定保留或改成 tag。
4. **`local/`**：照 §3.4 的流程重新盤點、核對、決定，由使用者刪除。
5. **文件**：照 §3.5，以 D408 的做法分批搬移，每批一個 PR，附對照表、pin 重新登記、連結檢查。
6. **收尾**：更新 PROGRESS、CODE_DOC_MAP、README 和交接文件，並在 #93 記決策、在 #674 追加一則。

## 4. 待辦（不屬於 §3 大整理、已經知道要做的）

- D394 後續：引用已刪 `local/` 項目的文件，要標「已刪除（D394）」（D394 第 5 點）。還沒做，併進 §3.6 第 5 步一次處理。
- `claude/docs-handoff-20261124` 的 `c37a0cc4`：決定是否補進合併文件（§3.3）。
