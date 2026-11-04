# 術語表

返回 [README](README.md)。

| 術語 | 意思 | 出處 |
| --- | --- | --- |
| **查找（case1）** | 給時間範圍與地點或特徵，回傳拍到目標的鏡頭畫面 | [D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045)；[SPEC §1](SPEC.md#1-case1-查找) |
| **追蹤（case2）** | 給特徵，畫面跟著看得到目標的鏡頭切換；盲區時顯示俯視圖與物理預測 | D126；[SPEC §2](SPEC.md#2-case2-追蹤) |
| **單畫面／多畫面** | 追蹤的兩種顯示：單畫面只播目前追蹤所在的鏡頭並自動切換；多畫面顯示所有找到目標的鏡頭 | D126；#408 |
| **查看** | 所有畫面一次顯示，不做追蹤 | #408 |
| **系統模式／單純模式** | 系統模式顯示完整證據與標籤；單純模式只留畫面與演示時間，證據不足時顯示「證據不足」 | 運行手冊 §10@`796cc17`（#406） |
| **Q1～Q5** | 舊的五項目標：Q1 依條件找相機、Q2 找畫面中某個人、Q3 自然語言轉查詢、Q4 判斷畫面是否含目標、Q5 目標離開時是否切鏡。D126 後，Q1 對應查找，Q2／Q5 對應追蹤 | `docs/specs/Q1Q5_PRODUCT_SPEC.md`@`796cc17` §1.1 |
| **OBSERVED** | 從來源畫面的偵測直接得到的證據 | `AGENTS.md`@`796cc17`；[SPEC §3](SPEC.md#3-證據狀態) |
| **INFERRED** | 系統依規則或圖推出來的結果，例如切鏡決策、物理預測 | 同上 |
| **MISSING** | 應該有、卻沒有的資料，例如沒有 RGB 的鏡頭 | 同上 |
| **UNKNOWN** | 系統不知道；在文件裡也代表「讀不到出處」 | 同上 |
| **UNCONFIRMED** | 身分未確認；跨鏡頭只是條件相符的候選 | `Q1Q5_PRODUCT_SPEC.md`@`796cc17` §1.2 |
| **GT（Ground Truth）** | 渲染時已知的真值：人物軌跡、mask、可見性、深度、劇本。只給評分與除錯，不進推論 | `docs/DEVELOPMENT_RULES.md`@`796cc17` 第 56 行 |
| **`gt_private/`** | 渲染輸出中放 GT 的資料夾；推論端、前端與外包工具都不可讀 | `frontend/event-viewer/README.md`@`796cc17` |
| **safe bundle／safe 區** | 渲染輸出中可以給推論端用的部分（RGB 影格等），由 checker 驗結構與 hash | `docs/engineering/CX7T_EVENT_BUNDLE_CHECKER_20261029.md`@`796cc17` |
| **RT-DETR** | 物件偵測模型；本專案用 R18、COCO 80 類，離線建偵測索引 | `src/amidst/q1q5/detection_index.py`@`796cc17` |
| **COCO** | 物件偵測常用的 80 類標籤集（person、car、chair…）；別名表 `class_alias_v1.json` 把中文用語對到這些標籤 | `configs/q1q5/class_alias_v1.json`@`796cc17` |
| **HSV 顏色證據** | 用 HSV 色彩判斷人物衣服顏色（STRONG／WEAK），只用在 person | `Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §6.1 |
| **偵測索引** | 離線跑完偵測後寫成的 JSONL 紀錄；查詢只讀索引，不在查詢時補推論 | `Q1Q5_PRODUCT_SPEC.md`@`796cc17` §2 |
| **region_graph（區域圖）** | 場景的區域與通道；通道只表示「依配置可能連通」，通行性 `UNKNOWN` | `configs/q1q5/graphs/r004/region_graph_v3_1.json`@`796cc17` |
| **camera_graph（鏡頭圖）** | 每台鏡頭涵蓋哪些區域（`covered_regions`）、出入口與鏡頭之間的轉移 | `configs/q1q5/graphs/r004/camera_graph_v3_1.json`@`796cc17` |
| **`covered_regions`** | camera_graph 中某台鏡頭看得到的區域，人工在靜態畫面上標（`MANUAL_ON_STATIC_FRAME`）；地點查找靠它 | 同上；[SYSTEM_ARCH §3](SYSTEM_ARCH.md#3-地點查找region_graph-與-camera_graph) |
| **tracking scope** | 哪些鏡頭可追蹤、哪些只供查找，以及可用的有向鏡頭對 | `configs/q1q5/graphs/r004/tracking_scope_v3_1.json`@`796cc17` |
| **G4** | r004 兩層圖 v3 的使用者核准關卡（#348）；目前 `G4_approved=false` | [D113](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6575688787) |
| **D28 排序** | 候選鏡頭的決定性排序規則；Agent 不排序、不增刪候選 | `DEVELOPMENT_RULES.md`@`796cc17` 第 63 行 |
| **Q2 linker** | 同鏡頭內以 IoU 把偵測連成軌跡；不做跨鏡頭身分 | `src/amidst/q1q5/linker.py`@`796cc17` |
| **RULE_ONLY／AGENT_SEQUENTIAL** | Q5 切鏡的兩種模式：純規則，或由本機 Agent 依序取證後決定（超過上限由規則兜底） | `Q1Q5_PRODUCT_SPEC.md`@`796cc17` §2 |
| **TEMP_LOST／SEARCHING／SWITCH／RETURN_TO_ORIGIN** | 追蹤狀態機的狀態與動作：暫失、搜尋中、切到其他鏡頭、回原鏡頭 | `Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §8.6 |
| **GAP／盲區** | 沒有任何鏡頭看到目標的時段 | #397 §E.3.2 |
| **fail-closed** | 條件不足時選擇「不做」而不是猜，例如圖未核准就不切鏡 | D113 |
| **物理預測** | 盲區時依最後偵測框的方向與鏡頭圖，推算目標可能出現的下一台鏡頭與時間窗；只是示意，不是路徑 | `docs/contracts/DEMO_UI_SUPPORT_V1.md`@`796cc17` §6 |
| **俯視圖** | 追蹤畫面旁的鏡頭位置圖；實線＝已觀測，虛線＝物理預測 | 同上 §7.1 |
| **宣告時鐘（DECLARED_DEMO_CLOCK）** | 每個 run 宣告的展示時鐘，把來源時間換成台灣時間；是設定，不是實際拍攝時刻 | `Q1_Q2_FIRST_DEMO_V1.md`@`796cc17` §3.1 |
| **來源時間** | run 內從 0 開始的整數微秒時間 | 同上 |
| **實際倍速** | 播放跟不上設定倍速時，自動降速後實際達到的倍速，顯示在播放列 | D126-4；#408 |
| **run** | 一次渲染產生的一組多鏡頭畫面，共用一個時鐘，例如 A4-1、B4-1 | 同上 §3.1 |
| **r004** | 目前的合成場景版本（`scene_id=controlled_scene_v1_s001`、`scene_revision=r004`） | `camera_graph_v3_1.json`@`796cc17` |
| **A4-1／B4-1** | r004 的兩個複雜人物事件：A4-1 50 s 4 台鏡頭，B4-1 42 s 5 台鏡頭，5 fps | #397 §E.1 |
| **P1 v4 包** | demo 用的工程場景包：A、B 兩台，各 160 張 PNG、20 fps、8 s；LOCAL | [D113](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6575688787) |
| **B-05a／B-05b** | demo 的兩段追蹤：live（fail-closed）與預錄（5.15 s 切到 B） | D113 |
| **#118／CX-8** | A4-1／B4-1 的偵測索引任務與 RULE_ONLY 追蹤任務 | [D124](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061) |
| **SYNTHETIC／ENGINEERING／RECORDED／LIVE** | 資料來源標示：合成資料、工程用、預錄回放、即時計算（LIVE 是運作模式，素材仍是合成） | 運行手冊 §0@`796cc17` |
| **LOCAL** | 只在本機、不進 repo 的檔案（RGB、錄製、權重） | `AGENTS.md`@`796cc17` |
| **merge commit only** | 合併只用 merge commit，不 squash、不 rebase，因為文件引用 commit SHA | 同上 Git workflow |
| **實際產出（Actual output）** | 每個 PR 與 issue 必寫的結果紀錄模板 | 同上 Checkpoints |
| **D 編號** | #93 上的決策編號，例如 D126 | [#93](https://github.com/Polalalabear/amidst/issues/93) |
| **待補** | 數字或內容還沒產生；不自己編 | 本文件包寫法 |
