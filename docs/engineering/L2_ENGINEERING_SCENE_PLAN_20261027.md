# L2-6 工程小場景規劃（2026-10-27）

F2／[#249](https://github.com/Polalalabear/amidst/issues/249)。**PLANNING_ONLY／PROPOSED；沒有建場景、複製資產、渲染或推論。** D90-3 已決定延後 L2-6 渲染；本文件不構成產製授權。Line 1 的 r004／A4-1／B4-1、圖 v3／G4、D79、既有題目與錄製不改。

## 1. 最小場景與鏡頭

建議先用 **2 台、30 s、5 fps、960×540** 的獨立工程 source/run；第 3 台只作另外明示的診斷選項。只要兩台能實現指定盲區，不為了湊鏡頭數增加第三台。此為新場景版本提案，不能沿用 r004 catalog／calibration／graph pin；版本名與 source path 待核定，尚未建立任何 `.blend`。

| 元素 | 設計規格 | 用途／限制 |
| --- | --- | --- |
| L 型走廊 | 兩段各約 8 m、寬 2.4 m，一個 90° 轉角；平地且尺度明確 | 單一受控幾何，方便靜態投影；實際通行／碰撞仍 UNKNOWN |
| CAM_L2_A | 第一段走廊，約高 2.5 m，固定 pinhole；HFOV 70°–75° 待靜態投影定案 | seed、兩次短暫失聯、回接；目標在主測試區內維持全身，另設邊界測試區 |
| CAM_L2_B | 第二段走廊，約高 2.5 m，固定 pinhole；HFOV 70°–75° 待靜態投影定案 | 轉角後接手，先有正常全身觀測，再測部分畫面邊界截斷 |
| 靜態短遮擋板 | 第一段走廊的畫面側遮擋；名義可見性缺口路程 1.2 m | 以計畫速度 1 m/s 對應 1.2 s；板不得放在名義行走帶中，須靜態幾何複核，不能先假定沒有碰撞 |
| 轉角盲區 | 名義路徑由 (-3,0) → (0,0) → (0,3)，共 6 m | 1 m/s 約 6 s；需 static frustum／遮擋幾何證明出口與入口設計成立。不能拿直線 √18 m／速度取代折線路長 |
| CAM_L2_REF（選配） | 高位固定參考鏡頭，可看到轉角 | 只作 LOCAL 視覺診斷，**不進 A/B 主 tracking scope、Q1/Q4/Q5 evidence 或 ranking**。若要納入產品，另註冊 camera set／run 與圖、重新凍結 |

世界座標只是規劃座標，不是已匯出的 source geometry。角色外觀／身高／材質用新工程設定明示；任何既有 immutable actor asset 的使用方式都要在產製授權中列清，不覆寫、移動或複製原資產。先固定背景／鏡頭／ROI，之後才產事件，不能看事件偵測結果後重畫出口來迎合分數。

## 2. 約 30 s 的計畫流程

以下時刻是規劃值，**不是 GT／實測 visibility，也不進 inference**。真正 `t_L`／`t_X`／`t_N`、可見區與 sampled RGB 必須在凍結設計後另行驗證。

| 計畫時間 (s) | 段落 | 工程目標 |
| --- | --- | --- |
| 0.0–3.0 | CAM_L2_A 正常全身觀測，顯式選 seed | 固定 detector／score／bbox 基準 |
| 3.0–4.2 | 靜態遮擋板後穿行，計畫暫失 1.2 s | L2-5 的第一次 RETURN／重新建立 local segment |
| 4.2–6.2 | 同鏡頭重現 2.0 s | 10 格名義可見樣本；2.0 s 大於 v2 卡的 1.4 s 間隔要求 |
| 6.2–7.4 | 沿同一遮擋板再穿行，暫失 1.2 s | 反覆暫失；不以人工 mask index 製造假漏檢 |
| 7.4–10.0 | CAM_L2_A 正常可見並走向轉角出口 | 供第二個 session 明確選 seed，記原始觀測 |
| 10.0–16.0 | L 型名義路徑 6 m、1 m/s，計畫 A/B 都看不到 | 計畫 SWITCH 空檔6s >5.2s，歸 Line 2 `LONG_GAP`；產品仍無 LOST enum／timeout |
| 16.0–20.0 | CAM_L2_B 入口後正常全身 | 選定 evidence 後接手，對照正常 bbox／score |
| 20.0–25.0 | 在 B 的邊界測試帶移動，計畫部分截斷 | F1 IoU／形狀變化診斷；不是預先保證 detector 失敗 |
| 25.0–30.0 | 回到 B 的正常觀測帶，停留至結束 | 量測恢復、保留顯式 UNKNOWN／GAP |

**一個 source run、兩個明確工程 request／session（提案）**：S1 `[0,9)` s 只查兩次短暫失聯；S2 `[8,30)` s 明確以 A 的觀測為 seed，查長盲區接手與 B 邊界段。同一 RGB/index 可重用，不因兩個 request 多渲染一份。分開 session 只為分離診斷範圍，**不保證能在輪數上限內完成接手**。現行參數是 `session_max_research_rounds=6`、`research_interval_us=1000000`；第6次 SEARCHING 可執行，第7次之前結束。v2 情境卡的每場次4次是設計稿保留餘裕的規劃值，不能當產品上限。

S2 的名義排程須另驗 phase／window：假設5fps、第一個 missing cell `t_fm=10.0s`、最後觀測 `t_last=9.8s`、`L=0.6s`、`Δ=0.2s`，第一次 SEARCHING 是 `t_last+L=t_fm+L−Δ=10.4s`，不是 `t_fm+L=10.6s`。若前面都 RETURN 且沒有重現，R=1s 時六次決策為10.4、11.4、12.4、13.4、14.4、15.4s；16.4s的第7次會先以輪數上限結束。目的鏡頭計畫16.0s出現的觀測，**可能**在第6次或更早的合法 candidate window／guard 中被選作未來 entry；這取決於凍結圖、窗口、實際觀測score／color／coverage，不能僅因16.0>15.4就判失敗，也不能保證成功。若到第6次仍無合法 entry，S2 無法靠第7次接手。實際 `t_fm` 的格點相位及提早漏檢還會改變以上排程。

因此兩個session的輪數與進入窗可行性為 **UNKNOWN，待 #248 契約核對與 #244 評分規則核定後驗證**。必要時可提議在轉角的靜態設計中調整停留／路徑長或計畫空檔，再重新核對所有時刻與事件窗；不暗改參數、退款輪數或把人工mid-gap重選當成功的自動接手。正式評分事件與窗由 #244 owner 提案／使用者核定；本規劃不定正解。

參考 v2 設計稿的 `LONG_GAP` 分類與反覆 RETURN 範圍，並不表示設計稿已核定。視野重疊若存在，依 D90-2 要先失聯、進入 SEARCHING，才可接手；不做提早切鏡。若靜態投影無法實現短遮擋與6m盲區，此排程標 UNKNOWN 並先修設計，不開渲染試誤。

## 3. 格數、磁碟與時間估算

歷史係數只作容量／forward 預算：RGB `63,976 KiB／150 格`、CPU detector forward `1.108406209 s／格`，出自 [r004 提案 §5](R004_SCENE_CHANGE_PROPOSAL.md)，沿用 [#261 v2 情境卡 §3](https://github.com/Polalalabear/amidst/pull/261)。**1.1084 s 是 detector inference，不是 Blender render 時間。** 新場景每格壓縮率、真 render seconds/frame、完整索引 throughput、source／texture 體積與峰值目前 UNKNOWN。

| 項目 | 2 台（建議） | 3 台（選配） |
| --- | ---: | ---: |
| RGB 格數 N = cameras ×30×5 | 300 | 450 |
| 歷史壓縮係數估 RGB | 0.1220 GiB | 0.1830 GiB |
| 如 RGB 同時有一次完整打包副本 | 0.2440 GiB | 0.3661 GiB |
| 全部 RGB 同時保留未壓縮 8-bit RGB（不建議） | 0.4345 GiB | 0.6518 GiB |
| 歷史 detector forward 估計 | 5.54 min | 8.31 min |
| 原始 top-300 JSONL 預留（假設每候選1 KiB） | ≤0.086 GiB 的預算值 | ≤0.129 GiB 的預算值 |

top-300 的1 KiB是**工作預算假設、不是量測上界**；編碼 bytes、其他 metadata 及模型 RSS 需分開量測。REF 若純視覺診斷，不應多做 detector；上表3台 forward是全部推論的保守比較值，兩台產品索引仍300格。

渲染估算公式是 `T_render_minutes ≈ N × r / 60 + setup_minutes`，其中 `r` 為未量測的每格渲染秒數。以下只是**明示假設的敏感度表**，提供使用者排程，不是本機速度或承諾：

| 假設 r（s/格） | 2 台300格 | 3 台450格 |
| ---: | ---: | ---: |
| 1 | 5 min＋setup | 7.5 min＋setup |
| 5 | 25 min＋setup | 37.5 min＋setup |
| 10 | 50 min＋setup | 75 min＋setup |

沒有可信的歷史 render 係數時，正式申請須將 render ETA 標 **UNKNOWN**；經另行授權後先量測限定幾格、同一 engine／resolution／settings，再用中位數與慢格值分別估全批。該量測本身是 render，也受授權與 disk gate；這次沒有啟動。

建議為新 source／RGB／index／raw audit／一次打包與暫存設 **2 GiB 軟預算**，並逐項量測；不是宣稱已量到2GiB。維持原模型與素材單份，不另建 venv／worktree、不複製大資產；zip 若造成超額先停止再回報。D90-3 的三個現有 `.local-worktrees` 與服務不動。

開工前的磁碟條件不能只看「現在13GiB」的舊快照：先取得 `df -k` 精確 available bytes。至少保留8GiB停止線，且本計畫保守保留既有 D41 的 **開始時 ≥12GiB**；另須滿足預算後 free≥8GiB。逐格或每小批檢查，低於8GiB立刻停止產製並保留失敗證據。未來如使用者變更開始門檻，記新決定；本規劃不自行放寬。報告 logical／allocated 本次新增用量，和全碟 free 差分分開，不能把共享磁碟差分全歸因本任務。

## 4. 待核定與交付門檻

1. 使用者選2台或3台，核定新 source/run 設計、兩個request scope、phase／window可行性與不改D65；選配REF的隔離明確化。
2. 另開靜態可行性：固定新 source、catalog／K／pose、支撐面、短遮擋區、6m折線盲區、兩台出口與入口、圖／tracking scope hashes；Claude獨立複核，未核定用途保留DRAFT／UNKNOWN。
3. #248／#244 契約與評分規則獲核定後再宣告工程比較條件。人工visible/bbox標註獨立於推論，固定分母再看recall／誤接。
4. **另有明確 render／inference 授權、fresh disk gate 與不覆寫新輸出檢查後**才產製。source/run/clock/hash/model/params pins、raw候選及完整錄製留LOCAL；GitHub只收code/docs/tests與curated receipts。
5. 未來結果分開報detector無person、低分、geometry拒收、歧義、RETURN／SWITCH、真正盲區；identity始終UNCONFIRMED、physical traversal/collision UNKNOWN。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 本次F2規劃Draft（head見PR）；沒有scene／render commit。
- Files changed: 只新增本文。
- Commands run and results: Python標準算術重算300／450格、RGB／未壓縮／forward與敏感度表；內容一致性／來源pin檢查；`git diff --check`由提交端執行。
- Artifacts: 本文SHA-256見PR；新`.blend`／catalog／RGB／index／recording **NONE**。
- Verified: 規劃格數與預算算術、render／forward分離、現行6輪參數與名義SEARCHING相位判讀、兩個session的phase／window可行性仍UNKNOWN、D90-3的禁止渲染與保留現有資產邊界。
- Not verified: 新場景幾何／相機投影／遮擋／實際可見性／路線／render時間／壓縮率／磁碟峰值／偵測品質／controller實際輪數／entry與評分；未跑Blender、推論、browser或實驗。
- Deviations, UNKNOWN items and follow-ups: render耗時缺係數，提供假設敏感度而不偽報實測；本文件只是可審查規劃，後續施工與render都需對應授權。

來源：#261 `d6e22e60eb56cc5ccd863e4f73e595d82f4b0e7b` 情境卡bytes SHA-256 `131fcbcde58899101880e3c968cd18b8fa65c96aa19c049b953b9dd36ec12a82`；#256 `dd0e69bb7775789eaa94436ead1726dfb2d13823` 可行性報告bytes SHA-256 `82719479cc33e9d2b825ed37ccf7b4df1999a8aaa2dbba1ed6111183f444e192`。這兩份只提供規劃約束與歷史係數，沒有給本小場景可行性或render授權。

輪數判讀來源固定 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`：`src/amidst/q1q5/q5_controller.py` bytes SHA-256 `7e42cfab8365520bd835f169c945f6eea71f1398e35fda264ddb6732fd312a2a`（`_search`、`_guard_observations`、RETURN重試），`configs/q1q5/parameter_set_v1.json` bytes SHA-256 `960d823c17c181c6b0b128a3cc7f39fb0d5f7af19828073b884d74aa8336ee6e`（6輪、1s重試、600ms gap）。本次只讀程式與設定；沒有執行controller或讀取計畫以外的actor軌跡。
