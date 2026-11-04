# 2026-11-04 Demo 運行手冊

- 狀態：依 `mainline/q1q5`@`97030cd`（tree `112229a`）於 2026-11-03 實測整理；攝影機時間標籤依 #404@`4fbd8c2`；後端候選快照 403 修正依 #403@`6d029ce`；複雜事件播放依 #399@`02afeb3`。實測結果與 P1／P2／P3 清單在 [#279](https://github.com/Polalalabear/amidst/issues/279) 的實際產出留言。
- 作者：Claude（Sonnet 5.5 / high）。對照：[`docs/agents/Q1Q5_DEMO_SCRIPT.md`](../agents/Q1Q5_DEMO_SCRIPT.md)（講稿與四條界線）、[`docs/agents/Q1Q5_BROWSER_ACCEPTANCE.md`](../agents/Q1Q5_BROWSER_ACCEPTANCE.md)、[`Q1Q5_DEMO_LAUNCH.md`](Q1Q5_DEMO_LAUNCH.md)。
- 範圍：桌機瀏覽器，視窗寬 ≥1280（建議 1440×900）。Demo 播放**預錄影片**；B-05a 是 live 但預期 fail-closed（D113）；複雜事件段**只有影像、無推論、無身分**。
- 本手冊不含 GT、劇本事件、真實路徑或標準答案；路徑一律用變數，不寫家目錄絕對路徑。

## 0. 三段一覽

| 段 | 內容 | 啟動 | 埠 | 資料來源 |
| --- | --- | --- | --- | --- |
| A | 錄製伺服器：監控牆、檢索彈窗、查找、B-05b 預錄切鏡、後台 | 第 2 節 | 8766 | RECORDED（P1 v4，SYNTHETIC） |
| B | B-05a live 追蹤：停在 A＋GAP，不切鏡 | 第 3 節 | 8765 | LIVE · SYNTHETIC（P1 v4，PROPOSED tracking scope；LIVE 是運作模式，素材仍是 SYNTHETIC） |
| C | 複雜事件播放 A4-1／B4-1（#399） | 第 4 節 | 8780 | LOCAL safe RGB，無推論 |

**A 與 B 必須是兩次獨立啟動**（帶 `--tracking-scope` 時不登錄錄製，`?recording=` 會被忽略；`p1_workbench.py:168`；scope 與 recording 綁定不同，不混在同一進程）。B-01／B-02／B-03／B-05b 在 A 做，B 只做 B-05a。

## 1. 事前檢查清單（demo 前一天與當天開場前各跑一次）

打 ✔ 才算過；任何一項不過，先看第 6 節備援。

1. **磁碟**：`df -g /` 可用 ≥ 9 GiB（低於 8 GiB 不啟動；啟動器本身也會拒絕）。複雜事件 server 啟動會把約 1.2 GB 的 PNG 全量驗證一次（不佔磁碟）。
2. **LOCAL 路徑存在且唯讀使用**：
   - P1 v4 包：`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/`（含 `MANIFEST.json`，pin `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`）。
   - 複雜事件資料根：`$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/`，只讀 `A4-1/safe`、`B4-1/safe`。**不要** `ls`、開啟或複製 `gt_private/`。
3. **Python ≥3.12**：`python3 --version`（2026-11-03 實測 3.14.7）。Node 可用：`node --version`。
4. **repo checkout 與已合併的 demo 修補**：`git rev-parse HEAD`、`git status` 乾淨。基準是 `97030cd`，之後預期依序合入 #403 → #400 → #404 → #399 → #401。**務必確認 #403 已在 checkout 內**：`git merge-base --is-ancestor 6d029ce9328ba922a252b851ae987314cbfd5b00 HEAD && echo 已含#403`（或其 merge commit 在 `git log --first-parent` 中）。合併後以 mainline 的實際 SHA 確認（上式回傳即含）；若不含，B-05a／B-05b 的決策證據讀取可能回 HTTP 403（見第 3.1 節與第 6 節）。#404（攝影機時間標籤）同理：`git merge-base --is-ancestor 4fbd8c2447b5e449cae7a508a7dcd74e57492fae HEAD`；未含則畫面沒有左上角標籤，不影響功能。
5. **埠沒被占**：`lsof -iTCP:8765 -iTCP:8766 -iTCP:8780 -sTCP:LISTEN`，應為空。被占就換埠（指令的 `--port`），不要殺不認得的程序。
6. **新的 state 目錄**：每次啟動 `--state-root` 必須是**不存在**的新路徑、父目錄存在，例如 `STATE_PARENT=$HOME/amidst-demo-state; mkdir -p "$STATE_PARENT"`，每次用 `$STATE_PARENT/run-$(date +%H%M%S)`。不要放進 P1 包內。**所有路徑都要用絕對、正規（無 `..`、無符號連結）的路徑**：2026-11-03 實測 `--state-root ../x` 這類相對路徑會直接 `DataIntegrityError` 起不來。
7. **瀏覽器乾淨**：用**新的瀏覽器 profile／無痕視窗**，或在 DevTools Console 執行
   `localStorage.removeItem('amidst.monitor-room.v1'); localStorage.removeItem('amidst.workbench-v2.track-map-float.v1')`。
   原因（2026-11-03 實測）：後台的速度、起點、顯示鏡頭、循環與選定事件，以及俯視圖的開／關與位置，都存在瀏覽器 localStorage；排練時設過「2×、只看 A」，主畫面下次開啟就只剩 1 台鏡頭。
8. **視窗**：桌機寬度 1440×900；瀏覽器分頁保持前景、不要被其他視窗蓋住或最小化（背景分頁的 rAF 降速，播放量測不可信）。關掉通知與螢幕保護，接上電源。
9. **不要需要 OpenAI key**：本 demo 不呼叫外部模型；外部推測開關預設關閉，保持關閉。

## 2. 段 A：錄製伺服器（監控牆、檢索、B-05b、後台）

段 A 有**兩個不同的入口，不要當成等價**：

