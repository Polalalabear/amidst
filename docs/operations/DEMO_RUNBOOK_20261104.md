# 2026-11-04 Demo 運行手冊

- 狀態：依 `mainline/q1q5`@`97030cd`（tree `112229a`）於 2026-11-03 實測整理；複雜事件播放依 #399@`c519d21`。實測結果與 P1／P2／P3 清單在 [#279](https://github.com/Polalalabear/amidst/issues/279) 的實際產出留言。
- 作者：Claude（Sonnet 5.5 / high）。對照：[`docs/agents/Q1Q5_DEMO_SCRIPT.md`](../agents/Q1Q5_DEMO_SCRIPT.md)（講稿與四條界線）、[`docs/agents/Q1Q5_BROWSER_ACCEPTANCE.md`](../agents/Q1Q5_BROWSER_ACCEPTANCE.md)、[`Q1Q5_DEMO_LAUNCH.md`](Q1Q5_DEMO_LAUNCH.md)。
- 範圍：桌機瀏覽器，視窗寬 ≥1280（建議 1440×900）。Demo 播放**預錄影片**；B-05a 是 live 但預期 fail-closed（D113）；複雜事件段**只有影像、無推論、無身分**。
- 本手冊不含 GT、劇本事件、真實路徑或標準答案；路徑一律用變數，不寫家目錄絕對路徑。

## 0. 三段一覽

| 段 | 內容 | 啟動 | 埠 | 資料來源 |
| --- | --- | --- | --- | --- |
| A | 錄製伺服器：監控牆、檢索彈窗、查找、B-05b 預錄切鏡、後台 | 第 2 節 | 8766 | RECORDED（P1 v4，SYNTHETIC） |
| B | B-05a live 追蹤：停在 A＋GAP，不切鏡 | 第 3 節 | 8765 | REAL（P1 v4，帶 tracking scope） |
| C | 複雜事件播放 A4-1／B4-1（#399） | 第 4 節 | 8780 | LOCAL safe RGB，無推論 |

**A 與 B 必須是兩次獨立啟動**（帶 `--tracking-scope` 時不登錄錄製，`?recording=` 會被忽略；`p1_workbench.py:168`）。B 的首頁監控牆是空的（「沒有可播放的來源」），所以 B-01／B-02／B-03 一律在 A 做，B 只做 B-05a。

## 1. 事前檢查清單（demo 前一天與當天開場前各跑一次）

打 ✔ 才算過；任何一項不過，先看第 6 節備援。

1. **磁碟**：`df -g /` 可用 ≥ 9 GiB（低於 8 GiB 不啟動；啟動器本身也會拒絕）。複雜事件 server 啟動會把約 1.2 GB 的 PNG 全量驗證一次（不佔磁碟）。
2. **LOCAL 路徑存在且唯讀使用**：
   - P1 v4 包：`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/`（含 `MANIFEST.json`，pin `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`）。
   - 複雜事件資料根：`$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/`，只讀 `A4-1/safe`、`B4-1/safe`。**不要** `ls`、開啟或複製 `gt_private/`。
3. **Python ≥3.12**：`python3 --version`（2026-11-03 實測 3.14.7）。Node 可用：`node --version`。
4. **repo checkout 是 `97030cd`**（或其後只含 demo 修補的 commit）：`git rev-parse HEAD`、`git status` 乾淨。
5. **埠沒被占**：`lsof -iTCP:8765 -iTCP:8766 -iTCP:8780 -sTCP:LISTEN`，應為空。被占就換埠（指令的 `--port`），不要殺不認得的程序。
6. **新的 state 目錄**：每次啟動 `--state-root` 必須是**不存在**的新路徑、父目錄存在，例如 `STATE_PARENT=$HOME/amidst-demo-state; mkdir -p "$STATE_PARENT"`，每次用 `$STATE_PARENT/run-$(date +%H%M%S)`。不要放進 P1 包內。**所有路徑都要用絕對、正規（無 `..`、無符號連結）的路徑**：2026-11-03 實測 `--state-root ../x` 這類相對路徑會直接 `DataIntegrityError` 起不來。
7. **瀏覽器乾淨**：用**新的瀏覽器 profile／無痕視窗**，或在 DevTools Console 執行
   `localStorage.removeItem('amidst.monitor-room.v1'); localStorage.removeItem('amidst.workbench-v2.track-map-float.v1')`。
   原因（2026-11-03 實測）：後台的速度、起點、顯示鏡頭、循環與選定事件，以及俯視圖的開／關與位置，都存在瀏覽器 localStorage；排練時設過「2×、只看 A」，主畫面下次開啟就只剩 1 台鏡頭。
