# r004 Line 2 靜態可行性複核（E2，2026-10-27）

**PLANNING_ONLY，未核定、未渲染。** 回答 #261 情境卡 v2 §5 V1–V10。使用者本次派工授權核定前先做靜態檢查；不把設計稿中的「等核定後」當作另一次授權要求。Line 1、圖 v3、G4、D89、#222、原卡 bytes 均未改。

結論：可提出符合支撐面的計畫折線，部分 footprint 時刻可在 ±0.5 s 內調整；**不能據此判任何卡的真實失聯／遮擋已可行**。尤其 EXT_CAR 沿門廳折線始終在視錐內；CORNER 整塊支撐面都在 BRANCH/WIDE 的視錐內，V2-OV2 沒有「只靠 FOV 離框」的獨有區。遮擋與全身可見性仍 UNKNOWN。

## 1. 證據與重現

基底 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`；卡片 #261 `d6e22e60eb56cc5ccd863e4f73e595d82f4b0e7b`；A1 方法 #256 `dd0e69bb7775789eaa94436ead1726dfb2d13823`。本次只讀下表七份檔案。LOCAL static root 由操作者設定；原 `.blend` 不開、不複製、不 hash，不宣稱重驗原 source bytes。靜態匯出內的 source pin 為 `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`。

| 輸入 | SHA-256 |
| --- | --- |
| LOCAL `safe_static/cameras.json` | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| LOCAL `safe_static/static_geometry.PROPOSED.json` | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| `static_patches_v3.json` | `17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151` |
| `region_graph_v3.json` | `717772600caaa51d88b55f62d118bbef2d3f10514ebffeabd41081e801a45ae0` |
| `camera_graph_v3.json` | `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e` |
| `tracking_scope_v3.json` | `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a` |
| #261 `R004_COMPLEX_SCENARIO_CARDS_V2.md` | `131fcbcde58899101880e3c968cd18b8fa65c96aa19c049b953b9dd36ec12a82` |

所有檔案執行前後 hash 相同。8 台 `static_validity=NOT_EVALUATED`。不讀 RGB、GT、renderer 軌跡、visibility、depth、keyframe，也不讀任何 actor 路線／時序檔。以下座標是本次新提出的**無人物、無絕對時刻計畫折線**，未凍結、未執行，不是 renderer 軌跡；只存在於這份工程審查收據，不是 runtime 輸入。

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python "$EXISTING_PYTHON" python scripts/check_r004_l2_static_feasibility.py \
  --static-root "$LOCAL_STATIC_ROOT" --graph-root configs/q1q5/graphs/r004 \
  --cards "$PINNED_CARDS_V2" --output "$NEW_RECEIPT_JSON"
```

`PINNED_CARDS_V2` 須是上表 #261 bytes；輸出須不存在。Python 不安裝新依賴。腳本只投影 pin 過的 calibration、計算折線弧長與 rectangle 首次進入；沿水平段每 2 cm 查支撐 cell。外部地板到室內 6 cm 高差單獨保留，不宣稱可跨越或 collision-free。全部 9 條折線水平支撐抽查失敗 0；這不是連續碰撞驗證。

## 2. 計畫路線與時刻（V2–V4）

座標詳見同名 JSON `route_audits`。時刻是自各折線起點起算、1.2 m/s；不是實際最後看見／首次看見時刻。戶外折線經西入口中心 `(-3.2,0)`，保留 6 cm 地板階差，避免直接用穿過邊界的最短直線當路線。

| 計畫折線 | 長度 m | 時間 s | 對卡片的影響 |
| --- | ---: | ---: | --- |
| EXT_CAR SOUTH 出口邊 `(-6.2,-4.1)` → 西門 → W1 入口邊 `(0.35,1.1)` | 8.856872 | 7.380726 | LG `t_X=5` → footprint `t_N=12.380726`；可提 12.4（+0.4）；A4-2 c1 可提 19.4（+0.4）。仍在 5.2 < g ≤ 7.8，但只對這條計畫成立 |
| NORTH 出口邊 `(-10,-0.9)` → 西門 → W1 | 10.635817 | 8.863181 | 9.0 s 變體只是時間上足夠；其重搜預算風險不消失 |
| EXT_CLEAR 出口邊 `(-3.35,0.4)` → 西門 → W1 | 4.203717 | 3.503098 | A4-2 c2 原 3.5 s 接近此候選，可提 3.6 或 3.7；全局時序仍待卡片作者重排 |
| W1 → 西門 → SOUTH（上一條 SOUTH 路線反向） | 8.856872 | CLEAR 首次進入 3.358779；CAR 7.380726 | PE2 可提 CLEAR `t_N=9.4`、CAR `13.4`（原 9.5／13.0，均在 ±0.5）；A4-2 e 為 47.4／51.4。兩台相差約 4.02 s，並非卡片假設 3.5 s |
| W2 出口邊 `(11.4,1.15)` → BRANCH 首次進入 `(15,1.4)` → WIDE 首次進入 `(15.5,1.4)` | 4.108670 | BRANCH 3.007225；WIDE 3.423892 | B4-2 b：BRANCH 14.1／WIDE 14.5 s；b2：BRANCH 70.1／WIDE 70.5 s（同一折線，向上取0.1 s）；共用3.5 s不能當兩台真實進入時刻 |
| BRANCH → 南側折返點 `(13.9,0.2)` → 穿過 W1 入口 → W2 | 5.120680 | W1 2.814902；W2 4.267233 | **本條候選**是 W1 先到；PE1 依往上取0.1 s規則可提 W1 8.9／W2 10.3（原 9.0／10.1）；B4-2 d 可提 24.4／25.8。入口差 1.452331 s，非 1.1 s |
| R101 出口邊 `(8,-0.1)` → W2 `(8,0.1)` → W1 `(7.9,0.6)` | 0.709902 | W2 0.166667；W1 0.591585 | B4-f 不能把這兩個 footprint 當同一 t_N。原 1.5 s 若保留，須另定較長動線／停留；本次不替卡片填值 |

