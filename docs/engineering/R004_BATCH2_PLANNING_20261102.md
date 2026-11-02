# r004 第二批候選規格與靜態證據邊界（#343）

本稿展開 #261 §4 的 B2-1～B2-5，全部保持 **PROPOSED／未選定**。目標是讓使用者能決定第二批範圍；不建立新 scene、camera ID、transition ID、authority、runtime schema 或參數組。五張卡目前均不可凍結或渲染，allowed_purposes 皆為空。原始 Blender、影片、GT、formal／clean 包未讀、未複製、未改動，沒有模型或渲染執行。

前置 #323 已交付；本輪fetch讀取 #261@b5302a0 的D105回修差異（RR分兩request、U6／U7定案），第二批§4清單未變。本稿改釘最新head；此增量尚未經Claude複審。本稿不改該文件，也不把它合進 feature 分支（#261 是 mainline 直合）。第一批的舊「待決」文字，依 #93 D105-4／#258@0b6e800 的定案表解讀，不能回復成早期建議值。

## 固定來源與可重算範圍

| 來源 | 固定 commit | bytes SHA-256 |
| --- | --- | --- |
| #261 `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md` §4 | b5302a0ad9a1895d728946d824854b6001b6b66a | 02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b |
| #258 `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md`（PROPOSED；含 D105-4 定案對照） | 0b6e8004b3a9ae03ce5184466498dc22b727f8c4 | 0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c |
| #271 `docs/engineering/R004_L2_STATIC_FEASIBILITY_20261027.json` | c5aa674ce772b7f49e813c89ab6fa415064e22ca | ecf1ce4615da7faf6a908e1a98ec329ac62814b9f162af60b6085f945f1baeab |

本輪在使用者提供locator後，先核對兩個safe_static檔的hash，再唯讀重跑限定的inventory／bounds／CORNER視錐檢查；與#271固定報告相互核對。未重跑#271的全部九條路線，也未採用舊卡片輸入。來源記為 **<LOCAL r004 safe_static>**，不在GitHub記錄絕對路徑。輸入 pins：`safe_static/cameras.json`＝`3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；`safe_static/static_geometry.PROPOSED.json`＝`bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a`。匯出內記載 source pin＝`466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`，本輪沒有另讀原 scene 來核對。

直接靜態重跑 **已完成**：8台校正（全為NOT_EVALUATED）、43個mesh物件、5個screen候選；兩檔前後hash一致，兩次輸出bytes完全相同。geometry自身仍為DRAFT、allowed_purposes=[]。既有投影、支撐與視錐都不能證明遮擋、完整人體可見、實際漏檢、碰撞或物理通行。本輪由WALK_CORNER實際bbox取四角、0/0.85/1.7m垂直軸並驗兩台相機的六個半空間，四角全入框；25×25均勻網格共視625、單獨區0／0，與#271一致。這是凸視錐對bbox的結論，未證明連續支撐面或遮擋，因此不能推出獨有出口或有效切鏡邊。

| 本輪safe_static inventory | xyz bounds（m，顯示四捨五入） | 只可用來說明 |
| --- | --- | --- |
| WALK_VEST_W | x[-3.2,4.88]、y[-2,2.4]、z=0 | B2-1有PROPOSED支撐mesh；新鏡頭姿態／涵蓋仍缺 |
| WALK_CORR_N | x[15,17.4]、y[2.4,12]、z=0 | B2-2北段支撐候選存在，不等於路線或用途獲准 |
| WALK_R102 | x[17.4,22.4]、y[7,11]、z=0 | R102被匯出不代表可擴大demo範圍 |
| OBSTACLE_SCREEN_W | x[10.4,10.55]、y[0,0.8]、z[0,3.2] | B2-3可供後續選路的靜態候選；未驗遮擋時長 |

另外有SCREEN_CORNER_N／N／R102／W_HOOD共五個screen；存在mesh只解除了「是否有候選物件」的未知，沒有解除其遮擋適用性。完整雙精度bbox在伴隨JSON。

## 五個候選

