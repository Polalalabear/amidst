# 本機產物台帳（D138）

- 產生日期：2026-11-09；baseline：`mainline/q1q5` @ `2616661`；決策：D138（#93 comment 6721703703；完整清單在 #486 comment 6721703498）。
- 機器可讀版：[`configs/provenance/artifact_ledger_v1.json`](../../configs/provenance/artifact_ledger_v1.json)；schema：[`artifact_ledger_v1.schema.json`](../../configs/provenance/artifact_ledger_v1.schema.json)（登記值 `amidst.artifact-ledger.v1`）；工具：[`scripts/artifact_ledger.py`](../../scripts/artifact_ledger.py)（`validate`／`compute`／`verify`，唯讀）。
- 刪除候選與可執行指令（未執行）：[CLEANUP_CANDIDATES_D138.md](CLEANUP_CANDIDATES_D138.md)。
- 台帳登記不等於核准：任何刪除、封存或搬移都要使用者授權（#431）；更新 `main` 另需授權。

## 範圍與方法

- 以 #486 的 D138 清單、Claude 11-09 唯讀盤點（`coordinator-20261109/local-redundancy-audit.md`，LOCAL）、Codex 11-08 本機盤點（#486 comment 6721656964）與 `docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md` 為基礎，沒有重新盤點整台機器；不在這些來源裡的路徑不在台帳內。
- 共 **169** 筆記錄（其中 9 筆是被另一筆包含的子項，合計時不重複計算）。
- SHA-256：單檔直接算；資料夾為 manifest（每個檔案 SHA 與相對路徑，依路徑排序後再取 SHA-256；格式見 JSON 的 `rules.manifest`）。完成度：**143 筆 complete／共 132,547 個檔案已逐檔串流計算**；其餘筆為 checkout／git ref（只記 git HEAD）、快取／venv／scratch（只記大小，可再生或不屬原件），`completeness` 欄位逐筆標明。
- 原始 Blender、影片、資料集、校正與 GT 只算 SHA 與大小，沒有開啟內容。名為 `gt_private`（與 `ground_truth`）的資料夾**完全沒有開啟**，只記路徑、檔案數與大小：
  - `ART-r004-cx7-d115-20261102-01a199f8` → `gt_private/`：7 檔／371.70 KiB
  - `ART-r004-cx7-d115-20261102-01a199f8` → `B4-1/gt_private/`：1,173 檔／541.19 MiB
  - `ART-r004-cx7-d115-20261102-01a199f8` → `A4-1/gt_private/`：1,119 檔／514.08 MiB
  - `ART-r004-cx7r-20261104-01a19f8b` → `gt_private/`：13 檔／408.80 KiB
  - `ART-r004-cx7r-20261104-01a19f8b` → `B4-1/gt_private/`：10 檔／578.20 KiB
  - `ART-r004-cx7r-20261104-01a19f8b` → `A4-1/gt_private/`：11 檔／578.61 KiB
- `size_bytes` 是逐檔 `st_size` 加總；hardlink 檔案以路徑重複計算（例如 D124 的 bundle RGB 與 event safe），不等於磁碟回收量。
- `referenced_by` 來自上列盤點的 `檔案:行`；`UNKNOWN` 表示來源盤點也沒有查到。其中 8 個引用指向不在 `mainline/q1q5@2616661` 的檔案（在 #485 或相關 PR 分支），已在記錄中標註；引用內容沒有逐行重新核對。

## 依處置分類的空間合計

| 處置 | 筆數（不含子項、不含 git ref） | 大小合計 | 檔案數 | 說明 |
| --- | ---: | ---: | ---: | --- |
| 可刪除（`deletable`） | 25 | 401.15 MiB | 42,233 | 快取、可重新編碼的衍生圖、與 mainline byte 相同的未追蹤副本；刪除需授權（#431） |
| 收進主線（`move_to_mainline`） | 8 | 152.15 KiB | 8 | repo 外但應收進主線的文件／程式（不含 GT、raw）；本 PR 不搬 |
| 可封存（`archivable`） | 2 | 297.65 MiB | 1,190 | 歷史保存或複本，建議壓縮封存後再決定是否刪 |
| 需使用者決定（`user_decision`） | 46 | 8.22 GiB | 88,593 | 是否仍被使用或是否已在主線不確定；使用者決定 |
| 保留原件（`keep_original`） | 73 | 14.16 GiB | 124,192 | 原始資料、原錄製與驗收證據、使用中的 checkout；只在台帳記 SHA |

另有 6 筆 git ref（本機分支，不佔檔案空間）：收進主線 1、需使用者決定 5，見清單文件的「無遠端備份的本機分支」。

各類說明：

- **保留原件**：Blender 原檔、資料集／RGB、D115／D124 原 run、q1q5 驗收／重播證據、Qwen 診斷、正式驗收 release、現行 demo 套件與 checkout。原因是原錄製與真實模型輸出無法保證重建，且已被 hash pin 或 #488 引用。
- **收進主線**：只有 mainline 沒有同路徑的文件／測試與一個未推送的 commit。bytes 不同的檔案不在此類，要看 diff 才能決定。
- **可封存**：`/Users/Shared` 的 clean-room 複本（最終測試已複製到 demo-owned-v1）與 10-14 儲存清理的 379 份歷史保存。
- **需使用者決定**：review pack／小型規劃交接資料夾、與 mainline 內容不同的未追蹤檔、使用中的 venv、Codex 資料與快取、worktree 內的未提交檔。
- **可刪除**：見清單文件；全部可重建或與 mainline 完全相同。

