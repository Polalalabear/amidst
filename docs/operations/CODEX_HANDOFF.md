# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

日期：2026-10-13。重用 checkout：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`。
目前工程 branch 為 `codex/simulation-engineering`；文件整理基線 `codex/docs-agent-handoff / 2c586b1` 已包含在其中。研究基線仍是
`phase1/finalization-sprint / 883204af854bed301506b39d63ccb33312b79ff2`，HEAD／origin 以實際 Git 為準。Canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 immutable scene/raw
artifacts，不在那裡實作或切換 branch。

### 新工程範圍與入口

<!-- PUBLICATION_CLEANUP_HANDOFF_20261013_BEGIN -->
目前GitHub工程tip為 `93eb6119c453d3daa067890f597f5aa4b4ea1d04`；本機已另有
`001a0fc3b3b3b99d0c9e04bc666f5345db246faa` 的A＋B＋C checkpoint，仍未push。
世界方向／幾何修改屬另一對話，保持未提交；本輪文件更新不處理其程式或人工資料。
先前指定push、exact93eb611的1061／213／12隔離驗證與本機證據位置見
[工作紀錄](../history/WORK_LOG.md#publication-cleanup-20261013)；不當成001a0fc或正式研究的測試。
下一步依[清理條件](PHASE1_ARTIFACT_CLEANUP.md#cleanup-review-20261013)保存獨有資料，
8768服務退役前保留preview；候選分類未授權刪除。本輪不push、merge或刪除。
[main盤點](PHASE1_ARTIFACT_CLEANUP.md#main-integration-20261013)優先評審已發布93eb611，
不可直接以目前分支名稱帶入001a0fc；A＋B＋C品質限制、research/frozen與c5956dc保留條件另列。
<!-- PUBLICATION_CLEANUP_HANDOFF_20261013_END -->

固定 TaskContext、LocationRegistry、typed tools、summary/detail/media/replay references 與輸出邊界，禁止 Agent 掃描整個資料庫或 repository。本階段 **SYNTHETIC_ENGINEERING_ONLY / NO_EXTERNAL_MODEL_CALLS**。依 2026-10-11 指示，token 兜底已先實作圖形／label 前處理原型；外部 API 接線仍空白，未量測 token 減量或 RAG 精度。

入口見 [Agent 檢索契約](../engineering/AGENT_RETRIEVAL_BOUNDARY.md) 與 [擴大工程續作 prompt](PHASE1_NEXT_CHAT_PROMPT.md)。可在同一 checkout 連續完成多個可執行 milestones，每段驗證、commit、普通 push 對應工程 branch；不為每段新增 worktree/clone/raw 副本。文件分類見 [導覽](../README.md)；正文按分類存放；必要的機器路徑與不可變核准文件見該頁說明。

工程閉環與原正式研究驗收並行。下方既有 corridor／formal blockers 保持有效。

### 2026-10-13 本對話的 Phase 2 授權範圍

已交付01範圍接續、02 accuracy v2調查接入、03 v2認證評估/比較，統一在8016。
01–03已完成；本輪結果以 [01–03 契約](../engineering/WORKBENCH_INVESTIGATION_GALLERY.md) 及
[新收據](../../data/engineering/workbench_010203_20261013/validation.json)為準：Python3222、Node183、
Ruff／strict mypy201檔、隔離HTTP86請求／939斷言及8016瀏覽器驗證PASS。原研究與人審權限不由此擴大。

- **COMPLETED_APPROVED_BATCH**：06固定來源任務、manual／assisted與持久化排演評分；04先支援單一E0既有RGB流程的新run、停止與來源綁定比較，入口仍是8016。範圍見[04／06契約](../engineering/WORKBENCH_RUN_STUDY.md)，結果見[本輪收據](../../data/engineering/workbench_0406_20261013/validation.json)：Python3325、Node213、Ruff／strict mypy204來源檔、隔離HTTP147請求／2881斷言PASS。06仍是PREPARATION_REHEARSAL，不等於15實際操作員驗收。
- **VALIDATED_LOCAL_ENGINEERING_WITH_UNMET_QUALITY_GATES**：05獨立精度實驗、09合成診斷、10區域出入與持續停留、11本機Qwen2.5 7B Agent原型、12實際PostgreSQL已整合8016「調查與品質」。完整Python3436、共享Node230／本批獨立快照225、Ruff／strict mypy224檔PASS；實際HTTP、模型停止／恢復及重啟、PG實際dump／restore、8016瀏覽器及原來源保留驗證完成。05測試switches4→5／fragmentation7→8，保留baseline，改善目標未完成；11真實題組6／8自動通過但語意品質未認證，`QUALITY_GATE_NOT_MET`。Phase2功能工作量暫估50%（45–55%），未達條件式60%目標。契約及限制見[本機A＋B＋C整合](../engineering/PHASE2_LOCAL_BATCH_ABC.md)，實際結果以[最終總收據](../../data/engineering/phase2_abc_20261013/validation.json)為準，各驗證總数不累加。
- **DEFERRED / REQUIRES_USER_CONFIRMATION**：07真實錄影、08真實偵測/追蹤、09真實/訓練ReID、10其他單人與全部多人事件、13串流、14帳號/部署、15實際操作員驗收。

接續核准11回答品質修正、05局部追蹤修正與整合驗收：**R1 demo已交付／R3 frozen48執行中**，目前工作台8016已載入typed evidence v2；逐欄核對、UNKNOWN分母、原需求／語言／scope持久化、拒絕與舊案唯讀均接入。05唯一候選development無strict gain，test(4,3,7,6)→(3,2,7,6)，缺採樣7未達≤6，維持baseline。新封存合成測試集與其他項目仍暫緩。操作、當次驗證及main依賴見[05／11修正](../engineering/PHASE2_LOCAL_REPAIR_0511.md)與[新收據](../../data/engineering/phase2_repair_0511_20261013/)，舊ABC數字不改寫，完成數不累加。Phase2品質結果尚未認定通過，暫維持50%估算；本批不merge／push，研究frozen refs不變。偵測main由另一對話推進至3991b79，當前main候選依即時審核。

其餘項目不得由本輪A＋B＋C完成自行開始；既有功能與獨立人工核對對話的原授權各自保留。
原 Phase1 formal gates 與 frozen Phase2 donor/tag 不變，沒有公開發布、push 或 main merge 的新增授權。

### 2026-10-13 最新人工核對階段

<!-- PHYSICAL_HUMAN_REVIEW_20261013_BEGIN -->
最新工程階段為 **AWAITING_ACTUAL_HUMAN_REVIEW**；來源門洞、走廊連通與人體淨空尚未確認。
完整分層資料流、來源證據、缺失與實際／替代測試只維護於[人工核對契約](../engineering/BLENDER_PHYSICAL_HUMAN_REVIEW.md)。

| 情況 | 待核對項／檢查 | 本階段狀態 |
| --- | ---: | --- |
| Office | 4／14 | 有7組原來源見證，保持UNKNOWN |
| CLASS101 | 3／10 | 走廊50來源影格／0投影，完整人體域缺失 |
| Auditorium | 4／14 | 保留原截斷候選與缺失，完整人體域缺失 |

共11項／38檢查；三站實際人工revision均0。本機差異儲存與併發測試只用SUBSTITUTE輸入，
不代替使用者確認，不改正式來源權限。可逐項記錄UNKNOWN／本機支持／本機矛盾及來源引用，
只存修改欄位、前一本機狀態與hash chain；確認後的限制匯入／Top-K／曲線／影片重跑尚未執行。
工作台上方導覽；主畫面可手動切換「3D 模型」／「2D 分時畫面牆」，
8／12／16格均為登錄鏡頭的時間抽樣，可選完整／前段／中段／後段並同步來源時間軸。
來源annotation／支持面／見證僅作核對預覽；原高度、孔洞與預覽截斷保留，
名義人體線框只表示已核准政策尺度，未量測實際身形；缺失時不外推或補人物。
本輪Python3186、Node160（workbench147＋product13）、Ruff／strict mypy199檔PASS；HTTP154請求／5119斷言與三站browser核對PASS。精確範圍依
[本輪收據](../../data/engineering/blender_physical_review_20261013/)核對；前一2de9821的3140／122／60 ports／175 HTTP保留歷史。
既有Top-K／曲線／影片不重排、不重編碼；不由Agent／GT作決策，不開啟、修改或複製原.blend。
<!-- PHYSICAL_HUMAN_REVIEW_20261013_END -->

### 2de9821 來源物理篩選歷史 checkpoint

<!-- PHYSICAL_FILTER_20261013_BEGIN -->
2026-10-13 已實作來源物理篩選：完整有界池先檢查再重排，不只篩舊Top-5；
來源有25個局部碰撞scope／58構件及1F59片支持面，門孔／完整局部身體域核准均0。
PARTIAL缺失仍UNKNOWN；原secondary連接區間、孤立點與支持點分開去重檢查，
長缺口保持MISSING，不掃端點直線、不補detour；空資料基線／ledger也UNKNOWN。
Office池5解，原3／4／2→新Top-3、原1→新4仍保留；CLASS101只有1基線，
走廊單鏡頭NO_RESULT；Aud池256截斷、原前三未變。三站硬排除0，全UNKNOWN。
主支持區間0/26、62/68、38/89；Aud secondary2/2、獨立點0/1，不能混入主加分。
原Office／Aud相機同名，以site／run／dataset隔離，名稱／site描邊不證明房間歸屬。
當次Python3140 PASS／0 fail／0 error／0 skip／527.69秒；Ruff／mypy197檔PASS；
Node122（工作台109＋product13）PASS。端口60/60（54實際＋6替代）無deferred；HTTP175／501 PASS。
v2各站curves.png／reconstruction.mp4／manifest.json位於ignored
`data/engineering/local_run/blender_physical_v2/{site}/`，三PNG／三MP4全解碼，
各影片1280×720、5 fps／50影格／10秒，共300精確來源RGB；原source與v1九檔不變。
三站實際播放、seek／手動／Play／雙影片交接與ended末影格9.8秒通過，console零警告／錯誤；[新收據](../../data/engineering/blender_physical_20261013/validation.json)只綁本次範圍，
不沿用2026-10-12歷史完整回歸。發布SHA／remote以實際Git為準，不能預編commit。
完整層級資料流、實際／替代測試及來源hash見[唯一物理契約](../engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md)。
續作保留身份／行為未確認、Class缺觀測與Aud非全域最優；不升權mesh／bounds，
不經Agent／GT決策，不開啟、改動或複製原.blend，不接串流、正式帳號或部署。
<!-- PHYSICAL_FILTER_20261013_END -->

本次從fc73eca工程基線接續；原association producer不變，工程unknown不解除formal gates。

### 2026-10-12 跨鏡頭 Top-K 與同步呈現入口

接續4b43aed的camera-local milestone，已實作每組site／run／clock獨立的
`BaselineAssociationIndex`與研究API `cross_camera_reconstruction`／issued-reference
`cross_camera_media`。時間、設定速度與合法floor幾何形成暫定跨鏡頭候選；Top-K
保留唯一邊配置，另有排序外未關聯基線，不確認人物／行為、不湊足K。
3D工作台可選候選／基線，路徑、XYZ／速度曲線與原camera時間游標同步，保留原canvas／
視角／DOM。同期支持點保留各鏡頭原投影，不平均；≤1秒合法短橋另標推斷，較長中間
位置MISSING，原局部hard gaps仍列出。同site同源以外不合併，floor-only不是碰撞或
可行走核准，沒有GT兜底或Agent決策。

| 情況 | nodes／合法edges／拒絕edges | 本次結果 |
| --- | ---: | --- |
| Office | 5／4／0 | Top-3；5個唯一配置完整枚舉，另保留baseline |
| CLASS101 | 6／0／0 | 1個baseline／`NO_CROSS_CAMERA_EVIDENCE`；走廊50來源／0投影／MISSING |
| Auditorium | 19／52／32 | Top-3；beam256截斷、10850次評估、`complete=false`，不認證全域最優 |

canonical關聯／排名採所選鏡頭完整來源0–9.8秒；查詢窗只裁切顯示，事件及路徑refs
保持來源綁定。預先物化的跨鏡頭影片固定全鏡頭／完整來源／請求K=3，與query及選定rank
不同時必須明列；GET只核對hash／讀取，不產制。原`.blend`／PNG唯讀且不複製。

**本次驗證完成：**完整Python3067 PASS／0 skip／443.27秒（`--require-physical-evidence`）；
Node110 PASS（工作台97＋product13）、Ruff／mypy193來源檔PASS；三站各16/16端口
（14實際＋2隔離替代），合計48/48（42＋6）且0 deferred；fresh HTTP160 requests／
450 assertions PASS、issues=[]。核心34項已包含於完整Python總數，不額外累加。
三站各1份PNG／MP4已物化，100次來源RGB選取／站，1280×720、H.264／yuv420p／faststart、
5 fps／50影格／10秒，無ffprobe的full decode fallback PASS。
瀏覽器三站播放、候選／排序外baseline、Class走廊MISSING、Aud截斷、3D／曲線／camera
時間同步、native video seek4.8秒、來源時間軸暫停影片、窄窗2–4秒K1／單鏡頭與完整K3
素材caption分開均PASS；source Play接管影片後RGB／3D／曲線同進至9.8秒，
console0 warning／error。原`.blend` SHA／468300506 bytes／mtime不變。
本次收據綁529檔code-tree SHA
`a341e5a10c5786643c06f8c37fd8c4d853fe8b8f59b649c6b32fc503a15a9739`及7份整理收據hash；
提交／遠端SHA以Git核對為準，發布僅普通工程branch push，不預編commit或宣稱main合併。
4b43aed的3017／92／98等驗證保留歷史，不代替本次結果。尚未完成的是正式身份／行為、
整場碰撞／可行走、Class走廊投影及Aud完整搜尋列舉，不把本次工程PASS當正式核准。
入口見[跨鏡頭契約](../engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)及
[新收據](../../data/engineering/blender_association_20261012/validation.json)。
正式Cases2／3／full Exit、Phase2 frozen與main邊界維持原狀；真實串流FUTURE、帳號／部署DEFERRED。

### 2026-10-12 Blender 位置／速度曲線與還原影片入口

已實作 `BaselineMotionIndex`、同相機局部track位置／速度曲線及8016的
`motion_reconstruction`／issued-reference media入口；三站曲線PNG／影片已實際物化，
完整解碼均PASS。此為2026-10-11之後的新milestone；下方影片DEFERRED記錄保留
當時狀態，現在的素材與解碼證據見2026-10-12收據。

來源仍是三情況的300張既有Blender RGB與安全pixel／floor-projection快照。
`PROJECTED_OBSERVATION`不是直接觀測3D；≤1秒、有效兩端、同camera-local track且
≤設定8 m/s時，才能線性補成`INFERRED_INTERPOLATION`。速度是原投影端點區間中點
的`INFERRED_FINITE_DIFFERENCE`。長缺口、失敗投影與超速保持MISSING／斷線；
不跨鏡頭／track／site／run合併，不外插。窄查詢不重建canonical事件IDs或端點。

同組實際資料的暫定全來源結果如下；tracks與點數不是人數或辨識精度：

| 情況 | 局部tracks | 投影點 | 插值點 | 缺失點 | 區間速度點 | 斷開區間 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Office | 3 | 31 | 0 | 0 | 26 | 2 |
| CLASS101 | 6 | 70 | 4 | 0 | 64 | 0 |
| Auditorium | 10 | 82 | 19 | 12 | 63 | 18 |

CLASS101的CORRIDOR04有50張來源影格，但0像素觀測／0投影，覆蓋狀態MISSING，
沒有該鏡頭track曲線。Office斷開2個SPEED_CAP；Auditorium斷開7個SPEED_CAP與
11個INVALID_PROJECTION。8 m/s為工程configured cap，floor-only basis不授予全場
碰撞／遮擋／可行走或人類物理核准，人物身分與行為均未確認，合成目標／活動保留。

操作及新物化指令見[Blender曲線與事件還原](../engineering/BLENDER_MOTION_RECONSTRUCTION.md)。
每情況影片1280×720、H.264／yuv420p／faststart、5 fps、50影格／10秒，完整來源範圍
0–9.8秒；每站100次來源RGB選取均為 `SOURCE_RGB_EXACT`。環境無ffprobe，三站以
`FFMPEG_FULL_DECODE_FALLBACK` 完整解碼PASS；三站provider manifest及六份媒體讀取
均PASS。完整Python驗證（含physical evidence）3017 passed／357.78秒，無fail／error／skip；
Node 92 PASS（workbench 79＋product 13），Ruff／strict mypy 191來源檔 PASS。最終HTTP
98 requests／254 assertions PASS、`issues=[]`；三站各13/13端口（11 ACTUAL_BLENDER＋
2 SUBSTITUTE）及六份媒體binary／hash／range／scope守門均PASS。

瀏覽器三站1280×720／10秒影片實際播放無decode error；Office seek7.838899秒與camera
同步通過，CLASS101 CORRIDOR04明列50source／0projection／50missing，Auditorium單鏡頭
2–4秒查詢與完整all-camera影片caption分開。scene切換清除舊影片，最終console無warning／error，
一般畫面不顯示opaque event IDs；source_integrity核對原`.blend` SHA／size／mtime不變。
本次整理證據放在[data/engineering/blender_motion_20261012](../../data/engineering/blender_motion_20261012/)，
與2026-10-11 receipts分開，不回寫歷史。原 `.blend`／PNG不改動、不複製；
串流FUTURE，帳號／部署DEFERRED，GT與formal／Phase2 FROZEN／main邊界不變。

### 2026-10-11 Blender camera RGB 與基底畫面檢索

目前 8016 catalog 共六個獨立情況：新增 `blender-office`、`blender-classroom101`、
`blender-auditorium`，加上既有 E0、E1、accuracy-v2 三個工程 fixtures。Blender 三情況
共接入 300 張實際來源 camera PNG；各情況兩鏡頭、每鏡頭50張、5 Hz、0–9.8秒。
同名camera仍按site/run分開，沒有混用Office與Auditorium的影格。

Blender 查詢不經 Agent。class-agnostic RGB producer 實際重算像素元件／local tracks，
以來源 camera calibration 與核准 floor plane 投影，再從有界 camera/time index 輸出
deterministic Top-K 畫面訊息。排序保留鏡頭多樣性、品質／投影優先與具體rank理由；
score不是機率，身分未確認、行為仍UNKNOWN。原模型 evaluated mesh以預設平滑灰材質
呈現 **PARTIAL source context**，不能改稱完整 `.blend` 或整場物理核准。

三情況各自實際重跑端口 **11/11 PASS**：9個ACTUAL_BLENDER、2個獨立SUBSTITUTE；
另1個事件曲線／還原影片端口DEFERRED，不計入完成數。Graph gaps與delta history由另外
臨時E0 fixture實際測試，source/model/run/clock/hash另綁，不當作Blender事件候選或曲線。
Fresh pixel index與各operator index一致，外部模型／Agent calls均0；原 `.blend` 未改動、
未複製，沒有實體串流或新增影片。PNG公開服務只去除文字metadata，原檔與IDAT保留。

資料種類、操作與下一段事件物理曲線／影片工作見
[Blender camera畫面檢索](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md)。本次整理收據：
[來源盤點](../../data/engineering/blender_workbench_20261011/scene_inputs.json)、
[畫面查詢](../../data/engineering/blender_workbench_20261011/frame_queries.json)、
[Office端口](../../data/engineering/blender_workbench_20261011/office_ports.json)、
[CLASS101端口](../../data/engineering/blender_workbench_20261011/classroom101_ports.json)、
[Auditorium端口](../../data/engineering/blender_workbench_20261011/auditorium_ports.json)。
本節不沿用下方歷史完整測試數作為本次回歸結果。

後續以已取得的像素、投影、時間及來源引用準備物理候選曲線與事件還原影片；目前尚未產生。
真實串流FUTURE、帳號／部署DEFERRED；formal Case2／Case3／full Exit、GT隔離及Phase2
FROZEN狀態保持原樣。既有E情況的MockAgent功能保留，不接到Blender基底判斷。

### 2026-10-11 有界 label 指引、系統端口與差異歷史

操作入口仍為 8016，共用工作區提供 dataset 的時間／地點／鏡頭，以及行走、跑步、出入
使用者意圖；navigation／observations／behavior label先由圖與索引整理有限特徵，再交
LOCAL_MOCK，顯示 Agent input/output 及最多2次實際 detail calls。未知label需要補充輸入，
不全域掃描。候選與UNKNOWN保留；selection不是已識別行為。

測試與評估新增整條假資料端口與隔離SQLite四階段併發；每個端口可展開輸入輸出。
本次[收據](../../data/engineering/workbench_20261011/http_validation.json)有22次真HTTP，
[資料流](../../data/engineering/workbench_20261011/system_ports.json)10/10 PASS，
[併發](../../data/engineering/workbench_20261011/storage_concurrency.json)4/4 PASS。
完整Python回歸2925 PASS／0fail／0error／0skip，Ruff PASS、strict mypy186sources。
前端58workbench＋13product，共71 Node PASS；實際瀏覽器確認3D／按需標註與各測試入口。
source/code hashes另綁[本次validation](../../data/engineering/workbench_20261011/validation.json)；
歷史2873等結果不回寫。

新published版本在SQLite只保存source-bound changed-leaf delta，讀取時由v0與父版本還原；
既有完整rows保留相容，draft仍保留單一修改對象的驗證上下文。匯出只含修改文件與hash，
例如[合成delta](../../data/engineering/workbench_20261011/synthetic_delta.json)。不複製.blend／raw。
3D canvas／renderer／視角與已解碼影格保持，晚到回應不換scope，事件ID只在log；
節點／邊顯示既有關係，沒有物理pose的節點不捏造座標。

媒體定義為Blender camera來源影像與依原.blend／預設平滑展示材質的模型；程序式RGB另標
測試替代。真實串流FUTURE，正式帳號與部署DEFERRED。Formal Case2／Case3 detour-growth／
full Exit仍BLOCKED，Case4 DEFERRED、原Phase2 FROZEN；其他未知與缺失維持原狀。
具體契約見[系統端口與label指引](../engineering/SYSTEM_PORTS_AND_LABEL_GUIDANCE.md)。

### 2026-10-10 主平台實作續作

8016 已接 [來源模型與行走](../engineering/SOURCE_PRESENTATION_WORKBENCH.md)、
[人物調查與展示庫](../engineering/WORKBENCH_INVESTIGATION_GALLERY.md)。Source P14 的
122workbench／19Node／16HTTP evidence綁c8c66e9，原receipt不回寫。後續integration
加入E1 product12actions／四鏡頭MP4／case/report、三個獨立scenes與15family192PNG；
[新receipt](../../data/engineering/workbench_20261010/integration_validation.json)綁當次code/config/
source/freeze及完整回歸，不沿用歷史2652。缺失素材與status-only RRD仍分開標示。
當次無排除required-physical-evidence **2873PASS／0fail／0error／0skip**；Ruff src/tests、
strict mypy183sources、58Node、63真HTTP與actualbrowser操作通過。原BlenderSHA/size/mtime
不變；raw／GT／192PNG／影片／RRD未stage。只發布code/docs/curatedreceipts。

第三scene local-camera-accuracy-v2 是 end_to_end/plus/RESULTS；source run仍local-camera-test-v1，
experiment accuracy-test-v2-final／namespace／config／freeze另綁。29segments165events保留
5SUPPORTED／7UNKNOWN／153GAP_ALTERNATIVES，不借E1 evaluation digest；v2 scene評估入口
UNAVAILABLE，已發表三列比較與7cards走human gallery。E1/E0及原productfreeze未替换。

評估aggregate DTO／獨立內容digest、發布後test/evaluation cache、評估文字已修復。
Typed plans的NEEDS_INPUT不殘留舊plan、晚到responses不換scope、有限batch stop/resume與
原server markers/measurement timestamp保留；body/gait皆DISPLAY_ONLY。啟動：
`uv run --offline --no-sync python -m amidst.workbench --port 8016`。
研究輸出仍低精度／未定；不作formal Phase1驗收或外部模型／token證據。

下方2026-10-08盤點／2652等測試保留日期基線；「待遷移」項目現況以本節與新覆蓋表為準。

### 本機 Phase 2 產品續作

最新使用者決策：**frontend/workbench／8016 為唯一主要網頁入口**；既有與後續頁面能力
都接入該工作台。frontend/product／8020 保留為已驗證工程lab／待遷移來源，勿繼續擴張
另一套主要前端。Product後端／資料／typed tools可供工作台adapter使用；目前未完成遷移，
不可把兩個獨立入口說成已統一。工作台相關規則／決策已接入工程分支。

2026-10-08 網站盤點見 [實驗展示覆蓋表](../engineering/WORKBENCH_EXPERIMENT_COVERAGE.md)。
8016 實際 catalog 僅 E1／E0，固定讀 `photos_plus_observations/RESULTS`；實驗展示
尚未全部接入。有效續作：

- 把 product intent／typed plans／stop-resume／案例／appearance tools／報告與 MP4 同步
  接入工作台 server-owned role/scope；現有 backend／資料可重用，主平台尚無相應操作。
- 為 Office recovery benchmark／Rerun、歷史 preview／projection／downstream 展示補
  source/context/clock/unit adapter；覆蓋表區分 checkout／canonical-only／缺失素材。
  新 corridor 全案例正式成果尚未完成，不能用已有部分展示替代。
- 補 evaluation aggregate DTO allowlist／內容 digest 認證（matching headers 仍可返回額外
  JSON 欄位）；sentinel-only probe 未發現或聲稱真資料外洩。發布後使 cached test 結果失效，
  並修正評估面板的 GT 文字；後端新檢查仍正確報 `NEEDS_RERUN`。

本輪只有網站操作、十次 HTTP 核對、素材與文件盤點；下面 2652 等為歷史程式驗證。

P7–P12 在同一工程分支接成可操作的 [本機產品](../engineering/LOCAL_PHASE2_PRODUCT.md)：
SQLite immutable read model、RGB-crop appearance／provisional same-camera stitching、有限
中英 intent→typed dynamic plans、多目標 inquiry／衝突與全部替代、四鏡頭影片／Three.js／
soft-sync timeline、持久案例／stop-resume／報告／独立 operator review／HTML export。
新 `product.run.v1` 以 source/dataset/config/producer/registry/media/algorithm/freeze hashes
核對；GET／reload 不重跑推論、不讀 GT。原 M1–M6、E1 canonical IDs/fields/order 及素材保留。

操作：`uv run --offline --no-sync python -m amidst.product serve --output data/product/local_run/operator_v2 --port 8020`，
瀏覽 `http://127.0.0.1:8020`；依賴、build/demo/evaluate/HTTP驗證與新的 empty output 重現命令見產品指南。
原 RGB source/CV 2.5Hz，15fps MP4 只重用實際影格；不是新增15Hz照片／observation。
Agent 的13tools與operator views均受 server-bound scope/stage守門，無任意SQL／shell／archives。

