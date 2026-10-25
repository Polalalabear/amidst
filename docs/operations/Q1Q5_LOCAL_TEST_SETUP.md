# Q1–Q5 工作台本機測試：啟動方式、所需檔案與重現現況

- 日期：2026-10-25（Claude 協調者撰寫；啟動指令已在本機實測）
- 測試對象：8 秒工程動態場景（Codex Draft #207 → #209 → #211，A→B 盲區審查見 #216）。這是 **P1 工程預驗收**用的場景，**不是正式 r004 baseline**，結果不算正式成績（見 [驗收計畫](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。
- 路徑寫法：`$AMIDST_ARTIFACTS` 代表本機的 `~/amidst-artifacts`；`$BUNDLE` 代表 `$AMIDST_ARTIFACTS/q1q5-dynamic-baseline-v1_20261025`。

## 1. 結論

| 問題 | 答案 |
| --- | --- |
| 在使用者自己的 Mac 上能不能另外啟動一份？ | **可以**，指令見 §3（2026-10-25 已實測，服務正常回應）。 |
| 只靠 GitHub 能不能重現？ | **還不能**。可執行的程式是 8 個 Draft PR head 組合起來的（§4.1），沒有任何單一分支能直接啟動。影像、錄製、索引和模型也都不在 GitHub。 |
| 組員能不能在自己的電腦上測？ | **還不能**。設定檔寫死了使用者本機的絕對路徑，相依套件只有 macOS arm64 版，也還沒有符合組員格式（說明檔加 RETURN）的測試包。這些由 Codex 的 CX-10 處理（§6）。 |

## 2. 需要多少檔案

| 用途 | 內容 | 檔數 | 大小 | 在 GitHub 嗎 |
| --- | --- | --- | --- | --- |
| **A. 只看工作台**（錄製重播，不跑模型） | `delivery-source/`（工作台程式與前端） | 536（凍結清單） | 約 9.5 MB | 程式散在 8 個 Draft PR（§4.1），沒有單一分支 |
| | `dynamic-rgb-v2/safe/`（A、B 各 160 張，960×540，20 fps，共 8 秒） | 322 | 約 142 MB | **否** |
| | `run/prepared/`、`run/query/`（registry、索引、查詢設定） | 約 19 | 約 1 MB | **否** |
| | `inputs/recordings.json` 加上 1 份錄製檔 | 2 | 小 | **否** |
| | Python 3.12 環境（numpy、Pillow；依 `pyproject.toml`、`uv.lock`） | — | — | 套件清單在，環境本身不在 |
| **B. 重新跑模型** | 再加上 `runtime-deps/`（torch 2.6.0、torchvision 0.21.0 等，macOS arm64） | 15,268 | 約 437 MB | **否** |
| | RT-DETR 權重 `rtdetr_r18vd_dec3_6x_coco_from_paddle.pth`（SHA-256 `3ba8b5c9…66f0`） | 1 | 81 MB | **否**（可依官方來源重新下載，要使用者授權） |
| | RT-DETR 官方原始碼（upstream `df2a96c8`） | 71 | 0.5 MB | **否** |
| | Ollama 0.35.0 與 `qwen3:1.7b-q4_K_M`（digest `8f68893c…`） | — | 1.36 GB | **否** |
| **C. Codex 凍結的完整交付包** | `DELIVERY_MANIFEST.json` 列出的全部檔案 | 18,909 | 約 728 MB | **否** |

只看工作台（A）大約需要 **880 個檔、155 MB**。要和使用者本機「一模一樣」（含重跑模型，A 加 B）大約需要 **1.6 萬個檔、0.7 GB，加上 1.36 GB 的 Qwen 模型**。

## 3. 在使用者本機另外啟動一份（已實測）

不要動正在執行的 63408 服務。換一個沒被占用的埠，並用全新的私有目錄：

```sh
BUNDLE="$HOME/amidst-artifacts/q1q5-dynamic-baseline-v1_20261025"
TEST="$HOME/amidst-artifacts/wb-test-$(date +%Y%m%d-%H%M%S)"   # 必須是不存在的新目錄
lsof -nP -iTCP:63418 -sTCP:LISTEN                                # 有輸出就換一個埠
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BUNDLE/delivery-source/src" \
  "$HOME/Developer/amidst-claude/.venv/bin/python3" \
  "$BUNDLE/delivery-source/scripts/serve_q1q5_linked_workbench.py" \
  --rgb "$BUNDLE/dynamic-rgb-v2/safe/rgb.json" --rgb-sha256 0fe6de8c3bedcc31463fd219a51e191805e8b0872e719c0a96ec8bad49b848da \
  --registry "$BUNDLE/run/prepared/registry.json" --registry-sha256 3bba08d41d9e69337290c9753d703795b2e04f9d7b2d162854005c7bb533c623 \
  --runtime "$BUNDLE/run/query/runtime.json" --runtime-sha256 a4f974263a9a77a0d12a9364e42d337ea5d2f70ff3144090ef6bdc53f2169f2b \
  --recordings "$BUNDLE/inputs/recordings.json" --recordings-sha256 77b3443210b75d36012f85996dcf704c8ae882b8800e868ecd6d3f102176765c \
  --private-root "$TEST/private" --receipt "$TEST/receipt.json" --port 63418
```

