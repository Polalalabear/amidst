# Claude 對「受控新場景與 2D → 3D 重現提案」的回覆

日期：2026-10-18（Asia/Taipei）

狀態：**回覆草稿，供使用者帶回給 Codex 檢視可行性與契約。不是已核准的實作計畫，也沒有實作、渲染或讀取 GT。**

- 回覆對象：Codex 提案 `CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md`。只在 Codex 的資產 repo 本機：LOCAL `/Users/polalabear/Developer/amidst/docs/agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md`，SHA-256 `80013790cda63af6cfd14c395989a2e137a7b50b3d7675bda7a702025744b88f`。本 repo 沒有複製這份檔案，要不要納入由 Codex 決定。以下「提案 §N」都指這份檔案。
- 使用者的決定（2026-10-18）：**這份提案就是新的 Demo，不再在舊 Office 人形 run 上反覆找問題。**使用者也說「先不要管日期」，所以本文不排日期，舊計畫的 10/24、10/29、11/01 只當歷史背景。
- 同時交付的 A 包文件：
  - 契約草案 [OFFICE_CONTROLLED_SCENE_V1](../contracts/OFFICE_CONTROLLED_SCENE_V1.md)
  - 操作草圖 [CONTROLLED_SCENE_UX_SKETCH_20261018](CONTROLLED_SCENE_UX_SKETCH_20261018.md)