當次 **2592 tests PASS／0 failed／0 skipped**（required physical evidence、明確排除並行
tests/workbench）；Ruff PASS、strict mypy159files PASS。前端13Node tests／actualbrowser、
初次77＋process restart後69真HTTP PASS；新empty output11份fixed documents逐byte一致、
4public query pairs相同。見 [validation](../../data/product/checkpoint_20261008/validation.json)。
2592/159不包含正在獨立開發的workbench；其驗證與文件由該工作階段另存，不混入本次PASS。
並行雙角色／場景切換／人審版本的 [共用工作台](../engineering/SHARED_WORKBENCH.md) 使用8016，
其獨立 [desktop receipt](../../data/engineering/workbench_20261008/desktop_validation.json)
與當次product測試相互排除，未把兩份PASS相加為新的full結果。
最後共享branch另做無排除的實際full整合：**2652passed／0fail／0error／0skip，255.995s**，
Ruff／mypy164files及兩前端28Node PASS。新增product test package namespace修正同名
test_service collection failure；原失敗log保留。此新full結果不來自兩份局部PASS相加。

五個 eligible pure-track appearance queries 的Recall@1/3/5=.4/.6/.8（同pool baseline=.2/.6/.8）；
六個mixedtracks排除、stitch TP1/FP2、四組unknown保留，global IDF1 N/A。這是有限synthetic
diagnostic。Full formal／新school攝影機／trainedReID／PostgreSQL或vector部署／external model
仍未交付，原Cases2/3/fullExit BLOCKED、Case4 DEFERRED、原Phase2 branch/tag FROZEN。

