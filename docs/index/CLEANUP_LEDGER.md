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
| `local/` 下 D394 清單的項目（uv 快取、pytest 暫存、PR 預覽 checkout、e3 preflight v1／v2、D115 原始 run、r004 八鏡頭原始 PNG、第一版 baseline 原錄製、demo-owned 舊驗證截圖、D133 proxy、P1 clean-room、office-canonical、舊 PR／relock 證據） | **已永久刪除**，文件裡引用的 SHA 收據已經核對不到原檔 | 刪除 | D394；清單 LOCAL `local/evidence/local-necessity-20261127/`（`SHA256SUMS` 的 SHA-256 `fcf339190c5de70eabd97624e482cf41df22f039f7357f54c0c700c1b4b18fd2`），腳本 `local/evidence/delete-20261127/delete.sh`（SHA-256 `e835eac9…6dfe`） |

D91 時期（2026-10-27）的封存是**原地加檔頭、不搬**，清單在 [`docs/archive/ARCHIVE_20261027.md`](../archive/ARCHIVE_20261027.md) §1–§6；D408 的搬移也記在同一份的 §7。

## 2. 執行紀錄（新的在上）

| 日期 | 決策 | PR／commit | 動作 | 內容與證據 |
| --- | --- | --- | --- | --- |
| 2026-11-28 | D409、D420 | [#799](https://github.com/Polalalabear/amidst/issues/799) 的 Draft PR | 唯讀盤點 | §3.7 記錄文件、程式碼、本機資產與針對性測試。264 項資產，18 個初步候選尚待用途核對，5,650,440,038 邏輯 bytes 同內容副本。 |
| 2026-11-27 | D411 | [#764](https://github.com/Polalalabear/amidst/pull/764) `c96196cb`；本總帳 PR `claude/docs-ledger-progress-d411` | 新增＋更新 | #720 換 pin 後 AC1–AC8（子 session ac720-acceptance，Sonnet，零付費、無頭）：AC8 通過、AC6 未通過、AC5 RULE_ONLY 通過（Agent 未驗證）、其餘部分通過；紀錄 `docs/operations/AC1_AC8_PIN_5727FC9A_20261127.md`，LOCAL `local/evidence/ac-720-20261127/`（`SHA256SUMS` SHA-256 `5e53b7d9171764f7c59a75af5a3e1b0a770bf84fc5e67bbb01f7102c3e5ebb04`）。#720 關閉；後續 issue #770（AC2 絕對時鐘解析）、#771（AC3／AC4 目標框）、#772（AC6 審核面板）、#773（AC7 B-05 hash）。#93 本文：8785 收尾、LIVE 第二段、est_xy＋8CAM 三列改寫，新增 #762、#770–#773 五列 |
| 2026-11-27 | D411 | [#761](https://github.com/Polalalabear/amidst/pull/761) `16a35980` | 更新 | #633 tokens 鏡像部分退役：`ab_flow.test.mjs`、`ab_menu.test.mjs`、`n6_ceiling_compare.mjs` 改讀正本 `frontend/workbench-v2/tokens.css`；鏡像 `frontend/live-mode/src/tokens.css` **保留**，因為 E3 凍結錄製器 `scripts/evaluation/e3_cases/record.mjs` 從 `frontend/live-mode/src/` 讀它，而 `record.mjs` 的 SHA 釘在 `configs/evaluation/e3_reappearances_v1.json`；`tokens-css-mirror.test.mjs` 改寫理由並加來源檢查。要刪鏡像，得等 E3 凍結解除或重新登記。#633 關閉 |
| 2026-11-27 | D411 | — （GitHub issue） | 更新＋新增 | #594 關閉（D302 只要求加一個 8CAM run，A4-1-8CAM、B4-1-8CAM 已由 #623 交付）；B-05、r005 8CAM 沒有素材，另開 #762（`owner:codex`、`deferred`） |
| 2026-11-27 | D413、D414（E6 協調對話請託） | — （#93 本文） | 更新 | #754 合併（`54df53d8`）後同步 #93 本文：更新行、FEAT-EXP-RUN、FEAT-REPORT、FEAT-LIVE-FINISH（#675：D414 預設規則，Agent 選項等 #727）、E6-2（#721 已關閉）；其他內容沒動 |
| 2026-11-27 | D410（使用者指示） | — （GitHub issue 與標籤）；本總帳更新在 PR `claude/docs-cleanup-ledger-d410` | 更新 | 大整理第 2 步提前：關閉 #717（#723）、#718（#726）、#719（#724）、#710（#714）、#700（gate r5，pin `5727fc9a`）、#612（#623＋#714）、#729（#738）、#659（not planned，併入 #734），每個都留言寫明完成處並清掉狀態標籤。#720、#594、#633 核對後還有未完成項目，留言說明後保持開啟（§3.1.1）。標籤：#733 `ready`＋`in-progress` → `deferred`；#728 `ready` → `deferred`；#740 加 `deferred`（三者依 D407 延後）；#734 移除 `ready`；#732 `owner:codex` → `owner:claude`（D396）；#594 移除 `needs-claude-review`；#479 移除 `pull:ready`；#675 `blocked-user` → `blocked`（卡在 E6 選組，不是等使用者）。開著的 issue 29 → 21 |
| 2026-11-27 | D410 | — | 更正 | 下一列（D409）的「本 PR」是 [#758](https://github.com/Polalalabear/amidst/pull/758)，merge `285ab8cb` |
| 2026-11-27 | D409 | 本 PR | 新增 | 建立本總帳；§3 是全專案大整理的盤點（只讀，main `ba7f74f6`） |
| 2026-11-27 | D408（使用者指示） | — （GitHub 標籤） | 更新 | 已關閉 issue 移除狀態標籤：`in-progress` 17 個（#577–#660）、`ready` 46 個、`blocked` 25 個、`needs-auth` 1 個；複查後四種都是 0 個。#742 的 `in-progress` 在同一天先移除 |
| 2026-11-27 | D408 | [#757](https://github.com/Polalalabear/amidst/pull/757) `ba7f74f6`（issue #756） | 刪除＋搬移＋新增＋更新 | 刪 14 份舊交接（全文已併入合併文件）；搬 5 份 Office 文件、3 張截圖；新增 `COORDINATOR_HANDOFFS_20261025_20261127.md`、`CODE_DOC_MAP_INACTIVE.md`；`docs/README.md`、`CODE_DOC_MAP.md` 只留現行導覽；`ARCHIVE_20261027.md` 加 §7 對照；CLAUDE.md、20261027 交接的 pin 重新登記 |
| 2026-11-27 | D407 | [#755](https://github.com/Polalalabear/amidst/pull/755) `84dbbc44` | 更新 | 交接指向改為 20261127b（CLAUDE.md、AGENTS.md、`docs/README.md`）；`Q1Q5_PROGRESS.md` 補到 #755；CODE_DOC_MAP 加 E6／E7、報告、重現包；pin 登記 |
| 2026-11-27 | D407 | — （#93 本文） | 更新 | 工作清單同步；`real-e2e.mjs` 多畫面格數列關閉（已由 #709 `579b431a` 與 #700 gate r3–r5 涵蓋） |
| 2026-11-27 | D394 | — （本機） | 刪除 | `local/` 約 8 GB，使用者執行 `delete.sh`，清單見 §1 最後一列；之後的 #729 盤點（LOCAL `local/evidence/cl-inventory-729-20261127/`，`MANIFEST.sha256` 的 SHA-256 `f20319cc7f34b273b4beffd40bd3d8c5381b1dfd8995f8b8b385bdce81fa0a54`）結論是剩下的可刪項目只有約 9.6 MB |
| 2026-11-19 | D319／D338 | [#632](https://github.com/Polalalabear/amidst/pull/632) `7ef1426b` | 盤點＋更新 | 第一輪檢索 `SWEEP_D319_PASS1_20261119.md`；處理結果見 `CODE_DOC_MAP_INACTIVE.md`（原 CODE_DOC_MAP §4） |
| 2026-10-27 | D91 | #263 | 封存（原地） | 91 份歷史文件加「已封存」檔頭，清單在 `ARCHIVE_20261027.md` |

## 3. 目前盤點（D409；2026-11-27，main `ba7f74f6`）

依據 #93 D408 第 6 點：目前的大工作（E6 結果、E7、報告）**完成後**才開始大整理，GitHub 和本機要一起更新。本節只盤點、不執行；數字取自 2026-11-27 的 `gh`、`git ls-files` 和 `du`。執行時照 §3.6 的順序做，做完一項就移到 §2。

### 3.1 GitHub issue（D409 盤點時開著 29 個；D410 關 8 個後是 21 個；2026-11-27 晚上新開 #762、#765–#773 等之後是 26 個）

#### 3.1.1 工作已合併、issue 還開著

**全部處理完畢。** D410 關 8 個（#717、#718、#719、#710、#700、#612、#729、#659）。D411 關 #633（#761 部分退役）、#594（D302 已滿足，B-05／r005 8CAM 另開 #762）、#720（AC1–AC8 已跑，#764；後續 #770–#773）。#721 由 E6 協調對話在 #754 合併後關閉。細節見 §2。

#### 3.1.2 等主線（E6／E7）
- #732（FEAT-EXP-RUN，執行中）、#734／#730（報告）、#727（E7，使用者在 Colab 跑）、#675（LIVE Agent 預設設定，等 E6 選組）、#735（FEAT-LIVE-FINISH，只剩 #675）。

#### 3.1.3 延後或 blocked
- D407 延後：#733、#728、#740（重現包）。
- blocked：#566、#574（等 R2 #589）、#589、#672（等 #676）。
- 開著但沒有狀態標籤：#676（LIVE bug）。

#### 3.1.4 常設
- #93（任務板）、#674（更新紀錄）、#479（報告 epic）。#479 和 #734 的範圍重疊，大整理時決定是否把 #479 併進 #734。

#### 3.1.5 開著的 issue 上不一致的標籤

D410 已全部修正，見 §2；複查後開著的 issue 上 `ready`＋`in-progress` 並存、`needs-claude-review`、`blocked-user`、`pull:ready` 都是 0 個。repo 裡 `needs-claude-review`、`blocked-user`、`pull:ready`、`pull:waiting` 這幾個標籤定義本身還在，要不要刪留到大整理決定。

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

- 既有盤點：LOCAL `local/evidence/cl-inventory-729-20261127/`（MANIFEST SHA-256 `f20319cc7f34b273b4beffd40bd3d8c5381b1dfd8995f8b8b385bdce81fa0a54`；`inventory.json`、`DELETE_LIST.md`、`deletable_candidates_xref.json`）。那次的結論是 77 個可刪候選裡有 59 個其實有被引用，最確定可刪的只有 9 項、約 9.6 MB；D394 已經清過一次。
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
2. **GitHub**（Haiku 執行、協調者核對）：~~關閉 §3.1.1 的 issue、修正 §3.1.5 的標籤~~（D410、D411 已做完）；#93 工作清單改為只列現行工作。
3. **分支**：協調者寫好一條刪除指令（17 支已合併分支），使用者執行；`claude/docs-handoff-20261124` 先處理 `c37a0cc4`；archive 類的分支由使用者決定保留或改成 tag。
4. **`local/`**：照 §3.4 的流程重新盤點、核對、決定，由使用者刪除。
5. **文件**：照 §3.5，以 D408 的做法分批搬移，每批一個 PR，附對照表、pin 重新登記、連結檢查。
6. **收尾**：更新 PROGRESS、CODE_DOC_MAP、README 和交接文件，並在 #93 記決策、在 #674 追加一則。

### 3.7 文件、程式碼與本機資產唯讀盤點（2026-11-28）

`main` 基線為 `7dbd2ac084600a86b03710cb9eedd6647667c078`。依使用者指示完成盤點與現行基線的針對性測試。#794、#796、#798 當時待 Claude 審查，跳過其後續變更。#781 等 #785 合併。零付費，未執行模型推論或瀏覽器互動。 [#799](https://github.com/Polalalabear/amidst/issues/799)

#### 本機資產

現行工具在 `local/` 找到 264 項、301,609 筆檔案項目、13,201,742,587 邏輯 bytes。13 個頂層資產包有保護標記，GitHub 與 Git 分支引用查詢均完成，輸出未截斷。 [盤點工具](../../scripts/inventory_local_assets.py)

| 工具分類 | 項目 | 檔案項目 | 邏輯 bytes |
| --- | ---: | ---: | ---: |
| `KEEP` | 188 | 282,067 | 12,844,429,853 |
| `DELETABLE_CANDIDATE` | 49 | 1,063 | 100,028,742 |
| `UNCERTAIN` | 27 | 18,479 | 257,283,992 |

- 補查 76 個工具未判為 `KEEP` 的項目，涵蓋 799 份 issue／PR 本文、4,386 則留言、`origin/main` 與 6 個開啟 PR 的精確 head。49 個初步候選中，31 個有額外名稱線索（54,752,000 bytes），18 個在兩次掃描皆無命中（45,276,742 bytes，仍待核對）。名稱線索包括可能無關的一般檔名，並逐項列於候選複查表。 [#740](https://github.com/Polalalabear/amidst/issues/740)
- 已人工確認三個原列候選的用途。`e8-smoke-20261128` 對應 E8 smoke 的 Colab 包，`e6-rn-old16-20261127` 是 E6 R-N 預設輸入，`e7-colab-pack-pertick-20261127` 是 E8 仍引用的逐 tick 請求包。 [E8 重現文件](https://github.com/Polalalabear/amidst/blob/f6f70f7cb361da6009893a5f40af0e1ddadf2649/docs/operations/E8_REPRO_20261128.md#L124) [E6 腳本](https://github.com/Polalalabear/amidst/blob/f6f70f7cb361da6009893a5f40af0e1ddadf2649/scripts/experiments/run_all.sh#L154) [E8 設計](https://github.com/Polalalabear/amidst/blob/f6f70f7cb361da6009893a5f40af0e1ddadf2649/docs/evaluation/E8_DESIGN_V1.md#L50-L67)
- 逐檔 SHA-256 掃描涵蓋 301,607 個一般檔案路徑，略過 138 個 symlink 及兩個 FIFO。一個執行中的 gateway 狀態 JSON 在讀取時變動，已跳過雜湊。找到 2,052 組 hardlink（合計 2,052 個額外名稱），另有 20,566 組跨 inode 同內容檔案（18,028 組跨資產包），合計 231,882 個額外 inode、5,650,440,038 邏輯 bytes。PNG／JPEG 約占這個量的 91.5%，不少是不同時間點或資產包所需的影格。磁碟可回收位元組未量測，原始資產、路徑與收據皆未更動。

#### 程式碼

掃描 3,189 個 tracked 路徑。全檔相同的 Git blob 有 41 組（含非程式檔）。1,554 個程式／介面檔案與 3 份 notebook 的 22 個程式碼 cell 納入掃描。Python AST 找到 72 組相同函式，跨檔正規化文字則找到 241 組重複區塊（Python 226、JavaScript 4、HTML 11）。兩種偵測可命中同一段，語意重複仍需核對呼叫點。

| 檢視項目 | 目前判定 |
| --- | --- |
| Workbench v2 `hms`、`windowText` 與三個顯示文字常數 | 兩套現行實作在 182 組輸入和 3 個常數對照均一致，屬顯示層重複。 [track-map](../../frontend/workbench-v2/track-map-model.mjs) [topdown](../../frontend/workbench-v2/topdown-model.mjs) |
| Workbench v2 `playbackBounds` | app 組合 Q1、Q2、core 等資料，UI shell 僅處理 core track 路徑，保留各自呼叫範圍。 [app](../../frontend/workbench-v2/app.mjs) [UI shell](../../frontend/workbench-v2/ui-shell.mjs) |
| 暴力配對與索引式相機關聯 | 重複區塊最多 106 行，測試亦有 268 行相同，兩套入口和候選配對的驗證條件有差異。 [association](../../src/amidst/engineering/association.py) [local association](../../src/amidst/engineering/local_association.py) [tests](../../tests/engineering/test_local_association.py) |
| 資料包 `frozen_scan_view` | 38 行 AST 相同。獨立 verifier 依契約只用 Python 標準函式庫，因此保留獨立入口。 [verifier](../../scripts/check_handoff_pack.py) [資料包](../../src/amidst/q1q5/team_eval_pack.py) |
| 歷史 Blender 素材版面和 r004 稽核腳本 | 版面有 141 行重複，r004 腳本共用型態的軌跡檢查約 47 行。兩邊各有獨立入口，這次只有查讀。 [association media](../../src/amidst/workbench/blender_association_media.py) [physical media](../../src/amidst/workbench/blender_physical_media.py) [四人稽核](../../scripts/audit_r004_4actor.py) [自然步行稽核](../../scripts/audit_r004_natural_walk_endpoints.py) |

#### 文件與驗證

- 核對 419 個 tracked Markdown 路徑，其中 291 份現行、125 份歷史、3 個指向受版控正本的 symlink。2,056 個 repo 相對連結中，現行文件 11 筆找不到目標，集中在人工審核 README 的 10 個本機預覽，均未出現在 checkout 且在忽略規則內。歷史文件 22 筆缺相對目標。189 個可解析的本機 Markdown 片段中，有 14 筆歷史來源連結未被近似錨點解析器匹配。外部網址只核對派工相關 issue／PR。 [人工審核 README](../../human_review/README.md) [忽略規則](../../human_review/.gitignore)
- `Q1Q5_PROGRESS.md` 在基線是 #783 的快照。協調 PR #791 的 guard 報 `AUTHORITY_CHANGED`／`AUTHORITY_DRIFT`，狀態與 pin 由原負責線處理。這次的文件變更只有本總帳。 [進度總表](../operations/Q1Q5_PROGRESS.md) [#791 的 CI](https://github.com/Polalalabear/amidst/actions/runs/46111463020/job/140875711560)
- 基線的資產盤點與 relock 回放測試 10 項通過，Workbench track-map 與 topdown 測試 28 項通過。顯示函式對照另驗 `hms` 13 組、`windowText` 169 組和常數 3 項。這次無瀏覽器或即時端點測試。

#### LOCAL 證據與重建

| 位置 | 內容 | 大小 | 檔案數 | SHA-256 | 可重建 |
| --- | --- | ---: | ---: | --- | --- |
| `$AMIDST_ARTIFACTS/cx799-project-audit-20261128/` | `local-inventory.json`、`local-exact-duplicates.json`、`local-candidate-crossrefs.json`、`local-candidate-review.md`、`tracked-code-redundancy.json`、`tracked-doc-links.json`、三支掃描器與候選名稱輸入 | 40,524,876 bytes | 11（含 MANIFEST） | `MANIFEST.sha256` 的 SHA-256 `bf8aba6e9d7e61e2d89c64fa1c89fd795b8e4a5c62de4877f53e6440ffb12792` | 同一基線和資產可重跑。LOCAL 檔案與 GitHub 留言會變動，盤點是時間快照。 |

在 scratch clone 固定到上述 commit，`AMIDST_LOCAL` 指向唯讀掃描輸入，`AMIDST_ARTIFACTS` 設為證據上層目錄。`PYTHON` 使用有專案 pytest 相依的 Python 環境。`origin/main` 與開啟 PR 的參照須保留當時的 head。候選複查表可對照 `local-candidate-crossrefs.json` 的來源欄位。

```sh
EVIDENCE_DIR="$AMIDST_ARTIFACTS/cx799-project-audit-20261128"
"$PYTHON" -B scripts/inventory_local_assets.py --repo . --local-root "$AMIDST_LOCAL" --include-github --include-git-branches --json-out "$EVIDENCE_DIR/local-inventory.json"
"$PYTHON" -B "$EVIDENCE_DIR/audit_local_duplicates.py" "$AMIDST_LOCAL" > "$EVIDENCE_DIR/local-exact-duplicates.json"
"$PYTHON" -B "$EVIDENCE_DIR/audit_local_candidate_refs.py" "$EVIDENCE_DIR" Polalalabear/amidst
"$PYTHON" -B "$EVIDENCE_DIR/audit_tracked_sources.py" . "$EVIDENCE_DIR"
PYTHONPATH=src "$PYTHON" -B -m pytest -q -o addopts= -p no:cacheprovider tests/operations/test_inventory_local_assets.py tests/live_mode/test_relock_replay.py
node --test frontend/workbench-v2/track-map.test.mjs frontend/workbench-v2/topdown.test.mjs
```


## 4. 待辦（不屬於 §3 大整理、已經知道要做的）

- D394 後續：引用已刪 `local/` 項目的文件，要標「已刪除（D394）」（D394 第 5 點）。還沒做，併進 §3.6 第 5 步一次處理。
- `claude/docs-handoff-20261124` 的 `c37a0cc4`：決定是否補進合併文件（§3.3）。
