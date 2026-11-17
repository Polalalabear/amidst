# 即時模式 A/B 雙畫面規格與介面契約 v1

- 日期：2026-11-17。狀態：**草案，待 Codex 確認契約**（issue [#566](https://github.com/Polalalabear/amidst/issues/566)；AGENTS.md：契約由 Claude 起草、Codex 確認；確認方式是在 CX-L5 issue 留言）。
- 依據：[#93](https://github.com/Polalalabear/amidst/issues/93) 的 D275、D276（使用者定義完整驗收的 LIVE 操作）。
- 實作：Codex，分支 `codex/feat-live-ab`。規格：Claude，分支 `claude/feat-live-ab`。
- 相關文件：[LIVE_MODE_GAME_DESIGN_V1](../design/LIVE_MODE_GAME_DESIGN_V1.md)、[V2](../design/LIVE_MODE_GAME_DESIGN_V2.md)、[LIVE_MODE_LLM_DECISION_V1](../design/LIVE_MODE_LLM_DECISION_V1.md)、[交接 20261116](../operations/LIVE_MODE_HANDOFF_20261116.md)（§13 是 #551 的 HUD）。
- 本文只寫行為和介面，**不含實作程式碼**。尺寸、秒數、半徑是預設值，集中放在一個設定物件，測試可以覆寫。

## 0. 目的與範圍

這個模式**只為了展示即時追蹤**：

- **A 畫面（操作端）**：像 3D 遊戲，用 WASD 在地圖中走動。開始前選一個角色，選定後中途不能換。
- **B 畫面（系統端）**：和 8785 追蹤模式一樣的選目標流程，使用者在 B 選「現在要追蹤哪個人物」，B 只能依鏡頭畫面判斷。
- **沒被選的人物**照腳本走。人物之間不碰撞。

不在範圍：身分辨識（身分仍是 unconfirmed）、真實導航或碰撞安全（physical navigation/collision 仍是 unknown）、多人同時操作、中途換角色、滑鼠操作（見 §1.3）。這是工程展示，不是正式研究驗收。

### 0.1 現況（2026-11-17，`main` 上 #563 已合併；#559 未合併）

| 項目 | 現況 | 這份規格要改成 |
| --- | --- | --- |
| A 的人物選單 | `operator.mjs` 只有 `red top／blue top`，是在設定目標外觀 | 開始前的角色選單（T/A/B/C），選的是「我是誰」，不是「追誰」 |
| 目標 | A 的句子＋人物決定，B 自動追（`system.mjs` 的 `pickTarget`；`tracker.py` 只認 `color == "red"`，所有紅衣人在同一處才鎖定） | B 的使用者選目標（顏色或候選），後台只在 B 要求後才開始鎖定 |
| B 的介面 | 沒有選擇介面 | 選特徵→開始追蹤→改選→停止 |
| 碰撞 | 只有牆面（`sim.mjs` 的 `blocked`，半徑 0.25 m） | 加上人物之間 |
| 腳本人物 | `scriptedPose` 依牆鐘 `tSec % durationSec` 內插 waypoints，循環；會和玩家及彼此重疊 | 每人有自己的腳本時鐘，前方有人時暫停 |
| 協定 | `protocol.mjs` 白名單，GT 類欄位被剝掉 | 只加 §5 列的欄位 |

## 1. A 畫面

### 1.1 角色選單（開始前）

- 頁面載入後先顯示全螢幕選單，**模擬、擷取、`/infer` 都還沒開始**（`captureTick` 不啟動）。
- 四張卡片，對應 N6 character variant `T`、`A`、`B`、`C`（`n6.mjs` 的 `VARIANTS`；資產 `local/data/live-assets-20261115/character.glb`，`KHR_materials_variants`）。每張卡片：
  - **外觀預覽**：用同一份 `character.glb` 的該 variant 材質渲染一個小 canvas（idle 姿勢）；渲染失敗時退回**色塊**，色塊顏色取該 variant 材質的 base color（不要寫死）。
  - **名稱**：預設「角色 T／A／B／C」（是否改成人名見 §11）。
  - 一行小字：該角色在腳本裡的出場秒數（取自 scenario，例如 A4-1 的 B 是 2.0–32.2 s）。
- 使用者點一張卡片，再按「開始」。按下後：
  1. 角色寫入 `session.actor_id`，**之後沒有任何 UI 或鍵盤可以改它**（驗收 A-4）。
  2. 呼叫 `POST /reset`（沿用）。回應新增 `session_id`（見 §5.3）。
  3. 開始模擬與擷取。
- 要換角色只能重新載入頁面（等於新的一局，選單重新出現）。
- 測試與自動重播用網址參數 `?actor=T|A|B|C` 跳過選單（沿用 `?auto=` 的重播模式不變；`?auto` 時玩家照該角色自己的腳本走，且不套用 §3 對玩家的阻擋，因為玩家就是腳本）。

### 1.2 操作（沿用現有 `operator.mjs` / `sim.mjs`）

- W／A／S／D 移動（世界座標：W=+Y、A=−X、S=−Y、D=+X），Shift 跑。走 1.2 m/s、跑 2.5 m/s（`WALK`／`RUN`，與 N6 clip 速度一致）。
- 越肩視角、牆面半透明（只在 A 自己的畫面；虛擬鏡頭照常渲染不透明牆）：沿用。
- 牆面碰撞沿用（半徑 0.25 m，沿牆滑動）。
- 移除：句子輸入框、`red top／blue top` 下拉。目標不再由 A 決定。
- 玩家起點：被選角色的 waypoint[0] 的 xy；若 2 倍人物半徑（§3.1）內有腳本人物，往最近的空位微調並記在 log（`spawn_adjusted`）。

### 1.3 滑鼠

現況（`operator.mjs`）**沒有**滑鼠操作，v1 也不新增（「沿用現有設計」）。要不要加滑鼠轉視角列在 §11。

### 1.4 其他人物

- 選定角色**之外**的三個 actor 照腳本走（§2）。被選的角色自己的腳本**不再執行**（只留一個玩家控制的身體）。
- 例：選 `A` → `T`、`B`、`C` 照腳本走；`T` 不再是「目標」，只是一個腳本人物。

## 2. 腳本人物

### 2.1 來源與格式

- 沿用 scenario v2.3：`docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json`（server 的 `/data/scenario.json` 提供）。`runs[].actors[].waypoints = [{t_us, xy:[x,y]}]`，線性內插，朝向取該段方向（`sim.mjs` 的 `scriptedPose`）。**v1 不新增腳本檔**。
- 預設 run：`A4-1-v2-4actor`（50 s，actor T/A/B/C）。`B4-1-v2-4actor`（42 s）可用 `?run=` 選。
- 數量與外觀：4 個 actor，選角色後場上共 **4 個人（1 玩家＋3 腳本）**；每個 actor 的外觀用自己 id 對應的 N6 variant（`makePerson(…, variant)`）；玩家用被選角色的 variant。**同一個 variant 不會同時出現兩次**。
- 離線量過的路線（取樣 0.1 s，單位 m；來源 v2.3 waypoints）：

| run | 兩人 | 最近距離（出現在該 run 的時刻） |
| --- | --- | --- |
| A4-1 | A–T 0.85（19.2 s）、A–B 0.86（15.5 s）、B–T 0.86（14.2 s）、A–C 0.80（26.9 s）、C–T 1.27（20.2 s）、B–C 6.4 |
| B4-1 | A–T 0.68（16.5 s）、A–C 1.94、C–T 6.45、A–B 1.21（41.9 s）、B–T 0.98（25.9 s）、B–C 3.27 |

  腳本路線本身**彼此最近 0.68 m（B4-1 的 A–T）**；所以人物碰撞半徑取 0.30 m（兩人中心距 ≥ 0.60 m）時，腳本人物彼此原則上不需要暫停。

### 2.2 每個腳本人物自己的時鐘

- 每個腳本人物 `i` 有自己的**腳本時鐘 `s_i`**（秒），起點 0，每個模擬步進 `dt` 前進 `dt`，**被擋住的那一步不前進**（人停在原地、速度 0、播 idle）。
- 位置 = `scriptedPose(actor_i, s_i, duration)`（循環沿用 `s_i % duration`）。
- 後果（要接受並記錄）：暫停只延後**該人物自己的**後續整條腳本（之後每個航點都晚 `pause_total_i` 秒），不影響其他人物。各人物的相位會和原場景時間線漸漸分開，原 scenario 設計的相遇時刻（例如 RETURN 事件）不保證在原本的秒數發生。**這個模式只展示即時追蹤，不重現原場景的時間線**；評估紀錄（§7）用實際位置，不依賴原時間線。
- 出場／離場：`s_i` 在第一個 waypoint 之前或最後一個之後時人物不顯示（沿用現行 `scriptedPose` 回傳 null）。不顯示的人物不參與碰撞。`s_i` 在不顯示時照常前進（不會被擋住）。

## 3. 不碰撞

### 3.1 半徑

- 人物碰撞圓半徑 `r_person = 0.30 m`（兩人中心距離 ≥ `2r = 0.60 m`）。理由：評估用的人物框 `projectBox` 是 0.5 m × 0.5 m（半寬 0.25 m），加 0.05 m 餘裕；N6 character 的 AABB 不大於這個寬度（`character_audit.json`，Codex 實作時確認，若更寬則取半寬＋0.05 m）。取 0.35 m（2r = 0.70 m）會讓 B4-1 的 A–T（最近 0.68 m）在離線檢查就不過，等於腳本本身有問題；可以覆寫，但預設用 0.30 m。
- 牆面半徑維持 0.25 m（`blocked` 的預設）。
- 設定物件欄位：`r_person`、`r_wall`、`wait_max_player_s`、`wait_max_mutual_s`、`eps_m`（量測容差 0.02 m）。

### 3.2 玩家

- 玩家每步嘗試移動到 `p'`。若 `p'` 與任何**顯示中**的其他人物中心距離 `< 2r`，**且比目前距離更近**，這個方向的移動取消；改試只動 X、只動 Y（和現有牆面滑動同一個作法）。都不行就原地不動。
- 「且比目前距離更近」是為了避免卡死：如果已經在 `2r` 內（例如出生時或對方走過來），玩家仍可以往遠離的方向走。
- 玩家**永遠不會被推動**；擋住是單向的（人物不能擠玩家）。

### 3.3 腳本人物 vs 玩家與其他人物

每個模擬步進，對每個顯示中的腳本人物 `i`（先照固定優先序 T、A、B、C 處理，用**上一步的位置**判斷，避免順序造成不對稱）：

1. 算出 `s_i + dt` 的預定位置 `p'`。
2. 找所有其他顯示中的實體 `j`（玩家或腳本人物）。若 `dist(p', p_j) < 2r` **且** `dist(p', p_j) < dist(p_i, p_j)`（正在靠近），則 `i` 本步**被擋住**：位置不變、`s_i` 不前進、速度 0。
3. 否則照腳本前進。

特性：

- 腳本人物**不偏離路線**，沒有繞路；前方有人就停，對方離開（或自己不再「靠近」）就繼續。
- 擋住只看「正在靠近」，所以已經在 `2r` 內的人可以往外走，不會互鎖在重疊狀態。
- 暫停只延後該人物自己的腳本（§2.2），不是整個場景。

### 3.4 死結

- 腳本人物被擋住的連續時間 `w_i` 超過上限就**穿過並記錄**，不繼續等：
  - 被**玩家**擋住：`wait_max_player_s = 8 s`。
  - 被**另一個腳本人物**擋住（含互相擋住）：`wait_max_mutual_s = 3 s`。互相擋住時只有**優先序較後**（T < A < B < C，C 最後）的那一個穿過，另一個照常。
- 「穿過」＝這一個人物暫時不做 §3.3 的步驟 2，直到它和對方的距離重新 `≥ 2r`（或對方不再顯示）。每次穿過記一筆 `forced_overlap` 事件：`{tick, t_sim, i, j, kind: 'player'|'script', waited_s, dist_m}`。
- 預期：v2.3 兩個 run 的腳本人物彼此間因為最近 0.68 m ≥ 0.60 m 而不會被擋；玩家擋路才會出現暫停。**腳本人物之間 `forced_overlap` 的預期次數是 0**（驗收 C-5）。

### 3.5 離線驗證（先做，作為測試）

- 純模組 `frontend/live-mode/src/crowd.mjs`（無 DOM，無 three）：`validateScripts(run, cfg)` 以 0.1 s 間隔取樣整段，對每一種選角（含不選，共 5 種）回報兩人最近距離與 `< 2r` 的區段。
- 規格要求：A4-1、B4-1 在 `r_person = 0.30` 時，**所有 actor 配對**最近距離 ≥ 0.60 m。若 Codex 發現與上表不符，在 issue 回報，不要自己改腳本檔（scenario 屬於 frozen 輸入，D89）。

### 3.6 可測的驗收條件（碰撞）

以 headless 模擬（不渲染，固定 `dt = 0.1 s`、固定亂數種子）跑 A4-1 兩圈（100 s 模擬時間）、四種選角各一次，玩家用一個固定種子的隨機走動機器人（含刻意朝人物衝）：

| 編號 | 條件 |
| --- | --- |
| C-1 | **玩家穿模次數 = 0**：任何一步結束後，玩家與任何顯示中人物的中心距離 `< 2r − eps` 的次數為 0（出生時已在 `2r` 內但之後不再更靠近的不計，記錄在 `spawn_adjusted`） |
| C-2 | **分離比例 ≥ 0.99**：所有取樣步（每步每一對顯示中的人物）中，距離 `≥ 2r − eps` 的比例；`forced_overlap` 期間的步數排除並另列 |
| C-3 | 腳本人物**不偏離路線**：每個腳本人物每一步的位置都落在其 waypoint 折線上（誤差 ≤ 1 mm） |
| C-4 | 暫停只延後自己：人物 `i` 的 `s_i`（腳本時鐘）= 模擬時間 − `pause_total_i`；其他人物的 `s_j` 不受 `i` 影響（以兩次模擬，一次有機器人、一次沒有，比較沒被擋住的人物，位置序列完全相同） |
| C-5 | 腳本人物彼此之間 `forced_overlap` 次數 = 0（A4-1、B4-1 各四種選角） |
| C-6 | 沒有死結：玩家站著不動 60 秒，腳本人物被擋住最多 `wait_max_player_s`，之後穿過並記一筆 `forced_overlap(kind:'player')`，模擬繼續前進（腳本時鐘最終走完一圈） |
| C-7 | 每步計算 ≤ 1 ms（4 個實體；用 `performance.now` 平均，只作回報不作閘門，列在 result record） |

## 4. B 畫面

### 4.1 狀態機

B 的狀態（`B.mode`，B 自己的 UI 狀態，與後台 `/track/state.mode` 一致）：

```
IDLE ──選特徵＋開始追蹤──▶ ACQUIRING ──(只有 1 個符合者)──▶ TRACKING
                                │
                                └─(≥2 個符合者)──▶ NEEDS_PICK ──點選候選──▶ TRACKING
TRACKING ──改選目標──▶ NEEDS_PICK（列出目前畫面的候選）／或重新選特徵
TRACKING / NEEDS_PICK / ACQUIRING ──停止──▶ IDLE
```

與 8785 的對應（`frontend/workbench-v2/ui-shell.mjs` 的 `buildQueryWindow(kind:'track')`）：

| 8785 追蹤查詢窗 | B 畫面 |
| --- | --- |
| 特徵（必填）：先選類別，類別是 `person` 才能選顏色 chip | 類別固定「人物」；顏色 chip：**紅衣、藍衣**（後台 `color.py` 只判斷 `red`／`blue`；其他顏色 = `UNKNOWN`，不提供） |
| 時間範圍 | 不適用（即時）；不顯示 |
| 「開始追蹤」按鈕＋回饋文字 | 「開始追蹤」按鈕＋回饋文字（沿用同樣的 `ui-feedback` 風格即可，不要求共用元件） |
| 追蹤中顯示、停止追蹤顯示 | 「停止追蹤」按鈕；停止後回 IDLE（畫面顯示「尚未開始追蹤」） |
| 開查詢窗追蹤新目標 | 「改選目標」按鈕 |

選特徵視窗位置：B 畫面頂端 HUD 下方的一條可收合的列（B 是單一跟隨畫面，沒有 8785 的牆）。UI 風格不強制和 8785 一樣，**流程一致**即可。

### 4.2 選特徵與句子

- 顏色 chip 必選一個（`red`／`blue`）。
- 句子（選填）：只做規則解析，**不呼叫 LLM、不花 API**：含「紅」／`red` → red；含「藍」／`blue` → blue。與 chip 衝突時以 chip 為準並在回饋文字說明；句子沒有可辨識的顏色且沒選 chip → 拒絕（`FEATURE_REQUIRED`）。句子原文不進 log 以外的任何地方。（要不要用 Q3 的解析器列在 §11。）

### 4.3 候選只能來自 B 自己從鏡頭畫面得到的資料

- 候選 = 後台在最近一輪 `/infer`（所有被推論的鏡頭）的偵測中，顏色符合的人，依地面位置 `est_xy` **分群**（距離 `< 1.5 m` 視為同一個人，與 `tracker.py` 目前的「同一處」規則一致；多個鏡頭看到同一人只算一個）。
- 一個候選含：`cand_id`、`tick`、`cam`（群中偵測分數最高那一支）、`bbox`、`score`、`color`、`est_xy`（全部都是現有白名單內的偵測欄位，後台由像素推得）。**沒有任何身分、角色、GT 欄位**。
- **不能讀 A 的角色選擇或位置**：B 只經 BroadcastChannel 收 `frame-batch`（protocol 白名單）和呼叫後台 `/track/*`（§5）；A 的 `session.actor_id`、玩家座標、腳本人物座標不會出現在 B 可達的任何地方（驗收 G-1～G-4）。
- 開始追蹤時：
  - **只有 1 個符合者** → 直接鎖定，`TRACKING`。
  - **0 個** → 保持 `ACQUIRING`，每輪重試；回饋文字「畫面中沒有符合的人」；使用者可隨時停止。
  - **≥ 2 個** → `NEEDS_PICK`：列出候選讓使用者點選。畫面上 B 用該候選的 `cam` 和 `bbox` 在對應鏡頭影格上畫編號框（1、2、3…，由左至右）；同時在右側小地圖畫對應 `est_xy` 的編號點；列表每項顯示「編號・鏡頭・位置」。使用者點框、點列表項或點地圖點都等於選取。B 保留最近 5 輪的 `frame-batch`，用候選的 `tick` 找對應影格；找不到就只顯示列表和地圖點。
- 候選選定前，**後台不鎖定任何人**（追蹤狀態 `NEEDS_PICK`）。選定後的追蹤用現有 `tracker.py` 的跟隨、切鏡、失聯邏輯，不改規則；只改「怎麼起始鎖定」和「目標顏色可以是 blue」（§5.4）。

### 4.4 改選與停止

- 改選目標（`TRACKING` 中）：按「改選目標」→ B 向後台取目前候選（`GET /track/candidates`），進入 `NEEDS_PICK`，**即使只有一個候選也要使用者確認**（因為改選的目的就是換人）；使用者也可以改選另一個顏色再「開始追蹤」。選定前 HUD 沿用目前的追蹤狀態（舊目標繼續追），選定後新目標生效，舊目標的 est_xy 和尾跡清掉。
- 停止追蹤：`POST /track/stop` → 後台回 `IDLE`；B 畫面清空主區域、顯示「尚未開始追蹤」；`/infer` 仍照常回偵測（供候選與小地圖用），但 `tracking.state = 'IDLE'`。
- A 端不會被 B 的操作影響（人物照走，擷取照送）。

### 4.5 HUD

沿用 #551（交接 §13）：四格 HUD、切鏡提示、失聯框與計時、狀態列、小地圖與事件清單，**欄位定義不變**。新增只有：

- `tracking.state` 新值 `IDLE`（HUD 第一格顯示「尚未開始追蹤」，色調 `searching`）和 `NEEDS_PICK`（顯示「請選擇要追蹤的人（N 位）」）。`hud.mjs` 的 `view()` 要處理這兩個值；其餘不變。
- `tracking.target`（§5.2）顯示在第一格小字：「目標：紅衣」。

## 5. A↔B 資料流與協定

### 5.1 總覽

```
A（operator.mjs，持有玩家／腳本人物／GT）
   │  POST /infer （標頭＋JPEG；無角色、無座標）
   ▼
後台（server.py）──推論→偵測（像素推得）──→ tracker／scheduler／advisor
   │  回應 res（含 dets、tracking、schedule）
   ▼
A ──buildSystemMessage（白名單）──BroadcastChannel──▶ B（system.mjs）
B ──POST /track/start|pick|stop、GET /track/candidates|state──▶ 後台
```

A 只負責「把像素送出去、把後台結果經白名單轉給 B」；B 的選目標請求**直接**打後台，不經 A。A 不呼叫 `/track/*`。

### 5.2 `frame-batch`（A→B，BroadcastChannel）：只加兩個鍵

`protocol.mjs` 的白名單現況不變，只新增：

| 位置 | 鍵 | 型別 | 說明 |
| --- | --- | --- | --- |
| `tracking` | `target` | `{color: 'red'\|'blue'\|null, mode: 'IDLE'\|'ACQUIRING'\|'NEEDS_PICK'\|'TRACKING'}` | 後台輸出，是 B 自己選的目標的回聲；`TRACK_KEYS` 加 `target`，並新增 `TARGET_KEYS = {color, mode}` 逐層過濾與驗證 |
| `tracking.state` | （值） | 現有值加 `IDLE`、`NEEDS_PICK` | `validateSystemMessage` 要接受這兩個值 |

仍然**禁止**（`validateSystemMessage` 逐層檢查，任何其他鍵都算違規並整則丟棄）：`actor_id`、`role`、`variant`、`person_id`、`operator_xy`、`player_xy`、`gt`、`gt_visible`、`waypoints`、`s_i`、`script_*`、`pause_*`、`forced_overlap`、`spawn_adjusted`，以及任何 `session.*`。

### 5.3 `POST /reset`（A→後台，沿用）

- request：不變（空）。
- response 新增：`{"ok": true, "session_id": "<16 hex>"}`。`session_id` 只是隨機字串，**不含角色資訊**；後台每次 `/reset` 換一個，並把追蹤模式重設為 `IDLE`。
- A 在按「開始」時呼叫（§1.1）。A **不**把 `session_id` 放進 `frame-batch`；B 自己從 `GET /track/state` 得知。

### 5.4 B→後台新端點（都在 `server.py`，同一個埠，JSON，UTF-8）

共同規則：

- 只接受下列 request 鍵；多出來的鍵回 **400** `{"error":"FIELD_NOT_ALLOWED","fields":[…]}`。
- 錯誤格式：`{"error": "<CODE>", "detail": "<人讀文字>"}`。
- response 一律只含下列欄位。後台內部沒有任何 GT／角色資料（後台本來就看不到），因此不需要額外剝除，但實作要在回應函式上用白名單輸出，並有測試（§8.4 G-5）。

**`POST /track/start`**

- request：`{"color": "red"|"blue", "sentence": "<選填，≤ 80 字>"}`。
- response 200：
  ```
  {"mode": "ACQUIRING"|"NEEDS_PICK"|"TRACKING",
   "color": "red"|"blue",
   "tick": <最近一輪 tick 或 null>,
   "candidates": [ {cand_id, tick, cam, bbox:[x0,y0,x1,y1], score, color, est_xy:[x,y]} … ]}
  ```
  - 1 個候選 → 後台**立刻**鎖定，`mode:"TRACKING"`，`candidates` 含那一個。
  - 0 個 → `mode:"ACQUIRING"`，`candidates: []`，之後每輪 `/infer` 若出現恰好 1 群就自動鎖定；若出現 ≥ 2 群則轉 `NEEDS_PICK`。
  - ≥ 2 個 → `mode:"NEEDS_PICK"`，不鎖定。
- 錯誤：400 `FEATURE_REQUIRED`（沒有 color 也解析不出）；400 `COLOR_UNSUPPORTED`；409 `NO_DETECTIONS_YET`（還沒有任何 `/infer`，可以視為 `ACQUIRING`，Codex 二選一，在 issue 回覆時定案）。
- 若目前已在 `TRACKING`：視為改選，先清掉舊目標（est_xy、lost、active 都重設）再走上面流程。

**`POST /track/pick`**

- request：`{"cand_id": "<string>"}`。
- response 200：`{"mode":"TRACKING","color":…,"picked":{cand_id,tick,cam,bbox,score,color,est_xy}}`。
- 後台以該候選的 `est_xy` 和 `cam` 作為追蹤起點（`est`、`active`、`t_seen`），發出 `ACQUIRE` 事件（`detail.by:"USER_PICK"`）。
- 錯誤：404 `CANDIDATE_UNKNOWN`；409 `CANDIDATE_STALE`（候選的 `tick` 比目前最新 tick 早超過 `stale_ticks`，預設 6 tick，約 3 秒 @2 fps；B 收到後重新 `GET /track/candidates`）。
- `cand_id` 是後台發的不透明字串（例如 `c{tick}-{序號}`），**每輪重發**；後台只保留最近 `stale_ticks` 輪的候選表。

**`GET /track/candidates`**

- query：`color`（選填，預設目前目標色；`any` 回傳兩色）。
- response 200：`{"tick": n|null, "color": …, "candidates":[…同上…]}`；沒有偵測時 `candidates:[]`。
- 用途：改選目標時列出目前畫面的候選。

**`POST /track/stop`**

- request：`{}`。response 200：`{"mode":"IDLE"}`。後台重設 tracker，`tracking.state = 'IDLE'`，advisor 一併重設（沿用 `/reset` 的重設方式，但**不換 `session_id`**）。

**`GET /track/state`**

- response 200：`{"mode": …, "color": …|null, "session_id": "<16 hex>", "tick": n|null}`。B 每 1 秒輪詢；`session_id` 變了代表 A 重新開始一局，B 回到 `IDLE`。

### 5.5 `/infer` 的行為改動（後台）

- 新增追蹤模式 `IDLE`（開機預設）：`/infer` 照常偵測、排程、回 `dets`，但 tracker 不鎖定、不發事件，回 `tracking = {state:'IDLE', active_cam:null, seen_cams:[], est_xy:null, events:[], lost_ticks:0, target:{color:null, mode:'IDLE'}}`。排程用「全鏡頭」模式（沿用 `INITIAL_SEARCH`／`ALL_CAMERAS`，與 #553/#559 的排程一致；#559 合併後以它的行為為準）。
- `tracker.py` 目標顏色參數化（`target_color`，預設 `red`，行為與現在相同）；`est_xy` 的地面投影對 `red`、`blue` 偵測都算（現況只對 red 算，B 要畫藍衣候選的位置需要）。
- 起始鎖定改為：`IDLE`→（B 的 `/track/start`）→ 只在 B 要求後鎖定，不再「所有紅衣人在同一處就自動鎖定」。`pick` 直接以候選起始。
- 候選表：`/infer` 每輪結束後，後台用該輪偵測更新候選表（§4.3 的分群）。
- 追蹤中、失聯、切鏡、advisor（LLM 開關，#563）全部沿用；`advisor` 在 `IDLE`／`NEEDS_PICK` 時不問。
- 事件（`events`）新增 `detail.by:"USER_PICK"|"AUTO_SINGLE"`（`ACQUIRE`），並在 `EVENT_KEYS` 白名單內（`detail` 已在，只是值）。

### 5.6 A 端記錄 vs B 端記錄（不可混）

| 記錄 | 在哪 | 內容 | 能不能進 B |
| --- | --- | --- | --- |
| A 的 GT 記錄（`window.__log.ticks`，沿用） | A 的視窗 | 每 tick：`t_capture`、被選角色與所有腳本人物的真實 xy、`gt_visible`（每個鏡頭是否看得到被選角色，`groundTruthVisible`）、`forced_overlap`、`spawn_adjusted`、`pause_total_i` | **不行**（§5.2 禁止清單） |
| B 的追蹤記錄（`window.__log`，沿用並擴充） | B 的視窗 | 每則 `frame-batch`：`tick`、`t_capture`、`tracking.state`、`active_cam`、`est_xy`、`lost_ticks`、`events`；B 的操作：`start`／`pick`（含 `cand_id`、候選 `est_xy`、`tick`）／`stop` 的時間 | — |
| 評分 | 事後離線（§7），輸入是 A 和 B 各自下載的兩個 JSON | — | 評分程式在視窗之外 |

## 6. 角色與選目標的獨立性

被選角色（玩家）**不等於**被追蹤的目標：B 的使用者可以追蹤任何一個符合顏色的人（含腳本人物，也可以追玩家自己的角色）。誰是目標由 B 的選擇決定，只有事後評分（§7）才把 B 選到的候選對到真實人物。

## 7. 評估紀錄與評分

### 7.1 事後評分（`scripts/live_ab_score.py`，離線；檔名可由 Codex 決定，在 issue 回覆）

輸入：A 的 GT 記錄、B 的追蹤記錄，用 `t_capture` 和 `tick`（同一輪相同）對齊。

1. **目標身分（事後）**：B 的第一次 `pick`（或 `AUTO_SINGLE` 的 `ACQUIRE`）時刻，取 `est_xy`，在同一 tick 的 GT 中找最近的實體；距離 `≤ 1.5 m` 則該實體是「被追蹤者」`target_gt`；超過 1.5 m 記為 `MISPICK`。每次改選各算一段。
2. **每 tick 判定**（從選定後到停止／改選／結束）：
   - 目標在至少一個鏡頭看得到（`gt_visible` 非空）時：
     - **跟對**：`tracking.state = TRACKING` 且 `dist(est_xy, gt_xy(target_gt)) ≤ 1.5 m`；
     - **跟錯**：`TRACKING` 但 `est_xy` 離 `target_gt` 超過 1.5 m（且更靠近別人）；
     - **失聯**：`state = LOST`、或 `lost_ticks > 0`、或沒有 `est_xy`。
   - 目標任何鏡頭都看不到時：**不計入跟對率**，另外回報此時系統是否正確宣告離開視野／失聯（`TARGET_OUT_OF_VIEW`、`LOST`）。
3. 報表（JSON，另可輸出一張表）：每段追蹤的 `target_gt`、MISPICK、跟對／跟錯／失聯 tick 數與比例、跟錯的連續區段數（連續 ≥ 2 tick 算一次身分交換）、失聯次數與每次秒數、切鏡次數、延遲（`t_resp − t_capture` 與 #551 HUD 的「取最近 1 秒中位數」同一算法，回報 p50／p95）、玩家穿模次數、`forced_overlap` 次數、`spawn_adjusted`、腳本人物被擋住的總秒數。
4. 閾值：**不設跟對率硬閾值**（目前沒有 A/B 的基準數字；既有的 0.45–0.62 是另一個定義的「作用中鏡頭看得到目標」比例，見交接 §8）。這份報表是展示紀錄，要不要訂目標列在 §11。

### 7.2 GT 隔離

- A 的 GT 記錄只供事後評分，**不進** B、不進後台、不進推論、排序或重建（DEVELOPMENT_RULES、AGENTS.md 共用規則）。
- 評分程式讀的是兩個已下載的 JSON，不在即時路徑上。

## 8. 驗收條件（逐條可測）

測試命名：前端 `node --test`（`frontend/live-mode/test/`）；後台 `pytest`（`tests/live_mode/`）。Codex 可調整檔名，但要在 issue 回覆中列出對應表。

### 8.1 功能（F）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| F-1 | 選單有 T/A/B/C 四張卡片，每張有預覽或色塊與名稱；沒選就不能按「開始」 | `ab_menu.test.mjs`（以純函式 `menuState()` 驗證；DOM 部分用瀏覽器截圖紀錄） |
| F-2 | 按「開始」前 `/infer` 呼叫次數 = 0；按下後才開始擷取 | `ab_menu.test.mjs`（以 fake fetch） |
| F-3 | 選角後，該角色的腳本不執行；其餘 3 個 actor 的腳本人物存在且 variant 各不相同、與玩家不同 | `crowd.test.mjs` |
| F-4 | B 的流程：`IDLE` →（選 red＋開始）→ 1 個候選：`TRACKING`；2 個候選：`NEEDS_PICK`→pick→`TRACKING`；改選→`NEEDS_PICK`→pick→新目標；停止→`IDLE` | `test_track_endpoints.py`＋`ab_flow.test.mjs`（B 端狀態機純函式 `reduceB()`） |
| F-5 | 兩個以上紅衣候選時，不會自動鎖定（`tracker.state` 保持非 `TRACKING` 直到 pick） | `test_track_endpoints.py` |
| F-6 | `pick` 過期候選回 409 `CANDIDATE_STALE`；未知 id 回 404 | `test_track_endpoints.py` |
| F-7 | `blue` 目標：鎖定、跟隨、失聯行為與 `red` 相同（以合成偵測序列驗證） | `test_tracker_color.py` |
| F-8 | `IDLE` 時 `/infer` 回 `tracking.state = 'IDLE'` 且無事件 | `test_track_endpoints.py` |
| F-9 | HUD：`IDLE`／`NEEDS_PICK` 顯示文字與色調符合 §4.5；其餘 HUD 欄位測試（`hud.test.mjs`）不變且全過 | `hud.test.mjs` |
| F-10 | `session_id` 改變時 B 回到 `IDLE` | `ab_flow.test.mjs` |

### 8.2 操作（A）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| A-1 | WASD、Shift 速度 1.2／2.5 m/s；牆面半徑 0.25 m、沿牆滑動（沿用現有行為不退步） | `crowd.test.mjs`（`stepPlayer` 回歸） |
| A-2 | 移除句子與 `red top／blue top` 下拉；A 沒有任何目標設定欄位 | `ab_menu.test.mjs`（檢查 `operator.mjs` 產生的 DOM 字串） |
| A-3 | 選角寫入 `session.actor_id` 後，沒有可改它的程式路徑（模組沒有 export setter；`window.__op` 不提供） | `ab_menu.test.mjs` |
| A-4 | 開始後按任何鍵都不會改角色；重新載入頁面才會出現選單 | `ab_menu.test.mjs` |

### 8.3 碰撞（C）

見 §3.6：C-1～C-7（`crowd.test.mjs`）。

### 8.4 GT 隔離（G）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| G-1 | `buildSystemMessage` 的輸入型別沒有 A 的任何欄位；對塞進 `actor_id`、`player_xy`、`gt` 等 §5.2 禁止鍵的結果，輸出沒有這些鍵 | `protocol.test.mjs`（擴充） |
| G-2 | `validateSystemMessage` 對含任一禁止鍵的訊息回報違規（逐一參數化） | `protocol.test.mjs` |
| G-3 | `system.mjs`、`hud.mjs` 的原始碼不 import `world.mjs`、`sim.mjs`、`crowd.mjs`、`operator.mjs`，也不含 `groundTruthVisible`、`actor_id`（靜態字串檢查） | `protocol.test.mjs`（新增 `b_isolation` 案例） |
| G-4 | `/track/*` 的 request 只收 §5.4 列的鍵，多餘的鍵 400 | `test_track_endpoints.py` |
| G-5 | `/track/*` 與 `/infer` 的 response 只含白名單鍵 | `test_track_endpoints.py` |
| G-6 | A 的原始碼不呼叫 `/track/*` | `ab_menu.test.mjs`（靜態字串檢查） |

### 8.5 延遲與效能（沿用現有預算，不新增）

- 偵測延遲 p50 ≤ 0.5 s、p95 ≤ 0.8 s（設計 V2 §延遲；**沿用**，量法同 #551）。
- HUD「目前延遲」門檻 0.5／1.0 s（沿用）。
- `/track/*` 本機往返 ≤ 200 ms（回報，不作閘門）；`GET /track/state` 每秒一次，對 `/infer` 的 p95 沒有可量測影響（回報）。
- 這些量測是**回報項**，列在 result record；未達標時說明，不用改規格。

### 8.6 一般

- `git diff --check` 乾淨。
- `hud.test.mjs`、`llm_switch.test.mjs`、`n6.test.mjs`、`protocol.test.mjs`、`schedule.test.mjs` 原有案例全過。
- 後台 `tests/live_mode/` 原有案例全過。
- 瀏覽器驗收（手動，截圖進 PR）：A 選角→開始→走到腳本人物前被擋住；B 選紅衣有兩個候選→點選→追蹤→改選→停止。

## 9. 檔案範圍與先後順序

### 9.1 會改的檔

| 檔 | 內容 | 與進行中 PR 重疊 |
| --- | --- | --- |
| `frontend/live-mode/src/crowd.mjs`（新） | 腳本時鐘、碰撞與暫停、離線驗證（純模組） | 無 |
| `frontend/live-mode/src/sim.mjs` | `stepPlayer` 加人物阻擋；`scriptedPose` 不變 | 無 |
| `frontend/live-mode/src/operator.mjs` | 角色選單、開始閘門、去掉句子與下拉、接 `crowd.mjs`、GT 記錄擴充 | 無（#563 沒改） |
| `frontend/live-mode/src/system.mjs` | 選特徵列、候選疊圖、`reduceB`、輪詢 `/track/state` | **#563**（LLM 開關，已合併進 `main`）；**#559** 若改動需協調 |
| `frontend/live-mode/src/hud.mjs` | `IDLE`／`NEEDS_PICK` 兩種狀態 | #563 已合併；無進行中 |
| `frontend/live-mode/src/protocol.mjs` | 白名單加 `target`；`state` 新值 | **#559**（排程欄位 `schedule` 已在 main；若 #559 再加欄位會衝突） |
| `frontend/live-mode/test/crowd.test.mjs`、`ab_menu.test.mjs`、`ab_flow.test.mjs`（新）、`protocol.test.mjs`、`hud.test.mjs` | 測試 | `protocol.test.mjs` 可能與 #559 重疊 |
| `src/amidst/live_mode/server.py` | `/track/*`、`/reset` 回 `session_id`、`IDLE` 模式、候選表 | **#559**（偵測與排程，重疊最多）；#563 已合併 |
| `src/amidst/live_mode/tracker.py` | `target_color`、blue 的 `est_xy`、`IDLE`、起始鎖定改由要求觸發、`pick` 起始 | #559 可能碰（待確認） |
| `src/amidst/live_mode/candidates.py`（新） | 分群與候選表 | 無 |
| `tests/live_mode/test_track_endpoints.py`、`test_tracker_color.py`（新） | 後台測試 | 無 |
| `scripts/live_ab_score.py`（新） | 事後評分 | 無 |
| `docs/operations/LIVE_MODE_HANDOFF_*.md` 或新文件 | 啟動與操作說明（AGENTS.md：handoff 文件進 GitHub） | — |

不改：`frontend/workbench/`、`frontend/workbench-v2/`（8785 的程式不動；B 只**參考**它的流程）、scenario 檔、LOCAL 資產、`ApiGuard` 與 advisor 邏輯。

### 9.2 先後順序

1. **等 #559 合併再開工**（建議）。理由：`server.py` 的 `infer()`、排程與偵測都在 #559 修，`/track/*` 與 `IDLE` 模式要接在同一段；先寫會在 rebase 時衝突，而且 `IDLE` 的排程行為要以 #559 為準。#563 已經合併（2026-11-17，`main` @`0606b164`），不必等。
2. 如果要提早動，**可以先做和 #559 不重疊的兩塊**：(a) `crowd.mjs`＋`sim.mjs`＋A 的選單與 `operator.mjs`（碰撞與腳本，驗收 F-1～F-3、A、C），(b) `scripts/live_ab_score.py`。這兩塊不碰 `server.py`、`protocol.mjs`、`system.mjs`。
3. 之後做後台 `/track/*` 與 `tracker.py`（F-4～F-8、G-4、G-5），再做 B 端與協定（F-9、F-10、G-1～G-3、G-6），最後整合與瀏覽器驗收。
4. 單一 feature 一個 PR（D216），分階段 commit。

## 10. 風險與未驗證

- **選角與外觀**：variant T/A/B/C 的實際衣色（紅／藍／橘）沒有在這份規格查證（`UNKNOWN`）；選單的色塊取材質 base color，B 的顏色 chip 只有後台判得出的 `red`／`blue`。若某個 variant 後台判為 `none`，B 就**追不到它**——要不要保證至少兩個 variant 判為 red（使其「多個符合者」情境可測）列在 §11。
- **B 只能看到後台回的 `est_xy`**：分群門檻 1.5 m 沿用 tracker；兩人貼近（< 1.5 m）時會被分成同一個候選。腳本最近 0.68 m，因此貼近時 B 看到的是一個候選（這是真實的辨識限制，不是 bug；評分時會記成跟錯或 MISPICK）。
- **原場景時間線不保留**（§2.2）。
- 沒有實測：本文的碰撞半徑、等待上限、`stale_ticks` 都是預設值，要靠 §8 的測試與瀏覽器驗收確認。
- #559 若改了 `infer()` 回傳形狀，§5.5 要跟著調整；Codex 開工前以當時 `main` 為準，不一致時在 issue 提出。

## 11. 待使用者決定

只列真正需要的。每項附預設，不回覆就照預設。

1. **角色名稱**：選單用「角色 T／A／B／C」還是人名／代號？（預設：角色 T／A／B／C，附衣色色塊）
2. **腳本人物數量**：固定 3 個（四個 actor 扣掉被選的）是否足夠？要不要允許關掉其中幾個？（預設：固定 3 個）
3. **玩家擋住腳本人物的處理**：等 8 秒後穿過（預設），還是一直等（展示時人物會僵住）？
4. **滑鼠**：要不要加滑鼠轉視角？（預設：不加）
5. **B 的句子**：只做規則解析（預設），還是要接 Q3 解析器／LLM？
6. **跟對率目標**：要不要為展示訂一個數字？（預設：不訂，只出報表）
7. **兩個 variant 的衣色**：是否確保選單中至少有兩個 variant 會被後台判為 `red`，讓「多個符合者要點選」的情境一定出現？（預設：不改資產，使用現有 scenario 的衣色）

## 12. 實際產出 / Actual output

見 PR 描述（本文件為規格，無程式碼、無實測數字；§2.1 的最近距離表是 `docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json` 的 waypoints 以 0.1 s 線性內插取樣算出，只讀，未渲染）。