### 局部跨鏡頭與行為研究續作

[局部 pilot](../engineering/LOCAL_CAMERA_PILOT.md) 已依 [R1–R8 交接](LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md) 完成可操作的 E1 synthetic extension；[protocol](../research/LOCAL_CAMERA_EVENT_PROTOCOL.md) 與 [curated receipt](../../data/engineering/local_camera_20261008/validation.json) 固定scope、版本、同run hashes及當次驗證。原 M1–M6 registry／RGB tracks／provisional v1／simulation-v2 不變，新 `local_association` 與 `local_behavior` 是外層版本化composition，不改原BoundGapEvent／Graph排序。

目前 `local-camera-test-v1` checkpoint：4 cameras／244 pinhole RGB／150 measurements／18 local tracks；真正scope/ref／camera-time／region/portal index在形成pairs前沿可達拓樸擴查。115 local pairs對照153 global diagnostic pairs，獨立條件式next-segment reference 8/8取回；不是未檢出人物的整段recall。Pair precision/recall 0.35/0.467；轉角／可能遊蕩仍有誤報，進出門在bounded identity評估仍未定。完整feature消融、混淆／缺失與限制見receipt；不宣稱唯一人物身分或行為意圖。

可直接開啟loopback8012（原8010保留）查局部camera/time事件卡、3–5實際RGB、局部3D候選與replay；操作／重建命令見pilot文件。Final artifacts位於ignored `data/engineering/local_run/local_camera_v1/test/checkpoints/final`，同一RGB materialization被development/test各自新freeze重用。2427 full tests／Ruff／mypy145files、34真HTTP、378MockAgent calls、瀏覽器操作、同run GT poisoning與empty-output hash reproduction當次PASS；formal clean-checkout與school authority未因此解鎖。

