# r004 靜態兩層圖與出口 ROI 提案收據

Refs #116、#113/PR #155/#162、#104/PR #150、#117、G4。**PROPOSED／DRAFT，未核准用途，不是正式凍結圖。** 人工校閱靜態畫面及loader結構通過，不代表拓撲、光學可見性、物理通行或Q5辨識品質已驗收。

## 來源與檔案

只讀#113 v2 safe_static：無人物8張960×540畫面、cameras與靜態mesh。沒有讀事件RGB、人物設定、路線、GT、逐幀visibility／depth；不是從人物走法反推候選圖。source SHA `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`；static geometry bytes SHA `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a`；cameras bytes SHA `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`。WIDE 90°依使用者選擇及原pin，未改source或重渲染。

| Git相對檔 | 內容 | bytes SHA-256 |
|---|---|---|
| configs/q1q5/graphs/r004/region_graph.PROPOSED.json | 7區域、6個人工拓撲連結 | f29bc01b0e3fccdd12eda34ba4403b701b91561e172f26243fa9a50a3621c56c |
| configs/q1q5/graphs/r004/camera_transition_graph.PROPOSED.json | 8相機／8出口、17個保守跨區路徑提案 | e5c96ed00b957b3df2096a5c4f642004784ca33e20c77cb32ae4109fd00b50c1 |
| configs/q1q5/graphs/r004/roi_mapping.PROPOSED.json | 作者、每台靜態圖與校正／ROI pins、PENDING_117_G4 | 341aacebd64003f56767fa5236dcbfd86d0e1e763c46c3f17890ee486a068538 |
| configs/q1q5/graphs/r004/region_meshes.PROPOSED.json | 直接引用靜態walk/floor mesh頂點與面，保留洞／分片，不以AABB補地面 | 4dd2861ded335a9b31454672d3ed1591405f5c53644ccc9df64736cfccdb8a8c |

Region graph content hash `23efa9f86f565ab5f0a3628d6ed6ed5badff91aef9b1ae10752206b0f951a436`；camera graph content hash `b3014759550cb0280e04fcdc0139c27d4ba1f47201173a1cba81d8b5d1097132`。兩個產品graph沿既有schema用approval_status=DRAFT／approval_ref=null；檔名、ROI sidecar和圖上文字明標PROPOSED，沒有新增假核准enum。

## 每台出口（靜態人工提案）

LOCAL `/Users/polalabear/amidst-artifacts/r004-graphs-proposed-20261021/` 含8張 `<camera_id>.EXIT_PROPOSED.png`、生成腳本build116.py與完整ARTIFACT_HASHES.json。橘色是出口**接近區域**提案，不是測量過的物理門檻線，也不是偵測框或人物答案。點位在相應原圖像素內，無全畫面邊緣兜底。未覆寫原圖。

| camera_id | 對應出口edge提案 | 接近區域 |
|---|---|---|
| CAM_W1 | E_W_CORNER | 長廊遠端地面、向轉角 |
| CAM_W2 | E_VEST_CORR | 向西側前室的遠端門口地面 |
| CAM_BRANCH | E_CORNER_N | 轉角前地面 |
| CAM_WIDE | E_CORNER_N | 北廊南端接近轉角地面 |
| CAM_R101_IN | E_PORTAL_R101 | 室內門口的地面帶 |
| CAM_ENTRY | E_OUT_VEST | 朝室外開口可見的地面區 |
| CAM_EXT_CAR | E_OUT_VEST | 車後方門口僅剩的小塊可見地面 |
| CAM_EXT_CLEAR | E_OUT_VEST | 清楚外景中的門口地面帶 |

每台一個exit_zone，帶static_frame_sha256與calibration_sha256。CAM_EXT_CAR地面可見範圍很窄、ENTRY近門檻未完整在影像內，兩者尤其需#117檢查；不能因有多邊形就稱出口語意正確。入口ROI尚未另標（entry_zones=[]）；沒有杜撰測量面積或path長度。covered_regions只做靜態人工提案，visible_area_m2=null、relation=UNKNOWN，非已核准D1 visibility index。

## 權限、缺口與凍結條件

現有scene_static是proposal格式、allowed_purposes=[]，不是已核定O10/G4 safe bundle。故**所有6個edge及17個path皆TOPOLOGICAL_ONLY，state UNKNOWN**，包括PORTAL_R102維持限制。尚無合法自動切鏡路徑；不能填APPROVED_WALKABLE只求Demo跑起來。

只列能保守描述的跨區路徑，沒有補齊8×7全矩陣。同區鏡頭重疊（如W1/W2）、完整涵蓋範圍、反方向出口、entry ROI、雙向拓撲及車遮擋尚未獨立驗證。**候選完整性UNKNOWN**；軟體snapshot的candidate_set_complete僅描述已宣告圖內top-k截斷，不能升格成物理世界相機完整性。原walk mesh之間有覆蓋／分片關係，不能直接把其包圍盒當可通行空間。

下一步由#117檢查每張圖、點位對應、靜態連結與來源；使用者G4核定允許用途及合法路徑後另版凍結。任何修圖須新版本與原因，保留本批hash。D68要求事件渲染之前完成凍結與獨立檢查，故#115仍不能先跑；此提案不是解除G4的替代品。

## 實際驗證

`load_graphs`用上述content pins載入成功；逐台移除exit並重封hash的8次探針均回EXIT_ZONES_MISSING；8個**SYNTHETIC bbox結構探針**得到0合法候選、拓撲路徑排除，不是假稱真實人物追蹤。原版#127 v0.2.1 @994d34c的DOCUMENT_LOADABLE／SCHEMA_VALID／CONTENT_HASH_RECOMPUTE／GRAPH_STRUCTURE／GRAPH_CROSS_REFERENCES／candidate hash/order/topological-exclusion共49 PASS。報告與探針存LOCAL artifact，沒有修改kit。

`git diff --check`為本任務另項focused。產製前後df-k及8GiB門檻均記錄，沒有刪檔或渲染。NOT_VERIFIED：#117/G4、每個出口物理／語意正確性、全相機候選完整性、正式事件／HSV／index／Controller／browser。
