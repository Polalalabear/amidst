# Amidst 磁碟安全稽核 — 2026-10-15（Asia/Taipei）

初次稽核完成後，使用者有條件核准清除3B模型與formal環境；兩項均已完成。最新結果見下方「核准後清理結果」，前段表格與空間值保留為初次稽核紀錄。沒有移除Worktree或正式研究證據。5GB目標未達。

GB 為十進位；下表 GiB 為 2^30 bytes。`du` 是配置量，APFS clone／hardlink／snapshot 不保證等量回收。各目錄分別量測，不能相加推算獨占容量；同次 du 遍歷會去重 hardlink，因此與初步值不同。

| Directory | Size | Git State | Unique Assets | Safe to Remove? | Recoverable Space |
| --- | ---: | --- | --- | --- | ---: |
| `.local-worktrees/phase1-finalization` | 8.005 GiB | codex/simulation-engineering / c6661dd；1 modified、2 untracked | 7B/3B models、live PG、ledger、review、工程資料、Python 環境 | KEEP：工作台/Ollama/PG 正在使用 | 整樹 0；3B 另列 REVIEW |
| `.local-worktrees/phase1-case23-formal` | 1.603 → 1.571 GiB | codex/phase1-case23-formal / 043bed2；tracked clean | 正式 frozen release 約603 MiB、重播/GT-poison/順序測試證據、人審約126 MiB；多數 ignored | KEEP：凍結原產物在此 | 整樹 0 |
| `.local-worktrees/phase1-case23-clean` | 0.417 GiB | detached c4a8a0a；9 untracked | clean 重現 release 約165 MiB、原始 receipt/lock/benchmark；多數 ignored | KEEP：必要重現證據及未提交檔 | 0 |
| `blender` | 1.307 GiB | canonical branch c5956dc；3個 ignored .blend | school_v2、school_v3、wall-marked 歷史場景 | KEEP：原始／獨有 Blender | 0 |
| `data` | 0.471 GiB | canonical；tracked、ignored 混合 | RGB、dataset/GT、校正、scene audit、歷史證據 | KEEP | 0 |
| `/Users/polalabear/Developer/amidst-claude` | 0.104 GiB | claude/office-demo-visualization / 70144ae；clean | Claude 專用 checkout | KEEP | 0 |
| `/Users/polalabear/.codex/worktrees` | 0.236 GiB | backend 400f42f / main f9b563f；均 clean | backend fixture/handoff、main demo checkout | KEEP：backend 有 Node processes，main 仍為 demo/reproduction 入口 | 0 |
| formal 的 `.mypy_cache`、`.pytest_cache`、`.ruff_cache` | 33.535 MiB | ignored、無 tracked files | 無；工具可重建快取 | SAFE：已刪除 | 35.16 MB 已清除 |
| finalization 的 `qwen2.5:3b-instruct` | 約1.930 GB | ignored model blobs/manifest | 可重新下載；與7B共用小型 layers | REVIEW：目前 provider pin7B，需批准後用 Ollama lifecycle 移除 | 約1.930 GB，未刪 |
| formal 的 `.venv` | 約0.745 GB | ignored；uv.lock/pyproject 保留 | 未見程序使用；套件為環境依賴 | REVIEW：刪後正式重跑需重新建環境 | 上限約0.745 GB，未刪 |
| formal / clean 的 Python bytecode | 約11 MiB | ignored | 尚未逐項排除 package/manifest 綁定 | UNKNOWN：保留 | 不計入 |

## 保留原因與現行使用情況

- **Claude 實際 cwd 是 canonical `/Users/polalabear/Developer/amidst`**（PID12656），不只是 `amidst-claude`。canonical 與 Claude 專用 checkout 均完整保留。backend checkout 亦有現存 Node 工作程序，保留其快取。
- finalization：工作台 PID97774/127.0.0.1:57597、Ollama PID97769/11437、PostgreSQL PID68475/55432。沒有停止／重啟服務。`/api/bootstrap` HTTP200；Ollama inventory 同時有7B與3B，`/api/ps` 當下無載入模型；不代表模型可以任意 rm。
- finalization 有 `docs/engineering/DEMO_V1.md` 修改、未追蹤 `scripts/start_local_demo.py`、`start-demo.command`，全部保留。
- 三個 Worktree 的 branch/SHA、tracked/untracked/ignored 已分別盤點；正式 tracked clean 仍含超過萬筆 ignored 檔案。formal/clean 的唯一性未做全量二進位去重，因此採 KEEP，沒有把缺乏唯一性證據當作刪除理由。
- `CURRENT_WORK_REPRODUCTION.md` 明列 formal、clean 兩棵樹的必要 release 與 finalization 退役前置條件；formal `.venv` 約710 MiB、正式資料約603 MiB、人審約126 MiB、快取等形成其主要用量。finalization 主要為模型約6.16 GiB、環境約775 MiB、PG約320 MiB與工程輸出。
- formal HEAD 由 `phase1/finalization-sprint`、`codex/phase1-case23-formal`、`phase1-scoped-case123-20261014` 本機 refs 保留；clean HEAD 是上述 refs 可達祖先。其他 checkout HEAD 也有本機 branch refs。未 fetch／push／切 branch；遠端追蹤 refs 僅是本機紀錄，沒有宣稱本輪遠端重新核對。

