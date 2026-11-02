# DEMO-UI-F：P1 live 追蹤

範圍：#372、#387（D110-1）。採 #372 選項 (a)：目前後端搭配既有、唯讀 P1 safe bundle；原始包、錄製與素材不改。這是 SYNTHETIC 工程展示，不能當正式 r004、G4 核准或 AC7 通過。

## 綁定與 scope

後端 `RuleController.session_id` 的 preimage 原本就含 `tracking_scope`。bootstrap 現在提供 `runs[].tracking_scope_sha256`（未使用明確為 null）；前端以同一個鍵及 pin 重算 session hash，也核對回應的 scope pin。介面提案與確認在 #387。沒有修改契約、後端 hash 或決策語意。

`configs/q1q5/p1_live_tracking_scope.json` 明列 A、B、既有 `T_A_B` 與 B→A 的排除；來源是 P1 既有註冊與工程拓撲宣告，不讀 GT、劇本、renderer 軌跡、visibility 或 depth。scope bytes SHA-256：`e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8`。沿用既有 scope schema 的固定欄位；r004 專用兩欄明列 P1 不適用。

scope 保持 `PROPOSED`、`G4_approved=false`，須由操作者同時傳檔案和 hash 才啟用。後端只在記憶體產生帶 scope pin 的兩圖並重算既有 content pins，合成圖整體仍為 DRAFT。缺 scope 仍 fail closed，不從相機清單自動補權限。

## 啟動

先選定 LOCAL P1 v4 包。預期 `MANIFEST.json` SHA-256 為 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`，原 source commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`。bundle 內含 397 個不可變 payload、149437452 bytes（歷史 manifest 宣告；本次驗收另見 PR）。不建立副本、不重渲染、不跑模型。

從含本 PR 的 checkout 執行（Python ≥3.12）：

```sh
python3 -S scripts/start_q1q5_p1.py \
  --bundle "$P1_BUNDLE" \
  --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 \
  --state-root "$LOCAL_STATE_PARENT/live-run-01" \
  --tracking-scope "$PWD/configs/q1q5/p1_live_tracking_scope.json" \
  --tracking-scope-sha256 e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8 \
  --current-ui --no-open
```

`P1_BUNDLE` 須是原包的 canonical 絕對路徑；`LOCAL_STATE_PARENT` 須是既存、repo 外的 LOCAL 目錄，`live-run-01` 必須不存在。明傳 `--state-root` 後不在原包建立 STATE。缺省參數保持舊啟動流程。`SERVER.json` 記錄 scope pin、current-ui 開關與原包 provenance。

`--current-ui` 提供執行此 launcher 的 checkout 之 workbench-v2。搜尋彈窗須使用 FEAT-9 #385 的 UI 組成；本 PR 不改 FEAT-9 檔案。新 scope 的 graph pins 與舊錄製不同，因此此 live 模式不註冊舊錄製，也不預載 `?recording=`；可另外新增 live 錄製到 LOCAL state，保留完整 hash 綁定。

## 驗收

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_demo_live_tracking_t.py tests/q1q5/test_api.py
AMIDST_P1_BUNDLE="$P1_BUNDLE" uv run python -m pytest -q tests/q1q5/test_p1_live_tracking.py tests/q1q5/test_p1_workbench.py tests/q1q5/test_portable_pack.py
node --test frontend/workbench-v2/q-api.test.mjs
git diff --check origin/codex/q1q5-staging HEAD
```

LOCAL P1 測試明確 opt-in；未設 `AMIDST_P1_BUNDLE` 為 SKIP。APPEARANCE 與 OBSERVATION 都使用原凍結偵測索引的真觀測起點、真正的 q-api.mjs 驗 session binding。合法 `PARTIAL`／`ENDED_BY_LIMIT`、缺口與 UNKNOWN 均保留，不為展示改寫狀態。

瀏覽器驗收須操作「搜尋彈窗 → 追蹤 → 選起點 → 單畫面播放」，在 PR 記錄固定組成 heads、結果與 LOCAL 證據 hashes。#307 交付前架構守門為 NOT_RUN；#127、正式 r004 和完整 FEAT-5 彩排不屬此獨立優先項的完成宣告。