| 候選 | 要檢驗的工程行為 | 最小計畫輸入 | 靜態可行性與仍缺證據 |
| --- | --- | --- | --- |
| B2-1 門廳補盲鏡頭 | 與既有 LG 路線對照，檢查加入 VEST_W 觀測後能否分成兩段有界 BLIND | 由使用者選定的新鏡頭姿態、內參、source/scene pin；唯一無人物計畫折線；每段出口／入口 patch | 現有 safe_static 沒有這個新鏡頭的核定校正。兩段距離、投影與 gap 均 UNKNOWN；不能將 7.4s 平分或用視錐重疊代替可見性 |
| B2-2 CORR_N 北段／R102 | 延伸已註冊鏡頭的追蹤範圍，檢查新方向與候選競爭 | 先選「只到北段」或「包括 R102」；新路線座標、完整 catalog 與逐方向 patch | #261 明列 E_CORNER_N／E_PORTAL_R102 沒有對應轉移；現有 CORNER 共視也不是新增邊的證據。R102 用途仍須另核，支撐、路徑、全身／遮擋皆 UNKNOWN |
| B2-3 短暫遮擋型 NO_SWITCH | 同一鏡頭內短暫失去觀測後恢復，完整覆蓋範圍內沒有錯誤 SWITCH | 固定鏡頭、已選定遮擋物／路線與 0<計畫遮擋≤0.4s；不預設 identity 已確認 | 5個screen mesh已核存在，其中SCREEN_W位於走廊南側；選定路線與遮擋適用性仍UNKNOWN，靜態物件不證明人體遮擋。5fps、Δ=0.2s 的相位與真正漏檢不同，不能由0.4s保證一定進 SEARCHING 或 RETURN |
| B2-4 超過 G_max 長空檔 | 診斷 session 上限與未執行後綴，避免把缺覆蓋寫成成功 | 明列 gap、每次新 request 的 seed、已有輪數、實際 ENDED cutoff；使用者另選 LIMIT 範圍／評分 | g>10.6s 要至少第7次搜尋，超過 session6輪；D105 的計畫預算≤4更早擋住（單一事件最大8.6s）。U-D4仍 PENDING；沒有合法正式計分／凍結路徑 |
| B2-5 多人干擾 | 固定追蹤對象路線與核定參數下，觀察非目的候選鏡頭干擾者造成的既有Q5結果 | 兩條分開的計畫路線、干擾者位置／顏色來源、run/clock/source綁定；與無干擾對照同參數 | 非目的候選鏡頭中的可見時間與空間間隔 UNKNOWN；靜態支撐點不保證不遮擋、不相撞或不誤配。不能用 renderer actor ID 或計畫標籤供推論辨識 |

每張卡的 run ID、query 範圍、OBSERVATION seed、clock/hash、實際最後／首次觀測時刻均為 **MISSING／UNKNOWN**，沒有虛構絕對時刻或產品輸入。路線選定後才可推導計畫時刻；觀測、投影與推論要各自留 provenance。

## #258 規則與圖／G4 依賴

| 候選 | #258 依賴 | 圖／G4 依賴與預設 |
| --- | --- | --- |
| B2-1 | §1搜尋相位與預算、§2.2 LOST分類、§2.3逐鏡頭窗、U-D5／6／9／10與UK-8；若出現重疊另受§2.4／D93 | E_OUT_VEST、E_VEST_CORR只能當既有拓樸名稱；新鏡頭逐方向transition／patch尚無ID。v4擴充或其他版本由權威擁有者另定，不能自行註冊。逐邊G4與用途未生效前不供runtime |
| B2-2 | §2.3、§2.5；重疊必須有§2.4的權威證據介面 | E_CORNER_N、E_PORTAL_R102所需轉移與範圍都MISSING；不能用W1↔W2、BRANCH↔WIDE草案替代。所有新邊用途保持空集合 |
| B2-3 | §2.1／§2.2的既有STANDARD NO_SWITCH與實際覆蓋檢查；D94 RETURN分類只在真的產生RETURN事件時適用 | 不新增切鏡邊，仍需原scope／run的有效來源與用途；無切鏡不等於豁免scope。沒有提出新NO_SWITCH計分方式 |
| B2-4 | §1.1的G_max、§2.5預算、§2.6 LIMIT／prefix；U-D4 PENDING優先fail closed | 沿用路線邊也須逐scope有效；不能延長N_max、重設同session計數、用padding補覆蓋或把B2-1改題稱B2-4已完成 |
| B2-5 | 沿所選單人卡的§2.2～§2.5；既有候選排序／earliest legal guard保持原樣 | 所有目標與干擾路線各自需要用途／G4；圖v4重疊競爭須核P-OV條件。任何偵測參數變更另等#345／U15，Line1不動 |

