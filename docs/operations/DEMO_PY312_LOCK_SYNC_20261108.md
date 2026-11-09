# #491 Python lock 同步與衝突解決（2026-11-08）

收到 #491 `claude/epic-c-cleanup@fa9a199a680533531680ab54ad8d110db6ca0563` 後，將其完整 history 合入 C，再接到 UI 驗收分支。保留原始 `pyproject.toml`、`uv.lock`、`.python-version`、`scripts/setup_env.sh` 與相關修正；沒有重產或手改 lock。C 收編再以 merge commit 接回 #491 feature branch，不合併 PR／mainline/main。

## 衝突處理

| 路徑 | 解法 |
| --- | --- |
| `.gitignore` | 保留 C 的自有 cache／repo Playwright 規則，加入 #491 的 `node_modules/`。 |
| `.python-version` | 採 #491 原值 `3.12`；本次實跑 Python 是 owned runtime 的 **3.12.12**，不借舊 venv。 |
| `start_445_demo.command` | 保留 checkout `.venv` 和 repo cache；不恢復可指向舊環境的 Python override。 |

C 同步 merge：`e62f9deb65d71de21d1f296f4dc9f3c45e7e545f`，parents 為 C `297696395f78700b59d65c9ea2f2b6babe508826` 與 #491 `fa9a199a680533531680ab54ad8d110db6ca0563`。UI 驗證 merge：`4bc53b8214f78cea289093ef6df8c2135809b1f9`。最終文件提交後的 heads 記在 A／C GitHub 回條；本次 runtime gates 都綁上述 UI 驗證 merge。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: #491、#487 保持 Draft；只使用 merge commits，不 force／rebase／刪分支，不改 integration/mainline/main。輸入 heads 與 lock hashes 見同名 JSON composition。
- Files changed: 接入 #491 原始變更；只在上表三檔解衝突，更新本交接與 owned dependency 文件。`frontend/` 和 browser drivers 相對 UI `86b72e66` bytes 完全相同。舊路徑 → 新位置表完整保留於 `DEMO_OWNED_DEPENDENCIES_20261108.md`。
- Commands run and results:
  - `UV_CACHE_DIR="$PWD/.local/demo-cache/uv" uv sync --frozen --no-install-project --extra product --link-mode copy --no-python-downloads --python "$PWD/.venv/bin/python"`：PASS，只新增 lock 內 `imageio-ffmpeg==0.6.0`，沒有替換任何既有套件；36 distributions 均在新 lock，Python 3.12.12，base 在 owned runtime。
  - `AMIDST_REQUIRE_IMPL=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$PWD/.local/demo-cache/uv" uv run --offline --no-project --python "$PWD/.venv/bin/python" python -B -m pytest -o addopts= -q tests/q1q5/test_core_search_track_t.py tests/q1q5/test_scene_graphs.py`：**121 passed / 23.70 s**，包括 r005 coverage gate。
  - `AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs`：**494 pass / 0 fail / 0 skip**。第一次沙盒執行的 5 個 loopback 測試遭 EPERM；允許本機監聽後重跑全數通過，沒有為此改程式。
  - `... python -B scripts/check_demo_dependencies.py --smoke --output <LOCAL>/dependency-check.json`：**4,788 項 bytes/hash/link、repo Node 340 檔、Ollama 五 blob digest、外部 I/O 拒絕、四來源 served PNG SHA 全 PASS**，沒有執行模型或 render。
  - `./start_445_demo.command --port 8787`；`CORE_BASE_URL=http://127.0.0.1:8787 UI_QA_HEIGHT=<900|1300> UI_QA_OUTPUT=<LOCAL>/real-<height> node tests/browser/ui-redesign/real-e2e.mjs`：**各 159 checks / 32 PNG / 0 page errors / 0 failed API，exit 0**。
  - `CORE_SOURCE="$PWD" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)" CORE_VIEWPORT_HEIGHT=<900|1300> CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' SCREENSHOT_DIR=<LOCAL>/synthetic-<height> node tests/browser/core-preview/core-e2e.mjs`：**各 51 checks / 16 PNG，exit 0**，新 UI 與 clean/head guards 啟用。
  - `CORE_BASE_URL=http://127.0.0.1:8787 UI_DOM_OUTPUT=<LOCAL>/dom node tests/browser/ui-redesign/dom-e2e.mjs`：**11 checks / exit 0**。
  - `... python -B scripts/check_architecture_guard.py --base 1fdc1a4da9824e8bd6230c1dbcd3a845ad869deb --report <LOCAL>/architecture-guard.json`：**PASS，無 allow**；`bash -n start_445_demo.command scripts/setup_env.sh`、`git diff --check`、branch diff check PASS。
- Artifacts: LOCAL `$AMIDST_ARTIFACTS/demo-owned-v1/evidence/491-lock-sync/`：**118 payload files / 17,321,089 bytes，96 PNG**。`RESULTS_MANIFEST.json` SHA-256 **`1e878051e2bc920c9de3d678eee25873a0ac5d5bf4b949d5c159723a1287638d`**，逐檔記錄 bytes/SHA，含來源 SHA、結果、圖、logs。歷史 `evidence/486/` 與 UI `FINAL_REVIEW_MANIFEST.json` 保持原 bytes，沒有改寫成新 lock 的證據。截圖可重跑上列 commands 產生；原始 RGB 不重產。
- Verified: #491 lock 與原交付逐 bytes 相同；Python 全程為 checkout 自有 venv；三事件查看／查找／單多畫面／盲區、r005、D137、兩高度 bar 的底邊誤差 <2 px、DOM cleanup 與 legacy colors 均通過。另目視檢查 900 case3 與 1300 case2 截圖，底部列貼齊視窗。所有來源、模型、資料 manifest 不變。
- Not verified: 本次依指示只重跑上述聚焦驗證，未重新跑整套 tests/q1q5；#491 原作者的 2098 PASS 是其歷史結果，不冒稱本次結果。Windows/Linux 與實體顯示 FPS 不屬本次 Mac 衝突解決的結果；需要對應平台／量測 owner。
- Deviations, decisions and handoff: 本次衝突與指定 gates 全部通過。依使用者最新指示，**8785（PID 99812）保持運行，沒有重啟或停止；只有另開的 QA 8787 已停**。Claude 通知後才安排 8785 重啟。本機清理盤點已由另一對話完成，本 chat 不重做、不刪不改盤點項目。沒有宣稱 A／C 整個大問題結案。

Claude 通知重啟時：保持 `claude/ui-redesign-v1`，在 demo checkout 執行 `./start_445_demo.command --port 8785`；先依通知結束舊程序，勿同時占用同一埠。目前不要執行此步。不要為了 C 交接切換正在提供 UI 的 checkout。