2026-10-10 [研究精度 v2](../research/LOCAL_CAMERA_ACCURACY_V2.md) 已交付獨立 frozen runs、
固定 pool／端到端比較、消融與只讀 typed adapter；當次 [receipt](../../data/engineering/accuracy_20261010/validation.json)
綁 implementation `48bfd49` 與170項 scoped回歸，不是全repo PASS。原v1／P8與並行工作台保留；
新output在 `data/engineering/local_run/accuracy_v2/{development,test}/final`，factory為
`amidst.research_accuracy.adapter.load_service`。Consumer須保留 `SUPPORTED/UNKNOWN/GAP_ALTERNATIVES`。
有效待續：追蹤碎片與讀取成本增加、融合不勝過所有消融、corner/wandering仍漏報、dwell新增誤報；
不能直接混比producer改變後的pool／eligibility。原Cases2/3/full Exit BLOCKED、Case4 DEFERRED、
Phase2 FROZEN仍有效。舊RESEARCH_PLAN/NOT_RUN標頭只屬歷史基線。

### 已接入的工程能力與續作邊界

`codex/phase1-preview-workspace / 04c699d` 已以 merge commit `ded5572` 接入目前工程分支；50 frames／58 verified images 的 view-only playback 可由原 exact inputs 重建。Projection branch `8f4055f` 的四個 model helpers 已在研究基底中；本次僅補相容的 comparison／surface-control／downstream／robustness 診斷工具，保留 sidecars，不改 Graph 權重或 domain schema。

