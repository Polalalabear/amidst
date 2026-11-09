# 清理步驟 2（D163）：證據重驗與驗證關卡結果（只驗證，未刪除、未搬移、未封存）

- 範圍：D157 要求的「清理前嚴格確認不影響專案」。輸入：`configs/provenance/artifact_ledger_v1.json`、[CLEANUP_CANDIDATES_D138.md](CLEANUP_CANDIDATES_D138.md) §6、`scripts/artifact_ledger.py`；基準 `mainline/q1q5` @ `e85b51ed9767aec6142f59115ddc4fe83751dc63`（#503、#504 之後）。
- Model / effort：Sonnet 5.5 / medium。
- **本步驟沒有刪除、搬移或封存任何東西。** 實際刪除需要使用者另行授權（#431）；更新 main 也是另一項授權，本 PR 不涉及。
- 唯一的 push：測試分支 `claude/cleanup-gate-test`（已推、CI 綠燈、已刪除；使用者授權的唯一一個可刪分支）。

## 1. 結論

| 項目 | 結果 |
| --- | --- |
| SAFE（25 項、401.15 MiB） | **全部維持 SAFE**：沒有任何一項因重驗而降級；引用、大小、SHA-256／manifest、lsof、8785 依賴都與 11-09 的結論一致 |
| UNKNOWN（44 項） | **全部維持 UNKNOWN**：沒有任何一項取得完整證據，沒有升級 |
| KEEP（100 項） | 不變 |
| 驗證關卡 | 1 單元測試 PASS、2 core-e2e PASS、3 real-e2e：新 UI 的 real-e2e PASS，**舊版 core-preview/real-e2e.mjs FAIL（原因 UNKNOWN，與移除無關）**、4 CI PASS、5 8785 PASS、6 台帳 PASS |
| 需要使用者知道的 | ① `~/.npm` 現在只剩 `_npx`（531 MB，專案外工具的 npx 快取）；② 三個舊 head 的 `start_445_demo.command` 仍指向已刪的 finalization `.venv`；③ 舊版 real-e2e 的 1 個檢查失敗；④ 8785 依賴 smoke 在 demo-owned-v1/state 留下一個小暫存目錄；⑤ §6 的 pytest 指令需要修正（見 §6） |

## 2. 證據重驗（對 e85b51e）

### 2.1 `git grep` 引用數：e85b51e 與全部 103 個 origin heads

指令（`bash` 逐 revision 跑；排除台帳與清單文件自身，因為它們本來就寫了這些字串）：

```bash
for r in e85b51e $(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v '^origin$'); do
  git grep -n -E 'npm_config_cache' $r -- . ':!configs/provenance/artifact_ledger_v1.json' ':!docs/history/CLEANUP_CANDIDATES_D138.md' ':!docs/history/ARTIFACT_LEDGER.md'
  git grep -n -E '(\.pytest_cache|\.ruff_cache)' $r -- . ':!.gitignore' ':!docs' ':!configs/provenance/artifact_ledger_v1.json'
  git grep -n -E 'Developer/amidst/(configs|docs|scripts|src|tests|frontend)' $r -- . ':!docs/history' ':!configs/provenance/artifact_ledger_v1.json'
  git grep -n -E 'Developer/amidst([^-/A-Za-z0-9_.]|$)' $r -- . ':!docs' ':!configs/provenance/artifact_ledger_v1.json'
  git grep -n -E '(\.npm\b|npm_config_cache|\.pytest_cache|\.ruff_cache|d133-playback|amidst-p1-clean-room|Developer/amidst/)' $r -- .github start_445_demo.command README.md
  git grep -n -E '\.npm\b' $r -- . ':!docs/history' ':!*package-lock.json' ':!configs/provenance/artifact_ledger_v1.json'
done
```