| 入口 | 指令 | 能力 | 用途 |
| --- | --- | --- | --- |
| **A1 可查詢的 P1 服務** | `scripts/start_q1q5_p1.py` | 保留可查詢的 QAPI：檢索彈窗、q1 查詢、命中牆、後台都能用 | B-01～B-03、B-03b、D-01，以及 B-05b 的 UI 操作（#404 驗收用此入口跑過） |
| **A2 唯讀重播入口** | 根目錄 `start_demo.command`（`prepare_demo()` 用 `RecordedAPI` 包住 API，bootstrap 強制 RECORDED，只允許 recorded／artifact／media／frames） | **唯讀**：q1 查詢會被 `RECORDED_READ_ONLY` 拒絕，所以**不能**做 B-02／B-03 | #279（Codex 啟動檢查）實測 B-05b 5.10 s A／5.15 s B 用的就是此入口（清環境 `env -i`） |

A1 與 A2 不是已證明等價；只開其中一個，用同一個埠或不同埠都可（A2 範例用 8767）。**每個 terminal 各自 `export P1_BUNDLE=…` 並建立自己的新 state 目錄**（另開的 terminal 不會繼承變數，貼上指令前先確認 `echo "$P1_BUNDLE"` 非空）。固定 8765／8766／8767 是本手冊為了好記所做的調整（#279 實測用 `--port 0`）；開頁網址一律照終端機實際印出的埠。

**A1 啟動**（repo 根目錄）：

```bash
export P1_BUNDLE="/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試"
mkdir -p "$HOME/amidst-demo-state"
python3 -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$HOME/amidst-demo-state/rec-$(date +%H%M%S)" --current-ui --no-open --port 8766
```

**A2 啟動**（只在要照 #279 實測方式獨立展示 B-05b 時使用；另開 terminal、另一個新 state）：

```bash
export P1_BUNDLE="/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試"
mkdir -p "$HOME/amidst-demo-state"
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" PYTHONDONTWRITEBYTECODE=1 ./start_demo.command --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$HOME/amidst-demo-state/replay-$(date +%H%M%S)" --port 8767 --no-open
```

A2 的 launcher 會直接印出正確的 `?recording=2777741d96ac9aff5bffb2f61a4d2938` 網址，照印出的開。（#279 的完整命令另含 `uv run --no-project --offline …` 與 `UV_CACHE_DIR`；若本機沒有 uv 且系統 `python3` ≥3.12，上式即可，與 #279 的差異未另行驗證。）

A1 終端機印出網址後，開以下網址（**不要**用印出的 `?mode=review` 網址，那是審核視角；A2 照印出的網址）：

- 首頁（監控牆）：`http://127.0.0.1:8766/workbench-v2/`
- B-05b：`http://127.0.0.1:8766/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938`
- 備用錄製（AGENT_SEQUENTIAL）：`?recording=d4b67fd71caef6fb80fc9d92af544959`
- 後台：`http://127.0.0.1:8766/workbench-v2/admin.html`

結束：在該終端機按 Ctrl-C。

### 2.1 操作順序與講稿要點（對應 DEMO_SCRIPT）

| 步驟 | 操作 | 預期畫面 | 講稿要點（四條界線隨時適用） |
| --- | --- | --- | --- |
| B-01 | 開首頁，等 10 秒 | 監控牆 2 台（A、B）同一時鐘播放，每格左上角有來源時間標籤（見 2.2），頂列「LIVE · SYNTHETIC」或「RECORDED · SYNTHETIC」，標「2 台鏡頭 · SYNTHETIC」；播放量測 2 台每台約 18–20 Hz、掉格約 4%；每格左上角標籤如 `A · x.xx s`、`B · x.xx s`（來源時間，非牆鐘），2 格各自顯示 | 預錄畫面同一時鐘；沒有畫面的鏡頭標 MISSING，不是「沒人」 |
| B-02 | 點「檢索」，看彈窗，Esc 關閉；再開，**手動切到「查找」**（彈窗預設是「追蹤」）、person、0:00:00–0:00:08，開始檢索 | 彈窗有查找／追蹤、類別、顏色、特徵、解析方式、起訖時:分:秒；送出後只顯示載入面板（牆隱藏），進度條標「示意」 | 進度條是示意，不代表找到或沒找到 |
| B-03 | 命中牆出現後按「同步播放全部命中鏡頭」 | 只有 #1 A、#2 B；片段外標「命中片段外 · 凍結於最近合法影格」；每格「身分未確認」；同步播放時各格左上角各自顯示自己的來源時間（2026-11-03 實測起點 `A · 0.15 s｜B · 5.15 s`，A 的命中片段在 0.05–0.60 s 附近，播放中 A 前進、B 凍結在 5.15 s）；靜態代表畫面顯示代表觀測的時間（實測 `A · 0.15 s｜B · 5.20 s`，**B 的靜態代表畫面是 5.20 s，同步播放後凍結在 5.15 s，兩者不同是正常的**；代表畫面對應多個不同時間時顯示 `<鏡頭> · UNKNOWN`） | 條件相符的觀測，不是同一個人；身分 UNCONFIRMED |
| B-03b（可選） | 結束檢索，檢索 car | 停在載入面板，顯示 `NO_MATCH · 在已推論的影格中沒有找到；不代表目標不存在`；按「結束檢索」才回牆 | 「沒找到」≠「不在」 |
| B-05b | 開 B-05b 網址；按 **M** 或「俯視圖 (M)」開俯視圖；按「播放」讓它從 0 播到約 5.2 s；用時間軸停在 5.10 s、5.15 s | 左側「決策紀錄」逐步出現；5.10 s 單畫面是 A，**5.15 s 起是 B**（#17 4.25 s SEARCHING→SWITCHING＋SWITCH＋MATCH_STRONG；#18 5.15 s SWITCHING→PLAYING「畫面換成 B」）；俯視圖只有**一條虛線**；每個攝影機畫格左上角有半透明標籤 `<鏡頭> · <秒> s`：5.10 s 單畫面是 `A · 5.10 s`，5.15 s 是 `B · 5.15 s`；多鏡頭時兩格各自顯示（例：`A · 5.15 s｜B · 5.15 s`）；秒數顯示兩位小數；往回拖到 2.0 s，決策紀錄只剩 #0～#6 | 這是預錄、工程場景的核定圖，不是 G4、不是正式核定；虛線是「輔助預測（示意，非實際路徑）」；外部推測開關保持關閉，勾選只會顯示「外部推測不可用」 |
| D-01 | 開後台，在「預設事件播放」選錄製按「播放」，回主畫面；展示篩選 | 主畫面切到所選事件；沒有標題的事件顯示 ID 並標「尚無可讀名稱」 | 後台只選預錄事件、調播放，不改判斷 |

