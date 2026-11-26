# `local/` 大型資產盤點與分類規則（LOCAL Asset Policy）

Refs: #729、#733、#598、D384、D386、D387、D171。

## 1. 範圍與核心原則

本規則適用於 repo 根目錄下已被 `.gitignore` 的 `local/`（`local/data`、`local/evidence`、`local/archive`），以及以唯讀資料包形式提供的同結構目錄（例如 `neon-datapack-20261126`）。

- **嚴格唯讀**：盤點腳本 `scripts/inventory_local_assets.py` 只讀取檔案中繼資料、清單檔與 SHA-256，**絕不刪除、移動或修改 `local/` 內任何檔案**。
- **人工核准後由使用者執行刪除**：工具輸出的刪除建議一律以註解或檢視清單呈現；任何刪除都必須先經使用者在對話中明確核准，再由使用者於自己的終端機執行（依 `AGENTS.md` 與 D387）。
- **原始資產只列不刪**：所有原始 Blender 檔（`.blend`）、原始影片（`.mp4`/`.mov`/`.mkv`/`.avi`）、Ground Truth（`gt`、`gt_private`、`gt-boxes`、`ground_truth`）與校正檔（`calibration`）無論是否被文件引用，一律歸類為 `KEEP` 並標註「只列不刪」，**絕不列入可刪候選**。
- **不破壞來源與雜湊**：不改動既有凍結證據與 `MANIFEST.sha256`。

## 2. 引用反查來源與祖先前綴規則

盤點工具掃描 repo 內所有受追蹤文字檔（排除 `.git/`、`local/`、`node_modules/`、`.venv/`）與結構化設定，反查**所有 `local/<relpath>` 路徑**（不只限於 `data`／`evidence`／`archive`，亦涵蓋頂層項目如 `local/runtime`、`local/manifests`、`local/logs`、`local/.migration-d169`、`local/demo-pin.json` 等，以及 `$AMIDST_ARTIFACTS/...` 對應至 `local/evidence/...`）：<!-- local-ref-ignore -->

1. **全 repo 文字檔**：`docs/`（含 `docs/agents/`、`docs/operations/`、`docs/evaluation/` 等）、`configs/`、`scripts/`、`src/`、`frontend/`、`tests/` 與 repo 根目錄之 `.md`、`.py`、`.json`、`.mjs`、`.js`、`.ts`、`.sh`、`.yml`、`.yaml`、`.command`、`.ps1`、`.txt`、`.toml` 等。
2. **結構化設定檔**：
   - 8785 demo 依賴設定：`configs/demo_integration_local.json`、`configs/demo_dependencies_manifest_v1.json` 及（若存在）`local/demo-pin.json`。
   - 舊路徑對應表：`configs/local_path_map_v1.json`（含 `generation`：`CURRENT`、`CITED`、`OBSOLETE`）。
   - 重現包清單（#728）：`configs/reproduce/artifact_manifest_v1.json`。
3. **祖先／前綴傳遞規則（Ancestor/Prefix Propagation）**：
   - 只要任一處引用指向子路徑 `local/X/child/...`（例如 `local/runtime/live-main`），則該子路徑與其所有非區段祖先（例如 `local/runtime`）都會繼承該引用並歸類為 **`KEEP`**（`active_reference_count >= 1`）。<!-- local-ref-ignore -->
   - 單純的區段根目錄名稱（`local/data`、`local/evidence`、`local/archive`）不向上展開成整區保留，以免覆蓋未引用子項。
4. **GitHub issue／PR 與 open PR 分支反查（提交刪除清單前必做）**：
   - 僅掃描單一 checkout 無法看到只出現在 GitHub issue／PR 本文、留言或尚未合併之 open PR 分支上的引用。
   - **提交任何刪除清單給使用者之前，必須補跑外部引用反查**：加上 `--include-github --include-git-branches`（透過 `gh` 與 `git grep` 唯讀掃描），或以 `--github-refs-json <snapshot.json>` 匯入離線快照。
   - JSON 報告固定記錄 `external_ref_scan`（含 `github_issues_prs_scanned`、`open_pr_branches_scanned`、`warning`）；若未執行外部反查，Markdown 報告的頁首與刪除專節都會顯示顯著警示，提醒人工複核後才可刪除。

## 3. 分類規則

每個盤點項目會被歸類至下列三種主分類之一，並附加布林旗標 `is_obviously_stale_or_broken`（D387 專用節）：

### 3.1 `KEEP`（保留）

符合下列任一條件者一律歸為 `KEEP`：