| 檢查 | e85b51e | 103 個 heads |
| --- | --- | --- |
| `npm_config_cache`（全 repo） | **0** | 全 0 |
| `.pytest_cache`／`.ruff_cache`（排除 .gitignore、docs） | **0** | 全 0 |
| `Developer/amidst/(configs\|docs\|scripts\|src\|tests\|frontend)`（排除 docs/history） | 13（`data/reports/benchmark/mock_comparison/benchmark_summary.json`，歷史 fixture 字串，與 2616661 相同） | 13；`archive/3d-line`、`controlled-scene-a` 14、`q5-statechart-stage2` 16、`448-local-cleanup-inventory` 51：多出的全在 docs 文字（盤點／回覆文件），沒有程式讀取 |
| `Developer/amidst` 作為 repo 根（排除 docs） | 2（`data/engineering/work_handoff_20261014/receipt.json`、`data/finalization/recovery_checkpoint_20261008/validation.json`，歷史紀錄） | 2；`rules-d108` 4 |
| CI／`start_445_demo.command`／README 的上述任一 pattern | **0** | 0；**例外**：`claude/487-p2p3`、`claude/epic-d-agentic`、`claude/experiment-record-latex` 的 `start_445_demo.command:4` 預設 `$HOME/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python` |
| `\.npm\b`（排除 docs/history、package-lock） | **0** | 全 0 |

說明：
- 重驗**發現的差異**：直接 grep 時 e85b51e 在台帳／清單文件自身有命中（#503 合併進來的文字），排除這兩個檔案後與 11-09 的 2616661 結果相同；**mainline 沒有新增任何引用**。
- 三個舊 head 的例外指向的是 finalization 的 `.venv`（11-09 已清除，**不在 SAFE 清單內**；SAFE 的 finalization 項目只有 `.pytest_cache`、`.ruff_cache`），mainline 的 `start_445_demo.command` 已改掉（e85b51e 為 0）。這三個分支若再被合併，會把舊預設帶回來，屬後續處理事項，不影響 SAFE 判定。
- `d133-playback-proxies` 的 19 個 heads 引用 → 仍是 KEEP（不在 SAFE）。

### 2.2 大小與 SHA-256

- `python3 scripts/artifact_ledger.py verify --only <25 個 SAFE id>` → **PASS**（現場大小、檔案數、SHA-256／manifest 都與台帳相同）；驗證前、關卡全部跑完後各跑一次，都是 PASS。
- 20 個「重複副本」：對 e85b51e 逐檔 `git hash-object` 對 `git rev-parse e85b51e:<path>`：25 個檔案 **0 個不一致**；`git ls-files --error-unmatch` 確認這些檔案在 `~/Developer/amidst` 是未追蹤。
- 5 個快取：不再只比大小。逐檔 SHA-256 manifest（`files_only`，連算兩次相同）寫入台帳：`~/.npm` 42,095 檔／419,546,852 B／manifest `200843c0f019ab6455f0f96b4780b2fee5adce5552d2848bc540fcfe227bbb88`；其餘 4 個見 §5 的表。
- `~/.npm` 內容：`_npx` 531 MB（create-vite、create-expo-app、create-next-app、`@mermaid-js/mermaid-cli`、`xcodebuildmcp`、從 GitHub 安裝的 `gemini-cli` 的 npx 快取）、`_logs`、`_prebuilds`；`_cacache` 已於 11-09 清除。mainline 與 demo 啟動器都沒有 `npx` 引用；Claude／Codex 的 config 沒有這些套件。清除後下次 `npx` 需要網路重新下載。

### 2.3 lsof：6 次取樣

2026-11-09 19:23:59–19:26:06，間隔約 25 秒，每次約 11,300 行（`lsof -nP`，全部行程）。6 次中 `'.npm'`、`'.pytest_cache'`、`'.ruff_cache'`、`/Developer/amidst(/|$)`、`phase1-finalization` 的命中都是 **0**，cwd 在 `~/Developer/amidst` 的行程 **0** 個。這仍只是目前使用者、當下的行程；`lsof` 在刪除當下還要再跑（執行腳本會跑 3 次取樣）。

### 2.4 8785 與 demo-owned-v1