南側折返至(13.9,0.2)沒有獨立證據是必要路線，只是本次候選假設，不是最短路／已選劇本；由卡片作者選定路線後才能固定入口時刻。另一條較直接路線尚未核對支撐，本次不採用或重算。

V3 的先後不是場景唯一答案：走廊入口是相隔的矩形，路線可繞過其中一台。上表回走廊的折線是新增的明示候選，不是從卡片推回的唯一「實際路線」；W1 入口內約 0.295 s 的通過也只有 1–2 格餘裕，不能保證 detector 有有效觀測。不能把「入口間最短距離 ÷ 速度」直接當兩台首次進入差。

**V2、V4 的實際可見性：UNKNOWN（雙向皆同）：**SOUTH→W1 的整條折線，以及反向 W1→SOUTH，EXT_CAR 的 0／0.85／1.7 m 垂直軸都在相機視錐內；CLEAR 也能在到達其 footprint 前投影入框。這些僅是in-frustum結果，不能證實早可見，也不能證明出口後已失聯／入口前不可見；雙向均無遮擋證據。牆／車／門的實際遮擋與整個人體輪廓未驗證，`t_L−t_X`、`t_V−t_N` 均 UNKNOWN；不能用上表通過時間宣稱 LONG_GAP、BLIND 進入窗或 P-OV2 已通過。

B4-e（包含B4-2 e）與B4-f同有門檻時刻問題：W1／W2出口到R101_IN入口footprint間距0.7／0.2 m，1.2 m/s僅0.583333／0.166667 s。卡片g=2 s隱含約1.4–1.8 s門檻停留且不被看到，但V1遮擋UNKNOWN；直接過門不能保證進入窗。名義決策約31.8 s早於B4-2 e進入窗[32.4,34.0)，僅是卡片相位推算，非runtime實測；Line1不在此改動。

## 3. 逐題回答 V1–V10

