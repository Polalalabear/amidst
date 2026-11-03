# CX-7-T 事件 run／safe bundle checker

狀態：測試工具已實作；production contract **UNSELECTED**。這份文件不是
safe bundle、G4、渲染收據或劇本的新權威 schema。#308／#351 全部仍為
PROPOSED，U8 尚未核定；#326 尚未交付已凍結 v2 劇本。

`scripts/check_event_run_bundle.py`（版本 `cx7t-synthetic-v1`）只讀明示輸入。
未提供選項及其 bytes SHA，或選項不是明示 TEST-ONLY projection，會回傳
`FAIL / CONTRACT_UNSELECTED`、exit 1。正式 wire decoder 必須在對應契約及
凍結來源核定後另行接入，不能把本文件的 fixture shape 當成採用。

## 可重跑檢查

議題 #311 指定的原命令如下。正式依賴尚未到位，前兩個命令現階段預設
fail closed，不能當作真實 G4 或渲染驗收通過。

```sh
python scripts/check_event_run_bundle.py --profile r004-a4b4 --bundle <LOCAL run 目錄> --receipt docs/engineering/R004_EVENT_RUNS_RECEIPT.json
python scripts/check_event_run_bundle.py --profile l2 --bundle <LOCAL run 目錄> --receipt <複雜事件渲染收據>
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_event_run_bundle.py
```

本 repo 實際執行 Python 使用 `uv run python`。已有環境可用以下離線命令：

```sh
AMIDST_REQUIRE_IMPL=1 uv run --no-project --offline --no-cache --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python -m pytest -q tests/q1q5/test_check_event_run_bundle.py
```

這是 LOCAL 工具環境路徑，不是 fixture／資料來源或發布輸入。測試本身只用
標準庫產生 4×4 RGB PNG 與合成 JSON，沒有 Blender、原始影片或資料集 bytes。
`l2` 每台 5 格；`r004-a4b4` 每台 250／210 格，保留 D89 的 50／42 秒及
既有 5 fps，沒有為縮小 fixture 改 fps 或放過缺格。

## TEST-ONLY projection

測試在 pytest 的暫存 `SYNTHETIC/` 內建立 `bundle/safe_bundle/`，以及該
bundle 外的 `contract.json`、`receipt.json`、`frozen.json`、
`authorization.json`、`g4.json`。這些不是 production 版本欄位。

合成 CLI 正例需另外傳入：

```sh
uv run python scripts/check_event_run_bundle.py --profile l2 --bundle <SYNTHETIC/bundle> --receipt <SYNTHETIC/receipt.json> --contract-options <SYNTHETIC/contract.json> --contract-sha256 <contract.json完整bytes的SHA-256>
```

選項必須為 `fixture_role=SYNTHETIC_ONLY`、
`projection=SYNTHETIC_EVENT_BUNDLE_V1`，並 pin 渲染收據 bytes、外部合成
凍結計畫、授權來源、G4 收據（r004 必要）。授權與 G4 要互相綁定同一
凍結計畫、圖與收據 pin。producer 單獨寫 `APPROVED` 不夠；缺 G4 時回
`G4_RECEIPT_MISSING`。合成 source ref 是 `SYNTHETIC:D-CX7T`，不冒充真實
checkpoint 留言或已採用 D 決策。

即使全部機械檢查通過，也只回 `SYNTHETIC_VALID`、exit 0，且固定回傳：

```json
{"authority_verified": false, "render_authorized": false, "formal_run_allowed": false, "production_contract": "UNSELECTED"}
```

測試的 `frozen.json` 只模擬未來已核定劇本可提供的 run／camera／duration
scope，並非 #326 的凍結輸出；l2 不寫死實際鏡頭數或時間。正式未知格式、
未凍結劇本、未核 U8 與真實人類授權仍不能由這個 projection 解除。

## 八項檢查及邊界

1. `source_duration_us` 由既有 `q-demo.clock-mapping.v1` 讀取；fps 由
   run 的 sampling 宣告讀取並比對外部合成凍結 scope。既有 clock schema
   不含 fps，所以不加入新 clock 欄位。完整格數須為整數，每台格號從 0
   連續到 duration×fps−1；檔案缺失、重複格號或不同 fps 均拒絕。
2. safe manifest 列出的每個 regular file 都核對實際 bytes SHA-256；
   frame row 再對其 pin。實際目錄多出的未列檔、漏列 PNG、symlink、
   逃出 root 的路徑、重複 JSON key、非有限 JSON 數值都拒絕。每檔最多
   16 MiB；讀取不跟隨 leaf symlink。工具只適用靜態離線輸入，不實作
   跨多檔的原子快照，呼叫方必須避免檢查期間修改輸入。
3. 重用既有 `ClockMapping.from_document` 驗證 timezone、wall_origin、
   t0_us、duration、content hash 及 run binding；兩 run 不可共用 clock ID。
   不把 self hash 當成人類核准。
4. r004 從 #238 的既有 D84 收據讀完整 catalog SHA，並先核對該收據
   bytes pin `3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5`。
   D89 的 A4-1 50 秒、B4-1 42 秒與 5 fps 固定檢查。合成 case 每 run
   只有兩台 placeholder camera，不宣稱重現正式 A4／B4 camera scope。
5. safe 實際檔名及每個 JSON 的巢狀 key 檢查 trajectory、visibility、depth、
   actor、script、GT／ground truth 樣式；manifest／clock／frame ref
   及任意巢狀 ref／path／filename 值必須是 safe root 內的正規相對路徑。
   private 目錄不掃描、不開檔。CLI 接受相對輸入路徑，只轉 absolute，
   不以 resolve 消除 symlink 檢查。
6. r004 的外部 G4 合成收據必須存在且 pin、圖及凍結 scope 相符；
   不依 producer 的 `APPROVED` 自行產生 authority。
7. 渲染收據必須引用同一凍結計畫 hash 與外部授權來源；缺一拒絕。
   合成計畫 hash 是 TEST-ONLY seam，不替 #310／#326 決定正式 hash preimage。
8. 前後 `df -k` 都必須是明確 1024-blocks 單筆紀錄。Available 各自至少
   `8 × 1024³` bytes，少 1 KiB 即拒絕；缺失或多筆歧義也拒絕。

不執行原資產 hash、渲染、推論、索引、全套測試、#127 kit 或正式驗收。
#307 尚因 authority pin 衝突 blocked-user，架構守門為 NOT_RUN。
