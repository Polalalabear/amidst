# Linux／macOS 重現包操作手冊（Reproduce Pack Guide）

Refs: #728、#733、#598、D380、D384、D386、D387。

> **私人使用邊界（D380／D384）**：雲端硬碟目前僅供專案使用者本人使用，不公開、不分享連結。本 repo、清單與腳本皆**不包含任何雲端連結、帳密或 API key**；含 GT 衍生資料（如 `expected`、答案表）僅供評分端使用，絕不進 Git，決策器／推論程式亦不得讀取。
>
> **清單狀態**：`configs/reproduce/artifact_manifest_v1.json` 目前標為 `DRAFT_PENDING_732`，待 #732（FEAT-EXP-RUN）完成後補入新證據並定稿。

---

## 1. 環境建立（Linux／macOS）

### 1.1 必備工具與版本

- **Git**（建議 2.39+）
- **Python**：依 repo 根目錄 `.python-version` 為 **`3.12`**（macOS 自有 runtime 鎖定為 `3.12.12`，見 `docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md`）
- **uv**：套件鎖定管理（`uv.lock`）
- **Node.js**：僅在執行前端／clean-clone 測試時需要，版本依 `.node-version`（`26.0.0`）

### 1.2 從 GitHub 建立乾淨 clone 並同步環境

```bash
git clone https://github.com/Polalalabear/amidst.git
cd amidst

# 使用 uv 依鎖定檔建立 .venv
uv sync --frozen --all-groups --python "$(tr -d '[:space:]' < .python-version)"

# 檢查乾淨 clone 與符號連結狀態
.venv/bin/python scripts/reproduce/check_symlinks.py --repo .
```

---

## 2. 從私人雲端硬碟下載並核對 `local/` 資產

1. 由使用者本人從私人雲端硬碟下載對應資料包至本機暫存資料夾（例如 `~/Downloads/amidst-repro-download`），保持 `configs/reproduce/artifact_manifest_v1.json` 內各 `local_path` 的目錄結構（可帶或不帶最外層 `local/`）。
2. 先以 `--dry-run` 檢查來源檔案是否齊全且 SHA-256 正確（不會寫入 repo）：

```bash
.venv/bin/python scripts/reproduce/fetch_and_verify.py \
  --repo . \
  --source-dir ~/Downloads/amidst-repro-download \
  --dry-run
```

3. 確認全部 `[OK]` 後，複製至 `<repo>/local/` 並逐項核對 SHA-256（**任何缺檔或雜湊不符會立即停止並回傳非零結束碼**）：

```bash
.venv/bin/python scripts/reproduce/fetch_and_verify.py \
  --repo . \
  --source-dir ~/Downloads/amidst-repro-download
```

4. 若檔案已放置於 `local/`（或欲對唯讀資料包原位核對），使用 `--verify-only`（加 `--deep` 會連同 `MANIFEST.sha256` 內列出的每個檔案逐一驗 hash）：

```bash
.venv/bin/python scripts/reproduce/fetch_and_verify.py \
  --repo . \
  --verify-only \
  --deep
```

---

## 3. 重算並核對 E5 實驗數字（離線，不呼叫付費 API）

以下指令**僅讀取已凍結的 E3／E5 執行紀錄與評分器**，不呼叫任何付費 API。重算產生的 `report.json` 與 `report-skeleton.md` 應寫到 `local/` 外的暫存目錄，勿覆寫凍結證據。

```bash
OUT_DIR=/tmp/e5-reproduce-check   # local-ref-ignore
mkdir -p "$OUT_DIR"

.venv/bin/python -B scripts/evaluation/e5_score.py \
  --scorer local/evidence/e3-652-20261122/e3_scoring.acacce39.py \
  --source local/evidence/e3-652-20261122 \
           local/evidence/e3-652-20261122/CORPUS.json \
           local/evidence/e3-652-20261122/runs-final-9 \
  --source local/evidence/e3-reappearances-20261122 \
           local/evidence/e3-reappearances-20261122/CORPUS.json \
           local/evidence/e3-reappearances-20261122/runs-final-665 \
  --source local/evidence/e3-652-20261122 \
           local/evidence/e3-652-20261122/CORPUS.json \
           local/evidence/e5-20261123/runs-9 \
  --source local/evidence/e3-reappearances-20261122 \
           local/evidence/e3-reappearances-20261122/CORPUS.json \
           local/evidence/e5-20261123/runs-665 \
  --out "$OUT_DIR/report.json" \
  --md "$OUT_DIR/report-skeleton.md"
```