8. **視窗**：桌機寬度 1440×900；瀏覽器分頁保持前景、不要被其他視窗蓋住或最小化（背景分頁的 rAF 降速，播放量測不可信）。關掉通知與螢幕保護，接上電源。
9. **不要需要 OpenAI key**：本 demo 不呼叫外部模型；外部推測開關預設關閉，保持關閉。

## 2. 段 A：錄製伺服器（監控牆、檢索、B-05b、後台）

啟動（repo 根目錄；`P1_BUNDLE` 是 P1 v4 包的完整路徑）：

```bash
export P1_BUNDLE="/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試"
python3 -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$HOME/amidst-demo-state/rec-$(date +%H%M%S)" --current-ui --no-open --port 8766
```

終端機印出網址後，開以下網址（**不要**用印出的 `?mode=review` 網址，那是審核視角）：

- 首頁（監控牆）：`http://127.0.0.1:8766/workbench-v2/`
- B-05b：`http://127.0.0.1:8766/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938`
- 備用錄製（AGENT_SEQUENTIAL）：`?recording=d4b67fd71caef6fb80fc9d92af544959`
- 後台：`http://127.0.0.1:8766/workbench-v2/admin.html`

結束：在該終端機按 Ctrl-C。

### 2.1 操作順序與講稿要點（對應 DEMO_SCRIPT）

| 步驟 | 操作 | 預期畫面 | 講稿要點（四條界線隨時適用） |
| --- | --- | --- | --- |
| B-01 | 開首頁，等 10 秒 | 監控牆 2 台（A、B）同一時鐘播放，頂列「LIVE · SYNTHETIC」或「RECORDED · SYNTHETIC」，標「2 台鏡頭 · SYNTHETIC」；播放量測 2 台每台約 18–20 Hz、掉格約 4% | 預錄畫面同一時鐘；沒有畫面的鏡頭標 MISSING，不是「沒人」 |
| B-02 | 點「檢索」，看彈窗，Esc 關閉；再開，選「查找」、person、0:00:00–0:00:08，開始檢索 | 彈窗有查找／追蹤、類別、顏色、特徵、解析方式、起訖時:分:秒；送出後只顯示載入面板（牆隱藏），進度條標「示意」 | 進度條是示意，不代表找到或沒找到 |
| B-03 | 命中牆出現後按「同步播放全部命中鏡頭」 | 只有 #1 A、#2 B；片段外標「命中片段外 · 凍結於最近合法影格」；每格「身分未確認」 | 條件相符的觀測，不是同一個人；身分 UNCONFIRMED |
| B-03b（可選） | 結束檢索，檢索 car | 停在載入面板，顯示 `NO_MATCH · 在已推論的影格中沒有找到；不代表目標不存在`；按「結束檢索」才回牆 | 「沒找到」≠「不在」 |
| B-05b | 開 B-05b 網址；按 **M** 或「俯視圖 (M)」開俯視圖；按「播放」讓它從 0 播到約 5.2 s；用時間軸停在 5.10 s、5.15 s | 左側「決策紀錄」逐步出現；5.10 s 單畫面是 A，**5.15 s 起是 B**（#17 4.25 s SEARCHING→SWITCHING＋SWITCH＋MATCH_STRONG；#18 5.15 s SWITCHING→PLAYING「畫面換成 B」）；俯視圖只有**一條虛線**；秒數顯示兩位小數；往回拖到 2.0 s，決策紀錄只剩 #0～#6 | 這是預錄、工程場景的核定圖，不是 G4、不是正式核定；虛線是「輔助預測（示意，非實際路徑）」；外部推測開關保持關閉，勾選只會顯示「外部推測不可用」 |
| D-01 | 開後台，在「預設事件播放」選錄製按「播放」，回主畫面；展示篩選 | 主畫面切到所選事件；沒有標題的事件顯示 ID 並標「尚無可讀名稱」 | 後台只選預錄事件、調播放，不改判斷 |

