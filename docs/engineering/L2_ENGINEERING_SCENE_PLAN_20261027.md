# L2-6 工程小場景規劃（2026-10-27）

F2／[#249](https://github.com/Polalalabear/amidst/issues/249)。**PLANNING_ONLY／PROPOSED；沒有建場景、複製資產、渲染或推論。** D90-3 已決定延後 L2-6 渲染；本文件不構成產製授權。Line 1 的 r004／A4-1／B4-1、圖 v3／G4、D79、既有題目與錄製不改。

## 1. 最小場景與鏡頭

建議先用 **2 台、33 s、5 fps、960×540** 的獨立工程 source/run；第 3 台只作另外明示的診斷選項。只要兩台能實現指定盲區，不為了湊鏡頭數增加第三台。此為新場景版本提案，不能沿用 r004 catalog／calibration／graph pin；版本名與 source path 待核定，尚未建立任何 `.blend`。

| 元素 | 設計規格 | 用途／限制 |
| --- | --- | --- |
| L 型走廊 | 兩段各約 8 m、寬 2.4 m，一個 90° 轉角；平地且尺度明確 | 單一受控幾何，方便靜態投影；實際通行／碰撞仍 UNKNOWN |
| CAM_L2_A | 第一段走廊，約高 2.5 m，固定 pinhole；HFOV 70°–75° 待靜態投影定案 | seed、兩次短暫失聯、回接；目標在主測試區內維持全身，另設邊界測試區 |
| CAM_L2_B | 第二段走廊，約高 2.5 m，固定 pinhole；HFOV 70°–75° 待靜態投影定案 | 轉角後接手，先有正常全身觀測，再測部分畫面邊界截斷 |
| 靜態短遮擋板 | 第一段走廊的畫面側遮擋；名義可見性缺口路程 1.2 m | 以計畫速度 1 m/s 對應 1.2 s；板不得放在名義行走帶中，須靜態幾何複核，不能先假定沒有碰撞 |
| 轉角盲區 | 名義路徑由 (-3,0) → (0,0) → (0,3)，共 6 m | 1 m/s 約 6 s；需 static frustum／遮擋幾何證明出口與入口設計成立。不能拿直線 √18 m／速度取代折線路長 |
| CAM_L2_REF（選配） | 高位固定參考鏡頭，可看到轉角 | 只作 LOCAL 視覺診斷，**不進 A/B 主 tracking scope、Q1/Q4/Q5 evidence 或 ranking**。若要納入產品，另註冊 camera set／run 與圖、重新凍結 |

**鏡頭內遮擋的定義：**本規劃只保留為不計分的工程診斷（IN_CAMERA_OCCLUSION_DIAGNOSTIC，非評分器enum），指目標未經出口footprint而因板遮擋暫失。實際候選依最後bbox及圖決定，可能RETURN／SWITCH；不預定為正式RETURN或NO_SWITCH，避免與#261第二批NO_SWITCH定義衝突。正式事件型別交#244／#248統一後才設計評分。1.2s仍可量測重複失配與重新取得，不因此充當正式事件。

世界座標只是規劃座標，不是已匯出的 source geometry。角色外觀／身高／材質用新工程設定明示；任何既有 immutable actor asset 的使用方式都要在產製授權中列清，不覆寫、移動或複製原資產。先固定背景／鏡頭／ROI，之後才產事件，不能看事件偵測結果後重畫出口來迎合分數。

## 2. 約 33 s 的計畫流程

以下時刻是規劃值，**不是 GT／實測 visibility，也不進 inference**。真正 `t_L`／`t_X`／`t_N`、可見區與 sampled RGB 必須在凍結設計後另行驗證。

| 計畫時間 (s) | 段落 | 工程目標 |
| --- | --- | --- |
| 0.0–3.0 | CAM_L2_A 正常全身觀測，顯式選 seed | 固定 detector／score／bbox 基準 |
| 3.0–4.2 | 靜態遮擋板後穿行，計畫暫失 1.2 s | 不計分的鏡頭內遮擋診斷，記實際RETURN／新segment，不能預定動作 |
| 4.2–6.2 | 同鏡頭重現 2.0 s | 10 格名義可見樣本；2.0 s 大於 v2 卡的 1.4 s 間隔要求 |
| 6.2–7.4 | 沿同一遮擋板再穿行，暫失 1.2 s | 反覆暫失；不以人工 mask index 製造假漏檢 |
| 7.4–13.0 | CAM_L2_A 正常可見並走向轉角出口 | 供第二個 session 明確選 seed，記原始觀測 |
| 13.0–19.0 | L 型名義路徑 6 m、1 m/s，計畫 A/B 都看不到 | 計畫 SWITCH 空檔6s >5.2s，歸 Line 2 `LONG_GAP`；產品仍無 LOST enum／timeout |
| 19.0–23.0 | CAM_L2_B 入口後正常全身 | 選定 evidence 後接手，對照正常 bbox／score |
| 23.0–28.0 | 在 B 的邊界測試帶移動，計畫部分截斷 | F1 IoU／形狀變化診斷；不是預先保證 detector 失敗 |
| 28.0–33.0 | 回到 B 的正常觀測帶，停留至結束 | 量測恢復、保留顯式 UNKNOWN／GAP |

**一個 source run、兩個明確工程 request／session（提案）**：S1 `[0,10.6)` s 只查兩次短暫失聯；S2 `[10,33)` s 明確以 A 的觀測為 seed，查長盲區接手與 B 邊界段。同一 RGB/index 可重用，不因兩個 request 多渲染一份。分開session只為分離診斷範圍。S6算術：S1最後計畫重現7.4 s，參考窗終點8.4 s，10.6≥8.4+2；S2首個離開錨點13.0≥10+3。重疊[10,10.6)只有正常觀測／seed，不放事件錨點。這是規劃條件，實際完整性UNKNOWN。現行參數是 `session_max_research_rounds=6`、`research_interval_us=1000000`；第6次 SEARCHING 可執行，第7次之前結束。v2 情境卡的每場次4次是設計稿保留餘裕的規劃值，不能當產品上限。

S2名義相位依#266 C1／C2：假設5fps、first missing `t_fm=13.0 s`、最後觀測12.8 s，
L=0.6 s、Δ=0.2 s，首次SEARCHING `D0=t_fm+L−Δ=13.4 s`；首窗從first missing起為[13.0,19.0)，
19.0 s的目的觀測在半開右端，不含於首窗。若未重新取得，第二次在14.4 s、窗[14.4,20.4)，
已涵蓋19.0 s目的入口。名義需要2次搜尋，遠低於6輪，不需等第6次；第6次仍可做完、第7次開始前終止。
若first missing相位不同或實際提早漏檢，搜尋數會改變；合法圖／出口、guard、score／color與coverage仍UNKNOWN，
所以「2次」是此明示假設的算術，非產品實跑保證。不能用延後decision一格來配卡片舊相位。

依[D94](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434821818)，Line2 STANDARD RETURN只收
`d≤L+R=1.6 s`，adapter拒絕1.6<d<1.8 s；1.8 s分類界線不動，Line1不回寫。
本規劃兩段1.2 s短遮擋滿足數值界線，但目前只作不計分診斷，不能宣稱正式RETURN通過。
其他LONG_LOSS／LOST_TAIL沒有設計進這33 s，是否新增仍由使用者決定；不暗改參數、退款輪數或把人工mid-gap重選當自動接手。
正式評分型別／窗由#244 owner提案與使用者核定；本次不代定正解。

參考 v2 設計稿的 `LONG_GAP` 分類與反覆 RETURN 範圍，並不表示設計稿已核定。視野重疊若存在，依 D90-2 要先失聯、進入 SEARCHING，才可接手；不做提早切鏡。若靜態投影無法實現短遮擋與6m盲區，此排程標 UNKNOWN 並先修設計，不開渲染試誤。

## 3. 格數、磁碟與時間估算

歷史係數只作容量／forward 預算：RGB `63,976 KiB／150 格`、CPU detector forward `1.108406209 s／格`，出自 [r004 提案 §5](R004_SCENE_CHANGE_PROPOSAL.md)，沿用 [#261 v2 情境卡 §3](https://github.com/Polalalabear/amidst/pull/261)。**1.1084 s 是 detector inference，不是 Blender render 時間。** 新場景每格壓縮率、真 render seconds/frame、完整索引 throughput、source／texture 體積與峰值目前 UNKNOWN。

| 項目 | 2 台（建議） | 3 台（選配） |
| --- | ---: | ---: |
| RGB 格數 N = cameras ×33×5 | 330 | 495 |
| 歷史壓縮係數估 RGB | 0.1342 GiB | 0.2013 GiB |
| 如 RGB 同時有一次完整打包副本 | 0.2685 GiB | 0.4027 GiB |
| 全部 RGB 同時保留未壓縮 8-bit RGB（不建議） | 0.4780 GiB | 0.7170 GiB |
| 歷史 detector forward 估計 | 6.096 min | 9.144 min |
| 原始 top-300 JSONL 預留（假設每候選1 KiB） | 約0.0944 GiB 的假設值 | 約0.1416 GiB 的假設值 |

top-300 的1 KiB是**工作預算假設、不是量測上界**；編碼 bytes、其他 metadata 及模型 RSS 需分開量測。REF 若純視覺診斷，不應多做 detector；上表3台 forward是全部推論的保守比較值，兩台產品索引仍330格。

渲染估算公式是 `T_render_minutes ≈ N × r / 60 + setup_minutes`，其中 `r` 為未量測的每格渲染秒數。以下只是**明示假設的敏感度表**，提供使用者排程，不是本機速度或承諾：

| 假設 r（s/格） | 2 台330格 | 3 台495格 |
| ---: | ---: | ---: |
| 1 | 5.5 min＋setup | 8.25 min＋setup |
| 5 | 27.5 min＋setup | 41.25 min＋setup |
| 10 | 55 min＋setup | 82.5 min＋setup |

沒有可信的歷史 render 係數時，正式申請須將 render ETA 標 **UNKNOWN**；經另行授權後先量測限定幾格、同一 engine／resolution／settings，再用中位數與慢格值分別估全批。該量測本身是 render，也受授權與 disk gate；這次沒有啟動。

建議為新 source／RGB／index／raw audit／一次打包與暫存設 **2 GiB 軟預算**，並逐項量測；不是宣稱已量到2GiB。維持原模型與素材單份，不另建 venv／worktree、不複製大資產；zip 若造成超額先停止再回報。D90-3 的三個現有 `.local-worktrees` 與服務不動。

開工前的磁碟條件不能只看「現在13GiB」的舊快照：先取得 `df -k` 精確 available bytes。至少保留8GiB停止線，且本計畫保守保留既有 D41 的 **開始時 ≥12GiB**；另須滿足預算後 free≥8GiB。逐格或每小批檢查，低於8GiB立刻停止產製並保留失敗證據。未來如使用者變更開始門檻，記新決定；本規劃不自行放寬。報告 logical／allocated 本次新增用量，和全碟 free 差分分開，不能把共享磁碟差分全歸因本任務。

## 4. 待核定與交付門檻

1. 使用者選2台或3台，核定新 source/run 設計、兩個request scope、phase／window可行性與不改D65；選配REF的隔離明確化。
2. 另開靜態可行性：固定新 source、catalog／K／pose、支撐面、短遮擋區、6m折線盲區、兩台出口與入口、圖／tracking scope hashes；Claude獨立複核，未核定用途保留DRAFT／UNKNOWN。
3. #248／#244 契約與評分規則獲核定後再宣告工程比較條件。人工visible/bbox標註獨立於推論，固定分母再看recall／誤接。
4. **另有明確 render／inference 授權、fresh disk gate 與不覆寫新輸出檢查後**才產製。source/run/clock/hash/model/params pins、raw候選及完整錄製留LOCAL；GitHub只收code/docs/tests與curated receipts。
5. 未來結果分開報detector無person、低分、geometry拒收、歧義、RETURN／SWITCH、真正盲區；identity始終UNCONFIRMED、physical traversal/collision UNKNOWN。

## CQ-11修訂的驗證界線

只做文件／算術重算，沒有新場景、asset副本、RGB、index或錄製。格數330／495與資源表依原歷史係數重算，
不是新量測或渲染申請。33 s排程的S6、名義兩次搜尋與D94僅規劃檢查；實際幾何／遮擋／模型／runtime／G4仍UNKNOWN。
不新增程式或測試；沒有跑pytest、renderer或推論。Actual output與檔案hash留在PR／議題。

來源：#261 `d6e22e60eb56cc5ccd863e4f73e595d82f4b0e7b` 情境卡bytes SHA-256 `131fcbcde58899101880e3c968cd18b8fa65c96aa19c049b953b9dd36ec12a82`；#256 `dd0e69bb7775789eaa94436ead1726dfb2d13823` 可行性報告bytes SHA-256 `82719479cc33e9d2b825ed37ccf7b4df1999a8aaa2dbba1ed6111183f444e192`。這兩份只提供規劃約束與歷史係數，沒有給本小場景可行性或render授權。

輪數判讀來源固定 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`：`src/amidst/q1q5/q5_controller.py` bytes SHA-256 `7e42cfab8365520bd835f169c945f6eea71f1398e35fda264ddb6732fd312a2a`（`_search`、`_guard_observations`、RETURN重試），`configs/q1q5/parameter_set_v1.json` bytes SHA-256 `960d823c17c181c6b0b128a3cc7f39fb0d5f7af19828073b884d74aa8336ee6e`（6輪、1s重試、600ms gap）。本次只讀程式與設定；沒有執行controller或讀取計畫以外的actor軌跡。
