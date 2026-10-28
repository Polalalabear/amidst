> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# 系統端口、label 指引與差異歷史 / System ports and label guidance

2026-10-11 第一個工程 checkpoint 範圍。所有新增能力接入同一個 8016 工作台；本 checkpoint 使用
synthetic/mock、既有 frozen inputs 與本機 MockAgent。正式 Phase 1 gates 另行保留。

## 來源與目前排除範圍

本專案的實際媒體有兩種：Blender 3D 模型內 camera 的來源影像，以及依原
`.blend` geometry、預設平滑展示材質呈現的 3D 模型。兩者都是模擬來源；
camera 截圖不等於實體攝影機。平滑材質只影響顯示，不改 `.blend`、geometry、
校正、物理核准或推論。程序式 E0/E1 RGB 是明確標記的替代測試影像，不能改稱
Blender camera 截圖；既有 overlay/audit stills 不改稱未標註的 tracking sequence。

真實攝影機串流標記 FUTURE；正式帳號與部署標記 DEFERRED，不列入本次待交付。
不新增 `.blend` 副本或 render。原始場景、正式 dataset/config、GT 邊界均保留。

## 本日後續 Blender checkpoint

後續已接入三組既有未標註 Blender camera RGB（共 300 PNG）與來源局部平滑模型，
於同一工作台執行不經 Agent 的基底 Top-K 畫面檢索。這三個新場景不是下文的 E0/E1
程序影像／LOCAL_MOCK 工作流；其實際 RGB、相機校正與 source-bound floor 投影均已
重跑，Graph／delta history 仍用獨立替代資料。三組各 11/11 ports PASS（9 actual、
2 substitute），影片端口另列 DEFERRED。詳細當前資料流、具體 request/response、
Top-K 與未完成項目見 [Blender camera frame retrieval](BLENDER_CAMERA_FRAME_RETRIEVAL.md)。
下文 2925 tests／22 HTTP／10 ports 等數字保留第一個 checkpoint 日期與收據，
不當作後續 Blender checkpoint 的完整驗證結果。

## 第一個 checkpoint 實際完成與尚未完成

| 層級 | 實際完成 | 尚未完成／限制 |
| --- | --- | --- |
| 來源與媒體 | 既有來源模型局部 mesh、camera 診斷影像與明示 E0/E1 替代 RGB；平滑材質只改顯示 | 未新增 Blender camera tracking sequence；局部 mesh 不是完整學校建築；實體串流 FUTURE |
| 量測、投影、Graph | 實際 RGB pixel producer、校準投影、有方向圖與盲區候選；假資料端口閉環 | 真實訓練模型及正式學校精度／完整物理核准未完成 |
| 狀態與儲存 | 原 frozen repository、SQLite 交易、人審版本、delta replay；四階段模擬併發 | 正式多人部署容量與長時間壓力測試未完成；帳號／部署 DEFERRED |
| 語意與 label | dataset 時間／地點；行走、跑步、出入意圖；圖與索引整理有限 summaries | preset 不是自動辨識或人工正式核准；正式語意仲裁未完成 |
| Agent | typed AgentInput/Output、LOCAL_MOCK、最多兩次實際 detail actions，禁止全域掃描 | 外部模型、完整 RAG 與 token 減量測量未完成 |
| 工作台 | 3D 主畫面、保留 canvas／視角／解碼影格、按需節點邊標註、event ID 只在 log | 歷史缺失素材與 status-only artifacts 保留；沒有通用自動 fallback |
| 分層驗證 | 十個端口實際調用、22 次 HTTP、四階段併發；替代資料與原 run 隔離 | 工程 PASS 不等於正式研究 gates 通過；formal Cases 2/3 與 full Exit 仍 BLOCKED |

## 確切資料流

| 端口 / interface | 輸入 | 輸出與下一站 |
| --- | --- | --- |
| `synthetic.generate_sequence → perception.produce_perception` | 2 cameras、51 frames/camera、5 Hz、0–10 s、無 GT 標註的 RGB | 102 PNG；camera/frame/time、media ref、SHA → pixel producer |
| `perception.produce_perception → association.build_inference` | RGB bytes、camera/time/static context | bbox、contact pixel、camera-local track、status/uncertainty、producer/hash → projection |
| `association._project → observation aggregation` | contact `(u,v)`、明確 calibration/plane、clock/metres | PROJECTED point、world XYZ、region/source refs；缺失狀態保留 → visible segments |
| `aggregation → Graph/reconstruction` | 完整可見 Observation、GAP endpoints、directed navigation、speed/time/budgets | BoundGapEvents、全部 configured routes/timings、termination/complete → canonical snapshot |
| `canonical snapshot → LOCAL_JSON repository` | 原 observations/events、source/config/freeze hashes | re-open 相同 IDs/content/order；不能重新聚合成新 ID → indexed retrieval |
| `camera/time index → label preprocessor` | 登錄 label、camera、有限 time range、使用者行為意圖、top_k | 有界 graph nodes/edges、必要 feature summaries、opaque refs、讀取量/截斷 → AgentInput |
| `AgentInput → LOCAL_MOCK → typed detail tool` | 僅 preprocessor 給出的 scope/features/allowed actions | 未確認身分與 UNKNOWN behavior；保留供應的 alternatives；最多 2 個 detail actions → 執行 digest/count 收據 |
| `frozen event → replay/workbench` | event ref、來源 timestamp、完整 hypotheses | 所有 hypotheses 的 presentation markers；插值標 INFERRED_GAP，不修改 inference |
| `review edits → delta document` | baseline source/version/hash、實際修改欄位、理由與驗證 | source-bound changed-leaf patch；可由相同 base 還原，無影像/GT/.blend 副本 |