**示範後務必還原**：後台改過速度／顯示鏡頭，要在後台改回 1×、全部鏡頭，或清掉 localStorage（第 1 節第 7 項）。

### 2.2 預期畫面（B-05b，供對照）

- 載入後直接進單畫面（A，0.00 s），頂列 `RECORDED · SYNTHETIC`、「程式試用來源 · 排除正式評估」；俯視圖預設**關閉**，按 M 才出現。
- 5.10 s：A，無目標框（GAP，RGB 背景保留）。5.15 s：B，目標有框；俯視圖 A→B 實線。
- 已知：俯視圖開啟時預設位置會蓋住攝影機畫面右下約 19%（見第 7 節 P2-1；修補 PR 合併前，用拖曳標題列把它移到不礙事處，或在講完該點後按「隱藏」）。

## 3. 段 B：B-05a live 追蹤（預期 fail-closed）

啟動（與段 A **不同進程、不同 state**，不同埠）：

```bash
python3 -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$HOME/amidst-demo-state/live-$(date +%H%M%S)" --tracking-scope "$PWD/configs/q1q5/p1_live_tracking_scope.json" --tracking-scope-sha256 e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8 --current-ui --no-open --port 8765
```

開 `http://127.0.0.1:8765/workbench-v2/`。**首頁監控牆為空是預期現象**（「沒有可播放的來源」，因為此模式不登錄錄製）；不要在這個進程上做 B-01。

| 步驟 | 操作 | 預期畫面 | 講稿要點 |
| --- | --- | --- | --- |
| B-05a | 檢索 → 模式選「追蹤」→ person、0:00:00–0:00:08 → 開始檢索 → 在「選起點觀測」清單點第一列 → 按「播放」，播約 6 s | 進入單畫面 A；**全程停在 A，不切到 B**（5.2 s 仍是 A＋GAP，只顯示當下狀態）；決策紀錄出現 TEMP_LOST／RETURNED_TO_ORIGIN；暫失時畫面標「緩衝中・前一來源影格」或不補框；時間顯示兩位小數；外部推測關閉 | 鏡頭關係圖尚未核准，系統不猜，所以離開 A 後不切到 B；沒偵測到≠不在畫面；這是預期的 fail-closed，不是故障 |

注意：
- 起點 0.05 s 起播放前約 4 s 較慢（首次緩衝，來源時間 0.05→0.31 s），之後以 1× 前進；彩排時先暖機，或開場先按一次播放。
- 講稿不要引用 2.5～3.4 s 的暫失時間：實測決策紀錄在 0.25 s 就出現 TEMP_LOST（見 P3-1）。
- 若出現 `TRACKING_SCOPE_MISSING` 或 `SESSION_BINDING`：直接跳到 B-05b，並說明 live 不切鏡。

結束：Ctrl-C。

## 4. 段 C：複雜事件播放（#399，只有影像、無推論）