| 題 | 判定 | 已知數字與尚缺證據 |
| --- | --- | --- |
| V1 門檻／深處 | **UNKNOWN** | `(8,-1,0)` 在 R101 支撐面、W1 垂直軸仍在 frustum；無法證明 1 m 內側遮擋。門口到深處 `(8,-4)` 有 3.9 m 支撐折線，1.2 m/s 為 3.25 s，collision／用途核准仍 UNKNOWN。走進約 1 m 再退出至少 2 m／1.2=1.667 s；RR 的 1.2 s 只能容納深度 ≤0.72 m（零停留）。不能同時承諾「深入1 m」與原 RR 時刻 |
| V2 長盲區 | **UNKNOWN；計畫長度已算** | SOUTH 8.856872 m／7.380726 s；可在 +0.4 s 內修 footprint 時刻。真正失聯並未由 footprint 定義，見 §2 |
| V3 分鏡頭進入 | **條件式計畫可行；可見性 UNKNOWN** | 明示折線為 W1 2.814902 → W2 4.267233；B4-f 明示折線反為 W2 0.166667 → W1 0.591585。沒有唯一全場景先後 |
| V4 出門 | **UNKNOWN；反向路線已算** | W1→CLEAR 3.358779 s、→CAR 7.380726 s；frustum投影只表示不能排除入框；實際早可見與t_V均UNKNOWN，不能當已證實風險 |
| V5 獨有區／v4 出口 | **EXT、W1/W2 有 frustum 候選；OV2 無 FOV-only 解** | 詳見 §4。BRANCH/WIDE 的整塊 CORNER 15–17.4 × 0–2.4 m 都在兩個視錐內；需要遮擋證據或改場景／卡片才能證明獨有區。v4 的 BRANCH/WIDE 邊界保持 MISSING，不畫假 ROI |
| V6 P-OV3 | **UNKNOWN** | 無凍結坐標／時序與完整遮擋證據，不能核過指定時間窗。W1 對 CORNER 靜態 probe `(16.2,1.85,0)` 投影仍在 frustum，OV2 排除 W1 需靠遮擋；PE1 折線在 BRANCH 失聯後 WIDE 垂直軸仍入框，若無遮擋就不能用 v4 滿足 P-OV3。OV1-b 若只用候選室外獨有點，W1 軸可在 frustum 外，但還須先凍結整段路線；不聲稱指定7秒窗通過 |
| V7 R101 視野外角落 | **有靜態 frustum 外支撐點；可達性 UNKNOWN** | `(5.2,-4.8,0)` 在支撐面，R101_IN 腳點投影約 `(-500.82,608.50)`，在框外；從 `(8,-0.5)` 有 5.131277 m 支撐折線。全身、門／牆碰撞、往返時長與用途未驗證 |
| V8 分場次 seed／預算 | **介面支援，實際 seed MISSING** | staging `q5_controller.py` 的 OBSERVATION seed 精確引用 observation_id；同區多鏡頭可指定其中一筆。`api._controller` 每次新建 controller，建構時 `searching_index=0`，各場次新 request 不共用輪數；不是在同一 session 裡換 seed 後假裝重設。未渲染／未產 index，S2/S3 真實 observation_id 尚不存在 |
| V9 用量 | **可估算；r004 實測 MISSING** | 11 卡逐卡 frames／GiB／分鐘已機械重算於 JSON；甲 2,150 格、0.874509 GiB、39.717889 min。係數仍為舊 A RGB／forward，並非 r004 渲染或 detector 時間。index、暫存／ZIP 峰值 UNKNOWN；本次未執行磁碟型生產，不以舊 df 當新授權 |
| V10 圖 v4 | **草案可交，未核定** | v3 已有 W1↔W2 兩條 same-corridor transition；應保留 ID 並以 PENDING_G4 註記，不能重複加兩條。新增 EXT/BRANCH 四條後共 26 個唯一 ID；22 條原 transition 逐欄保留；全份只能是 draft envelope，不能直接交 runtime loader |

LG／A4-2 c1的P-OV3新增缺項：SOUTH折線在t_X+3.8211–4.02 s穿過EXT_CLEAR入口；若v4的EXT_CAR→EXT_CLEAR將SOUTH_APPROACH列為via_exit，EXT_CLEAR會成為BLIND決策窗的合法競爭候選。是否實際可見／可切及via_exit內容仍UNKNOWN；需v4逐方向出口與adapter P-OV3驗證，不能把草案當既有合法候選。U-V2-6的W2→W1經E_W_CORNER路徑在v3已存在，不能稱僅v4＋M1才會出現。

## 4. 重疊區與出口的靜態界線

以 0.1 m 網格掃各指定支撐面，僅測腳、0.85 m、1.7 m 三點組成的垂直軸是否落入 frustum；不代表人體寬度、姿勢、偵測或遮擋後的可見性。`counts` 不是面積估計。邊緣 0/width/height 使用連續投影幾何，不決定 runtime ROI 的 inclusive 政策。

| 對 | 共視軸點／前者獨有／後者獨有 | 示例座標（m） |
| --- | --- | --- |
| EXT_CAR / EXT_CLEAR | 5,478 / 3,149 / 927 | 共視 `(-5.5,2.2,-0.06)`；CAR 獨有 `(-7.9,-3,-0.06)`；CLEAR 獨有 `(-8.6,5.5,-0.06)` |
| BRANCH / WIDE，僅 CORNER | 625 / 0 / 0 | 共視 `(16.2,1.2,0)`。更強的檢查：矩形四角、三個高度全在兩個凸 frustum 內，因此整塊 CORNER 垂直軸都在兩視錐內，非僅「網格沒找到」 |
| W1 / W2，CORR_W exact 支撐 cell | 2,776 / 898 / 85 | 共視 `(5.8,1.2,0)`；W1 獨有 `(13.2,1.2,0)`；W2 獨有 `(0.2,0.8,0)`；後者在 W1 底緣外、仍屬 CORR_W，W2 depth 約 14.36 m |

這些只是站位候選，並未聲稱「車旁」語意位置或可連續站滿 6 s 的實際偵測品質已驗證。靜止共視點可在幾何上任意停留；6 s 的 RGB／detector 證據 MISSING。v4 草案會把可求出的出口放在舊鏡頭投影邊緣內側 0.15 m 的條帶；BRANCH/WIDE 在 CORNER 內求不到 FOV 邊緣，幾何填 null／MISSING，保留後續靜態遮擋／新場景審查。