上表是程式內模組端口，不是每層另開一台 network server。人類可見的實際 HTTP
入口皆在 `http://127.0.0.1:8016/api/...`，由 server-owned role/session/scene 守門。

| HTTP endpoint | request 的具體資料 | response 的具體資料 |
| --- | --- | --- |
| `semantic_presets` | session_ref、scene_id | dataset place/time/cameras、navigation/observations/behavior labels、預設選項 |
| `navigation_guide` | 上述 scope、label、camera_id、start/end、behavior、top_k | guide_ref、status、AgentInput、明示 LOCAL_MOCK 的 AgentOutput |
| `agent_decision` | 同 session/scene 的 server-issued guide_ref | 原 AgentInput、MockAgent 決策、實際 bounded detail 執行收據 |
| `system_ports` | session_ref、scene_id | **獨立假資料**的實際逐層 input/output、PASS/FAIL、Agent I/O、GT-poison 比較 |
| `storage_probe` | session_ref、scene_id、stage | 隔離 SQLite 的 readers/appends/publish_conflict/reopen_replay 結果與 counts |
| `export_delta` | session_ref、scene_id、published version ≥1 | changed-parts JSON document、source/base/parent/result hashes，不輸出整個場景 |
| `logs` | session_ref、scene_id | 端口 action/status；event refs 只在 log/內部 transport 用於追蹤 |

系統端口 probe 會建立新的短期 E0 fixture，實際調用現有 producer、projection、Graph、
repository、query、MockAgent、replay、review/delta，再污染 fixture 的 GT sidecar重讀。
所選 operator scene 並不是該 probe 的輸入，也不被修改。這是工程接口證據，不是原場景
的精度測量、formal school benchmark、完整 production 或高併發容量認證。

本次具體樣本：CAM_A／t=0 的 bbox=[34,159,59,203]，contact pixel=[46,202]；
合法affine地面投影得到 world=[0.7894736842105263,2,0]m。102張RGB產生89個量測、
6個local tracks與4個canonical gaps。端口中的candidate/hypothesis counts指示範選取的
一個event（1 route／1 timing），不是四個events的合計；完整snapshot/replay仍保留其餘候選。
可核對[本次實際端口收據](../../data/engineering/workbench_20261011/system_ports.json)。

另一份 [Agent navigation 收據](../../data/engineering/workbench_20261011/agent_navigation.json)
使用工作台既有 **E1 operator scene**，不是上述短期 E0；它讀原 run/freeze，不重新推論。
兩者的 source/model/clock 各自綁定，不能把 E0 的 102 張 RGB 與 E1 的 guide counts
合併當成同一條執行紀錄。

## label → 必要資料 → Agent

時間與地點取自已登錄 dataset；使用者選取行走、跑步、出入作為調查意圖。
此 preset 不直接成為已辨識行為或身分真值；缺少支持時仍為 UNKNOWN。

匯入 frozen scene 時一次建立 label aliases、camera/region 節點、有方向 configured
links 與 feature summaries。查詢時使用有界 BFS 與已存在的 camera/time index，
先縮小可查資源再回傳有限 summaries。UNKNOWN/AMBIGUOUS label 回 NEEDS_INPUT，
不改用全資料掃描。最大 3 hops／12 nodes／24 edges／4 camera queries，HTTP top_k≤5；
每個 feature 最多 8 個有序 candidate refs，省略數量與 detail references 一起保留。
每個 feature 最多 4 個 media refs，保留 omitted_media_count／MEDIA_REF_BUDGET；
AgentInput 不含照片 bytes。agent_decision 執行 detail 後回傳 digest/count，
不自動取照片或 replay；replay 由其獨立端口以 frozen event/time 執行。
這個 top_k 是上下文摘要上限，與原 Graph route Coverage@K 分開。
序列化AgentInput另有64KiB上限，超過則拒絕，沒有偷偷裁改既有資料或宣稱token節省。