來源：分支 `claude/demo-event-viewer`（PR [#399](https://github.com/Polalalabear/amidst/pull/399)），head `c519d214b8cbe52e74e3757c1d3e78cac9ece2a9`。**在 #399 合併進 `mainline/q1q5` 之前，要先切到該 head**（`git fetch origin claude/demo-event-viewer && git checkout --detach origin/claude/demo-event-viewer`；demo 後再 `git checkout mainline/q1q5` 換回），並確認 `git rev-parse --short HEAD` 為 `c519d21`。

啟動：

```bash
node frontend/event-viewer/server.mjs --root "$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8" --port 8780
```

啟動時會全量驗證每張 PNG，**約 15 秒**（2026-11-03 實測 14.5 s；PR 自述 6.0 s），印出 `A4-1: OK`、`B4-1: OK` 和網址才算好，之前不要開頁。開 `http://127.0.0.1:8780/`。結束：Ctrl-C。

| 步驟 | 操作 | 預期畫面 |
| --- | --- | --- |
| C-1 | 事件選 **A4-1**，按「播放」，播 10 秒以上；再按「暫停」，拖時間軸，按「下一格／上一格」 | 4 鏡頭格狀（CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY、CAM_W1）；5 fps；10 s 對應 frame 50／249；跳格 0、停滯 0；頂列固定「ENGINEERING／只有影像、無推論、無身分」 |
| C-2 | 事件選 **B4-1**，同樣操作 | 5 鏡頭格狀（CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE）；frame 0–209；拖到 frame 105＝21.00 s；下一格×3 → 108＝21.60 s，上一格 → 107＝21.40 s |

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

## 6. 出錯時的備援

| 狀況 | 做法 |
| --- | --- |
| 段 A 起不來（`PORT_IN_USE`、manifest 驗證失敗、磁碟不足） | 換 `--port`；確認 P1 包路徑與 pin；清出磁碟（≥8 GiB）後重啟；仍不行→用 P1 包的 `./start.command`（RULE_ONLY 錄製，徽章 ENGINEERING／SYNTHETIC），或播預錄影片（第 8 節） |
| 播放卡頓（時鐘顯示不前進、量測 Hz 低） | 先確認分頁在前景；按一次「暫停」再「播放」；把格數降為 4（頂列 1／2／4／8 的 4）；關掉其他占 CPU 的程式 |
| 後台設定殘留（只剩 1 台、2×、從 0:01 起） | 清 localStorage（第 1 節第 7 項）後重新整理 |
| 俯視圖蓋住畫面 | 拖標題列移開，或按「隱藏」；修補 PR 合併後會自動讓出右側欄 |
| B-05a 出現 `TRACKING_SCOPE_MISSING`／`SESSION_BINDING` | 口頭說明 live 追蹤這段壞了，直接跳到 B-05b；不可說成 live 已切鏡 |
| B-05b 錄製載入失敗 | 改開備用錄製 `d4b67fd71caef6fb80fc9d92af544959`；**旁白要照實說「模型逾時，由規則兜底」**；再不行→預錄截圖／影片，口頭說明不是現場切鏡 |
| 段 C 顯示 `UNAVAILABLE`／`INTEGRITY_FAIL`、0 張影像 | fail-closed：確認資料根路徑；不要手動繞過；改播預錄影片（第 8 節）並說明資料驗證未通過 |
| 瀏覽器掛掉 | 換新 profile 重開，從第 1 節第 7、8 項重來；server 不必重啟 |

預備品（demo 前一天產生，存 LOCAL、不 commit）：每段至少一張預錄截圖與一支約 1 分鐘的螢幕錄影；截圖檔名與 SHA-256 記在 #279 留言。

## 7. 已知問題（2026-11-03 實測；P1＝demo 當天會出錯或誤導觀眾）

**P1：無。** 以下均已有 workaround，列在這裡是因為會影響現場。

| 編號 | 級別 | 問題 | 歸屬 | workaround／處理 |
| --- | --- | --- | --- | --- |
| P2-1 | P2 | 開啟的俯視圖預設蓋住攝影機畫面右下約 19%（1440×900，單畫面） | Claude（FEAT-9） | 修補 Draft PR [#400](https://github.com/Polalalabear/amidst/pull/400)（開啟時保留右側欄，實測無重疊）；未合併前拖曳或隱藏 |
| P2-2 | P2 | 後台設定與俯視圖開關存在 localStorage，排練後殘留會改變主畫面（只剩 1 台鏡頭、2×） | Claude（FEAT-9） | 第 1 節第 7 項；現場用新 profile |
| P2-3 | P2 | live（帶 tracking scope）進程首頁監控牆為空「沒有可播放的來源」 | Codex（launcher／scope 模式不登錄錄製） | B-01～B-03 在段 A 做，段 B 只做 B-05a |
| P2-4 | P2 | UI-07 8 台：LOCAL 只有 2 台真實 RGB，沒有 8 台資料；未量 | Codex（資料） | 口頭只說「2 台」；不宣稱 8 台流暢 |
| P3-1 | P3 | 講稿寫 live 暫失約 2.5～3.4 s，實測決策紀錄 0.25 s 起即 TEMP_LOST | Claude（腳本文字） | 旁白不引用秒數 |
| P3-2 | P3 | 腳本寫「載入錄製後直接進單畫面＋俯視圖」，實測俯視圖預設關閉（設計：預設不蓋鏡頭） | Claude（腳本文字） | 按 M 開啟 |
| P3-3 | P3 | 外部推測不可用時，圖例仍列「外部模型推測（非系統判斷）」一行，勾選旁註「外部推測不可用」 | Claude（FEAT-9） | 旁白說明未接外部模型 |
| P3-4 | P3 | live 播放前約 4 s 較慢（首次緩衝） | Codex／Claude | 開場先預播一次 |
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