- 開啟：`http://127.0.0.1:63418/workbench-v2/`；審核模式加 `?mode=review`。按 Ctrl-C 停止。
- 只看工作台時，`PYTHONPATH` 不必加 `runtime-deps`：實測只用到 numpy 與 Pillow，不載入 torch。
- 每個 `--*-sha256` 都會核對檔案，不符就拒絕啟動。這是正常的保護機制，不要改掉。
- 操作方式（照 Codex 的 README）：
  1. 直接播放。
  2. 查找可以輸入「哪幾台拍到人13:00:00到13:00:08」。
  3. 選一個片段播放，再用「回結果牆」選另一台鏡頭。
- 離線重播與真模型重現的指令，見 `$BUNDLE/README.md`。

## 4. GitHub 上拿不到的東西

### 4.1 程式：分散在 8 個 Draft PR

工作台需要的模組，只有在把下列 Draft head 組合起來時才齊全：

| 模組 | 來源 PR（head） |
| --- | --- |
| 工作台主線 `linked_workbench`、`linked_runtime`、`dynamic_rgb`、前端 | #207 `a8a38a74` → #209 `d6ad8089` → #211 `16bdba88` |
| `q1_search` | #157 `7b0ef332` |
| `q4_evidence` | #154 `e6eb30ba` |
| `q5_controller` | #169 `798f7371` |
| `ollama_runtime` | #174 `d9125b68` |
| `production_preflight` | #195 `d0ad8585` |
| `runtime_telemetry` | #203 `7fa4d4ed` |
| `baseline_runner` | #205 `a54c3945` |

精確的組合紀錄在 LOCAL 的 `$BUNDLE/DELIVERY_COMPOSITION.json`。Codex 的 CX-4（baseline 整合分支，D75）完成之後，才會有單一分支可以啟動。

### 4.2 資料、模型與環境：全部是 LOCAL

- 8 秒事件的 RGB 影像。重新產生要用 Blender 與 LOCAL 的 producer，Blender 版本 UNKNOWN。
- 索引、registry、查詢設定、錄製檔。用 `accept_q1q5_linked_baseline.py` 重跑可以產生，但需要 Ollama。
- `runtime-deps/`、RT-DETR 權重與原始碼、Qwen 模型。
- 工作台的審核資料庫 `review.sqlite3`，屬於執行狀態，不在凍結範圍。
- 依公開 repo 的規則，原始影像、錄製、權重和資料庫都不上傳 GitHub，只上傳程式、設定、文件與精簡收據。

## 5. 目前還不能交給組員的原因

1. **絕對路徑**：例如 `inputs/recordings.json` 的 `recording_root` 寫死了使用者本機的路徑，整包複製到別台電腦會找不到檔案。
2. **作業系統**：`runtime-deps` 是 macOS arm64 版。Windows 或 Intel Mac 必須另外安裝環境，目前沒有任何 Windows 的紀錄。
3. **沒有單一可執行來源**（§4.1）。
4. **沒有組員格式的包**：組員包要有說明檔和指定的 `RETURN/` 回交檔（D76）。

## 6. 讓組員也能自己測：CX-10 可攜測試包（Codex 負責）

| 要求 | 內容 |
| --- | --- |
| 單一資料夾或 ZIP | 只含「A. 只看工作台」需要的檔案（約 155 MB），另附可選的「模型重跑」說明 |
| 相對路徑 | 所有設定改用相對於包根目錄的路徑；啟動時重新核對 SHA-256，不符就拒絕 |
| 一鍵啟動 | macOS 用 `start.command`；如果要支援 Windows，另附 `start.bat` 並實測 |
| 環境 | 列出 Python 版本與安裝步驟（`uv sync` 或 requirements），只看工作台不需要 torch 和 Ollama |
| 說明檔 | `README.txt`，分「這份工作內容／要提交項目／操作／不要改」四段 |
| 回交 | `RETURN/測試回報_<姓名>_YYYY-MM-DD.csv`，逐項對照驗收標準 AC1–AC8，填 T、F 或「不確定」並寫理由 |
| 驗證 | 在一份乾淨的複本（不同使用者目錄）上實測啟動，附截圖；Claude 會再走一次 |

CX-10 完成之前，組員只能在使用者的電腦上，照 §3 測試。

## 7. 參考

- 驗收計畫：[Q1Q5_BASELINE_ACCEPTANCE_PLAN.md](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)
- 動態工程場景：`docs/engineering/Q1Q5_DYNAMIC_BASELINE.md`（#211）；A→B 盲區審查：#216
- 決定：D74–D77（#93）
