# CS-B 準備：場景設計稿與生成前門檻提案

日期：2026-10-18（Asia/Taipei）。**設計稿待審，尚未授權建 .blend**。

本輪只寫文件及對 literal 設計值做純 Python 算術；未建 `.blend`、未啟動 Blender、未渲染、未讀 GT／影像／影片、未改後端或原資產，也不接觸正在 CS-R 合併的程式檔。所有幾何、像素、遮擋與時間窗結果一律是 **「設計估計，不是覆蓋證據」**。本稿的路線、事件窗與預期人物數是 private production／人工驗收設計，不得作為檢索、排序、關聯、定位或預測輸入。

依據：[D32／CS-A 核准](https://github.com/Polalalabear/amidst/issues/66#issuecomment-6246311276)、[核准契約 OFFICE_CONTROLLED_SCENE_V1 @ 2643771](https://github.com/Polalalabear/amidst/blob/264377112d1859c5472a9a47dcb56c9b4b38e19e/docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md)、[原提案](../agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md)、[預算](CONTROLLED_DEMO_PREPARATION_20261018.md)、[CS-A 審查](CONTROLLED_SCENE_CS_A_REVIEW_20261018.md)。規則依 [AGENTS.md](../../AGENTS.md)、[DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md)。D32 沒有授權 B 包生成；下列數值都是新提案，不能當已決定或已通過。

## 1. 平面、尺度與風格

`scene_id: controlled-l-corridor`、`scene_version: 1`（尚未生成），右手系、Z-up、XY 地面，單位 m；支撐平面 point=(0,0,0)、normal=(0,0,1)。單層、牆高3.2、一般牆厚0.12、地板厚0.12（頂面z=0），頂棚z=3.2。首版不建樓梯、不複製校園 `.blend`。

風格僅參考已核准提案 §4 的「灰色室內建築、走廊、房間、簡化人形」；低細節、無大貼圖、明亮漫射照明、深灰牆與可分辨的地板。沒有檢視原建築或參考錄影，不宣稱材質／外觀已逐項對照。地標使用靜態房號、門框與地板接縫；不把人物著色或外觀當跨鏡頭身份答案。建議關閉景深與 motion blur，固定產製設定；實際引擎／Blender版本在之後授權的B包記錄，現在UNKNOWN。

| 區域 | 設計範圍 | 說明 |
| --- | --- | --- |
| 西走廊 | x=[0,17.4]、y=[0,2.4] | 沿用契約起始尺寸；西段分到x=15、轉角獨立到17.4。 |
| 北走廊 | x=[15,17.4]、y=[2.4,12] | 不重複計轉角面積；P1到y=11.5。 |
| R101 | x=[5,11]、y=[−5,0] | 6×5m，無鏡頭；門y=0、x=[7.4,8.6]，寬1.2、高2.4。 |
| R102 | x=[17.4,22.4]、y=[7,11] | 5×4m；門x=17.4、y=[8.4,9.6]，寬1.2、高2.4；內有對照鏡頭。 |
| AREA_R101_FRONT | x=[6.5,9.5]、y=[0,2.4] | 公共查詢區域。D27針對人物沿y=1.2穿越此區的全部sample，不宣稱區域內任意位置都符合雙鏡全身。 |
| 西側觀測前廳（新增提案） | x=[−3.2,5]、y=[−2,2.4] | 與西走廊做聯集；讓W1退到(−2.6,−1.4)，不靠超廣角壓低目標像素。R101西牆x=5以後仍保留。 |
| 北側觀測凹室（新增提案） | x=[12.5,15]、y=[7,14.2] | N1移到(13,13.5)，與北走廊間有觀測開口；北走廊實體地板向北延至14.2供結構收口，測試walkable仍只到12。凹室不是演員路線。 |

平面示意，非比例圖：

```text
                N1觀測凹室      北走廊       R102
 y=14.2        ┌──────────┬─────────┐
 y=13.5        │  N1 ↘    │         │
 y=11          │          │ P1終點  ├────────────┐
 y=9           │ 觀測開口 │         門  遮屏  CTRL│
 y=7           └──────────┤         ├────────────┘
 y=5.3                    │遮屏     │
 y=2.4 ───────────────────┘  轉角   │  ←不放鏡頭
 y=1.2       A/P1/P2 →        W2 ◀  │
 y=0  ┌───────────────門────────────────┘
      │ W1 ↗ 前廳    │ R101 │
 y=-2 └──────────────┤      │
 y=-5               └──────┘
```

### 1.1 Walkable 與遮擋結構

walkable以已分類地板polygon聯集為唯一來源：`WALK_VEST_W`、`WALK_CORR_W`、`WALK_CORNER`、`WALK_CORR_N`、`WALK_R101`、`WALK_R102`。重疊區只歸屬一次；牆／下表屏障footprint挖除為BLOCKED，未分類或觀測凹室／北端延伸未核准區為UNKNOWN，不自動開放導航。房門連接各自兩側walkable；同地板接界connection對稱。標記現在NOT_EVALUATED；之後C7/K7核對，不由驗證器另造地圖。

下列是可見的建築屏障，實際mesh／遮擋都需日後核對；不以renderer clip距離製造人物消失。遮屏全部不透明、底z=0、頂z=3.2。

| 物件ID（OBSTACLE_前綴） | XY設計範圍 | 用途及代價 |
| --- | --- | --- |
| OBSTACLE_SCREEN_W | x=[10.4,10.55]、y=[0,0.8] | 南側短翼牆，限制W1看向遠段；主動線y=1.2的包絡r=.30外仍有.10m名義淨距。 |
| OBSTACLE_SCREEN_W_HOOD | x=[−1.65,−1.60]、y=[−2,−1.23] | 前廳遮板；與轉角屏障合用，防止轉角後再次漏進W1。不得變成不透明的軟體ROI／影像遮罩。 |
| OBSTACLE_SCREEN_CORNER_N | x=[14.5,14.65]、y=[1.55,2.4] | 北側短翼牆；P1直行到x16.2後轉北，不穿屏障。包絡外最窄名義淨距.05m，需使用者選擇是否接受或重設計。 |
| OBSTACLE_SCREEN_N | x=[15,15.8]、y=[5.25,5.4] | 北走廊西側翼牆，限制N1看向轉角；路線x16.2保留包絡外.10m名義淨距。 |
| OBSTACLE_SCREEN_R102 | x=[18,18.15]、y=[7.8,10.2] | 室內入口擋屏，避免CTRL透過門拍到走廊人物；仍可繞屏進房，但首輪不測這條通路。 |

北走廊西牆x=[14.88,15]：y=[2.4,7]為實牆；y=[7,14.2]保留開口，窗台z=.5、上緣2.9，供N1觀察，不加透明玻璃效果。門洞z=0–2.4，上方門楣到3.2。外牆、R101/R102三側牆與全部試算AABB在附錄A完整列出；頂棚高於所有射線，不在射線盒集合中。這些新前廳、凹室、翼牆與private盲區西界x=13.7（原候選14.5）都是**待決的場景設計變更**。

## 2. 四鏡頭設計值

yaw為世界XY中從+x逆時針；pitch欄為**向下俯角的正值**，roll=0；這不是直接可填入Blender Euler的數字。附錄以forward/right/up明確定義，匯出時camera local −Z=forward、+Y=up、+X=right，組成camera_to_world列陣列並核對右手旋轉矩陣。

全部960×540、100% resolution、正方形pixel、cx=480/cy=270、shift_x=shift_y=0、針孔無畸變；sensor_fit=HORIZONTAL、sensor_width=36mm、對應感光高度20.25mm；clip=.05–60m，不用clip裁出假盲區。

| 鏡頭 | XYZ m | yaw／俯角／roll ° | 水平／垂直FOV ° | 焦距mm；fx=fy px | 用途 |
| --- | --- | --- | --- | --- | --- |
| CAM_W1 | (−2.6,−1.4,2.0) | 15／16／0 | 57／33.9667 | 33.151876；884.050025 | 西前廳斜看目標／西走廊；解近端出框。 |
| CAM_W2 | (15.0,1.2,2.8) | 180／17／0 | 57／33.9667 | 33.151876；884.050025 | 從東往西看R101前目標區。 |
| CAM_N1 | (13.0,13.5,2.4) | −65／20／0 | 82／52.1148 | 20.706631；552.176835 | 經北側觀測開口看北走廊，補y=11–11.5。 |
| CAM_R102_CTRL | (21.8,10.5,2.8) | 225／25／0 | 74／45.9417 | 23.886807；636.981514 | 室內對照，入口遮屏阻擋走廊視線。 |

A只渲染W1、W2、CTRL三台，N1不在A的run目錄；B1渲染四台。轉角不放鏡頭，8台以上仍用UI fixture。表列小數只是顯示，計算用附錄公式的未取整值；不能把截短後焦距當原K繼續沿用hash。

## 3. 事件、路線與5fps時間表（private design）

兩事件使用相同靜態場景／光學校正、不同run與clock。採`[0,duration)`、t=i/5；A i=0–49（末9.8s）、B1 i=0–99（末19.8s）。日後產製建議Blender frame_start=1、step=1、fps=5、fps_base=1，t=(frame−1)/5；這個產製對應留private。

人物名義高1.70m、半徑.25m；本次幾何包絡用r=.30、z=0–1.80（預留肢體擺動，不是已量測人體）。若生成的人形／動作超出包絡，停止並修訂設計，不縮小估計器不確定性掩飾。兩人使用共同預宣告人體prior，禁止按actor ID選prior。

| 事件／角色 | 路線、速度與時序 |
| --- | --- |
| A | t=0從(1,1.2)以1.3m/s直行到(14,1.2)，數學終點t=10不存影格；末sample x=13.74。目標區連續穿越約[4.2308,6.5385]s；實際sample 22–32，即4.4–6.4s共11個時刻，每台都要D27全身＋接地。 |
| B1 P1 | t=0從(1,1.2)直行到(16.2,1.2)，t≈11.6923轉北，到(16.2,11.5)，t≈19.6154後停留到20。 |
| B1 P2 | **提議改為t=11.0進場**（契約原名義約8s）；從(1,1.2)以1.3m/s到(8,1.2)，t≈16.3846轉南；t≈17.3077過R101門y=0；t≈19.2308到(8,−2.5)，之後停留。進場前不在畫面中，也不能把它藏在另一個測試鏡頭裡。 |

下表全部是「設計估計，不是覆蓋證據」。`有探針可見`只表示290個包絡探針中至少一個通過理想視錐與已列AABB，可能只有身體片段，**不等於全身、可偵測或腳可用**。

| 範圍 | 有探針可見的設計sample | 全包絡探針皆可見的設計sample |
| --- | --- | --- |
| A／P1→W1 | i0–45，t0–9.0 | i0–33，t0–6.6 |
| A／P1→W2 | i0–49，t0–9.8 | i0–36，t0–7.2 |
| B1／P1→W1 | i0–45，t0–9.0 | i0–33，t0–6.6 |
| B1／P1→W2 | i0–49，t0–9.8 | i0–36，t0–7.2 |
| B1／P1→N1 | i67–99，t13.4–19.8 | i74–99，t14.8–19.8 |
| B1／P2→W1、W2 | i55–85，t11.0–17.0 | i55–83，t11.0–16.6 |
| CTRL | A、B1皆無人物探針可見 | 不適用；仍需RGB證明對照鏡頭未拍到人物 |

時窗用半開bin報告：P1預期完全不可見sample i50–66（10.0–13.2s，17格），對應設計bin **[10.0,13.4)s，3.4s**；最後可見sample9.8s到再現13.4s相隔3.6s。不可把這個bin或端點間隔當連續不可見證明；sample之間也未做實際RGB驗收。private `BLIND_CORNER`候選polygon改為`[[13.7,0],[17.4,0],[17.4,3.5],[15,3.5],[15,2.4],[13.7,2.4]]`，是人工驗收定位標記，不宣稱整個polygon全體積都盲。

三段必須保留不同狀態：P1 t7.4–9.8的西鏡尾段、t13.4–14.6的N1再現段僅部分包絡可見；真正的設計全盲bin在中間。不能把partial、缺檔MISSING、推論UNKNOWN都叫盲區。A在目標區外的尾段允許部分可見（仍至少一台有探針）；**本稿不提議A全10s每格全身可見**。若使用者要求擴大全程全身或要求盲窗兩端立即是可用C4a端點，要重新設計鏡頭／遮屏，不能以這張表保證K1端點READY。這項風險列為B-Q4。

P2預期離開所有西鏡視野：i86起t17.2s，位置約(8,.14)，尚在門前；之後穿門進房，不因「房內無鏡頭」就宣稱不可能被看見。這是遮擋設計的預期離視位置，日後用RGB逐格核對。P1北端選擇**補覆蓋**，不列預期離視；末sample在(16.2,11.5)停留。

## 4. 可見性與分離試算的方法／結果

附錄A只有標準庫，讀自己的文字以計SHA，不讀repo／資產／GT／媒體。K的公式`fx=fy=480/tan(HFOV/2)`，`VFOV=2 atan(270/fy)`；對世界點q，d=q−camera：`depth=d·forward`、`u=480+fx(d·right)/depth`、`v=270−fy(d·up)/depth`。逐條射線以slab法與明列不透明AABB相交；不是Blender BVH、renderer visibility或物件mask。

包絡：32個圓周角×9個高度，再加腳／頭中心，共290探針。A50與B1 100時刻共550個相機時間格；B1最多兩個包絡。另在目標中心線x=6.5–9.5每.01m共301個設計位置重算兩鏡頭。它不涵蓋整個AREA的任意y、未取樣的圓柱表面、肢體自遮擋、抗鋸齒、光照／背景對比、姿態、contact estimator、校正誤差或source mesh，故所有實際覆蓋與精度仍UNKNOWN。

| D27中心線加密設計估計 | W1 | W2 |
| --- | --- | --- |
| 名義1.70m頭中心到腳中心的像素高度範圍 | 124.880–160.597px | 168.962–243.653px |
| r=.30／高1.80包絡探針最小左／右餘量 | 436.001／411.782px | 432.231／432.231px |
| 同包絡最小上／下餘量 | 31.549／326.981px | 105.881／93.337px |
| 301個位置×290探針的理想射線檢查 | 全部探針在框內且未命中已列盒 | 同左；只是設計檢查，不是D27驗收PASS |

近端問題：原W1 (.3,1.2,2.8)距起點水平.7m。本提案移到西前廳(−2.6,−1.4,2.0)，水平距約4.441m，配57°HFOV／16°俯角；t=0名義高度337.323px，包絡左/右/上/下餘量63.076/727.193/58.959/91.014px。解法是新增小前廳及pose，不是以bbox底邊猜腳、拉遠clip、縮短盲窗或增加第五台。

北端問題：N1換到觀測凹室，不沿用(16.2,11.8)近乎頭頂的舊位置；末sample名義高度243.618px、四邊最小餘量59.203px，設計探針可見。N1觀測開口的窗台、門框／翼牆都要實際建成並核對，不能只把校正移出牆外卻省略牆體。

B1分離：使用11.0s進場，四鏡頭的5fps設計sample中「兩個包絡同格有探針可見」各為0；W1的P1末9.0→P2首11.0，間隔2.0s；W2末9.8→P2首11.0，間隔1.2s，中間5個sample空窗。分段直線的相對位置解析最小值是**10.220078m**（t≈16.384615s），減去兩個.30m包絡後為9.620078m；只查5fps中心的最小值為10.244003m。這是設計角色間距算術，不供正式系統作身份配對。

## 5. 建立時標記、safe/private 與 E 包介面

| 物件／資料 | 建立／匯出欄位與E包檢查 |
| --- | --- |
| 所有靜態mesh | `amidst_id`（穩定大寫ID）、class、source_object_id、geometry_version、geometry_ref/sha256、geometry_encoding_version、WORLD_METRES、bounds；非顯示用途須列source_method、allowed_purposes、approval_status/scope/ref/hash。未核對一律NOT_EVALUATED，不預填APPROVED。 |
| 支撐面／walkable | floor_id、plane point/normal、polygon/holes、support_surface_id、source_static_sha256、狀態／核准scope、對稱connections；先聯集去重、挖障礙footprint，未知區不補可走。 |
| 牆／翼牆／門楣 | WALL_*／OBSTACLE_*、PHYSICAL、實際mesh、floor/base_z/height、EXACT_MESH、body_policy ref/hash；display_only不得進遮擋／碰撞；門洞不是一個填滿的牆bbox。 |
| 門／房間／查詢地標 | PORTAL_R101/R102的opening a/b、width、sill_z、height、connects；ROOM_*／CORR_*／AREA_*有floor、polygon/geometry與關聯。裝飾字牌DISPLAY_ONLY，不能改walkability。 |
| 四相機 | CAM_*、camera_to_world、convention、K、pixel_origin、尺寸/aspect/shift/sensor/clip、calibration hash；每run另有clock/valid_range/visibility_ref/binding hash。 |
| RGB與技術readiness | source/run/clock/sampling/grid、frame_index/timestamp/rgb_ref/file_sha256、missing紀錄；runtime_profile只含技術期望，不讀角色、盲窗或正確答案。 |

safe僅放核准用途的scene_static／實際geometry、光學校正／run binding、RGB index、query預填及公共detector/body設定／技術profile。正式推論不讀附錄的route functions或下面驗收窗。

private放production_manifest（generator設定與hash、Blender frame mapping）、persons.sim（角色、人數、route、speed、gait、start/end）、event.validation（覆蓋、盲窗、錯開）、之後產製的GT/mask。CS-B只用RGB人工逐格核對＋靜態／校正／產製完整性；GT、mask、renderer visibility/depth只能在輸出凍結並核對hash後評估。作者路線不是人物推論身份。

給Claude E包的最小介面：`schema_version, scene_id/version, frame_id, length/time_unit, source_static_sha256, objects[], floors[], walkable[], portals[], cameras[]/run_bindings[]`；validator輸出`status, checked_schema_version, input_file/content_hashes, checked_purposes, issues[{code,id,field,scope,severity}], unknown_scopes, verifier_version, output_sha256`。缺ID／引用／用途／幾何、重複ID、支撐面／尺度不一致、door兩側缺失均明列；只回報、不自動改標記，不把完整schema當科學準確度通過。E的private validation checker與正式safe validator分開入口，不能遞迴掃到GT。

## 6. 生成前 CS-Q9 門檻提案（全部待使用者約定）

| 提案項目 | 建議值／範圍及理由 | 影響設計參數 | 何時定 |
| --- | --- | --- | --- |
| B1進場時間差 | 推薦11.0s；容許討論10.8–11.2s，仍在20s內走完。原約8s已不足以保證兩鏡頭錯開，不能原樣承諾。 | start_s、兩人同鏡時序、在房內停留時間 | **生成前** |
| 同鏡頭錯開 | 任一鏡頭任一5fps frame最多1個人物；P2首可見sample−P1末可見sample≥1.0s，至少4個中間空sample。推薦設計值目前最窄1.2s／5個空sample。 | camera FOV／遮屏／start_s；不靠GT ID刪第二個偵測 | **生成前** |
| 人物空間間隔 | 活動期中心距至少8.0m；本設計解析最小10.220m。此數是低歧義B1情境限制，非人體安全距離或關聯判準。 | 路線、速度、start_s | **生成前** |
| 全身可見與邊界 | D27目標路徑每sample雙鏡皆頭頂到鞋底整體外廓在框內；上下與左右各≥16px，承重足與地面交界可由RGB人工辨認、無靜態遮屏遮住。不能以bbox底邊或產製座標代替足部證據。 | pose／lens／照明／演員包絡／支撐面 | **生成前** |
| 最小人物像素高度 | **推薦目標區雙鏡均≥112px高度**；可討論112–120px。本設計W1最低124.88px，若選128px需改lens／pose。這是新的高度提案，非沿用D21。部分可見尾段不冒稱達標全身。 | camera距離／focal／解析度／人物尺寸 | **生成前** |
| D21可偵測面積 | 保留`4×28=112`個影像像素的**投影面積（px²）**作舊嚴格負證據介面參考，**不是112px人物高度**。新場景仍需核對detector/body pins；本稿未算或驗收D21正證／負證據足跡。 | 取樣密度／K／腳腰投影／偵測器設定 | 介面沿契約；若改數值**生成前**議定 |
| 全盲窗 | 推薦sample-bin長度3.2–4.0s；本設計3.4s（17格），最後可見到再現sample間隔另報3.6s。每台RGB在指定sample均看不到任何人物部分；不以嚴格footprint以外推定全身盲。不短於舊名義約3.1s，若不符就重設計，不悄悄縮窗。 | 翼牆／hood／相機與路線 | **生成前** |
| 查找通路距離 | 推薦10m，討論8–12m；由AREA邊界沿已核准walkable/portal作geodesic擴展，不能隔牆直線擴張。10m有機會納入北段的實際靜態足跡；是否相交須之後index核對，不能按P1路線指定N1必入選。 | 場景連通、門／AREA尺寸、候選scope | **生成前** |
| 同步容差 | 離線同grid：`abs(clock_error_s)≤0.001s`，缺格仍MISSING，不靠epsilon換格。sample_age獨立：5fps正常`0≤age<0.2s`，它是重複顯示舊sample的年齡，不是時鐘誤差；邊界用有理grid。 | fps_base／frame mapping／校正binding／多鏡同步 | **生成前** |
| 人物／靜態淨距 | nominal height1.70m／r=.25；產製動作包絡不超過1.80m／r=.30；沿路包絡外對已知靜態障礙淨距至少.05m。最窄corner屏障正好.05m；若要.10m需重算屏障／相機，不保證只平移即可。 | 走廊、屏障、gait／肢體擺幅 | **生成前** |
| 光照與blur | 首版固定照明／材質、關景深與motion blur；RGB人工可辨腳/地面，不能靠暫存renderer mask驗收。 | 材質、光源、產製設定與峰值大小 | **生成前** |

只影響輸出／凍結後評估的項目：候選召回率、接地區間涵蓋率與容差／長度、K1範圍帶涵蓋率、關聯正確率、錯誤剪枝率、推論效能等，**凍結前定**，本稿不定結果門檻。`HUMANOID_DISPLAY_MAX_INTERVAL_M`、local-track gap／速度／方向資格與API批次預算也待相應介面／凍結前定；若後來影響場景或鏡頭，須提早到生成前，不以本稿假定已解。D28仍是幾何relation／面積／camera_id排序，不用偵測數。

## 7. B包最小版計畫、耗時與 CS-Q11

**以下是未執行計畫**：使用者先決定§8題目與生成前門檻，再另行授權生成／四張preview。CS-A核准及本文件push都不代表這項授權。

1. 後續任務先核對CS-R已批准且實際整合的baseline、來源版本與可用資源；只建立全新`data/pilot/controlled_scene_v1/assets/controlled_scene_v1.blend`，原資產不複製、不覆寫。新場景封存後修訂另檔名／版本。
2. 建地板／牆／真開口／屏障與簡化人形／行走動畫；建立即標記。驗動作包絡、mesh與校正，safe/private分開匯出；先產靜態validator報告，不讀GT/mask當CS-B結果。
3. preview run用`ctrl-lcorr-s1-preview-5fps-v1-r001`、`purpose=CALIBRATION_PREVIEW, complete=false`。**四張都用同一份B1產製設定與preview clock**：W1 t=0看近端；W2 t=5.0看與A共用的目標路段；N1 t=19.8看北端；CTRL t=5.0看空室。sample選擇只留private；不跨事件混圖，也不當正式A/B1完整run，不作推論或凍結。
4. 每台各1張960×540／PNG_RGB8，記原bytes/file_sha256、相機K/transform、source hash、settings、elapsed與磁碟變化。這四張只檢查外觀／校正／大小及所選sample，**不能驗收11個雙鏡目標時刻、17格盲窗或B1全段錯開**。若要補四張以外的診斷影格或整段A/B1，另報範圍後取得授權。
5. 交回preview與NOT_EVALUATED清單，經授權後先A150張，再B1 400張；不生B2／10Hz／depth／影片／全套縮圖。正式550張與可選4張preview分別盤點，峰值須把preview也算進去。

人工作業規劃估計：標記場景.75–1.5日＋簡化人形/gait .5–1日＋校正/隔離匯出.5–1日＋四張核對.25–.5日，合計**2–4個開發工作日**，不含新後端/前端/C4b、關卡等待或完整RGB驗收。渲染耗時UNKNOWN，先編列四張5–30min的人工排程額度，不宣稱機器會在此範圍內完成；整段ETA須由四張的實測耗時另估。

本次最後`df -k .`：Available **18,651,504 KiB**（同一內建Data卷，約17.79GiB），是會變動的快照，不是已保留空間。授權生成前、每張前後與每個camera批次前後都要重查。

| 資料／暫存 | 規劃額度（非新場景實測） |
| --- | --- |
| A+B1 canonical550 PNG | .133–.398GiB；每張0.5–1.5bytes/pixel的原估算 |
| preview4張 | 約1–3.2MB；計入總額，不當作已刪除 |
| 新blend／幾何／產製設定 | .02–.15GiB |
| safe/private metadata／index／觀測與小收據 | .05–.20GiB；GT/mask不為本輪產製驗收預先輸出 |
| 單批staging | .25–.50GiB；不另存第二份RGB或ZIP |
| optional cache | .02–.06GiB，首批先不生 |

合計維持約**1.5GiB資料＋staging峰值額度**（不含OS swap），不因現在空間較多就升規格。安全bundle以hash/ref引用單份canonical RGB，沒有symlink繞過與raw副本；不清理原資產、既有環境或其他服務。

生成前待同意的停止條件提案：起跑free≥12GiB；任一檢查free<8GiB立即停止；預估下一張／批次會使free<8GiB也不開始；本任務新增資料及暫存接近1.5GiB即停止重估（OS swap另量，不能假定固定2GiB足夠）。單張>5min或四張總耗時>30min先停查設定／資源，不自行擴額。hash/source/pin不符、原資產變動、safe/private越界、校正／尺度錯誤、動作超包絡、D27腳無法判讀、盲窗太短或同鏡雙人，都停下報告；不使用GT補答案、不無限重渲、不擅自清理。這些是Q11與產製保護的**提案，未實作、未授權採用**。

## 8. 請使用者決定（題號供#68回覆）

| 題號 | 建議選項 | 其他選項、風險／代價 |
| --- | --- | --- |
| B-Q1 平面與相機 | **採本稿兩個觀測凹室、四鏡pose、五道遮屏、北端補覆蓋** | 保留原相機位置／不加凹室：須重設計並重新試算，不能承諾近端及北端；不採第五台。 |
| B-Q2 B1時間與盲區 | **P2=11.0s進場、至少1.0s同鏡錯開、中心距≥8m；盲窗bin3.2–4.0s，採3.4s候選及西界13.7** | 堅持原約8s需重新限制鏡頭可見範圍，不可用actorID排除另一人；變更盲窗起訖／區域必須更新private validation，不能悄悄縮窗。 |
| B-Q3 D27畫質與動作 | **目標區雙鏡全身＋接地、四邊≥16px、高度≥112px；包絡1.80m/.30m、包絡外淨距≥.05m** | 高度128px、邊界32px或淨距.10m：現稿至少W1高度/上界或corner淨距不滿足，需調pose/焦距/結構；不能靠縮小包絡或調評估容差假裝通過。 |
| B-Q4 非目標區partial／端點 | **接受§3明列partial過渡，僅D27目標窗要求全身；不承諾盲窗邊緣就是C4a/K1合格端點** | 要求A全10s或B1盲窗相鄰sample全身＋接地：本稿未滿足，應先重設計，再申請生成。長partial段可能使後續定位／關聯UNKNOWN，不能以本次射線試算稱接地估計已可用。 |
| B-Q5 查找通路 | **10m geodesic，固定模板，候選依靜態證據排序** | 8m較窄可能少北側建議；12m範圍較廣但對照/無關候選增加；不按角色路線指定排序。 |
| B-Q6 同步／Q11／preview | **1ms clock_error容差，sample_age獨立；1.5GiB峰值、12/8GiB起停保護與四張preview計畫** | 門檻或停止額度需另選；改容量/硬體只重估，不授權清理。即使本題同意，仍需明說是否授權「新blend＋四張preview」，本輪尚無此授權。 |

以上不是CS-Q9全面結案，也不是CS-B驗收；請先記錄設計決定，再由後續有界任務實作。若B-Q4選擴大全身覆蓋，其餘設計數值不能直接作為生成版本。

## 9. 本輪驗證／實際產出

本輪純Python僅執行附錄的設計算術。沒有執行專案測試／推論／render，也未以函式名稱或設計summary中`all_grid_clear`等欄位冒稱場景驗收PASS。初次設計試算曾顯示轉角後W1漏視且同框雙包絡，已在文件定稿前以實體hood／corner翼牆修訂並重算；沒有碰原始影像或用GT回填。

D21面積單位已唯讀核對[既有檢索契約 @ 9e1234c §2](https://github.com/Polalalabear/amidst/blob/9e1234cc0e626abf49669f6ab0624c42f6e8bacf/docs/contracts/OFFICE_FRAME_RETRIEVAL_V1.md#L46)，不是從記憶推定新高度門檻。文件檢查已確認5個相對連結存在、附錄與實際計算文字稿逐位元相同、所有引用的設計比較／影格與時長算術一致、分支正確、無project venv／尾端空白。LOCAL計算文字稿SHA-256 `74e0b52b94d638904c20c149b612c16381a03f49993ae48eb1c8162fab738605`；設計JSON收據（14,842 bytes）SHA-256 `fc6f514f50c716bcf9f98f4034183420f7d12aa4e4205d9211165424584e71f0`。這些是設計文字／數值的hash，不能當新資料集或覆蓋證據hash。

主要命令：`git status --short`、`git branch --show-current`、`git show 2643771:docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`、`gh issue view 66`（D32）、`gh issue view 68`、`gh pr view 54`、`git ls-remote --heads origin refs/heads/codex/office-demo-rehearsal-docs`、`df -k .`。設計計算指令：

```sh
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --no-sync --python /opt/homebrew/bin/python3 /private/tmp/amidst-b-design-calc.py
```

`--no-project`保證本輪不用專案環境，不建venv／不裝依賴。附錄A可另存為該LOCAL路徑重現；標準庫計算只寫`/private/tmp/amidst-b-design-calc.json`，不接任何`.blend`或後端資料。所有產製計畫指令均未執行。

## 實際產出 / Actual output

- Model / effort: Codex；精確model／effort UNKNOWN，不沿用舊PR的模型標記。
- PR / commits: 僅`codex/office-demo-rehearsal-docs`／Draft #54；本稿commit與normal push後的SHA見#68交接留言。先前本地CS-A審查commit `f50fc37`也隨本次授權的文件分支push公開；不合併整合分支或main。
- Files changed: 本文件、`docs/README.md`索引；附錄只有文內純Python設計算術，不是後端程式。
- Commands run and results: 上列metadata/文件唯讀查核；literal design計算550個相機時間格、目標路徑301個位置×2鏡頭×290探針，分段直線最小間距解析計算；結果見§3–4。文件相對連結、附錄可重現、算術與`git diff --check`在交接記錄結果；專案測試0次。
- Artifacts: 本Markdown；LOCAL `/private/tmp/amidst-b-design-calc.py`與`.json`是設計文字／數值收據，hash見#68；沒有新blend/RGB/GT/index或可用runtime bundle。
- Verified: D32核准對象、文件分支／遠端head、固定設計值與理想投影／有限probe結果、Q9/Q11與必要設計變更／風險已明列。
- Not verified: source geometry、實際校正／人形／腳接地／連續盲區、偵測率／C4a/K1端點資格、GT/指標、runtime/API/瀏覽器、render品質／耗時／RAM／swap均UNKNOWN；未啟動Blender／服務。
- Deviations, UNKNOWN items and follow-ups: 新增觀測前廳／凹室與翼牆，P2由原名義約8改11s，盲區西界改13.7；需B-Q1–B-Q6決定。D21的112是面積，人物112px高度另立提案。**設計稿待審，尚未授權建 .blend**。

## 附錄A：可重現的純Python設計算術

此附錄只含上述literal設計值與理想幾何，不可載入正式推論或當覆蓋證據。輸出中的actor路線／預期窗均為PRIVATE_DESIGN_ONLY。以下程式碼由本輪實際執行的LOCAL文字稿原樣附入：

```python
import math, json, hashlib
from pathlib import Path

DEG=math.pi/180
def camera(pos,yaw,pitch,hfov):
    y,p=yaw*DEG,pitch*DEG
    f=(math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),-math.sin(p))
    right=(math.sin(y),-math.cos(y),0)
    up=(math.sin(p)*math.cos(y),math.sin(p)*math.sin(y),math.cos(p))
    fx=480/math.tan(hfov*DEG/2)
    return dict(pos=pos,yaw_deg=yaw,pitch_down_deg=pitch,roll_deg=0,hfov_deg=hfov,vfov_deg=2*math.atan(270/fx)/DEG,fx=fx,fy=fx,cx=480,cy=270,sensor_width_mm=36,sensor_height_mm=20.25,sensor_fit='HORIZONTAL',lens_mm=36*fx/960,forward=f,right=right,up=up,clip_m=[.05,60])
CAMS={
 'CAM_W1':camera([-2.6,-1.4,2.0],15,16,57),
 'CAM_W2':camera([15,1.2,2.8],180,17,57),
 'CAM_N1':camera([13,13.5,2.4],-65,20,82),
 'CAM_R102_CTRL':camera([21.8,10.5,2.8],225,25,74),
}
# literal proposed opaque wall boxes, no source or renderer reads
BOXES=[
 ('WALL_VEST_W',[-3.32,-2,0],[-3.2,2.4,3.2]),
 ('WALL_VEST_S',[-3.2,-2.12,0],[5,-2,3.2]),
 ('WALL_CORNER_E',[17.4,0,0],[17.52,2.4,3.2]),
 ('WALL_BAY_N_W',[12.38,7,0],[12.5,14.2,3.2]),
 ('WALL_BAY_N_S',[12.5,6.88,0],[14.88,7,3.2]),
 ('WALL_N_TOP',[12.5,14.2,0],[17.4,14.32,3.2]),
 ('WALL_R102_E',[22.4,7,0],[22.52,11,3.2]),
 ('WALL_W_N',[-3.2,2.4,0],[15,2.52,3.2]),
 ('WALL_W_S1',[5,-.12,0],[7.4,0,3.2]),
 ('WALL_W_S2',[8.6,-.12,0],[17.4,0,3.2]),
 ('WALL_R101_LINTEL',[7.4,-.12,2.4],[8.6,0,3.2]),
 ('WALL_R101_W',[4.88,-5,0],[5,0,3.2]),
 ('WALL_R101_E',[11,-5,0],[11.12,0,3.2]),
 ('WALL_R101_S',[5,-5.12,0],[11,-5,3.2]),
 ('WALL_N_W',[14.88,2.4,0],[15,7,3.2]),
 ('WALL_N_WINDOW_SILL',[14.88,7,0],[15,14.2,.5]),
 ('WALL_N_WINDOW_HEADER',[14.88,7,2.9],[15,14.2,3.2]),
 ('WALL_N_E1',[17.4,2.4,0],[17.52,8.4,3.2]),
 ('WALL_N_E2',[17.4,9.6,0],[17.52,14.2,3.2]),
 ('WALL_R102_LINTEL',[17.4,8.4,2.4],[17.52,9.6,3.2]),
 ('WALL_R102_S',[17.4,6.88,0],[22.4,7,3.2]),
 ('WALL_R102_N',[17.4,11,0],[22.4,11.12,3.2]),
 ('SCREEN_W',[10.4,0,0],[10.55,.8,3.2]),
 ('SCREEN_W_HOOD',[-1.65,-2,0],[-1.6,-1.23,3.2]),
 ('SCREEN_CORNER_N',[14.5,1.55,0],[14.65,2.4,3.2]),
 ('SCREEN_N',[15,5.25,0],[15.8,5.4,3.2]),
 ('SCREEN_R102',[18,7.8,0],[18.15,10.2,3.2]),
]
def proj(c,q):
    v=[q[i]-c['pos'][i] for i in range(3)]
    dot=lambda a:sum(v[i]*a[i] for i in range(3))
    d=dot(c['forward'])
    if d<=0:return None
    return (480+c['fx']*dot(c['right'])/d,270-c['fy']*dot(c['up'])/d,d)
def blocked(o,q):
    for name,lo,hi in BOXES:
        a,b=0.,1.
        for k in range(3):
            d=q[k]-o[k]
            if abs(d)<1e-12:
                if o[k]<lo[k] or o[k]>hi[k]:break
            else:
                t0,t1=(lo[k]-o[k])/d,(hi[k]-o[k])/d
                a,b=max(a,min(t0,t1)),min(b,max(t0,t1))
                if a>b:break
        else:
            if a<b and a<1-1e-9 and b>1e-9:return name
    return None
def envelope(x,y,r=.30,h=1.8):
    return [(x+r*math.cos(i*2*math.pi/32),y+r*math.sin(i*2*math.pi/32),h*j/8) for i in range(32) for j in range(9)]+[(x,y,0),(x,y,h)]
def evaluate(c,x,y):
    pts=envelope(x,y)
    projected=[proj(c,p) for p in pts]
    inside=[p is not None and .05<=p[2]<=60 and 0<=p[0]<=960 and 0<=p[1]<=540 for p in projected]
    clear=[ins and not blocked(c['pos'],p) for ins,p in zip(inside,pts)]
    finite=[p for p in projected if p is not None]
    margins=None if not all(p is not None for p in projected) else [min(p[0] for p in finite),960-max(p[0] for p in finite),min(p[1] for p in finite),540-max(p[1] for p in finite)]
    head,foot=proj(c,(x,y,1.7)),proj(c,(x,y,0))
    return dict(any_grid_visible=any(clear),all_grid_visible=all(clear),visible_probes=sum(clear),probes=len(pts),margins_px=margins,nominal_height_px=None if not head or not foot else abs(foot[1]-head[1]))
def route1(t):
    d=min(1.3*t,25.5)
    return (1+d,1.2) if d<=15.2 else (16.2,1.2+d-15.2)
DELAY=11.0
def route2(t):
    if t<DELAY:return None
    d=min(1.3*(t-DELAY),10.7)
    return (1+d,1.2) if d<=7 else (8,1.2-(d-7))
def groups(values):
    out=[]
    for i in values:
        if not out or i!=out[-1][-1]+1:out.append([i])
        else:out[-1].append(i)
    return [dict(first_index=g[0],last_index=g[-1],sample_times_s=[g[0]/5,g[-1]/5],sample_count=len(g)) for g in out]
A=[]; B=[]
for i in range(100):
    t=i/5
    if i<50:
        x,y=route1(t);A.append(dict(i=i,t=t,xy=[x,y],cameras={k:evaluate(c,x,y) for k,c in CAMS.items() if k!='CAM_N1'}))
    p2=route2(t)
    B.append(dict(i=i,t=t,p1=route1(t),p2=p2,cameras={k:dict(p1=evaluate(c,*route1(t)),p2=None if p2 is None else evaluate(c,*p2)) for k,c in CAMS.items()}))
target=[r for r in A if 6.5<=r['xy'][0]<=9.5]
dense_target={k:[evaluate(CAMS[k],6.5+j/100,1.2) for j in range(301)] for k in ['CAM_W1','CAM_W2']}
breaks=sorted(set([DELAY,15.2/1.3,25.5/1.3,DELAY+7/1.3,DELAY+10.7/1.3,20]))
continuous=[]
for a,b in zip(breaks,breaks[1:]):
    p,q=route1(a),route2(a);p1,q1=route1(b),route2(b)
    r=[p[i]-q[i] for i in range(2)];v=[((p1[i]-q1[i])-r[i])/(b-a) for i in range(2)]
    vv=sum(z*z for z in v); dt=0 if vv==0 else max(0,min(b-a,-sum(r[i]*v[i] for i in range(2))/vv))
    continuous.append((math.hypot(*(r[i]+dt*v[i] for i in range(2))),a+dt))
summary={
 'label':'DESIGN_ESTIMATE_NOT_COVERAGE_EVIDENCE',
 'A_no_visible_camera_indices':[r['i'] for r in A if not any(c['any_grid_visible'] for c in r['cameras'].values())],
 'A_target':{k:dict(sample_indices=[r['i'] for r in target],all_grid_clear=all(r['cameras'][k]['all_grid_visible'] for r in target),min_margins_px=[min(r['cameras'][k]['margins_px'][j] for r in target) for j in range(4)],height_range_px=[min(r['cameras'][k]['nominal_height_px'] for r in target),max(r['cameras'][k]['nominal_height_px'] for r in target)]) for k in ['CAM_W1','CAM_W2']},
 'B_both_visible':{k:[r['i'] for r in B if r['cameras'][k]['p1']['any_grid_visible'] and r['cameras'][k]['p2'] and r['cameras'][k]['p2']['any_grid_visible']] for k in CAMS},
 'B_p1_all_cameras_no_visible_probe':groups([r['i'] for r in B if not any(c['p1']['any_grid_visible'] for c in r['cameras'].values())]),
 'A_visible_windows':{k:groups([r['i'] for r in A if r['cameras'][k]['any_grid_visible']]) for k in A[0]['cameras']},
 'B_visible_windows':{k:{p:groups([r['i'] for r in B if r['cameras'][k][p] and r['cameras'][k][p]['any_grid_visible']]) for p in ['p1','p2']} for k in CAMS},
 'B_full_grid_windows':{k:{p:groups([r['i'] for r in B if r['cameras'][k][p] and r['cameras'][k][p]['all_grid_visible']]) for p in ['p1','p2']} for k in CAMS},
 'B_min_center_separation_m':min(math.dist(r['p1'],r['p2']) for r in B if r['p2']),
 'B_continuous_min_center_separation_m_and_time_s':min(continuous),
 'dense_target_step_m':.01,
 'dense_target':{k:dict(all_grid_clear=all(r['all_grid_visible'] for r in rows),min_margins_px=[min(r['margins_px'][j] for r in rows) for j in range(4)],height_range_px=[min(r['nominal_height_px'] for r in rows),max(r['nominal_height_px'] for r in rows)]) for k,rows in dense_target.items()},
 'A_start_W1':A[0]['cameras']['CAM_W1'],
 'B_p1_final_N1':B[-1]['cameras']['CAM_N1']['p1'],
}
out=dict(schema_version='controlled-scene.design-calculation.v1',claim='DESIGN_ESTIMATE_NOT_COVERAGE_EVIDENCE',inputs=dict(cameras=CAMS,opaque_design_boxes=BOXES,envelope=dict(radius_m=.30,height_m=1.8,nominal_height_m=1.7,azimuth_probes=32,height_levels=9),fps=5,duration_a_s=10,duration_b1_s=20,delay_s=DELAY,speed_mps=1.3,source='LITERAL_DESIGN_VALUES_ONLY'),summary=summary,source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
Path('/private/tmp/amidst-b-design-calc.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps(summary,indent=2));print('receipt_bytes',Path('/private/tmp/amidst-b-design-calc.json').stat().st_size)
```