FROZEN Phase 2 checkpoint `5b51d2c` 的 repository、read-only API、legacy replay importer 與 TypeScript consumer 已選擇性接入。使用 [Phase 2 整合](../engineering/PHASE2_INTEGRATION.md) 的本機啟動命令與 [本次驗證 receipt](../../data/engineering/integration_20261008/compatibility.json)。這是 SYNTHETIC_MOCK_ONLY 接口：GET 讀固定 snapshot、保留 canonical observation/event IDs 與候選順序，不重跑 inference。

工程基底 `4271b2b` 的完整測試 **2255 passed／0 failed／0 skipped**，含 Blender／physical evidence；Ruff PASS，strict mypy PASS（125 source files）。該checkpoint的25次實際loopback HTTP requests與Node consumer／replay驗證通過，既有318個核心／腳本／測試檔、29 inputs、297 review records及immutable source不變；這不是後續M1/M2或目前草稿的全測試重跑。

M1–M6 已實作：source/context/clock/unit registry／media、真實未標註 RGB 與 pixel local tracks、兩種輸入與 stage/freeze 守門、provisional associations／Graph adapter、八個 strict typed Agent tools、MEMORY／LOCAL_JSON fixed reads、MockAgent／互動照片與3D alternatives replay、independent evaluation／reproduction。操作與完整界限見 [模擬工程](../engineering/SIMULATION_ENGINEERING.md)，本輪 [validation receipt](../../data/engineering/simulation_20261008/validation.json) 綁定 source hashes／run／config。

當次2351 tests PASS／0 failed／0 skipped（required physical evidence），Ruff／strict mypy138 files PASS，36真HTTP及4events／12TypeScript replay PASS；只排除並行local research草稿，詳見receipt。

目前 local run `data/engineering/local_run/simulation_v2`：2 cameras／102張5Hz RGB、89量測／6tracks、21association records、4canonical gaps／8routes。使用既有環境執行 `uv run --offline --no-sync python -m amidst.engineering serve --run data/engineering/local_run/simulation_v2 --port 8010`；瀏覽 `http://127.0.0.1:8010`。完整GT只在simulation/export與local evaluation/debug；photo入口只有獨立synthetic-lab-v1，沒有虛構school RGB tracking sequence。Office importer certificate僅為structured recovery partial，native BU不回寫，0.0247 m/BU顯式normalize。