## Office Demo 依賴與驗證

`configs/office_demo_fixture_v1.json` 的 source/dataset/safe-input pins 對應 finalization 的 `data/engineering/local_run/blender_camera_v1/office/manifest.json` 與 `safe_inputs.json`，原 RGB/dataset 在 canonical `data/pilot/school_v3_multisite_20261005/office/`。兩個開發 checkout 的 fixture/文件均已查閱。

safe_inputs SHA256 已重算並匹配 fixture；校正仍在 safe_inputs 的兩個 camera records。100張RGB的檔案存在／大小匹配；dataset 存在。原 `school_v3.blend` 的468300506 bytes／mtime與來源manifest相符，依metadata-first限制，沒有重新讀取整份大型 Blender binary 計算hash。未重跑研究、render、推理或 Office MVP 功能測試，這些檢查不代表 demo 功能驗收。

刪前 `lsof` 未發現 formal/clean 的開啟檔案或 cwd；Codex 狀態未見該正式任務正在執行。三個快取無 tracked 科學資產、無 symlink、無 release manifest 綁定；檢查後才限定刪除此三個名稱。未清除 active 目錄或 `.venv` bytecode。

所有 checkout HEAD、完整 Git status、index SHA256 於刪除前後完全一致，refs 相同；`git fsck --connectivity-only --no-dangling` 成功。Git objects 未作全量內容重驗。

## 初次稽核時的後續動作與核准邊界（歷史）

已執行：只刪 formal 根目錄 `.mypy_cache`、`.pytest_cache`、`.ruff_cache`，配置空間共35164160 bytes。

可供核准的下一批（尚未執行）：

1. 重新核對服務與7B pins後，執行 `OLLAMA_HOST=http://127.0.0.1:11437 ollama rm qwen2.5:3b-instruct`；不直接刪共享 blobs，保留7B。約1.930 GB。
2. 再次確認 formal 無程序使用、鎖檔與來源套件皆可重建後，僅移除 `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-formal/.venv`。約0.745 GB；未來重跑須重新安裝依賴，本次不安裝。

這兩項合計**最多約2.675 GB**，若全部核准並實際釋放，預期可用空間約9.94 GB；只有3B則約9.20 GB。hardlink/APFS/系統寫入可能降低實際回收量，不能保證達到5 GB。

目前**沒有整份 Worktree 已確認可退役**，因此不建議核准移除任何一棵。未來必須先完成必要證據／runtime依賴保留及重新驗證，再取得明確核准，僅用 `git -C /Users/polalabear/Developer/amidst worktree remove <已核准的絕對路徑>`；不加 force，不執行 git clean/reset。移動必要資產本身不回收空間。

## 初次稽核空間結果（歷史）

稽核開始可用 7.276642 GB，結束量測 7.267283 GB；全磁碟淨變化 -9.36 MB。清除瞬間 available 增加35.12 MB，與35.16 MB快取配置量相符。期間其他程序寫入，因此不可將全程磁碟差額全歸因本次清理。

DISK_AUDIT: PASS
SAFE_CLEANUP_COMPLETED: YES
WORKTREE_REMOVAL_APPROVAL_REQUIRED: YES
SPACE_BEFORE: 7.276642 GB
SPACE_AFTER: 7.267283 GB
SPACE_RECOVERED: -0.009359 GB（全磁碟淨值；本次已刪快取 0.035164 GB）

稽核完成；5GB目標未達，不續作功能開發。


## 核准後清理結果 — 2026-10-15（本輪最新）

兩項均通過安全條件並依序完成。僅執行授權的模型生命週期移除與單一環境刪除，沒有移動資產、移除整份Worktree、變更程式、安裝依賴或執行推理／實驗。

| 順序 | 動作與分類 | 動作前可用 GB | 動作後可用 GB | 當步可用空間增量 GB |
| --- | --- | ---: | ---: | ---: |
| 1 | SAFE／COMPLETED：官方 `OLLAMA_HOST=http://127.0.0.1:11437 ollama rm qwen2.5:3b-instruct`，exit0 | 10.905235 | 12.835688 | 1.930453 |
| 2 | SAFE／COMPLETED：僅刪 `phase1-case23-formal/.venv` | 12.814152 | 12.839727 | 0.025575 |

**兩步瞬間可用空間增量合計 1.956028 GB。** 第二項配置量為744.94MB，但只增加25.58MB可用空間；APFS／硬連結／系統同期寫入會影響實際釋放量，沒有把配置量冒稱回收量。

