# Office 可驗證 Demo 計畫（目標 2026-11-01）

> 狀態：2026-10-16 規劃文件，由使用者與 Claude Code 討論後整理。功能凍結 **2026-10-29**，報告 **2026-11-01**（12 分鐘，主流程 10 分鐘＋2 分鐘緩衝）。
> 證據依據：[綠球診斷](../engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)、[接地點 QA](../engineering/OFFICE_CONTACT_SPATIAL_QA.md)、[管線地圖](../engineering/OFFICE_PIPELINE_MAP.md)、[MVP](OFFICE_DEMO_MVP.md)。
> 本文件不改變 [DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)：GT 隔離、來源追溯、`MISSING`／`UNKNOWN` 分離與身分 `UNCONFIRMED` 全部照舊。

## 1. 專案定位（對外說法）

| 面向 | 建議說法 | 不要說 |
| --- | --- | --- |
| 研究 | 多鏡頭、視野不重疊條件下，對**選定目標**的跨盲區位置推測與不確定性量化 | 「追蹤特定人物」：系統沒有外觀／身分辨識，身分維持 `UNCONFIRMED`；目前目標是合成圓柱，應稱「類人目標」 |
| 工程 | ① 可重現與證據完整性（來源／hash 綁定、GT 隔離、缺資料即 fail-closed、確定性重播）；② 以索引取代逐張掃描的有界檢索 | 「大量資料檢索」在量測前不成立：目前每個 run 只有 100 張影格 |
| Agent | Agent 編排＋確定性備援：Agent 只呼叫有界、可稽核的工具，結果可重播 | 「Agent 語意判斷」：Office MVP 中 Agent 為延後項目；R2 品質門檻未過、R3 首次真實模型 demo 失敗（見 main README） |
| 實用性 | 調查人員不必逐支影片回看，系統指出「該去看哪幾段」，並誠實標示不確定之處 | 物理安全、通行性或身分確認 |

核心主張是**可信的不確定性**：系統不只輸出單一答案，而是給出物理上可能的情境（推測曲線），並說明不確定的原因。

## 2. 目前成果（2026-10-16）

