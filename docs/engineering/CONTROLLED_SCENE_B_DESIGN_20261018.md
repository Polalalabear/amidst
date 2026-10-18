# CS-B 修訂設計稿：D36–D42／D45／D47／D48–D50

日期：2026-10-18（Asia/Taipei）。**已依 D50 修訂，待 Claude 確認**。D49條件2依D50重新計算，須等這版yaw205°確認；本輪未建blend／渲染。

本輪只改文件、對literal設計值做純Python試算。未建／開blend、未啟動Blender、未渲染、未讀GT／影像、未改後端或原資產。本次依[Claude複核R1](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250606802)、[B-Q7補充](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250681019)與[使用者D48–D49](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250719072)更新；以下D36–D47是持續有效的前置決定。依[Claude審查§8七項](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247834352)、[D36–D42](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6247956630)、本輪使用者D45與D47指示修訂。D47取代先前「人工逐格看全數影格」的流程；不放寬D1／D26。

核准基準仍是[D32](https://github.com/Polalalabear/amidst/issues/66#issuecomment-6246311276)與[契約@2643771](https://github.com/Polalalabear/amidst/blob/264377112d1859c5472a9a47dcb56c9b4b38e19e/docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md)，規則見[AGENTS.md](../../AGENTS.md)、[DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)。設計文內的角色路線／預期窗只供產製／審查；正式loader、檢索、關聯、定位與預測不得讀本文件、private路線或事件答案。CS-A及門檻核准本身不是生成授權；D49的特定條件式授權見§7.0，不以文件push冒稱條件已全部成立。

## 0. D45：每個數值的估計／誤差約定（文件與Demo都適用）

**所有幾何、投影、餘量、可見窗、淨距、耗時與容量數字均標為「設計估計，不是覆蓋證據」。**各表共用以下誤差標記，適用每一格數值及附錄的每個輸出，不省略成準確度保證：

- 設計輸入（座標／角度／尺寸／速度）：literal設定值，算術輸入誤差±0；實際建模、校正與動作偏差UNKNOWN，尚無實測誤差界。它們是設計估計的參數，不是量測。
- 投影／距離輸出：顯示至.001單位時，只有顯示捨入誤差±.0005該單位；表列到其他精度時為末位半單位。有限探針／圓柱／AABB模型誤差UNKNOWN，不把捨入誤差當實際位置誤差。表列min/max是設計範圍，不是信賴區間。
- 5fps時間窗：sample grid精確間隔.2s（有理數算術），sample index及計數無算術誤差；連續邊界只限於相鄰sample間，單側量化不確定度<.2s，兩端合計<.4s，且實際遮擋模型誤差UNKNOWN。bin長度不是連續全盲證明。
- 人工／偵測器：未測的RGB輪廓、足部、誤判率與實際校正／接地／物理位置誤差均UNKNOWN；不得用bbox底邊推定腳。容量／工時以範圍或上限額度報告，實測偏差UNKNOWN。
- 已決門檻（例如≥112px、≥16px、≥3.2s、10%）是使用者規定，無估計誤差；相對門檻的**設計估計餘量**另報。ID、版本、hash、影格尺寸等協定常數是精確標籤／規格，不能誤稱為物理量測。

Demo常駐說明文字：「設計估計；實際位置與接地誤差未量測。投影、內插、假設與RGB觀測分開；不確定度非準確度保證。」Demo交接必須口頭說明相同限制，人物／曲線推論須帶uncertainty及來源／單位／方法；缺少不可顯示為確定結果。後端第一批另處理欄位驗證，不更改C4a估計器。

## 1. 平面、地板與靜態結構（設計估計；輸入±0／實體誤差UNKNOWN）

`controlled-l-corridor`，新scene初版1；右手系Z-up，單位m。**所有可走地板一律z=0，只有同一個FLOOR_GROUND、support_plane point=[0,0,0]、normal=[0,0,1]；不設高低差或分層（D36）。**牆高3.2、牆厚.12、地板厚.12且頂面0、頂棚3.2。採原提案的灰色室內建築／走廊／簡化人形風格，不讀參考媒體；低細節、固定漫射照明、無大型貼圖、景深與motion blur關閉。沒有複製原blend。

| 區域ID | XY範圍m（設計估計） | 說明／誤差 |
| --- | --- | --- |
| CORR_W | [0,17.4]×[0,2.4] | 西走廊及轉角；實體建模誤差UNKNOWN |
| CORR_N | [15,17.4]×[2.4,12] | 北走廊；北端結構地板延至14.2，walkable只到12 |
| ROOM_R101 | [5,11]×[−5,0] | 門y=0、x=[7.4,8.6]、高2.4；寬1.2 |
| ROOM_R102 | [17.4,22.4]×[7,11] | 門x=17.4、y=[8.4,9.6]、高2.4；寬1.2 |
| CORR_VEST_W | [−3.2,5]×[−2,2.4] | W1觀測前廳，和走廊相接；去重規則如下 |
| AREA_OBS_BAY_N | [12.5,15]×[7,14.2] | N1觀測凹室，DISPLAY／UNKNOWN，不建立walk connection |
| AREA_R101_FRONT | [6.5,9.5]×[0,2.4] | D27只驗沿y=1.2的目標路徑sample，不宣稱任意位置雙鏡全身 |

### 1.1 Walk polygon頂點／重疊歸屬

以下是z=0、**挖洞／扣除前**的CCW polygon設計估計；座標算術±0，建模誤差UNKNOWN。先做平面聯集、挖牆／OBSTACLE footprint，門口地板有實體支撐，未核准處UNKNOWN。只在已核准polygon範圍內主張WALKABILITY，C7／K7只驗證標記。

| WALK ID | XY頂點（設計估計） | 對稱connections |
| --- | --- | --- |
| WALK_VEST_W | [[−3.2,−2],[5,−2],[5,0],[0,0],[0,2.4],[−3.2,2.4]] | WALK_CORR_W |
| WALK_CORR_W | [[0,0],[15,0],[15,2.4],[0,2.4]] | WALK_VEST_W、WALK_CORNER、WALK_R101（經PORTAL_R101） |
| WALK_CORNER | [[15,0],[17.4,0],[17.4,2.4],[15,2.4]] | WALK_CORR_W、WALK_CORR_N |
| WALK_CORR_N | [[15,2.4],[17.4,2.4],[17.4,12],[15,12]] | WALK_CORNER、WALK_R102（經PORTAL_R102） |
| WALK_R101 | [[5,−5],[11,−5],[11,0],[5,0]] | WALK_CORR_W（經PORTAL_R101） |
| WALK_R102 | [[17.4,7],[22.4,7],[22.4,11],[17.4,11]] | WALK_CORR_N（經PORTAL_R102） |

原重疊[0,5]×[0,2.4]全部歸WALK_CORR_W，從VEST挖除；共享邊不重複計面積，邊界歸屬依上表順序的唯一owner登錄，對稱connection不依面積重複創建。FLOOR_GROUND只是同一支撐面ID，不代表整個外框都walkable。北凹室／北端延伸無walk polygon；觀測窗不是走道。

### 1.1.1 預期挖除清單（設計估計，供E包；不是實際walkability證據）

§1.1頂點為扣除前範圍。下表是附錄literal AABB與walk polygon在z=0的正面積交集；座標為設計輸入±0、實體建模誤差UNKNOWN，面積顯示至.0001m²時捨入±.00005m²。所有項目均須從walkable扣除，不把被牆／屏障佔用處保留為可走。

| WALK owner | 挖除物件ID | XY交集範圍m（設計估計） | 面積m²（設計估計） | 匯出方式 |
| --- | --- | --- | --- | --- |
| WALK_VEST_W | WALL_R101_W | x=[4.88,5]、y=[-2,0] | 0.2400 | 貼邊扣除，改outer polygon |
| WALK_VEST_W | OBSTACLE_SCREEN_W_HOOD | x=[-1.65,-1.6]、y=[-2,-1.23] | 0.0385 | 貼邊扣除，改outer polygon |
| WALK_CORR_W | OBSTACLE_SCREEN_W | x=[10.4,10.55]、y=[0,0.8] | 0.1200 | 貼邊扣除，改outer polygon |
| WALK_CORR_W | OBSTACLE_SCREEN_CORNER_N | x=[14.5,14.65]、y=[1.6,2.4] | 0.1200 | 貼邊扣除，改outer polygon |
| WALK_CORR_N | OBSTACLE_SCREEN_N | x=[15,15.8]、y=[5.25,5.6] | 0.2800 | 貼邊扣除，改outer polygon |
| WALK_R101 | WALL_W_S1 | x=[5,7.4]、y=[-0.12,0] | 0.2880 | 貼邊扣除，改outer polygon |
| WALK_R101 | WALL_W_S2 | x=[8.6,11]、y=[-0.12,0] | 0.2880 | 貼邊扣除，改outer polygon |
| WALK_R102 | WALL_N_E1 | x=[17.4,17.52]、y=[7,8.4] | 0.1680 | 貼邊扣除，改outer polygon |
| WALK_R102 | WALL_N_E2 | x=[17.4,17.52]、y=[9.6,11] | 0.1680 | 貼邊扣除，改outer polygon |
| WALK_R102 | OBSTACLE_SCREEN_R102 | x=[18,18.15]、y=[7.8,10.2] | 0.3600 | 內部洞holes_m（CW） |

共10處，五屏障合計.9185m²（原.7585，加深SCREEN_N增加.1600）；全部扣除合計2.0705m²。扣除前138.8800m²，互不重疊的扣除後設計面積136.8095m²（顯示±.00005m²；實體誤差UNKNOWN）。WALK_CORNER無正面積挖除；只接觸邊界的牆不虛增面積。

唯一內部洞是WALK_R102的`holes_m=[[[18,7.8],[18,10.2],[18.15,10.2],[18.15,7.8]]]`（CW，設計座標±0）；其餘九處接outer邊界，應以平面差集改outer polygon／必要時分片，不輸出與外環共邊的無效洞。E包在核對後再建立最終polygon_m／holes_m及geometry hash；若出現碎片或連通差異就報UNKNOWN，不自動補連通。上表交集不互相重疊，不重複扣面積；它不是人體半徑膨脹後的可達區，也不是碰撞通過證明。

### 1.2 遮擋物與窗洞（設計估計）

| OBSTACLE ID | XY範圍m；z=[0,3.2] | 包絡外最小淨距／用途 |
| --- | --- | --- |
| OBSTACLE_SCREEN_W | [10.4,10.55]×[0,.8] | .10m（相對.10門檻餘量0；實體誤差UNKNOWN） |
| OBSTACLE_SCREEN_W_HOOD | [−1.65,−1.60]×[−2,−1.23] | 遮掉W1轉角後漏視；與路線無近接 |
| OBSTACLE_SCREEN_CORNER_N | [14.5,14.65]×[1.60,2.4] | **由1.55移至1.60；淨距.10m、門檻餘量0**；只移屏障的對照試算時間窗不變（與原W2比較），W2修改造成的變化另報 |
| OBSTACLE_SCREEN_N | **[15,15.8]×[5.25,5.6]** | **D48沿+y加深.20m**，x與主路線不變；包絡外淨距仍.10m、淨距門檻餘量0；限制N1看向轉角 |
| OBSTACLE_SCREEN_R102 | [18,18.15]×[7.8,10.2] | 擋住CTRL透門拍到走廊；不作本輪人物通路 |

所有屏障在正文與附錄均用OBSTACLE_前綴；牆保留契約WALL_類別前綴，不混成屏障ID。北走廊西牆x=[14.88,15]：y=[2.4,7]實牆；y=[7,14.2]留觀測窗，窗台z=.5、窗楣z=2.9–3.2；`WALL_N_WINDOW_SILL`／`WALL_N_WINDOW_HEADER`是WALL，窗洞是非通行觀測開口、非PORTAL、無walk connection，凹室仍UNKNOWN。門洞則是PORTAL_R101／R102（sill_z=0），不以填滿的牆bbox當門。實體mesh／遮擋目前NOT_EVALUATED。

## 2. 四鏡頭（設計估計；literal輸入±0，實際pose／K誤差UNKNOWN）

yaw從世界+x逆時針；俯角向下為正。Blender camera local −Z向前、+Y向上；rotation_euler為XYZ度，公式(90−俯角,0,yaw−90)。匯出camera_to_world須核對右手旋轉、K與同一WORLD_METRES尺度，不直接把yaw／俯角塞進Euler。

| Camera | XYZ m（設計估計） | yaw／俯角／roll ° | rotation_euler XYZ ° | HFOV／VFOV °；fx=fy px；lens mm |
| --- | --- | --- | --- | --- |
| CAM_W1 | (−2.6,−1.4,2.0) | 15／16／0 | 74／0／−75 | 57／33.9667；884.050025；33.151876 |
| CAM_W2 | **(14.4,2.1,1.8)** | **205／10／0** | **80／0／115** | 57／33.9667；884.050025；33.151876 |
| CAM_N1 | (13,13.5,2.4) | −65／20／0 | 70／0／−155 | 82／52.1148；552.176835；20.706631 |
| CAM_R102_CTRL | (21.8,10.5,2.8) | 225／25／0 | 65／0／135 | 74／45.9417；636.981514；23.886807 |

W2先前(14.5,2.1,1.8)貼住角屏西側表面；D48 R1移到(14.4,2.1,1.8)；[D50](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251036732)依[Claude複核](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250913691)再把yaw從202°改205°、Euler從(80,0,112)改(80,0,115)，取代D48「角度不變」條款。位置、俯角10°、roll0°、K與全部其他設計值不變。相機位置點到OBSTACLE_SCREEN_CORNER_N西面設計間隙.100m（顯示±.0005m、實體mesh／mount誤差UNKNOWN）；到所有列出AABB的最小間隙亦為.100m，避免共面。這只是camera位置點，不是未建mount的碰撞保證。W2位於轉角西側.6m（x<15），在private BLIND_CORNER範圍內朝西南西；不能把該polygon當成整體不可觀測。其原始候選(15,1.2,2.8)／180°／17°已被取代，不在轉角設鏡頭。其他三鏡不變；未加第五台。全鏡960×540、100%、pixel aspect=1、cx=480/cy=270、shift=0、針孔無畸變、sensor_fit=HORIZONTAL、寬36mm／高20.25mm、clip .05–60m。這些為精確規格或設計估計輸入，實際校正誤差UNKNOWN；焦距小數捨入±.0000005mm、FOV顯示±.00005°，實作須由未取整公式匯出並hash，不以印出的截短K當實際pin。

事件A只渲W1、W2、CTRL；B1渲四台；>8台只用UI fixture。鏡頭數／影格數是規格計數，沒有估計誤差。

## 3. 路線／時間與接地候選（private設計估計）

A為10s／50sample／三鏡150張，B1為20s／100sample／四鏡400張；5fps、t=i/5、半開[0,duration)。末sample分別9.8／19.8s，與duration分開。產製Blender frame_start=1、fps=5等mapping只在private。精確grid算術±0，實際連續遮擋邊界<.2s單側量化且模型誤差UNKNOWN。

- A：從(1,1.2)以1.3m/s直行，t=10到(14,1.2)但不存此格；i49在(13.74,1.2)。目標中心線x=[6.5,9.5]，穿越[4.2308,6.5385]s（顯示±.00005s），sample i22–32／4.4–6.4s，共11時刻。所有可走地板z=0。
- B1 P1：同起點／速度，到(16.2,1.2)於約11.6923s轉北，約19.6154s到(16.2,11.5)後停留；末sample北端補覆蓋，不列預期離視。
- B1 P2：**固定11.0s進場（D37）**，同起點／速度，到(8,1.2)於約16.3846s轉南、約17.3077s穿R101門、約19.2308s到(8,−2.5)後停留。進場前不出現在其他鏡頭。時間顯示捨入±.00005s，生成誤差UNKNOWN。
- 兩人名義1.70m／r=.25；實際人形允許高1.65–1.75m（中心±.05m）、肩寬≤.5m，動作包絡高1.80m／r=.30。身高上界相對包絡剩.05m、肩寬相對直徑餘量0；動作不得超包絡。兩人相同中性外觀，不用顏色／衣物／actorID暗示關聯答案。

正證模型用名義人體、另算1.65／1.75m敏感度；盲窗、同鏡雙人、淨距用較大包絡，不能用包絡高於頭頂的區域證明有人可見。下表是有限探針的設計估計，不是RGB覆蓋證據；「any」可能僅部分身體，另驗頭＋部分軀幹。

| 模型／鏡頭 | A可見any | B1 P1可見any | B1 P2可見any | B1 P1全身探針 |
| --- | --- | --- | --- | --- |
| nominal／CAM_W1 | i0–44 | i0–44 | i55–85 | i0–34 |
| nominal／CAM_W2 | i0–49 | i0–50 | i55–87 | i0–37 |
| nominal／CAM_N1 | 無 | i69–99 | 無 | i74–99 |
| nominal／CAM_R102_CTRL | 無 | 無 | 無 | 無 |
| envelope／CAM_W1 | i0–45 | i0–45 | i55–85 | i0–33 |
| envelope／CAM_W2 | i0–49 | i0–50 | i55–87 | i0–36 |
| envelope／CAM_N1 | 無 | i68–99 | 無 | i75–99 |
| envelope／CAM_R102_CTRL | 無 | 無 | 無 | 無 |

**接地端點候選（設計估計）**：名義腳環z=0全探針可見，W1 i0–34（0–6.8s）、新W2 i0–37（0–7.4s）、N1 i74–99（14.8–19.8s）；保守包絡腳環W1只到i33（6.6s）；D50後W2由i0–37縮為**i0–36（0–7.2s，少一格）**，N1仍從i75（15.0s）開始，保守候選端點間隔由7.6變7.8s。名義W2腳環仍i0–37，不把包絡改變誤套到名義端點。名義人體N1仍從i74（14.8s）開始，名義候選端點不變；不能籠統說所有模型端點都不變。新pose最後候選W2 **7.4s → N1 14.8s，端點間隔7.4s**，中間i38–73缺少此腳環證據（不是已確認無足部影像）。D39／原審查所列**舊pose W2 7.2s → N1 14.8s、間隔7.6s**保留作版本對照，不能把舊值當新pose結果；改pose使最後候選晚一格、間隔少.2s。單側時間量化<.2s、連續間隔模型誤差UNKNOWN。這是幾何候選，不是C4a／K1合格端點；不得用bbox底邊補腳。

**接受partial（D39）**：只有D27目標窗要求全身＋接地；西鏡尾段與N1再現先partial、後全身，與全盲／MISSING／UNKNOWN分開顯示。盲窗邊緣不承諾就是接地端點。新W2的P2離視時刻／位置以表中末格之後的sample另用RGB確認，不用「已進房」當無人可見的證明。

private `BLIND_CORNER` polygon仍為[[13.7,0],[17.4,0],[17.4,3.5],[15,3.5],[15,2.4],[13.7,2.4]]（設計估計輸入±0）。它是驗收定位範圍，**不等於未觀測地板**，不宣稱整個polygon全體積盲，也不進正式索引／剪枝。RGB盲窗任何人物像素都算可見；全程覆蓋至少頭＋部分軀幹。

## 4. 兩種模型重算／餘量（全部設計估計，不是覆蓋證據）

理想針孔投影與slab線段／明列不透明AABB相交，無Blender BVH、GT、mask、renderer visibility或深度。每模型32角×9高度＋頭腳中心=290探針；腳環64角；A i45–i49保留圓柱64角×35高=2242探針作對照，D50正證另外依Claude模型試算半徑.10m頭球（中心H−.10）、r=.25軀幹（z=.45H–.75H）；不再用r=.25的表面環替頭。中心線301位置、間距.01m（設計網格，不是覆蓋誤差界）。不涵蓋人體真實外廓、自遮擋、光照或未取樣表面；模型誤差UNKNOWN。附錄與LOCAL收據可重現。

| D27中心線設計估計 | W1（未改） | D50 W2 | 相對門檻餘量／誤差 |
| --- | --- | --- | --- |
| 名義1.70m頭腳高度px | 124.880／160.597 | 196.752／300.461 | 最低高度相對112px：+12.880／+84.752px；顯示±.0005px，模型誤差UNKNOWN |
| 名義1.70m最小左／右／上／下px | 440.955／415.649／39.110／327.983 | 654.823／148.785／125.793／90.271 | 最窄邊相對16px：+23.110／+74.271px；顯示±.0005px，模型誤差UNKNOWN |
| 1.65m敏感度頭腳高度px | 121.068／155.640 | 190.743／291.094 | 最低高度相對112px：+9.068／+78.743px；顯示±.0005px，模型誤差UNKNOWN |
| 1.65m敏感度最小左／右／上／下px | 441.014／415.723／42.848／327.983 | 654.823／149.176／131.611／90.271 | 最窄邊相對16px：+26.848／+74.271px；顯示±.0005px，模型誤差UNKNOWN |
| 1.75m敏感度頭腳高度px | 128.701／165.569 | 202.776／309.863 | 最低高度相對112px：+16.701／+90.776px；顯示±.0005px，模型誤差UNKNOWN |
| 1.75m敏感度最小左／右／上／下px | 440.896／415.574／35.363／327.983 | 654.823／148.393／119.962／90.271 | 最窄邊相對16px：+19.363／+74.271px；顯示±.0005px，模型誤差UNKNOWN |
| 1.80m／r=.30包絡頭腳高度px | 132.531／170.556 | 208.813／319.299 | 最低高度相對112px：+20.531／+96.813px；顯示±.0005px，模型誤差UNKNOWN |
| 1.80m／r=.30包絡最小左／右／上／下px | 436.001／411.782／31.549／326.981 | 646.056／141.566／114.118／86.806 | 最窄邊相對16px：+15.549／+70.806px；顯示±.0005px，模型誤差UNKNOWN |

四種模型的目標中心線探針兩鏡均框內且未撞列出的盒，為設計／校正檢查，不稱D27 PASS。r=.40仍僅作超包絡敏感度，不放寬允許步態，也不作正證。

| 模型（設計估計） | 全盲sample／半開bin | bin長度及相對≥3.2s餘量 | A無any圓柱探針／無舊頭軀幹**中心**探針sample |
| --- | --- | --- | --- |
| nominal | i51–68／[10.2,13.8)s | 3.6s，餘量+0.4s | []／[] |
| short | i51–68／[10.2,13.8)s | 3.6s，餘量+0.4s | []／[] |
| tall | i51–68／[10.2,13.8)s | 3.6s，餘量+0.4s | []／[49] |
| envelope | i51–67／[10.2,13.6)s | 3.4s，餘量+0.2s | []／[49] |
| expanded_r040 | i51–66／[10.2,13.4)s | 3.2s，餘量+0.0s | []／[49] |

盲窗與D48相同：包絡3.4s，r=.40為3.2s，名義／矮／高3.6s。bin算術±0；sample間不是連續全盲證明，實體模型誤差UNKNOWN。RGB只強制≥3.2s，不以4.0s當失敗上限。表內舊中心probe定義仍為z=.97H／.80H，與下表**頭球中心H−.10**不同，不能混用。

### 4.1 D50：A i45–i49頭球／軀幹可見性（設計估計）

頭球r=.10m、中心H−.10m，採13個polar層×24方位=312探針（極點含重複，**計數不是像素／機率**）；軀幹r=.25m、z=.45H–.75H，4層×32方位=128探針。所有設定都是設計估計輸入±0，真實人體mesh／步態／可辨識誤差UNKNOWN。影像寬度是有限可見探針的投影u最大−最小，僅近似範圍，不是RGB bbox或保證的完整頭寬；px顯示捨入±.0005px。

| 名義1.70m（設計估計） | i45 | i46 | i47 | i48 | i49 |
| --- | --- | --- | --- | --- | --- |
| 頭球可見探針／312 | 312/312 | 312/312 | 312/312 | 312/312 | 163/312 |
| 頭球中心u px | 435.387 | 371.953 | 288.388 | 173.303 | 4.719 |
| 頭部可見u範圍px | 389.271／481.093 | 319.167／424.207 | 225.730／349.373 | 95.256／247.191 | 0.329／100.722 |
| 頭部可見水平跨度px | 91.822 | 105.040 | 123.643 | 151.935 | 100.393 |
| 軀幹表面可見探針／128 | 102/128 | 79/128 | 52/128 | 30/128 | 10/128 |

| i49身高敏感度（設計估計） | 頭中心u px（相對左界餘量） | 頭球可見探針／312 | 頭部可見u範圍／跨度px | 軀幹可見探針／128 |
| --- | --- | --- | --- | --- |
| short | +8.816 | 192/312 | 0.549／103.887／103.337 | 9/128 |
| nominal | +4.719 | 163/312 | 0.329／100.722／100.393 | 10/128 |
| tall | +0.549 | 157/312 | 0.408／97.505／97.096 | 12/128 |

D50把i49頭球中心移回畫面內，頭部仍是partial、左側被裁切，不能描述為全頭／全身可見或邊界餘量充足；D27的16px全身邊界只要求目標窗。舊D48名義頭球中心u約−55.5px是Claude歷史設計估計，本輪未把它當新yaw結果；此次球體／軀幹模型與圓柱表面環各自保留在附錄，不靠加寬「頭部」宣稱改進。實際RGB能否辨識頭及部分軀幹仍由D47判讀。

B1四鏡同格雙圓柱／包絡探針計數均0；W2仍末i50（10.0s）→首i55（11.0s），**1.0s／4個空sample，門檻餘量0**；W1維持2.0s／9空sample，餘量1.0s／5格。r=.40的W2同樣末i50→首i55。這些皆設計估計計數±0，實際首可見格／keyframe與人體外擴仍屬D49渲染前核對；不改P2進場或任何門檻。

中心距解析最小10.220078m（顯示±.0000005m），相對8m產製約束餘量2.220078m；扣兩個.30m包絡後9.620078m。這只用產製路線算術，不列入RGB驗收或任何正式配對。

近端W1不變：與起點水平4.441m（±.0005m顯示），名義高度337.323px、包絡邊餘量63.076／727.193／58.959／91.014px（±.0005px）；相對16px最窄多42.959px。以pose／前廳解距.7m近端出框，不加第五台、不用clip或bbox底邊推腳。北端N1補y=11–11.5，名義末格高度243.618px、四邊最小約74.810px（實際見收據；顯示／模型誤差依§0），不用「預期離視」迴避。

W2敏感度（設計估計）：以yaw205°／俯角10°為中心，兩軸各±.25°的9組擾動，包絡目標最窄邊82.396–91.202px（對16px最少餘量66.396px），P1末可見index集合[50]。舊z=.97H／.80H中心probe在最矮人體i45–i49的檢查集合為[False, True]，不將它混稱頭球中心檢查。擾動非實測校正誤差界；px顯示±.0005、實體模型誤差UNKNOWN。W1歷史敏感度不重跑。

## 5. E包介面、預期物件表與safe／private

所有ID唯一、geometry_version初版1、建立時amidst_id；用途核准狀態先NOT_EVALUATED，不能預填APPROVED。完整預期ID集合是下表＋§1.1六個WALK＋附錄全部WALL／OBSTACLE AABB（逐項ID／範圍），不靠模糊名稱生成新authority。

| ID／集合 | class | allowed_purposes候選 | display_only | connects |
| --- | --- | --- | --- | --- |
| FLOOR_GROUND | 支撐面紀錄（floors[]，非自創objects class） | WALKABILITY／DISPLAY（核准scope內） | false | 六WALK引用同面；不自動連通 |
| WALK_VEST_W／WALK_CORR_W／WALK_CORNER／WALK_CORR_N／WALK_R101／WALK_R102 | WALKABLE | WALKABILITY／DISPLAY | false | §1.1對稱表 |
| CORR_VEST_W／CORR_W／CORR_N | CORRIDOR | DISPLAY | true | 無（實際連通只在WALK／PORTAL） |
| ROOM_R101／ROOM_R102 | ROOM | DISPLAY | true | 無 |
| AREA_R101_FRONT | AREA | DISPLAY | true | 公開查詢polygon；不靠display升權 |
| AREA_OBS_BAY_N | AREA | DISPLAY | true | 無；凹室walkability UNKNOWN |
| PORTAL_R101 | PORTAL | WALKABILITY／DISPLAY | false | WALK_CORR_W↔WALK_R101 |
| PORTAL_R102 | PORTAL | WALKABILITY／DISPLAY | false | WALK_CORR_N↔WALK_R102 |
| 附錄每個WALL_* | WALL | OCCLUSION／COLLISION／VISIBILITY_INDEX／DISPLAY | false | 無；窗不是門 |
| 附錄每個OBSTACLE_SCREEN_* | OBSTACLE | OCCLUSION／COLLISION／VISIBILITY_INDEX／DISPLAY | false | 無 |
| CAM_W1／CAM_W2／CAM_N1／CAM_R102_CTRL | cameras[]紀錄 | 校正／DISPLAY（非objects用途擴權） | false | run binding另檔 |

每個靜態物件需source_mesh/source_object_id、實際geometry_ref/file_sha256／encoding/version、WORLD_METRES、bounds、source_method、allowed_purposes、approval_status/scope/ref/hash。bounds不可當raycast幾何；步道需polygon/holes、floor/support_surface、對稱connection；窗台與門楣是實體mesh，門洞不填滿。

safe只包含用途核准的scene_static／geometry、光學cameras、獨立run_binding、rgb_index、runtime_profile、公開查詢prior／模板及RGB推得outputs；manifest逐檔白名單。正式loader不解析private、不遞迴讀docs、不讀事件覆蓋／盲窗／actor數來決定readiness。private包含production_manifest、角色／路線／進場／動作、預期validation窗；GT／mask／visibility／depth只在輸出凍結並hash核對後才評估。公開文件含private設計值仍不准作推論輸入。

E介面：`schema_version, scene_id, scene_version, frame_id, length_unit, time_unit, world_axes, floors[], objects[], walkable[], portals[], cameras[], run_bindings[]`及每一層source/hash/purpose/pin。validator輸出`status, checked_schema_version, input_file/content_hashes, checked_purposes, issues[{code,id,field,scope,severity}], unknown_scopes, verifier_version, output_sha256`。safe與private checker分開入口；缺ID／用途／實際geometry／校正／index不回READY，完整性錯誤不降MISSING。

### 5.1 D38＋D47＋D54：模型先篩的RGB驗收計畫（未執行）

2026-10-19依[使用者D54](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6251885971)更新驗收比較與抽樣規則；[D55](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6252064337)本輪只授權序列渲染，不執行下列D47篩選。場景設計、鏡頭、路線及既有門檻不變。

既有可接的偵測器是`src/amidst/engineering/perception.py`的`produce_perception(frames, model_id=…, run_id=…)`，producer `rgb-temporal-components-v1`。它是逐鏡頭temporal median／RGB差分連通元件，**非語意person detector**；可能合併、碎裂、吃掉停留人物，不能宣稱自動辨人可靠。`perception_v2.produce_contact_v2`同時含接地heuristic，這輪不接、不改C4a，也不使用舊`contact_pixel`／local IDs當腳或身份答案。

後續獲准序列產製後，另做只讀adapter：從新run的safe manifest／rgb_index核對source/run/clock／每格hash，建`RGBFrame(media_ref,camera_id,timestamp,path,sha256,width,height)`，以新scene/run namespace逐鏡頭送入既有`produce_perception`。只讀已授權safe RGB；不使用private route／GT／mask指定bbox，不靠actorID挑component。`HASH_MISMATCH`／無效輸入整run完整性錯誤，不沿舊producer狀態把hash錯誤降成MISSING；真正預期RGB缺格另列MISSING。

1. 設計／校正投影先檢查名義1.70m高度≥112px及四邊≥16px；最小1.65m另列敏感度。這是設計檢查，非RGB準確度。
2. 偵測器先跑完**全數影格**，算`bbox_height_px=ymax−ymin`與`[xmin,960−xmax,ymin,540−ymax]`；bbox邊界約定沿現有xyxy右／下exclusive。依D54 A1保守多標：D27目標窗缺人、同格≥2人、人高<112px、邊距<16px、觸邊、全程覆蓋應有人卻無人、盲窗內有人、B1同格≥2人、merged或歧義，以及與投影不一致均標給人工；另立D47專用偵測設定，不沿用舊小目標常數。非D27 partial尾段可被保守標記，人工接受partial不改為全身。**D54 A2投影比較基準改為產製路線＋名義身高1.70m**，用核對過的校正投影，只供隔離的**CS-B驗收**：存在性不同、人物高度相對投影差>20%、中心偏移>0.25倍投影人高即標記；無法比較則記UNKNOWN並標記。這是產製設計基準，不是GT或RGB推得定位；不讀GT／mask／depth，不拿產製位置回填偵測或接地結果。路線、逐格預期投影及比較結果留在private驗收側，不進safe bundle、正式索引、檢索、排序、關聯、定位或預測；正式推論仍只能用合法RGB／校正，不放寬D1。
3. D47人工只看三類的聯集：**所有被標記格**；**D27目標窗及盲窗前後邊界格**；**其餘未納入影格的10%**。依D54 A4，盲窗前後各2格（四台共16格），另加偵測結果切換處前後各1格；不能用GT事後選格。依D54 A3，每run／camera的其餘集合以`SHA-256(seed, run_id, camera_id, index)`升冪排序，取前`ceil(.10×N)`；seed須在本輪渲染前寫進repo並記錄檔案SHA-256，渲染開始後不得修改。抽樣序列化／tie-break規格隨seed檔固定，之後記錄抽樣版本／全集hash與選中refs，不挑好看的格。數量是精確抽樣規則，不是假稱10%足以證明全程；本輪不執行抽樣。若出現漏人或額外人物，記異常、停止結案並回報，不自行擴權或宣稱通過。
4. 人工判準：目標窗看頭頂到鞋底與可辨承重足／地面交界；全程覆蓋至少頭及部分軀幹；盲窗任何人物像素即算可見。**人工優先**，逐格保留模型值／投影值／人工判讀／差異理由／reviewer／時間與refs；不覆寫原模型結果。未抽查的格明示MODEL_SCREENED_NOT_HUMAN_REVIEWED，不能叫逐格人工驗收。D47變更須在正式RGB驗收收據引用，不把D26歷史逐格文字當本輪流程。

工時設計估計（非效能量測）：safe RGB adapter與input驗證.5–1日、bbox／投影差異與抽樣收據.5–1日、人工清單／差異留存.25–.5日，合計1.25–2.5個開發工作日，偏差UNKNOWN。離線偵測執行／人工看圖工時UNKNOWN，先以四張與獲准小樣本實測再估；D33四張後仍必須停下，不因這份計畫先跑全序列。

### 5.2 未來OpenAI視覺provider介面（只預留，不實作／不呼叫）

只在使用者另行授權後，由使用者設定API key（不入repo／prompt／log），選定模型與額度。provider輸入只准送白名單**safe RGB像素**及不含答案的prompt，不送GT、private manifest／actorID／路線／盲窗答案、depth／mask、校正私有locator或整份blend。輸入schema預留`provider, model_requested, model_version_requested, safe_frame_refs[], input_rgb_sha256[], prompt, prompt_sha256, image_detail, request_budget_currency, max_cost`；key由程序環境注入，不在schema中。

輸出預留`provider_request_id, model_returned, model_version_returned(or UNKNOWN), prompt/ref/hash, input_hashes, observations[], uncertainty{method,units,bounds_or_UNKNOWN,limitations}, usage, cost{currency,estimated,actual_or_UNKNOWN,pricing_source_date}, latency, status, error, human_review`。模型回傳版本不可取得就寫UNKNOWN，不猜snapshot。記錄實際token usage與費用／可用帳單對照；費率、模型與費用上限待另授權時查證，本輪費用0（未發API請求）。輸出只作輔助證據，不可自動升為GT／人身分／腳接地／科學準確度或替人工核准。

介面僅參考[OpenAI官方Images and vision](https://developers.openai.com/api/docs/guides/images-vision)：可輸入影像，影像會計費且模型有辨識限制；這裡不選模型、不承諾費率或像素量測精度。實接估計另需.5–1.5開發日（設計估計範圍、實際偏差UNKNOWN），不在本輪後端第一批範圍。

## 6. 生成前門檻（D36–D42已決；設計餘量依§0／§4）

| 項目 | 已決規定 | 設計估計餘量／誤差 |
| --- | --- | --- |
| 正／負證據人體模型 | 看得到用1.70m／r=.25名義；看不到／同鏡雙人／淨距用1.80m／r=.30包絡 | 正證另算1.65–1.75m；模型誤差UNKNOWN |
| 身高／比例 | 身高1.65–1.75m、肩寬≤.5m | 上界對包絡高剩.05m；實體動作未測 |
| 可見判準 | 盲窗任何人物像素；全程覆蓋頭＋部分軀幹 | 幾何探針不能等同像素；以D47人工為準 |
| 外觀 | 兩人相同中性外觀 | 不用外觀給身份答案；關聯難度UNKNOWN |
| B1時序 | 固定11.0s；每鏡同格≤1人；間隔≥1.0s且中間≥4空sample | 新W2設計1.0s／4格，餘量0；見B-Q7 |
| B1空間 | 中心距≥8m，只是產製約束 | 設計最小10.220078m，餘量2.220078m，模型誤差UNKNOWN |
| 盲窗 | RGB只強制≥3.2s；4.0s僅設計目標，超過不因太長失敗；西界13.7 | 包絡bin餘量見§4；不縮短／不讀GT |
| D27 | 頭頂到腳、可辨接地；四邊≥16px、人高≥112px | 投影／偵測器／人工配合，模型先篩（D47）；餘量見§4 |
| 淨距 | 包絡外≥.10m，角屏y=[1.60,2.4] | 角屏／W／N名義.10m，餘量0；實體誤差UNKNOWN |
| 查找通路 | 10m geodesic；公開prior約1.3m/s×7.7s≈10m，不按N1位置選數字 | 乘積10.01m，與10m差.01m只是prior取整；非速度／可達性證明。沿核准walkable／portal計，不隔牆 |
| 同步 | abs(clock_error_s)≤.001s，sample_age獨立 | 同grid精確；5fps age為[0,.2)s，非時鐘容差；實際誤差待量測 |
| 光照／背景 | 固定照明／材質、景深／motion blur關閉 | RGB對比與可辨足部UNKNOWN；模型異常由人工判定 |
| D21 | 舊4×28=112px²是投影面積，非112px高度 | 不把舊面積換成新高度；strict／suggestion需合法新pins，未驗收 |

凍結前才約定的評估門檻：召回率、涵蓋率、接地誤差／區間、錯誤剪枝率、關聯正確率、效能。估計誤差實際未量測即UNKNOWN，不填0；local-track／遮擋邊界／身高軌跡／速度資格等C4a v1.1（D44）待Claude起草後確認，這輪不改。D28仍不用偵測數排序。

## 7. B包最小版計畫、D33人工審查與D41額度

**未執行。**[D49](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6250719072)已給有界的**條件式授權**，不是無條件生成；條件未全部成立就停止回報，不啟動Blender／建blend／渲染。文件push與後端fixture不能替代關卡。

### 7.0 D49執行關卡（全部成立才執行）

1. D48及本輪D50修訂已normal push到#54，記錄commit SHA並核對遠端head；文件完成記於#68。
2. D48版5c5babd已有Claude「可交使用者授權建 .blend 與四張 preview」結論；但D50明定**條件2重新計算**，須等Claude確認本輪yaw205°修訂後才成立，不能沿用舊版結論。本輪不建blend、不渲染，等待此次確認。
3. 渲染前核對、不得讀GT：整個步態側向半徑≤.30m（並遵守D42高度≤1.80m）及P2第一個可見sample=i55；按t=i/5、Blender frame=i+1，所以i55對frame56／t11.0s。必須據新產製mesh／動作與keyframe mapping核對，記方法、最大值／frame及結果；本附錄的理想圓柱／route2在i55啟動只是設計估計，**不能冒稱第三條實物核對已完成**。本輪mesh／完整步態尚未建立，第三條NOT_EVALUATED。

全部成立後依既有D49授權執行下列最小版；任一失敗或UNKNOWN均停下回報，不擅自改pose／包絡／P2時刻／門檻。真正開始前重查df，free≥12GiB才開始；任一檢查<8GiB或預估下一次寫入會低於8GiB即停（D41）。不合併、不渲染整段、不凍結、不讀GT。

1. 核對整合baseline、資源、source／hash與已決門檻，只建全新資產；正本規劃`data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r001.blend`，不複製／改原blend。
2. 按標記建同平面地板／牆／真門窗／遮屏／簡化人形與動作；產製端檢查包絡、標記、校正與safe/private邊界，不讀GT／mask驗收。
3. preview用`ctrl-lcorr-s1-preview-5fps-v1-r001`，purpose=CALIBRATION_PREVIEW、complete=false；同一B1設定與clock：W1 t0／W2 t5／N1 t19.8／CTRL t5；各1張960×540 PNG_RGB8。sample選擇只留private，不跨事件混圖。
4. **正本建好、四鏡各1張後立即停止；使用者開審查副本人工審查通過前，不跑A／B1整段、不追加診斷圖、不凍結。**需要額外圖先報範圍並取得授權。四張不是11個D27時刻或全盲／B1全段驗收。
5. 使用者審查通過且授權全序列後才產A150／B1 400張；依D47模型先篩與人工清單驗收。凍結另依契約，GT仍在凍結並hash核對後才讀；不生B2／10Hz／depth／影片／全套縮圖。

### 7.1 D33交付／版本規則

- (a) 正本：回報實際絕對路徑與SHA-256；不讓使用者直接開正本，避免存檔覆寫。
- (b) **人工查看用副本（非artifact／證據）**：規劃`data/pilot/controlled_scene_v1/review_only/ctrl-lcorr-s1-preview-5fps-v1-r001/controlled_scene_v1_s001_r001_REVIEW.blend`；與assets／run分開、ignored（本輪check-ignore確認；建立前重查）。獨立一般檔案，不用symlink／hardlink；回報實際絕對路徑、bytes／MiB。
- (c) 四張PNG：逐張實際絕對路徑、SHA-256、camera_id／sample時間；未生成前路徑與hash均NONE。
- (d) Blender物件名稱CAM_W1、CAM_W2、CAM_N1、CAM_R102_CTRL（交付核對真實名稱）；副本Outliner選鏡頭，View→Cameras→Set Active Object as Camera（Ctrl+Numpad 0），再Numpad 0看該active camera。Numpad 0本身不更換active camera。
- (e) 若實際確認乾淨，附一句「此審查副本不含GT或私有評估資料」。若做不到，逐一列副本中private人物／rig、Action／NLA、Text事件腳本／custom properties的實際名稱與用途；不以「無外部GT檔」掩飾內嵌private。外部GT／mask／depth／visibility不為此讀取，GT／評估輸出不打包；不確定寫UNKNOWN。審查不放寬D1／D26。

**正本從第一次落盤起即不覆寫。**D33前草稿修改也新增`r002`等revision，回報parent正本hash／修改摘要／新hash，重新產四張需授權且用新preview run，不把舊圖當新pose。場景geometry／校正改變時scene_version遞增（s002），asset、calibration及run binding都新版本；只修改動畫／產製設定也用新asset revision／run／clock，不覆寫任何原始輸出。封存後更不得原地存檔。

**審查副本及它的.blend1由使用者自行刪除；Codex不刪，不列為artifact、證據、manifest、pin或media allowlist。**每輪都用獨立新副本位置，不覆蓋上一輪；交付提醒「看完請自行刪除審查副本及其.blend1」。未確認使用者已刪前，每一輪副本／備份／autosave都繼續計入磁碟。正式服務不得發布`assets/`、`review_only/`、private或.blend1。

### 7.2 磁碟／工時／停止條件（設計估計，不是實測）

D41已決：新增資料＋暫存峰值≤1.5GiB、起跑free≥12GiB、free<8GiB或下一次寫入將低於8GiB即停；不清其他服務或原資產。先前17.79GiB是歷史快照，本輪未以它保證可用；生成前、每張／每批及建立副本前後重查`df -k .`。OS swap另量，不能假設固定額度。

原1.461GiB沒有計足.blend1／多輪副本；不能說加上它們仍保證1.5GiB。改為下列**兩輪情境的分配提案**，不是額外授權第二輪；每個容量為設計上限額度，實測誤差UNKNOWN，接近額度立即停，不刪副本湊額度。

| 項目 | 兩輪情境設計估計上限GiB | 誤差／計入方式 |
| --- | --- | --- |
| A+B1單份550張RGB | .398 | 原.133–.398估計，每像素.5–1.5bytes；實際壓縮率UNKNOWN |
| 兩輪四張preview | .006 | 每輪約.003，未授權第二輪；保留舊圖不覆寫 |
| 兩份revision正本／設定 | .200 | 每份≤.100，超額先重算，非blend大小保證 |
| 兩輪人工查看副本（非artifact／證據） | .200 | 每份≤.100；未由使用者刪除前全部計入 |
| 正本.blend1／副本.blend1／autosave預留 | .300 | 三份×.100的示例額度，實際每一份都盤點；更多備份即重估 |
| safe/private metadata／索引／收據 | .120 | 不預輸出GT／mask；超額停 |
| staging | .150 | **按單台camera批次計**；100張960×540、1.5bytes/pixel約.072420GiB；不整批複製550張、不ZIP；實測若超額即停 |
| optional cache | .000 | 首版不生 |
| 合計 | **1.374** | 相對1.5額度餘量.126GiB；顯示±.0005GiB，實測／swap偏差UNKNOWN |


Staging設計估計理由：單台B1最多100張，`100×960×540×1.5/2^30=.072419643…GiB`；按.072420顯示捨入±.0000005GiB，.150GiB相對單批餘量約.077580GiB，可容納約兩個單鏡批次等值（2×.072420=.144840），但不是允許維持兩份RGB。後續產製必須逐鏡／逐檔寫canonical位置、單批驗證，不做全run暫存副本；壓縮率、Blender暫存與峰值實測仍UNKNOWN，超額就停，不改額度或代刪副本。D49初版僅四張，不能用本批次估算順手產整段。若沿舊.50GiB staging，總額會是1.724GiB（超1.5約.224GiB），因此.150的前提是改為單鏡批次；不能在保留舊全量暫存流程時只改表格數字。

Blender Save Versions與autosave設定須在產製收據記錄，即使設為0也先查有無備份；不假設使用者設定相同、不代刪其備份。多於兩輪按實際正本／副本／PNG／backup逐份累加，不承諾仍能容納；若超1.5GiB停下回報容量取捨，由使用者決定，不自行清理。

工時：建模／標記.75–1.5日、簡化人形.5–1日、校正／隔離匯出.5–1日、四張交付.25–.5日，合計2–4開發日；本次設計修正與複核另約.5–1日（設計估計範圍，實際偏差UNKNOWN）。D47 adapter另見§5.1，不把模型篩選工時藏在渲染時間。四張渲染耗時UNKNOWN，排程額度5–30min只是估計，>5min／張或>30min／四張先停查；不是效能保證。hash/source/pin、原資產變動、safe/private越界、動作包絡／校正錯誤、D27不可辨或盲窗<3.2s／同鏡雙人均停止報告，不用GT補答案、不無限重渲。

## 8. 決策狀態與新取捨

| 題號 | 狀態 | 內容 |
| --- | --- | --- |
| B-Q1 | **已決定 D36** | 原平面／凹室／屏障／N1／CTRL，修W2；全部可走地板z=0 |
| B-Q2 | **已決定 D37** | 固定11s、≥1s且≥4空格、盲窗只驗≥3.2s、西界13.7、中心距僅產製 |
| B-Q3 | **已決定 D38＋D47** | 投影＋全影格偵測器先篩＋三類人工；全身接地／16px／112px；角屏1.60／.10淨距 |
| B-Q4 | **已決定 D39** | 接受partial，不承諾端點資格；舊7.2→14.8s／7.6s與新pose重算7.4→14.8s／7.4s候選均列§3 |
| B-Q5 | **已決定 D40** | 10m geodesic，公開速度×時間prior |
| B-Q6 | **已決定 D41** | 1ms與sample_age分開、1.5GiB／12／8保護，四張preview，全部備份／副本計入 |
| B-Q7 | **已決定（D48）** | R1 W2 x=14.4；角度條款由D50改yaw205°／Euler(80,0,115)取代；SCREEN_N y=[5.25,5.6]。包絡盲窗設計3.4s（餘量.2s），r=.40為3.2s；W2間隔仍1.0s／4空格、餘量0，風險以D49產製前核對處理，不改門檻 |

D42模型／比例／外觀、D45誤差說明、D47模型先篩流程都維持；D48不採P1起點前移，也不再列原B-Q7的接受零餘量／再設計選項為待決。D49只有條件式授權，具體狀態見§7.0；不是CS-B驗收或D33人工審查通過。**已依 D50 修訂，待 Claude 確認**。

## 9. 實際產出 / Actual output

### 9.1 前次6f6c800實際產出（歷史，不是本輪結果）

- Model / effort: Codex；精確model／effort UNKNOWN。
- PR / commits: 文件分支codex/office-demo-rehearsal-docs／Draft #54，本次SHA與normal push結果見#68留言；無合併／rebase／force-push。
- Files changed: 僅本設計稿；按審查七條、D36–D42、D45、D47修訂正文與可重現附錄。
- Commands run and results: `git show f481fe0:src/amidst/engineering/perception.py`唯讀確認producer介面；`gh api …/issues/68/comments`核對決策。純Python以uv在LOCAL文字稿重算，所有輸入literal，不讀GT／影像；hash／文件一致性／相對連結及`git diff --check`結果見#68。專案測試0次。
- Artifacts: 本Markdown、LOCAL純設計算術文字稿與JSON收據（hash如下）；無blend／RGB／GT／審查副本，不把未來審查副本當artifact。
- Verified: 名義／包絡分算、最矮／最高人體敏感度、A i48–49頭／軀幹探針、目標區餘量、盲窗、同鏡錯開、腳環候選、標記／walk polygon／Euler／副本版本與額度；全為設計估計。
- Not verified: 實體mesh、校正／RGB輪廓／足部／偵測率／接地誤差、C4a／K1、renderer／RAM／swap／磁碟與工時；尚未授權生成，未跑後端／推論／API。
- Deviations, UNKNOWN items and follow-ups: 原W2由包絡誤推名義覆蓋已修正；新零餘量取捨列B-Q7；D47人工範圍取代逐格人工；GT隔離不變。**設計稿已修訂，待Claude複核，尚未授權建 .blend**。

LOCAL `/private/tmp/amidst-b-design-revised.py` SHA-256 `1b9aefe7179492f209e52f3f1411ea51964f11a9e603ece1fe9ab2a9c0be7118`；LOCAL JSON設計收據SHA-256 `de0fa11416c702e019b87b58142f32a0378804b035dbed070a2913d28aea27b7`。這些只是設計文字／算術收據，不是覆蓋證據。重現命令：

```sh
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /opt/homebrew/bin/python3 /private/tmp/amidst-b-design-revised.py
```

### 9.2 前次D48修訂／D49條件狀態（5c5babd歷史，不是D50結果）

- Model / effort: Codex；精確model／effort UNKNOWN。
- PR / commits: codex/office-demo-rehearsal-docs／Draft #54；本輪commit與normal push後SHA見#68，不合併。
- Files changed: 僅本文件；W2 x、SCREEN_N尺寸、重算表／附錄、walk挖除清單、staging理由、B-Q7已決與D49關卡。
- Commands run and results: `gh api …/issues/68/comments --paginate`讀指定複核／決策；`uv run --no-project --offline --python /opt/homebrew/bin/python3 /private/tmp/amidst-b-design-d48.py`（UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache）僅literal設計算術，五種模型×550相機時間格、每鏡目標中心線301位置、A i45–49密探針／表面環、9組角度敏感度與10項平面挖除。文件一致性與git diff --check結果見#68；專案測試0次。
- Artifacts: 更新後Markdown；LOCAL純設計算術文字稿／JSON收據，非覆蓋證據；無blend／PNG／GT或審查副本。
- Verified: D48參數、設計盲窗／間隔／目標區餘量、名義與包絡接地候選、A中心與表面探針差異、walk挖除與staging算術；全部設計估計，不是實際mesh／RGB／科學驗收。
- Not verified: D49第二條使用者轉達的新版本Claude複核尚未收到；第三條整步態mesh外擴與實際P2 keyframe／首可見格NOT_EVALUATED。未啟動Blender、建blend、渲染、讀GT／影像、實測df／RAM／swap；真正生成前須重新量測。
- Deviations, UNKNOWN items and follow-ups: D48預期盲窗3.4／3.2s重現，W2間隔仍零餘量；i49中心探針出框但名義表面頭／軀幹探針仍有可見，實際RGB可辨識UNKNOWN；N1包絡腳環改i75、名義仍i74。D49條件未齊，停止於文件交接。**已依 D48 修訂，待 Claude 複核**。

LOCAL `/private/tmp/amidst-b-design-d48.py` SHA-256 `c39ae9e499e5a6ce73e60560b24a1546307a0198da9c478284831a7e4427846a`；LOCAL `/private/tmp/amidst-b-design-d48.json` SHA-256 `03183fe3bfdede08df1db60e7ff43cedd13b7c62a9f70840a65603b2cb4f147f`。均為設計算術收據，不是覆蓋證據。重現：

```sh
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /opt/homebrew/bin/python3 /private/tmp/amidst-b-design-d48.py
```

### 9.3 本輪D50實際產出

- Model / effort: Codex；精確model／effort UNKNOWN。
- PR / commits: codex/office-demo-rehearsal-docs／Draft #54；D50 commit與normal push結果見#68；無合併／rebase／force-push。
- Files changed: 僅本文件。唯一場景輸入修改是W2 yaw202→205°／Euler(80,0,112)→(80,0,115)；位置／俯角／roll／其他相機／牆盒／路線／門檻不變。同步更新受影響的設計結果與D49待確認狀態，保留舊收據為歷史。
- Commands run and results: `gh api …/issues/68/comments --paginate`核對D50／Claude複核；uv執行LOCAL純Python literal設計算術，重算五模型、A頭球／軀幹、盲窗、D27、B1、腳環、障礙間距。文件一致性與git diff --check結果見#68；專案測試0次，未執行Blender／render／推論。
- Artifacts: 本Markdown與LOCAL設計算術文字／JSON收據（hash如下）；非覆蓋證據。無blend、PNG、GT或審查副本。
- Verified: yaw／Euler與可重現附錄一致；設計估計的頭中心／可見跨度、D27餘量、時窗／間隔、包絡腳環少一格、相機位置點最小間距；不以探針數當像素或偵測率。
- Not verified: 真實人形mesh／步態、keyframe／P2首可見格、實際RGB品質／接地、校正／推論誤差、資源；D49條件2仍待這次Claude確認，第三條NOT_EVALUATED。本輪不建blend、不渲染、不讀GT／影像。
- Deviations, UNKNOWN items and follow-ups: 數字皆設計估計；頭部可見範圍是有限頭球探針投影，不是實測bbox／完整頭部。D49依D50重算條件2，不沿用5c5babd核准結論。**已依 D50 修訂，待 Claude 確認**。

LOCAL `/private/tmp/amidst-b-design-d50.py` SHA-256 `d670ab85845185bac49bb65134b62f807d26860182d8e127b7392097aa6e8674`；LOCAL `/private/tmp/amidst-b-design-d50.json` SHA-256 `70f05474a39ecc8a6338378d3c27abe9c8e3bab73f7a12126350d51d58bcc8f2`；設計算術收據，不是覆蓋證據。重現：

```sh
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /opt/homebrew/bin/python3 /private/tmp/amidst-b-design-d50.py
```

## 附錄A：D50完整設計值與可重現試算（設計估計）

不讀場景、媒體或GT；僅供產製／審查，不接正式推論。literal輸入算術±0、物理模型誤差UNKNOWN，結果誤差依§0；舊D48附錄仍在5c5babd，不用新yaw重現舊收據。

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
    return dict(pos=pos,yaw_deg=yaw,pitch_down_deg=pitch,roll_deg=0,rotation_euler_xyz_deg=[90-pitch,0,yaw-90],hfov_deg=hfov,vfov_deg=2*math.atan(270/fx)/DEG,fx=fx,fy=fx,cx=480,cy=270,sensor_width_mm=36,sensor_height_mm=20.25,sensor_fit='HORIZONTAL',lens_mm=36*fx/960,forward=f,right=right,up=up,clip_m=[.05,60])
CAMS={
 'CAM_W1':camera([-2.6,-1.4,2.0],15,16,57),
 'CAM_W2':camera([14.4,2.1,1.8],205,10,57),
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
 ('OBSTACLE_SCREEN_W',[10.4,0,0],[10.55,.8,3.2]),
 ('OBSTACLE_SCREEN_W_HOOD',[-1.65,-2,0],[-1.6,-1.23,3.2]),
 ('OBSTACLE_SCREEN_CORNER_N',[14.5,1.60,0],[14.65,2.4,3.2]),
 ('OBSTACLE_SCREEN_N',[15,5.25,0],[15.8,5.6,3.2]),
 ('OBSTACLE_SCREEN_R102',[18,7.8,0],[18.15,10.2,3.2]),
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

def visible(c,q):
 p=proj(c,q)
 return bool(p and .05<=p[2]<=60 and 0<=p[0]<=960 and 0<=p[1]<=540 and not blocked(c['pos'],q))
def model(c,x,y,r,h,n=32,levels=9):
 pts=[(x+r*math.cos(i*2*math.pi/n),y+r*math.sin(i*2*math.pi/n),h*j/(levels-1)) for i in range(n) for j in range(levels)]+[(x,y,0),(x,y,h)]
 ps=[proj(c,q) for q in pts]; clear=[visible(c,q) for q in pts]
 margins=None if any(p is None for p in ps) else [min(p[0] for p in ps),960-max(p[0] for p in ps),min(p[1] for p in ps),540-max(p[1] for p in ps)]
 foot=[(x+r*math.cos(i*2*math.pi/64),y+r*math.sin(i*2*math.pi/64),0) for i in range(64)]
 a,b=proj(c,(x,y,h)),proj(c,(x,y,0))
 torso=visible(c,(x,y,h*.80)) and visible(c,(x,y,h*.97))
 return dict(any=any(clear),full=all(clear),probes=len(pts),visible=sum(clear),margins=margins,height=None if not a or not b else abs(a[1]-b[1]),foot_ring=all(visible(c,q) for q in foot),head_and_torso=torso)
MODELS={'nominal':(.25,1.70),'envelope':(.30,1.80),'short':(.25,1.65),'tall':(.25,1.75),'expanded_r040':(.40,1.80)}
rows={}
for name,(r,h) in MODELS.items():
 A=[];B=[]
 for i in range(100):
  p1=route1(i/5);p2=route2(i/5)
  if i<50:A.append({k:model(c,*p1,r,h) for k,c in CAMS.items() if k!='CAM_N1'})
  B.append({k:{'p1':model(c,*p1,r,h),'p2':None if p2 is None else model(c,*p2,r,h)} for k,c in CAMS.items()})
 dense={k:[model(CAMS[k],6.5+j/100,1.2,r,h) for j in range(301)] for k in ['CAM_W1','CAM_W2']}
 rows[name]=dict(
  A_no_any=[i for i,row in enumerate(A) if not any(v['any'] for v in row.values())],
  A_no_head_torso=[i for i,row in enumerate(A) if not any(v['head_and_torso'] for v in row.values())],
  A_tail={str(i):A[i]['CAM_W2'] for i in range(45,50)},
  A_any={k:groups([i for i,row in enumerate(A) if row[k]['any']]) for k in A[0]},
  B_any={k:{p:groups([i for i,row in enumerate(B) if row[k][p] and row[k][p]['any']]) for p in ['p1','p2']} for k in CAMS},
  B_full={k:groups([i for i,row in enumerate(B) if row[k]['p1']['full']]) for k in CAMS},
  B_feet={k:groups([i for i,row in enumerate(B) if row[k]['p1']['foot_ring']]) for k in CAMS},
  B_blind=groups([i for i,row in enumerate(B) if not any(v['p1']['any'] for v in row.values())]),
  B_double={k:[i for i,row in enumerate(B) if row[k]['p2'] and row[k]['p1']['any'] and row[k]['p2']['any']] for k in CAMS},
  target={k:dict(all_full=all(v['full'] for v in vv),height=[min(v['height'] for v in vv),max(v['height'] for v in vv)],margins=[min(v['margins'][j] for v in vv) for j in range(4)]) for k,vv in dense.items()},
  near_W1=A[0]['CAM_W1'],north=B[-1]['CAM_N1']['p1'])
# Extra dense probes specifically for positive tail claims (not a human silhouette).
tail_dense={name:{str(i):model(CAMS['CAM_W2'],*route1(i/5),r,h,64,35) for i in range(45,50)} for name,(r,h) in MODELS.items()}
# A declared sensitivity range is not a measured calibration error bound.
sens=[]
for dy in [-.25,0,.25]:
 for dp in [-.25,0,.25]:
  c=camera([14.4,2.1,1.8],205+dy,10+dp,57)
  target=[model(c,x,1.2,.30,1.8) for x in [6.5,8,9.5]]
  pp=[i for i in range(100) if model(c,*route1(i/5),.30,1.8)['any']]
  sens.append(dict(yaw_delta=dy,pitch_delta=dp,target_min_margin=min(min(v['margins']) for v in target),last_p1=max(pp),tail_short_head_torso=all(model(c,*route1(i/5),.25,1.65)['head_and_torso'] for i in range(45,50))))

# Literal pre-cut walk polygons; independent 2D footprint clipping, no asset/GT input.
WALK_POLYGONS={
 'WALK_VEST_W':[[-3.2,-2],[5,-2],[5,0],[0,0],[0,2.4],[-3.2,2.4]],
 'WALK_CORR_W':[[0,0],[15,0],[15,2.4],[0,2.4]],
 'WALK_CORNER':[[15,0],[17.4,0],[17.4,2.4],[15,2.4]],
 'WALK_CORR_N':[[15,2.4],[17.4,2.4],[17.4,12],[15,12]],
 'WALK_R101':[[5,-5],[11,-5],[11,0],[5,0]],
 'WALK_R102':[[17.4,7],[22.4,7],[22.4,11],[17.4,11]],
}
def area(poly):
 return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2 if poly else 0

def clip_box(poly,lo,hi):
 for axis,bound,sign in [(0,lo[0],1),(0,hi[0],-1),(1,lo[1],1),(1,hi[1],-1)]:
  result=[]
  if not poly:return []
  for a,b in zip(poly,poly[1:]+poly[:1]):
   ai=sign*(a[axis]-bound)>=0;bi=sign*(b[axis]-bound)>=0
   if ai:result.append(a)
   if ai!=bi:
    t=(bound-a[axis])/(b[axis]-a[axis]);result.append([a[j]+t*(b[j]-a[j]) for j in [0,1]])
  poly=result
 return poly
exclusions=[]
for walk,poly in WALK_POLYGONS.items():
 for obstacle,lo,hi in BOXES:
  if not lo[2]<=0<hi[2]:continue
  clipped=clip_box(poly,lo,hi)
  if area(clipped)>1e-9:
   exclusions.append(dict(walk_id=walk,obstacle_id=obstacle,polygon_xy=clipped,area_m2=area(clipped)))
# Camera vs box gap; Euclidean distance to exact design AABB (point camera only).
def gap(point,lo,hi):return math.sqrt(sum(max(lo[i]-point[i],0,point[i]-hi[i])**2 for i in range(3)))
camera_gaps={name:min((gap(c['pos'],lo,hi),obj) for obj,lo,hi in BOXES) for name,c in CAMS.items()}
# Bounds for head/torso centre probes are not full silhouette margins.
tail_head_torso={name:{str(i):[proj(CAMS['CAM_W2'],(*route1(i/5),h*f)) for f in [.97,.80]] for i in range(45,50)} for name,(r,h) in MODELS.items() if name!='expanded_r040'}
extra=dict(walk_polygons=WALK_POLYGONS,walk_exclusions=exclusions,walk_base_area_m2=sum(area(v) for v in WALK_POLYGONS.values()),excluded_area_sum_m2=sum(e['area_m2'] for e in exclusions),camera_min_box_gap_m=camera_gaps,tail_head_torso_pixels=tail_head_torso,staging_single_camera_high_estimate_gib=100*960*540*1.5/(1024**3))


# Positive partial-visibility proxy: ring surfaces vs centre points are distinct checks.
tail_rings={}
for name,(r,h) in MODELS.items():
 if name=='expanded_r040':continue
 tail_rings[name]={}
 for i in range(45,50):
  x,y=route1(i/5);levels={}
  indices={}
  for label,f in [('head',.97),('torso',.80)]:
   qs=[(x+r*math.cos(j*2*math.pi/64),y+r*math.sin(j*2*math.pi/64),h*f) for j in range(64)]
   indices[label]=[j for j,q in enumerate(qs) if visible(CAMS['CAM_W2'],q)]
   pixels=[proj(CAMS['CAM_W2'],qs[j]) for j in indices[label]]
   levels[label]=dict(visible_ring_probes=len(pixels),probes=64,image_bounds_uv=None if not pixels else [[min(v[k] for v in pixels),max(v[k] for v in pixels)] for k in [0,1]])
  levels['same_azimuth_head_and_torso']=len(set(indices['head'])&set(indices['torso']))
  tail_rings[name][str(i)]=levels
extra['tail_surface_rings']=tail_rings


# D50 positive visibility design: a head sphere, distinct from the old r=.25 head ring.
def projected_visible(c,qs):
 ps=[proj(c,q) for q in qs if visible(c,q)]
 return dict(visible_count=len(ps),total_count=len(qs),uv_bounds=None if not ps else [[min(p[k] for p in ps),max(p[k] for p in ps)] for k in [0,1]])
head_torso_design={}
for name,H in [('nominal',1.70),('short',1.65),('tall',1.75)]:
 head_torso_design[name]={}
 for i in range(45,50):
  x,y=route1(i/5);c=CAMS['CAM_W2']
  centre=(x,y,H-.10)
  sphere=[(x+.10*math.sin(j*math.pi/12)*math.cos(k*2*math.pi/24),y+.10*math.sin(j*math.pi/12)*math.sin(k*2*math.pi/24),H-.10+.10*math.cos(j*math.pi/12)) for j in range(13) for k in range(24)]
  torso=[(x+.25*math.cos(k*2*math.pi/32),y+.25*math.sin(k*2*math.pi/32),H*(.45+.10*j)) for j in range(4) for k in range(32)]
  head=projected_visible(c,sphere);body=projected_visible(c,torso);center=proj(c,centre)
  head['visible_horizontal_span_px']=None if not head['uv_bounds'] else head['uv_bounds'][0][1]-head['uv_bounds'][0][0]
  head_torso_design[name][str(i)]=dict(head_sphere=head,head_center_uv_depth=center,head_center_visible=visible(c,centre),torso_cylinder=body)
extra['d50_head_torso_design']=dict(head_radius_m=.10,head_center_height='H-.10',sphere_sampling='13 polar levels including duplicate pole probes x 24 azimuths; 312 probes, not pixels',torso_radius_m=.25,torso_height_range_fractions=[.45,.75],torso_sampling='4 height levels x 32 azimuths; 128 probes, not pixels',rows=head_torso_design)

out=dict(label='DESIGN_ESTIMATE_NOT_COVERAGE_EVIDENCE',cameras=CAMS,opaque_design_boxes=BOXES,models=MODELS,rows=rows,tail_dense=tail_dense,w2_sensitivity=sens,d48=extra,rounding_error='display to .001: +/- .0005 of displayed unit; sample boundary quantization .2s; physical error UNKNOWN',input_model_error='AABB/cylinder and finite probes; not mesh/RGB evidence',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
Path('/private/tmp/amidst-b-design-d50.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(json.dumps(out,indent=2))
```
