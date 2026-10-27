# Q1–Q5 工作台本機測試：啟動方式、所需檔案與重現現況

- 日期：2026-10-25（Claude 協調者撰寫；啟動指令已在本機實測）；2026-10-27 更新：程式已整合進 staging `680ca35`（#231），組員可攜包 v4 已完成（#234）。
- 先看這兩份（只在 staging，連結用 SHA）：[Q1Q5_P1_START.md](https://github.com/Polalalabear/amidst/blob/680ca357a31b664bed3feb6a5284dcd7c5c0d94d/docs/operations/Q1Q5_P1_START.md)（P1 啟動與操作）、[Q1Q5_PORTABLE_PACKAGE_20261026.md](https://github.com/Polalalabear/amidst/blob/680ca357a31b664bed3feb6a5284dcd7c5c0d94d/docs/operations/Q1Q5_PORTABLE_PACKAGE_20261026.md)（可攜包 v4）。
- 測試對象：8 秒工程動態場景（Codex #207，已併入 staging；#209、#211 已關閉，內容由 #231 整合涵蓋；A→B 盲區審查見 #216）。這是 **P1 工程預驗收**用的場景，**不是正式 r004 baseline**，結果不算正式成績（見 [驗收計畫](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。
- 路徑寫法：`$AMIDST_ARTIFACTS` 代表本機的 `~/amidst-artifacts`；`$BUNDLE` 代表 `$AMIDST_ARTIFACTS/q1q5-dynamic-baseline-v1_20261025`。

## 1. 結論

| 問題 | 答案 |
| --- | --- |
| 在使用者自己的 Mac 上能不能另外啟動一份？ | **可以**，指令見 §3（2026-10-25 已實測，服務正常回應）。 |
| 只靠 GitHub 能不能重現？ | **程式可以，資料還不行**。可執行的程式已整合成單一 commit：staging `680ca35`（#231，§4.1）。影像、錄製、索引和模型仍不在 GitHub（§4.2）。 |
| 組員能不能在自己的電腦上測？ | **可以用可攜包 v4**（CX-10，#234；401 檔，MANIFEST SHA-256 `6e9a0a4c…`）：相對路徑、`start.command` 一鍵啟動、README.txt 四段加 `RETURN/` 回交檔，只需 Python 3.12+ 與瀏覽器。限制：Windows 未測；AC7 尚未通過，P1 回交表只供人工閱讀（D83），不能直接當 P2 正式發包（§5、§6）。 |

## 2. 需要多少檔案

| 用途 | 內容 | 檔數 | 大小 | 在 GitHub 嗎 |
| --- | --- | --- | --- | --- |
| **A. 只看工作台**（錄製重播，不跑模型） | `delivery-source/`（工作台程式與前端） | 536（凍結清單） | 約 9.5 MB | 是：staging `680ca35`（§4.1）；可攜包 v4 已內含同一整合 commit 的程式 |
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

### 4.1 程式：已整合進 staging `680ca35`

先前工作台需要把 8 個 Draft head 組合起來才齊全。[#231](https://github.com/Polalalabear/amidst/pull/231)（baseline 整合，已併入 `codex/q1q5-staging`，merge `680ca35`）把它們收成單一整合 commit：

| 項目 | 現況 |
| --- | --- |
| 整合 commit | staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`（#231） |
| 原 8 個 Draft | #207、#195、#203、#205、#157、#154、#169、#174 已併入 staging；#209、#211 關閉（內容由 #231 涵蓋，分支保留） |
| 可攜包 v4 的程式來源 | 整合分支 commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`，`SOURCE.json` 逐檔 hash；沒有 8 個 head 的 runtime overlay |
| 進 mainline | staging → mainline 的整合為 [#267](https://github.com/Polalalabear/amidst/pull/267)（Draft，未合併）；合併前 mainline 沒有這些程式 |

舊的 LOCAL `$BUNDLE/DELIVERY_COMPOSITION.json` 記錄的是 8 個 head 的舊組合，僅供歷史對照。

### 4.2 資料、模型與環境：全部是 LOCAL

- 8 秒事件的 RGB 影像。重新產生要用 Blender 與 LOCAL 的 producer，Blender 版本 UNKNOWN。
- 索引、registry、查詢設定、錄製檔。用 `accept_q1q5_linked_baseline.py` 重跑可以產生，但需要 Ollama。
- `runtime-deps/`、RT-DETR 權重與原始碼、Qwen 模型。
- 工作台的審核資料庫 `review.sqlite3`，屬於執行狀態，不在凍結範圍。
- 依公開 repo 的規則，原始影像、錄製、權重和資料庫都不上傳 GitHub，只上傳程式、設定、文件與精簡收據。

## 5. 組員測試的現況與限制

先前（2026-10-25）擋住組員測試的四個原因，現況如下：

| 原因 | 現況 |
| --- | --- |
| 絕對路徑 | 已解決：可攜包 v4 所有設定都是包根目錄的相對路徑，啟動時逐檔核對 MANIFEST |
| 作業系統 | 未解決：只需 Python 3.12+ 與瀏覽器，不需 torch／Ollama；macOS 實測，**Windows 未測、不附 `start.bat`**；也未宣稱第二個帳號或另一台實機驗收 |
| 沒有單一可執行來源 | 已解決：整合 commit（§4.1） |
| 沒有組員格式的包 | 已解決：README.txt 四段（這份工作內容／要提交項目／操作／不要改）加 `RETURN/` 回交檔 |

仍然成立的限制：

1. AC7（#127 全符合性）尚未通過；可播放、focused tests 或錄製 hash 相同不等於 PASS。
2. 可攜包是 P1 工程場景，不含正式 r004 資料、GT、producer、模型權重；G4 與正式 baseline 仍待。
3. P1 回交表只供人工閱讀，不進正式指標（D83）。

## 6. 組員可攜測試包：CX-10 v4（已完成，[#234](https://github.com/Polalalabear/amidst/pull/234)）

| 項目 | 內容（來源：[Q1Q5_PORTABLE_PACKAGE_20261026.md](https://github.com/Polalalabear/amidst/blob/680ca357a31b664bed3feb6a5284dcd7c5c0d94d/docs/operations/Q1Q5_PORTABLE_PACKAGE_20261026.md)） |
| --- | --- |
| 單一資料夾或 ZIP | `q1q5-p1-portable-v4-20261026/`：401 檔、149,501,743 bytes；ZIP 148,511,008 bytes |
| 完整性 | `MANIFEST.json` SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；397 個不可變 payload 逐檔 hash |
| 一鍵啟動 | macOS：`./start.command`；啟動時驗證 SHA、選未占用的 loopback 埠；詳見 [Q1Q5_P1_START.md](https://github.com/Polalalabear/amidst/blob/680ca357a31b664bed3feb6a5284dcd7c5c0d94d/docs/operations/Q1Q5_P1_START.md) |
| 回交 | `RETURN/測試回報_<姓名>_YYYY-MM-DD.csv`，逐項對照 AC1–AC8；只供人工閱讀（D83） |
| 驗證 | 在含中文與空白的 Shared 獨立根目錄實測啟動；Python 3.12.12 重建與原包 401 檔逐 bytes 相同 |
| 未涵蓋 | Windows、第二個帳號或另一台實機、AC7 全符合性 |

組員實際測試仍受 [#228 走查清單](Q1Q5_P1_WALKTHROUGH_CHECKLIST.md)的 AC1–AC8 範圍限制；P2 正式發包要等 AC7 通過與 G4。

## 7. 參考

- 驗收計畫：[Q1Q5_BASELINE_ACCEPTANCE_PLAN.md](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)
- 動態工程場景：`docs/engineering/Q1Q5_DYNAMIC_BASELINE.md`（#211）；A→B 盲區審查：#216
- 決定：D74–D77（#93）
