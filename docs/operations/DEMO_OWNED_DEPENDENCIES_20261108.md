# C / #486：自有依賴與主線交接（2026-11-08）

本次從 #445 `1fdc1a4da9824e8bd6230c1dbcd3a845ad869deb` 的 saved-observation demo 收編依賴，分支 `codex/486-vendor-deps`。WIP `e34c16af` 已先保存並 push；#487 的 UI 修正在 `claude/ui-redesign-v1`，沒有把 #487 合入本分支。本分支的程式、鎖定、啟動器、manifest 與文件以進 `mainline/q1q5` 為交接目標；依使用者指示不開 PR、不合併、不整理或刪除分支。

## 啟動與重現

固定 LOCAL 根目錄為 `~/amidst-artifacts/demo-owned-v1`，可用 **單一** `AMIDST_DEMO_HOME` 改到另一個 canonical 目錄。設定集中於 `configs/demo_integration_local.json`。移機時傳送自有 package 的 data、metadata、models、runtime 與 provenance，校驗 repo manifest；不從舊 checkout 或臨時資料夾補檔。raw RGB、模型與環境不進 Git。這次保存的 Python runtime profile 是 **Mac darwin-arm64**；Windows／Linux runtime 與整個 C 的其他清單仍屬獨立平台驗收，不能把本機 PASS 當它們的結果。

在 demo checkout：

```sh
# 第一次建立／按鎖定同步；有完整 cache 時可加 --offline。
export AMIDST_DEMO_HOME="${AMIDST_DEMO_HOME:-$HOME/amidst-artifacts/demo-owned-v1}"
PYTHONPATH=src uv run --offline --no-project \
  --python "$AMIDST_DEMO_HOME/runtime/python/bin/python3.12" \
  python -B scripts/setup_owned_demo.py

./start_445_demo.command --port 8785
```

若沒有設定環境變數，第一個命令的 Python 改用 `~/amidst-artifacts/demo-owned-v1/runtime/python/bin/python3.12`。第二個命令會自己讀同一設定，不需要任何舊環境參數。setup 僅使用 repo `uv.lock` 和 `tests/browser/core-preview/package-lock.json`；venv 在 checkout `.venv`，`uv sync --frozen --no-install-project --link-mode copy --no-python-downloads`，專案由 `PYTHONPATH=src` 讀取。Node 依 `.node-version` 為 26.0.0，npm 本次為 11.12.1，Playwright **devDependency** 鎖 1.56.0；`npm ci --ignore-scripts --no-audit --no-fund` 安裝於 repo 下，無 TMP fallback。Python `.python-version` 為 3.12.12。

服務會拒絕讀取 checkout／owned package 以外的 home、Shared、TMP 輸入，並拒絕模型子程序與外連。immutable JSON 裡的舊來源字串只作 provenance；不被解析成活的讀檔路徑。圖、index、clock、records、local tracks、r005 人工回條及 RGB 原始 bytes/pins 均不改；新 job 只有 locator 換成相對路徑。state／證據落在 owned 根目錄；uv cache 在 checkout `.local/demo-cache/uv`。

## 舊路徑 → 新位置

表內新相對位置皆以 `AMIDST_DEMO_HOME` 為根，除明確標 repo 者。bytes 是**這次複製範圍**，不是宣稱整個舊資料夾可回收的量。