Pixel recall為83/129（64.34%，24px eligibility matching），mean contact error3.09px／ground error0.102m；這些是獨立fixture診斷，association identity accuracy及formal指標N/A。Same-camera為HOLD，overlap不偽造gap，全部歧義／incompatible alternatives均保留。兩模式使用相同照片，photos-only從pixels重算；未使用GT兜底或external model。

原 `phase2/integration-hardening` 與 tag 保持 FROZEN；新增碼只在工程分支。不 merge `main`，不改原 Blender/source、locked inputs 或正式研究狀態。外部模型 API 仍空白；token 前處理現況依上方2026-10-11節。

### 恢復 checkpoint 的既有證據

以下是 `883204a` 所記錄的 runtime 恢復工作；本次工程整合的測試另見上方 receipt，不與恢復紀錄混用。
該恢復工作因舊 `/private/tmp` worktree 與 raw outputs 已不存在，從已發布
`5c2b67b9c48ae4028fd9fb2e7636f6b3af5121c0` 恢復到上述持久路徑。
使用 locked Python 3.12.12；29 個原鎖定輸入與297份 review package 檔案均驗證，
physical evidence 為 VERIFIED。完整測試 **1978 passed／0 failed／0 skipped**，
Ruff、mypy 與 source CLI strict mypy 全 PASS。執行指令見 [恢復後運行指南](PHASE1_RESTORED_RUNTIME.md)，
該恢復工作的實際檢查見 [recovery receipt](../../data/finalization/recovery_checkpoint_20261008/validation.json)。
新的 office 5 Hz export → V3 inference freeze → evaluation → ready-case reproduction
已實際完成；27列 baseline、45列 ablation、兩個 reader-verified RRD／PNG 在
`data/finalization/reviewed_run_recovery_20261008/`。這是既有核准 office 流程的重新運行，
新 corridor 全案例研究交付仍待下列工程。原 source/核准/config/producer bytes 保留。
歷史 V3–V8 bulk raw 與舊獨立 `/tmp` 輸出目前不存在；Git 中 curated receipts 仍在。

使用者已核准精確 corridor proposal，要求準備新對話，完成一個可重現 dataset、
一份 benchmark 結果表、一個 Rerun 3D demo，綁定同一 frozen run。直接使用
[下一對話 prompt](PHASE1_NEXT_CHAT_PROMPT.md)；完整實作起點、原因／解法與交付驗收見
[研究成果續作交接](PHASE1_RESEARCH_RELEASE_HANDOFF.md)。