| 工作 | 結果 | 證據 | 狀態 |
| --- | --- | --- | --- |
| 綠球跳動診斷 | 椅背遮住圓柱底部＋視線太斜（incidence 0.158–0.188），地板跳 1.7–2.0 m；不是分軌、太小或投影失敗 | [診斷](../engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md) | 已確認 |
| REAR 未偵測 | REAR 0.0–8.2 s 影格逐像素相同；路線刻意選擇「可見→盲區→可見」 | 同上 | 已確認 |
| 單位 | 後端已轉公尺（z = 0.496 m） | 同上 | 已排除 |
| 底部可見驗證 run＋perception v2（Codex） | 62 配對點平均誤差 0.155→0.097 m、最大 0.356→0.133 m；0 個 `SPEED_CAP` 跳點；47/50 時刻有位置。代價：Office 原 31 點在 v2 下全部被拒絕（多為 `LOW_INCIDENCE`） | Codex 報告 `CONTACT_CONTROL_VALIDATION_20261016.md`（Codex 本機 commit `bb3d282`，2026-10-16 尚未推送）；Claude 以其 CSV 獨立重算一致 | 完成，待推送 |
| 管線地圖 | 一頁對照每階段檔案、符號與門檻 | [PR #9](https://github.com/Polalalabear/amidst/pull/9) | 已合併 |
| GitHub 整理 1、3、4 | PR #4、#6–#9 以 merge commit 併入 `claude/office-demo-visualization`；刪除 6 條已合併分支；main、tags 未動 | — | 完成 |

## 3. 方法：觀測 → 假設 → 檢索 → 驗證

1. **觀測（RQ1）— 混合接地估計器。** 腳點可見：v2 地板投影，輸出點。腳點被擋：頭頂射線＋身高範圍（例 1.5–1.9 m），輸出射線上的**區間**；再以已知遮擋物幾何（腳必在遮擋物後方）與可走區域裁剪。輸出統一為「點或線段」。
   - 不採「只用頭頂映射」：本攝影機配置下更差，見[診斷 §4](../engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md#4-頭頂映射可行性分析)。
2. **假設（RQ2）— 盲區物理推測曲線。** 輸入盲區兩端狀態、可走區域與門口標註、速度範圍（設定檔，非 GT）、**負證據**（盲區內所有攝影機皆未偵測 → 路徑須落在不可見地板）。在可走區域路徑網格上篩選 K 條代表路徑＋每時刻可能位置範圍。狀態 `INFERRED_HYPOTHESIS`，排序為合理程度而非機率；物理通行性仍 `UNKNOWN`。
3. **檢索（RQ4）— 可能畫面。** 預算各攝影機地板可見範圍索引；以假設路徑的時空範圍求交集 → 「哪台、哪段」→ 調出影格。對應畫面沿用既有 `timeline`／畫面牆有界索引。
4. **驗證（閉環）。** 檢索畫面中未偵測 → 新負證據 → 刪除假設 → 帶寬收斂。

### CP1 決策（2026-10-16，紀錄見 [#25](https://github.com/Polalalabear/amidst/issues/25)）

- **D1：** 攝影機地板可見範圍索引可用靜態來源幾何做射線測試；渲染器逐幀可見性、目標軌跡與深度仍禁止進入推論。
- **D2：** 速度範圍為模擬設定，挑選貼近真實的值後於評估前寫入版本化設定檔並固定，不依路線或結果調整；基準路線的目標速度落在同一範圍。
- **D3：** 可走區域、門口與障礙物由來源網格推導（C7，[#29](https://github.com/Polalalabear/amidst/issues/29)），`WALK_*`／`PORTAL_*`／`AREA_*` 標註只作交叉核對（K7，[#30](https://github.com/Polalalabear/amidst/issues/30)）；僅限 Demo 區域。K1 在 K7 通過前先以標註開發，之後改用推導地圖。真實建築通行性維持 `NOT_CERTIFIED`。

## 4. 研究議題與量化指標

| 子議題 | 方法 | 指標 | 現況 |
| --- | --- | --- | --- |
| RQ1 單鏡頭接地定位 | v1 bbox 底邊 vs v2 遮罩最低點 vs 混合區間 | 平均／最大誤差（m）、覆蓋率、跳點數、每像素敏感度、遮擋幀真值落入區間比例與區間長度 | v1/v2 已有結果；混合區間未做 |
| RQ2 盲區假設 | 約束路徑法 vs 現有直線橋接 | 涵蓋率（真值落入帶狀區的時間比例）、帶寬、最佳假設平均距離、最佳假設排名 | 未做 |
| RQ3 跨鏡頭關聯 | 現有關聯圖與排名 | Top-1／Top-3 命中率、MRR、錯誤關聯率 | 機制已有，未批次評估 |
| RQ4 畫面檢索 | 假設 × 可見範圍 vs 全部畫面 | 召回率、需檢視畫面比例、查詢延遲（ms）、讀取筆數；擴充至 10⁵–10⁶ 筆紀錄量測 | 未做 |

**樣本：** 單一路線不構成統計。基準至少 10–15 條「可見→盲區→可見」路線（含盲區內轉彎）＋5 條全程可見對照。所有評估在預測凍結後才讀 GT。

## 5. 場域選擇

| 選項 | 判斷 |
| --- | --- |
| **A. 現有 `school_v3.blend` 其他攝影機（首選）** | 至少 7 台已校正：`CAM_1F_AUDITORIUM_FRONT/REAR`、`CAM_1F_SIDE_ENTRANCE`、`CAM_1F_CLASS101`、`CAM_1F_CORRIDOR_02/03/04`；比例尺、可走區域與來源鏈已完備。走廊攝影機地板可見範圍 `UNKNOWN`，需先做規劃腳本視線測試（不渲染）。 |
| B. 同一 `.blend`，不存檔程序加虛擬（俯拍）攝影機 | A 不足時的備案；屬於修改來源場景設定，需使用者明確授權並完整記錄來源。 |
| C. 另建模擬場景 | 不建議：比例尺、校正、物理證據需重建，16 天內無法完成審核。 |

其他決策：新 run 改用人形尺寸代理目標（約高 1.7 m、半徑 0.25 m），舊 run 保留 2.94 m 圓柱以維持連續性。多攝影機路線需放寬 `MAX_CAMERAS=4`、`MAX_WINDOW_S=10.0`。

## 6. 分工（2026-10-16 起，取代舊「Claude 只做前端」）

| 項目 | Codex | Claude Code |
| --- | --- | --- |
| 場域與資料 | 可行性檢查、路線規劃、渲染（含人形代理）、bundle、場景預設與啟動器 | 審核路線、抽查影格 |
| 單鏡頭定位 | perception v2、混合估計器 | 獨立重算誤差 |
| 盲區假設（P0） | 接上 API、整合 `target_reconstruction` 與審查證據 | **演算法模組**（純函式＋單元測試） |
| 畫面檢索（P1） | 可見範圍索引、查詢 API、規模化延遲量測 | 「建議檢視」畫面牆、延遲分析圖表 |
| 負證據閉環 | 提供檢索「未偵測」紀錄 | 接入假設模組、收斂帶寬 |
| 評估 | 輸出預測、維持 GT 隔離 | **評估工具**與結果圖表 |
| Agent | 調查規劃者編排與錄製重播 | 重播呈現與 hash 核對 |
| 前端 | — | 假設路徑束、區間觀測、品質標示、場景切換、Demo 模式（數字鍵跳步驟） |
| 驗收與文件 | 各自任務相關測試 | 瀏覽器驗收、驗收紀錄、Demo 腳本、研究文件、報告視覺素材 |

**協作：** 10/17 先定三份資料契約（區間觀測、盲區假設、畫面檢索），Claude 起草、Codex 確認，之後雙方以假資料平行開發。分支 `codex/*`／`claude/*`，PR 以 merge commit 併入 `claude/office-demo-visualization`（不 squash、不 rebase；文件引用 commit SHA），互相審查。整合點 10/24，凍結 10/29。目前畫面以「功能正確」為主，之後會整體重構 UI／UX，前端不投資樣式。

## 7. 時程與取捨

| 日期 | Codex | Claude Code | 使用者 |
| --- | --- | --- | --- |
| 10/16–10/18 | 推送 v2；任務 3；A 方案視線可行性檢查 | 資料契約草案；整理步驟 2、5 | 指派任務 3、4 |
| 10/19–10/23 | 混合估計器；P0 API 整合 | 假設模組；場景切換＋品質標示前端；評估工具（RQ1） | 決定渲染授權（基準路線／B 方案） |
| 10/24–10/27 | P1 索引＋檢索 API；基準路線渲染 | P0 前端；Demo 模式 | — |
| 10/28–10/29 | P2 指標輸出；**凍結** | P1 前端；最終驗收 | 準備投影片 |
| 10/30–10/31 | — | 錄製備援影片 | 排練兩次並計時 |

**落後時依序刪除：** 虛擬攝影機（B）→ Agent 重播 → 規模化檢索量測 → P2 基準量化（研究段改報 RQ1 實測＋RQ2–RQ4 方法與預定指標）→ P1。**必保：** 混合估計器、多攝影機或多路線資料、P0 盲區假設。

## 8. Codex 任務

### 任務 1、2（已完成，待推送）

底部可見驗證 run `blender-contact-control-auditorium-v1` 與 perception v2，結果見 §2。

### 任務 3：工作台多場景預設＋接地點品質旗標

- **前提：** v2 commit 並推送至 `codex/mvp-backend-integration`。
- **多場景：** `scripts/office_demo_backend.py` 改讀預設清單（例 `configs/office_demo_presets_v1.json`），每個預設各自 fixture／bundle／hash 驗證並註冊場景；以 `SceneAdapter.with_display_identity` 給獨立 `scene_id` 與中文 `label`／`description`；預設維持 `blender-office`。
- **(b) `blender-office`：** 原 31 個觀測、fixture、track_ref 與位置不改，只加 `contact_quality` 旗標。
- **(a) 新場景（例 `blender-contact-control`）：** 驗證 run，位置用 perception v2；逐場景設定 `perception_version`；新增 fixture。
- **逐場景 fail-closed：** 缺 physical source 或 motion／association／physical 資料時只關閉該層並讓前端知道；不得以 Office 資料頂替；run／時鐘／hash／觀測不得混用。
- **啟動器：** `scripts/start_office_demo.py` 的 `readiness` 改為「場景清單與預設清單一致」（現寫死 `{'blender-office'}`）；啟動指紋納入預設清單與每份 fixture。
- **`contact_quality` 契約：**

```json
"contact_quality": {
  "version": "rgb-mask-contact-v2",
  "status": "PASS | FLAGGED | NOT_EVALUATED",
  "reasons": ["LOW_INCIDENCE", "CONTACT_OCCLUDED", "TOUCHES_IMAGE_EDGE", "AMBIGUOUS_MERGE"],
  "pixel_sensitivity_m": 0.15,
  "authority": "QUALITY_FLAG_ONLY_POSITION_UNCHANGED"
}
```

  附在所有帶 `observation_ref` 處（query observations、cross-camera path samples、physical review `synchronized_evidence.samples`）。v1→v2 對應（2026-10-16 修訂；原「v2 遮罩像素涵蓋 v1 接地點」會因 bbox 底邊中點常落在遮罩外而全部變成 `NOT_EVALUATED`）：同幀同鏡頭、**v1 元件的遮罩像素屬於哪個 v2 元件**就對到該元件（兩者同為 `>30` 差值遮罩，4-連通元件必包含於唯一的 8-連通元件，故對應唯一）；若無法重算 v1 遮罩，退用「v2 元件包圍框涵蓋 v1 接地點」，命中多個 v2 包圍框時設 `NOT_EVALUATED` 並記錄 `AMBIGUOUS_MAPPING`。找不到為 `NOT_EVALUATED`；兩個 v1 對到同一 v2 時皆標並加 `AMBIGUOUS_MERGE`。對應只決定旗標，不改 v1 位置。(a) 保留點為 `PASS`；被拒絕點維持 `MISSING`，原因寫在原 missing 欄位。
- **驗收：** readiness 通過並列出兩場景；`blender-office` 回應除新增欄位外逐欄相同、31 觀測斷言仍成立；0.4、0.6、1.8、2.0、4.4 s 為 `FLAGGED` 並附原因；(a) 可載入且缺資料層明確標示；只跑相關測試與 `git diff --check`。

### 任務 4（範圍，詳細交接待寫）

混合估計器（§3.1）、P0 盲區假設 API 整合、P1 可見範圍索引與檢索 API、基準路線渲染（需授權）、P2 指標輸出。

## 9. 報告與 Demo（10 分鐘，畫面為主、數據為輔）

| 時間 | 段落 | 主畫面 |
| --- | --- | --- |
| 0:00–0:45 | 簡介 | 一句定位＋場景全景 |
| 0:45–1:45 | 問題與實用性 | 盲區示意：兩台攝影機中間的空白 |
| 1:45–2:30 | 流程 | 觀測→假設→檢索→驗證閉環圖 |
| 2:30–3:30 | 架構與工程性 | 管線圖；來源綁定、GT 隔離、fail-closed |
| 3:30–8:00 | 現場 Demo | 見下 |
| 8:00–9:30 | 研究面 | 遮擋放大圖、新舊接地點疊圖、帶寬收斂動畫；數字作角落標籤 |
| 9:30–10:00 | 下一步 | 多攝影機路線、事件檢索、真實影像 |

**現場 Demo：** 兩鏡頭＋3D 同步播放 → 4.4 s FRONT 選定 → 盲區 4.6–8.4 s 不畫位置、展開假設路徑束 → 8.6 s REAR 再出現 → 候選切換（`UNCONFIRMED`／`UNKNOWN`）→ 建議檢視畫面牆亮起 → Classroom101 負例（可刪）。

**視覺語言：** 觀測藍綠、推論琥珀、缺失灰色虛線、假設半透明第五色；圖例常駐；標籤 ≤6 字。每個數字都要有對應畫面。

**上台規則：** 只現場操作已在瀏覽器驗證的路徑；未完成者用預製圖。舊流程的 E1 調查／報告與 Agent 回答移出主線（附錄）。2D 分時畫面牆降為診斷面板。

**準備：** 備援錄影；報告前 10 分鐘跑 readiness；固定跳轉時間點（0.0、4.4、6.0、8.6 s）；固定瀏覽器狀態；排練兩次並計時；每次 Demo 產生逐項驗收紀錄（通過／失敗／`UNKNOWN`＋hash）。

## 10. 限制與 UNKNOWN

- 全部結果僅限合成場景；目標為 2.94 m 合成圓柱，未驗證真人。
- 兩台攝影機時盲區只有兩端點；負證據與 RQ3 需多攝影機路線。
- 走廊攝影機地板可見範圍、E1 場景攝影機配置、Agent 憑證現況：`UNKNOWN`。
- 物理通行性、碰撞與身分：維持 `UNKNOWN`／`UNCONFIRMED`。
- 錯誤處理與誤差回報的現況與缺口：見[管線地圖 §6](../engineering/OFFICE_PIPELINE_MAP.md#6-錯誤處理與誤差回報)。