## 總表

`SHA` 欄為 manifest／檔案 SHA-256 前 12 碼（checkout 與 git ref 為 git HEAD 前 12 碼），完整值在 JSON。`子` 表示被上一層包含。

### 可刪除（27 筆）

| ID | 路徑 | 類型 | 大小 | 檔案數 | SHA | 可重建 | 用途／理由 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `ART-d133-proxies-v2-jpeg` 子 | `~/amidst-artifacts/d133-playback-proxies-v2/jpeg` | derived_data | 105.49 MiB | 2370 | `466f39f2dc31` | yes | 2,370 張 JPEG90 播放用衍生圖（非 inference 原圖，無 symlink/hardlink） |
| `ART-d133-proxies-v2-webp` 子 | `~/amidst-artifacts/d133-playback-proxies-v2/webp` | derived_data | 58.78 MiB | 2370 | `6dcce0dff02d` | yes | 2,370 張 WebP90 播放用衍生圖 |
| `CACHE-npm` | `~/.npm` | cache | 400.11 MiB | 42095 | — | yes | npm 快取（11-09 已清一部分，剩約 519 MiB） |
| `LOC-fin-pytest_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.pytest_cache` | cache | 431.10 KiB | 5 | — | yes | 工具快取（pytest／ruff） |
| `LOC-fin-ruff_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.ruff_cache` | cache | 85.75 KiB | 43 | — | yes | 工具快取（pytest／ruff） |
| `LOC-main-pytest_cache` | `~/Developer/amidst/.pytest_cache` | cache | 90.11 KiB | 5 | — | yes | 工具快取（pytest） |
| `LOC-main-ruff_cache` | `~/Developer/amidst/.ruff_cache` | cache | 15.74 KiB | 54 | — | yes | 工具快取（ruff） |
| `UNT-configs--q1q5` | `~/Developer/amidst/configs/q1q5` | untracked_source | 353.17 KiB | 11 | `b6d12b871374` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_BASELINE_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md` | untracked_source | 5.59 KiB | 1 | `e6a6de7f1891` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_BASELINE_DECISIONS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_DECISIONS.md` | untracked_source | 3.47 KiB | 1 | `27c8930dbb28` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_BASELINE_RUNNER.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_RUNNER.md` | untracked_source | 9.87 KiB | 1 | `e16daed41e34` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_BASELINE_V1_PROTOCOL.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md` | untracked_source | 15.59 KiB | 1 | `31c49330a682` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_LINKED_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md` | untracked_source | 6.72 KiB | 1 | `55330e00bb5b` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_PRODUCTION_PREPARATION.md` | `~/Developer/amidst/docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md` | untracked_source | 3.01 KiB | 1 | `f5f1f1802f20` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_REVIEWED_INPUTS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_REVIEWED_INPUTS.md` | untracked_source | 3.27 KiB | 1 | `b65e90df3395` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--evaluation` | `~/Developer/amidst/docs/evaluation` | untracked_source | 3.16 KiB | 2 | `89d316dea021` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | untracked_source | 4.14 KiB | 1 | `275a4e1101eb` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--Q1Q5_LINKED_ACCEPTANCE_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json` | untracked_source | 5.81 KiB | 1 | `5826fb3dea4b` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--accept_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/accept_q1q5_linked_baseline.py` | untracked_source | 1.33 KiB | 1 | `64aeeea9ab29` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--build_q1q5_pinned_index.py` | `~/Developer/amidst/scripts/build_q1q5_pinned_index.py` | untracked_source | 1.11 KiB | 1 | `41f465691d98` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--import_q3_minimum_review.py` | `~/Developer/amidst/scripts/import_q3_minimum_review.py` | untracked_source | 2.75 KiB | 1 | `8ce5f1aa58f3` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--measure_q1q5_dynamic_rgb.py` | `~/Developer/amidst/scripts/measure_q1q5_dynamic_rgb.py` | untracked_source | 3.21 KiB | 1 | `a3d5aa3b47af` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--preflight_q1q5_production.py` | `~/Developer/amidst/scripts/preflight_q1q5_production.py` | untracked_source | 2.19 KiB | 1 | `b9329bac83d2` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--prepare_q1q5_baseline_source.py` | `~/Developer/amidst/scripts/prepare_q1q5_baseline_source.py` | untracked_source | 1.11 KiB | 1 | `eaa4074d9a41` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--replay_q1q5_dynamic_evidence.py` | `~/Developer/amidst/scripts/replay_q1q5_dynamic_evidence.py` | untracked_source | 4.25 KiB | 1 | `1b46a491188f` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--run_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/run_q1q5_linked_baseline.py` | untracked_source | 2.03 KiB | 1 | `8982ec819204` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-src--amidst--evaluation--q3_review_import.py` | `~/Developer/amidst/src/amidst/evaluation/q3_review_import.py` | untracked_source | 9.53 KiB | 1 | `5db6c4d742a7` | partial | 主庫未追蹤的程式／設定／文件 |

### 收進主線（9 筆）