### 必須完全一致的檢核數字（對照 `docs/evaluation/E5_NUMBERS_TABLE_20261124.md` 與 `docs/operations/E5_REPORT_20261123.md`）

| 組別 | 指標 | 預期數值 | JSON 路徑 |
| --- | --- | ---: | --- |
| **B1（E3 規則基線）** | 錯人秒（16 段合計） | **`114.0`**（表列 `114.00`） | `/per_arm/B1/wrong_person_s` |
| **AO（E5 離線，K=3）** | 錯人秒（16 段合計） | **`243.067`**（表列 `243.07`） | `/per_arm/AO/wrong_person_s` |
| **B1** | 跟對率／決策點對 | `0.7587`／`28/68` | `/per_arm/B1/follow_rate`、`/per_arm/B1/dp_correct` |
| **AO** | 跟對率／決策點對 | `0.6515`／`15/68` | `/per_arm/AO/follow_rate`、`/per_arm/AO/dp_correct` |

快速單行核對：

```bash
.venv/bin/python -c '
import json, sys
r = json.load(open(sys.argv[1]))
b1 = r["per_arm"]["B1"]["wrong_person_s"]
ao = r["per_arm"]["AO"]["wrong_person_s"]
assert abs(b1 - 114.0) < 1e-6, f"B1 mismatch: {b1}"
assert abs(ao - 243.067) < 1e-3, f"AO mismatch: {ao}"
print(f"E5 VERIFIED: B1 wrong_person_s={b1}, AO wrong_person_s={ao}")
' "$OUT_DIR/report.json"
```

---

## 4. 跨平台限制與已知風險

### 4.1 Linux 上 8785 Demo Runtime 限制（重要）

依 `docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md`：

- 現有自有依賴包（`local/data/demo-owned-v1`，不適用單一雜湊）內建的 Python runtime 為 **macOS `darwin-arm64`（CPython 3.12.12）**。
- **Linux 可以重現實驗評分、重算 E3／E5 數字與執行單元測試**（透過 `uv sync` 建立本機 Linux `.venv`），但**不能直接啟動 Mac `darwin-arm64` 的 `start_445_demo.command` 自有 runtime**；Linux 上執行 8785 demo 需另行建立原生 Linux runtime 並完成獨立平台驗收。

### 4.2 換行符號與 SHA-256（`.gitattributes`）

- 本 repo 已新增 `.gitattributes`，將 `.json`、`.jsonl`、`.csv`、`.sha256`、影像、影片、權重與壓縮檔設為 `-text`，避免跨平台 `core.autocrlf` 改動檔案 bytes 導致 SHA-256 核對失敗。
- Shell 腳本（`*.sh`、`*.command`）強制 `eol=lf`。

### 4.3 3 個 Git 符號連結的跨平台退路

本 repo 目前追蹤 3 個 Git 符號連結（mode `120000`）：

1. `docs/DEVELOPMENT_RULES.md` → `specs/DEVELOPMENT_RULES.md`
2. `docs/GEOMETRY_PROVIDER.md` → `specs/GEOMETRY_PROVIDER.md`
3. `docs/PHASE1_BENCHMARK_PROTOCOL.md` → `research/PHASE1_BENCHMARK_PROTOCOL.md`

- 在 Linux／macOS 上，Git 會直接建立標準符號連結。
- 在不支援符號連結的檔案系統或未啟用 `core.symlinks=true` 的環境（例如部分 Windows 設定），Git 會將上述 3 個檔案檢出為單行純文字指標檔。
- 請執行 `python scripts/reproduce/check_symlinks.py --repo .` 確認 3 個連結皆可解析；程式如需跨平台讀取這些文件，應呼叫 `scripts/reproduce/check_symlinks.py` 提供的 `resolve_tracked_symlink()`，不可直接覆寫或破壞 Unix 原生符號連結。

### 4.4 `local/` 長路徑風險（超過 200 字元）

- 實測 `local/` 內的相對路徑最長達 **205 字元**（已超過 200 字元門檻）。
- 在 Linux／macOS（上限通常為 4096 bytes）通常無礙，但若 clone 路徑過深，或在 Windows（傳統 `MAX_PATH = 260`）上解壓／複製資料包，極易觸發路徑過長錯誤。
- **建議**：
  - 將 repo 與下載暫存資料夾放在淺層目錄（例如 `/opt/amidst`、`~/amidst` 或 Windows `C:\amidst`）。
  - Windows 若需使用，請確認已啟用 `git config --system core.longpaths true` 與系統 LongPathsEnabled（Windows 是否正式納為重現平台待 #598 使用者決定）。