- 8785：PID **21060**（啟動 `Mon Nov 9 17:57:49 2026`，整個驗證期間未重啟），`127.0.0.1:8785` 監聽，HTTP 200。
- cwd `~/amidst-demo-20261104`；執行檔與 dylib 來自 `~/amidst-artifacts/demo-owned-v1/runtime/python`；`PYTHONPATH=~/amidst-demo-20261104/src`、`VIRTUAL_ENV=~/amidst-demo-20261104/.venv`；唯一的其他開啟檔案是 scratchpad 的 `serve8785.log`。環境變數沒有 `npm_config_cache`；`.venv/pyvenv.cfg` 的 `home` 在 demo-owned-v1。
- `~/amidst-demo-20261104` 與 `demo-owned-v1` 內**沒有**指向 `~/Developer/amidst`、`~/.npm`、`phase1-finalization` 的 symlink；demo checkout 的程式／config 沒有指向 SAFE 路徑的引用（只有 `.gitignore` 的快取名稱與 `data/reports/.../benchmark_summary.json` 的歷史字串）。
- 結論：8785 仍只使用 `~/amidst-demo-20261104`、`demo-owned-v1` 與 scratchpad log；兩者都不在 SAFE 清單。

### 2.5 UNKNOWN 重驗（44 項）

- 17 個 `UNT-*`：對 e85b51e 逐檔比對，**全部**至少有一個檔案 bytes 不同（mainline 較新）或在 mainline 沒有 → 不是重複副本，不能證明刪除無影響 → 維持 UNKNOWN（`UNT-frontend--workbench-v2`、`UNT-src--amidst--q1q5`、`UNT-tests--q1q5` 是部分相同、部分不同／缺少）。
- 其餘 27 項（`ART-*`、`CACHE-codex-*`、`CACHE-torch`、`CO-wt-finalization`、`ENV-d139-venv`、`LOC-fin-*` 等）：沒有「已收進主線或有等價備份」的證據 → 維持 UNKNOWN。
- 每筆的 `safety.recheck` 欄位已寫入台帳。

## 3. 驗證關卡（scratchpad 的精簡 clone，`git clone --shared ~/Developer/amidst-q1q5`，origin 設為 GitHub；用完刪除）

環境：`uv sync --frozen --all-groups --python 3.12`（uv 快取在 scratchpad）；`npm ci` 用**空的** `npm_config_cache`（成功，從網路重新下載）；`RUFF_CACHE_DIR` 空目錄、`-p no:cacheprovider`；clone 在 `e85b51e`，`git status` 乾淨；pytest／node／e2e 都在 `sandbox-exec` 之下跑（禁止寫入 `~/amidst-artifacts`、`~/amidst-demo-20261104`、`~/Developer/amidst*`、`~/.npm`、`~/.codex`、`/Users/Shared`），所以真實檔案沒有被測試寫入。