| ID | 路徑 | 類型 | 大小 | 檔案數 | SHA | 可重建 | 用途／理由 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `REF-codex--controlled-scene-real-v2-2a` | `~/Developer/amidst` | git_ref | — | — | `60fa8ef64988` | no | 本機分支 codex/controlled-scene-real-v2-2a：287 行 Q1-Q5 demo 討論文件（docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md）；GitHub 找不到此 SHA |
| `UNT-docs--engineering--Q5_STATECHART.md` | `~/Developer/amidst/docs/engineering/Q5_STATECHART.md` | untracked_source | 9.17 KiB | 1 | `43e20b32bad9` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q5_STATECHART_STAGE1_REVIEW.md` | `~/Developer/amidst/docs/engineering/Q5_STATECHART_STAGE1_REVIEW.md` | untracked_source | 29.19 KiB | 1 | `16b22478ddea` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q5_STATECHART_STAGE2_EVIDENCE.json` | `~/Developer/amidst/docs/engineering/Q5_STATECHART_STAGE2_EVIDENCE.json` | untracked_source | 5.27 KiB | 1 | `c190527870a5` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q5_STATECHART_STAGE2_RESULTS.md` | `~/Developer/amidst/docs/engineering/Q5_STATECHART_STAGE2_RESULTS.md` | untracked_source | 15.91 KiB | 1 | `6b97fe462e5f` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--SCENE_Q1_Q2_PLAN_20261020.md` | `~/Developer/amidst/docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md` | untracked_source | 14.87 KiB | 1 | `87bf10605127` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--DISK_AUDIT_20261015.md` | `~/Developer/amidst/docs/history/DISK_AUDIT_20261015.md` | untracked_source | 12.59 KiB | 1 | `6aaa880b00e9` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--WORKTREE_RETIREMENT_ASSESSMENT_20261020.md` | `~/Developer/amidst/docs/history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md` | untracked_source | 11.61 KiB | 1 | `82023e4b8f4a` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--disk_cleanup_receipt_20261015.json` | `~/Developer/amidst/docs/history/disk_cleanup_receipt_20261015.json` | untracked_source | 53.54 KiB | 1 | `823e0d77a61c` | partial | 主庫未追蹤的程式／設定／文件 |

### 可封存（2 筆）

| ID | 路徑 | 類型 | 大小 | 檔案數 | SHA | 可重建 | 用途／理由 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `LOC-shared-cleanroom` | `/Users/Shared/amidst-p1-clean-room-20261026` | evidence | 285.16 MiB | 806 | `14cf018896d4` | partial | P1 工程／最終測試 clean-room 複本（非 git）；最終測試已複製到 demo-owned-v1/data/p1-v4/ |
| `UNT-docs--history--storage_cleanup_20261014` | `~/Developer/amidst/docs/history/storage_cleanup_20261014` | untracked_source | 12.49 MiB | 384 | `e2c7a5dc803e` | partial | 主庫未追蹤的程式／設定／文件 |

### 需使用者決定（51 筆）

| ID | 路徑 | 類型 | 大小 | 檔案數 | SHA | 可重建 | 用途／理由 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `ART-coordinator-20261025` | `~/amidst-artifacts/coordinator-20261025` | doc | 83.83 KiB | 8 | `fbc0fbb041ba` | unknown | 小型規劃／協調／交接歷史 |
| `ART-coordinator-20261108` | `~/amidst-artifacts/coordinator-20261108` | doc | 85.55 KiB | 7 | `373e714cf847` | unknown | 小型規劃／協調／交接歷史 |
| `ART-d133-playback-proxies-v2` | `~/amidst-artifacts/d133-playback-proxies-v2` | derived_data | 166.03 MiB | 4741 | `10841709f872` | partial | 播放 proxy（JPEG90／WebP90 為衍生圖；manifest.json 與量測收據必留） |
| `ART-d67` | `~/amidst-artifacts/d67` | doc | 226.51 KiB | 95 | `7a3e59b650df` | unknown | 小型規劃／協調／交接歷史 |
| `ART-hsv-proposal-20261021` | `~/amidst-artifacts/hsv-proposal-20261021` | doc | 249.82 KiB | 39 | `52a7efde644c` | unknown | 小型規劃／協調／交接歷史 |
| `ART-q1q2-plan-x2-x3-20261020` | `~/amidst-artifacts/q1q2-plan-x2-x3-20261020` | doc | 18.88 KiB | 4 | `bfd32c006ce2` | unknown | 小型規劃／協調／交接歷史 |
| `ART-q1q3-authoring-yyin-v0-pilot_20261102_01a199f8` | `~/amidst-artifacts/q1q3-authoring-yyin-v0-pilot_20261102_01a199f8` | derived_data | 3.71 MiB | 27 | `a2ea951d145d` | unknown | yyin authoring pilot 資料夾（11 月） |
| `ART-q1q3-authoring-yyin-v0-pilot_20261102_01a199f8.zip` | `~/amidst-artifacts/q1q3-authoring-yyin-v0-pilot_20261102_01a199f8.zip` | derived_data | 3.71 MiB | 1 | `c02da7e2bc1b` | unknown | yyin authoring pilot zip（3,889,180 bytes） |
| `ART-q1q5-clock-mapping` | `~/amidst-artifacts/q1q5-clock-mapping` | doc | 154.88 KiB | 33 | `f0fd792fe203` | unknown | 小型規劃／協調／交接歷史 |
| `ART-q1q5-contract-1d1e061` | `~/amidst-artifacts/q1q5-contract-1d1e061` | doc | 204.27 KiB | 5 | `101144a6daa5` | unknown | 小型規劃／協調／交接歷史 |
| `ART-q1q5-search-budget-proposal-20261020` | `~/amidst-artifacts/q1q5-search-budget-proposal-20261020` | doc | 644 B | 1 | `c13794e63c64` | unknown | 小型規劃／協調／交接歷史 |
| `ART-q4-eval-program-20261021` | `~/amidst-artifacts/q4-eval-program-20261021` | doc | 14.58 KiB | 5 | `a5e00b51ef07` | unknown | 小型規劃／協調／交接歷史 |
| `ART-r004-prereview-team-v1_20261023` | `~/amidst-artifacts/r004-prereview-team-v1_20261023` | derived_data | 7.55 MiB | 74 | `e44595d405ef` | unknown | team review pack／prereview 離線交付版本 |
| `ART-r004-prereview-team-v2_20261024` | `~/amidst-artifacts/r004-prereview-team-v2_20261024` | derived_data | 10.27 MiB | 83 | `0bb09a95c700` | unknown | team review pack／prereview 離線交付版本 |
| `ART-r004-scene-change-proposal` | `~/amidst-artifacts/r004-scene-change-proposal` | doc | 186.88 KiB | 15 | `79f709d9afef` | unknown | 小型規劃／協調／交接歷史 |
| `ART-team-handoff-yyin-20261025` | `~/amidst-artifacts/team-handoff-yyin-20261025` | doc | 3.46 MiB | 17 | `9d7c1c63e85b` | unknown | 小型規劃／協調／交接歷史 |
| `ART-team_review_pack_v0-pilot_20261021` | `~/amidst-artifacts/team_review_pack_v0-pilot_20261021` | derived_data | 9.85 MiB | 33 | `7e9e28e8f27e` | unknown | team review pack／prereview 離線交付版本 |
| `ART-team_review_pack_v0-pilot_20261021.df-after.txt` | `~/amidst-artifacts/team_review_pack_v0-pilot_20261021.df-after.txt` | doc | 188 B | 1 | `4e6a5e49e512` | no | review pack 前後 df 收據（文字） |
| `ART-team_review_pack_v0-pilot_20261021.df-before.txt` | `~/amidst-artifacts/team_review_pack_v0-pilot_20261021.df-before.txt` | doc | 188 B | 1 | `ce99015f95b8` | no | review pack 前後 df 收據（文字） |
| `CACHE-codex-home` | `~/.codex` | cache | 2.90 GiB | 11967 | — | no | Codex 資料（archived_sessions、visualizations、plugins、sessions；約 3 GiB） |
| `CACHE-codex-runtimes` | `~/.cache/codex-runtimes` | cache | 1.55 GiB | 30002 | — | unknown | Codex 執行環境（約 1.7 GiB） |
| `CACHE-torch` | `~/.cache/torch` | cache | 34.33 MiB | 226 | — | unknown | 可能含預訓練權重（約 35 MiB） |
| `CO-wt-finalization` | `~/Developer/amidst/.local-worktrees/phase1-finalization` | code_checkout | — | — | `c6661dd53507` | partial | worktree：分支 codex/simulation-engineering，3 項未提交 |
| `ENV-d139-venv` | `~/amidst-d139-20261108/.venv` | environment | 752.02 MiB | 7402 | — | yes | D147/D149 checkout venv |
| `ENV-demo-venv` | `~/amidst-demo-20261104/.venv` | environment | 737.57 MiB | 6807 | — | yes | demo checkout 自有 venv（約 0.72 GB） |
| `LOC-fin-DEMO_V1` | `~/Developer/amidst/.local-worktrees/phase1-finalization/docs/engineering/DEMO_V1.md` | untracked_source | 12.44 KiB | 1 | `67440fb25c3d` | no | 舊 PG／Ollama launcher 操作說明（tracked 檔案新增 14 行未提交） |
| `LOC-fin-untracked-start-demo` | `~/Developer/amidst/.local-worktrees/phase1-finalization/start-demo.command` | untracked_source | 325 B | 1 | `26bac8d3f93b` | no | 舊啟動器（untracked，325 bytes） |
| `LOC-fin-untracked-start_local_demo` | `~/Developer/amidst/.local-worktrees/phase1-finalization/scripts/start_local_demo.py` | untracked_source | 12.77 KiB | 1 | `e927310b6688` | no | 舊 PostgreSQL／Ollama／workbench 啟動腳本（untracked，13,074 bytes） |
| `REF-phase1--physical-policy-approval` | `~/Developer/amidst` | git_ref | — | — | `c5956dc825f6` | no | 本機分支 phase1/physical-policy-approval：phase1 物理政策與 known collider scopes 核准（53 檔／24,053 行新增） |
| `REF-phase1--pilot-robustness-validation` | `~/Developer/amidst` | git_ref | — | — | `ce2974b25b31` | no | 本機分支 phase1/pilot-robustness-validation：controlled pilot robustness scenarios（14 檔／3,194 行） |
| `REF-phase1--projection-conditioning-mitigation` | `~/Developer/amidst` | git_ref | — | — | `5f020b075d4a` | no | 本機分支 phase1/projection-conditioning-mitigation：pilot projection conditioning mitigation 比較（34 檔／10,684 行） |
| `REF-phase1--projection-model-upgrade` | `~/Developer/amidst` | git_ref | — | — | `8f4055ffcdc3` | no | 本機分支 phase1/projection-model-upgrade：additive pilot projection model 比較（42 檔／13,785 行） |
| `REF-phase1--projection-sensitivity` | `~/Developer/amidst` | git_ref | — | — | `b90e81adb3ac` | no | 本機分支 phase1/projection-sensitivity：projection precision evidence scope（24 檔／7,080 行） |
| `SCR-claude-scratch-root` | `/private/tmp/claude-501` | scratch | 2.08 GiB | 26929 | — | yes | Claude session scratchpads（各 session 的 clone、venv、e2e 結果；含本 session） |
| `UNT-docs--README.md` | `~/Developer/amidst/docs/README.md` | untracked_source | 22.65 KiB | 1 | `ba25582b2667` | no | 主庫 docs/README.md 的 2 行新增（M） |
| `UNT-docs--engineering--FINALIZATION_DECOUPLING_PLAN_20261020.md` | `~/Developer/amidst/docs/engineering/FINALIZATION_DECOUPLING_PLAN_20261020.md` | untracked_source | 11.35 KiB | 1 | `6b2c731ac78a` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_DYNAMIC_BASELINE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_DYNAMIC_BASELINE.md` | untracked_source | 1.65 KiB | 1 | `b16b6d9a0622` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_DYNAMIC_BASELINE_RESULTS.json` | `~/Developer/amidst/docs/engineering/Q1Q5_DYNAMIC_BASELINE_RESULTS.json` | untracked_source | 13.00 KiB | 1 | `7de2f572fe0a` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_LINKED_RUNTIME.md` | `~/Developer/amidst/docs/engineering/Q1Q5_LINKED_RUNTIME.md` | untracked_source | 2.27 KiB | 1 | `3417c0fbf4bc` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_PARAMETER_PROPOSAL.md` | `~/Developer/amidst/docs/engineering/Q1Q5_PARAMETER_PROPOSAL.md` | untracked_source | 4.88 KiB | 1 | `20bec3ce3b93` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--Q1Q5_PLAYBACK_CONTINUITY.md` | `~/Developer/amidst/docs/engineering/Q1Q5_PLAYBACK_CONTINUITY.md` | untracked_source | 6.05 KiB | 1 | `25606b79b60a` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--engineering--R004_SCENE_CHANGE_PROPOSAL.md` | `~/Developer/amidst/docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` | untracked_source | 13.53 KiB | 1 | `29d01fa0b6e1` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-docs--history--Q1Q5_PLAYBACK_ACCEPTANCE_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_PLAYBACK_ACCEPTANCE_20261024.json` | untracked_source | 7.81 KiB | 1 | `18b427f50339` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-frontend--workbench-v2` | `~/Developer/amidst/frontend/workbench-v2` | untracked_source | 117.07 KiB | 12 | `feb03cf78341` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--build_q1q5_detection_index.py` | `~/Developer/amidst/scripts/build_q1q5_detection_index.py` | untracked_source | 3.45 KiB | 1 | `9883fd986a78` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--prepare_q1q5_synthetic_registry.py` | `~/Developer/amidst/scripts/prepare_q1q5_synthetic_registry.py` | untracked_source | 4.78 KiB | 1 | `c5f1f7472c27` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--render_q1q5_dynamic_rgb.py` | `~/Developer/amidst/scripts/render_q1q5_dynamic_rgb.py` | untracked_source | 10.17 KiB | 1 | `25b812d95ccb` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--run_q1q5_baseline.py` | `~/Developer/amidst/scripts/run_q1q5_baseline.py` | untracked_source | 9.96 KiB | 1 | `bc13cb65006a` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-scripts--serve_q1q5_linked_workbench.py` | `~/Developer/amidst/scripts/serve_q1q5_linked_workbench.py` | untracked_source | 1.87 KiB | 1 | `558e4cb231e3` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-src--amidst--q1q5` | `~/Developer/amidst/src/amidst/q1q5` | untracked_source | 208.34 KiB | 17 | `afc14c8c14ff` | partial | 主庫未追蹤的程式／設定／文件 |
| `UNT-tests--q1q5` | `~/Developer/amidst/tests/q1q5` | untracked_source | 158.55 KiB | 24 | `4f37e1ba2469` | partial | 主庫未追蹤的程式／設定／文件 |

### 保留原件（80 筆）

| ID | 路徑 | 類型 | 大小 | 檔案數 | SHA | 可重建 | 用途／理由 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `ART-coordinator-20261109` | `~/amidst-artifacts/coordinator-20261109` | evidence | 83.27 MiB | 373 | `1f0b3e3cff18` | no | 協調者今日證據（含 local-redundancy-audit.md） |
| `ART-d127-418-office-expanded-r005` | `~/amidst-artifacts/d127-418-office-expanded-r005` | evidence | 1.94 MiB | 11 | `b34a2f43c08a` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d127-418-office-expanded-r005-preview-v2` | `~/amidst-artifacts/d127-418-office-expanded-r005-preview-v2` | evidence | 3.44 MiB | 11 | `1383d702fe9c` | partial | r005 六張相機 RGB 預覽（已複製到 demo-owned-v1） |
| `ART-d129-464-r005-probe-20261105-a` | `~/amidst-artifacts/d129-464-r005-probe-20261105-a` | evidence | 345.71 KiB | 6 | `23accf4acb58` | partial | r005 detection probe report（已複製到 demo-owned-v1 data/artifacts/） |
| `ART-d131-previews` | `~/amidst-artifacts/d131-previews` | evidence | 213.17 MiB | 8353 | `9bee2c1b9930` | partial | 四個 preview checkout 與 job／receipts／tooling；node PID 54190/54195、python3.12 PID 54263 仍開其 logs |
| `ART-d133-bench-pilot` | `~/amidst-artifacts/d133-bench-pilot` | evidence | 654.84 KiB | 3 | `11e2412309a3` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-measurement-report` | `~/amidst-artifacts/d133-measurement-report` | evidence | 618.60 KiB | 20 | `d4d5234764ec` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-playback-measurements` | `~/amidst-artifacts/d133-playback-measurements` | evidence | 28.73 MiB | 55 | `90e831fcdeff` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-playback-proxies` | `~/amidst-artifacts/d133-playback-proxies` | evidence | 0 B | 0 | `e3b0c44298fc` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-proxies-v2-manifest` 子 | `~/amidst-artifacts/d133-playback-proxies-v2/manifest.json` | evidence | 1.76 MiB | 1 | `48668dcfc5ca` | no | D133 proxy manifest（量測收據綁定） |
| `ART-d133-switch-baseline` | `~/amidst-artifacts/d133-switch-baseline` | evidence | 1.41 MiB | 44 | `229b4708ae84` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-switch-headless` | `~/amidst-artifacts/d133-switch-headless` | evidence | 1.62 MiB | 65 | `dcc5fb97f9b7` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-switch-pilot` | `~/amidst-artifacts/d133-switch-pilot` | evidence | 0 B | 0 | `e3b0c44298fc` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-switch-pilot-v2` | `~/amidst-artifacts/d133-switch-pilot-v2` | evidence | 743.14 KiB | 5 | `93c3d5bb85fd` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-workbench-measurements` | `~/amidst-artifacts/d133-workbench-measurements` | evidence | 5.26 MiB | 19 | `ed4f175a7669` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-workbench-pilot` | `~/amidst-artifacts/d133-workbench-pilot` | evidence | 0 B | 0 | `e3b0c44298fc` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d133-workbench-pilot-v2` | `~/amidst-artifacts/d133-workbench-pilot-v2` | evidence | 544.49 KiB | 3 | `46399395f0bb` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d134-445-integration` | `~/amidst-artifacts/d134-445-integration` | evidence | 8.10 MiB | 49 | `f559b78700a2` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-d135-487-mac-ui` | `~/amidst-artifacts/d135-487-mac-ui` | evidence | 71.92 MiB | 405 | `6c45be67fd2c` | partial | #487 Mac UI 驗證截圖與結果 |
| `ART-demo-20261104` | `~/amidst-artifacts/demo-20261104` | evidence | 531.79 KiB | 15 | `69ad0b54e302` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-demo-all-events-shots-20261104` | `~/amidst-artifacts/demo-all-events-shots-20261104` | evidence | 1.01 MiB | 32 | `7b885dcb80ab` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-demo-launcher_20261102_01a199f8` | `~/amidst-artifacts/demo-launcher_20261102_01a199f8` | evidence | 94.30 KiB | 2 | `ce9f06a0adb2` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-demo-owned-v1` | `~/amidst-artifacts/demo-owned-v1` | derived_data | 3.54 GiB | 12835 | `e15cee23e380` | partial | 現行 saved-observation demo 自有資料、模型、runtime、metadata、provenance 與 evidence（#486 收編） |
| `ART-demo-ui-f_20261102_01a199f8` | `~/amidst-artifacts/demo-ui-f_20261102_01a199f8` | evidence | 50.08 KiB | 2 | `21b7c73fd681` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-epicd-b-20261108` | `~/amidst-artifacts/epicd-b-20261108` | evidence | 631.17 KiB | 9 | `faaa9edba508` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-experiment-record-20261108` | `~/amidst-artifacts/experiment-record-20261108` | evidence | 45.30 MiB | 119 | `3eebe3e40e89` | no | 實驗紀錄（#488）工作資料夾 |
| `ART-project-docs-20261104` | `~/amidst-artifacts/project-docs-20261104` | evidence | 138.14 KiB | 11 | `6e51ec26c4d9` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動）（含 project-docs-20261104.zip、branch_retirement_20261108.md、deleted_branches_20261108.tsv） |
| `ART-q1q5-baseline-acceptance-v1_20261024` | `~/amidst-artifacts/q1q5-baseline-acceptance-v1_20261024` | evidence | 9.10 MiB | 1334 | `72aa22d41062` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-baseline-runner-v1_20261024` | `~/amidst-artifacts/q1q5-baseline-runner-v1_20261024` | evidence | 37.36 MiB | 8279 | `96f7f964a30b` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-baseline-telemetry-20261024` | `~/amidst-artifacts/q1q5-baseline-telemetry-20261024` | evidence | 530.35 KiB | 135 | `486e540571b2` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-baseline-telemetry-v1_20261024` | `~/amidst-artifacts/q1q5-baseline-telemetry-v1_20261024` | evidence | 531.30 KiB | 135 | `2cd38e60ce09` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-baseline-telemetry-v2_20261024` | `~/amidst-artifacts/q1q5-baseline-telemetry-v2_20261024` | evidence | 2.18 MiB | 300 | `ef35950581f2` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-dynamic-baseline-v1_20261025` | `~/amidst-artifacts/q1q5-dynamic-baseline-v1_20261025` | evidence | 743.27 MiB | 21091 | `0eb5d8910303` | partial | dynamic RGB、錄製、原始逐次數據、source 與 runtime-deps |
| `ART-q1q5-event-modes-20261022` | `~/amidst-artifacts/q1q5-event-modes-20261022` | evidence | 7.61 MiB | 704 | `c4acea4f3b1a` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-linked-baseline-v1_20261024` | `~/amidst-artifacts/q1q5-linked-baseline-v1_20261024` | evidence | 20.80 MiB | 1975 | `33af89849b6f` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-model-compare-20261023` | `~/amidst-artifacts/q1q5-model-compare-20261023` | evidence | 3.09 MiB | 207 | `5c9f5e4a75cc` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-playback-continuity-v2_20261024` | `~/amidst-artifacts/q1q5-playback-continuity-v2_20261024` | evidence | 53.07 MiB | 4013 | `4f7375a2eb96` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-qwen-diagnosis-20261023` | `~/amidst-artifacts/q1q5-qwen-diagnosis-20261023` | evidence | 352.27 KiB | 78 | `211a499a160a` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-qwen-runtime-20261023` | `~/amidst-artifacts/q1q5-qwen-runtime-20261023` | evidence | 6.05 MiB | 571 | `2a6fec13eaf5` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-qwen3-contention-20261023` | `~/amidst-artifacts/q1q5-qwen3-contention-20261023` | evidence | 3.74 MiB | 424 | `ffff03fda365` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-qwen3-switch-20261023` | `~/amidst-artifacts/q1q5-qwen3-switch-20261023` | evidence | 373.32 KiB | 76 | `b741df3e65ff` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-qwen3-untruncated_20261026_01a1735f` | `~/amidst-artifacts/q1q5-qwen3-untruncated_20261026_01a1735f` | evidence | 184.41 KiB | 123 | `feadb0533a2b` | no | Qwen 診斷／競爭／逾時／錄製結果 |
| `ART-q1q5-rc3-rerecord-v1_20261026` | `~/amidst-artifacts/q1q5-rc3-rerecord-v1_20261026` | evidence | 53.52 MiB | 10175 | `15b784f27569` | no | rc3 重錄結果 |
| `ART-q1q5-rc5-rerecord-20261027-d92` | `~/amidst-artifacts/q1q5-rc5-rerecord-20261027-d92` | evidence | 54.02 MiB | 10867 | `24f4fdb97edc` | no | rc5 重錄結果 |
| `ART-q1q5-rc5-rerecord-20261027-d92-validation` | `~/amidst-artifacts/q1q5-rc5-rerecord-20261027-d92-validation` | evidence | 7.87 MiB | 178 | `b5fff334c861` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-review-closeout-v1_20261025` | `~/amidst-artifacts/q1q5-review-closeout-v1_20261025` | evidence | 30.67 MiB | 1177 | `96842d551bb2` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-staging-20261021` | `~/amidst-artifacts/q1q5-staging-20261021` | evidence | 35.45 MiB | 3377 | `276d8179d7ce` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-q1q5-workbench-reopen_20261025T175011` | `~/amidst-artifacts/q1q5-workbench-reopen_20261025T175011` | evidence | 95.00 KiB | 7 | `7c161a30d762` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `ART-q1q5_acceptance` | `~/amidst-artifacts/q1q5_acceptance` | evidence | 819.08 KiB | 17 | `6baa6c91677d` | partial | q1q5 驗收／重播／linked／telemetry／staging 工程結果 |
| `ART-r004-build-20261021` | `~/amidst-artifacts/r004-build-20261021` | raw_data | 26.19 MiB | 94 | `c9bc9dd753ef` | unknown | r004 靜態 build／graphs／hfov 選擇（含 .blend 與安全 catalog） |
| `ART-r004-build-v2-20261021` | `~/amidst-artifacts/r004-build-v2-20261021` | raw_data | 28.23 MiB | 94 | `964834783bd9` | unknown | r004 靜態 build／graphs／hfov 選擇（含 .blend 與安全 catalog） |
| `ART-r004-cx7-d115-20261102-01a199f8` | `~/amidst-artifacts/r004-cx7-d115-20261102-01a199f8` | raw_data | 1.03 GiB | 2050 | `3a3eb809457b` | unknown | D115 原 run：safe 輸出與 GT（gt_private 只記路徑與大小） |
| `ART-r004-cx7r-20261104-01a19f8b` | `~/amidst-artifacts/r004-cx7r-20261104-01a19f8b` | raw_data | 2.06 GiB | 4111 | `95f3ac023ecf` | partial | D124 原件與 private producer 證據；bundle RGB 與 event safe 用 hardlink（兩個 locator 不是兩份空間） |
| `ART-r004-graphs-proposed-20261021` | `~/amidst-artifacts/r004-graphs-proposed-20261021` | evidence | 3.21 MiB | 31 | `d7756a67e061` | unknown | r004 靜態 build／graphs／hfov 選擇（含 .blend 與安全 catalog） |
| `ART-r004-hfov-selection-20261021` | `~/amidst-artifacts/r004-hfov-selection-20261021` | evidence | 1009 B | 3 | `2eb92d4f6cbc` | unknown | r004 靜態 build／graphs／hfov 選擇（含 .blend 與安全 catalog） |
| `ART-research-plan-ui-20261108` | `~/amidst-artifacts/research-plan-ui-20261108` | evidence | 3.20 MiB | 13 | `d6299d95db19` | unknown | 近期工作、小型計畫／報告／pack／截圖（Codex 盤點：保留，不值得動） |
| `CO-claude` | `~/Developer/amidst-claude` | code_checkout | — | — | `7c01522523d6` | partial | 協調者 worktree（主庫 amidst）：分支 claude/k1-hypothesis |
| `CO-d139` | `~/amidst-d139-20261108` | code_checkout | — | — | `9fade4a89d05` | partial | Codex 的 D147/D149 checkout：分支 codex/d147-d149-backend |
| `CO-demo` | `~/amidst-demo-20261104` | code_checkout | — | — | `89a73e6516c6` | partial | demo checkout（8785 使用中）：分支 claude/ui-redesign-v1 |
| `CO-main` | `~/Developer/amidst` | code_checkout | — | — | `60fa8ef64988` | partial | 主庫 clone（其他 worktree 的 git 主庫）：分支 codex/controlled-scene-real-v2-2a，50 筆未提交 |
| `CO-q1q5` | `~/Developer/amidst-q1q5` | code_checkout | — | — | `5f22c46b94d2` | partial | mainline/q1q5 clone（各 session clone 來源） |
| `CO-wt-clean` | `~/Developer/amidst/.local-worktrees/phase1-case23-clean` | code_checkout | — | — | `c4a8a0acfd3d` | partial | worktree：detached HEAD，1 筆 untracked（clean release 目錄） |
| `CO-wt-formal` | `~/Developer/amidst/.local-worktrees/phase1-case23-formal` | code_checkout | — | — | `043bed2d6dac` | partial | worktree：分支 codex/phase1-case23-formal，clean |
| `ENV-claude-venv` | `~/Developer/amidst-claude/.venv` | environment | 330.87 MiB | 6569 | — | yes | 協調者 worktree venv（使用中） |
| `LOC-clean-data` | `~/Developer/amidst/.local-worktrees/phase1-case23-clean/data` | raw_data | 292.26 MiB | 1121 | `e01e3010c32c` | unknown | phase1-case23-clean data |
| `LOC-clean-human_review` | `~/Developer/amidst/.local-worktrees/phase1-case23-clean/human_review` | raw_data | 124.82 MiB | 273 | `a24f962b1f5c` | unknown | clean 人審資料 |
| `LOC-clean-release` 子 | `~/Developer/amidst/.local-worktrees/phase1-case23-clean/data/finalization/reviewed_run_case123_clean_v2_20261014` | raw_data | 163.60 MiB | 777 | `06411547935b` | no | case1-3 clean v2 正式重現 release（約 777 個檔案，default untracked 展開 9 檔） |
| `LOC-fin-data` | `~/Developer/amidst/.local-worktrees/phase1-finalization/data` | raw_data | 2.12 GiB | 13860 | `a86c10e6b4ce` | unknown | phase1-finalization 原資料、PG 與 Ollama state |
| `LOC-fin-human_review` | `~/Developer/amidst/.local-worktrees/phase1-finalization/human_review` | raw_data | 125.62 MiB | 299 | `fdf52df0df90` | unknown | phase1-finalization 人審資料 |
| `LOC-formal-data` | `~/Developer/amidst/.local-worktrees/phase1-case23-formal/data` | raw_data | 750.59 MiB | 3298 | `43f31a5af145` | unknown | phase1-case23-formal data（含 formal release） |
| `LOC-formal-human_review` | `~/Developer/amidst/.local-worktrees/phase1-case23-formal/human_review` | raw_data | 125.22 MiB | 289 | `3019b671f892` | unknown | formal 人審資料 |
| `LOC-formal-release` 子 | `~/Developer/amidst/.local-worktrees/phase1-case23-formal/data/finalization/reviewed_run_case123_formal_v2_20261014` | raw_data | 595.81 MiB | 2891 | `d447c6e3d07a` | no | case1-3 formal v2 正式驗收 release |
| `LOC-main-blender` | `~/Developer/amidst/blender` | raw_data | 1.31 GiB | 4 | `e401ab5be351` | no | school_v2.blend、school_v3.blend 與 working/（原始 Blender） |
| `LOC-main-data` | `~/Developer/amidst/data` | raw_data | 771.14 MiB | 4385 | `d24edcf23396` | unknown | 資料集、RGB、校正／人審、source/GT 隔離資料與 checkpoint（含 data/engineering 三個 untracked 目錄） |
| `LOC-main-gdrive` | `~/Developer/amidst/Google_Drive_Q3_20261020` | raw_data | 170.95 KiB | 6 | `a586d2bd0ff8` | unknown | Google Drive Q3 下載（untracked） |
| `LOC-models` | `~/Models/amidst` | model | 77.25 MiB | 2 | `ee6aa26933e6` | partial | RT-DETR 模型權重（已複製到 demo-owned-v1/models/rtdetr/） |
| `UNT-Google_Drive_Q3_20261020` 子 | `~/Developer/amidst/Google_Drive_Q3_20261020` | raw_data | 170.95 KiB | 6 | `a586d2bd0ff8` | unknown | 主庫未追蹤的資料目錄 |
| `UNT-data--engineering--contact_control_20261016_v1` 子 | `~/Developer/amidst/data/engineering/contact_control_20261016_v1` | raw_data | 847.72 KiB | 11 | `b4c31a2bc424` | unknown | 主庫未追蹤的資料目錄 |
| `UNT-data--engineering--office_person_20261016_v1` 子 | `~/Developer/amidst/data/engineering/office_person_20261016_v1` | raw_data | 467.38 KiB | 5 | `56bf342472b0` | unknown | 主庫未追蹤的資料目錄 |
| `UNT-data--engineering--q1q5_linked_rgb_20261024_v1` 子 | `~/Developer/amidst/data/engineering/q1q5_linked_rgb_20261024_v1` | raw_data | 4.56 MiB | 4 | `7fcd2942842c` | unknown | 主庫未追蹤的資料目錄 |

## 驗證與重算

```bash
python3 scripts/artifact_ledger.py validate
# 在持有原件的機器上逐筆重算並比對（唯讀；只用 --only 驗證要動的項目）
python3 scripts/artifact_ledger.py verify --only ART-d133-proxies-v2-jpeg,ART-d133-proxies-v2-webp
```

台帳只描述 2026-11-09 當下狀態；原件之後若被修改，`verify` 會回報 MISMATCH。動手清理前請先對要動的項目跑 `verify`。
