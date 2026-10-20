# 決策索引（D1–D67）

> 本文只是**索引**。**決策全文以 GitHub 原始留言為準**；本文的一句摘要、狀態是整理，與原文不一致時以原文為準。
> **新增或改變決策時要同步更新這份索引**（新增一行；被取代者在原行的「狀態」寫明取代者）。
> 找不到原始位置的項目寫 `UNKNOWN`，不要推測。

整理日期：2026-10-20（含 D65–D67）。建立時對照的來源：#25／#26／#66／#67／#68／#69／#72／#81 與 #65 的留言（以 `gh api` 逐則讀取）、`OFFICE_CONTROLLED_SCENE_V1.md` @ `98451bd` §0.2、`COORDINATOR_HANDOFF_20261018.md`。

## 閱讀說明

- **日期**：留言標題或內文寫的決定日期（Asia/Taipei）。標題沒寫日期的，用留言時間換算。
- **狀態**：
  - 「有效」：目前仍適用。
  - 「被取代／被修訂」：寫明取代者。被取代的決策保留，作為歷史與理由。
  - 「已執行／已完成」：決定的動作已做完。
  - 「舊 Office 專用」：只適用 2026-10-18 以前的舊 Office 人形 run 與舊 Demo；D25 轉向後暫停，新場景的契約 §0.1 明列不沿用的項目。
- **使用者決定** vs **協調者決定**：D24 是協調者依 K8 設計決定；其餘為使用者決定（由協調者轉達的，引號內為使用者選項原文，見各留言）。
- 同一則留言可能含多項決策，連結相同。
- 連結格式 `issues/N#issuecomment-ID` 與 `pull/N#issuecomment-ID` 都指向同一個 repo 的 GitHub 留言；D26–D28 的使用者原話只在契約 §0.2 與 #65 的修訂說明留言中有摘要，原始對話：UNKNOWN。D65–D67 是協調者 session 以 AskUserQuestion 取得的使用者選擇，留言內有選項與依據。
- D43–D47 同樣只能在 #65／#72 的記錄留言與契約 §0.2 找到摘要（引號內為使用者選項原文）；使用者原始對話：UNKNOWN。

## 索引