| # | 關卡 | 指令（摘要） | 結果 |
| --- | --- | --- | --- |
| 1 | 單元測試 | 基準（快取開啟）：`python -m pytest -o addopts= -q tests/q1q5 tests/evaluation tests/operations`＋`node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs`；移除模擬（空 npm 快取、無 pytest／ruff 快取）重跑同一組 | 基準 **2228 passed／56 skipped／0 failed**；node **544 pass／0 fail／0 skipped**。移除模擬：**2228 passed／56 skipped／0 failed**；node 544／0／0（兩者相同，最少剩餘磁碟 9.03 GiB）。**PASS** |
| 2 | core-e2e | `CORE_SOURCE=$PWD CORE_INTEGRATION_HEAD=$(git rev-parse HEAD) CHROME_EXECUTABLE=… node tests/browser/core-preview/core-e2e.mjs`（SCREENSHOT_DIR 在 scratchpad） | exit 0；**130 checks**、16 PNG＋1 JSON、`page_errors: []`、clean tree／head 守門啟用（#486 留言的 49 checks 是舊數字，D139 之後增加）。**PASS** |
| 3a | real-e2e（新 UI） | `node tests/browser/ui-redesign/real-e2e.mjs`（打 8785；輸出在 scratchpad） | exit 0；**347 checks**、61 張截圖、`errors: []`、`http: []`（0 failed API）。**PASS** |
| 3b | real-e2e（舊版 RGB 相容閘） | `node tests/browser/core-preview/real-e2e.mjs`（§6 原列的指令） | **exit 1，第 21 個檢查失敗**：`A4-1 missing intervals preserved`（要求 `single_view` 同時有 GAP 與 LOST）。原因 **UNKNOWN**：此閘的檔案名稱註解已寫「new UI real gate is ../ui-redesign/real-e2e.mjs」，且該檔在 8785 部署版（89a73e65）與 e85b51e 相同，失敗與快取／重複副本都無關。未改任何程式。**不計入通過**，列為 UNKNOWN 待 Codex／使用者判斷這個舊閘是否仍要維持 |
| 4 | CI 綠燈 | 推 `claude/cleanup-gate-test` @ e85b51e（只 push，沒有開 PR）→ Actions run [42615223193](https://github.com/Polalalabear/amidst/actions/runs/42615223193) | **success**；checks job：architecture guard PASS、node 544 pass／0 fail／0 skipped、pytest **2211 passed／56 skipped／17 deselected**、`git diff --check` PASS；已刪除遠端測試分支（`git ls-remote` 0 筆）。**PASS** |
| 5 | 8785 不受影響 | 前後各查：`lsof -nP -iTCP:8785 -sTCP:LISTEN`、`curl …/`、`check_demo_dependencies.py --smoke` | PID 21060 不變（啟動時間不變）、HTTP 200、smoke **PASS**（`entries: 4788`、`bytes: 2756614124`、`source_mutations: false`）；demo checkout HEAD 仍是 89a73e6 且 `git status` 乾淨。**PASS**（副作用見 §3.2） |
| 6 | 台帳一致 | `artifact_ledger.py verify --only <25 個 SAFE id>`、`validate`、`check_architecture_guard.py --base 46835218…`、`git diff --check` | verify **PASS**；validate **PASS（169 筆）**；guard **PASS**（authority／inference／schemas 全 PASS）；diff-check exit 0。**PASS** |

### 3.1 失敗紀錄與原因（沒有改程式去讓它通過）

1. 第一次單元測試（`AMIDST_DEMO_HOME` 指向空目錄）：178 failed／16 errors，原因是我把測試的真實資料目錄換成空的 → 無效，已丟棄（改用預設的 owned root，唯讀）。
2. 第二、三次：222 failed，原因全是 repo 自己的 **`DISK_BELOW_8_GIB` 守門**（可用空間低於 8 GiB；此 Mac 的可用空間在 6.2–9.4 GiB 間來回，原因是同時有別的 session 在跑 pytest 與寫入）。用 repo 外的診斷外掛把可用空間報成 ≥ 9 GiB 時，baseline 與移除版失敗集合**完全相同**（110 vs 110）。此外掛只用來判斷原因，**不算通過**。
3. §6 原本的指令帶 `AMIDST_REQUIRE_IMPL=1` 給 pytest：會讓 `tests/evaluation/test_team_eval_return_scoring.py` 7 個測試因 `CQ39_IMPLEMENTATION_MISSING` 失敗；CI 只對 **node** 設這個變數、pytest 不設。已把 §6 的 pytest 指令改成 CI 的形式（不設 `AMIDST_REQUIRE_IMPL`）。
4. 之後的兩次移除模擬：一次 107 failed（可用空間降到 7.6 GiB，錯誤碼全是 `DISK_BELOW_8_GIB`／`DISK_SPACE_BELOW_8_GIB`／`LOW_DISK`）；另一次 1 failed（`test_check_event_run_bundle.py::test_d119_resealing_valid_replacement_pixels_cannot_override_producer`），單獨重跑 2 次都 PASS，當時可用空間也在 8 GiB 附近波動，原因**無法單獨證明**，記為 UNKNOWN（暫時性）。等別的 session 的 pytest 結束、可用空間 ≥ 9 GiB 後重跑，才得到 §3 表中的 0 failed。已知 flaky 的 `test_baseline_runner.py` 在最後兩次完整執行中都沒有失敗（基準與移除模擬各一次）；在低空間的執行中它因 `DISK_*` 失敗。
5. 診斷時發現 `sandbox-exec` 預設會擋 `/bin/ps`，造成 15 個測試的 `PermissionError`；已在沙箱設定允許 `ps`，與專案無關。

### 3.2 對真實檔案的影響（要誠實記錄）

- `check_demo_dependencies.py --smoke` 的設計會在 `~/amidst-artifacts/demo-owned-v1/state/` 建立 `dependency-check-<random>/`（4 KB、內含 `state/registry.json` 與 `recordings/`）；這次在 `state/dependency-check-x_06b2ej` 留下一個（11-08、11-09 前已有 4 個同類目錄）。這是 §6 關卡 5 指定的指令的正常行為，我只開放沙箱寫這個目錄前綴，**沒有刪除它**（本步驟不刪任何東西）。是否清理由使用者決定。
- `demo-owned-v1/models/ollama` 內的 mtime 比我的開始時間新：那是正在執行的 Ollama 的行為，不是本步驟的測試（測試在寫入禁止的沙箱中）。

## 4. 修正與建議（給下一步）

- 本 PR 已把 D138 清單 §6 的 pytest 指令改成 CI 形式，並補上 CI／pytest 的實際數字與 core-e2e 新數字。
- 真正刪除前要再跑：`artifact_ledger.py verify`、`lsof`（執行腳本內建 3 次取樣）、8785 PID／HTTP 200。執行腳本需要 ≥ 5 GiB 可用空間，且若有別的 session 在跑 pytest，請等它結束再做驗證。
- 後續另開事項（不在本步驟）：三個舊 head 的 `start_445_demo.command` 預設路徑；舊版 `core-preview/real-e2e.mjs` 第 21 個檢查；`dependency-check-*` 暫存目錄是否要由 smoke 自己清理。

## 5. 最終建議刪除的項目（25 項，共 420636415 bytes（401.15 MiB），25 項。）

**全部都「先封存、驗證封存、再刪除」。** 沒有任何一項是原始 Blender／影片／資料集／calibration／GT；沒有任何一項被 8785、`demo-owned-v1`、任何分支或已知流程使用。

| ID | 路徑 | 大小（bytes） | 檔案數 | SHA-256（單檔）／manifest SHA-256（目錄） | 還原方式 |
| --- | --- | ---: | ---: | --- | --- |
| `CACHE-npm` | `~/.npm` | 419546852 | 42095 | `200843c0f019ab6455f0f96b4780b2fee5adce5552d2848bc540fcfe227bbb88`（manifest） | 快取，自動重建（npm ci／pytest／ruff；需要網路的只有 npm） |
| `LOC-fin-pytest_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.pytest_cache` | 441451 | 5 | `a76ebcf4d2903227de2ce24fdeb51675bebc989a242a1a31d8fcfa57b8378393`（manifest） | 快取，自動重建（npm ci／pytest／ruff；需要網路的只有 npm） |
| `LOC-fin-ruff_cache` | `~/Developer/amidst/.local-worktrees/phase1-finalization/.ruff_cache` | 87810 | 43 | `4540261ee4b8295d0dac084a26eb0553090c80364105496f7d6592fed7422fa7`（manifest） | 快取，自動重建（npm ci／pytest／ruff；需要網路的只有 npm） |
| `LOC-main-pytest_cache` | `~/Developer/amidst/.pytest_cache` | 92276 | 5 | `a1a6080bbb83b8740962735d0b9cd89671e03f7c94b3e69f8b15b49181c9e4d7`（manifest） | 快取，自動重建（npm ci／pytest／ruff；需要網路的只有 npm） |
| `LOC-main-ruff_cache` | `~/Developer/amidst/.ruff_cache` | 16118 | 54 | `89d0bb3a5bfdb69a6c8368180ca83b6dacea4bda4db1bee50b0b09935252c74f`（manifest） | 快取，自動重建（npm ci／pytest／ruff；需要網路的只有 npm） |
| `UNT-configs--q1q5` | `~/Developer/amidst/configs/q1q5` | 361647 | 11 | `b6d12b87137424fb8fa6a365d3f3f8c2ac5aa190c18bf23cf63e70346ed32c1a`（manifest） | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_BASELINE_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md` | 5727 | 1 | `e6a6de7f189195d95655f5602fbb7387c645de49c1479e47cce80a6cb1d1636d` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_BASELINE_DECISIONS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_DECISIONS.md` | 3556 | 1 | `27c8930dbb28fccce6cbd8ec96b7c8c3ae9d805bb109a2e4024a32cfabf534db` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_BASELINE_RUNNER.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_RUNNER.md` | 10108 | 1 | `e16daed41e3493e9448ab746962f397d5516c53d44f8957a85ff4a2bd902d18c` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_BASELINE_V1_PROTOCOL.md` | `~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md` | 15960 | 1 | `31c49330a682021b242c07c2bd3f86b34b09195e8e16b7421f02a8f0266ec89d` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_LINKED_ACCEPTANCE.md` | `~/Developer/amidst/docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md` | 6886 | 1 | `55330e00bb5be9ddcd7f77d0cdcc0ec5a06396c5a57b7d77b4ab917023448137` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_PRODUCTION_PREPARATION.md` | `~/Developer/amidst/docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md` | 3084 | 1 | `f5f1f1802f20af196cde6c49853a4c66e21cdd6407d1570174bbf430f72e745b` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--engineering--Q1Q5_REVIEWED_INPUTS.md` | `~/Developer/amidst/docs/engineering/Q1Q5_REVIEWED_INPUTS.md` | 3348 | 1 | `b65e90df3395776183098bb1e29c4b370a0036d2df2ea39618f3fecc67bee9b0` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--evaluation` | `~/Developer/amidst/docs/evaluation` | 3235 | 2 | `89d316dea0214730529f6e878076346fd276162eac858d45f1e82c42fd6aee04`（manifest） | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--history--Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json` | 4240 | 1 | `275a4e1101eb6cf015428bde416290a7b41b6c03ec2da3fa6b4fa837e10f15d4` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-docs--history--Q1Q5_LINKED_ACCEPTANCE_20261024.json` | `~/Developer/amidst/docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json` | 5950 | 1 | `5826fb3dea4bb7f18a852d84b46d29771318f275576757f347ec38f4fc49c82d` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--accept_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/accept_q1q5_linked_baseline.py` | 1362 | 1 | `64aeeea9ab29848c71f4b1eb955f663f8ed70dcf39bb483678e40f56858b9a21` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--build_q1q5_pinned_index.py` | `~/Developer/amidst/scripts/build_q1q5_pinned_index.py` | 1133 | 1 | `41f465691d98a26712782b3d2c98ee3ca0ea6e94f06c9bf5fa7c2482cd7c28e2` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--import_q3_minimum_review.py` | `~/Developer/amidst/scripts/import_q3_minimum_review.py` | 2817 | 1 | `8ce5f1aa58f37067867e4d2eefe000382e50d5455b930e85d60ca40144f76253` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--measure_q1q5_dynamic_rgb.py` | `~/Developer/amidst/scripts/measure_q1q5_dynamic_rgb.py` | 3284 | 1 | `a3d5aa3b47afe48c14fc1d1d072fdf3008e9035180882693e1bd5c36748f3729` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--preflight_q1q5_production.py` | `~/Developer/amidst/scripts/preflight_q1q5_production.py` | 2241 | 1 | `b9329bac83d2f670cda70c909d0ba9457508f9472a1c02b812c40a3337415e1d` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--prepare_q1q5_baseline_source.py` | `~/Developer/amidst/scripts/prepare_q1q5_baseline_source.py` | 1135 | 1 | `eaa4074d9a41d7741fa19ab30dabe73bc24a75b88fe1f09add78afee94e743e9` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--replay_q1q5_dynamic_evidence.py` | `~/Developer/amidst/scripts/replay_q1q5_dynamic_evidence.py` | 4356 | 1 | `1b46a491188f5faadb72d0cc46c776afb085761b02cce16729a7fae7446dbf89` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-scripts--run_q1q5_linked_baseline.py` | `~/Developer/amidst/scripts/run_q1q5_linked_baseline.py` | 2076 | 1 | `8982ec819204dbeddfd1b6b4fd8916c09592b6b8b5d0d293711c563f3e7b8cf8` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |
| `UNT-src--amidst--evaluation--q3_review_import.py` | `~/Developer/amidst/src/amidst/evaluation/q3_review_import.py` | 9763 | 1 | `5db6c4d742a7997d493cc67cdf99c20b6db7f4558d175590d61289ced40603aa` | `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑>`；或解開封存 tar |

合計 420636415 bytes（401.15 MiB），25 項。

還原方式補充：
- 20 個重複副本：內容與 `mainline/q1q5` 同路徑完全相同，隨時可用 `git -C ~/Developer/amidst-q1q5 show mainline/q1q5:<repo 相對路徑> > <目的地>` 取回；執行腳本也會先把它們放進封存 tar。
- 5 個快取：不需要還原（工具下次執行會重建；`~/.npm` 的 `_npx` 需網路）。執行腳本預設仍會封存（`--skip-cache-archive` 可略過，省 ≈0.4 GB 暫存）。

## 6. 封存後刪除的執行腳本（預設 dry-run；本 PR 沒有執行）

[CLEANUP_EXECUTE_D163.sh](CLEANUP_EXECUTE_D163.sh)：

```bash
bash docs/history/CLEANUP_EXECUTE_D163.sh              # dry-run：只做檢查並印出計畫（預設）
bash docs/history/CLEANUP_EXECUTE_D163.sh --execute    # 使用者授權（#431）後才執行
```

流程：① 前置檢查（台帳 verify、可用空間 ≥ 5 GiB、8785 仍由 PID 21060 服務且 HTTP 200、`lsof` 取樣 3 次無人開啟、20 個重複副本對 `mainline/q1q5` 逐檔 blob 相同且未追蹤）→ ② 把 25 個路徑打成一個 `tar.gz` 並寫 `.sha256` → ③ 解開封存逐檔 `diff -r` 比對原件，不一致就中止（尚未刪任何東西）→ ④ 只刪清單中的明確路徑（`rm -r --`，無萬用字元、無 sudo）→ ⑤ 事後檢查（ledger verify、8785 PID 不變、HTTP 200）。只經過 `bash -n` 語法檢查，**沒有跑過任何一行**。

## 7. 未驗證與 UNKNOWN

- 引用檢查仍是 `git grep` 字串計數：動態組出的路徑、本機未追蹤的腳本、Codex 本機未推送的 checkout 不會被抓到；`lsof` 只看目前使用者的行程。
- 執行腳本本身沒有執行過（含 dry-run）；它的 `check()`／封存／還原流程是依 D138 清單的同名函式改寫，只做了語法檢查。
- 舊版 real-e2e 第 21 個檢查失敗原因 UNKNOWN（§3 3b）。
- `sandbox-exec` 防寫只涵蓋測試與 e2e 子行程；其他 session 的寫入無法排除（`demo-owned-v1/models/ollama` mtime）。
- APFS clone／snapshot 讓實際釋放空間可能與 401.15 MiB 不同。
- 44 個 UNKNOWN、100 個 KEEP 沒有重新做完整五項檢查（只比對 `UNT-*` 與 mainline 的 bytes）。