| 舊位置 | 新位置 | 範圍／大小 | 誰引用（baseline 或目前） |
| --- | --- | --- | --- |
| `~/Developer/amidst/.local-worktrees/phase1-finalization/.venv` | **repo** `.venv`，從 lock 建立 | 舊 venv 798,852 KiB；新環境大小見 C 最終回條，35 個鎖定 distributions | 舊 `start_445_demo.command:4` → 新同檔、`scripts/setup_owned_demo.py` |
| `~/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none` | `runtime/python/` | 1,895 entries / 47,801,129 bytes | `.venv/pyvenv.cfg` 的 base；新 runtime guard 確認 base 在 owned runtime |
| `/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試` | `data/p1-v4/` | 398 / 149,497,111 bytes | 舊 `serve_demo_integration.py:282`、P1 super constructor；新 config `p1_bundle` |
| `~/amidst-artifacts/r004-cx7r-20261104-01a19f8b/bundle/safe_bundle` | `data/artifacts/r004-cx7r-20261104-01a19f8b/bundle/safe_bundle/` | 2,056 / 1,105,936,480 bytes，含 2,050 RGB | `serve_demo_integration.py` Media manifest／catalog／clocks |
| `~/amidst-artifacts/d131-previews/cross-camera-job.json`、其 `checkouts/pr477/configs/q1q5/graphs/r004/camera_graph_v3_1.json`；`/private/tmp/amidst-d131-417-output/{A4-1,B4-1}`；`/private/tmp/amidst-d131-control/{A4-1,B4-1}-config.json` | `provenance/original-cross-camera-job.json`；`metadata/{cross-camera-job.json,graphs/,config/}`；`data/indexes/{A4-1,B4-1}/` | 原始 12 / 1,605,219 bytes；另產生相對 locator job | 舊 Demo constructor 的 job 引用；新 `resolve_job`。逐檔舊／新／bytes 在 inventory JSON |
| `~/amidst-artifacts/d127-418-office-expanded-r005-preview-v2/rgb`、`d129-464-r005-probe-20261105-a/report.json` | `data/artifacts/` 下同名相對路徑 | 7 / 3,022,482 bytes，六張相機圖＋回條；無 overhead/GT | `serve_demo_integration.py` r005 loader |
| `~/Models/amidst/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth`、`~/amidst-artifacts/q1q5-dynamic-baseline-v1_20261025/model-source/rtdetr_pytorch`、`/private/tmp/amidst-d131-control/model-source-hashes.json` | `models/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth`、`models/rtdetr/source/rtdetr_pytorch/`、`provenance/model-source-hashes.json` | 73 / 81,225,896 bytes | frozen A4/B4 config 的模型 provenance；新 config `models`，本 demo 不執行模型 |
| `~/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/ollama_models` 的 Qwen3 1.7b q4_K_M | `models/ollama/` | manifest＋5 個被引用 blobs，6 / 1,359,294,303 bytes | 新 config `models.ollama_models`；未啟動 Ollama |
| `/private/tmp/amidst-d131-playwright/node_modules/playwright-core` | **repo** `tests/browser/core-preview/node_modules/playwright-core`（從 lock 安裝）；遷移副本仍保留於 `tooling/playwright-core/` | 遷移副本 340 / 8,228,434 bytes；repo 套件 340 檔 hash 相符 | 兩個 browser gates 的 `owned-runtime.mjs` |
| 舊 `INTEGRATION_OUTPUT`／臨時截圖根目錄、`/private/tmp/amidst-445-*` state | `evidence/486/{synthetic,real}`、`state/` | 每次產物大小與 SHA 見 LOCAL receipts | config `evidence_root/state_root`，兩個 browser gates／server main |

完整 inventory：`docs/engineering/DEMO_DEPENDENCY_INVENTORY_20261108.json`。它還列出 baseline 82 列／60 個程式檔的其他 literal（另補入口 refs），區分不在 demo call path 的歷史工具、guard／測試字串；不把 regex、輸出位置或 GT 隔離測試的字串當成應複製資料。受保護資產不讀。host tools 是 `/opt/homebrew/bin/{uv,node}` 與 `/Applications/Google Chrome.app/.../Google Chrome`；本機版本 uv 0.9.26、Node 26.0.0、npm 11.12.1、Chrome 156.0.8078.80。它們是安裝的主機工具，沒有複製舊 checkout 的二進位或把主機 app 上傳 Git。

## Manifest 與持久 LOCAL 證據

- repo `configs/demo_dependencies_manifest_v1.json`：**4,788 entries / 2,756,614,124 bytes**（含 9 個相對 symlinks 與新 job），逐檔 SHA-256；manifest SHA-256 `ddc833d701274595dd6d3102219a0d5a50b2731dda702119d36a5e2496441c50`。
- LOCAL `demo-owned-v1/copy-manifest.json`：原始 **4,787-entry** copy receipt，SHA-256 `8b9a4b4b98f52fa56317e0673dcf4da0d688b846c75dc0003b2d8bca743d061f`；原始一般檔案 bytes 2,756,610,945。複製期間記錄的最低 free **10,814,017,536 bytes**，高於 8 GiB。
- LOCAL `demo-owned-v1/provenance/486-copy-plan.json`：原計畫 SHA-256 `2467de25476dae79ccdcbc78b082fb31edcb57beb864e0ce35b9d8105cc8f9da`。`scripts/collect_demo_dependencies.py --plan <該計畫>` 只接受**全新**目的根目錄，exclusive create、hash 比對並逐塊檢查 8 GiB；不直接對現有根目錄重跑。
- `scripts/export_demo_dependency_manifest.py --owned-root <根> --output configs/demo_dependencies_manifest_v1.json` 可逐 bytes 重現 repo ledger；已有輸出只接受完全相同 bytes。
- 新 `metadata/cross-camera-job.json` SHA-256 `651906f9ca18a02d8efd300eb9cef57877ad8da758d9a323b590f82feb86d49e`；原始 job 與每個輸入 pin 仍保留。
- RT-DETR 權重 SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`。Ollama Qwen3 model blob SHA-256 `3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6`；其餘 descriptor/blob digest 逐一在 repo ledger 與 checker 證據。
- `uv.lock` SHA-256 `18c66a46f799efcfb4da36a15246245d2c959e42768a67b01f667eb73d284a17`（原 lock 未改）；Node lock SHA-256 `d875f6ffa3ee7863fdd0570ce17907238215690e58c0b6d71a9362f48c6f6263`。35 個 installed distributions 的精確版本都必須出現在 uv lock。舊環境的 editable project／非 #445 必要的可選 video extra 不當 runtime 借用；可選 dependency 本身仍在 lock。

## 聚焦驗證

```sh
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="$PWD/.local/demo-cache/uv"
uv run --offline --no-project --python .venv/bin/python python -B \
  scripts/check_demo_dependencies.py --smoke \
  --output "$AMIDST_DEMO_HOME/evidence/486/dependency-check.json"