AgentInput 保存 selection、source/run/clock/freeze scope、navigation_nodes/edges、features、
budget、telemetry、allowed_next_actions、不確定性。AgentOutput 明列 provider=LOCAL_MOCK、
selected_refs、全部供應的候選 refs、next_bounded_actions、confirmed_identity=null、
behavior_verdict=UNKNOWN。Agent 沒有 repository/filesystem/任意 SQL 或 catalog scan tool。
這個實作是 token 兜底的前處理原型，尚未量測 tokenizer、外部模型 token 減量或 RAG 精度。

具體 E1 測試輸入為 `label=navigation`、`camera_id=WEST`、時間 `[0,24]` 秒、
`behavior=walking`、`top_k=3`。前處理輸出給 Agent 的內容為 7 個 nodes、11 個 edges、
3 個必要 features，以及限定 source/run/freeze、budgets 與 allowed_next_actions。
實際讀 3 個 camera queries／127 records／177 index entries、0 frames／0 media bytes，
回報 FEATURE_TOP_K_BUDGET 與 scoped_inventory_complete=false，不宣稱窮盡。
MockAgent 輸出 `provider=LOCAL_MOCK`、`confirmed_identity=null`、`behavior_verdict=UNKNOWN`，
並提出兩個 get_event_detail；server 實際執行後，每個收據確認原有 3 candidates／6 hypotheses
與 response hash。完整 typed input/output 見上述 E1 收據；畫面不展示 event refs。

## 分層測試、併發與歷史文件

各層保持可替換 producer-neutral 契約。上游失敗時，用另一個明確 SYNTHETIC test run
的合法 fixture 繼續測其他層；來源/clock/unit/hash 不一致會拒絕，不以假資料回填正式 run。
本次不新增通用自動 fallback。

SQLite 併發分階段測：同時讀取、獨立追加、同 base 的雙發布競爭、關閉重開與 delta replay。
使用獨立 worker connections、起跑 barrier、完成 counts／conflict／integrity；不以不穩定
latency 門檻宣稱效能。測試資料庫與原操作資料庫分開。

可發布歷史只有修改部分的 document；v0 source/baseline 只作 hash binding與還原依據。
Git 普通 commit/push 保存 code/docs/tests/curated evidence 與合成 delta；raw DB、RGB、GT、
MP4、RRD、source archives、`.blend` 不納入。實驗資產仍依既有明確授權與隔離規則處理。

3D 為主要工作畫面；camera 影像是可展開的證據。原畫布與最後完整 frame 保留，晚到回應
不能換掉新 scope。節點/邊標籤是 registered/configured 關係，不授予物理可達或語意核准。
事件 ID 不在正常畫面或技術資訊呈現；內部 refs 和專用 log 保留診斷能力。
圖形仍保留全部由 AgentInput 供應的來源節點與邊；該 scope 本身受圖形 budgets 約束。
預設只標註目前鏡頭，按需最多顯示五個簡短標籤，
完整關聯可展開文字，不為畫面清楚而截斷 Agent 圖形資料。
歷史診斷圖片中已烘焙的文字保留原始bytes，與新的正常介面欄位分開；沒有修改影像來源。

## 本次驗證

完整 `pytest --require-physical-evidence -rs`：2925 passed，零 failure/error/skip；
前端 Node：工作台 58、產品 13，共 71 passed；Ruff src/tests 與 strict mypy 186 sources 通過。
真 HTTP 22 次涵蓋合法資料流與角色／scope／budget 拒絕；十端口與四併發階段全部 PASS。
實際瀏覽器確認預設 3D、按需圖形標註、Agent I/O、端口展開與併發結果。
可核對[本次驗證與 source/code hashes](../../data/engineering/workbench_20261011/validation.json)。

## English

This milestone adds local synthetic interface probes, import-built bounded label navigation,
user-selected walking/running/enter-exit intent, an explicit MockAgent input/output contract,
phased SQLite concurrency checks and source-bound delta documents. It preserves source assets,
canonical alternatives, truth isolation and independent formal research gates. Real camera
streaming is future work; accounts and deployment are deferred. The project media are Blender
camera images and source-bound model presentation with smooth display material; procedural
RGB fixtures remain labelled substitutes. No `.blend` is copied or rendered.

HTTP actions share the existing workbench/session boundary. The system probe uses its own fresh
fixture rather than mutating the selected frozen scene. Graph-guided summaries constrain Agent
reads; labels and behavior presets are intent, not identity or behavior truth. No external model,
token saving, RAG accuracy or production capacity is claimed. Delta exports contain only changed
document parts and verification metadata. The stable 3D workspace keeps IDs in logs only.