G4選定副本不是有效核准；依D112仍要使用者checkpoint引用與決策生效紀錄。本稿不設定G4有效、不填新authority、不擴充allowed_purposes。PROPOSED規則也不由本稿採納。

## 需要誰決定

這是下一輪選項清單，目前全部未選，不代表本次要求立即渲染。由**使用者**決定展示範圍／新場景與授權，由**Claude協調者**固定契約／圖版本與來源pins，Codex才在被選範圍做後續靜態檢查。

| 候選 | 選項A（推薦） | 選項B | 選項C |
| --- | --- | --- | --- |
| B2-1 | 暫緩，先保留LG作對照，等新鏡頭校正與範圍核定 | 核准只做新鏡頭靜態設計，姿態與FOV由使用者選定；不含render | — |
| B2-2 | 先選CORR_N北段規格，R102保留排除；仍等新邊／校正 | 將R102納入規格提案，另核用途、來源與新路線；不自動允許渲染 | 全部延後，避免與第一批範圍混淆 |
| B2-3 | 待既有safe_static有足夠遮擋物／路線證據再選卡 | 選新場景遮擋物的純靜態設計；實際短暫失聯仍等影像證據 | — |
| B2-4 | 暫緩；U-D4未核且超預算，不列可評／可凍結候選 | 另提ENGINEERING上限診斷；明列計畫預算衝突與未覆蓋後綴，另核prefix證據介面／政策；選E2本身仍不足以解除全部gate | 改做B2-1補盲對照，承認問題已改為兩段有界gap，不稱超上限卡成功 |
| B2-5 | 先有單人凍結輸出與完整比較，再選干擾者路線 | 先核兩人靜態站位／路線設計，維持既有參數；不含render或調參 | — |

## 重算與後續驗收

隨附 `scripts/report_r004_batch2_planning.py` 只讀三份固定Git文件，核bytes pins、摘錄safe_static衍生報告，重算整數微秒上界，產診斷JSON。沒有讀劇本時刻去驅動推論，也不改產品設定。依#258：

`n_r_max(g)=0`（g≤5.2s）；否則`max(1, ceil((g−6.6s)/1s)+1)`；`n_s=n_r_max+1`。

| 計畫gap | 搜尋上界 | 判讀 |
| --- | ---: | --- |
| 5.2s | 1 | 分類端點 |
| 6.6s | 2 | 不把RETURN的同數值端點混入SWITCH公式 |
| 8.6s | 4 | D105計畫預算的單事件端點，沒有其他事件時 |
| 10.6s | 6 | session上限的端點，已超本輪計畫預算 |
| 10.8s | 7 | 超session上限；不能當可凍結LONG_GAP |

```bash
python3 scripts/report_r004_batch2_planning.py --static-root "<LOCAL r004 safe_static>" --output /tmp/batch2-fresh.json
cmp /tmp/batch2-fresh.json docs/engineering/R004_BATCH2_PLANNING_20261102.json
```

`<LOCAL r004 safe_static>`須由操作者代入本機來源。腳本先核pins再解析，重算inventory／bbox／CORNER投影，結束再核hash；不把絕對locator寫進收據。省略static-root時明記NOT_RUN，不能拿省略參數的報告代替本次有輸入的結果。只檢查兩份safe_static，不執行mesh遮擋／collision／新鏡頭設計，也不讀#271腳本要求的舊卡片。

本輪direct-static限定檢查已完成；候選新幾何／遮擋、run／scope／index、正式評分與實機結果仍NOT_RUN，原因是上表尚未選定的輸入／使用者gate。後續被選卡才固定camera／source／run／clock／parameter hashes與request，再做相應驗收；渲染、資料生產、發包仍照原授權關卡。#344仍等yyin Y0，#345仍等U15／完整比較。本稿沒有驗收這兩項。