1. **受保護原始資產（只列不刪）**：含 `.blend`、原始影片、GT／`gt_private`／`gt-boxes`、校正資料。
2. **重現包清單必要項目（#728）**：列於 `configs/reproduce/artifact_manifest_v1.json` 的 `local_path` 及其父目錄／子項目。
3. **8785 demo 依賴**：`local/data/demo-owned-v1`、`local/demo-pin.json` 及其明確鎖定的依賴項目（見 `configs/demo_dependencies_manifest_v1.json`，不適用單一雜湊）。
4. **E3／E5／E7 凍結證據與報告引用**：被非封存（non-archive）之 repo 文件、設定、程式或報告引用的 `local/...` 項目。

### 3.2 `DELETABLE_CANDIDATE`（可刪候選）

不屬受保護原始資產、且未被活躍（non-archive）來源引用，符合下列任一條件者歸為 `DELETABLE_CANDIDATE`：

1. **沒有任何引用**：反查不到任何 repo 文件、設定、程式、重現清單或 demo pin 引用。
2. **已被新版取代**：同系列已有更新版本（如 `-v1` 已有 `-v2`，或同前綴已有較新日期 `YYYYMMDD`）且舊版無活躍引用；或在 `configs/local_path_map_v1.json` 標記為 `OBSOLETE`。
3. **失敗或中止的執行**：空目錄、0 位元組壞檔，或名稱含明確失敗／中止／暫存標記（如 `failed`、`aborted`、`broken`、`corrupt`、`stale`、`tmp`）。
4. **重複副本**：SHA-256 或 `MANIFEST.sha256` 與另一份已標為 `KEEP` 的資產完全相同。
5. **可由腳本重建的暫存與快取**：如 `uv-cache`、`__pycache__`、`.pytest_cache`、`.DS_Store`、`*.tmp`、`*.part`、`*.bak`。

### 3.3 `明顯過期或錯誤`（`OBVIOUSLY_STALE_OR_BROKEN`，D387 獨立專節）

依 D387，Markdown 報告必須將「明顯過期或錯誤」獨立成節，優先呈現給使用者核准清理（例如為 #732 釋放渲染空間）。符合 `DELETABLE_CANDIDATE` 且滿足以下任一明確條件者，標記 `is_obviously_stale_or_broken: true`：

- 空目錄或 0 位元組檔案（`empty_or_zero_byte`）。
- 可重建快取或系統垃圾檔（`rebuildable_cache_or_temp`）。
- 失敗／中止／損毀／明確過期標記（`failed_aborted_or_stale_marker`）。
- `configs/local_path_map_v1.json` 標為 `OBSOLETE` 且無活躍引用（`local_path_map_obsolete`）。
- 已被同系列新版取代且無活躍引用（`superseded_by_newer_version`）。

此專節逐項列出：**路徑、大小、檔數、判斷理由、引用反查結果**，並在文末附上以 `#` 註解的「供使用者於自己終端機核對執行的刪除指令參考」，工具絕不自動執行。

### 3.4 `UNCERTAIN`（不確定）

不符合 `KEEP` 且不適合直接列為可刪候選者，一律歸為 `UNCERTAIN` 並附理由交由人工判斷：

- 僅被 `docs/archive/` 封存文件引用（`referenced_only_in_archive_docs`）。
- 在 `configs/local_path_map_v1.json` 標為 `CITED` 或 `CURRENT`，但現行檔案未反查到直接 `local/...` 引用（`path_map_cited_without_direct_ref`）。
- 位於 `local/archive/` 且無法確認是否仍具對照價值（`archive_item_requires_human_review`）。
- 符號連結（symlink）或權限異常項目（`symlink_or_unreadable`）。

## 4. 使用方式

```bash
# 在 Mac / Linux 盤點 repo 內的 local/（輸出寫到 repo 外或 scratch，勿直接進 git）
# 提交刪除清單給使用者前，務必加上 --include-github --include-git-branches
python3 scripts/inventory_local_assets.py \
  --repo . \
  --local-root ./local \
  --include-github \
  --include-git-branches \
  --json-out /path/to/scratch/local_inventory.json \
  --md-out /path/to/scratch/local_inventory.md
```

Windows 以唯讀資料包試跑（不改動資料包）：

```powershell
python scripts/inventory_local_assets.py `
  --repo . `
  --local-root "C:\path\to\neon-datapack-20261126" `
  --json-out "C:\path\to\scratch\datapack_inventory.json" `
  --md-out "C:\path\to\scratch\datapack_inventory.md"
```

## 5. 與 #728 重現包及 #598 的銜接

- 盤點確認為 `KEEP` 且屬實驗重現必要資產者，登記進 `configs/reproduce/artifact_manifest_v1.json`（#728）。
- #598 的 `local/` 盤點步驟改用本工具產出報告，不再以人工零散估算。