## 5. 每張卡與 run 的建議

| 卡 | 本次可交的判斷 |
| --- | --- |
| V2-RR | 門內遮擋 UNKNOWN；1 m 進退與1.2 s衝突；RR-b 仍依 #248/#244 決定合併或分場次 |
| V2-LG | SOUTH 計畫 footprint gap 可提7.4 s；真正 LONG_GAP 未被靜態證據成立 |
| V2-LL | 3 s 可容納1 m進退加約1.33 s停留，但門內遮擋、接回仍未驗證 |
| V2-LT | 預設不做；深處支撐候選存在，離開所有渲染鏡頭尚未成立 |
| V2-PE1 | 有明示 W1→W2 折線和逐鏡頭時刻；v4 的 WIDE 競爭候選排除未成立 |
| V2-PE2 | 可提9.4/13.4，但CAR是否早可見為UNKNOWN；雙向只有frustum，不能證實或否定實際可見，不能直接核BLIND |
| V2-OV1 | 有相鄰 frustum 共視／獨有候選；尚欠凍結整段坐標、P-OV2／3 和遮擋證據 |
| V2-OV2 | CORNER 沒有 FOV-only 獨有區；保持 UNKNOWN，不先選作可執行卡 |
| V2-OV3 | CORR_W 門廳端有 W2 獨有軸點與底緣出口候選；仍 PENDING_G4／M1 |
| V2-A4-2 | 沿用 LG/PE2/RR 限制；只給局部調時，不宣稱77 s整體路線已排通 |
| V2-B4-2 | b/b2/d/e/f 應使用逐鏡頭t_N或明示門檻停留；r1 有 frustum 外支撐候選；整體80 s／遮擋／M1影響仍未驗證 |

**建議先一卡一 run。**同鏡頭組可在工程上合併成一個較長 run、用不同 query/OBSERVATION seed 建各場次，但必須先凍結拼接後的唯一時間軸、run_id、clock、camera registration、scope與新 hashes；不能把現有不同 run 的資料混接成一份。每場次仍是新的 controller request，評估腳本各自綁定 request 與該 run；多場次 summary 由評估端制定。合併不會減少同樣的 camera×seconds×fps，若增添銜接段還增加格數；先分開較易歸因且不讓一張卡阻塞全部。

只渲 W1 的 RR/LL 是合法的**新最小工程 run 提案**，須另做 catalog run registration、index、scope/parameter pins 與計畫；不等於已有 A4 run，也不在本次產製。所有渲染延後，D90-3 不變。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 由主代理發布獨立 Draft PR；本文件不代表已合併。
- Files changed: 新增本文件、同名 `.json`、`scripts/check_r004_l2_static_feasibility.py`；沒有改既有圖、卡片或來源。
- Commands run and results: 上列離線 uv 指令完成；同輸入第二次輸出 byte-identical；9 條折線支撐抽查失敗0；7份輸入前後 pins 相同；改過的卡片input pin確實 fail closed；變更script `ruff check --select F,UP,B` PASS（先修4處zip strict標註）；靜態校正重投影 frozen patch 共26組／104頂點，最大像素差0 px；`git diff --check` 由主代理提交前檢查。第一次 sandbox 內 uv 因 macOS system-configuration NULL panic 退出101；同一 Python 離線解除sandbox後成功，沒有改用新環境。
- Artifacts: 本次 JSON／script SHA-256 由 PR「實際產出」列出；LOCAL static原始檔保留，不上傳；無新RGB、錄製、index或renderer產物。
- Verified: 靜態input hashes、精確折線長／入口先後、frustum投影、支撐cell抽查、v3 22條transition現況與V1–V10的上述界線。
- Not verified: 真實影像、遮擋、完整人體、detector／linker結果、t_L／t_V、連續碰撞、物理通行、G4／M1、正式run、渲染／索引峰值與全卡時序。
- Deviations, UNKNOWN items and follow-ups: 卡片缺唯一座標，本次提出有來源綁定的候選折線；交Claude選定／調時／核定，不能稱已驗證其原始未定路線。OV2獨有區、EXT早可見、R101遮擋、P-OV3皆維持UNKNOWN；未代核任何評分規則。


## CQ-10 修訂邊界

七項逐項回應見PR與議題。此次只修文字解釋／向上取0.1 s，script與JSON bytes保持fd6f749原值，
未重產輸出或做新遮擋檢查。原PR沒有列pytest focused檔（複核發現7亦確認腳本未附測試且非阻擋），
所以沒有增跑其他測試；歷史實跑／lint數字只代表原交件，不是本次重驗。
原Model／effort與GT隔離界線維持；卡片修訂清單由Claude回#261，不代改卡片或核定。
