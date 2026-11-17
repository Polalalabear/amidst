# 本機清理候選清單（D138，只列不執行）

- 依據：[ARTIFACT_LEDGER.md](ARTIFACT_LEDGER.md) 與 `configs/provenance/artifact_ledger_v1.json`（2026-11-09 狀態）；baseline `mainline/q1q5` @ `2616661`。
- **D163 更新（2026-11-09）**：證據已對 `e85b51e` 重驗、§6 驗證關卡已在 scratchpad clone 跑完，結果與最終刪除清單、封存後刪除腳本見 [CLEANUP_GATE_D163.md](CLEANUP_GATE_D163.md)；25 項 SAFE 全部維持、44 項 UNKNOWN 全部維持。**仍然沒有刪除任何東西**。
- **本文件與其 PR 不刪、不改、不搬任何東西**。所有指令都只是寫在文件裡，供使用者授權 #431 時使用；執行順序依 D138：驗收 A → 台帳 → 收進主線 → 刪除 → 分支（先打 archive tag 再刪）。
- 每個指令區塊前先跑 `verify`（檢查要動的項目與台帳記錄相同），沒有 MISMATCH 再動手；刪除一律用明確路徑，不用萬用字元，不用 `sudo`。
- 空間是逐檔 `st_size` 加總（十進位以外為 GiB／MiB 二進位）；APFS clone／snapshot 會讓實際釋放量不同，**UNKNOWN**。

## 0. 已經由 11-09 清除的項目（不再列入候選）

依使用者同意，Haiku 5.5 / low 已於 11-09 清除（紀錄：`coordinator-20261109/local-redundancy-audit.md` 的「清除紀錄」，LOCAL）：`~/.cache/uv`（1.9 GiB）、`~/.npm` 的一部分（240.9 MB）、`~/Library/Caches/pip`、`~/.cache/puppeteer`、phase1-finalization 的 `.venv`（780 MiB）與 `.mypy_cache`、amidst-claude 的 `.mypy_cache`。可用空間 7.3 → 9.7 GiB。

注意：D138 第一類「finalization 的 `.venv`：先把舊 Office launcher 改成用 repo lock 再刪」的前置條件**尚未做**就已刪除。`start-office-demo.command:7` 仍把 evidence repo 預設指向 `.local-worktrees/phase1-finalization`（evidence 而非 venv）；該 launcher 是否還需要那個 `.venv` 是 **UNKNOWN**。venv 可依 `uv.lock` 重建（約 0.8 GiB、需網路）。

## 1. SAFE 項目：不影響專案的證據與刪除指令（未執行）

D157：只有五項檢查**全部**通過的項目才標 SAFE；無法確認標 UNKNOWN，不能標 SAFE。檢查基準：`mainline/q1q5@2616661`、目前 tip `1026b84`（已含 #501、#502）、其餘 103 個 origin heads；open PR：#503（本 PR）、#490、#488。

### 1.1 五項檢查與實際結果

| 檢查 | 指令 | 結果 |
| --- | --- | --- |
| 1 引用（程式、tests、scripts、configs、CI、docs、README、`start_445_demo.command`） | `git grep -n -E "npm_config_cache" 2616661 -- .` | **0 筆** |
| 1 | `git grep -n -E "(\.npm\b\|npm_config_cache\|\.pytest_cache\|\.ruff_cache\|d133-playback\|amidst-p1-clean-room\|Developer/amidst/)" 2616661 -- .github start_445_demo.command README.md`（同指令對 `1026b84` 也跑） | **0 筆**（CI workflow `.github/ci.yml`、`ci-linux-deselect.txt`、`start_445_demo.command`、README 都沒有引用） |
| 1 | `git grep -n -E "\.pytest_cache\|\.ruff_cache" 2616661 -- . ":!docs/history"` | 只有 `.gitignore:3-4` 與 `docs/operations/q1q5_local_handoff_20261025/LOCAL_ARTIFACTS.json:364-365`（排除清單的文字），沒有任何程式讀取 |
| 1 | `git grep -n -E "\.npm" 2616661 -- . ":!docs/history"` | 3 筆，全是 `package-lock.json` 的 `registry.npmjs.org` URL（誤判，非 `~/.npm` 路徑） |
| 1（主庫副本） | `git grep -E -l "Developer/amidst/(configs\|docs\|scripts\|src\|tests\|frontend)" 2616661 -- . ":!docs/history"`（`1026b84` 同） | 只有 `data/reports/benchmark/mock_comparison/benchmark_summary.json`（歷史 fixture 路徑字串，不是這 20 個檔案）；`*.py *.mjs *.sh *.command *.yml` 中 `Developer/amidst` 的引用：0 筆 |
| 2 執行中的服務 | `lsof -nP -iTCP:8785 -sTCP:LISTEN`；`lsof -nP -p 21060` | 8785：PID 21060，cwd `~/amidst-demo-20261104`，載入 `~/amidst-artifacts/demo-owned-v1/runtime/python`；serve8785.log 在 scratchpad `1a05815b-…`（這些全部 **KEEP**，見 1.3） |
| 2 | `lsof -nP \| grep -cF -- "<候選路徑>"`（`.npm`、`.pytest_cache`、`.ruff_cache`、`/Developer/amidst/{docs,scripts,src,tests,configs,frontend}`） | 各 **0**；`lsof -nP \| grep " cwd " \| grep -F "/Developer/amidst"`（排除 amidst-claude、amidst-q1q5）：**0** 個行程 |
| 3 未合併的工作 | 上列 `git grep` 對 `origin/*` 全部 heads（104 個 revision，含 #490、#488、#503、codex/*、claude/*）逐一計數，與 `2616661` 比較 | `.npm`、`npm_config_cache`、cache 與主庫副本：**沒有任何 head 比主線多引用**（#503 自己的台帳文字除外）；`d133-playback-proxies` 有 19 個 heads 引用 → 該項標 KEEP |
| 4 證據保全 | 候選全部是快取或 byte 相同的副本；與研究紀錄 v3、量測 B、#479、#445、#93 引用的產物無交集（那些在 `amidst-artifacts`、`demo-owned-v1`，皆 KEEP） | pass |
| 5 原始資產 | 候選不含 Blender、影片、資料集、calibration、GT（`raw_data` 類型不可能是 SAFE，`validate` 強制） | pass |