| 編號 | 一句摘要 | 日期 | 狀態 | 原始位置 |
| --- | --- | --- | --- | --- |
| D1 | 靜態來源幾何可用於射線測試（可見範圍索引）；renderer 逐幀可見性、軌跡、深度仍禁止進推論 | 2026-10-16 | 有效 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6212450891) |
| D2 | 速度範圍是模擬設定，評估前固定在有版本的 config，不依結果調整 | 2026-10-16 | 有效 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6212450891) |
| D3 | 走道／通路／障礙由來源網格推導，`WALK_*`／`PORTAL_*`／`AREA_*` 標註只作交叉核對 | 2026-10-16 | 被取代（新場景）：D25 在新場景反轉為「標記為主，C7／K7 當驗證器」；舊 Office 仍適用 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6212500183) |
| D4 | 授權 C6 步驟 2 渲染（人形代理版舊路線＋10–15 條基準路線），每次渲染是新 run、不覆寫原資產 | 2026-10-16 | 範圍縮小：D14 把 15 條路線延後、不渲染 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6215674075) |
| D5 | 新 run 的目標代理為圓柱 1.70 m／r 0.25 m；身高先驗逐 run 設定 | 2026-10-16 | 有效（舊 Office 人形 run）；新場景人體見 D42 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6215674075) |
| D6 | 走道膨脹的身體半徑新 run 用 0.25 m，逐 run 參數 | 2026-10-16 | 有效 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6215674075) |
| D7 | 端點不可用時，C4b 可沿同 track 回溯／前探至多 1.0 s，須明示；原端點仍為 `UNKNOWN` | 2026-10-16 | 有效（舊 Office）；新場景是否沿用：UNKNOWN（D18 的人形 run 不用 D7） | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D8 | `AMBIGUOUS_MERGE` 端點到 2026-11-01 前一律 `UNKNOWN` | 2026-10-16 | 被修訂：D25 改為「B2 驗收前不可用」 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D9 | C7 Office 地圖 2026-10-22 前交付 | 2026-10-16 | 擱置：D25 暫停舊 Office 工作 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D10 | K7 發現 GT 路線違反地圖時，不依此修改地圖，只報告為 K7 結果 | 2026-10-16 | 有效 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D11 | C7／K7 逾期時座位區標 `walkable: UNKNOWN`；禁止把端點吸附到最近可走點 | 2026-10-16 | 被修訂：D16（座椅可解析者改視為障礙物）；「不得吸附端點」仍有效 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D12 | 速度上限設定 ≤2.0 m/s（CONFIGURED_NOT_GT） | 2026-10-16 | 有效；D56 Q5 重申 `v_max` 2.0 m/s | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D13 | Office 與人形重渲兩線並行，10/24 選定現場路線 | 2026-10-16 | 被取代：D14 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6216426172) |
| D14 | 現場 Demo 主軸選 Office；C6（15 條跨鏡頭路線）延後、不渲染、不列基準 | 2026-10-17 | 主軸部分被取代：D25 轉向受控新場景；C6 延後仍適用 | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6220982401) |
| D15 | 禁止區是獨立政策圖層，不是障礙物；路徑可經過並標示 `RESTRICTED_POLICY`（D3 的明確例外） | 2026-10-17 | 有效（僅舊 Office）；契約 §0.1：新場景不沿用 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6229832567) |
| D16 | 來源網格可解析的座椅／講台視為障礙物，走道可走；無法解析的座位區才標 `UNKNOWN` | 2026-10-17 | 有效（僅舊 Office；修訂 D11） | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6229832567) |
| D17 | R1：LOW_INCIDENCE-only 先用頭頂射線區間；v1.1 升級為 `FOOT_RAY_PIXEL_BAND`（±2 px） | 2026-10-17 | 有效；契約 §0.1：新場景沿用 `FOOT_RAY_PIXEL_BAND`（R1／D17） | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6231333549) |
| D18 | 人形 run 盲區端點改為 4.6 s → 8.2 s（盲區 4.8–8.0 s）；舊 run 維持 4.4 → 8.6 s | 2026-10-17 | 有效（僅舊 Office 人形 run）；契約 §0.1：新場景不沿用 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6231333549) |
| D19 | Demo 以「先不套用負證據、再套用」展示；只講可達帶收斂，不講路線條數（D21 留言內有更正） | 2026-10-17 | 有效（舊 Office Demo）；D25 後暫停 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6232257591)；更正：[#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6233644309) |
| D20 | `MAX_SEGMENT_LENGTH_M = 8.0` 定案（工程設定） | 2026-10-17 | 有效；新場景是否沿用：UNKNOWN | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6232257591) |
| D21 | C5 負證據可見性收緊為「腳＋腰都可見」＋可偵測性（≥112 px）；any-probe 足跡只作 `suggestion_polygons`；以影格去重 | 2026-10-17 | 有效；契約 §0.1：新場景沿用 strict／suggestion 規則 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6233644309) |
| D22 | 從舊 Demo 移除原步驟 5（跨鏡頭候選） | 2026-10-17 | 舊 Demo 專用；D25 後暫停 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6234034728) |
| D23 | 系統能力以 Office 地圖上的合成段（K8）展示 | 2026-10-17 | 舊 Demo 專用；D25 後暫停 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6234254765) |
| D24 | 舊 Demo 步驟編排：1–5 真實、6–8 SYNTHETIC、9 負例（決定者是協調者，依 K8 設計，不是使用者） | 2026-10-17 | 舊 Demo 專用；D25 後暫停 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6234968351) |
| D25 | Demo 轉向受控新場景（960×540／5 fps／PNG；B1／B2；固定 2 人；D3 反轉；D8 改 B2 驗收前）；舊分支與 PR 保留 | 2026-10-18 | 有效 | [#26 留言](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6245364536) |
| D26 | CS-B 用 RGB 驗收；GT 要輸出凍結且 hash 驗證後才讀（D1 不放寬） | 2026-10-18 | 有效；「逐格人工核對」部分被 D47 改為 §8.1 流程 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6245600311)（契約 §0.2 另有摘要） |
| D27 | 事件 A 雙鏡重疊的目標窗，兩台鏡頭都要拍到全身＋接地 | 2026-10-18 | 有效 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6245600311) |
| D28 | 候選鏡頭排序 `relation_tier → overlap_area_m2_desc → camera_id`，不列入偵測數 | 2026-10-18 | 有效 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6245600311) |
| D29 | 核准 CS-R：18 個 PR 以 merge commit 併入整合分支（條件：CS-A 先核准） | 2026-10-18 | 已執行（整合分支 `dcb89f4` → `f481fe0`） | [#67 留言](https://github.com/Polalalabear/amidst/issues/67#issuecomment-6246163511)；完成：[#67 留言](https://github.com/Polalalabear/amidst/issues/67#issuecomment-6246386637) |
| D30 | #64 只 cherry-pick 自己的 2 個 commit；測試修正放在 #35 步驟 | 2026-10-18 | 已執行 | [#67 留言](https://github.com/Polalalabear/amidst/issues/67#issuecomment-6246163511) |
| D31 | #51、#45 不納入 CS-R，維持 Draft | 2026-10-18 | 有效 | [#67 留言](https://github.com/Polalalabear/amidst/issues/67#issuecomment-6246163511) |
| D32 | 核准 CS-A：#65 @ `2643771`；不授權 `.blend` 與渲染 | 2026-10-18 | 有效（已完成） | [#66 留言](https://github.com/Polalalabear/amidst/issues/66#issuecomment-6246311276) |
| D33 | 初版 `.blend` 與四張 preview 建好後，停下等使用者人工審查 | 2026-10-18 | 已完成（D52、D53 審查通過） | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6246349043) |
| D34 | 前端重做：新外框＋新視覺、保留邏輯；先做功能保留清單與 mockup，核准才實作 | 2026-10-18 | 有效 | [#69 留言](https://github.com/Polalalabear/amidst/issues/69#issuecomment-6246389918) |
| D35 | 舊工作台不動、當備援；新版放 `frontend/workbench-v2/`，驗收後改預設 | 2026-10-18 | 有效 | [#69 留言](https://github.com/Polalalabear/amidst/issues/69#issuecomment-6246389918) |
| D36 | 修正 W2 pose；所有可走地板統一 z=0 | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D37 | P2 固定 11.0 s 進場；同鏡頭兩人至少錯開 1.0 s；盲窗 RGB 驗收只強制 ≥3.2 s | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D38 | 全身＋接地、距邊 ≥16 px、人高 ≥112 px；偵測器只作輔助 | 2026-10-18 | 有效；人工逐格部分被 D47 修訂 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D39 | 接受 partial 段；只有 D27 目標窗要求全身；partial 不稱盲區 | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D40 | 速度 prior 用 10 m geodesic（1.3 m/s × 約 7.7 s 的公開 prior） | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D41 | `clock_error` 容差 1 ms；磁碟峰值額度 1.5 GiB（起跑 ≥12 GiB、<8 GiB 停） | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630) |
| D42 | 名義人體 1.70 m／r 0.25 判可見，包絡 1.80 m／r 0.30 判不可見；P1、P2 中性外觀 | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630)；r004 新 run 不適用（D63） |
| D43 | 工作台 v2 設計 Q1、Q4–Q10 全部照建議 | 2026-10-18 | 有效 | [#72 留言](https://github.com/Polalalabear/amidst/pull/72#issuecomment-6248230792)；[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6248193907) |
| D44 | 人物接地估計納入三種條件：靜態遮擋邊界、軌跡身高、速度界（契約 §3.12、§6.3、§6.3.1） | 2026-10-18 | 有效 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6248148114) |
| D45 | 估計誤差要明確標出：機器可讀不確定度、UI 顯示、Demo 逐步說明（契約 §2.4） | 2026-10-18 | 有效 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6248193907) |
| D46 | 3D 人物只顯示從 2D 重現的結果；工作台不讀 GT、不做 GT 對照圖層 | 2026-10-18 | 有效 | [#72 留言](https://github.com/Polalalabear/amidst/pull/72#issuecomment-6248230792)；[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6248193907) |
| D47 | CS-B 影像驗收改為「模型先篩、人工看重點格」，之後可能接 OpenAI 視覺 API（契約 §8.1、§7） | 2026-10-18 | 有效（取代 D38 人工逐格；修訂 D26 該句） | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6248210817) |
| D48 | B-Q7：W2 改 x=14.4；`OBSTACLE_SCREEN_N` 加深到 y=[5.25, 5.6]（盲窗 3.2 → 3.4 s） | 2026-10-18 | 有效；角度部分被 D50 修訂 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250719072) |
| D49 | 條件式授權建 `.blend` 與四張 preview；建完停下等 D33 | 2026-10-18 | 已執行（條件 3 一度未通過 → D51 → D53） | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250719072) |
| D50 | W2 yaw 改 205°（Euler 80, 0, 115） | 2026-10-18 | 有效（修訂 D48 的角度） | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251036732) |
| D51 | 收窄人形（側向半徑 ≤0.30 m、高度 ≤1.80 m），建 r002，r001 保留不渲染 | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251274212) |
| D52 | D33 審查：修牆面黑縫，建 r003；不改牆面位置、遮屏、路線、鏡頭、門檻 | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251557354) |
| D53 | 「r003 確認，D33 通過」；r003 為整段渲染基準 `.blend` | 2026-10-18 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251816000) |
| D54 | 生成前門檻 A1–A4：保守多標、路線投影 ±20%、雜湊排序抽 10%、邊界各 2 格＋切換處 | 2026-10-18 | 有效；看過 RGB／GT 後不得調整 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251885971) |
| D55 | 授權整段渲染：A 3 台各 50、B1 4 台各 100，共 550 張，5 fps；不凍結、不讀 GT | 2026-10-19 | 已執行（550 張，缺格 0） | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6252064337)；完成：[#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6253836773) |
| D56 | 門檻提案 #76 第 2–7 輪（Q5–Q26）：v_max 2.0 m/s、軌跡身高、`quality_grade`、E1–E5 目標、延遲目標等 | 2026-10-19 | 有效；Q10 被 D61 修改 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6270650347) |
| D57 | `rgb_index` 正式鍵名 `records[]`；舊版 `frames[]` 只能經 pin 清單的 adapter 在記憶體內轉換 | 2026-10-19 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6270789403) |
| D58 | 實體與 walkable 重疊改以穿透深度判定，容差 1×10⁻⁵ m（≤ 記 INFO） | 2026-10-19 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6270789403) |
| D59 | CS-B 通過（事件 A、B1 的 r003 影像與靜態標記；不含推論正確性、凍結、GT、runtime READY） | 2026-10-19 | 有效 | [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6271380297) |
| D60 | 核准契約 v1.1 @ `98451bd`；之後修改要開新版本 | 2026-10-20 | 有效 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6271569817)；同文：[#66 留言](https://github.com/Polalalabear/amidst/issues/66#issuecomment-6271570361) |
| D61 | 不再串入姿態模型；§6.3.1 第 4 步「外部視覺判斷」保留欄位、v1 固定 `NOT_USED` | 2026-10-20 | 使用者已決；契約 v1.2 條文為草案（待 Codex 確認與使用者核准）；修改 D56 Q10 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6271619178) |
| D62 | 第二批整合規格未決項目 O1–O14 全部照建議（O10 改為「先跑 K7 再核准」） | 2026-10-20 | 使用者已決；契約 v1.2 條文為草案 | [#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6281314876)；同文：[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6281315154) |
| D63 | Q1／Q2 第一版轉向：主線為 Q1／Q2，3D 線暫停保留；場景修改另存 r004（r003 不動）；LLM 只做語意解析，切鏡由規則決定；允許 HSV 顏色輔助訊號（身分仍 UNCONFIRMED）。**修訂（2026-10-20）**：(c) 改為 Agent 輪詢合法 top-k、超過上限由決定性規則兜底（排序不交給 Agent）；新增 (e) 第一版不做同色干擾、(f) 授權下載 RT-DETR 權重；首要目標 Q1–Q5 | 2026-10-20 | 有效；(c) 被同日修訂取代，規則例外見 D64 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6285089392)；同文：[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6285089691)；修訂：[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6286156319) |
| D64 | Q1–Q5 規則例外與 Q4 模型範圍：契約 #86 Q-01 列 DEVELOPMENT_RULES 例外，允許 Agent 在合法 top-k 內切鏡上 Demo（排序仍決定性、有上限與兜底、全程記錄、GT 不進 Agent，只限 Q1–Q5 主線）；Q-08 第一版只用 RT-DETR＋HSV，VLM 留第二版、不接外部 API | 2026-10-20 | 使用者已決；規則條文為 PR [#125](https://github.com/Polalalabear/amidst/pull/125)（未合併；D67 決定 Codex 審查通過後由協調者合併，合併後 G3 成立） | [#86 留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727)；同文：[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286157140) |
| D65 | 核准檢查點 #88：契約 #86 @ `3873ff2`（檔案 bytes SHA-256 `924c4365…78078`）與計畫 #92 @ `86877b2` 以 merge commit 依序合併進 `mainline/q1q5`（不進 `main`），G1 成立；契約 §11 參數組當**第一版初值**（top_k 3、3 輪、5,000 ms、2,000 ms、IoU 0.30、中心距 0.50、缺 2 格〔`link_max_gap_us` 600,000 us〕），綁定 `parameter_set` hash，前提索引取樣 5 fps（改 2.5 或 1 fps 會 `PARAMETER_GRID_MISMATCH`）；之後只能用 r004 preview 另出新版調整。#126 預算不在本次範圍。未放行：#125（G3）、O10／K7（G4）、r004 建檔與渲染（G5）、D41 磁碟門檻、#90 的 U 決定、§14 其他選項 | 2026-10-20 | 有效；契約 #86 → merge `f62ab72`、計畫 #92 → merge `b1a1b32`；G3、G4、G5 仍各自保留（G3、G5 部分由 D67 補充） | [#88 留言](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432)；送審紀錄：[#88 留言](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291447941) |
| D66 | #90 的待決 U-1–U-8 全部採建議：U-1 底座 #74／#71／#79 合入 mainline；U-2 劇情預期清單用瀏覽器檔案選擇器或拖放載入，檔案放 repo 外；U-3 匯出的審核 JSON 只帶 `expectation_id` 與預期檔 `file_sha256`；U-4 SYNTHETIC 下的人工判定照實記 `verdict`、`counts_for_acceptance: false`；U-5 審核進度以 `output_sha256` 為鍵存 `localStorage`，正式紀錄只有匯出檔；U-6 UI 照回應的 `switch_mode` 顯示、Demo 預設 `RULE_ONLY`，`AGENT_SEQUENTIAL` 等 G3 後才開放；U-7 Q3 解析成功後直接執行並顯示可修改的結構化查詢（`origin: MANUAL` 重查）；U-8 Q5 硬切、時間軸畫決策點、候選欄在 `SEARCHING` 期間常駐。G7 成立；不放行 G3、G4、G5 | 2026-10-20 | 有效；設計 [#90](https://github.com/Polalalabear/amidst/pull/90) 仍是 Draft，欄位對應待對齊 `3873ff2` | [#90 留言](https://github.com/Polalalabear/amidst/pull/90#issuecomment-6291537538) |
| D67 | ① #125 規則例外先請 Codex 審查，審查通過後協調者直接以 merge commit 合併，不再另問使用者（合併後 G3 成立）；② #126 搜尋／兜底預算當第一版初值（`agent_max_illegal_submissions` 2、`search_window_us` 6,000,000、`research_interval_us` 1,000,000、`session_max_research_rounds` 6、`fallback_budget_ms` 1,000、`session_max_agent_rounds` 12），綁定 `parameter_set` hash，之後只能用 r004 preview 另出新版；③ G5 **只授權建檔**：#132（#97 提案）經 Claude 審查通過後 Codex 可建 r004（r003 的複本，r003 與其 pin 不動）並做靜態校正匯出，**不授權任何渲染**（含廣角小批 preview、A4／B4 事件 run），渲染待磁碟 ≥ 12 GiB（D41）後另問使用者；④ #131 finalization：Codex 先把移除計畫寫成 repo 內文件並開 Draft PR 由 Claude 審查，**不執行任何搬移或刪除**，執行與否另問使用者；⑤ 本板上 Codex 任務的 PR，只要 Claude 審查通過、#127 測試包（當時綁定的契約版本）通過、合併前 head SHA 相符，協調者即以 merge commit 合進 `mainline/q1q5`，不再逐一問使用者（**不含**規則、契約、r004／渲染、finalization 類 PR，以及 `main`）；⑥ 允許疊分支：上游 Codex Draft PR 已開，下游即可從其分支開工，PR base 先指向上游分支，上游合併後改回 `mainline/q1q5`，上游要求修改時下游以 merge 跟上（不 rebase、不 force）；自選規則第 1、3 條據此放寬。仍未放行：渲染、G4 | 2026-10-20 | 有效；補充 D64（#125）、D65（#126 與 G5） | [#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) |