**示範後務必還原**：後台改過速度／顯示鏡頭，要在後台改回 1×、全部鏡頭，或清掉 localStorage（第 1 節第 7 項）。

### 2.2 預期畫面（B-05b，供對照）

- 載入後直接進單畫面（A，0.00 s），頂列 `RECORDED · SYNTHETIC`、「程式試用來源 · 排除正式評估」；俯視圖預設**關閉**，按 M 才出現。
- 5.10 s：A，無目標框（GAP，RGB 背景保留），左上角 `A · 5.10 s`。5.15 s：B，目標有框，左上角 `B · 5.15 s`；俯視圖 A→B 實線。
- 時間標籤：每個攝影機畫格左上角一個半透明標籤 `<鏡頭> · <秒> s`（兩位小數、截斷），多鏡頭時各格各自顯示；這是**來源時間**，不是牆鐘（牆鐘對應仍為 UNKNOWN）；來源時間未知則顯示 `<鏡頭> · UNKNOWN`，不會顯示 0 或空白。標籤在左上，俯視圖預設在右下，兩者不互相遮擋。
- 俯視圖開啟時在預設的 docked 位置（右側獨立欄位），不遮擋攝影機畫面（#400 修正；見第 7 節 P2-1）。**俯視圖重新載入後固定回到 docked 預設位置，不保留拖曳座標**；手冊只承諾預設位置不遮擋，拖到別處後的遮擋不在承諾內（可按「隱藏」或重新載入回預設）。

### 2.3 不展示 Q4 證據畫格；看候選前先關俯視圖

- **不要安排或宣稱現場展示 Q4「檢視證據影格」**。「檢視證據影格」按鈕只在候選有命中觀測時才出現；本次 demo 的兩份錄製（RULE_ONLY `2777741d…`、AGENT_SEQUENTIAL `d4b67fd7…`）所有候選（◆10–◆17）都是 `NO_PERSON_DETECTED`／`NOT_EVALUATED`、相符觀測 0，live 也沒有候選，所以**按鈕不顯示**。被問到時照實說：「此版錄製沒有命中證據，所以沒有證據影格可看；證據影格的程式路徑只用合成資料驗過，不是真實命中。」
- 進入 Q2 review 看「候選與證據」：#400（fc91d46 起）修正後，俯視圖 docked 開啟時 1440×900 下該側欄預期留在右側，不再退化成約 100 px。**#400 合併後仍要在 1440×900 開著俯視圖實際看一眼**側欄是否正常；若側欄仍被擠到下方，備援是先按「隱藏」關閉俯視圖，看完候選再按 M 重開。（修正前 #404 驗收曾實測 720×100，屬舊版行為，不代表新版必現。）

## 3. 段 B：B-05a live 追蹤（預期 fail-closed）

啟動（與段 A **不同進程、不同 state**，不同埠）：

```bash
python3 -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$HOME/amidst-demo-state/live-$(date +%H%M%S)" --tracking-scope "$PWD/configs/q1q5/p1_live_tracking_scope.json" --tracking-scope-sha256 e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8 --current-ui --no-open --port 8765
```

開 `http://127.0.0.1:8765/workbench-v2/`（另開的 terminal 要先 `export P1_BUNDLE=…`，見第 2 節）。此進程帶 tracking scope、不登錄錄製，與段 A 的 recording 綁定不同，所以**分進程**，B-01～B-03、B-05b 仍在段 A 做；段 B 只做 B-05a。一般首頁的 A／B 監控牆 RGB 取自 bootstrap，通常仍會顯示（#279 實測 recordings=0 仍有 A／B 兩台）；若看到空牆，多半是殘留的 recording 選擇（清 localStorage，第 1 節第 7 項），不是故障。

| 步驟 | 操作 | 預期畫面 | 講稿要點 |
| --- | --- | --- | --- |
| B-05a | 檢索 → 模式選「追蹤」→ person、0:00:00–0:00:08 → 開始檢索 → 在「選起點觀測」清單點第一列 → **拖時間軸到 5.10／5.15／5.20 s**（主要操作；連續按「播放」只是備案，見下方注意，可能要等很久） | 進入單畫面 A，左上角標籤 `A · x.xx s`（緩衝時標籤可能比時鐘慢一格，因為標籤顯示的是已換上的那一格）；**全程停在 A，不切到 B**（5.2 s 仍是 A＋GAP，只顯示當下狀態；2026-11-03 #404 驗收實測 5.20 s 的狀態文字是 `RETURNED_TO_ORIGIN`，時間軸為 GAP，左上角 `A · 5.20 s`，不切鏡——念狀態字時照實唸，語意仍是 A＋GAP fail-closed）；決策紀錄出現 TEMP_LOST／RETURNED_TO_ORIGIN；暫失時畫面標「緩衝中・前一來源影格」或不補框；時間顯示兩位小數；外部推測關閉 | 鏡頭關係圖尚未核准，系統不猜，所以離開 A 後不切到 B；沒偵測到≠不在畫面；這是預期的 fail-closed，不是故障 |