- 規則依 [DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)、[AGENTS.md](../../AGENTS.md)、[現行計畫 §6](OFFICE_DEMO_PLAN_20261101.md#6-分工2026-10-16-起取代舊claude-只做前端)。本文不放寬 GT 隔離。

閱讀方式：每節先列「判定」，再把**使用者已指定的需求**（照提案 §2 與使用者 10/18 的話，不改寫內容）和 **Claude 的新增建議**分開。新增建議都需要使用者確認，Codex 檢視可行性。

## 0. 結論摘要

1. 提案方向同意。最大的修改有四項：
   - 事件 B 拆成 **B1（兩人錯開、不交會）** 和 **B2（交會或分離）**。先驗收 B1，B2 才處理多解與未關聯。
   - 3D 人物第一版以**接地區間**為主體，不以人形為主體。RQ1 的實測結果是：REAR 鏡頭的腳點帶 0/6 涵蓋真值（Draft [#61](https://github.com/Polalalabear/amidst/pull/61)），所以畫面必須能表達區間。
   - 新場景的 walkable 標記是**唯一**允許使用的靜態地圖來源。C7 和 K7 都改當驗證器，不再各自產生一份地圖。
   - 先定解析度、格式和存放位置，再談渲染。實測既有 Office 960×540 PNG 平均約 0.41 MB／張，兩個事件合計約 0.5 GB（見 §4 與 Q2）。
2. 兩個事件共用**一個場景、一組 4 台鏡頭**（見 Q2）。事件 A 不設盲區；事件 B1 在轉角刻意設計一段盲區，沿用 K1。
3. 查找模式第一版用「**地面多邊形 + 時間範圍 + 查詢模板（經過／進出）**」，不用 Agent，也不用外部模型。
4. 舊工作不刪任何分支或 PR。可重用的模組都列在 Q7，處置清單在 Q8。舊的 CP2／CP3 建議暫停，改設新的檢查點，由使用者決定。

## 1. 對提案各節的回應

### §1 目的與改變方向的原因：同意

- **使用者已指定：**另建資訊完整、可控制的場景；從最終展示與操作需求倒推資料規格；這份提案就是新的 Demo。
- **Claude 新增建議：**
  - 「初始標記可能不完整」維持為待驗證假說。舊 `.blend` 不改，也不寫成「原標記有錯」。
  - 舊 Office run 的結果（C4a、C4b、C5、K1／K5、K7、RQ1）照原 run 綁定保存，不搬到新場景比較。新場景另有自己的 run、pin 與 hash。

### §2 使用者已明確指定的需求：同意（全部照錄）

- **使用者已指定：**§2 表格全部照錄，不改寫：取消綠球、物理曲線在 3D 以虛線表示、1／2／4／8 格同步、查找模式、搜尋結果保留所有候選、3D 由 2D 影像重現（不讀 GT）、像影片一樣播放與點選、事件 A 單人直線、事件 B 多人跨轉角、先驗場景再擴充預測。
- **Claude 新增建議：**
  - **現行工作台也先移除綠球。**新 Demo 的前端完成之前，不讓舊工作台繼續示範綠球。範圍是 `frontend/workbench/scene.mjs` 的時間游標球與跨鏡頭游標（彩排分支 `claude/rehearsal-20261018` @ `5a2c613` 的 `cursor`，約 212 行）。原始診斷資料與 [綠球診斷](../engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md) 保留。這是一個獨立的小任務，A 包核准後再做，不在本次文件中修改。
  - **事件 B 拆成 B1 和 B2：**
    - B1：兩人錯開進入，路線與時間不交會，任一鏡頭的任一影格最多只有 1 人。B1 先驗收。
    - B2：兩人交會或分離，才處理多解、未關聯基線與 `AMBIGUOUS_MERGE`。
    - D8 原本是「`AMBIGUOUS_MERGE` 在 11/01 前一律不可用」。因為已經不看日期，建議改成「**B2 驗收前**不可用」。這需要使用者重新確認 D8。
  - 是否固定兩人：B1、B2 都建議固定 2 人。人數多寡另作 UI fixture 測試，不靠渲染（見 Q2）。

### §3 預期使用體驗：修改（流程同意，補兩項約束）

- **使用者已指定：**§3 的 1–6 步、候選鏡頭集合與當頁格數分開、「最有可能」只代表建議檢視順序。
- **Claude 新增建議：**
  - 第 5 步「3D 顯示個體位置、方向或區間」改成**以區間為主**。RQ1 Draft [#61](https://github.com/Polalalabear/amidst/pull/61) 用 C4a v1.1 在舊人形 run 量到：0.25 m 容差下涵蓋 23/33，其中 FRONT 腳點帶 19/23、**REAR 腳點帶 0/6**、頭頂射線 4/4；0 容差 0/33；腳點帶長度 0.732–1.185 m。所以估計器實際交付的是區間，不是點。若 3D 第一版只能畫點或人形，就會把不確定性藏起來。畫法見 Q3。
  - 第 6 步「多解時保留多個候選」只在 B2 才開始驗收。B1 只要求不把兩個人連成同一條曲線。
  - 候選不足格數時不複製鏡頭補位；候選超過 8 台時用分頁保留，不丟棄。這兩點同意提案，畫法見 [UX 草圖 §3](CONTROLLED_SCENE_UX_SKETCH_20261018.md#3-格數切換1248)。

### §4 新 `.blend` 的規劃：修改（補磁碟、解析度、格式、存放位置）

- **使用者已指定：**全新的獨立 `.blend`，參考目前建築風格，建立物件時就加完整標記；兩事件共用場景與資料規格、各自獨立 run；原資產不覆寫。
- **Claude 新增建議：**
  - **磁碟估算（必須在渲染前決定）。**本機剩約 11 GiB（`df -h` 2026-10-18 實測）。只看既有 PNG 的檔案大小（沒有開啟影像內容）：Office 人形 run 和接地對照 run 都是 960×540，平均每張 0.41 MB（各 100 張）。

    | 選項 | 每張大小 | 事件 A（4 台 × 10 s × 10 Hz = 400 張） | 事件 B1（4 台 × 20 s × 10 Hz = 800 張） | 合計 |
    | --- | --- | --- | --- | --- |
    | 960×540 PNG（沿用現況） | 0.41 MB（實測平均） | ≈ 0.17 GB | ≈ 0.33 GB | **≈ 0.5 GB** |
    | 1280×720 PNG | ≈ 0.73 MB（依像素數線性外推，**未實測**） | ≈ 0.29 GB | ≈ 0.58 GB | ≈ 0.9 GB |

    協調者先前的粗估是「4 鏡頭、20 s、10 Hz、720p PNG 約 1–1.6 GB」，假設每張 1.25–2 MB。以實測值看，這個估計大約多估一倍。不過新場景的材質與內容不同，實際大小仍要先試算一張才算數。
  - **解析度建議沿用 960×540。**D21 的可偵測門檻（≥112 px）、C4a 的像素敏感度、C5 的偵測器參數，都是在這個解析度下設定的。換解析度就要重新驗證這些門檻。
  - **格式用 PNG**（無損、保留像素 chunk，符合 DEVELOPMENT_RULES 對公開 PNG 的規定）。不輸出逐影格深度 EXR：深度只屬於評估端，而且單張就要好幾 MB。評估端需要的人物遮罩用 8-bit PNG，放在 GT 目錄。
  - **存放位置：**放在資產 repo 的 `data/pilot/<新 run>/`，和既有 `office_person_20261016_v1` 同一層。不進 Git，也不放進共用 checkout。RGB、安全 bundle、GT 分成三個目錄（見 [契約 §7](../contracts/OFFICE_CONTROLLED_SCENE_V1.md#7-gt-隔離邊界)）。實際路徑由 Codex 確認；未確認前記為 `UNKNOWN`。
  - 樓梯：同意預留分類，但首輪事件不使用，標為「未驗收」。

### §5 先驗證輸入場景，再做影像重現與預測：同意

- **使用者已指定：**先定時間、區域、鏡頭需求，再配置與產製；「場景符合條件」與「影像估計正確」分開驗收。
- **Claude 新增建議：**驗收表分成兩欄，見 [契約 §8](../contracts/OFFICE_CONTROLLED_SCENE_V1.md#8-驗收表)。B1 的盲區是**設計出來的**，契約要寫明盲區的空間範圍與預期時間窗；渲染後要在模擬端核對「這段時間沒有任何鏡頭看得到人物」。未預期的缺影格一律記為 `MISSING`，不算進設計盲區。

### §6 正式資料流與 GT 邊界：同意，補一項來源規則

- **使用者已指定：**3D 主目標由 2D 影像重現；GT 回放至多是評估與除錯參考，正式播放不能退回 GT。
- **Claude 新增建議：**
  - **新場景的 walkable 標記就是允許使用的靜態幾何。**推論端只讀這一份地圖（含障礙物、門、連通關係）。C7 不再另外產生一份推導地圖，改當驗證器：用來源 mesh 核對標記有沒有漏標或不一致。K7 也同理：核對標記地圖與 C7 結果、離線路線。這樣才不會出現兩個地圖來源。D3「地圖由來源網格推導，標註只作交叉核對」是針對舊 Office 的規則；在新場景要反過來，這需要使用者重新確認。
  - 事件情境規格中的「每段應由哪些鏡頭覆蓋」與「設計好的盲區」只能用於場景驗收，**不能給檢索或排序讀**。否則等於先把答案交給系統（見 [契約 §7](../contracts/OFFICE_CONTROLLED_SCENE_V1.md#7-gt-隔離邊界)）。

### §7 建議的交付與驗收邊界：同意，補順序

- **使用者已指定：**工作包 A–E 是從成果倒推的，不是逐點修補的承諾。
- **Claude 新增建議：**
  - **A 包經使用者確認前不渲染。**B 包開始時，先渲染每台鏡頭各 1 張試算大小與外觀，再渲染整段。
  - 建議順序：A（契約與草圖）→ B（場景與 RGB，只做 A、B1）→ C（查找與重現）→ D（曲線與預測）→ B2 → E（標記範本）。E 的 validator 可在 B 期間先做初版，因為 K7 已經是驗證器。

### §8 分工：同意（細節見 Q7）

- 同意提案 §8 的分工表。檔案集合的單一主責見 Q7。

### §9 參考與未驗證項目：同意

- 提案提到的視覺參考影片（LOCAL `/Users/polalabear/Desktop/Screen Recording 2026-10-07 at 13.40.38.mov`），本回覆也**沒有**檢視。外觀細節要由使用者對照後再定。

## 2. 逐題回答（提案 §8 的 Q1–Q8）

### Q1. 各節同意／修改

見第 1 節。

### Q2. 兩個事件的最小場景、鏡頭、人數與查詢

**場景（建議值，等 Codex 做可行性檢查）：**L 形走廊加兩個房間。

```text
 y(m)
  12 ┤                                    ┌─────┐  ▼ CAM_N1（北端朝南）
     │                                    │     │    地面視野 y≈3.5–11
     │                         北走廊 CORR_N│     ├─門─┬───────────┐
     │                                    │     │    │ R102 對照房間│
     │                                    │     │    │ CAM_R102_CTRL│
     │                                    │     │    └───────────┘
 3.5 ┤                                    │░░░░░│ ← 轉角盲區（設計，無鏡頭）
 2.4 ┼────────────────────────────────────┘░░░░░│
     │ ▶CAM_W1   [AREA_R101_FRONT]      ◀CAM_W2 ░│  西走廊 CORR_W
   0 ┼──────────┬───門───┬─────────────────────┘
     │          │  R101  │ 目標房間（無鏡頭）
  -5 ┤          └────────┘
     └──────────┴───┬────┴────────────────┴─────┴──→ x(m)
     0          5   8    11              15  17.4
     CAM_W1 地面視野 x≈1–9；CAM_W2 地面視野 x≈6–14.5；兩者在目標區域重疊
```

（示意，非比例圖。坐標與尺寸在 [契約 §5](../contracts/OFFICE_CONTROLLED_SCENE_V1.md#5-事件情境規格)。）

**鏡頭（兩事件共用同一組，4 台）：**

| 鏡頭 | 位置與視野（建議） | 事件 A 的角色 | 事件 B1 的角色 |
| --- | --- | --- | --- |
| `CAM_W1` | 西走廊西端朝東，地面視野 x≈1–9 m | 目標區域（重疊之一） | 西走廊前段 |
| `CAM_W2` | 西走廊東端朝西，地面視野 x≈6–14.5 m | 目標區域（重疊之二） | 西走廊後段 |
| `CAM_N1` | 北走廊北端朝南，地面視野 y≈3.5–11 m | 無關（事件 A 的人不經過） | 北走廊 |
| `CAM_R102_CTRL` | 對照房間 R102 內，只看房內 | 無關、對照 | 無關、對照 |

- 協調者的初步意見是：事件 A 用 3 台（2 台重疊並涵蓋目標區域、1 台無關），事件 B1 用 4 台（兩條走廊各 1、轉角 1、無關 1）。**Claude 修改一處：**「轉角有鏡頭」和「轉角刻意設計盲區」互相矛盾。建議取消轉角鏡頭，轉角就是設計盲區，B1 的西走廊改用 `CAM_W1`、`CAM_W2` 兩台。這樣兩個事件可以共用同一組鏡頭、同一份校正，只要一個 `.blend`。事件 A 的人只走西走廊，所以 `CAM_N1` 和 `CAM_R102_CTRL` 自然成為查找時的無關鏡頭。另一個選項是保留轉角鏡頭，把盲區移到北走廊中段。這由使用者決定（見第 3 節第 2 項）。
- 事件 A 渲染 4 台而不是 3 台：多 100 張（約 0.04 GB），換來兩個事件同一組鏡頭，查找模式在事件 A 有 2 台要排除。

**人物與時間（建議值）：**

| 事件 | 人數 | 路線 | 時長 | 盲區 |
| --- | --- | --- | --- | --- |
| A | 1 | 沿西走廊由西往東，直線經過 `AREA_R101_FRONT`，不進房間 | 約 10 s（13 m、約 1.3 m/s） | 無；全程至少 1 台看得到 |
| B1 | 2（固定） | P1：西走廊由西往東，過轉角進北走廊。P2：比 P1 晚約 8 s 進入西走廊，走到 R101 門口進房 | 約 20 s | 只有 P1 經過轉角時，約 3 s |

- B1 的時間錯開條件：P1 離開 `CAM_W2` 視野之後，P2 才進入 `CAM_W2` 視野（預估間隔約 1.5 s）。確切的間隔門檻「待約定」。
- B1 有一個可以拿來驗證檢索的情況：P2 進入目標區域時（約 12.2 s），P1 還在轉角盲區裡（約 10.4–13.5 s）。

**查詢示例：**

| 事件 | 查詢 | 應該出現的候選（場景驗收用，不給系統讀） |
| --- | --- | --- |
| A | 模板「經過」；區域 `AREA_R101_FRONT`；時間 0–10 s | `CAM_W1`、`CAM_W2` 涵蓋目標區域；`CAM_N1`、`CAM_R102_CTRL` 不相交，但仍列在候選清單底部標「不相交」 |
| B1 | 模板「進出」；區域 `AREA_R101_FRONT`；時間 8–20 s | `CAM_W1`、`CAM_W2` 涵蓋目標區域；`CAM_N1` 是否算「進出通路」取決於通路距離設定（待約定）；`CAM_R102_CTRL` 不相交 |

**八台以上是否要真的建：不建。**候選集合大於格數時的分頁、排序與保留，用 UI fixture（宣告為 `FIXTURE` 的假鏡頭清單，例如 12 台）測。場景只建 4 台。理由：鏡頭數量增加不會讓估計或檢索更可信，只會增加渲染量與磁碟；UI 的完整性問題用 fixture 就能測完整。

### Q3. 3D 人物重現第一版

**從 RGB 估出的（推論端）：**

| 量 | 來源 | 狀態 |
| --- | --- | --- |
| 接地估計：點或區間 | C4a v1.1（`FOOT_POINT`、`FOOT_RAY_PIXEL_BAND`、`HEAD_RAY_HEIGHT_PRIOR`），格式沿用 [區間觀測 v1](../contracts/OFFICE_INTERVAL_OBSERVATION_V1.md) 的 `ground_estimate` | `PROJECTED_OBSERVATION` |
| bbox 高度（px） | 影像偵測 | 觀測 |
| 移動方向 | 同一鏡頭前後影格的接地估計差分 | **推論**（`INFERRED_INTERPOLATION`），兩端任一是 `UNKNOWN` 時就不給方向 |

**只是顯示設定的（不是量測）：**

- 人形尺寸：D5 的 1.70 m 高、半徑 0.25 m。
- 顏色、材質、姿態、走路動畫。示意人形一律不擺姿態，不跟著影像做動作。

**畫法：**

- 區間用**實線段**畫在地面上（觀測色），兩端加短橫線，表示「人在這段上的某處」。
- 只有區間長度不超過顯示門檻 `HUMANOID_DISPLAY_MAX_INTERVAL_M` 時，才沿整段畫**半透明人形範圍**（把人形沿區間掃過的外框）。門檻值「待約定」，要在凍結前定，不依結果調。
- **不在中點放實心人形**，也不放任何點狀替身。這符合區間觀測 v1 §1「不得把 SEGMENT 收成中點」。
- 點估計（POINT）畫一個地面短十字加半透明人形。
- 不使用 2D 輪廓或貼片：要把影像貼到 3D 需要深度，而深度是評估端資料。也不用姿態模型：第一版沒有姿態估計器，畫姿態等於假裝量到了姿態。

### Q4. 虛線曲線、預測、時間表示與點選

**線型（顏色沿用 K4 `blind-hypothesis.mjs` 的圖例，[#35](https://github.com/Polalalabear/amidst/pull/35)）：**

| 元素 | 證據狀態 | 線型 | 顏色 |
| --- | --- | --- | --- |
| 單筆觀測（點或區間） | `PROJECTED_OBSERVATION` | 實線 | 觀測青綠 `#76d9cf` |
| 觀測之間的連接 | `INFERRED_INTERPOLATION` | 短虛線 | 推論琥珀 `#ffc266` |
| 盲區假設（兩端都有觀測） | `INFERRED_HYPOTHESIS` | 長虛線＋半透明範圍帶 | 假設玫紅 `#ff6fa8` |
| 預測（只有起點、往未來；D 包） | `INFERRED_HYPOTHESIS`，`kind: PREDICTION` | 長虛線＋往前變寬的範圍帶，尾端開口 | 假設玫紅，透明度較低 |
| 缺失 | `MISSING` | **3D 不畫連線**，只在時間軸畫灰色斜線區 | 灰 `#8292a9` |
| 未知 | `UNKNOWN` | 3D 不畫；在面板列出原因 | 灰，加「?」 |

- 觀測是區間時，「連接」不能從中點連到中點。建議用一條**緞帶**：兩條短虛線分別連接前後兩個區間的對應端點，中間淡色填滿。這表示「連接範圍」，不是一條路線。
- 物理曲線和預測的差別：曲線前後都有觀測支持；預測只有一端，沒有終點，尾端開口、範圍帶持續變寬。

**目前時間（不用球）：**

- 曲線上把 [t−Δ, t] 這一段加亮加粗（Δ 預設 1 s，可設定）。
- 再加一個**時間刻度**：在加亮段的末端畫一條垂直於曲線的短線，旁邊標 `t = 12.4 s`。刻度只標時間，不代表人物位置。
- 時間落在盲區時，只把那一刻的範圍帶切片加亮（K4 已經會跟時間軸走），不畫任何位置。
- 時間落在 `MISSING` 時，3D 不加亮任何東西，時間軸標「此時無觀測」。

**點選：**點曲線或區間 → 找出支持它、且時間最接近點擊位置的那筆觀測 → 2D 跳到該鏡頭、該影格並框出 bbox，3D 同步跳到那一刻。點假設或預測 → 列出兩端觀測與套用的負證據影格。點 `MISSING` → 說明「此段沒有支持證據」，不跳轉。流程見 [UX 草圖 §6](CONTROLLED_SCENE_UX_SKETCH_20261018.md#6-點擊回溯)。

### Q5. 查找模式的有限查詢

第一版：**地面多邊形 + 時間範圍 + 查詢模板**，不用 Agent，也不用外部模型。

1. **輸入：**
   - 目標區域：在 3D 地面上畫多邊形，或從場景標記中選一個 `AREA_*`；
   - 時間範圍 `[t0, t1]`，有上限；
   - 模板：`PASS_THROUGH`（經過）或 `ENTER_EXIT`（進出）。
2. **找通路：**從地圖的連通關係取得與目標區域相鄰的門與走廊格（`ENTER_EXIT` 時才需要）。通路沿可走區域往外延伸一個固定距離，距離值「待約定」。只用靜態地圖，不用人物資料。
3. **候選鏡頭：**沿用 C5 的靜態可見範圍索引（`SOURCE_MESH_RAYCAST`）。足跡與目標區域相交的是第一級；只與通路相交的是第二級；都不相交的是第三級，仍列出來，標「不相交」。
4. **檢索影格：**對第一、二級鏡頭呼叫 C5 `TIME_RANGE`，取得影格與既有偵測結果。
5. **排序依據（全部可解釋、可重現）：**依序是相交等級 → 與目標區域的重疊面積 → 時間範圍內有偵測的影格數 → `camera_id`。每個候選都附排序理由。不讀 GT、事件腳本或設計的覆蓋表。
6. 結果超過格數時分頁；少於格數時留空格。

偵測數當排序鍵之一，只代表「這段影格裡有東西」，不代表是同一個人。要不要用它，列為 [契約 CS-Q4](../contracts/OFFICE_CONTROLLED_SCENE_V1.md#9-待決問題)。

### Q6. 必填標記、scene schema、consumer API 與驗收

見新契約 [OFFICE_CONTROLLED_SCENE_V1](../contracts/OFFICE_CONTROLLED_SCENE_V1.md)：
- §3 scene schema
- §5 事件情境
- §6 API payload 範例
- §7 GT 隔離
- §8 驗收表

### Q7. 可重用模組與需要集中重構的模組

**可重用（照原主責，不改檔案集合）：**

| 模組 | PR | 主責 | 在新 Demo 的用途 | 需要的調整 |
| --- | --- | --- | --- | --- |
| C5 可見範圍索引與檢索 | [#47](https://github.com/Polalalabear/amidst/pull/47)、[#53](https://github.com/Polalalabear/amidst/pull/53) | Codex | 候選鏡頭、`TIME_RANGE` 檢索、負證據 | 新場景要重建索引；`MAX_CAMERAS = 4` 的上限要依候選數重新檢視 |
| C4a 接地估計 | [#37](https://github.com/Polalalabear/amidst/pull/37)、[#46](https://github.com/Polalalabear/amidst/pull/46) | Codex | 3D 人物的點與區間 | 新的相機參數與地板高度；新場景建議地板 z = 0 |
| K1 盲區假設 | [#33](https://github.com/Polalalabear/amidst/pull/33)（[#48](https://github.com/Polalalabear/amidst/pull/48) 的 D21 去重） | Claude | B1 轉角盲區 | 新場景的設定條目；地圖改讀 walkable 標記 |
| K5 剪枝與檢索轉負證據 | [#36](https://github.com/Polalalabear/amidst/pull/36) | Claude | B1 負證據 | 無 |
| K8c 跨鏡頭候選篩選 | [#57](https://github.com/Polalalabear/amidst/pull/57) | Claude | B1 盲區後出現的人，評估「可達／排除／無法判定」 | 用真實 B1 資料，不再需要合成 |
| K4 範圍帶與圖例 | [#35](https://github.com/Polalalabear/amidst/pull/35) | Claude | 假設範圍帶、顏色 | 由 `curve-layer.mjs` 使用 |
| K3 場景預設、品質標示、區間顯示 | [#31](https://github.com/Polalalabear/amidst/pull/31)、[#42](https://github.com/Polalalabear/amidst/pull/42) | Claude | 場景選單；區間畫法搬到 `person-layer.mjs` | 讀 `target_reconstruction` 的 `ground_estimate` |
| K6 Demo 模式 | [#38](https://github.com/Polalalabear/amidst/pull/38) | Claude | 數字鍵跳步驟的框架 | Office 步驟組不再使用，改寫新步驟組 |
| A5 選取高亮 | 彩排分支 `5a2c613`（`observation-selection.mjs`） | Claude | 點擊回溯 | 改接 `evidence_lookup` |
| launcher、`rehearsal-check` | [#50](https://github.com/Polalalabear/amidst/pull/50)、[#64](https://github.com/Polalalabear/amidst/pull/64) | Codex | 新場景的 readiness 與收據 | 新的 preset 與 pin |
| K7 地圖驗證 | [#41](https://github.com/Polalalabear/amidst/pull/41) | Claude | **改當驗證器**：walkable 標記 vs 來源 mesh、路線 | 輸入改成新場景標記 |
| C7 來源地圖 | [#40](https://github.com/Polalalabear/amidst/pull/40) | Codex | **改當驗證器**：從 mesh 核對標記 | 不再輸出推論用地圖 |
| RQ1 評估工具 | [#61](https://github.com/Polalalabear/amidst/pull/61) | Claude | 新場景的接地涵蓋率（凍結後才讀 GT） | 輸入改成新 run |

**需要集中重構的前端（Claude 主責，一個檔案集合一個主責）：**

| 檔案 | 內容 |
| --- | --- |
| `frontend/workbench/player-grid.mjs`（新） | 1／2／4／8 格同步播放、空格、分頁、釘選 |
| `frontend/workbench/search-mode.mjs`（新） | 區域與時間輸入、模板、查找前後狀態、候選清單、返回 |
| `frontend/workbench/person-layer.mjs`（新） | 區間實線段、半透明人形範圍、POINT 十字 |
| `frontend/workbench/curve-layer.mjs`（新） | 實線、短虛線緞帶、長虛線＋範圍帶、時間加亮與刻度、點選 |
| `frontend/workbench/scene.mjs`（修改） | 移除綠球與游標球；把人物與曲線交給新圖層 |
| `frontend/workbench/app.mjs`、`index.html`、`style.css`（修改） | 接上新模組、模式切換 |
| `src/amidst/workbench/service.py` 的靜態檔白名單（**一行**） | 新增 `.mjs` 要加進白名單，否則回 403（K4 的教訓）。這一行屬於 Codex 的檔案，由 Claude 在 PR 中提出，Codex 審查 |

**後端（Codex 主責）：**候選鏡頭 API、同步影格 API、`evidence_lookup` API、新場景 bundle、preset、launcher 條目、C5 新索引、C4a 新 run。

**依賴：**以下模組都還沒合併進整合分支，不能當作已合併：K1（#33）、K5（#36）、K1 D21（#48）、C4a（#37、#46）、C5（#47、#53）、K3（#31、#42）、K4（#35）、K6（#38）、K7（#41）、C7（#40）、K8c（#57）、RQ1（#61）。整合分支 `claude/office-demo-visualization` 目前在 `dcb89f4`，只含 #10、#11、#12、#32 以前的內容。新工作要用到這些模組有兩種做法：一是使用者先核准「可重用模組」合併，二是新分支堆疊在這些 PR 上。這由使用者決定（見第 3 節第 6 項）。

### Q8. 計畫修訂、最小交付、標記範本與舊工作處置

#### 舊工作處置（不刪任何分支或 PR；不靠刪分支關 PR）

標記說明：**重用**＝模組進新 Demo；**暫停**＝保留，不再推進，日後可能用到；**不再需要**＝不推進，保留作紀錄。三種都保留分支。

**Claude：**

| PR | 內容 | 處置 |
| --- | --- | --- |
| [#31](https://github.com/Polalalabear/amidst/pull/31) | K3 場景預設、品質旗標 | 重用（場景選單、`contact_quality` 標示） |
| [#42](https://github.com/Polalalabear/amidst/pull/42) | K3 後半：接地區間顯示 | 重用（區間畫法移到 `person-layer.mjs`） |
| [#33](https://github.com/Polalalabear/amidst/pull/33) | K1 盲區假設 | 重用（B1 轉角盲區） |
| [#36](https://github.com/Polalalabear/amidst/pull/36) | K5 剪枝、檢索轉負證據 | 重用（B1 負證據） |
| [#48](https://github.com/Polalalabear/amidst/pull/48) | K1 禁止區（D15）＋以影格去重（D21） | 重用 D21 去重；D15 禁止區暫停（新場景目前沒有禁止區） |
| [#35](https://github.com/Polalalabear/amidst/pull/35) | K4 假設路徑束與範圍帶 | 重用（範圍帶與圖例顏色） |
| [#38](https://github.com/Polalalabear/amidst/pull/38) | K6 Demo 模式 | 重用框架；Office 步驟組與腳本不再需要 |
| [#41](https://github.com/Polalalabear/amidst/pull/41) | K7 地圖驗證 | 重用，改當驗證器 |
| [#45](https://github.com/Polalalabear/amidst/pull/45) | 契約 v1.1／v1.2 | 重用與場景無關的條文（R1、D17、D20、D21）；v1.2 的 K8 合成部分暫停；D15、D16、D18 屬於 Office 專用 |
| [#39](https://github.com/Polalalabear/amidst/pull/39) | Office 問答 | 不再需要（保留紀錄） |
| [#56](https://github.com/Polalalabear/amidst/pull/56) | K8 合成能力設計（D23） | 暫停 |
| [#57](https://github.com/Polalalabear/amidst/pull/57) | K8c 跨鏡頭候選篩選 | 重用（B1 真實資料） |
| [#58](https://github.com/Polalalabear/amidst/pull/58) | K8a 合成可見性方法 | 暫停 |
| [#60](https://github.com/Polalalabear/amidst/pull/60) | K8b 合成產生器與 fixture | 暫停 |
| [#61](https://github.com/Polalalabear/amidst/pull/61) | RQ1 接地區間評估 | 重用（評估工具）；舊 run 的結果保留為 3D 必須表達區間的依據 |
| Draft K8d（RQ2） | 合成真值評估 | 不再需要。遠端查無 K8d 分支（`git branch -r` 2026-10-18），**視為未推送**；本機內容 `UNKNOWN` |
| Draft K5 畫面牆 | 建議檢視畫面牆 | 不再需要，功能由 `player-grid.mjs` 與 `search-mode.mjs` 取代。遠端只有 Codex 的 fixture 分支（#62），沒有 Claude 的畫面牆分支，**視為未推送**；本機內容 `UNKNOWN` |

清單外：[#52](https://github.com/Polalalabear/amidst/pull/52)（10/17 協調者交接）保留為歷史，建議合併時加註「已被 2026-10-18 的轉向取代」。

**Codex：**

| PR／issue | 內容 | 處置 |
| --- | --- | --- |
| [#37](https://github.com/Polalalabear/amidst/pull/37) | C4a 混合接地估計 | 重用 |
| [#40](https://github.com/Polalalabear/amidst/pull/40) | C7 來源地圖 | 重用，改當驗證器 |
| [#43](https://github.com/Polalalabear/amidst/pull/43) | Office 人形 preset／fixture | 不再需要（preset 機制由 #51、#50 承接） |
| [#44](https://github.com/Polalalabear/amidst/pull/44) | C4b 盲區假設 API | 重用；要改掉「固定一對端點」與 `D18_INTERVAL_CONTAINS_OBSERVATION` 這兩個限制，才能處理 B1 的兩人（[#55](https://github.com/Polalalabear/amidst/issues/55) Codex 評估已指出） |
| [#46](https://github.com/Polalalabear/amidst/pull/46) | C4a v1.1 `FOOT_RAY_PIXEL_BAND` | 重用 |
| [#47](https://github.com/Polalalabear/amidst/pull/47) | C5 索引、檢索 API | 重用 |
| [#50](https://github.com/Polalalabear/amidst/pull/50) | 啟動器、人形 readiness、D19 三模式 | 重用啟動器；D19 的 Office 敘事不再需要 |
| [#51](https://github.com/Polalalabear/amidst/pull/51) | C3b 後續（preset 隔離） | 重用 |
| [#53](https://github.com/Polalalabear/amidst/pull/53) | C5 D21 嚴格可見性 | 重用 |
| [#54](https://github.com/Polalalabear/amidst/pull/54) | 彩排文件、CP2 合併準備 | 不再需要（保留紀錄） |
| [#62](https://github.com/Polalalabear/amidst/pull/62) | K5 畫面牆 HTTP fixture | 不再需要；fixture 格式可當新 API 的參考 |
| [#63](https://github.com/Polalalabear/amidst/pull/63) | K8a 預同步 | 暫停（隨 K8） |
| [#64](https://github.com/Polalalabear/amidst/pull/64) | `rehearsal-check` | 重用 |
| [#34](https://github.com/Polalalabear/amidst/pull/34) | C6 多鏡頭可行性 | 不再需要（Office 的 15 條路線不渲染） |
| [#55](https://github.com/Polalalabear/amidst/issues/55)（issue） | Office 第二人形 | 不再需要，由 B1／B2 取代。建議在 issue 留言說明後關閉，由使用者決定 |

**彩排分支** `claude/rehearsal-20261018` @ `5a2c613`：暫停，保留為 Office 證據。其中 A5 選取高亮（`observation-selection.mjs`）可重用到點擊回溯。

#### 檢查點怎麼改（建議，由使用者決定）

- CP2 [#26](https://github.com/Polalalabear/amidst/issues/26)、CP3 [#27](https://github.com/Polalalabear/amidst/issues/27)：建議**暫停**，不要關閉。在 issue 留言寫明「2026-10-18 轉向受控場景，範圍不再推進」。D1–D24 的決策紀錄繼續留在原 issue。
- CP4 [#28](https://github.com/Polalalabear/amidst/issues/28)：保留，範圍改成新 Demo 的發布審查。
- 新設檢查點（都標 `checkpoint`）：

| 檢查點 | 審什麼 | 通過前不能做 |
| --- | --- | --- |
| CS-A | A 包：本回覆、契約、UX 草圖；Codex 的可行性與契約確認 | 建 `.blend`、渲染 |
| CS-R | 可重用模組（Q7）合併進整合分支，或改用堆疊分支 | 新前端與 API 依賴這些模組 |
| CS-B | 場景驗收：事件 A、B1 的 RGB 與標記符合「場景符合條件」欄 | 凍結預測、評估 |
| CS-C | 查找與重現：「影像估計正確」欄、瀏覽器驗收 | D 包預測 |
| CS-D | 曲線與預測；B2 另開 | 對外 Demo |

#### 計畫文件要修訂的段落

| 文件 | 段落 | 修訂 |
| --- | --- | --- |
| [OFFICE_DEMO_PLAN_20261101](OFFICE_DEMO_PLAN_20261101.md) | 標頭、§2、§7 | 移除日期；標明 2026-10-18 轉向；舊進度改為歷史 |
| 同上 | §1 | 目標從「合成圓柱」改成人形與多人；身分仍 `UNCONFIRMED` |
| 同上 | §3 | 方法沿用，但第 1 步的輸出明確為區間；第 3 步加入候選鏡頭查詢 |
| 同上 | §4 | RQ 樣本改成新場景的兩事件；RQ3 改在 B1、B2 驗證 |
| 同上 | §5 | 選項 C「另建模擬場景」從「不建議」改為「已採用」，並說明理由 |
| 同上 | §6 | 加入 Q7 的檔案集合主責 |
| 同上 | §8、§9 | Codex 任務改成 B、C 包；Demo 流程改成 [UX 草圖](CONTROLLED_SCENE_UX_SKETCH_20261018.md) 的步驟；D22–D24 不再適用 |
| [OFFICE_DEMO_MVP](OFFICE_DEMO_MVP.md)、[OFFICE_DEMO_TASKS](OFFICE_DEMO_TASKS.md) | 全文 | 加註「已被受控場景取代」，任務表改指向新任務 |
| `CLAUDE.md` | 閱讀順序 | 第 1 項改成本回覆與新契約 |
| 契約 [區間觀測 v1](../contracts/OFFICE_INTERVAL_OBSERVATION_V1.md)、[盲區假設 v1](../contracts/OFFICE_BLIND_HYPOTHESIS_V1.md)、[畫面檢索 v1](../contracts/OFFICE_FRAME_RETRIEVAL_V1.md) | 範圍 | 新場景沿用格式；Office 專用常數（`floor_z_m`、`MAX_CAMERAS`）改由場景設定提供 |
| D3、D8、D14 | 決策 | D3 在新場景反轉（標記為主、C7 驗證）；D8 改為「B2 驗收前」；D14「Demo 主軸選 Office」被取代 |

#### 先做哪些最小交付

1. CS-A：Codex 回覆本文件與契約的可行性；使用者確認範圍。
2. B 包最小版：建場景與標記匯出，每台鏡頭先渲染 1 張，確認外觀、大小與標記驗證器結果。
3. 事件 A 全段 RGB，再做事件 B1。
4. 同時，Claude 可以先用 fixture 做 `player-grid.mjs`、`search-mode.mjs`。這兩個模組不依賴 RGB，只依賴契約中的 payload。

#### 標記人員怎麼以新場景為範本補其他場景（E 包）

- 範本：新場景的標記匯出檔（契約 §3）加上一份標記說明，逐類列出必填欄位、ID 規則與範例。
- validator：由 K7 改造，輸入任一場景的標記匯出檔，輸出「缺欄位、ID 重複、walkable 與 mesh 不一致、門沒有兩側連接」清單。它只報告問題，**不自動修改**標記。
- 其他場景（例如 `school_v3`）補標時，只產生新的標記檔，原 `.blend` 不改。補完的結果以 validator 報告為準，不靠口頭說「已補完整」。

#### 舊 GT 與研究結果的隔離與保留

- 舊 run 的 GT（例如 LOCAL `data/pilot/office_person_20261016_v1/rendered/ground_truth.json`）原地保留，不複製、不移動。本回覆沒有讀它。
- RQ1（#61）、C4b 凍結（#50、#53）、K7 IoU、D19 收斂 0% 等結果，都綁定原 run 與原 hash，不改寫，也不和新場景混算。
- 新場景的 GT 放在獨立目錄、使用獨立 hash，只在預測凍結後由評估工具讀取（照 RQ1 的「預測 SHA 驗證通過後才載入 GT」做法）。

## 3. 需要使用者決定的事項

| # | 事項 | Claude 建議 |
| --- | --- | --- |
| 1 | 事件 B 拆成 B1／B2，先驗收 B1 | 拆 |
| 2 | B1 盲區要不要刻意設計；轉角要不要有鏡頭 | 刻意設計在轉角，轉角不放鏡頭 |
| 3 | B1、B2 人數是否固定 2 人 | 固定 2 人；人數多寡用 UI fixture 測 |
| 4 | 解析度、幀率、格式、存放位置 | 960×540、10 Hz、PNG、資產 repo `data/pilot/<新 run>/`（路徑由 Codex 確認） |
| 5 | 八台以上用 UI fixture 測，不真的建 | 用 fixture |
| 6 | 可重用模組怎麼進新工作：先核准合併（CS-R），或新分支堆疊在 PR 上 | 先核准合併，堆疊太深時合併衝突難處理 |
| 7 | 檢查點：CP2／CP3 暫停、新設 CS-A～CS-D | 照建議 |
| 8 | D3 在新場景反轉（標記為主、C7／K7 驗證）；D8 改為「B2 驗收前」 | 照建議 |
| 9 | 現行工作台先移除綠球（A 包核准後的小任務） | 做 |
| 10 | 各項門檻：區間顯示門檻、通路距離、B1 錯開間隔、涵蓋率、同步容差 | 凍結前約定；本文不定數字 |
| 11 | #55 是否以「被 B1／B2 取代」為由關閉 | 留言說明後關閉 |

## 實際產出 / Actual output

- Model / effort: Claude Opus 5.5（`claude-opus-5-5`）／ effort 未由本 session 指定（UNKNOWN）
- PR / commits: 見本文件所在的 Draft PR（分支 `claude/controlled-scene-a`）
- Files changed: `docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md`（本文件）、`docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`、`docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md`
- Commands run and results:
  - 讀提案並計算 SHA-256（`80013790…5744b88f`）；
  - `gh pr list`、`gh issue list`、`git branch -r` 查舊工作狀態；
  - `stat` 讀既有 PNG 檔案大小（Office 人形 run、接地對照 run 各 100 張，960×540，平均 413,708／417,058 bytes），**沒有開啟影像內容**；
  - `df -h`：可用 11 GiB。
- Artifacts: 三份 Markdown，SHA 見 PR 描述
- Verified: PR 與 issue 的編號、狀態、head 與 RQ1 數字，都對照了 `gh` 輸出與 PR 描述；K4 顏色對照 `blind-hypothesis.mjs` @ `5a2c613`；綠球位置對照 `scene.mjs` @ `5a2c613`
- Not verified: 沒有讀 GT；沒有檢視影片或影像內容；沒有跑程式或測試；720p 每張大小是外推，不是實測；場景尺寸與鏡頭視野是建議值，可行性未檢查
- Deviations, UNKNOWN items and follow-ups: 「轉角有鏡頭」與「轉角設計盲區」的矛盾，Claude 改成「轉角不放鏡頭」，待使用者決定；Draft K8d 與 K5 畫面牆的本機內容 `UNKNOWN`