本輪前置快照可用9.461887GB，第一次刪除前已變成10.905235GB；結束可用12.826747GB，全程淨變化3.364860GB。外部程序期間亦有顯著磁碟變動，故不能把全程淨變化全歸因本次清理。每步數值皆為現場`statvfs`量測。

### 3B前置條件與7B保護

- 工作台PID97774使用finalization的Python環境；Ollama PID97769、PG PID68475仍為既有服務。沒有重啟或停止。
- 重新讀取`phase2_abc/agent_provider.json`與`phase2_repair_0511/agent_provider_180.json`，均固定7B及digest`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`。transport profile只調timeout、不選另一模型；provider失敗為unavailable，沒有切3B；Office deterministic fallback adapter記錄model_calls0。已查三份相關checkout的src/configs，無3B fallback設定。
- 刪前`/api/ps`未載入3B；刪後`/api/tags`只剩7B。使用官方命令，未直接刪blobs。
- 7B manifest bytes/digest與config及4個layers的size/mtime/inode刪前後全部一致，共用blobs保留。`/api/show`HTTP200且model_info可讀；未作completion或品質驗收。

### formal環境可重建條件

- 刪前新鮮`lsof`全量開啟檔案檢查，無任何檔案或cwd位於該`.venv`；環境不是symlink且無tracked檔案。
- `pyproject.toml`／`uv.lock`均為原HEAD內容；`uv lock --check --offline --no-cache --project <formal>`成功，解析35packages，沒有安裝依賴。
- 34個已安裝distribution的版本全部在lock內，來源均為registry或保留的editable專案根。唯一direct_url指回formal專案原始碼，原始碼不在被刪範圍。
- RECORD覆蓋檔案與環境生成檔；6,493筆RECORD sizes、3,743筆小型程式／metadata hashes均相符。其餘未列入RECORD者為標準activate/deactivate腳本、uv環境檔及bytecode；無額外dataset、checkpoint、媒體或唯一實驗資料。19份大型套件binary只核對metadata，沒有全量讀取。
- Python3.12.12實體在`.local/share/uv/python/`，不在被刪目錄；現行finalization環境完整保留。未來可在formal執行`uv sync --locked --group dev`重建；需套件來源／快取可用，本次沒有實際重建或保證離線安裝。

### 完成後驗證

- Workbench`http://127.0.0.1:57597/api/bootstrap`HTTP200；Ollama tags及7B show均HTTP200。
- PostgreSQL透過既有`/private/tmp/amidst-pg-abc`socket、55432、amidst_local／amidst_abc執行唯讀`SELECT 1`回傳1。TCP最初被原pg_hba規則拒絕，沒有修改驗證規則。
- Office safe-input SHA匹配fixture；兩台camera calibration仍在；100張RGB檔存在且大小匹配；dataset與原Blender存在，Blender size/mtime未變。沒有讀GT內容或重算大型binary hash。
- 全部checkout的HEAD、status、index SHA刪前後一致；branch/tag/remote refs未變，`git fsck --connectivity-only --no-dangling`通過。Codex app自身內部`refs/codex/turn-diffs`隨本輪操作更新，不能宣稱所有內部refs不變；本次未執行修改refs的Git命令。
- formal data/human_review、canonical Blender及Office原資料共3,707個保護檔案的size/mtime/inode全相同。Claude與Codex checkout、formal/clean Worktree、正式研究證據均保留。
- 初次移除腳本將第二份provider設定誤定位於phase2_abc而在移除前中止；以檔案清單定位至phase2_repair_0511後重新完整核對才執行。uv初次sandbox檢查遇macOS system-configuration panic，改於受審環境執行同一唯讀離線檢查後通過。沒有強制略過安全條件。

| Directory | Size after | Git State | Unique Assets | Safe to Remove? | Actual recovered |
| --- | ---: | --- | --- | --- | ---: |
| phase1-finalization | 6.207GiB | HEAD/status/index原樣 | 7B/live PG/runtime/工程證據 | KEEP | 3B步驟 1.930453GB |
| phase1-case23-formal | 0.877GiB | 043bed2／tracked clean | formal frozen evidence、人審 | KEEP | venv步驟 0.025575GB |
| phase1-case23-clean | 0.417GiB | c4a8a0a／9 untracked原樣 | clean reproduction evidence | KEEP | 0 |

DISK_AUDIT: PASS
SAFE_CLEANUP_COMPLETED: YES
WORKTREE_REMOVAL_APPROVAL_REQUIRED: YES（未核准／未執行任何整樹移除）
SPACE_BEFORE: 10.905235 GB（第一個刪除動作前）
SPACE_AFTER: 12.826747 GB（完成驗證後）
SPACE_RECOVERED: 1.921511 GB（首個刪除前至最後量測的全磁碟淨差；兩步瞬間增量合計1.956028GB，差額含同期其他程序影響）

清理完成，5GB目標未達；沒有續作功能開發。
