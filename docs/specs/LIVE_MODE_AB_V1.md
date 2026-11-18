# 即時模式 A/B 雙畫面規格與介面契約 v2.1

- 日期：v1 2026-11-17；v2 2026-11-18；**v2.1 2026-11-18**（D282：C-5 補定義，見變更紀錄）。狀態：**v2：§11 已由使用者決定（D279），吸收 Codex 契約審閱（[#566 留言](https://github.com/Polalalabear/amidst/issues/566#issuecomment-6953407249)）**。工作拆成板上的子 issue（見 §9.3）。
- 依據：[#93](https://github.com/Polalalabear/amidst/issues/93) 的 D275、D276（使用者定義完整驗收的 LIVE 操作）、D279（§11 的決定）。
- 實作：Codex，分支 `codex/feat-live-ab`（一個 Draft PR 分階段交，D248）。規格：Claude，分支 `claude/feat-live-ab`。
- 相關文件：[LIVE_MODE_GAME_DESIGN_V1](../design/LIVE_MODE_GAME_DESIGN_V1.md)、[V2](../design/LIVE_MODE_GAME_DESIGN_V2.md)、[LIVE_MODE_LLM_DECISION_V1](../design/LIVE_MODE_LLM_DECISION_V1.md)、[NL_QUERY_PARSE_V1](../contracts/NL_QUERY_PARSE_V1.md)、[交接 20261116](../operations/LIVE_MODE_HANDOFF_20261116.md)（§13 是 #551 的 HUD）。
- 本文只寫行為和介面，**不含實作程式碼**。尺寸、秒數、半徑是預設值，集中放在一個設定物件，測試可以覆寫。

## 變更紀錄

| 版本 | 變更 |
| --- | --- |
| v1 | 初稿（D275、D276）。 |
| v2 | **使用者決定（D279）**：§11-3 玩家擋路改「一直等」（改寫 §3.4、C-6）；§11-4 加滑鼠轉視角（§1.3、A-5）；§11-5 B 的句子接 Q3 解析器（§4.2、§5.4）；§11-1、2、6、7 照預設。另：A 開始前先選場景（A4-1／B4-1）再選角色（§1.1）。 |
| v2 | **吸收 Codex 契約審閱**：§5.2 nested 白名單與禁止鍵；§5.3／§5.4 `session_id`、`reselect`、error schema `{error,detail?,fields?}`、無偵測時 200 `ACQUIRING`、409 `TRACK_MODE_CONFLICT`／`SESSION_MISMATCH`、stale 保留 7 個 generation、`cand_id` 綁 session 與 epoch；§5.5 `ACQUIRING`／`NEEDS_PICK` 語意；§3.3 成對相對移動的碰撞檢查（C-8）；C-1 排除 `forced_overlap` 配對並另報原始數；C-6 以 `s_i`／`pause_total_i` 驗證進展；§5.6 A 私有 log 記每個 actor 的 `present／xy／gt_visible`、`schema_version`、session 對齊；§7 `AMBIGUOUS_PICK`／`UNMATCHED`、延遲分開列、CLI；§8 測試檔對應表。 |
| v2 | **不同意或調整的地方（理由見 §10-1）**：(1) Codex 建議 `/track/start` 無 infer 時二選一，v2 定案 200 `ACQUIRING`；(2) 玩家擋路改一直等後，腳本人物 j 追上被玩家擋住的 i 時會出現「連鎖」的 script–script `forced_overlap`，C-5 改成排除連鎖並另列（Codex 未提，是 D279 的後果）；(3) 事件 `detail`／`timing_ms` 的現有合法形狀由 Codex 在實作時列舉，v2 只定原則。 |
| v2.1 | **C-5 補定義（D282，#585）**：(1) 新增 §3.4「相位差與 `cause`」：玩家造成的暫停讓腳本人物相位永久延後，玩家離開後腳本人物互擋仍可能發生（#568 反例：A4 玩家 T @78.7 s，B 先前被擋 21.9 s）；(2) 以「污染（taint）集合」判定一方是否曾被玩家影響（含傳遞），`forced_overlap` 事件加 `cause`（`script`／`player_phase_shift`）與 `tainted`；(3) C-5 改為：**無玩家基線必須 0**、有玩家時 `cause:'script'` 必須 0，`player_phase_shift` 另外計數、不設閘門；(4) `chain` 改為 `player_phase_shift` 的子集（欄位保留）；(5) §5.6、§7.1 報表同步，C-5 加反例回歸測試。未改其他驗收、seed、scenario。 |

## 0. 目的與範圍

這個模式**只為了展示即時追蹤**：

- **A 畫面（操作端）**：像 3D 遊戲，用 WASD 加滑鼠轉視角在地圖中走動。開始前先選場景（A4-1／B4-1）再選一個角色，選定後中途不能換。
- **B 畫面（系統端）**：和 8785 追蹤模式一樣的選目標流程，使用者在 B 選「現在要追蹤哪個人物」，B 只能依鏡頭畫面判斷。
- **沒被選的人物**照腳本走。人物之間不碰撞。

不在範圍：身分辨識（身分仍是 unconfirmed）、真實導航或碰撞安全（physical navigation/collision 仍是 unknown）、多人同時操作、中途換角色。這是工程展示，不是正式研究驗收。

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

### 1.1 場景與角色選單（開始前）

- 頁面載入後先顯示全螢幕選單，**模擬、擷取、`/infer` 都還沒開始**（`captureTick` 不啟動）。
- **步驟 1：場景**。兩張卡片：`A4-1`（50 s）、`B4-1`（42 s）（scenario v2.3 的 `A4-1-v2-4actor`、`B4-1-v2-4actor`）。預設選 `A4-1`。選場景決定腳本人物、角色出場秒數與地圖。
- **步驟 2：角色**。四張卡片，對應 N6 character variant `T`、`A`、`B`、`C`（`n6.mjs` 的 `VARIANTS`；資產 `local/data/live-assets-20261115/character.glb`，`KHR_materials_variants`）。每張卡片：
  - **外觀預覽**：用同一份 `character.glb` 的該 variant 材質渲染一個小 canvas（idle 姿勢）；渲染失敗時退回**色塊**，色塊顏色取該 variant 材質的 base color（不要寫死）。
  - **名稱**：「角色 T／A／B／C」，附衣色色塊（§11-1 已決定）。
  - 一行小字：該角色在所選場景腳本裡的出場秒數（取自 scenario，例如 A4-1 的 B 是 2.0–32.2 s）；換場景時更新。
- 使用者選場景、點一張角色卡片，再按「開始」。沒選角色不能按「開始」。按下後：
  1. 場景與角色寫入 `session.run_id`、`session.actor_id`，**之後沒有任何 UI 或鍵盤可以改它們**（驗收 A-4）。
  2. 呼叫 `POST /reset`（沿用）。回應新增 `session_id`（見 §5.3）。
  3. 開始模擬與擷取。
- 要換場景或角色只能重新載入頁面（等於新的一局，選單重新出現）。
- 測試與自動重播用網址參數 `?run=A4-1|B4-1`、`?actor=T|A|B|C` 跳過選單（沿用 `?auto=` 的重播模式不變；`?auto` 時玩家照該角色自己的腳本走，且不套用 §3 對玩家的阻擋，因為玩家就是腳本）。

### 1.2 操作（沿用現有 `operator.mjs` / `sim.mjs`）

- W／A／S／D 移動，Shift 跑。**方向相對於視角朝向 `view_yaw`（§1.3）**：W＝視角前方、S＝後、A＝左、D＝右；`view_yaw` 初值使 W＝世界 +Y（與 v1 相同），所以不動滑鼠時行為與 v1 一致。走 1.2 m/s、跑 2.5 m/s（`WALK`／`RUN`，與 N6 clip 速度一致）。斜向（W+D 等）速度不得大於單軸（向量先正規化）。
- 越肩視角、牆面半透明（只在 A 自己的畫面；虛擬鏡頭照常渲染不透明牆）：沿用，但越肩相機的朝向改由 `view_yaw`／`view_pitch` 決定（目前 `operator.mjs` 的相機如何跟隨玩家 heading，由 Codex 實作時確認並在 issue 回報；`UNKNOWN`）。玩家**人物自己的朝向**（`heading`，給 N6 動畫與虛擬鏡頭看到的外觀）仍取移動方向，不取視角。
- 牆面碰撞沿用（半徑 0.25 m，沿牆滑動）。
- 移除：句子輸入框、`red top／blue top` 下拉。目標不再由 A 決定。
- 玩家起點：被選角色的 waypoint[0] 的 xy；若 2 倍人物半徑（§3.1）內有腳本人物，往最近的空位微調並記在 log（`spawn_adjusted`）。

### 1.3 滑鼠轉視角（D279，§11-4）

只轉**視角**，不移動人物、不影響碰撞、不進 `/infer`、不進 B 可達的任何地方（和玩家座標一樣屬於 A 私有）。

- **模式**：預設 **pointer lock**（點 A 的畫布請求 `requestPointerLock`，`Esc` 釋放；釋放後不吃滑鼠移動，再點畫布重新鎖定）。pointer lock 不可用或被拒時（headless、被瀏覽器擋）退回**拖曳**：按住滑鼠左鍵拖曳轉視角。網址參數 `?mouse=drag` 強制拖曳、`?mouse=off` 關閉滑鼠（測試與自動重播用；`?auto` 重播時滑鼠固定關閉）。
- **靈敏度**：`mouse_sens_deg_per_px = 0.15`（設定物件欄位）；pointer lock 用 `movementX／movementY`，拖曳用游標位移，兩者同一換算。向右移＝視角向右轉（`view_yaw` 順時針，從上往下看）；向上移＝抬頭（`view_pitch` 增加）。Y 軸不反轉。
- **角度**：`view_yaw` 無範圍限制（取模 360°）；`view_pitch` 限制在 `[−15°, +50°]`（`pitch_min_deg`／`pitch_max_deg`），避免相機穿牆或翻轉。單次事件位移上限 `|Δ| ≤ 200 px` 後才換算（防止 pointer lock 重新鎖定時的跳動）。
- **和 WASD 的相對方向**：WASD 的世界方向 ＝ 把「前＝`(sin(view_yaw), cos(view_yaw))`」旋轉後的向量；`view_yaw = 0` 時 W＝+Y、D＝+X。只轉視角不按鍵時人物不動。
- **不改的**：不能用滑鼠點選、攻擊或其他互動；選單與按鈕仍用滑鼠點擊（pointer lock 只在開始後、點畫布時才啟動；`Esc` 不會重開選單，也不能換角色，A-4）。
- **純函式**（無 DOM，便於測試）：新增 `frontend/live-mode/src/view.mjs`，輸出 `applyMouseDelta(view, dx, dy, cfg) → view'`（含 pitch 夾限與單次上限）與 `moveVector(keys, view_yaw, speed) → {vx, vy}`（正規化斜向）。`operator.mjs` 只負責把 DOM 事件餵進這兩個函式。
- **測試方式**：
  1. 單元（`mouse_view.test.mjs`，驗收 A-5）：`applyMouseDelta` 的方向、靈敏度（dx=100 → 15°）、pitch 夾限、單次上限；`moveVector` 在 yaw = 0／90°／180°／270° 時 W 對應 +Y／+X／−Y／−X、斜向速度不超過單軸、與 v1 的 `stepPlayer`（yaw = 0）逐步結果相同。
  2. 瀏覽器（§8.6，截圖進 PR）：點畫布→移動滑鼠→畫面轉動，WASD 方向跟著轉；`Esc` 釋放後移動滑鼠視角不動；`?mouse=drag` 拖曳同樣可用。headless 無法驗 pointer lock，只驗拖曳與純函式，並在 result record 的 Not verified 寫明 pointer lock 真實手感未驗。

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
- 設定物件欄位：`r_person`、`r_wall`、`wait_max_mutual_s`（腳本人物彼此互擋的上限，3 s）、`eps_m`（量測容差 0.02 m）。**沒有 `wait_max_player_s`**：玩家擋路時等待無上限（D279，§3.4）。

### 3.2 玩家

- 玩家每步嘗試移動到 `p'`。若 `p'` 與任何**顯示中**的其他人物中心距離 `< 2r`，**且比目前距離更近**，這個方向的移動取消；改試只動 X、只動 Y（和現有牆面滑動同一個作法）。都不行就原地不動。
- 「且比目前距離更近」是為了避免卡死：如果已經在 `2r` 內（例如出生時或對方走過來），玩家仍可以往遠離的方向走。
- 玩家**永遠不會被推動**（人物不能擠玩家）。玩家的提案位移與腳本人物的提案同時進入 §3.3 的成對檢查；玩家在檢查中依序試 full → 只 X → 只 Y 候選位移。

### 3.3 腳本人物 vs 玩家與其他人物

每個模擬步進（`dt`），所有顯示中的實體（玩家＋腳本人物）**同時**由同一份快照（步初位置）算出各自的預定位置，再做**成對相對移動檢查**（v1 只比對「自己的預定位置 vs 對方的上一步位置」，兩人同時往內走仍會穿模：中心 0 與 0.8 m、dt = 0.1、各向內走 0.12 m，兩邊各看 0.68 m 而放行，步後 0.56 m < 0.58 m；v2 以同步位移檢查取代）：

1. **提案**：玩家的提案依 §3.2 的候選位移（full → 只 X → 只 Y，各自須通過牆面）取第一個；腳本人物 `i` 的提案是 `scriptedPose(s_i + dt)`（`s_i + dt` 超出出場範圍時該人物不顯示，不參與檢查）。
2. **成對檢查**：對每一對顯示中的 `(i, j)`，令 `d_cur = |p_i − p_j|`（步初）、`d_new = |p'_i − p'_j|`（兩人**都用提案位置**）。若 `d_new < 2r` **且** `d_new < d_cur`（正在靠近）→ 這一對違規。
3. **依固定優先序拒絕**：優先序 **玩家 > T > A > B > C**。對違規的一對，**先拒絕優先序較低且本步有移動的一方**（它的位置不變、`s_i` 不前進、速度 0、播 idle）；拒絕後重新檢查（被拒絕者的提案換成步初位置），仍違規則再拒絕另一方（玩家改試下一個候選位移，都不行才原地）。重複到沒有違規為止（最多實體數輪）。
4. 通過檢查的人照提案前進。腳本人物**不偏離折線、不被推動**；玩家**不被推動**，擋住是互相的（人物不能擠玩家，玩家也不能穿人物）。

驗算（C-8）：中心 0 與 0.8 m 各向內 0.12 m → 違規（`d_new = 0.56 < 0.60`，且 < 0.8）；拒絕較低優先序者後，另一人 0.12 m 對步初位置 0.8 m 的距離 0.68 m ≥ 0.60 m，放行。

特性：

- 腳本人物**不偏離路線**，沒有繞路；前方有人就停，對方離開（或自己不再「靠近」）就繼續。
- 擋住只看「正在靠近」，所以已經在 `2r` 內的人可以往外走，不會互鎖在重疊狀態。
- 暫停只延後該人物自己的腳本（§2.2），不是整個場景。

### 3.4 等待與死結（D279：玩家擋路「一直等」）

- **被玩家擋住：一直等，無上限。** 玩家站著不動時，被擋住的腳本人物持續等待（位置不變、`s_i` 不前進、播 idle），**不穿過、不記 `forced_overlap(kind:'player')`**；其他人物與模擬照常前進（每個人物只被「正在靠近的對象」擋住，沒有全域暫停，所以不會死結）。玩家走開（或不再擋住）後，下一步即恢復。展示時被擋的人會站著不動，這是已接受的後果（§11-3）。
  - 腳本人物會一直等到玩家離開；**沒有任何逾時機制能讓玩家被「穿過」**。
  - 記錄（不是違規）：每個腳本人物被玩家擋住的連續秒數 `block_wait`：`{i, j:'player', waited_s}`，事件結束時寫一筆；供 §7 報表「腳本人物被擋住的總秒數」。
- **被另一個腳本人物擋住（含互相擋住）：規則不變，`wait_max_mutual_s = 3 s`。** 超過上限就穿過並記錄，只有**優先序較後**（T < A < B < C，C 最後）的那一個穿過，另一個照常。「穿過」＝這一個人物暫時不做 §3.3 的步驟 2，直到它和對方的距離重新 `≥ 2r`（或對方不再顯示）。每次穿過記一筆 `forced_overlap` 事件：`{tick, t_sim, i, j, kind:'script', cause, waited_s, dist_m, chain, tainted}`（`cause`、`tainted` 見下「相位差與 `cause`」）。
- **連鎖（v2，D279 的後果）**：玩家擋住 `i` 之後，`i` 的位置不動；另一個腳本人物 `j` 若沿路線走到 `i` 後面，會被 `i` 擋住，3 s 後穿過。`chain: true` 表示對方 `j` **當下**正被玩家擋住。連鎖是「相位差」的特例（v2.1：`chain:true` 的事件一定同時是 `cause:'player_phase_shift'`）。
- **相位差與 `cause`（v2.1，D282）**：玩家擋路讓人物 `i` 的 `s_i` 停住 `pause_player_i` 秒，之後 `i` 整條腳本永久晚這麼多。原 scenario 的「兩人錯開 ≥ 0.68 m」只在原時間線成立；相位分開後，兩個腳本人物可能在玩家早已離開後才在同一處相遇。這不是不碰撞邏輯的錯，不算 C-5 失敗，但必須分開計數。判定方法（只看 A 端狀態，可重播、可測）：
  1. 每個腳本人物 `i` 有 `pause_player_i`（只累計被**玩家**擋住的秒數）與 `pause_script_i`（只累計被腳本人物擋住的秒數）；`pause_total_i = pause_player_i + pause_script_i`（C-4、C-6 的 `pause_total_i` 不變）。
  2. **污染集合 `tainted`**（單調，只增不減，一個 run 內不重置）：`i` 在 `pause_player_i > 0` 的那一步加入；`i` 因為等一個**已污染**的腳本人物 `k`（`k ∈ tainted`）而等待的那一步也加入（傳遞：被被擋住的人擋住，也算相位被改過）。
  3. 每筆 script–script `forced_overlap` 在穿過發生的那一步判定：`i ∈ tainted` 或 `j ∈ tainted` → `cause:'player_phase_shift'`；否則 `cause:'script'`。事件的 `tainted` 欄記該步兩人各自是否在集合內：`{i:bool, j:bool}`。
  4. 無玩家基線（沒有玩家實體，或玩家從未擋住任何人）時 `tainted` 恆為空，所有事件都是 `cause:'script'`。
  5. 交叉檢查（測試用，不進產品）：同 seed、同 scenario、**移除玩家**重跑，`cause:'player_phase_shift'` 的事件不應出現（它們只是相位差的後果）；`cause:'script'` 的事件兩次都會出現。
- 預期：v2.3 兩個 run 的腳本人物彼此間因為最近 0.68 m ≥ 0.60 m 而不會被擋；沒有玩家擋路（`tainted` 為空）時，**腳本人物之間 `forced_overlap(cause:'script')` 的預期次數是 0**（驗收 C-5）。

### 3.5 離線驗證（先做，作為測試）

- 純模組 `frontend/live-mode/src/crowd.mjs`（無 DOM，無 three）：`validateScripts(run, cfg)` 以 0.1 s 間隔取樣整段，對每一種選角（含不選，共 5 種）回報兩人最近距離與 `< 2r` 的區段。
- 規格要求：A4-1、B4-1 在 `r_person = 0.30` 時，**所有 actor 配對**最近距離 ≥ 0.60 m。若 Codex 發現與上表不符，在 issue 回報，不要自己改腳本檔（scenario 屬於 frozen 輸入，D89）。

### 3.6 可測的驗收條件（碰撞）

以 headless 模擬（不渲染，固定 `dt = 0.1 s`、固定亂數種子）跑 A4-1 兩圈（100 s 模擬時間）、四種選角各一次，玩家用一個固定種子的隨機走動機器人（含刻意朝人物衝）：

| 編號 | 條件 |
| --- | --- |
| C-1 | **玩家穿模次數 = 0**：任何一步結束後，玩家與任何顯示中人物的中心距離 `< 2r − eps` 的次數為 0。排除：出生時已在 `2r` 內但之後不再更靠近的（記錄在 `spawn_adjusted`），以及有明確 `forced_overlap` 活動的配對的步數（v2 玩家不會被穿過，預期此類為 0）；**同時另報原始穿模數**（不排除任何步），不得無聲放寬 |
| C-2 | **分離比例 ≥ 0.99**：所有取樣步（每步每一對顯示中的人物）中，距離 `≥ 2r − eps` 的比例；`forced_overlap` 期間的步數排除並另列 |
| C-3 | 腳本人物**不偏離路線**：每個腳本人物每一步的位置都落在其 waypoint 折線上（誤差 ≤ 1 mm） |
| C-4 | 暫停只延後自己：人物 `i` 的 `s_i`（腳本時鐘）= 模擬時間 − `pause_total_i`；其他人物的 `s_j` 不受 `i` 影響（以兩次模擬，一次有機器人、一次沒有，比較沒被擋住且未受連鎖影響的人物，位置序列完全相同） |
| C-5 | 腳本人物彼此之間的 `forced_overlap`，依 §3.4「相位差與 `cause`」分兩類：(a) **無玩家基線**（A4-1、B4-1，移除玩家實體、固定 seed）：全部事件數 = 0；(b) **有玩家**（A4-1、B4-1 各四種選角，玩家機器人隨機走動，含 seed 0x568 壓力案例）：`cause:'script'` 次數 = 0；`cause:'player_phase_shift'`（含 `chain:true`）另外計數並逐筆列出（`i`、`j`、`tainted`、`pause_player_i/j`、`t_sim`），**不設閘門、不算 C-5 失敗**。報表同時列出兩個數字，不得把 `player_phase_shift` 併入或隱藏。**反例回歸測試**：#568 的 A4 玩家 T @78.7 s 案例（C 3 s 後穿過 B，B 先前被玩家擋 21.9 s）必須分到 `player_phase_shift`；另需負向對照：兩個都未被玩家影響的腳本人物被迫互擋穿過（測試覆寫 `wait_max_mutual_s` 製造）必須是 `cause:'script'` |
| C-6 | **一直等且沒有死結**：玩家站在某腳本人物 `i` 的路線上不動 60 秒（A4-1、B4-1 各挑一個會被擋住的位置）：(a) `i` 被擋住期間位置不變、`s_i` 不前進，`forced_overlap(kind:'player')` 次數 = 0（不論等多久，包含超過 8 s）；(b) 模擬照常以固定 `dt` 前進、不卡住；(c) 沒被擋住且未受連鎖影響的腳本人物，位置序列與沒有玩家的基準模擬相同；(d) 玩家走開後，`i` 在 1 步內恢復前進；(e) 進展以 `s_i` 和 `pause_total_i` 驗證（`s_i = 模擬時間 − pause_total_i`，且 `pause_total_i` ≥ 被擋住的總秒數），**不要求** 60 s 內走完一圈（暫停後總時間不保證 ≤ 60 s）；(f) 連鎖的 script–script `forced_overlap(chain:true)` 允許出現但必須有記錄 |
| C-7 | 每步計算 ≤ 1 ms（4 個實體；用 `performance.now` 平均，只作回報不作閘門，列在 result record） |
| C-8 | **成對相對移動不穿模**：兩人中心距離 0.8 m，同一步各向內走 0.12 m（dt = 0.1）；步後距離 ≥ 2r − eps，被拒絕者是優先序較低且有移動的一方，腳本人物不偏離折線、玩家不被推動。另含：玩家朝正在走近的腳本人物衝（雙方都有移動）、玩家朝已暫停的人物衝（對方原地不動）、三人同時進入同一點。實作須通過「提案＋成對檢查＋依序拒絕」，不得只做「自己提案 vs 對方舊位置」的端點檢查 |

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

### 4.2 選特徵與句子（D279，§11-5：接 Q3 解析器）

- 顏色 chip 必選一個（`red`／`blue`），除非句子能解析出顏色。
- 句子（選填，≤ 80 字）由**後台**用 Q3 一句話解析器解析（N1，`src/amidst/q1q5/nl_query_parse.py`，契約 [NL_QUERY_PARSE_V1](../contracts/NL_QUERY_PARSE_V1.md)；已在 `main`）。介面（`main` 上實際存在）：`parse_nl_query(text, vocab, *, mode='RULES', api=None, local=None, timeout_ms=2500, clock=…) → {schema_version, action: '查找'|'追蹤'|null, location: [], target: [], time: {start,end}|null, unrecognized: [], parser, latency_ms, cost_usd, fallback_trail}`；詞彙是 `NlVocabulary(class_labels, color_labels, region_ids, class_aliases, color_aliases, region_aliases)`（`vocabulary_from_catalog(catalog)` 或直接建構）。
- **即時模式的詞彙**是固定的小詞彙（後台建構，不讀 run catalog）：`class_labels = ('person',)`、`color_labels = ('red','blue')`、`region_ids = ()`，別名沿用 Q3 現有的紅／藍、紅衣／藍衣對照（實際別名表來源 `UNKNOWN`，Codex 實作時確認並在 issue 回報）。
- **結果對應**：
  - `target` 含 `red`／`blue` 其中恰好一個 → 該顏色；**兩個都有** → 400 `FEATURE_AMBIGUOUS`（不任意挑色）；都沒有且沒有 chip → 400 `FEATURE_REQUIRED`。
  - chip 與句子顏色衝突 → **以 chip 為準**，回饋文字說明（`parse.note:'CHIP_OVERRIDES_SENTENCE'`）。
  - `action = '查找'` 或有 `location`／`time`：即時模式只有「追蹤」，這些欄位**忽略並告知**（`parse.ignored` 列欄位名），不是錯誤。
  - `unrecognized` 不回傳原文片段，只回 `unrecognized_count`。**句子原文不 echo、不進 log 以外的任何地方**（沿用 v1）。
- **模式與付費**：預設 `RULES`（不花錢、不連網）。**LLM 只走 #563 已合併的 LLM 開關**（`src/amidst/live_mode/llm_switch.py` 的 `resolve()`；預設 `off`）：開關 `effective = off` 時，句子解析固定 `RULES`；開關開啟且後台 ApiGuard 已核准時，才讓 `parse_nl_query(mode='API')` 的 API → LOCAL → RULES 鏈生效（逾時 2500 ms 退回 RULES）。**付費呼叫另外核准**：先 dry-run，使用者在對話裡核准金額才實跑；核准的預算只用於這個用途，不沿用 advisor 的預算、不用 WP5 的 USD 46（D242）。CI 一律用 fake client，不呼叫真實 API。#563 開關原本是 advisor 的 `off/review/lead`；本功能只讀 `effective != off` 當作「允許 LLM」，不新增第二個開關。ApiGuard 實際接線（`clients_from_environment(env, guard)`）在 live server 的做法 `UNKNOWN`，Codex 實作時確認；若需要新增開關欄位，在 issue 提出，不要自己加。
- 解析在**取得追蹤狀態 lock 之前**完成（網路呼叫不得持有 lock，§5.4）。

### 4.3 候選只能來自 B 自己從鏡頭畫面得到的資料

- 候選 = 後台在最近一輪 `/infer`（所有被推論的鏡頭）的偵測中，顏色符合的人，依地面位置 `est_xy` **分群**（距離 `< 1.5 m` 視為同一個人，與 `tracker.py` 目前的「同一處」規則一致；多個鏡頭看到同一人只算一個）。
- 一個候選含：`cand_id`、`tick`、`cam`（群中偵測分數最高那一支）、`bbox`、`score`、`color`、`est_xy`（全部都是現有白名單內的偵測欄位，後台由像素推得）。**沒有任何身分、角色、GT 欄位**。
- **不能讀 A 的角色選擇或位置**：B 只經 BroadcastChannel 收 `frame-batch`（protocol 白名單）和呼叫後台 `/track/*`（§5）；A 的 `session.actor_id`、玩家座標、腳本人物座標不會出現在 B 可達的任何地方（驗收 G-1～G-4）。
- 開始追蹤時：
  - **只有 1 個符合者** → 直接鎖定，`TRACKING`。
  - **0 個** → 保持 `ACQUIRING`，每輪重試；回饋文字「畫面中沒有符合的人」；使用者可隨時停止。
  - **≥ 2 個** → `NEEDS_PICK`：列出候選讓使用者點選。畫面上 B 用該候選的 `cam` 和 `bbox` 在對應鏡頭影格上畫編號框（1、2、3…，由左至右）；同時在右側小地圖畫對應 `est_xy` 的編號點；列表每項顯示「編號・鏡頭・位置」。使用者點框、點列表項或點地圖點都等於選取。B 保留最近 5 輪的 `frame-batch`，用候選的 `tick` 找對應影格；找不到就只顯示列表和地圖點（退回列表／地圖）。注意這個 5 輪是 B 的**影格快取**，與後台候選保留的 7 個 generation（§5.4）是兩件事。
- 候選選定前，**後台不鎖定任何人**（首次選取時追蹤狀態 `NEEDS_PICK`；改選時舊目標繼續追，§4.4）。選定後的追蹤用現有 `tracker.py` 的跟隨、切鏡、失聯邏輯，不改規則；只改「怎麼起始鎖定」和「目標顏色可以是 blue」（§5.4）。

### 4.4 改選與停止

- 改選目標（`TRACKING` 中）：按「改選目標」→ B 送 `POST /track/start {color: 目前色, reselect: true, session_id}`（§5.4）。後台**保留舊 tracker 與尾跡繼續追**，只把選取狀態切到 `NEEDS_PICK`，回傳目前候選；B 進入選取畫面，**即使只有一個候選也要使用者確認**（改選的目的就是換人，永不 `AUTO_SINGLE`）。選定（`POST /track/pick`）後新目標生效，舊目標的 est_xy 與尾跡清掉。選定前 HUD 沿用目前的追蹤狀態（`tracking.state` 仍為 `TRACKING`，舊目標繼續追；`tracking.target.mode` 是 `NEEDS_PICK`）。
- 使用者也可以改選另一個顏色再「開始追蹤」：這是**一般 start**（`reselect` 省略或 false），照 §5.4 規則清掉舊目標。
- 改選中要放棄：按「停止追蹤」（回 `IDLE`）；或在候選中再選回原目標。不另設「取消改選」端點（`UNKNOWN`／已知限制：原目標若當下不在畫面，只能停止）。
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

### 5.2 `frame-batch`（A→B，BroadcastChannel）：只加兩個鍵，並檢查 nested

`protocol.mjs` 的白名單現況不變，只新增：

| 位置 | 鍵 | 型別 | 說明 |
| --- | --- | --- | --- |
| `tracking` | `target` | `{color: 'red'\|'blue'\|null, mode: 'IDLE'\|'ACQUIRING'\|'NEEDS_PICK'\|'TRACKING'}` | 後台輸出，是 B 自己選的目標的回聲；`TRACK_KEYS` 加 `target`，並新增 `TARGET_KEYS = {color, mode}` 逐層過濾與驗證（`target` 內只准這兩個鍵，型別與 enum 逐一檢查） |
| `tracking.state` | （值） | 現有值加 `IDLE`、`NEEDS_PICK` | `validateSystemMessage` 要接受這兩個值 |

**nested 物件也要逐層檢查**（G-2 的「逐層禁止鍵」承諾）：`tracking.events[].detail` 與 `timing_ms` 目前是任意物件，只加 `TARGET_KEYS` 不足以防止把 `actor_id`／`gt` 等塞進去繞過。要求：

- `events[].detail`：依事件類型各定一組允許鍵與值型別（`ACQUIRE.detail.by` 只接受 `USER_PICK`／`AUTO_SINGLE`；其他事件類型沿用**現有合法形狀**，由 Codex 實作時從現行程式列舉出來寫進 `protocol.mjs`，並在 issue 回報清單；原則：不在清單內的鍵＝違規，值只准有限數字、短字串〔≤ 64 字〕、字串／數字陣列、白名單內的 nested 小物件）。
- `timing_ms`：只准已知的計時鍵（現有鍵由 Codex 列舉），值必須是有限數字。
- 任何 `NaN`／`Infinity` 座標或缺投影 → 不製造候選、不製造 `est_xy`，該欄位保持 `UNKNOWN`／`null`（不補預設值）。
- 逐層檢查的深度：整則訊息遞迴檢查，禁止鍵在**任何層級**出現都算違規並整則丟棄。

仍然**禁止**（`validateSystemMessage` 逐層檢查，任何其他鍵都算違規並整則丟棄）：`actor_id`、`role`、`variant`、`person_id`、`operator_xy`、`player_xy`、`gt`、`gt_visible`、`waypoints`、`s_i`、`script_*`、`pause_*`、`forced_overlap`、`spawn_adjusted`、`run_id`、`view_yaw`、`view_pitch`，以及任何 `session.*`。

### 5.3 `POST /reset`（A→後台，沿用）與 `session_id`

- request：不變（空物件）。
- response：`{"ok": true, "session_id": "<16 hex>"}`。`session_id` 是後台產生的隨機 token，**不含角色資訊、不由 A 提供**；後台**啟動時就建立 session**，每次 `/reset` 換新 token，並**原子地**把追蹤模式重設為 `IDLE`、清掉選取、tracker、advisor、候選歷史。
- A 在按「開始」時呼叫（§1.1）並**記住** `session_id`（寫進 A 的私有 log，§5.6），但**不**把它放進 `frame-batch`；B 自己從 `GET /track/state` 得知。
- `session_id` 的用途：B 的三個 POST 都帶它，避免上一局延遲到達的 `start`／`stop`／`pick` 改到新的一局。它不是角色／GT 資料，不增加 A→B 的白名單鍵。

### 5.4 B→後台新端點（都在 `server.py`，同一個埠，JSON，UTF-8）

共同規則：

- request 必須是 JSON 物件。只接受下表列的鍵；多出來的鍵回 **400** `FIELD_NOT_ALLOWED`，`fields` 只列**鍵名**，不回值。GET 的 query 鍵同樣只接受列出的。
- 數字必須是有限值；enum、長度（`sentence` ≤ 80 字、`cand_id` ≤ 64 字、`session_id` 恰 16 hex）逐項驗證。
- **錯誤格式**：`{"error": "<CODE>", "detail"?: "<人讀文字>", "fields"?: ["<鍵名>"…]}`。`fields` 只用於 `FIELD_NOT_ALLOWED`；`detail` 不含 request 的值（尤其不含句子原文）。
- **一致性**：所有狀態讀寫與 `/infer` 的候選快照在**同一個 lock** 內完成；網路呼叫（句子的 API 解析）在 lock 外先做完。
- **response 用明確白名單輸出**，並有測試（G-5）。

端點總表：

| 端點 | request／query | response 200 | 錯誤 |
| --- | --- | --- | --- |
| `POST /track/start` | `{color?: red\|blue, sentence?: str, reselect?: bool = false, session_id}` | `{mode, color, tick, candidates, parse?}`（見下） | 400 `FEATURE_REQUIRED`／`FEATURE_AMBIGUOUS`／`COLOR_UNSUPPORTED`／`FIELD_NOT_ALLOWED`／`SESSION_REQUIRED`；409 `SESSION_MISMATCH`／`TRACK_MODE_CONFLICT` |
| `POST /track/pick` | `{cand_id, session_id}` | `{mode:'TRACKING', color, picked}` | 404 `CANDIDATE_UNKNOWN`；409 `CANDIDATE_STALE`／`TRACK_MODE_CONFLICT`／`SESSION_MISMATCH` |
| `GET /track/candidates` | query：`color?: red\|blue\|any` | `{tick, color, candidates}` | 400 `FIELD_NOT_ALLOWED`／`COLOR_UNSUPPORTED` |
| `POST /track/stop` | `{session_id}` | `{mode:'IDLE'}` | 409 `SESSION_MISMATCH` |
| `GET /track/state` | 無 query 鍵 | `{mode, color, session_id, tick}` | 400 `FIELD_NOT_ALLOWED` |

候選物件：`{cand_id, tick, cam, bbox:[x0,y0,x1,y1], score, color, est_xy:[x,y]}`（全部是現有白名單內的偵測欄位）。

**`POST /track/start`**

- `color` 與 `sentence` 至少要能得到一個顏色（§4.2：chip 優先；句子經 Q3 解析器；無 chip 且句子同時有紅藍 → 400 `FEATURE_AMBIGUOUS`，不任意挑色）。`session_id` 必填，缺 → 400 `SESSION_REQUIRED`；不符目前 session → 409 `SESSION_MISMATCH`。
- **一般 start**（`reselect` 為 false）：清掉舊目標（est_xy、lost、active、tail 都重設）、新 epoch，再依候選數：
  - 1 個候選 → 立刻鎖定，`mode:'TRACKING'`，ACQUIRE 事件 `detail.by:'AUTO_SINGLE'`；
  - 0 個 → `mode:'ACQUIRING'`，之後每輪 `/infer` 若出現**恰好 1 群**就 `AUTO_SINGLE` 自動鎖定；若出現 ≥ 2 群則轉 `NEEDS_PICK`，**一旦進入 `NEEDS_PICK` 就不會因下一輪只剩 1 人而自動鎖定**；
  - ≥ 2 個 → `mode:'NEEDS_PICK'`，不鎖定。
  - **尚無任何 `/infer`**（開機後第一次 start）：**200**，`mode:'ACQUIRING'`、`tick:null`、`candidates:[]`（v1 的 409 `NO_DETECTIONS_YET` 刪除；定案理由：這是正常等待狀態，不是衝突）。
- **改選**（`reselect: true`）：只在目前 `mode = TRACKING` 且 `color` 等於目前顏色時允許，否則 409 `TRACK_MODE_CONFLICT`（換色請用一般 start）。保留舊 tracker／尾跡直到 pick，選取模式進 `NEEDS_PICK`（**1 人也不 auto**，不 `AUTO_SINGLE`），回傳目前候選；`advisor` 派發暫停至選定。此時 `/infer` 的 `tracking.state` 維持 `TRACKING`，`tracking.target.mode` 與 `/track/state.mode` 是 `NEEDS_PICK`（§5.5）。
- **句子解析結果** `parse`（只在有 `sentence` 時回）：`{parser:'RULES'|'API'|'LOCAL', note?:'CHIP_OVERRIDES_SENTENCE', ignored:[欄位名…], unrecognized_count:n}`；不含原文或片段。
- 新的 start／pick／stop／reset 都使**舊的 epoch 失效**（見 pick）。

**`POST /track/pick`**

- 只在 `NEEDS_PICK`（首次選取或改選）有效；`IDLE`、尚未 start、已在 `TRACKING` 且不在改選中 → 409 `TRACK_MODE_CONFLICT`（不可用預覽候選繞過開始）。`ACQUIRING` 中也是 409。
- 後台以該候選的 `est_xy` 和 `cam` 作為追蹤起點（`est`、`active`、`t_seen`），發出 `ACQUIRE` 事件（`detail.by:'USER_PICK'`）。`picked.color` 必須在**本輪意圖的顏色集合**內，否則 404 `CANDIDATE_UNKNOWN`。
- `cand_id` 是後台發的不透明字串，**綁 session、epoch、tick、序號**（例如 `c<session前8碼>.<epoch>-<tick>-<n>`；格式由後台決定，B 不解析）；**不可重用**，reset 後 tick 歸零也不會撞號。
- 判定順序：格式不符或不屬於本 session 的格式 → 404（帶了 `session_id` 但與目前不符先回 409 `SESSION_MISMATCH`）；epoch 已失效（期間有新的 start／pick／stop／reset）或 `age > stale_ticks` → **409 `CANDIDATE_STALE`**（stale id 必須能與「從未存在」區分，不能因為快取被清掉就變 404：判定靠 id 內含的 epoch／tick 與目前狀態，不靠候選表是否仍有該列）。
- **stale 邊界**：`stale_ticks = 6`；`age = 目前最新 tick − 候選 tick`；`age ≤ 6` 接受，`age > 6` 拒絕。因此後台**保存最新 ＋ 前 6 輪共 7 個 generation** 的候選表（保存 6 個會讓 `age = 6` 提前變 404）。
- B 收到 409 `CANDIDATE_STALE` 後重新 `GET /track/candidates`（改選中）或重新 start。

**`GET /track/candidates`**

- query：`color`（選填，`red`／`blue`／`any`；預設目前目標色，沒有目標色時 `any`）。response 的 `color` 型別為 `'red'|'blue'|'any'|null`。
- **GET 保持只讀**：不能靠 GET 進入改選模式、不改 epoch、不鎖定；沒有偵測時 **200**，`candidates:[]`、`tick:null`。`IDLE` 時仍回最近的候選（供預覽），但這些候選的 `cand_id` 在 `IDLE` 不能 pick（`TRACK_MODE_CONFLICT`）。

**`POST /track/stop`**

- request：`{session_id}`。response 200：`{mode:'IDLE'}`。**冪等**（已經 `IDLE` 也回 200）。後台重設 tracker、advisor、選取 epoch（沿用 `/reset` 的重設方式），**不換 `session_id`**，仍持續更新像素候選。

**`GET /track/state`**

- response 200：`{mode, color: …|null, session_id, tick: n|null}`。`mode` 取 `IDLE`／`ACQUIRING`／`NEEDS_PICK`／`TRACKING`；改選中是 `NEEDS_PICK`。B 每 1 秒輪詢；`session_id` 變了代表 A 重新開始一局，B **清掉 intent、候選與影格快取與舊請求結果**，回到 `IDLE`。

### 5.5 `/infer` 的行為改動（後台）

- 新增追蹤模式 `IDLE`（開機預設）：`/infer` 照常偵測、排程、回 `dets`，並**更新 red／blue 候選**；tracker 不鎖定、不發事件、advisor 不問，回 `tracking = {state:'IDLE', active_cam:null, seen_cams:[], est_xy:null, events:[], lost_ticks:0, target:{color:null, mode:'IDLE'}}`。`active = null` 所以排程用「全鏡頭」模式（沿用 `INITIAL_SEARCH`／`ALL_CAMERAS`，與 #553/#559 的排程一致；#559 合併後以它的行為為準）。
- `ACQUIRING`：start 之後、尚無鎖定。只有這個模式允許 `AUTO_SINGLE`（恰好 1 群時自動鎖定）；進入 `NEEDS_PICK` 後不再自動。`tracking.state = 'SEARCHING'`（沿用現有值）、`target = {color, mode:'ACQUIRING'}`。
- `NEEDS_PICK`（首次，沒有舊目標）：`tracking.state = 'NEEDS_PICK'`、`target.mode = 'NEEDS_PICK'`；不鎖定；**不問 advisor**。
- `NEEDS_PICK`（改選，有舊目標）：`tracking.state` 維持 `TRACKING`（舊 tracker 繼續跑），`target.mode = 'NEEDS_PICK'`；advisor **暫停派發**直到選定。
- `tracker.py` 目標顏色參數化（`target_color`，預設 `red`，行為與現在相同）；`est_xy` 的地面投影對 `red`、`blue` 偵測都算（現況只對 red 算，B 要畫藍衣候選的位置需要）。追蹤／切鏡／失聯規則與 ApiGuard 不改。
- 起始鎖定改為：只在 B 要求後鎖定，不再「所有紅衣人在同一處就自動鎖定」。`pick` 直接以候選起始。
- 候選表：`/infer` 每輪結束後，後台用該輪偵測更新候選表（§4.3 的分群），保留 7 個 generation（§5.4）。
- 追蹤中、失聯、切鏡、advisor（LLM 開關，#563）全部沿用。
- 事件（`events`）新增 `detail.by:'USER_PICK'|'AUTO_SINGLE'`（`ACQUIRE`），在 `EVENT_KEYS` 與 §5.2 的 nested 檢查內。
- 實作以 #559 合併後的 `infer()` 為準；#559 若改了回傳形狀，在 issue 提出，不先動（#566 子 issue 的依賴欄）。

### 5.6 A 端記錄 vs B 端記錄（不可混）

| 記錄 | 在哪 | 內容 | 能不能進 B |
| --- | --- | --- | --- |
| A 的私有 log（`window.__log`，下載成 JSON） | A 的視窗 | `schema_version: 'live-ab.a-log.v1'`、`session_id`（`/reset` 回傳）、`run_id`、被選 `actor_id`、設定物件快照；每 tick：`tick`、`t_capture`、`actors: [{id, present, xy, gt_visible}]`（**每個 actor** 都記，含玩家與所有腳本人物；`present` 是否顯示中；`xy` 真實位置，不顯示時 `null`；`gt_visible` 是該 actor 在哪些鏡頭可見，`groundTruthVisible`）、`pause_total_i`、`pause_player_i`、`pause_script_i`、`spawn_adjusted`、`forced_overlap`（含 `cause`、`tainted`）、`block_wait` | **不行**（§5.2 禁止清單；B 與後台完全不接收） |
| B 的追蹤記錄（`window.__log`，沿用並擴充，下載成 JSON） | B 的視窗 | `schema_version: 'live-ab.b-log.v1'`、`session_id`（`GET /track/state` 得知）；每則 `frame-batch`：`tick`、`t_capture`、`t_resp`、`t_display`、`tracking.state`、`target`、`active_cam`、`est_xy`、`lost_ticks`、`events`；B 的操作：`start`／`pick`（含 `cand_id`、候選 `est_xy`、候選 `tick`、操作時刻 `t_op`）／`reselect`／`stop`；HUD 延遲序列（最近 1 秒中位數） | — |
| 評分 | 事後離線（§7），輸入是 A 和 B 各自下載的兩個 JSON | — | 評分程式在視窗之外 |

A 的 log 需要**每個 actor** 的 `gt_visible`，因為 B 可以選任何腳本人物當目標，只用被選角色的可見性無法評分。A 的 log 只在 A 的視窗與使用者下載的檔案裡，不經 BroadcastChannel、不經後台。

## 6. 角色與選目標的獨立性

被選角色（玩家）**不等於**被追蹤的目標：B 的使用者可以追蹤任何一個符合顏色的人（含腳本人物，也可以追玩家自己的角色）。誰是目標由 B 的選擇決定，只有事後評分（§7）才把 B 選到的候選對到真實人物。

## 7. 評估紀錄與評分

### 7.1 事後評分：`scripts/live_ab_score.py`（離線）

- CLI：`python scripts/live_ab_score.py --operator-json A.json --system-json B.json --out result.json`（定案檔名與參數）。只讀這兩份輸入檔；**不 import 後台（`amidst.live_mode`）、不發 HTTP、不讀 scenario 或素材、不寫輸入檔**。輸入無法解析或 `schema_version` 不支援 → 非零結束碼與錯誤訊息（`result.json` 不產生）。輸出 `schema_version: 'live-ab.score.v1'`。
- **對齊**：先比對兩份 log 的 `session_id`（不同 → 整份 `UNKNOWN`，`unknown_reasons: ['SESSION_MISMATCH']`），再依 `tick` 與 `t_capture`（同一輪相同）嚴格對齊；缺 GT 或時鐘不合的 tick 記 `UNKNOWN` 並排除於比率之外，**不能把未知算成失聯**。

1. **目標身分（事後）**：每次 `pick`（或 `AUTO_SINGLE` 的 `ACQUIRE`），以**候選來源 tick** 的候選 `est_xy`，對該 tick 的 GT（A log 所有 `present` 的 actor）求距離：
   - 最近者距離 `≤ 1.5 m` → 該實體是「被追蹤者」`target_gt`；
   - 第一、第二近的距離都 `≤ 1.5 m` 且差 `< 0.05 m` → `AMBIGUOUS_PICK`（並列，不指定 `target_gt`，該段 `UNKNOWN`）；
   - 最近者 `> 1.5 m` → `MISPICK`；
   - 每次改選各算一段；**該段的生效區間用 B 的操作時刻 `t_op` 劃分**（不是候選的來源 tick）。
2. **每 tick 判定**（從選定後到停止／改選／結束）：
   - 目標在至少一個鏡頭看得到（`target_gt` 的 `gt_visible` 非空）時：
     - **跟對**：`tracking.state = TRACKING` 且 `dist(est_xy, gt_xy(target_gt)) ≤ 1.5 m`；
     - **跟錯**：`TRACKING` 但 `est_xy` 離 `target_gt` 超過 1.5 m，且在 1.5 m 內有別的實體（更靠近別人）；
     - **UNMATCHED**：`TRACKING` 但 `est_xy` 離**所有**實體都超過 1.5 m（補足 v1 沒有覆蓋的分類）；
     - **失聯**：`state = LOST`、或 `lost_ticks > 0`、或沒有 `est_xy`。
   - 目標任何鏡頭都看不到時：**不計入跟對率**，另外回報此時系統是否正確宣告離開視野／失聯（`TARGET_OUT_OF_VIEW`、`LOST`）。
3. 報表（JSON，另可輸出一張表）：每段追蹤的 `target_gt`／`MISPICK`／`AMBIGUOUS_PICK`、跟對／跟錯／`UNMATCHED`／失聯 tick 數與比例、跟錯的連續區段數（連續 ≥ 2 tick 算一次身分交換）、失聯次數與每次秒數、切鏡次數、**延遲分開列兩組**：(a) 原始 `t_resp − t_capture` 的 p50／p95，(b) #551 HUD 的「最近 1 秒中位數」序列的 p50／p95（兩者不混）、玩家穿模次數（與原始數）、`forced_overlap` 次數（依 `cause` 分列：`script`、`player_phase_shift`；`chain:true` 為 `player_phase_shift` 的子集，另列一欄）、`spawn_adjusted`、`block_wait` 腳本人物被擋住的總秒數，以及 `unknown_reasons`。
4. 閾值：**不設跟對率硬閾值**（§11-6 已決定：不訂目標，只出報表；既有的 0.45–0.62 是另一個定義的「作用中鏡頭看得到目標」比例，見交接 §8）。這份報表是展示紀錄。

### 7.2 GT 隔離（不可變弱）

- A 的 GT 記錄只供事後評分，**不進** B、不進後台、不進推論、排序或重建（DEVELOPMENT_RULES、AGENTS.md 共用規則）。
- 評分程式讀的是兩個已下載的 JSON，不在即時路徑上。
- v2 沒有放寬任何一條 v1 的隔離：§5.2 的禁止清單只增加（`run_id`、`view_yaw`、`view_pitch`）、nested 逐層檢查是新增的限制；新增的 `session_id` 是後台產生的 token，不含角色資訊；B 的句子只進後台的規則／LLM 解析，不含 GT；A 的 log 的 per-actor `gt_visible` 只在 A 的視窗與使用者下載的檔案。

## 8. 驗收條件（逐條可測）

測試命名：前端 `node --test`（`frontend/live-mode/test/`）；後台 `pytest`（`tests/live_mode/`、`tests/evaluation/`）。檔名與驗收的對應如下（Codex 審閱時確認，v2 定案；要改檔名須在子 issue 回覆）：

| 驗收 | 檔案 |
| --- | --- |
| F-1/F-2、A-2～A-4、G-6 | `frontend/live-mode/test/ab_menu.test.mjs` |
| A-5（滑鼠） | `frontend/live-mode/test/mouse_view.test.mjs`（新） |
| F-3、A-1、C-1～C-8、`validateScripts` 五種選角 | `frontend/live-mode/test/crowd.test.mjs` |
| F-4/F-5/F-6/F-8/F-12/F-13、G-4/G-5、session／stale／改選競態 | `tests/live_mode/test_track_endpoints.py` |
| F-11（句子 → Q3 解析器） | `tests/live_mode/test_track_sentence.py`（新） |
| F-7（red/blue 對稱） | `tests/live_mode/test_tracker_color.py` |
| F-4 前端、F-10（session 切換） | `frontend/live-mode/test/ab_flow.test.mjs` |
| F-9 | `frontend/live-mode/test/hud.test.mjs`（擴充） |
| G-1/G-2/G-3 與 nested 禁止鍵 | `frontend/live-mode/test/protocol.test.mjs`（擴充） |
| §7 離線對齊、`MISPICK`／`AMBIGUOUS_PICK`／`UNMATCHED`／`UNKNOWN`、分段、碰撞與延遲統計 | `tests/evaluation/test_live_ab_score.py`（新） |
| §8.5 回報、§8.6 瀏覽器流程 | 最終 feature PR 的 LOCAL 量測 log／截圖＋已提交的 handoff 文件（**不是**單元測試冒充瀏覽器驗收） |

### 8.1 功能（F）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| F-1 | 選單有場景（A4-1／B4-1）兩張卡片與 T/A/B/C 四張角色卡片，角色卡片有預覽或色塊與名稱；沒選角色就不能按「開始」；換場景時出場秒數更新 | `ab_menu.test.mjs`（以純函式 `menuState()` 驗證；DOM 部分用瀏覽器截圖紀錄） |
| F-2 | 按「開始」前 `/infer` 呼叫次數 = 0；按下後才開始擷取 | `ab_menu.test.mjs`（以 fake fetch） |
| F-3 | 選場景與角色後，該角色的腳本不執行；其餘 3 個 actor 的腳本人物存在且 variant 各不相同、與玩家不同（A4-1、B4-1 各五種選角檢查） | `crowd.test.mjs` |
| F-4 | B 的流程：`IDLE` →（選 red＋開始）→ 1 個候選：`TRACKING`；2 個候選：`NEEDS_PICK`→pick→`TRACKING`；改選→`NEEDS_PICK`→pick→新目標；停止→`IDLE` | `test_track_endpoints.py`＋`ab_flow.test.mjs`（B 端狀態機純函式 `reduceB()`） |
| F-5 | 兩個以上紅衣候選時，不會自動鎖定（`tracker.state` 保持非 `TRACKING` 直到 pick）；進入 `NEEDS_PICK` 後下一輪只剩 1 人也不自動鎖定 | `test_track_endpoints.py` |
| F-6 | `pick`：`age ≤ 6` 接受、`age > 6` 回 409 `CANDIDATE_STALE`（保留 7 個 generation）；已失效 epoch 的 id 回 409（不是 404）；未知／格式不符 id 回 404 | `test_track_endpoints.py` |
| F-7 | `blue` 目標：鎖定、跟隨、失聯行為與 `red` 相同（以合成偵測序列驗證） | `test_tracker_color.py` |
| F-8 | `IDLE` 時 `/infer` 回 `tracking.state = 'IDLE'` 且無事件 | `test_track_endpoints.py` |
| F-9 | HUD：`IDLE`／`NEEDS_PICK` 顯示文字與色調符合 §4.5；其餘 HUD 欄位測試（`hud.test.mjs`）不變且全過 | `hud.test.mjs` |
| F-10 | `session_id` 改變時 B 回到 `IDLE`，並清掉 intent、候選與影格快取、舊請求結果 | `ab_flow.test.mjs` |
| F-11 | B 的句子經 Q3 解析器：chip 優先；句子只有紅／只有藍 → 該色；紅藍都有且無 chip → 400 `FEATURE_AMBIGUOUS`；沒有顏色且無 chip → 400 `FEATURE_REQUIRED`；`查找`／地點／時間被忽略並列在 `parse.ignored`；response 不含句子原文；LLM 開關 `off` 時固定 `RULES`，開啟但 ApiGuard 未核准時退回 `RULES`；CI 用 fake client，不呼叫真實 API | `test_track_sentence.py` |
| F-12 | 改選：`start {reselect:true}` 保留舊 tracker 與尾跡、`target.mode = NEEDS_PICK`、`tracking.state` 仍 `TRACKING`、1 人也不 auto、advisor 暫停；pick 後新目標生效；非 `TRACKING` 或顏色不同 → 409 `TRACK_MODE_CONFLICT`；一般 start（換色）清舊目標 | `test_track_endpoints.py` |
| F-13 | session：reset 換 token 並原子清狀態；舊 session 的 `start`／`pick`／`stop` → 409 `SESSION_MISMATCH`；`IDLE`／未 start 時 `pick` → 409 `TRACK_MODE_CONFLICT`；無偵測時 `start` → 200 `ACQUIRING`、`tick:null`；`stop` 冪等；`cand_id` 不因 reset 重新撞號 | `test_track_endpoints.py` |

### 8.2 操作（A）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| A-1 | WASD、Shift 速度 1.2／2.5 m/s；牆面半徑 0.25 m、沿牆滑動（沿用現有行為不退步） | `crowd.test.mjs`（`stepPlayer` 回歸） |
| A-2 | 移除句子與 `red top／blue top` 下拉；A 沒有任何目標設定欄位 | `ab_menu.test.mjs`（檢查 `operator.mjs` 產生的 DOM 字串） |
| A-3 | 選角寫入 `session.actor_id` 後，沒有可改它的程式路徑（模組沒有 export setter；`window.__op` 不提供） | `ab_menu.test.mjs` |
| A-4 | 開始後按任何鍵（含 `Esc`）都不會改場景或角色；重新載入頁面才會出現選單 | `ab_menu.test.mjs` |
| A-5 | 滑鼠轉視角（§1.3）：`applyMouseDelta` 方向與靈敏度（dx = 100 → 15°）、pitch 夾限、單次上限；`moveVector` 在 yaw = 0／90／180／270° 的方向、斜向不超速、yaw = 0 時與 v1 `stepPlayer` 逐步相同；視角資料不出現在 `frame-batch` | `mouse_view.test.mjs` |

### 8.3 碰撞（C）

見 §3.6：C-1～C-8（`crowd.test.mjs`）。

### 8.4 GT 隔離（G）

| 編號 | 條件 | 測試 |
| --- | --- | --- |
| G-1 | `buildSystemMessage` 的輸入型別沒有 A 的任何欄位；對塞進 `actor_id`、`player_xy`、`gt` 等 §5.2 禁止鍵的結果，輸出沒有這些鍵 | `protocol.test.mjs`（擴充） |
| G-2 | `validateSystemMessage` 對含任一禁止鍵的訊息回報違規（逐一參數化）；**禁止鍵放在 `events[].detail`、`timing_ms`、`target` 等 nested 位置也要違規**；非有限座標不產生候選 | `protocol.test.mjs` |
| G-3 | `system.mjs`、`hud.mjs` 的原始碼不 import `world.mjs`、`sim.mjs`、`crowd.mjs`、`operator.mjs`，也不含 `groundTruthVisible`、`actor_id`（靜態字串檢查） | `protocol.test.mjs`（新增 `b_isolation` 案例） |
| G-4 | `/track/*` 的 request／query 只收 §5.4 列的鍵，多餘的鍵 400 `FIELD_NOT_ALLOWED`（`fields` 只含鍵名、不含值）；error schema 為 `{error, detail?, fields?}` | `test_track_endpoints.py` |
| G-5 | `/track/*` 與 `/infer` 的 response 只含白名單鍵（含 `parse`、`target`） | `test_track_endpoints.py` |
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
- 瀏覽器驗收（手動，截圖進 PR）：A 選場景與角色→開始→滑鼠轉視角、WASD 隨視角→走到腳本人物前被擋住（站著不動，被擋的人持續等待）；B 選紅衣有兩個候選→點選→追蹤→改選→停止；B 輸入句子（RULES）。pointer lock 的真實手感 headless 驗不到，列入 Not verified。

## 9. 檔案範圍與先後順序

### 9.1 會改的檔

| 檔 | 內容 | 與進行中 PR 重疊 |
| --- | --- | --- |
| `frontend/live-mode/src/crowd.mjs`（新） | 腳本時鐘、成對碰撞與暫停、離線驗證（純模組） | 無 |
| `frontend/live-mode/src/view.mjs`（新） | 滑鼠轉視角與視角相對移動（純模組） | 無 |
| `frontend/live-mode/src/sim.mjs` | `stepPlayer` 加人物阻擋與視角相對移動；`scriptedPose` 不變 | 無 |
| `frontend/live-mode/src/operator.mjs` | 場景與角色選單、開始閘門、滑鼠事件、去掉句子與下拉、接 `crowd.mjs`、A 私有 log 擴充 | 無（#563 沒改） |
| `frontend/live-mode/src/system.mjs` | 選特徵列、句子輸入、候選疊圖、`reduceB`、輪詢 `/track/state` | **#563**（已合併）；**#559** 若改動需協調 |
| `frontend/live-mode/src/hud.mjs` | `IDLE`／`NEEDS_PICK` 兩種狀態 | #563 已合併；無進行中 |
| `frontend/live-mode/src/protocol.mjs` | 白名單加 `target`、`state` 新值、nested 檢查 | **#559**（排程欄位 `schedule` 已在 main；若 #559 再加欄位會衝突） |
| `frontend/live-mode/test/crowd.test.mjs`、`ab_menu.test.mjs`、`mouse_view.test.mjs`、`ab_flow.test.mjs`（新）、`protocol.test.mjs`、`hud.test.mjs` | 測試 | `protocol.test.mjs` 可能與 #559 重疊 |
| `frontend/live-mode/measure/smoke.mjs` | R4：預設輸出不寫 `/private/tmp`（#486 留言 6953090327 的 R4） | 無 |
| `src/amidst/live_mode/server.py` | `/track/*`、`/reset` 回 `session_id`、`IDLE` 模式、候選表 | **#559**（偵測與排程，重疊最多）；#563 已合併 |
| `src/amidst/live_mode/tracker.py` | `target_color`、blue 的 `est_xy`、`IDLE`／`ACQUIRING`／`NEEDS_PICK`、起始鎖定改由要求觸發、`pick` 起始 | #559 可能碰（待確認） |
| `src/amidst/live_mode/candidates.py`（新） | 分群、候選表、epoch 與 7 個 generation | 無 |
| `src/amidst/live_mode/track_sentence.py`（新） | 即時詞彙＋呼叫 `nl_query_parse.parse_nl_query`＋結果對應（§4.2） | 無 |
| `tests/live_mode/test_track_endpoints.py`、`test_track_sentence.py`、`test_tracker_color.py`（新） | 後台測試 | 無 |
| `scripts/live_ab_score.py`、`tests/evaluation/test_live_ab_score.py`（新） | 事後評分 | 無 |
| `docs/operations/LIVE_MODE_HANDOFF_*.md` 或新文件 | 啟動與操作說明（AGENTS.md：handoff 文件進 GitHub） | — |

不改：`frontend/workbench*`、`frontend/workbench-v2/`（8785 的程式不動；B 只**參考**它的流程）、`src/amidst/q1q5/nl_query_parse.py`（只呼叫，不改）、scenario 檔、LOCAL 資產、`ApiGuard` 與 advisor 邏輯。

### 9.2 先後順序

1. **可立即做（不碰 #559 的檔）**：(a) crowd＋sim 不碰撞、(b) A 的場景／角色選單＋滑鼠轉視角、(c) 離線評分、(f) R4。建議順序 a → b（b 把 a 的 `crowd.mjs` 接進 `operator.mjs`），c、f 與其他獨立。
2. **等 #559 合併再開工**：(d) 後台 `/track/*`＋session、(e) B 選目標流程＋Q3 接線＋HUD＋協定。理由：`server.py` 的 `infer()`、排程與偵測都在 #559 修；`protocol.mjs` 也重疊；`IDLE` 的排程行為要以 #559 為準。#563 已合併，不必等。
3. 最後 (g)：整合、瀏覽器驗收、handoff 文件。
4. 單一 feature 一個 PR（D216、D248）：全部交到 `codex/feat-live-ab` 同一個 Draft PR，分階段 commit；Claude 在全部完成後審查。

### 9.3 板上的子 issue（#566 為 epic）

| 子 issue | 範圍 | 驗收 | 狀態 |
| --- | --- | --- | --- |
| #568 CX-L5a | crowd＋sim 不碰撞（腳本時鐘、成對檢查、一直等、連鎖記錄、`validateScripts`） | F-3（純模組部分）、A-1、C-1～C-8 | `ready` |
| #569 CX-L5b | A 場景＋角色選單、開始閘門、滑鼠轉視角、去句子與下拉、A 私有 log | F-1、F-2、F-3（整合）、A-1～A-5、G-6 | `ready` |
| #570 CX-L5c | `scripts/live_ab_score.py` 離線評分 | §7、`test_live_ab_score.py` | `ready` |
| #571 CX-L5d | 後台 `/track/*`、session、候選表、`IDLE`／`ACQUIRING`／`NEEDS_PICK`、blue、句子接 Q3 | F-4（後台）、F-5～F-8、F-11～F-13、G-4、G-5 | `blocked`（#559） |
| #572 CX-L5e | B 選目標流程、句子輸入、候選疊圖、HUD、`protocol.mjs` nested | F-4（前端）、F-9、F-10、G-1～G-3 | `blocked`（#559、#571） |
| #573 CX-L5f | R4：`smoke.mjs` 不寫 `/private/tmp` | R4 | `ready` |
| #574 CX-L5g | 整合、瀏覽器驗收、§8.5 回報、handoff 文件 | §8.5、§8.6 | `blocked`（#568～#573） |

## 10. 風險與未驗證

- **選角與外觀**：variant T/A/B/C 的實際衣色（紅／藍／橘）沒有在這份規格查證（`UNKNOWN`）；選單的色塊取材質 base color，B 的顏色 chip 只有後台判得出的 `red`／`blue`。若某個 variant 後台判為 `none`，B 就**追不到它**——是否保證至少兩個 variant 判為 red 已決定：不改資產（§11-7），多個符合者的情境依現有 scenario 的衣色自然出現與否；測試用合成偵測序列覆蓋。
- **B 只能看到後台回的 `est_xy`**：分群門檻 1.5 m 沿用 tracker；兩人貼近（< 1.5 m）時會被分成同一個候選。腳本最近 0.68 m，因此貼近時 B 看到的是一個候選（這是真實的辨識限制，不是 bug；評分時會記成跟錯或 MISPICK）。
- **原場景時間線不保留**（§2.2）。
- **一直等的後果（D279）**：玩家站在路上不動，被擋的腳本人物會一直站著；連鎖時另一個腳本人物追上他會記 `forced_overlap(cause:'player_phase_shift', chain:true)`；玩家離開後因相位差造成的互擋也歸 `player_phase_shift`（v2.1）。這讓展示畫面可能出現多個人站著不動，已被使用者接受；報表會列出被擋總秒數與連鎖次數。
- **v2 與 Codex 審閱的差異（§10-1）**：(1) `/track/start` 無 infer 時定案 200 `ACQUIRING`（Codex 建議的選項之一；409 容易讓 B 把正常等待當錯誤）；(2) C-5 改為排除連鎖（Codex 未提，D279 後才有）；(3) nested 白名單原則由規格定、現有 `detail`／`timing_ms` 形狀由 Codex 列舉；(4) 規格不接受「取消改選」端點（限制見 §4.4），保持五端點。
- **pointer lock 手感未驗證**：滑鼠靈敏度 0.15°／px、pitch 範圍都是預設值，headless 測試只能驗純函式與拖曳（§1.3）。
- **Q3 解析器接線有兩處 `UNKNOWN`**：即時詞彙的別名表來源；ApiGuard 在 live server 的接線（§4.2）。Codex 在 #571 開工時確認並在 issue 回報；不一致時提出，不自行擴大範圍。
- 沒有實測：本文的碰撞半徑、等待上限、`stale_ticks` 都是預設值，要靠 §8 的測試與瀏覽器驗收確認。
- #559 若改了 `infer()` 回傳形狀，§5.5 要跟著調整；Codex 開工前以當時 `main` 為準，不一致時在 issue 提出。

## 11. 使用者決定（D279，2026-11-18）

使用者確認：A／B 指兩個畫面（A＝操作端、B＝系統端）；先選場景 A4-1／B4-1，再從 T／A／B／C 選一個角色操控，其餘照劇本走。七點決定如下（Codex 的契約審閱當時以為全照預設，3、4、5 點已改，已通知）：

| # | 問題 | 決定 | 落在 |
| --- | --- | --- | --- |
| 1 | 角色名稱 | **照預設**：「角色 T／A／B／C」附衣色色塊 | §1.1 |
| 2 | 腳本人物數量 | **照預設**：固定 3 個 | §1.4 |
| 3 | 玩家擋住腳本人物 | **改為一直等**：`wait_max_player_s` 無上限；玩家不動時被擋的人持續等、不記 player 的 `forced_overlap`，其他人物與模擬照常前進、沒有死結；腳本人物互擋 3 s 規則不變 | §3.1、§3.4、C-6 |
| 4 | 滑鼠 | **改為加滑鼠轉視角**（pointer lock 或拖曳） | §1.3、A-5 |
| 5 | B 的句子 | **改為接 Q3 解析器** `nl_query_parse.py`（不花錢的 RULES 預設）；LLM 只走 #563 已合併的開關（預設關），付費呼叫另外核准，不用 WP5 的 USD 46 | §4.2、§5.4、F-11 |
| 6 | 跟對率目標 | **照預設**：不訂，只出報表 | §7.1 |
| 7 | 兩個 variant 的衣色 | **照預設**：不改資產，使用現有 scenario | §10 |

## 12. 實際產出 / Actual output

見 PR 描述（本文件為規格，無程式碼、無實測數字；§2.1 的最近距離表是 `docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json` 的 waypoints 以 0.1 s 線性內插取樣算出，只讀，未渲染）。v2 的 Q3 解析器介面來自 `main` 上 `src/amidst/q1q5/nl_query_parse.py` 與 `docs/contracts/NL_QUERY_PARSE_V1.md` 的讀取，未執行。