各 head 的原始計數在 `scratchpad/grep_results.txt`（LOCAL，未進 repo）；結果會過期，執行前要重跑。

### 1.2 SAFE 清單（25 項，共 401.15 MiB）

| ID | 路徑 | 大小 | SHA-256（檔案）／manifest（目錄）；檔案數 | 還原方式 |
| --- | --- | ---: | --- | --- |
| `CACHE-npm` | `~/.npm` | 400.11 MiB | （快取，未算 SHA）；42095 檔 | 重新 npm ci（需網路）自動重建 |
| `LOC-fin-pytest_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.pytest_cache` | 431.10 KiB | （快取，未算 SHA）；5 檔 | 下次 pytest／ruff 執行時自動重建 |
| `LOC-fin-ruff_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.ruff_cache` | 85.75 KiB | （快取，未算 SHA）；43 檔 | 下次 pytest／ruff 執行時自動重建 |
| `LOC-main-pytest_cache` | `~/Developer/amidst/.pytest_cache` | 90.11 KiB | （快取，未算 SHA）；5 檔 | 下次 pytest／ruff 執行時自動重建 |
| `LOC-main-ruff_cache` | `~/Developer/amidst/.ruff_cache` | 15.74 KiB | （快取，未算 SHA）；54 檔 | 下次 pytest／ruff 執行時自動重建 |
| `UNT-configs--q1q5` | `~/Developer/amidst/configs/q1q5` | 353.17 KiB | `b6d12b87137424fb8fa6a365d3f3f8c2ac5aa190c18bf23cf63e70346ed32c1a`；11 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_BASELINE_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md` | 5.59 KiB | `e6a6de7f189195d95655f5602fbb7387c645de49c1479e47cce80a6cb1d1636d`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_BASELINE_DECISIONS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_DECISIONS.md` | 3.47 KiB | `27c8930dbb28fccce6cbd8ec96b7c8c3ae9d805bb109a2e4024a32cfabf534db`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_BASELINE_RUNNER.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_RUNNER.md` | 9.87 KiB | `e16daed41e3493e9448ab746962f397d5516c53d44f8957a85ff4a2bd902d18c`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_BASELINE_V1_PROTOCOL.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md` | 15.59 KiB | `31c49330a682021b242c07c2bd3f86b34b09195e8e16b7421f02a8f0266ec89d`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_LINKED_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md` | 6.72 KiB | `55330e00bb5be9ddcd7f77d0cdcc0ec5a06396c5a57b7d77b4ab917023448137`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_PRODUCTION_PREPARATION.md` | `~/Developer/amidst/docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md` | 3.01 KiB | `f5f1f1802f20af196cde6c49853a4c66e21cdd6407d1570174bbf430f72e745b`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--engineering--Q1Q5_REVIEWED_INPUTS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_REVIEWED_INPUTS.md` | 3.27 KiB | `b65e90df3395776183098bb1e29c4b370a0036d2df2ea39618f3fecc67bee9b0`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--evaluation` | `~/Developer/amidst/docs/evaluation` | 3.16 KiB | `89d316dea0214730529f6e878076346fd276162eac858d45f1e82c42fd6aee04`；2 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--history--Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | 4.14 KiB | `275a4e1101eb6cf015428bde416290a7b41b6c03ec2da3fa6b4fa837e10f15d4`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-docs--history--Q1Q5_LINKED_ACCEPTANCE_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json` | 5.81 KiB | `5826fb3dea4bb7f18a852d84b46d29771318f275576757f347ec38f4fc49c82d`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--accept_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/accept_q1q5_linked_baseline.py` | 1.33 KiB | `64aeeea9ab29848c71f4b1eb955f663f8ed70dcf39bb483678e40f56858b9a21`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--build_q1q5_pinned_index.py` | `~/Developer/amidst/scripts/build_q1q5_pinned_index.py` | 1.11 KiB | `41f465691d98a26712782b3d2c98ee3ca0ea6e94f06c9bf5fa7c2482cd7c28e2`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--import_q3_minimum_review.py` | `~/Developer/amidst/scripts/import_q3_minimum_review.py` | 2.75 KiB | `8ce5f1aa58f37067867e4d2eefe000382e50d5455b930e85d60ca40144f76253`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--measure_q1q5_dynamic_rgb.py` | `~/Developer/amidst/scripts/measure_q1q5_dynamic_rgb.py` | 3.21 KiB | `a3d5aa3b47afe48c14fc1d1d072fdf3008e9035180882693e1bd5c36748f3729`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--preflight_q1q5_production.py` | `~/Developer/amidst/scripts/preflight_q1q5_production.py` | 2.19 KiB | `b9329bac83d2f670cda70c909d0ba9457508f9472a1c02b812c40a3337415e1d`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--prepare_q1q5_baseline_source.py` | `~/Developer/amidst/scripts/prepare_q1q5_baseline_source.py` | 1.11 KiB | `eaa4074d9a41d7741fa19ab30dabe73bc24a75b88fe1f09add78afee94e743e9`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--replay_q1q5_dynamic_evidence.py` | `~/Developer/amidst/scripts/replay_q1q5_dynamic_evidence.py` | 4.25 KiB | `1b46a491188f5faadb72d0cc46c776afb085761b02cce16729a7fae7446dbf89`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-scripts--run_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/run_q1q5_linked_baseline.py` | 2.03 KiB | `8982ec819204dbeddfd1b6b4fd8916c09592b6b8b5d0d293711c563f3e7b8cf8`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |
| `UNT-src--amidst--evaluation--q3_review_import.py` | `~/Developer/amidst/src/amidst/evaluation/q3_review_import.py` | 9.53 KiB | `5db6c4d742a7997d493cc67cdf99c20b6db7f4558d175590d61289ced40603aa`；1 檔 | 可由 git 重建：git -C <repo> show mainline/q1q5:<path> |

每筆的 `safety.evidence`、`verify_commands`、`restore` 完整內容在台帳 JSON。

**指令（未執行；每一段前先 `verify`，不一致就中止）：**

```bash
npm cache clean --force   # CACHE-npm（也可 rm -r -- "$HOME/.npm"）
rm -r -- "$HOME/Developer/amidst/.pytest_cache" "$HOME/Developer/amidst/.ruff_cache"
rm -r -- "$HOME/Developer/amidst/.local-worktrees/phase1-finalization/.pytest_cache" "$HOME/Developer/amidst/.local-worktrees/phase1-finalization/.ruff_cache"
```

主庫未追蹤、與 mainline 相同的 20 筆（先 verify，再逐項比對 blob，不一致就中止）：

```bash
REPO="$HOME/Developer/amidst-q1q5"   # 含 scripts/artifact_ledger.py 的 mainline checkout
python3 "$REPO/scripts/artifact_ledger.py" verify --ledger "$REPO/configs/provenance/artifact_ledger_v1.json" --only UNT-configs--q1q5,UNT-docs--engineering--Q1Q5_BASELINE_ACCEPTANCE.md,UNT-docs--engineering--Q1Q5_BASELINE_DECISIONS.md,UNT-docs--engineering--Q1Q5_BASELINE_RUNNER.md,UNT-docs--engineering--Q1Q5_BASELINE_V1_PROTOCOL.md,UNT-docs--engineering--Q1Q5_LINKED_ACCEPTANCE.md,UNT-docs--engineering--Q1Q5_PRODUCTION_PREPARATION.md,UNT-docs--engineering--Q1Q5_REVIEWED_INPUTS.md,UNT-docs--evaluation,UNT-docs--history--Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json,UNT-docs--history--Q1Q5_LINKED_ACCEPTANCE_20261024.json,UNT-scripts--accept_q1q5_linked_baseline.py,UNT-scripts--build_q1q5_pinned_index.py,UNT-scripts--import_q3_minimum_review.py,UNT-scripts--measure_q1q5_dynamic_rgb.py,UNT-scripts--preflight_q1q5_production.py,UNT-scripts--prepare_q1q5_baseline_source.py,UNT-scripts--replay_q1q5_dynamic_evidence.py,UNT-scripts--run_q1q5_linked_baseline.py,UNT-src--amidst--evaluation--q3_review_import.py
cd "$HOME/Developer/amidst"
check() { find "$1" -type f ! -name .DS_Store | while IFS= read -r f; do [ "$(git hash-object -- "$f")" = "$(git -C "$REPO" rev-parse "mainline/q1q5:$f" 2>/dev/null)" ] || { echo "DIFFERS: $f"; exit 1; }; done; }
check "configs/q1q5" && rm -r -- "configs/q1q5"
check "docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md" && rm -- "docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md"
check "docs/engineering/Q1Q5_BASELINE_DECISIONS.md" && rm -- "docs/engineering/Q1Q5_BASELINE_DECISIONS.md"
check "docs/engineering/Q1Q5_BASELINE_RUNNER.md" && rm -- "docs/engineering/Q1Q5_BASELINE_RUNNER.md"
check "docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md" && rm -- "docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md"
check "docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md" && rm -- "docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md"
check "docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md" && rm -- "docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md"
check "docs/engineering/Q1Q5_REVIEWED_INPUTS.md" && rm -- "docs/engineering/Q1Q5_REVIEWED_INPUTS.md"
check "docs/evaluation" && rm -r -- "docs/evaluation"
check "docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json" && rm -- "docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json"
check "docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json" && rm -- "docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json"
check "scripts/accept_q1q5_linked_baseline.py" && rm -- "scripts/accept_q1q5_linked_baseline.py"
check "scripts/build_q1q5_pinned_index.py" && rm -- "scripts/build_q1q5_pinned_index.py"
check "scripts/import_q3_minimum_review.py" && rm -- "scripts/import_q3_minimum_review.py"
check "scripts/measure_q1q5_dynamic_rgb.py" && rm -- "scripts/measure_q1q5_dynamic_rgb.py"
check "scripts/preflight_q1q5_production.py" && rm -- "scripts/preflight_q1q5_production.py"
check "scripts/prepare_q1q5_baseline_source.py" && rm -- "scripts/prepare_q1q5_baseline_source.py"
check "scripts/replay_q1q5_dynamic_evidence.py" && rm -- "scripts/replay_q1q5_dynamic_evidence.py"
check "scripts/run_q1q5_linked_baseline.py" && rm -- "scripts/run_q1q5_linked_baseline.py"
check "src/amidst/evaluation/q3_review_import.py" && rm -- "src/amidst/evaluation/q3_review_import.py"
```

### 1.3 明確標 KEEP／UNKNOWN 的項目（D157 第 2–6 點）

| 項目 | 狀態 | 原因（證據） |
| --- | --- | --- |
| `ART-d133-proxies-v2-jpeg` | KEEP | 主線文件把整個 d133-playback-proxies-v2 當 benchmark 輸入：docs/engineering/D133_PLAYBACK_PROXY_MEASUREMENT_20261108.md:65、:69、:84 與 d133_playback_latency_20261108.json:2176；刪掉 jpeg/webp 會讓量測無法重現 |
| `ART-d133-proxies-v2-webp` | KEEP | 主線文件把整個 d133-playback-proxies-v2 當 benchmark 輸入：docs/engineering/D133_PLAYBACK_PROXY_MEASUREMENT_20261108.md:65、:69、:84 與 d133_playback_latency_20261108.json:2176；刪掉 jpeg/webp 會讓量測無法重現 |
| `ART-demo-owned-v1` | KEEP | 8785 服務（PID 21060）執行中：cwd ~/amidst-demo-20261104，載入 ~/amidst-artifacts/demo-owned-v1/runtime/python 的 python3.12；runtime、venv、資料與 config 一律 KEEP |
| `CO-demo` | KEEP | 8785 服務（PID 21060）執行中：cwd ~/amidst-demo-20261104，載入 ~/amidst-artifacts/demo-owned-v1/runtime/python 的 python3.12；runtime、venv、資料與 config 一律 KEEP |
| `ENV-demo-venv` | KEEP | 8785 服務（PID 21060）執行中：cwd ~/amidst-demo-20261104，載入 ~/amidst-artifacts/demo-owned-v1/runtime/python 的 python3.12；runtime、venv、資料與 config 一律 KEEP |
| `LOC-shared-cleanroom` | KEEP | 主線 runbook 仍以此路徑為 P1_BUNDLE：docs/operations/DEMO_RUNBOOK_20261104.md:26、:52、:60；EVENT_NAMES.md:9；COORDINATOR_HANDOFF_20261026.md:80；DEMO_OWNED_DEPENDENCIES_20261108.md:33。可封存（壓縮副本），不可刪原件 |
| `SCR-claude-scratch-root` | KEEP | 8785 的 log（serve8785.log）在 /private/tmp/claude-501/.../1a05815b-.../scratchpad；PID 34710 正在使用 0f3ae16a-... 的 venv 與 clone；其他 session 仍在寫入。不可整批刪 |
| `UNT-docs--history--storage_cleanup_20261014` | KEEP | 主線文件稱此目錄「原位保留」：data/README.md:10、docs/operations/PHASE1_ARTIFACT_CLEANUP.md:9、docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md:225；只可壓縮副本，不可刪原件 |
| `ENV-d139-venv`、所有 `CO-*`、`REF-*` | KEEP | Codex 的 D147/D149 分支與各 checkout 使用中；分支一律不刪（D157） |
| `ART-*`（除上列）、`LOC-main-blender`、`LOC-main-data`、worktree `data/`、人審與正式 release | KEEP | Blender、資料集、calibration、GT、原 run、驗收證據；不列入候選；`gt_private` 完全未開啟 |
| 其餘 44 筆（review pack、小型規劃交接、bytes 不同的未追蹤檔、Codex 資料等） | UNKNOWN | 使用狀態無法確認；不能標 SAFE，需使用者決定 |

已被 11-09 清除、不再列入的項目見第 0 節。D133 的 `jpeg/`、`webp/`（約 164 MiB）在前一版清單中是「可刪除」，這次因為 D133 量測文件的重現命令引用（`D133_PLAYBACK_PROXY_MEASUREMENT_20261108.md:65,69,84`）改為 **KEEP／需使用者決定**；`/Users/Shared` clean-room 與 `storage_cleanup_20261014/` 因主線 runbook／README 引用，只可壓縮副本、不可刪原件。

## 2. `~/Developer/amidst` 的本機分支：哪些有價值、要先 push 備份

背景說的「25 個遠端沒有的本機分支」來自盤點時該庫自己的 remote-tracking refs，而那些 refs 是**過期**的（GitHub 上已刪 187 個遠端分支，見 `deleted_branches_20261108.tsv`）。本 PR 把 25 個與其餘本機分支的 tip 抓進精簡 clone，用目前 GitHub 的 `origin` 重算：

- 本機分支共 **163** 個；其中 **32** 個同名遠端仍存在，且本機 tip 都已包含在遠端同名分支（沒有未推送提交）。
- **131** 個本機分支名稱在 GitHub 已不存在。其中 **125** 個 tip 仍被至少一個現存遠端分支包含（多數是 `mainline/q1q5` 的祖先，也有 `codex/feat-4-complex` 等）；`phase2/integration-foundation` 只被一個現存遠端分支包含；**只有 6 個 tip 不被任何現存 GitHub 分支包含**，這 6 個刪了就真的沒了。
- 上述與 Codex 11-08 的結論一致：27 個追蹤已刪遠端分支的本機分支中 26 個全部提交已在記錄的刪除 tip，只有 `codex/controlled-scene-real-v2-2a`（`60fa8ef`）多一個提交。

### 2.1 必須先備份的 6 個分支

| 分支 | tip | 獨有提交 | 相對 mainline 變更 | 價值判斷 | 建議 |
| --- | --- | ---: | --- | --- | --- |
| `codex/controlled-scene-real-v2-2a` | `60fa8ef649` | 1 | 1 檔 +287 行 | **高**：`Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`，已被其他文件引用（:215／:217）；GitHub 找不到此 SHA（422） | 先 push 備份，再把該文件收進 `docs/history/`（見第 5 節） |
| `phase1/physical-policy-approval` | `c5956dc825` | 1 | 53 檔 +24,053／−57 | 中：phase1 物理政策與 known collider scopes 核准（10-06）；是否已被後續 finalization 取代 **UNKNOWN** | push 備份（archive 命名空間） |
| `phase1/pilot-robustness-validation` | `ce2974b25b` | 1 | 14 檔 +3,194／−11 | 中：controlled pilot robustness scenarios | push 備份 |
| `phase1/projection-conditioning-mitigation` | `5f020b075d` | 4 | 34 檔 +10,684／−11 | 中：projection conditioning mitigation 比較 | push 備份 |
| `phase1/projection-model-upgrade` | `8f4055ffcd` | 5 | 42 檔 +13,785／−11 | 中：additive projection model 比較 | push 備份 |
| `phase1/projection-sensitivity` | `b90e81adb3` | 3 | 24 檔 +7,080／−11 | 中：projection precision evidence scope | push 備份 |

獨有提交數是「不在任何現存遠端分支內」的數量，四條 phase1 分支彼此共用部分祖先，所以總和大於實際唯一提交。六個分支的提交內容都是文字（程式、文件、JSON），沒有 Blender／影像。

**備份指令（outward-facing，需使用者明確授權後才執行）：**

```bash
cd "$HOME/Developer/amidst"
git push origin 60fa8ef64988435530b09fb258d79130e83977af:refs/heads/archive/codex--controlled-scene-real-v2-2a
git push origin c5956dc825f669e28e2694578be0fed97432a786:refs/heads/archive/phase1--physical-policy-approval
git push origin ce2974b25b31a8cb0ec9bc579a84d708d3356bf7:refs/heads/archive/phase1--pilot-robustness-validation
git push origin 5f020b075d4a670f60007eab7baeb12055f2f5d9:refs/heads/archive/phase1--projection-conditioning-mitigation
git push origin 8f4055ffcdc3bf6efd723c7956ac685e1fe033f1:refs/heads/archive/phase1--projection-model-upgrade
git push origin b90e81adb3acc1a0c1e599d488f3113f0842cfb4:refs/heads/archive/phase1--projection-sensitivity
```

也可以改成不上網的備份（不需任何遠端授權），之後再決定是否 push：

```bash
cd "$HOME/Developer/amidst"
mkdir -p "$HOME/amidst-artifacts/_archive_d138"
git bundle create "$HOME/amidst-artifacts/_archive_d138/unpushed_branches_20261109.bundle" \
  refs/heads/codex/controlled-scene-real-v2-2a refs/heads/phase1/physical-policy-approval refs/heads/phase1/pilot-robustness-validation \
  refs/heads/phase1/projection-conditioning-mitigation refs/heads/phase1/projection-model-upgrade refs/heads/phase1/projection-sensitivity