原 HR01–HR04 4/4 APPROVE 且 applied；獨立 reference MOVING/departure-DWELL policy
已核准並在既有 office run 中使用。新 corridor proposal content SHA
`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad` 已直接人工核准，
[receipt](../../data/finalization/reviewed_corridor_scope_approval_v1/human_decision.json) content SHA
`702c2f7ca8165fc7669072847e26f38174b6525ed104999e35b467d23cebda09`。
六個 cells 原數值 application 全通過，完整 union certificate SHA
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`。
Historical independent clean `d8b94a6` regeneration **PASS_LOCAL_UNION_REGENERATED**；
該恢復工作再執行原完整數值重建亦通過；原 hashes 見
[current checkpoint](../../data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json)。
不重問既有核准；歷史 review/strict-preview/V5 packet 保留原 bytes。

Phase1 仍 **PHASE1_FINALIZATION_BLOCKED / PARTIAL_APPROVED**。Case2／Case3 detour-growth
尚缺 scoped pipeline adapters、source-bound same-camera HOLD、相同 actual eligibility 的
canonical directed graph 與獨立 exhaustive inventory、新版本 config freeze、fresh 5 Hz
export/inference/evaluation/benchmark/demo、完整 clean-checkout reproduction。
舊 office CLI 不能直接消費新 union application。原 Graph 允許 repeated edge sequences、
CameraTransition 拒絕 self-transition；不能用 simple-cell DFS 冒充 exhaustive 或假造
CAM01 handoff。Lower-bound proof 的 recall N/A/readiness=false；V7 sample39 的真實 recovery
與兩段分開 GAP 必須保留。
原 Case2 `PORTALS_WITH_TWO_SIDED_ACCESS` 仍須查核既有 approved portal/anchor 證據；
新 corridor receipt 不新增 portal role，不能由 HOLD／分支數代替此 gate。

恢復 checkpoint 的 fresh office 局部成果：Case1／Case3 temporal A/B/C、27列 baseline、45列
ablation、RRD/PNG 與 ready-case reproduction；Case2 BLOCKED rows 保留。
[Collision V4 fresh receipt](../../data/finalization/reviewed_checkpoint_v4/manifest.json) 僅證明
`8cb0df3` 的既有 delivery。Source preparation `d8b94a6` 的1978 tests／zero skips、Ruff/mypy
是歷史 code validation；恢復工作重新運行的測試、資料流程與數值重建另存 recovery receipt。

完成／歷史證據見 [WORK_LOG](../history/WORK_LOG.md)、[final report](../research/PHASE1_FINAL_REPORT.md)；
持續規則只留在 [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md)。原29 inputs／57 frames、
HR／reference policy／protocol／V1–V3 locks、source asset 全部保留。
Case4 **DEFERRED**；Phase2 `phase2/integration-hardening / 5b51d2c` **FROZEN**。
原 full Exit Gates 全過才 freeze，不 merge main。

## English

<!-- PUBLICATION_CLEANUP_HANDOFF_20261013_EN_BEGIN -->
GitHub engineering is pinned to 93eb611; local 001a0fc contains the separate A+B+C
checkpoint and is unpublished. Concurrent direction/geometry edits remain untouched.
See the [dated log](../history/WORK_LOG.md#publication-cleanup-20261013) for the prior
push and exact 93eb611 scoped tests; they do not certify 001a0fc or formal research.
Follow the [cleanup conditions](PHASE1_ARTIFACT_CLEANUP.md#cleanup-review-20261013),
preserve unique data and the active 8768 preview, and treat eligibility as no authority
to delete. The [main inventory](PHASE1_ARTIFACT_CLEANUP.md#main-integration-20261013)
prefers review of published 93eb611, separately from 001a0fc quality gates and frozen
research refs. This documentation task performs no push, merge or deletion.
<!-- PUBLICATION_CLEANUP_HANDOFF_20261013_EN_END -->

<!-- PHYSICAL_HUMAN_REVIEW_20261013_EN_BEGIN -->
The latest [source-geometry human-review stage](../engineering/BLENDER_PHYSICAL_HUMAN_REVIEW.md) has **11 pending items and 38 checks**
(Office 4/14, CLASS101 3/10, Auditorium 4/14). No actual human confirmation has been recorded;
apertures, corridor connectivity and body clearance remain UNKNOWN. The top navigation and
3D/8–16 temporal source-frame wall share the selected source time segment. Local checklist deltas
are engineering records, without formal authority or automatic reranking/media encoding.
Fresh Python3186, Node160 (147 workbench + 13 product), Ruff, strict mypy199, HTTP154 requests / 5119 assertions and three-site browser checks passed; exact scopes are in the [new receipts](../../data/engineering/blender_physical_review_20261013/).
Checkpoint2de9821 rankings, curves, videos and validation totals remain historical. No Agent/GT
decision, original Blender opening/change/copy or real stream is introduced.
<!-- PHYSICAL_HUMAN_REVIEW_20261013_EN_END -->

The current engineering branch is `codex/simulation-engineering`, reusing the existing checkout and including documentation checkpoint `2c586b1`; the research baseline remains `phase1/finalization-sprint / 883204a`. Preview checkpoint `04c699d` was merged as `ded5572`. Compatible projection diagnostics and frozen `5b51d2c` adapters were imported selectively. This remains **SYNTHETIC_ENGINEERING_ONLY / NO_EXTERNAL_MODEL_CALLS**. The 2026-10-11 addition provides bounded label/graph preprocessing, dataset time/place and user-selected walking/running/enter-exit intent, explicit MockAgent I/O with two real detail actions, ten synthetic ports, four SQLite concurrency phases and delta-only new publication history. API wiring stays empty; no token saving or RAG accuracy is claimed. Streaming is FUTURE; accounts/deployment are DEFERRED. Stable3D and log-only eventIDs do not change formal research gates.

The preceding physical-filter checkpoint (2de9821) re-searches the full bounded pool before source-authorized
checks/reranking. All actual candidates remain UNKNOWN with zero hard rejection: Office original
3/4/2 become Top-3 while original1 remains new4; CLASS101 keeps one baseline, with corridor-only
NO_RESULT; Auditorium retains a truncated 256-state pool and unchanged Top-3. Partial scopes cover
25 collider scopes/58 components and 59 1F support surfaces; approved apertures/body domains remain
zero. Secondary segments and isolated/support points are checked/deduplicated without bonus inflation;
long gaps stay missing and empty-body baselines/ledgers remain UNKNOWN. Names do not prove ownership.
Fresh verification passed 3,140 Python tests (zero failures/errors/skips; 527.69 s), Ruff/mypy197,
122 Node tests (109 workbench + 13 product), 60/60 ports (54 actual + 6 substitute) and 175 HTTP
requests/501 assertions. Actual three-site playback, seek/manual/Play/dual-video handoff and the
9.8-second final-source cursor passed with zero console warnings/errors. Ignored `blender_physical_v2/{site}/` holds
three PNGs/MP4s with full decode, 50 frames at 5 fps/10 s and 300 exact source-RGB selections; original
source/v1 nine files remain unchanged. See the [fresh receipt](../../data/engineering/blender_physical_20261013/validation.json) and
[physical contract](../engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md) for the sole complete data-flow,
source hashes and substitute-test guide. Preserve identity/behavior uncertainty, missing corridor and
bounded search; no Agent/GT decisions, geometry promotion, original Blender opening/change/copy,
streaming, production accounts/deployment or pre-invented publication SHA.


The preceding 2026-10-12 extension, based on 4b43aed, implements independent site/run/clock
cross-camera graphs, `cross_camera_reconstruction` and issued-reference media delivery. Provisional
Top-K assignments and a separate unassociated baseline share 3D paths, XYZ/speed curves and the
source-clock cursor. Original corroborating projections remain separate; bounded short bridges are
inferred, long intermediate positions and original local hard gaps remain missing. No identity,
behavior, Agent, GT or whole-scene collision/walkability authority is asserted.

Office has five nodes/four eligible edges and three candidates from five exactly enumerated
assignments. CLASS101 has six nodes/no eligible cross-camera edges and one baseline, with fifty
CORRIDOR04 source frames/zero projections/MISSING. Auditorium has nineteen nodes/fifty-two
eligible/thirty-two rejected edges and three candidates, with beam256 truncation, 10,850 evaluations
and `complete=false`, without global-optimality claims. Ranking uses selected cameras' full source
0–9.8-second graph; time windows only slice display. Fixed full-camera/full-time/requested-K3 media
must be labelled separately from the query and selected rank/baseline.

Fresh validation passed 3,067 Python tests with `--require-physical-evidence`, zero skips and
443.27-second duration, 110 Node tests (97 workbench + 13 product), and Ruff/mypy for 193 files.
All three sites passed 16/16 ports (14 actual + 2 isolated substitutes; total48/48 with no deferred).
Actual HTTP passed 160 requests/450 assertions with `issues=[]`. Three curve PNGs and three
1280×720 H.264/yuv420p/faststart MP4s are materialized, with fifty frames at 5 fps/ten seconds,
100 exact source-RGB selections per site and complete fallback decoding PASS without ffprobe.
Browser checks passed all-site playback, candidate/baseline selection, missing corridor/truncation
notices, 3D/curve/camera clock synchronization, native seeking to 4.8 seconds, manual source-timeline
video pausing and narrow 2–4-second K1/single-camera versus full-source K3 media captions, with zero
console warnings/errors. Source Play took over from video and advanced RGB/3D/curves
together to 9.8 seconds. Original `.blend` SHA/468300506 bytes/mtime remained unchanged.
The receipt binds 529 code-tree files with SHA
`a341e5a10c5786643c06f8c37fd8c4d853fe8b8f59b649c6b32fc503a15a9739` and seven curated receipt
hashes. Commit/remote SHAs require Git verification; publication is ordinary engineering-branch push,
without presuming a commit SHA or main merge. Previous 4b43aed totals remain historical. Confirmed
identity/behavior, whole-scene collision/walkability, CLASS101 corridor projections and exhaustive
Auditorium search remain incomplete. See the
[cross-camera contract](../engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md) and
[independent receipt](../../data/engineering/blender_association_20261012/validation.json).
Original `.blend`/PNG assets remain read-only and uncopied. Formal Cases2/3/full Exit, frozen Phase2
and main remain unchanged; real streaming is FUTURE and accounts/deployment are DEFERRED.

The 2026-10-12 motion milestone implements camera-local curves, interval-midpoint finite-difference
speed, bounded reconstruction and issued-reference media endpoints. All three sites have materialized
curve PNGs and videos with complete decoding PASS; the 2026-10-11 DEFERRED video receipt is historical.
Positions are projected RGB contact pixels, not directly observed 3D. Same-track interpolation
requires valid endpoints, at most one second and the configured 8 m/s cap; long, speed and projection
gaps remain disconnected. No camera stitching, extrapolation, Agent or semantic confirmation is used.
The provisional table above records actual source-derived output counts; CLASS101's fifty CORRIDOR04
frames have no pixel/projection observations and remain MISSING. Full-scene collision/occlusion/
walkability remain unknown, with synthetic target/motion provenance preserved. See the
[motion operation](../engineering/BLENDER_MOTION_RECONSTRUCTION.md) and
[new receipt directory](../../data/engineering/blender_motion_20261012/). Each video is
1280×720 H.264/yuv420p/faststart, 5 fps and fifty frames/ten seconds, with 100 `SOURCE_RGB_EXACT`
source selections per site. With ffprobe unavailable, all three passed `FFMPEG_FULL_DECODE_FALLBACK`;
provider manifests and all six media reads passed. The full Python suite with physical evidence
passed 3,017 tests in 357.78 seconds without failures, errors or skips; 92 Node tests passed
(79 workbench + 13 product), plus Ruff and strict mypy for 191 source files. Final HTTP passed
98 requests/254 assertions with `issues=[]`; each site passed 13/13 ports (11 ACTUAL_BLENDER +
2 SUBSTITUTE) and six media binary/hash/range/scope checks passed.
All three 1280×720, ten-second videos played without browser decode errors. Office seeking to
7.838899 seconds synchronized its camera; CLASS101 CORRIDOR04 showed fifty source frames, zero
projections and fifty missing samples. Auditorium's single-camera 2–4 second query was distinct
from the full all-camera artifact caption; scene changes cleared old video. The final console had
no warnings/errors, normal views hid opaque event IDs and source integrity confirmed unchanged
original `.blend` SHA/size/mtime.
Original source assets and formal/GT/frozen Phase 2/main boundaries are preserved.

The 2026-10-11 Blender milestone adds three independent preset scenarios to the three existing E
fixtures, giving six catalog entries and 300 source-camera PNGs. Class-agnostic RGB measurements,
source-calibrated floor intersections and bounded deterministic Top-K frame messages operate
without an Agent. The orange target/motion remain simulated substitutes; smooth gray evaluated
geometry is PARTIAL display context, not the complete `.blend` or whole-scene physical authority.
Each scenario's probe passes 11 completed ports: nine actual Blender boundaries and two independent
E0 Graph/delta substitutes. One reconstruction-video port is deferred. Probe indexes match operator
indexes, with zero Agent/external calls and no source mutation/copy or physical stream. See the
[Blender contract](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md) and
[current receipts](../../data/engineering/blender_workbench_20261011/scene_inputs.json).
Physical curves and event-restoration video remain the next work; formal/GT/frozen Phase 2 gates
are preserved. This section does not promote historical full-test counts to this milestone.

M1–M6 now provide an operating synthetic RGB-to-local-track-to-provisional-association-to-3D-event composition, strict typed tools, immutable repositories, a browser/MockAgent workflow and independent evaluation/reproduction. See the simulation engineering document and current validation receipt. The local run has 102 images, 89 measurements, six tracks, 21 association records and four canonical gaps with eight alternatives. The separate office certificate covers structured partial recovery only; school RGB, arbitrary corridor packages and formal gates remain uncertified.

R1–R8 now provides an operating, separately versioned indexed synthetic pilot. See the local pilot guide and curated receipt for current metrics, 2427 full passing tests and scoped photo/3D/replay operation. Low pair accuracy and behavior false positives remain explicit; the original lab, formal gates, main and frozen Phase 2 are preserved.

The [accuracy v2 research](../research/LOCAL_CAMERA_ACCURACY_V2.md) now has separate frozen
experiments and a read-only typed adapter. Preserve UNKNOWN support states and distinguish the
changed producer population. Fragmentation/read costs, non-dominant fusion and missed behaviors
remain actionable; the [current receipt](../../data/engineering/accuracy_20261010/validation.json)
reports 170 scoped regression tests, not a full-repository pass. Formal gates stay unchanged.

P7–P12 now provide an operating [local synthetic Phase 2 product](../engineering/LOCAL_PHASE2_PRODUCT.md):
durable scoped SQLite retrieval, handcrafted pixel appearance, provisional stitching, bounded
intent-driven multi-subject plans, four-camera video/Three.js playback, saved cases, independent
reviews and exported reports. The current 2592-test regression, lint, 159-file types, 13 frontend
tests, 146 actual HTTP calls including process restart, browser operation and identical fresh-output
reproduction have separate source/run-bound receipts. Concurrent workbench validation is excluded.
Small conditional appearance/stitch populations and failures remain explicit. Original formal
research, production/live capabilities, source assets and frozen branches are not promoted.

The 2026-10-10 workbench integration now registers three independently bound frozen scenes,
source-model walking, E1 investigations/video/cases/reviews/reports, and a fifteen-family gallery
with 192 verified PNGs. The new integration receipt binds a full 2873-test run with no exclusions,
zero failures/errors/skips, lint, 183-file strict types, 58 Node tests and 63 actual HTTP requests.
Missing assets, status-only RRD/GIF entries and formal gates remain explicit; the original source
and all historical receipts are preserved. See the current coverage and investigation contracts above.

The following 2026-10-08 migration audit and 2652-test result are historical baselines:
The latest human decision selects frontend/workbench/8016 as the unified primary web UI.
Preserve product/8020 as an engineering lab/migration source and integrate existing/future
page capabilities into workbench. Backend adapters can use the product interfaces; the UI
migration is not yet complete. Do not describe the independent entries as already unified.
The [current presentation audit](../engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) confirms
only E1/E0 are registered. Migrate product tools/video and add source-bound research adapters;
keep missing assets and formal blockers explicit. Evaluation aggregate DTO/content validation,
cached-test invalidation after publication and GT-panel wording are still open issues.
A subsequent actual full run with no exclusions passes 2652 tests in255.995s, with zero
failures/errors/skips; lint, 164-file types and28 frontend tests pass. The product test
package namespace fixes a collection collision; prior failed collection evidence is retained.

Continue in the sprint worktree above. The human approved the exact corridor proposal and
requests a new-chat continuation to finish one reproducible dataset, benchmark table and
Rerun 3D demo tied to one frozen run. Use the linked prompt and release handoff.
Original HR01–HR04 and the independent reference movement policy are approved and applied;
the new exact scope has a direct-human receipt and six passing numerical cell certificates.
Independent clean-checkout regeneration passes; read the current checkpoint for precise hashes. Do not repeat
approval questions or rewrite historical review/preview packets.
Case2 and Case3 detour-growth remain blocked pending additive scoped pipeline adapters,
source-bound same-camera HOLD, unchanged-eligibility independent exhaustive inventory,
new config freeze, fresh 5 Hz execution and complete delivery reproduction. The old office
CLI cannot consume the new union directly. Preserve repeated-edge graph semantics and the
actual sample39 recovery; lower-bound proofs do not establish recall/readiness.
Audit the original Case2 two-sided-portal requirement against existing approved evidence;
the new corridor receipt grants no portal role.
The earlier `883204a` recovery checkpoint reran the existing office dataset/inference/evaluation;
the current integration checks have their own receipt. That recovery checkpoint includes
reader-verified demos, ready-case reproduction and corridor numerical verification. Read the
recovery receipt and runtime guide for current results; old temporary bulk outputs are absent.
This does not complete the new corridor release. Case4 stays deferred, Phase2
frozen, and a Phase1 freeze requires every original full Exit Gate.