AMIDST_REQUIRE_IMPL=1 uv run --offline --no-project --python .venv/bin/python \
  python -m pytest -o addopts= -q tests/q1q5/test_core_search_track_t.py tests/q1q5/test_scene_graphs.py
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
CORE_SOURCE="$PWD" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)" \
  CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  node tests/browser/core-preview/core-e2e.mjs
node tests/browser/core-preview/real-e2e.mjs
```

未設定 `AMIDST_DEMO_HOME` 時第一個 checker 的 output 可直接填預設根目錄，其他指令會由設定取預設值。synthetic gate 必須在乾淨 tree 上執行；exact head pin 與 ancestry guard 不關閉。real gate 需要前述 8785 服務，可用 `CORE_BASE_URL` 指定本次服務。

實際已執行：離線 setup、4,788 項 hash/link、repo Node 340 檔、Ollama manifest 的五個 blob digest、外部輸入負向探針、four-source bootstrap 與四張 served PNG SHA 均 PASS；模型／render 皆未執行。四組 #445 acceptance 已實跑通過，詳見下列實際產出。

## 清理與主線邊界

所有舊位置對本 demo 的活讀取已解除，受 runtime guard 保障；但**沒有任何舊路徑可在本輪宣稱全球無人引用或可刪**。例如 `scripts/start_office_demo.py:30` 仍是另一個 Office launcher 的歷史 evidence/vendor 預設；其他 checkout／服務不屬本輪盤點。表中來源可交給 C（原 #448）複核其他 owner，不能據此清理。原始 assets／舊 venv／舊 worktree／原模型與分支全部保留。

本輪只完成 #486 的本機依賴收編子項。D132 的 Windows／Linux、CI、清理／主線合併、索引改寫等大清單不因這個本機收據自動勾選。平台測試需要相應環境，清理／合併需要使用者決定；下一位處理者以 C issue 清單與使用者授權為準。這裡沒有用 UNKNOWN 代替本次可修的 runtime／測試問題。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: `codex/486-vendor-deps`，runtime 與四組 gate 綁 `eff11e47432a449d5abd5ba049c59d8e370d2c37`；其後只補 schema registry、原件驗證器與結果文件。最終 SHA 在 C 回條。未開 PR、未合併。
- Files changed: single config／repo dependency manifest、Python/Node version pins、Node devDependency lock、owned startup/config/helper、setup/check/export/collector、兩個 browser gate 的 owned paths、schema registry、inventory、本文與總索引。
- Commands run and results: 上列 pytest **121 passed / 1.13 s**；Node **478 passed / 0 failed / 0 skipped**；synthetic **49 checks / 16 PNG**；real **53 checks / 17 PNG / 0 page errors / 0 failed API**。no-allow architecture guard、launcher `bash -n`、`git diff --check` PASS。新 metadata schema 以 #486 正常登錄，無 guard bypass。
- Artifacts: LOCAL `$AMIDST_ARTIFACTS/demo-owned-v1/evidence/486/`：**48 payload files / 8,492,837 bytes**，另附 `EVIDENCE_MANIFEST.json` SHA-256 **`746236989d7e6a95980444db0a851d1ed2c7de7075278643207f573f62095de8`**。manifest 綁逐檔 hash、runtime commit／檔案 hashes、registry／原件驗證器 hashes。runtime 自有根目錄當次 `du -sk` 2,718,832 KiB；checkout `.venv` 722,588 KiB、Node package 8,736 KiB，環境由 locks 重建，raw 不進 Git。
- Verified: 離線 setup PASS；4,788 項 manifest hash/link PASS；repo Node 340 檔與原 pin 相符；Ollama 五個 blob digest/size PASS；35 個 installed distributions 全部在 uv lock；venv prefix 是 checkout、base prefix 在 owned runtime；外部 I/O 負向探針拒絕成功；four-source bootstrap／served PNG hashes PASS。另 `collect_demo_dependencies.py --verify-sources <copy-manifest.json>` 重新讀取 allowlist 的 **4,778 一般檔案＋9 相對 links = 4,787 項**，與 copy receipt 全部一致；只讀，原件未寫回。四組 #445 gate 全部使用新路徑；r005 R101 與 laptop 也有實際 RGB。
- Not verified: Windows/PowerShell 與 Linux 執行需要對應平台環境，本輪明確只有 Mac runtime profile；主機實體顯示 FPS 沒有量測資料，UNKNOWN。沒有執行新 inference 或 render，這是 saved-observation demo 的依賴遷移，不以它冒稱模型／研究驗收。
- Deviations, decisions and scope: 本機依賴收編沒有未修 runtime／測試問題。source/run/clock/hash 與 DRAFT/DEMO_DEFAULT、identity UNCONFIRMED、physical UNKNOWN 不升權。C 大清單的其他工作與 mainline 合併由使用者／對應平台 owner 接續；本 chat 的不開 PR、不合併、不清理分支指示保持有效。