git bundle verify "$HOME/amidst-artifacts/_archive_d138/unpushed_branches_20261109.bundle"
```

### 2.2 其餘 157 個本機分支

- 32 個同名遠端仍在、無未推送提交：可在 `git fetch --prune origin` 後依 D138 第二、三類處理（先打 archive tag 再刪）。
- 125 個 tip 已在現存遠端：刪本機分支不會遺失提交。建議刪除前跑下列檢查，只列出「沒有任何現存遠端包含」的分支，輸出應只有上表 6 個：

```bash
cd "$HOME/Developer/amidst"
git fetch --prune origin
for b in $(git for-each-ref refs/heads --format='%(refname:short)'); do
  [ -z "$(git branch -r --contains "$b" | grep -v HEAD)" ] && echo "UNBACKED: $b"
done
```

- `phase2/integration-foundation`（`e4e5afc`，10-02，27 檔 +3,463）只被一個現存遠端分支包含，不在 mainline；刪除前確認那個遠端分支不會被刪。
- 分支整理仍依既定規則：使用者通知才做，不刪、不動分支。這份清單**不是**刪除授權。

## 3. `~/Developer/amidst` 主庫的 50 筆未提交變更（49 筆未追蹤＋1 筆 `docs/README.md` 修改）

比較對象是 `mainline/q1q5` @ `2616661` 的同路徑 blob（`git hash-object` vs `git ls-tree`）。這與 Codex 11-08 對 `796cc17` 的比較同一方法，但 baseline 不同，數字略有差異。

| 項目 | 展開檔數 | 比較結果 | 建議處置 |
| --- | ---: | --- | --- |
| `Google_Drive_Q3_20261020` | 5 | 未比對（raw 邊界） | 保留（raw／人審，只記錄） |
| `configs/q1q5` | 11 | 相同 11／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `data/engineering/contact_control_20261016_v1` | 11 | 未比對（raw 邊界） | 保留（raw／人審，只記錄） |
| `data/engineering/office_person_20261016_v1` | 5 | 未比對（raw 邊界） | 保留（raw／人審，只記錄） |
| `data/engineering/q1q5_linked_rgb_20261024_v1` | 4 | 未比對（raw 邊界） | 保留（raw／人審，只記錄） |
| `docs/README.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/FINALIZATION_DECOUPLING_PLAN_20261020.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_BASELINE_DECISIONS.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_BASELINE_RUNNER.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_DYNAMIC_BASELINE.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_DYNAMIC_BASELINE_RESULTS.json` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_LINKED_RUNTIME.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_PARAMETER_PROPOSAL.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_PLAYBACK_CONTINUITY.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q1Q5_REVIEWED_INPUTS.md` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/engineering/Q5_STATECHART.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/engineering/Q5_STATECHART_STAGE1_REVIEW.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/engineering/Q5_STATECHART_STAGE2_EVIDENCE.json` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/engineering/Q5_STATECHART_STAGE2_RESULTS.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/evaluation` | 2 | 相同 2／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/history/DISK_AUDIT_20261015.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `docs/history/Q1Q5_PLAYBACK_ACCEPTANCE_20261024.json` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `docs/history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/history/disk_cleanup_receipt_20261015.json` | 1 | 相同 0／不同 0／無同路徑 1 | 收進主線（逐檔審查後） |
| `docs/history/storage_cleanup_20261014` | 379 | 相同 0／不同 0／無同路徑 379 | 壓縮封存，不進 repo |
| `frontend/workbench-v2` | 12 | 相同 1／不同 11／無同路徑 0 | 需使用者決定：看 diff |
| `scripts/accept_q1q5_linked_baseline.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/build_q1q5_detection_index.py` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `scripts/build_q1q5_pinned_index.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/import_q3_minimum_review.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/measure_q1q5_dynamic_rgb.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/preflight_q1q5_production.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/prepare_q1q5_baseline_source.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/prepare_q1q5_synthetic_registry.py` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `scripts/render_q1q5_dynamic_rgb.py` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `scripts/replay_q1q5_dynamic_evidence.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/run_q1q5_baseline.py` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `scripts/run_q1q5_linked_baseline.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `scripts/serve_q1q5_linked_workbench.py` | 1 | 相同 0／不同 1／無同路徑 0 | 需使用者決定：看 diff |
| `src/amidst/evaluation/q3_review_import.py` | 1 | 相同 1／不同 0／無同路徑 0 | 可刪除（與 mainline 完全相同） |
| `src/amidst/q1q5` | 17 | 相同 8／不同 9／無同路徑 0 | 需使用者決定：看 diff |
| `tests/q1q5` | 24 | 相同 13／不同 7／無同路徑 4 | 需使用者決定：看 diff |

合計（有比較者）：相同 **53**、bytes 不同 **41**、mainline 無同路徑 **391**。

處置原則：

1. **相同**：重複副本，可刪（第 1 節）。
2. **bytes 不同**（`frontend/workbench-v2/`、`src/amidst/q1q5/`、`tests/q1q5/`、`scripts/` 的 4 個、docs 的 7+1 個）：mainline 在 10-24 之後由 #485 等 PR 大幅改過，這些多半是舊版；但**語意是否已被取代為 UNKNOWN**，不能不看 diff 就丟。建議做法：先用 `git diff --no-index` 把 41 檔的差異存成一份 patch 放到 `~/amidst-artifacts/_archive_d138/`，之後即使刪除也能還原；不建議進 mainline。
3. **mainline 無同路徑**的 12 個文件／測試（`Q5_STATECHART*.md`、`SCENE_Q1_Q2_PLAN_20261020.md`、`docs/history/` 3 個、`tests/q1q5/q5_*`／`test_q5_*` 4 個）：收進主線候選，見第 5 節。
4. `docs/history/storage_cleanup_20261014/`（379 份，13.1 MB；Codex 11-08 記 384，差異未查）：10-14 儲存清理的歷史保存，建議壓縮封存、在 `docs/history/` 只留一份索引，不整包進 repo。
5. `Google_Drive_Q3_20261020/` 與 `data/engineering/` 三個目錄：raw／人審資料，**不比對、不刪**；可能沒有別處備份，只在台帳記 SHA。
6. `docs/README.md` 的 2 行 discussion link：指向 `60fa8ef` 的文件，與該文件一起處理。

## 4. 封存建議：壓縮哪些、放哪裡

建議的封存根目錄：`~/amidst-artifacts/_archive_d138/`（與現有 LOCAL 盤點同一根；若使用者有外接碟，整個資料夾可再搬過去）。**壓縮不是刪除**；原件在使用者確認壓縮檔 `verify`／解壓比對無誤、且授權後才可以考慮刪。

| 項目 | 原大小 | 建議 | 指令（未執行） |
| --- | ---: | --- | --- |
| `/Users/Shared/amidst-p1-clean-room-20261026` | 285.16 MiB | 壓成 `p1-clean-room-20261026.tar.gz`；最終測試 398 檔已複製到 demo-owned-v1，剩餘「工程測試」是否為交付物 UNKNOWN，所以先封存不刪 | `tar -C /Users/Shared -czf "$HOME/amidst-artifacts/_archive_d138/p1-clean-room-20261026.tar.gz" amidst-p1-clean-room-20261026` |
| `docs/history/storage_cleanup_20261014/`（主庫未追蹤） | 12.49 MiB | 壓縮；repo 只留索引 | `tar -C "$HOME/Developer/amidst/docs/history" -czf "$HOME/amidst-artifacts/_archive_d138/storage_cleanup_20261014.tar.gz" storage_cleanup_20261014` |
| 主庫 41 檔 bytes 不同（含 docs/README.md）的未追蹤檔 | 小 | 存成一份 patch／tar | 見第 3 節第 2 點 |
| 6 個無備份分支 | 小 | `git bundle`（第 2 節） | 見第 2 節 |
| phase1-finalization 的 3 個未提交項目（`DEMO_V1.md` 14 行、`scripts/start_local_demo.py` 13,074 B、`start-demo.command` 325 B） | 小 | 一份含新增檔的 tar／patch（單純 `git diff` 不含 untracked，tag 不保存 dirty） | `tar -C "$HOME/Developer/amidst/.local-worktrees/phase1-finalization" -czf "$HOME/amidst-artifacts/_archive_d138/finalization_uncommitted_20261109.tar.gz" scripts/start_local_demo.py start-demo.command docs/engineering/DEMO_V1.md` ＋ `git diff` 另存 |
| `r004-cx7-d115-20261102-01a199f8`（D115 原 run，`gt_private` 另佔約 1.0 GiB） | 約 2.1 GiB | **不建議壓縮後刪**；D124 不是 byte 等價替代品。若要省空間，整個資料夾搬到外接碟並保留台帳 SHA | 使用者決定 |
| `q1q5-dynamic-baseline-v1_20261025`、各 `q1q5-*` 驗收／重播證據、Qwen 診斷 | 約 1.3 GiB | 保留原件；有外接碟時可整批搬移，台帳 manifest 供搬移後比對 | 使用者決定 |
| 三個 worktree 的正式驗收 release（`reviewed_run_case123_{formal,clean}_v2_20261014`） | 約 0.9 GiB | 保留原件；patch／tag 不能保存全部 ignored 產物 | — |

## 5. 應收進主線、目前還在 repo 外的項目（不含 GT；本 PR 不搬）

| 項目 | 現在位置 | 建議放哪 | 備註 |
| --- | --- | --- | --- |
| `60fa8ef` 的 287 行 demo 討論文件 | 本機分支 `codex/controlled-scene-real-v2-2a`（未推送） | `docs/history/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`（維持原檔名，已被別處引用） | 先 push 備份分支；收進主線時保留原 SHA 在文件頭 |
| 12 個 mainline 無同路徑的文件／測試 | `~/Developer/amidst` 未追蹤 | `docs/engineering/Q5_STATECHART*.md`、`SCENE_Q1_Q2_PLAN_20261020.md` → `docs/engineering/`；`DISK_AUDIT_20261015.md`、`WORKTREE_RETIREMENT_ASSESSMENT_20261020.md`、`disk_cleanup_receipt_20261015.json` → `docs/history/`；`tests/q1q5/q5_*`、`test_q5_*` 4 檔 → `tests/q1q5/`（先確認它們對目前 mainline 能跑，否則只收文件） | 測試能否通過 **未驗證** |
| finalization 的 3 個未提交項目 | worktree `phase1-finalization` | 建議**不進 mainline**：封存成 patch（第 4 節）並在 `docs/history/` 記一行。理由：它們是舊 PG／Ollama launcher；新 `start_445_demo.command` 是不同 demo 的啟動器，是否等價 UNKNOWN | 需使用者判斷「還需要嗎」 |
| demo-owned-v1 的小型 metadata 與 provenance（約 12 檔／1.6 MB：`metadata/cross-camera-job.json`、`metadata/graphs/camera_graph_v3_1.json`、`metadata/config/*.json`、`provenance/model-source-hashes.json`、`copy-manifest.json`） | `~/amidst-artifacts/demo-owned-v1/` | `configs/demo_owned/`（與 `configs/demo_dependencies_manifest_v1.json` 並列）；raw RGB、模型、runtime 不進 repo | 屬 Codex 的 #486 範圍；已有 manifest 的檔案不重複。SHA 已在本台帳 |
| `evidence/486/EVIDENCE_MANIFEST.json`、`evidence/491-lock-sync/RESULTS_MANIFEST.json` | demo-owned-v1 | 只把 SHA-256 記入 repo（已列在 #486 留言：`7462…95de8`、`1e87…7638d`）；PNG 與 logs 留 LOCAL | 與 CI／provenance 腳本（#501）接軌 |
| 舊路徑引用（Office launcher、research scripts 指向舊 venv／舊 worktree） | repo 內：`start-office-demo.command:7`、`tests/workbench/test_office_demo_presets.py:49,340,343,384,447`、`tests/workbench/test_controlled_scene_rgb.py:368`、`docs/research/PHASE1_REVIEWED_REPRODUCTION.md:7,95,96`、`docs/research/PHASE1_FINAL_REPORT.md:15` | 改成 repo 內路徑或 `AMIDST_DEMO_HOME`／`OFFICE_EVIDENCE_REPO` 單一設定 | D138 第二類最後一項；`.local-worktrees/phase1-finalization` 仍是 evidence 預設，在改完之前**不能**刪該 worktree |
| `~/Models/amidst/rtdetr` 權重 | `~/Models/amidst`（77 MiB） | 權重留 LOCAL；repo 只放 SHA（`provenance/model-source-hashes.json` 已有） | 台帳 `LOC-models` 有 manifest |

bytes 不同的 41 檔**不在**此表：mainline 較新，預設視為已被取代，除非 diff 顯示有缺漏的功能。

## 6. 驗證關卡：在 scratchpad clone 移除 SAFE 項目後必須全部通過

SAFE 項目大多在 repo 外（快取、主庫的未追蹤副本），所以關卡用「乾淨的 mainline scratchpad clone ＋ 不含這些項目的環境」模擬移除。scratchpad clone 本來就沒有主庫那 20 個未追蹤檔，等於已移除；快取則用空目錄取代。**以下全部通過才算可執行；任何一項失敗就中止、不刪。**

```bash
SCR="<scratchpad>"; git clone --shared "$HOME/Developer/amidst-q1q5" "$SCR/gate" && cd "$SCR/gate"
git fetch origin mainline/q1q5 && git checkout -B gate origin/mainline/q1q5
# 模擬已移除：空的 npm 快取、不寫入 pytest／ruff 快取
export npm_config_cache="$(mktemp -d)" RUFF_CACHE_DIR="$(mktemp -d)" PYTEST_ADDOPTS="-p no:cacheprovider"
```

| # | 關卡 | 指令 | 通過條件 | D163 結果（e85b51e） |
| --- | --- | --- | --- | --- |
| 1 | 單元測試 | `PYTHONPATH=src python -m pytest -o addopts= -q tests/q1q5 tests/evaluation tests/operations`；`node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs`（D163 修正：pytest 不設 `AMIDST_REQUIRE_IMPL`，與 CI 相同）| exit 0；pytest／node 的 pass 數 ≥ 移除前在同一 clone 記錄的基準（基準在關卡前先跑一次存檔：未移除版本） | **PASS**：基準 pytest 2228 passed／56 skipped／0 failed、node 544／0／0；移除模擬相同（需 ≥ 8 GiB 可用空間，見 D163 §3.1） |
| 2 | core-e2e | `CORE_SOURCE="$PWD" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)" CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node tests/browser/core-preview/core-e2e.mjs` | exit 0；checks 數與基準相同（#486 留言記錄 49 checks／16 PNG；以當時 mainline 重跑的基準為準）；clean/head 守門啟用 | **PASS**：130 checks、16 PNG＋1 JSON、0 page errors |
| 3 | real-e2e | `node tests/browser/core-preview/real-e2e.mjs`（用 owned runtime／`AMIDST_DEMO_HOME`） | exit 0；0 page errors／0 failed API；checks 數與基準相同 | 新 UI `ui-redesign/real-e2e.mjs` **PASS**（347 checks、61 PNG、0 error）；舊版 `core-preview/real-e2e.mjs` **FAIL 第 21 檢查（UNKNOWN，與移除無關）** |
| 4 | CI 綠燈 | 把同一個 commit 推到不會被合併的測試分支，等 GitHub Actions `ci.yml` 完成 | guard PASS、node 0 fail、pytest 0 fail（ubuntu 的 deselect 清單以 `.github/ci-linux-deselect.txt` 為準）；**push 需使用者授權** | **PASS**：run 42615223193，guard PASS、node 544／0／0、pytest 2211 passed／56 skipped／17 deselected；測試分支已刪 |
| 5 | 8785 不受影響 | 動手前後各跑：`lsof -nP -iTCP:8785 -sTCP:LISTEN`、`curl -fsS http://127.0.0.1:8785/ -o /dev/null -w "%{http_code}\n"`、`python scripts/check_demo_dependencies.py --smoke`（在 demo checkout，用 owned runtime） | 8785 仍由 **PID 21060** 監聽、HTTP 200、依賴 smoke 與 4,788 項 bytes/hash PASS；`~/amidst-artifacts/demo-owned-v1` 與 `~/amidst-demo-20261104` 的 `git status` 為 clean 且 HEAD 不變 | **PASS**：PID 21060 不變、HTTP 200、smoke PASS（4788 entries／2,756,614,124 B） |
| 6 | 台帳一致 | `python3 scripts/artifact_ledger.py verify --only <SAFE 的 ID>`；`python3 scripts/artifact_ledger.py validate`；`scripts/check_architecture_guard.py --base 46835218c600d99b8c973e52f62e8dd95e79ff15` | 無 MISMATCH；validate PASS；guard PASS | **PASS**：verify PASS、validate PASS（169）、guard PASS |

執行順序：先在未移除的 clone 記錄基準 → 套用「模擬移除」→ 關卡 1–3、6 → 使用者授權後推測試分支跑關卡 4 → 關卡 5 在**真正**刪除前後各做一次。**真正執行刪除要等使用者另外授權（#431）；本 PR 與本文件不執行任何刪除。**

## 7. 未驗證與 UNKNOWN

- 沒有執行任何刪除、搬移、壓縮、push、fetch --prune 或 git clean；所有指令都未執行。第 6 節的驗證關卡已由 D163 在 scratchpad clone 跑完（結果見 [CLEANUP_GATE_D163.md](CLEANUP_GATE_D163.md)；仍然沒有刪除任何東西）。
- 引用檢查是字串／regex 計數（`git grep`），不是語意分析：動態組出的路徑、環境變數展開後的路徑、或不在 git 裡的本機腳本不會被抓到；Codex 本機 checkout 內未推送的檔案同理（Codex 的 `codex/*` 只檢查了已 push 的 heads）。
- `lsof` 只看得到目前使用者、目前正在跑的行程；之後才啟動的 session 或排程不在內，所以關卡 5 與檢查 2 要在刪除當下重跑。
- 檢查基準是 2026-11-09 18:53 的狀態；D163 已對 `e85b51e`（#503、#504 之後）全部重跑；之後再有 merge 就要重跑。
- 台帳內的引用行號（44 筆 `檔案:行`）只核對檔案是否存在與行數是否足夠（36 筆通過，8 筆指向 mainline 沒有的檔案），**沒有逐行比對內容**。
- r004-cx7*、q1q5-* 等「保留原件」項目是否仍被驗收／yyin 流程引用，來源盤點為 UNKNOWN；台帳因此保守地全部保留。
- worktree `data/` 的備份狀態（是否別處另有副本）UNKNOWN；`phase1-case23-clean` 的 detached HEAD `c4a8a0a` 是否在遠端，本 PR 的 clone 沒有核對。
- 8785 demo 服務（`~/amidst-demo-20261104`）使用中，本 PR 完全沒有碰。
- `d131-previews` 仍有 node／python 行程開著其 logs（Codex 11-08 lsof）；本 PR 沒有重新檢查，台帳保留。
- Homebrew 快取、Chrome 快取與其他非 Amidst 路徑不在範圍內。