## 相關的非 D 編號決定與檢查點

| 項目 | 位置 |
| --- | --- |
| CP1 核准（2026-10-17，K2、C3b、K0 v1 草稿） | [#25 留言](https://github.com/Polalalabear/amidst/issues/25#issuecomment-6229577255)；D14 之後 C6 移出 CP1 |
| CS-A／CS-R／CS-B／CS-C 檢查點 | [#66](https://github.com/Polalalabear/amidst/issues/66)、[#67](https://github.com/Polalalabear/amidst/issues/67)、[#68](https://github.com/Polalalabear/amidst/issues/68)、[#69](https://github.com/Polalalabear/amidst/issues/69) |
| #88 Q1–Q5 計畫與契約核准檢查點 | 已核准（D65，2026-10-20）：[#88](https://github.com/Polalalabear/amidst/issues/88) |
| CS-D（曲線與預測） | 尚未建立檢查點；方向見 D56 Q12 |
| 契約仍 OPEN 的項目 | 契約 `OFFICE_CONTROLLED_SCENE_V1.md` §9；D62 已結案其中 CS-Q15 (6)(7)(11) 與 CS-Q9 通路項 |

## 維護規則

1. 新決策先貼在對應 issue／PR 留言（含使用者選項原文、日期、依據），再回來加一行。
2. 狀態改變（被取代、已執行）時改原行，並在取代者那一行寫明取代了誰。
3. 本文不複製決策全文，也不複製 schema 或數值表；要查數值，看 `SYSTEM_OVERVIEW.md` 的規格總表指向的契約章節。