注意：
- **B-05a 連續播放非常慢**（2026-11-03 驗收實測：從起點按「播放」，約 30 s 牆鐘只前進到 1.55 s，之後約 3 s 前進 0.15 s），先前記載的「前約 4 s 較慢、之後 1×」不適用於該次驗收。所以 B-05a **主要操作是拖時間軸到 5.10／5.15／5.20 s**；連續播放只當備案，現場要播到 5 s 可能等很久。demo 前在目標機器實測一次。
- **拖時間軸後先等標籤**：拖到 5.10／5.15／5.20 s 後，等攝影機畫格左上角 A 的來源標籤換成目標秒數（如 `A · 5.20 s`）再開始解說；標籤還是舊秒數代表畫格還沒換上。（單純模式請先切回系統模式，等來源標籤換成目標秒數後，再切回單純模式解說；時間軸與「證據不足」不代表 RGB 已換上。）
- **當天又出現慢播時**：播放幾秒後按暫停，記下工作台「播放量測與素材說明」裡的 `raf_hz`、`max_raf_gap_ms`、`buffering_samples`／`raf_samples`、`request_ms`、`decode_ms`，貼回 [#279](https://github.com/Polalalabear/amidst/issues/279)（可區分回呼稀疏與等待解碼；診斷見該 issue 的 Codex 留言）。
- 起點 0.05 s 起播放前約 4 s 較慢（首次緩衝，來源時間 0.05→0.31 s）；彩排時先暖機，或開場先按一次播放。
- 講稿不要引用 2.5～3.4 s 的暫失時間：實測決策紀錄在 0.25 s 就出現 TEMP_LOST（見 P3-1）。
- 若出現 `TRACKING_SCOPE_MISSING` 或 `SESSION_BINDING`：直接跳到 B-05b，並說明 live 不切鏡。

結束：Ctrl-C。

### 3.1 #403：候選快照 HTTP 403 修正（後端）

- 問題（Codex 於 [#279](https://github.com/Polalalabear/amidst/issues/279) 啟動檢查中重現）：live 在未核准跨鏡頭圖的搜尋中，會重複產生同內容、同 hash 的候選快照；`q2_artifact` 原先要求該 hash 恰好出現一次，導致合法的決策證據請求回 **HTTP 403**。
- 修正（[#403](https://github.com/Polalalabear/amidst/pull/403)，`codex/demo-launch-fix`@`6d029ce`，只改 `src/amidst/q1q5/api.py`、`tests/q1q5/test_api.py`，無前端變更）：允許**內容完全相同**的重複項目；未知 ref、跨 session、同 hash 但內容不同仍被拒絕。修後候選快照 403→200，`candidates=[]`、`T_A_B / GRAPH_NOT_APPROVED`，D113 fail-closed 不變。
- 驗證責任：Codex 實測 mainline@`97030cd` 的 B-05a／B-05b 本身 PASS（5.20 s A＋GAP；5.10 s A／5.15 s B），#403 是修實際 HTTP 讀取錯誤；本手冊未獨立重跑 #403 測試。
- **Demo 前要確認**：#403 已合進 `mainline/q1q5`（第 1 節第 4 項）。合併後以 mainline 的實際 SHA 確認（`git merge-base --is-ancestor 6d029ce9328ba922a252b851ae987314cbfd5b00 HEAD`）；不含時遇到證據回 403 照第 6 節備援處理。

## 4. 段 C：複雜事件播放（#399，只有影像、無推論）

來源：PR [#399](https://github.com/Polalalabear/amidst/pull/399)（分支 `claude/demo-event-viewer`），head `02afeb3017ee94c635aac39b35fda26d4093cd15`。合併順序是 #399 先於 #401，**demo 時直接用合併後的 `mainline/q1q5`**，先核對 mainline 已包含該 SHA：

```bash
git checkout mainline/q1q5 && git pull --ff-only origin mainline/q1q5
git merge-base --is-ancestor 02afeb3017ee94c635aac39b35fda26d4093cd15 HEAD && echo 已含#399
```

**合併前備案**（#279 的 clean clone 是 single-branch，只有 `mainline/q1q5` 的 refspec，沒有 `origin/claude/demo-event-viewer`，所以不能用 `origin/…` 名稱）：

```bash
git fetch origin claude/demo-event-viewer
test "$(git rev-parse FETCH_HEAD)" = 02afeb3017ee94c635aac39b35fda26d4093cd15 && echo MATCH
git checkout --detach 02afeb3017ee94c635aac39b35fda26d4093cd15
git rev-parse --short HEAD   # 應為 02afeb3
```

沒印出 `MATCH` 就停，不要 checkout。備案已在 single-branch 的 scratchpad clone 實跑確認可照做（FETCH_HEAD＝完整 SHA，detach 後 `frontend/event-viewer/` 存在）；demo 後 `git checkout mainline/q1q5` 換回。

啟動：

```bash
node frontend/event-viewer/server.mjs --root "$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8" --port 8780
```

啟動時會全量驗證每張 PNG，**約 15 秒**（2026-11-03 實測 14.5 s；PR 自述 6.0 s），印出 `A4-1: OK`、`B4-1: OK` 和網址才算好，之前不要開頁。開 `http://127.0.0.1:8780/`。結束：Ctrl-C。

| 步驟 | 操作 | 預期畫面 |
| --- | --- | --- |
| C-1 | 事件選 **A4-1**，按「播放」，播 10 秒以上；再按「暫停」，拖時間軸，按「下一格／上一格」 | 4 鏡頭格狀（CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY、CAM_W1）；5 fps；10 s 對應 frame 50／249；跳格 0、停滯 0；每格左上角標籤 `CAM_… · 12.40 s`（frame 62＝12.40 s；frame 100＝20.00 s；frame 249＝49.80 s），暫停與逐格時標籤隨該格更新；頂列固定「ENGINEERING／只有影像、無推論、無身分」 |
| C-2 | 事件選 **B4-1**，同樣操作 | 5 鏡頭格狀（CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE）；frame 0–209；拖到 frame 105＝21.00 s；下一格×3 → 108＝21.60 s，上一格 → 107＝21.40 s；每格標籤同為 `CAM_… · <秒> s`（來源 frame÷5 fps，非牆鐘），例：frame 105 各格顯示 `… · 21.00 s` |

講稿要點（必講）：

1. 「這一段**只有影像，沒有任何推論**：沒有追蹤、沒有路線、沒有時間窗、沒有身分判斷。我們只是把複雜事件的各鏡頭畫面放在同一個時鐘上同步播。」
2. 「這些事件包含一個窗口內多次回到原鏡頭、長時間 LOST、重疊交接、新增鏡頭或路線——**目前的評分器與規則還判斷不了**，這就是第二條線（Line 2，複雜場景）要研究的：盲區區間假設、以負面證據剪枝、可達區域的假設束。研究路線與 D79 決策視窗見 [`docs/evaluation/Q5_DECISION_WINDOW_D79.md`](../evaluation/Q5_DECISION_WINDOW_D79.md)、[兩線計畫](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md)。」
3. 「資料是工程模擬（ENGINEERING），不是真實監視畫面；身分 UNCONFIRMED，物理通行 UNKNOWN。」

只能讀 safe 區：頁面與 server 只送 `A4-1|B4-1/safe/media/<camera>/NNNNNN.png`；`/gt_private/*`、`..`、符號連結一律被拒（2026-11-03 實測 `/gt_private/`、`/gt_private/x`、`/media/B4-1/../gt_private/a` 皆 404）。

## 5. 建議的整體順序（約 12–15 分鐘）

1. 開場（段 A 首頁）B-01 → B-02 → B-03（→ B-03b）。
2. B-05b 預錄切鏡（段 A）。
3. D-01 後台（段 A，可略）。
4. 切到段 B（B-05a），說明 live 為何停在 A。
5. 切到段 C 複雜事件：只有影像、無推論，帶出研究路線。
6. 收尾：四條界線；Q&A 時用決策紀錄與 DEMO_SCRIPT 的 D-06 用語表回答。

同時只開需要的伺服器；切段前按 Ctrl-C 關掉上一段（避免占埠與佔記憶體）。

## 5.1 demo 當天用哪一份 checkout

**待使用者決定**（手冊不寫死路徑）。選定的 checkout 必須同時滿足：

1. 含 `c64add89e94e1b6fda25ef5a71f9266b431e90f4` 之後的 `mainline/q1q5`（含 #403、#400、#404、#399、#401）：`git merge-base --is-ancestor c64add89e94e1b6fda25ef5a71f9266b431e90f4 HEAD && echo 已含`。
2. 工作樹乾淨（`git status`），沒有未提交變更；建議用專為 demo 準備的乾淨 checkout。
3. 若要展示單純顯示模式，還需含 #406 合併後的 mainline（`frontend/workbench-v2/simple-view.mjs` 存在）。
4. 啟動指令都在該 checkout 的 repo 根目錄執行（第 2、3、4 節）；`start_demo.command` 也在該根目錄，且要帶 `--bundle`、`--manifest-sha256`、`--state-root` 等參數，不是無參數雙擊即可。

## 6. 出錯時的備援

| 狀況 | 做法 |
| --- | --- |
| `OSError: [Errno 48] Address already in use`（P1 launcher 直接 bind，未包成 demo launcher 的 `PORT_IN_USE`） | 埠被占：`lsof -iTCP:<埠> -sTCP:LISTEN` 看是誰；是自己上一輪的進程就在該 terminal Ctrl-C，不認得的程序不要殺；或換 `--port`，開頁網址跟著換 |
| 段 A 起不來（`PORT_IN_USE`、manifest 驗證失敗、磁碟不足） | 換 `--port`；確認 P1 包路徑與 pin；清出磁碟（≥8 GiB）後重啟；仍不行→用 P1 包的 `./start.command`（RULE_ONLY 錄製，徽章 ENGINEERING／SYNTHETIC），或播預錄影片（第 8 節） |
| 播放卡頓（時鐘顯示不前進、量測 Hz 低） | 先確認分頁在前景；按一次「暫停」再「播放」；把格數降為 4（頂列 1／2／4／8 的 4）；關掉其他占 CPU 的程式 |
| 後台設定殘留（只剩 1 台、2×、從 0:01 起） | 清 localStorage（第 1 節第 7 項）後重新整理 |
| Console 出現 `q_physical_prediction`／`q_camera_map` 的 403 | review 模式每次換格都會出現；**已知、可忽略**，畫面不受影響（與候選快照 403 是不同問題，不是 #403 修掉的） |
| B-05a／B-05b 點決策或證據時出現 HTTP 403／證據載入失敗（候選快照） | 先確認 checkout 含 #403（第 1 節第 4 項、第 3.1 節）；不含則改用含 #403 的 mainline SHA 並重啟該段伺服器。現場來不及→跳到預錄截圖／影片，口頭說明；不可說成系統判斷結果 |
| 俯視圖蓋住畫面 | 按「隱藏」，或重新載入回 docked 預設位置（重新載入不保留拖曳座標）；#400 合併後預設 docked 位置不遮擋；時間標籤在左上，與預設在右下的俯視圖不互相遮擋 |
| B-05a 出現 `TRACKING_SCOPE_MISSING`／`SESSION_BINDING` | 口頭說明 live 追蹤這段壞了，直接跳到 B-05b；不可說成 live 已切鏡 |
| B-05b 錄製載入失敗 | 改開備用錄製 `d4b67fd71caef6fb80fc9d92af544959`；**旁白要照實說「模型逾時，由規則兜底」**；再不行→預錄截圖／影片，口頭說明不是現場切鏡 |
| 段 C 顯示 `UNAVAILABLE`／`INTEGRITY_FAIL`、0 張影像 | fail-closed：確認資料根路徑；不要手動繞過；改播預錄影片（第 8 節）並說明資料驗證未通過 |
| 瀏覽器掛掉 | 換新 profile 重開，從第 1 節第 7、8 項重來；server 不必重啟 |

預備品（demo 前一天產生，存 LOCAL、不 commit）：每段至少一張預錄截圖與一支約 1 分鐘的螢幕錄影；截圖檔名與 SHA-256 記在 #279 留言。

## 7. 已知問題

**講稿與風險注意事項（#404 驗收，2026-11-03）：** (1) 不展示 Q4 證據畫格，見 2.3；(2) 看 Q2 候選時確認側欄沒被擠到下方（#400 後預期正常，異常才先關俯視圖），見 2.3；(3) 播放與量測期間分頁保持前景，分頁被隱藏時畫格解碼會降速並卡在「取得來源畫面…」；(4) 時間標籤在左上，B 鏡頭 5.15–5.20 s 時目標框貼左邊緣，標籤會蓋住框的左上角一小塊，不影響讀時間。（2026-11-03 實測；P1＝demo 當天會出錯或誤導觀眾）

**P1：無。** 以下均已有 workaround，列在這裡是因為會影響現場。

| 編號 | 級別 | 問題 | 歸屬 | workaround／處理 |
| --- | --- | --- | --- | --- |
| P2-1 | P2 | 開啟的俯視圖預設蓋住攝影機畫面右下約 19%（1440×900，單畫面） | Claude（FEAT-9） | [#400](https://github.com/Polalalabear/amidst/pull/400)（開啟時保留右側欄，實測無重疊；重新載入固定回 docked 預設位置、不保留拖曳座標）；合併後以預設位置為準，若 #400 尚未含在 checkout 則按「隱藏」；#404 的攝影機時間標籤在畫格左上，俯視圖預設在右下，兩者不互相遮擋 |
| P2-2 | P2 | 後台設定與俯視圖開關存在 localStorage，排練後殘留會改變主畫面（只剩 1 台鏡頭、2×） | Claude（FEAT-9） | 第 1 節第 7 項；現場用新 profile |
| P2-3 | P2 | live（帶 tracking scope）進程不登錄錄製、與段 A 的 recording 綁定不同；首頁牆通常仍有 A／B RGB，但殘留 recording 選擇可能造成空牆 | Codex（launcher／scope） | 分進程；B-01～B-03、B-05b 在段 A 做，段 B 只做 B-05a；空牆先清 localStorage |
| P2-4 | P2 | UI-07 8 台：LOCAL 只有 2 台真實 RGB，沒有 8 台資料；未量 | Codex（資料） | 口頭只說「2 台」；不宣稱 8 台流暢 |
| P3-1 | P3 | 講稿寫 live 暫失約 2.5～3.4 s，實測決策紀錄 0.25 s 起即 TEMP_LOST | Claude（腳本文字） | 旁白不引用秒數 |
| P3-2 | P3 | 腳本寫「載入錄製後直接進單畫面＋俯視圖」，實測俯視圖預設關閉（設計：預設不蓋鏡頭） | Claude（腳本文字） | 按 M 開啟 |
| P3-3 | P3 | 外部推測不可用時，圖例仍列「外部模型推測（非系統判斷）」一行，勾選旁註「外部推測不可用」 | Claude（FEAT-9） | 旁白說明未接外部模型 |
| P3-4 | P3 | live 播放前約 4 s 較慢（首次緩衝） | Codex／Claude | 開場先預播一次 |
| P2-5 | P2 | demo 錄製沒有帶命中觀測的候選，Q4「檢視證據影格」按鈕不顯示 | 資料 | 不展示、不宣稱，見 2.3 |
| P2-6 | P2 | （舊版行為）俯視圖 docked 開啟時 Q2 review「候選與證據」側欄被擠到下方約 100 px | Claude（#400 fc91d46 起已修） | #400 合併後預期不再發生；現場仍看一眼，異常才先按「隱藏」 |
| P3-7 | P3 | review 模式換格時 console 403（`q_physical_prediction`／`q_camera_map`） | 未追 | 已知、可忽略 |
| P3-6 | P3 | 後台關閉「循環」後主畫面播到 7.99 s 就停住，但按鈕仍顯示「Ⅱ 暫停」；重啟伺服器後第一次載入，牆要約 6 s 才開始出畫面（冷快取） | Claude／Codex | 開場前先載入一次暖機；循環保持勾選（開／關／重新勾選已實測，設定會寫入並生效） |
| P3-5 | P3 | 複雜事件 server 啟動 14.5 s（PR 自述 6.0 s） | Claude（#399） | 提前啟動，見 `A4-1: OK／B4-1: OK` 再開頁 |

## 8. Demo 結束後：錄製完整影片

目的：留一份完整、可重播的 demo 影片（LOCAL，不 commit）。

1. **開錄前**：做完第 1 節檢查；解析度固定 1440×900（或整個螢幕 1920×1080）；關閉通知；游標顯示開。
2. **錄影工具**：macOS 螢幕錄影（`Shift-Cmd-5` →「錄製選取部分」→ 框住瀏覽器視窗；選項勾「顯示滑鼠點按」；麥克風選旁白用的輸入）。輸出存到 `$HOME/amidst-artifacts/demo-recording_20261104/`（LOCAL，新目錄）。
3. **段落分段錄**（方便剪輯與重錄）：01 段 A（B-01～B-03）、02 B-05b、03 後台、04 B-05a、05 複雜事件 A4-1、06 複雜事件 B4-1。每段開錄前重啟對應伺服器並清 localStorage，結束後 Ctrl-C。
4. **每段旁白照 DEMO_SCRIPT 與第 2–4 節**；複雜事件段必說「只有影像、無推論」。
5. **錄完驗證**：逐段播放確認可看、時間碼連續、沒有露出 `gt_private`、終端機密鑰或家目錄路徑。
6. **記錄**：`shasum -a 256` 每支影片，檔名、大小、SHA-256 與錄製日期寫入 #279 留言，**標 LOCAL**；不要把影片放進 repo。
7. **收尾**：Ctrl-C 關閉所有伺服器；`lsof -iTCP:8765 -iTCP:8766 -iTCP:8780 -sTCP:LISTEN` 應為空；刪除 `$HOME/amidst-demo-state/` 下本次的 state 目錄；`git checkout mainline/q1q5` 換回主線。

## 9. 本手冊自身的驗證範圍

- 已實測（2026-11-03，內建瀏覽器，桌機 1440×900，前景、rAF 約 60 Hz）：段 A 全流程、B-05a、段 C 兩個事件的播放／暫停／拖時間軸／逐格、後台、node `frontend/workbench-v2/*.test.mjs` 333／333、`git diff --check`。
- 未驗證：Chrome／Safari、窗寬 <1280、8 台鏡頭流暢度、俯視圖修補 PR 的跨解析度表現、完整影片錄製流程（第 8 節是步驟，未實錄一次）。

## 10. 單純顯示模式（#406）

模擬真實使用情境：只看攝影機畫面，不顯示任何標註。與「系統模式」（本手冊其他各節的畫面，顯示全部標註，供修正系統用）共用同一份資料與狀態；切換**不重載、不重置播放位置**，鏡頭切換點完全沿用系統模式（D113：B-05b 在 5.15 s 切到 B；B-05a live 是 A＋GAP，不切鏡）。僅支援桌面（1440×900）。

### 10.1 怎麼切換

- **按鈕**：頂列的「系統模式｜單純顯示」切換鈕（單純模式下頂列只剩這顆、「檢索」與「結束檢索」）。
- **網址直接開**：在任何頁面網址加 `view=simple`（回系統模式用 `view=system`）。例：
  - B-05b：`http://127.0.0.1:8766/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938&view=simple`
  - 監控牆首頁：`http://127.0.0.1:8766/workbench-v2/?view=simple`
  - B-05a live：`http://127.0.0.1:8765/workbench-v2/?view=simple`
- **預設與記憶**：預設系統模式；最後一次按鈕的選擇記在瀏覽器 localStorage（`amidst.workbench-v2.view.v1`）。網址的 `view=` 優先於記住的選擇。演練後若要清掉，併入第 1 節第 7 項的 `localStorage.removeItem(...)` 清單。

### 10.2 畫面上會看到／不會看到

| 會看到 | 不會看到 |
| --- | --- |
| 攝影機影像（監控牆、單畫面追蹤）；播放、影格、速度、時間拖曳軸；「檢索」「結束檢索」；選起點觀測的清單；右上角半透明「證據不足」（見 10.3） | OBS／目標框；左上角來源時間標籤；俯視圖與其開關；候選與證據側欄；假說帶／時間軸；決策紀錄；狀態徽章與 OBSERVED／INFERRED／MISSING／UNKNOWN 等文字；圖例、頂部來源列與 SYNTHETIC 條、後台與其他連結、除錯資訊 |

單純模式不新增、補齊或推測任何畫面；緩衝時不顯示「緩衝中」字樣，畫面維持前一個合法影格；缺圖時格內的 `MISSING · …` 等原始文字也隱藏，只由右上角「證據不足」提示（不補圖）。「選起點觀測」清單仍帶觀測 ID（那是選目標的操作，未改）。

### 10.3 「證據不足」何時出現

右上角一行半透明小字，不彈窗、不遮畫面中央。只看**目前可見的畫面**，且只用系統模式已有的狀態：

- 事件播放（Q2）：當前時間點是 GAP／UNKNOWN／fail-closed（含決策資料不完整）、回應有錯誤，或畫面格是 MISSING；有觀測的 ON_CAMERA 時間點不出現。
- 找相機（Q1）：回應有錯誤，或畫面格是 MISSING。
- 監控牆：畫面格（tile）是 MISSING；只讀牆自己，不會讀到先前事件播放殘留的 GAP。
- 暫停中畫格被換掉（MISSING→READY）時，提示在新畫格實際上場後立即更新；還在背景解碼、未上場的畫格不計。

| 情境 | 單純模式畫面 |
| --- | --- |
| B-05b 5.10 s | A 畫面＋「證據不足」（系統模式此時是 GAP，無目標框） |
| B-05b 5.15 s | 切到 B，無框、無標籤、無「證據不足」 |
| B-05b 5.20 s | B |
| B-05a live 5.20 s | 停在 A＋「證據不足」（A＋GAP fail-closed，不切鏡） |

### 10.4 demo 時兩種模式各展示哪些段落

- **系統模式**（預設，顯示全部標註）：B-01～B-03、B-03b（監控牆、檢索、命中牆）、B-05b 與 B-05a 的**解說**（決策紀錄、俯視圖、時間標籤、狀態字都在這裡講）、D-01 後台、段 C 的證據說明與第 7 節的問題解答。需要看標註或修正系統時一律用它。
- **單純顯示**：先用系統模式講完一遍後，在 B-05b（5.10／5.15／5.20 s）與 B-05a live（5.20 s）各切一次（B-05a 同樣**拖時間軸**到 5.10／5.15／5.20 s，不要等連續播放；單純模式請先切回系統模式，等來源標籤換成目標秒數後，再切回單純模式解說；時間軸與「證據不足」不代表 RGB 已換上），展示「使用者實際只會看到什麼」：畫面在 5.15 s 從 A 換成 B；live 停在 A，右上角只有「證據不足」。監控牆（B-01）也可切過去給觀眾看純畫面。命中牆（B-03）在單純模式的實景未實測，不建議在單純模式展示。
- 切換時**不要**重新整理頁面；用頂列按鈕切，播放位置才會保留（網址帶 `view=simple` 開新頁則是重新載入）。

### 10.5 驗證範圍

2026-11-03 在內建瀏覽器 1440×900 下實測：B-05b 5.10／5.15／5.20 s、B-05a live 5.20 s、監控牆，兩種模式各一組截圖（LOCAL，SHA-256 在 [#406 留言](https://github.com/Polalalabear/amidst/pull/406#issuecomment-6600987279)）。未實測：手機版、命中牆（B-03）的單純模式畫面、Q4 證據畫格、非 Chrome 系瀏覽器。

## 8.1 一鍵啟動與事件選單

第 2、3、4 節的三段指令保留作為備案；這一節是同樣三段的一次啟動（不改語意：同樣的參數、manifest 與 tracking-scope 的 sha256、各進程各自新的 state 目錄；A 與 B 仍是兩個獨立進程）。

```bash
./start_all_demo.command
```

（可在 Finder 雙擊。）腳本依序做：

1. 檢查 Python（≥3.12）、node、P1 包與 `MANIFEST.json`、CX-7 資料根、tracking scope 檔、磁碟 ≥8 GiB、三個埠沒被占用。**任何一項不過就清楚報錯並停止，不啟動任何進程**；埠被占用時印 `[Errno 48]`，不會去關別人的程序。
2. 啟動段 A（埠 8766，`$STATE_PARENT/rec-<時分秒>`）、段 B（埠 8765，`$STATE_PARENT/live-<時分秒>`，帶 tracking scope）、段 C（埠 8780，唯讀複雜事件 server，約 15 秒全量驗證）。日誌在 `$STATE_PARENT/logs-<時分秒>/`。
3. 全部 ready 後印出工作台網址並開瀏覽器：`http://127.0.0.1:8766/workbench-v2/?ev=wall&ev_live=8765&ev_cx=8780`。
4. 在該視窗按 Ctrl-C 會關掉三個子進程；任何一個子進程中途結束也會報錯並收掉其餘進程。

預設路徑可用環境變數覆蓋：`P1_BUNDLE`、`CX7_ROOT`（預設 `$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8`）、`STATE_PARENT`（預設 `$HOME/amidst-demo-state`）、`PYTHON`（預設 `python3`）、`PORT_REC`／`PORT_LIVE`／`PORT_CX`、`NO_OPEN=1`（不自動開瀏覽器）。不需要、也不讀取 OpenAI key。

### 事件選單（工作台上方列「事件」）

| 事件 | 呈現方式 | 講者說明（選單下的一行） |
| --- | --- | --- |
| 監控牆 | 本頁 | B-01：A、B 同一時鐘預錄畫面；沒畫面標 MISSING，不是「沒人」 |
| Q1 找相機 | 本頁（按「檢索」→「查找」） | B-02／B-03：條件相符的觀測，不是同一個人，身分 UNCONFIRMED |
| B-05b 預錄切鏡 | 本頁（重新載入並帶 `?recording=2777741d…`） | 5.10 s 是 A、5.15 s 起切到 B；虛線是輔助預測；不是 G4 |
| B-05a live 追蹤 | iframe 內嵌埠 8765 的工作台 | 預期 fail-closed：全程停在 A，5.20 s 仍是 A＋GAP，不切鏡 |
| 複雜事件 A4-1／B4-1 | iframe 內嵌埠 8780 的唯讀 event-viewer | 只有影像、無推論、無身分；A4-1 frame 62＝12.40 s、frame 100＝20.00 s；B4-1 frame 105＝21.00 s |

- 本頁事件以重新載入切換（乾淨狀態）；跨埠事件以 iframe 內嵌，所以**不需要 CORS**，也不改它們的資料來源與讀取範圍：event-viewer 仍只讀 `A4-1|B4-1/safe/media/<camera>/NNNNNN.png`，`gt_private/`、`..`、符號連結一律 404。埠只收 1024–65535 的整數、主機固定 `127.0.0.1`；event-viewer 另加 `frame-ancestors http://127.0.0.1:*`，只允許 loopback 頁面內嵌。
- 系統／單純兩種模式對所有事件生效。單純模式只剩攝影機畫面與播放控制；複雜事件沒有任何推論，所以右上角固定顯示半透明「證據不足」。講者說明在單純模式不顯示。顯示方式由上層工作台以 `postMessage` 傳給 iframe（只接受來自上層視窗、loopback 來源、值為 `system`／`simple` 的訊息）。
- 啟動腳本沒帶某一段的埠時（例如直接開 8766 網址），該事件在選單中標「（未啟動）」且不能選。
- 驗證：`node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs`。

### 查看／追蹤模式（事件選單旁的兩組按鈕）

- **查看**：所有攝影機畫面一次全部顯示（沒有決策）。B-05b／B-05a 的查看是 A、B 兩台同時鐘；A4-1／B4-1 的查看就是唯讀 event-viewer。
- **追蹤**：只用系統既有的、非 GT 的 Q2 決策與切鏡時點（B-05b 錄製、B-05a live），可在「單畫面鎖定」（畫面跟著決策換鏡）與「多畫面」（全部畫面，目前追蹤所在的鏡頭加框並標「目前畫面」）之間切換。B-05a 的 5.20 s 仍是 A＋GAP、不切鏡；單純模式在證據不足時右上角顯示「證據不足」。
- **A4-1／B4-1 的追蹤**：#118 索引與 CX-8 RULE_ONLY 還沒產生任何系統追蹤輸出（輸出格式 UNKNOWN），所以顯示「追蹤結果尚未產生（需 #118／CX-8 RULE_ONLY）· UNKNOWN」，不載入畫面、不模擬切鏡；單純模式只剩右上角「證據不足」。查看模式照常可用。
- 監控牆與 Q1 只有查看（追蹤從「檢索」開始）。
- 兩組模式都可以和系統／單純疊加。
- **之後接 CX-8 輸出要改哪裡**：追蹤模式的資料入口集中在 `frontend/workbench-v2/tracking-source.mjs`。輸出格式確定後，只在該檔把 `a41`／`b41` 由 `NOT_PRODUCED` 改為 `AVAILABLE` 並提供讀取；`event-menu.mjs` 只問 `trackingStatus()`；追蹤畫面本身（單畫面／多畫面）要另外為複雜事件提供追蹤版面（目前只有 B-05a／B-05b 沿用工作台的 Q2 播放）。安全邊界不變：不得用劇本、情境卡的計畫時刻、GT、渲染軌跡、可見性或深度來產生切鏡。

### 演示時間（虛擬世界時間）標示

- 所有攝影機畫格左上角標籤第一行是 `<鏡頭> · 2026-11-01 14:00:12.40（UTC+8）`，第二行（次要，系統模式）是 `+12.40 s · DECLARED_DEMO_CLOCK`。**這是宣告的 demo 時鐘（起點 + 來源時間），不是真實世界時間**；本節以上各處寫的 `A · 5.15 s` 現在是第二行的 `+5.15 s`。工作台的目前時間顯示、時間軸的 tooltip 也用同一時鐘；單純模式只留畫格角落的「鏡頭 · 時間」與播放列的演示時間，其餘標註隱藏。
- 時鐘來源只用各 run 已宣告的設定：A4-1＝`configs/q1q5/clocks/r004_a4_v1.json`（2026-11-01 14:00 Asia/Taipei）、B4-1＝`r004_b4_v1.json`（14:10 +08:00）、P1 v4 的 B-05 事件用該 run 的 `clock_mapping`（目前 2026-11-01 13:00 +08:00）。找不到宣告的就顯示 `UNKNOWN`，不假設日期；不用牆鐘、GT 或渲染時間。
- 檢索對話框的開始／結束可以輸入演示時間（`2026-11-01 13:00:08`）或經過時間（`0:00:08`），在前端換成同一個整數來源 µs，**後端 API 契約不變**；下方一行顯示兩種表示的對照。沒有宣告時鐘的來源只能輸入經過時間。
- 複雜事件的資料根維持可設定（`CX7_ROOT`／`--root`），之後新 run 的路徑換上即可；新 run 的時鐘要在 `frontend/event-viewer/runs.mjs` 與 `configs/q1q5/clocks/` 加上宣告（測試會逐欄比對）。
