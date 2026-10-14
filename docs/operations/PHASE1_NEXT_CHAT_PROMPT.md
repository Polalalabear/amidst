# 下一個工作 prompt / Engineering and research continuation

## 目前續作入口 / Current continuation — 2026-10-14

先讀[目前交接](CODEX_HANDOFF.md)、[全部工作與重現](CURRENT_WORK_REPRODUCTION.md)及[demo 指南](../engineering/DEMO_V1.md)。本頁下方保留舊 prompt，不能直接當作目前任務。

```text
在既有工程工作上續接目前授權的 11 修正，先以文件的 exact checkpoint／收據核對範圍及並行工作。
main439c866只含已驗證R1；工程b1cf0c4的R3工程回歸已通過，但首次真實demoFAILED，新48題尚未開始。R2全題常規12/40品質未過。
05保留baseline，Phase2功能估算約50%；不能用fixture／HTTP通過取代模型品質，不自動merge main或清理共享工作樹。
當前Web入口、PG／Ollama／SQLite依賴與Saved Agent憑證恢復依CURRENT_WORK_REPRODUCTION及DEMO_V1；不套用歷史固定port或舊工作樹指令。
獨立Phase1正式043bed2已通過18個受限Exit gates，Case3性能目標未達且整校幾何未認證；不重做已完成的Case2／3工程，不把Office展示UNKNOWN當該正式驗收失敗。
保留來源、原核准、歷史收據、負結果與其他工作的修改。以當次新收據更新文件，不冒稱歷史PASS為新測試。
```

English: Continue from the current handoff and exact receipts. R3 engineering checks passed but the actual demo failed; R2 quality failed. Keep the baseline, shared state and scoped formal acceptance distinct.

## 歷史續作 prompt / Historical prompts — not current instructions

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

直接複製以下 prompt。M1–M6工程閉環、Blender基底畫面檢索、camera-local曲線與跨鏡頭多解與來源物理篩選API已實作；從最新已驗證
checkpoint續作；最新為來源幾何人工核對準備，等待實際人工確認，不主動重排或重編碼。

局部跨鏡頭人物關聯、進出門／轉角／可能遊蕩事件與不全域掃描的具體 R1–R8、實驗／指標及下一對話 prompt，見 [研究交接](LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md)。它具體化本輪工程，保留原 formal gates；未提交並行草稿須先核對與續接，不以檔案存在當驗證完成。

```text
請在 Amidst 既有純模擬工程閉環上續作，保留目前可操作的 Blender camera 查詢、基底 Top-K、來源模型、同相機局部track曲線、跨鏡頭多解與來源物理篩選API。先核對2026-10-13人工核對契約與新收據的實際完成／未完成狀態，再依最新使用者指示續接，不重做已完成演算法。4b43aed的camera-local三站曲線PNG／影片已物化、完整解碼與瀏覽器播放PASS；其3017 Python／92 Node／98 requests是歷史驗證，不充當本次跨鏡頭PASS。

工程可先以有限辨識／關聯精度完成，再逐步改善；來源可追溯、資料邊界、接口正確與可重現性必須通過。完整 GT 另存供 evaluation/debug，不用 GT 兜出推論答案。本階段不接真攝影機，不串接 OpenAI 或其他外部模型 API。

最新階段（先讀此段，後續歷史保留作參照）：

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

目前已完成的Blender歷史 milestone：

8016有六個獨立catalog情況：blender-office、blender-classroom101、blender-auditorium，以及原E0／E1／accuracy-v2三個工程fixtures。新增三情況共300張原來源camera PNG，各2鏡頭×50張，960×540、5Hz、0–9.8秒。Office／Auditorium的同名camera不能跨site/run合併。
Blender pipeline不經Agent決策，實際從PNG重算class-agnostic pixel components／local tracks，使用來源校正與核准floor plane，經camera/time有界索引輸出deterministic Top-K畫面訊息。行走、跑步、出入仍是使用者意圖，behavior UNKNOWN／identity UNCONFIRMED；品質／投影優先與鏡頭多樣性排名不是機率。
原.blend保持未改動、未複製。3D為來源evaluated mesh局部PARTIAL context，預設平滑灰材質只影響顯示，不能稱完整模型或全場walkability／occlusion核准。橙色目標與路徑是替代simulation。
2026-10-11三情況各自端口11/11 PASS（9 ACTUAL_BLENDER＋2 SUBSTITUTE），當時另1 reconstruction.video DEFERRED；Graph gap與delta history使用隔離E0 fixture的獨立source/model/run/clock/hash，不回填Blender run。Agent／外部模型calls均0，GT額外污染不改pixel index／query。此段保留當時狀態，最新曲線／影片現況依下一段。
讀 docs/engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md 與 data/engineering/blender_workbench_20261011/ 的source/query/ports receipts。當次完整回歸依其新收據核對，不把下列2255、2925等歷史結果當作本次PASS。
以下原工程接口／M1–M6說明保留作契約參考；只續做尚未完成的能力，不重建已完成的pipeline或把舊MockAgent接到本階段Blender基底判斷。

2026-10-12 camera-local曲線目前已實作：

BaselineMotionIndex只讀安全pixel measurements、floor projections與local tracks，不讀圖片／GT／recipe／私有路徑，不經Agent。位置標PROJECTED_OBSERVATION，不是直接觀測3D；同track有效端點、缺口≤1秒及速度≤設定8 m/s才可INFERRED_INTERPOLATION。速度為區間中點INFERRED_FINITE_DIFFERENCE。長缺口、超速或投影失敗保持MISSING／斷線，不跨相機或track合併，不外插；narrowwindow保留canonical事件端點與IDs。
全來源暫定輸出：Office3tracks／31投影點／0插值／0缺失／26速度點／2斷開區間；CLASS1016／70／4／0／64／0；Auditorium10／82／19／12／63／18。CLASS101 CORRIDOR04為50sourceframes／0pixel／0projection／50missing，不能用另一鏡頭的曲線聲稱走廊tracking。Tracks不等於人數，人物／行為保持未確認。
8016 POST /api/motion_reconstruction 接受研究session／scene、最多4個camera與≤10秒窗，限400points／32tracks，回傳curve／velocity／missing／camera coverage及optional artifacts。GET /api/motion_media只供應已發出的同session／scene refs，不接受locator、不在GET時encode。缺素材或來源／renderer hash失配須明列NOT_MATERIALIZED／INVALID_OR_STALE_ARTIFACT。
物化入口 scripts/materialize_blender_motion.py 已實作；三站實際影片各為1280×720H.264／yuv420p／faststart、5fps、50frames／10s，以完整來源0–9.8秒呈現，每站100次來源RGB選取皆SOURCE_RGB_EXACT。環境無ffprobe，三站FFMPEG_FULL_DECODE_FALLBACK完整解碼PASS，三站provider manifest及六份媒體讀取PASS。讀 docs/engineering/BLENDER_MOTION_RECONSTRUCTION.md 與 data/engineering/blender_motion_20261012/ 新收據，不回寫2026-10-11歷史。
最終三站各13/13端口PASS（11 ACTUAL_BLENDER＋2 SUBSTITUTE），六份媒體binary／hash／range／scope守門PASS。Browser三站10秒／1280×720實際播放無decode error；Office seek7.838899秒與camera同步，Class corridor顯示50來源／0投影／50缺失，Auditorium單camera2–4秒查詢與完整all-camera影片caption分開。scene切換清除舊影片，最終console0warning／error、一般畫面無opaque event IDs；source_integrity確認原.blend SHA／size／mtime不變。
8m/s為工程configuredcap，floor-only幾何不證明整場碰撞／遮擋／可行走或人類物理核准；合成target／motion來源保留。原.blend／PNG未變更、未複製，formal／GT／Phase2 FROZEN／main保留。

2026-10-12 跨鏡頭多解增量已實作，接續同日camera-local曲線checkpoint：

BaselineAssociationIndex在每組site／run／clock內使用安全pixel-derived motion／floor快照建立canonical圖。最多64nodes／256edges／beam256、K1–5；正時間差及8m/s設定cap、共同sourceclock≤0.75m同步投影與全路徑切換速度、一進一出／非相鄰同步衝突等守門。不平均不同camera原投影、不間接修補同track hard gap，身份UNCONFIRMED／行為UNKNOWN、不經Agent或GT。
Office5nodes／4edges／Top-3，5uniquehypotheses完整枚舉；CLASS1016nodes／0edge／1未關聯baseline、NO_CROSS_CAMERA_EVIDENCE，走廊仍50source／0projection；Auditorium19nodes／52eligible／32reject／Top-3、beam256 truncated=true／complete=false、10850評估、不保證全域最優。不補K；baseline_candidate另保留全部未關聯片段。
8016新增POST /api/cross_camera_reconstruction與GET /api/cross_camera_media；canonical關聯與排名使用所選鏡頭完整來源0–9.8秒，narrowquery只裁切顯示並保留refs，不能宣稱僅用窗內證據重新排名。預物化影片固定全鏡頭／完整來源／請求K=3，與query或選定rank／baseline差異必須明列；GET不encode或接受路徑。素材缺失／stale不得阻斷有效候選／曲線。
3D、XYZ／速度曲線與sourceclock游標同步，保留canvas／視角／DOM；同期support另存原投影，短橋INFERRED_CROSS_CAMERA、長gap中間位置MISSING，原局部unresolved_local_gaps仍列。事件ID僅專用log。原blend／PNG唯讀不複製，無真實串流；partialmesh與floor-only不證明完整collision／walkability。
本次完整驗證3067 Python PASS／0 skip／443.27秒，使用--require-physical-evidence；核心34已包含，不額外累加。Node110 PASS（工作台97＋product13）、Ruff／mypy193檔PASS；三站各16/16端口（14實際＋2替代），合計48/48（42＋6）無deferred；fresh HTTP160 requests／450 assertions PASS、issues=[]。
三站各物化1PNG與1MP4，每站100次來源RGB選取，1280×720 H.264／yuv420p／faststart、5 fps／50frames／10s；環境無ffprobe，full decode fallback PASS。Office三解長gap8.2／6.8／4.2秒保持MISSING，Aud原支持投影不平均，Class走廊仍0projection。
Browser三站播放、候選／排序外baseline、缺corridor與截斷提示、3D／曲線／camera同步、native video seek4.8秒、來源時間軸暫停影片、窄窗2–4秒K1／單camera與完整K3素材caption分開均PASS，source Play接管影片後RGB／3D／曲線同進至9.8秒，console0 warning／error。原.blend SHA／468300506bytes／mtime unchanged，未開啟或複製source。
先核對 docs/engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md 與 data/engineering/blender_association_20261012/validation.json；收據綁529 codefiles SHA a341e5a10c5786643c06f8c37fd8c4d853fe8b8f59b649c6b32fc503a15a9739及其他7receipt hashes，commit／remote須核對Git，不預編SHA或宣稱已push。4b43aed的3017／92／98是歷史，正式identity／behavior／collision／walkability、Class走廊投影、Aud完整列舉、帳號／部署／stream仍未完成或暫緩。依最新指示續作，不重做已完成core／UI／影片或重問已授權範圍。

2de9821 來源物理篩選歷史 checkpoint 接續fc73eca：

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


新增physical_cross_camera_reconstruction／issued-reference physical_cross_camera_media；
query只驗pin及裁顯示，完整pool／ledger物理決策在import預建，body資料缺失必UNKNOWN。

一、起點、分支與資源

重用 checkout：/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization。
本輪統一在 codex/simulation-engineering 開發；先確認 pwd、git status、branch、HEAD、origin 與遠端 refs，保留無關修改。

已驗證的工程基底為 4271b2bdfb255aa15dcddb25cba31127a6890aa6；從目前工程分支包含此基底的最新已驗證 checkpoint 續作。文件整理 2c586b1、preview merge ded5572、projection checkpoint f58157f 與 Phase 2 additive adapters 均已包含，不退回 docs checkpoint，不重複匯入或 whole-branch merge 舊 core。
該工程基底實際驗證2255 tests、零失敗／跳過，Ruff／mypy PASS、25次本機 HTTP requests 與 TypeScript consumer/replay PASS；這不是後續修改已通過測試或正式 Phase 1 驗收。

先讀：
- docs/README.md
- docs/specs/DEVELOPMENT_RULES.md
- docs/operations/CODEX_HANDOFF.md
- docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md
- docs/engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md
- docs/engineering/BLENDER_MOTION_RECONSTRUCTION.md
- docs/engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md
- data/engineering/blender_association_20261012/validation.json
- data/engineering/blender_workbench_20261011/scene_inputs.json
- docs/engineering/PHASE2_INTEGRATION.md
- data/engineering/integration_20261008/compatibility.json

需要素材重建或 corridor 接入時，再讀 docs/operations/PHASE1_RESTORED_RUNTIME.md、docs/operations/PHASE1_RESEARCH_RELEASE_HANDOFF.md、data/finalization/recovery_checkpoint_20261008/validation.json、data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json。其餘按問題與分類讀取，不全目錄掃描。舊 handoff 的 branch/path/test 記錄屬其日期基線，不據此切換本輪工程分支。

phase1/finalization-sprint / 883204af854bed301506b39d63ccb33312b79ff2 是研究恢復基線；codex/docs-agent-handoff 是文件基線，均不是本輪開發目標。phase2/integration-hardening / 5b51d2c 與 frozen tag 保持 FROZEN；只擴充工程分支已接入的相容模組，不在 frozen branch 開發，不 merge main。

canonical checkout /Users/polalabear/Developer/amidst 只供應 immutable Blender scene/raw artifacts，不切換其 branch，不修改原 .blend、原 locked inputs 或歷史證據。重用現有 environment 與單一重型資產來源，不為每個 milestone 建 worktree、clone、venv 或 raw 副本，不清理／刪除既有 worktree/media。
本次重用既有Blender camera PNG與source-bound模型archive，不新增render或.blend副本。若後續另有明確授權產生新照片／序列，須保存新run的來源／設定／hash，不回寫原scene，不藉此擴大geometry／portal／walkability authority。GitHub只保存符合artifact policy的程式、文件與curated receipts；本機素材用manifest/hash/materialization/replay refs接入。

二、重用既有工程接口

已有 canonical snapshots、Memory/LOCAL_JSON、camera/time/event reads、legacy replay importer 和 TypeScript consumer。可啟動：
uv run python -m amidst.integration --config configs/integration/mock_v1.json --serve --port 8000

此接口服務四個 synthetic cases，GET 只讀固定 snapshot；保留 canonical observation/event IDs、完整候選／hypotheses、排序、bindings、nullable fields、termination_reason 與 complete。不要以窄時間窗重新聚合結果取代 event 的 canonical endpoints；replay 插值只屬 presentation，不改推論。

低階 mock API 尚非 Agent allowlist DTO；其 synthetic target IDs、完整座標與 source references 只作內部開發資料，不直接開給 Agent。保留內部契約，在外層新增受 mode/stage/scope 限制的 Agent facade，不以刪除欄位或回寫舊 records 取代守門。

Legacy importer 只認 COMPLETE artifacts.json v1.0 package；新 reviewed/finalization package 尚未認證。完成獨立 source/context/clock/unit adapter，核對 camera、座標系與 scale，顯式 normalization 後認證匯入。固定 METRES metadata 不能只覆蓋 historical native BU；school-v3 核准尺度為 1 BU = 0.0247 m，原 frozen BU artifacts 不回寫。Mock PASS 不等於 reviewed package 相容。

三、照片模式、影像量測與跨鏡頭關聯

完整保存 simulation/GT package。GT actor identity、GT 3D position/path、recipe/reference annotations 留在獨立 simulation/export、evaluation/debug 邊界，不進 image producer、association、Graph、ranking 或 Agent-visible query。合法校正／靜態 geometry 和真正推論出的 3D 投影、區域與候選不是 GT，可由相應服務使用，並保存 origin/authority/uncertainty。

先核對既有照片是否包含可辨識目標及足夠時序；diagnostic 動畫、標記、拓樸圖或代表影格不自動等於可追蹤的 camera sequence。需要時產生最小必要的新合成 RGB 序列，影像不加 GT 身分／路徑／bbox 標註，GT 在獨立 sidecar 完整保存。不要把既有5Hz資料時間點當作已存在5Hz camera照片。

Local image producer 從 RGB pixels 產生可見特徵、2D量測與 tracks，可使用合法 camera calibration；不讀 simulator segmentation/object-index/depth、GT bbox/keypoints、GT身分／位置或 recipe/reference annotations。允許低精度、class-agnostic detection/tracking，不要求先擴充完整物件分類。缺圖、漏檢與不確定結果須明示；不得退回模擬 UV 或 GT 再宣稱完成 CV。
合成圖片經影像演算法處理仍屬 SYNTHETIC 來源；另記 image-measurement producer、版本、輸入hash與真實量測來源。不把它標成真攝影機 REAL_CV；既有 image_measurement=false／模擬投影 records 保留原語意，不改稱影像量測。

用外層 composition 建立兩種輸入模式：
1. photos_only：完整合成照片與必要 camera/frame/time/evidence refs，不附預先算好的 structured observation 答案。
2. photos_plus_observations：相同照片，加真正由圖片 producer 產生、來源明確的可見特徵／bbox或keypoints／local tracks及准許的幾何衍生結果；無法量測的欄位保持缺失，不補造。

明定模式比較的接收端與判斷階段，使用相同照片、任務、population及核准靜態 context。Photos-only 流程需要量測時由本輪 producer 從 pixels 重新產生，不能讀另一模式預先儲存的答案。分別記錄 camera retrieval 與 observation-mode 差異；本機模式比較不宣稱 GPT品質或 token 降幅。

Local track IDs 以 model/run/camera namespace 保存，不使用 simulator global actor identity 作跨鏡頭答案。跨鏡頭輸出 association hypotheses，保留歧義、無法關聯與全部替代候選。
既有事件聚合依 target_id 分組，reconstructor 要求端點 target_id 相同；它們不是 association solver。新增相容 adapter，在各 hypothesis scope 建立明確 provisional association binding，保存原 track／observation／衍生 event 對照，不填入 GT actor ID、不壓成已確認唯一身分、不回寫原 canonical IDs或records。重疊可見段與同鏡頭 recovery 明確處理，不偽造時間或 camera handoff 去繞過舊介面限制。

四、地點模型與 Agent 資源

建立 LocationRegistry/CameraCatalog：place_id、model_id/revision、source hash、spatial_context、coordinate frame、scale/normalization、run/clock、camera groups、region/coverage mapping 和 origin/authority。保留原 camera_id，外層加模型／地點 namespace；按模型/run 分隔推論，再查各自 canonical records。名稱不證明 coverage 或 region authority。
先接入已有且可核對來源的地點；完成其他模型的 importer 與 fixture，不虛構未提供的資產／鏡頭／跨模型 transform。衍生子模型保存 parent revision/source hash、derivation manifest/hash、顯式 transform（可為identity）及 camera/calibration correspondence；缺映射不得混用校正，subset/crop 不擴大 authority。

Agent 只定位資源、調用查詢、取得必要證據與解釋結果；projection、world-to-region、pathfinding、collision、Graph traversal 和 reconstruction 由服務執行。先落實角色、工具與 DTO，再以 MockAgent 展示；不做 Agent semantic reranking。

提供精簡 TaskContext：place/model/source/context/run/clock/mode/stage/registry versions、opaque resource refs及allowed tools。Mode/stage/permissions 由服務端綁定 run manifest，不信任 Agent或caller自行宣告。Photos-only 判斷／association 前，summary/detail/query/media/replay及logs不能旁路露出已存投影、zone、candidate或hidden身分答案。進入結果查詢stage須核對同一run/mode/input/config綁定的 inference-freeze receipt/hash；改request參數不能跳過守門。

實作 typed tools：resolve_place、list_cameras、query_observations、query_events、get_event_summary、get_event_detail、get_media、get_replay。
預設摘要保留 scope、camera/time、evidence/event refs、origin/authority、candidate/hypothesis counts、termination_reason、complete、uncertainty與detail/media/replay refs；按需取得細節。完整 canonical資料另存，摘要省略不表示底層不存在，search complete不表示query成功。不要把全scene、NavMesh、camera matrices、所有座標、Embedding或raw metadata注入TaskContext，不提供repository/filesystem/任意SQL/shell掃描工具。

五、執行期與發布資料邊界

只做本機 service/data-export/MockAgent。系統執行期不向外部模型或服務送出照片、檢索資料、GT或秘密；這不禁止已授權的GitHub普通push。發布仍依artifact policy，只上傳允許的程式／文件／curated證據，不上傳LOCAL ONLY、raw/private/secret資產。

Agent-facing tools/API/export/DTO/logs驗證 mode/stage/source/context/run/reference allowlist，不帶GT、hidden actor答案、secret、private filesystem paths或完整source archives。照片以opaque refs透過本機media工具取得；越界／缺失／錯誤回應同樣守門。內部legacy mock開發接口保持隔離，不自動列為Agent allowed tools；獨立local evaluation/debug可保留GT與必要定位資料，不清洗或改寫immutable歷史紀錄。

不新增OpenAI SDK、live provider、API key配置或live model smoke call；外部API接線章節仍空白。
依2026-10-11新指示，token兜底先用圖形／label前處理整理必要feature summaries與navigation，
再交LOCAL_MOCK；禁止Agent大規模掃描，明列Agent input/output、budgets、讀取與省略量。
本原型已接入8016，見[系統端口與label指引](../engineering/SYSTEM_PORTS_AND_LABEL_GUIDANCE.md)；
不宣稱已量測token減量或完整RAG精度。後續保持dataset時間／地點與行走、跑步、出入意圖，
分層測試可用獨立替代fixture，不回填正式run。真實串流FUTURE、正式帳號／部署DEFERRED；
歷史只存修改文件，不複製.blend／raw。一般local image processing、缺失結果處理與typed
retrieval守門仍須完成，不以外部API空白為由停工。

六、可連續推進的工程 milestones

M1：LocationRegistry/CameraCatalog/media索引與source-clock-unit bindings；從地點取得真實存在的camera/frame refs，未知coverage明示。
M2：可用RGB序列、真正pixel-derived local perception/tracks、兩種輸入模式及mode/stage守門；保留量測缺失與低精度結果，不使用GT兜底。
M3：association hypotheses與原local records映射、合法projection/world-to-region、相容Graph/reconstructor adapter；保留全部歧義與替代路徑，明確處理same-camera recovery。
M4：重用canonical snapshots、Memory/LOCAL_JSON及legacy reads/replay；完成新package獨立adapter certification、place/region查詢和Agent summary/detail/media/replay工具，GET不重跑推論或改寫永久IDs。
M5：可操作MockAgent展示：地點定位→鏡頭/時間查詢→摘要→必要照片/細節→3D區域事件/replay。可重用Rerun與既有素材，但不得只交預錄影片或接口scaffold；主展示不含GT overlay，debug另設入口。
M6：同一run綁定dataset/config/producer/model-registry/media/freeze hashes；交付sample輸入輸出、模式比較、精度與失敗結果、工具紀錄、可重現命令、必要RRD/PNG和資料外洩測試。覆蓋正常、空結果、歧義、缺圖／缺reference、越界、錯誤mode/stage、跨run以及GT污染不能改變推論等情境。

按依賴循序實作，可並行獨立子任務；共享checkout不得同時切branch或操作Git index。每個可執行milestone做相稱unit/integration、既有階段相容與文件檢查，獨立commit並普通push codex/simulation-engineering，續做下一段。重用既有驗證入口，實際結果綁定當次commit/config/run，不把歷史2255 tests當本次PASS；不force push、reset、rebase或改寫使用者歷史。

七、正式研究的獨立續作與完成條件

原HR01–HR04、reference MOVING/departure-DWELL policy及exact corridor proposal 7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad已核准，不重問或回寫歷史bytes。Office recovery run僅為局部能力證據；舊/tmp/bulk raw不存在時由exact inputs按runtime指南重建，不引用不存在的raw作當前證據。

若工程使用新corridor union，先完成必要scoped adapters、source-bound same-camera HOLD及原Case2 portal/anchor evidence gate；保留實際recovery與分開GAP，不把route-class lower bound或simple-cell DFS當exhaustive inventory，不虛構CAM01 handoff。缺少formal authority時明示BLOCKED，繼續可獨立執行的mock工程，不推定新核准。

正式Cases1–3 × A/B/C × K、必要消融、相同eligibility的獨立exhaustive inventory、fresh 5Hz frozen dataset/inference、independent evaluation與完整clean-checkout reproduction仍須續作，dataset/benchmark/Rerun綁定同一frozen run。正式驗收與工程M1–M6分開記錄，不作mock工程前置，也不因工程完成而標成PHASE1_VALIDATED_AND_FROZEN。未量測指標N/A，Case2/Case3 full gates未過仍BLOCKED，原full Exit全過才freeze，Case4 DEFERRED。保持原Phase2 branch/tag FROZEN，不自動切換研究branch或merge main。

從目前已完成的M1–M6與Blender檢索checkpoint直接續作本輪實際要求，不停在規劃／scaffold，也不重做已完成階段。低精度、缺資產或核准不足須明列具體限制，繼續可獨立完成的工作，不假造曲線／影片或正式驗收。更新CODEX_HANDOFF、WORK_LOG與相關契約，清楚區分已實作、當次已驗證、formal待辦與保留章節；保留原source/protocol/checkpoint及所有無關修改。
```

## English

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


The preceding same-day cross-camera extension is based on 4b43aed. `BaselineAssociationIndex`
constructs independent site/run/clock temporal/speed/floor graphs and distinct Top-K assignments,
with an unassociated baseline retained separately. Office has five nodes/four edges/three candidates
from five exactly enumerated assignments; CLASS101 has six nodes/no eligible cross-camera edges/
one baseline and `NO_CROSS_CAMERA_EVIDENCE`; Auditorium has nineteen nodes/fifty-two eligible/
thirty-two rejected edges/three candidates, beam256 truncation, 10,850 evaluations and
`complete=false`, without global-optimality claims. Identity/behavior remain unconfirmed.

Canonical ranking uses selected cameras' full 0–9.8-second graph; a narrow window only slices
display and preserves source-bound references. Fixed full-camera/full-time/requested-K3 media must
be distinguished from the query, selected rank or baseline. The 3D/XYZ/speed/source-camera cursors
share one clock; original supporting projections are not averaged, short transitions are inferred,
and long intermediate positions/local hard gaps stay missing. Event IDs remain in dedicated logs.
No GT or Agent decides association, and partial meshes/floor-only geometry confer no whole-scene
collision/walkability authority.

Fresh validation passed 3,067 Python tests with physical evidence and zero skips in 443.27 seconds,
110 Node tests (97 workbench + 13 product), Ruff/mypy for 193 files, all three sites' 16/16 ports
(14 actual + 2 substitute; total48/48 with no deferred), and 160 actual HTTP requests/450 assertions
with `issues=[]`. Each site has materialized curve PNG/MP4, with 100 exact source-RGB selections,
1280×720 H.264/yuv420p/faststart, fifty frames at 5 fps/ten seconds and full fallback decode PASS
without ffprobe. Office's three long gaps of 8.2/6.8/4.2 seconds remain missing.

Browser checks passed all-site playback, candidate/baseline selection, missing corridor/truncation
notices, 3D/curve/camera synchronization, native seeking to 4.8 seconds, manual source-timeline
video pausing and narrow 2–4-second K1/single-camera versus full-source K3 captions, with zero
console warnings/errors. Source Play took over from video and advanced RGB/3D/curves together
to 9.8 seconds. Original `.blend` SHA/468300506 bytes/mtime remained unchanged, without
opening or copying source. Read the [cross-camera contract](../engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)
and [new validation](../../data/engineering/blender_association_20261012/validation.json) first. The
receipt binds 529 code files with SHA
`a341e5a10c5786643c06f8c37fd8c4d853fe8b8f59b649c6b32fc503a15a9739` and seven curated receipt
hashes; verify Git commit/remote state without inventing a SHA or claiming push completion.
Confirmed identity/behavior, full collision/walkability, CLASS101 corridor projection and exhaustive
Auditorium search remain incomplete; accounts/deployment/streams remain deferred/future. Do not
repeat completed core/UI/media work. The following camera-local totals are 4b43aed history.


Continue from the completed M1–M6 engineering composition and latest Blender frame retrieval
checkpoint on the existing checkout/branch. The catalog has three Blender scenarios plus three
existing E fixtures. Its 300 source-camera PNGs feed actual class-agnostic pixel measurements,
source-calibrated floor projection and bounded deterministic Top-K messages without an Agent.
Smooth gray source geometry remains PARTIAL context; the target/motion are simulated substitutes.
Each scenario passes 11 ports (nine actual, two independent E0 Graph/history substitutes), with
one reconstruction-video port deferred. Read the
[Blender contract](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md) and
[source receipts](../../data/engineering/blender_workbench_20261011/scene_inputs.json).
The 2026-10-12 camera-local motion API now supplies projected position curves, short-gap interpolation
and interval-midpoint finite-difference speed. Original projected pixels are not directly observed 3D;
the one-second/8 m/s engineering policy leaves rejected intervals disconnected. Camera identity
stitching, extrapolation and behavior confirmation remain absent. CLASS101 CORRIDOR04 has fifty
source frames but no pixel/projection observations and remains MISSING.
Curve PNGs and videos are materialized for all three sites at 1280×720 H.264/yuv420p/faststart,
5 fps and fifty frames/ten seconds each, with 100 `SOURCE_RGB_EXACT` source selections per site.
With ffprobe unavailable, all three passed `FFMPEG_FULL_DECODE_FALLBACK`; provider manifests
and all six media reads passed. The full Python suite with physical evidence passed 3,017 tests
in 357.78 seconds without failures, errors or skips; 92 Node tests passed (79 workbench + 13 product),
plus Ruff and strict mypy for 191 source files. Final HTTP passed 98 requests/254 assertions with
`issues=[]`; each site passed 13/13 ports (11 ACTUAL_BLENDER + 2 SUBSTITUTE) and six media
binary/hash/range/scope checks passed. All three 1280×720, ten-second videos played without browser
decode errors. Office seeking to 7.838899 seconds synchronized its camera; CLASS101 CORRIDOR04
showed fifty source frames, zero projections and fifty missing samples. Auditorium's single-camera
2–4 second query stayed distinct from the full all-camera artifact caption. Scene changes cleared
old video; the final console had no warnings/errors and normal views hid opaque event IDs.
Source integrity confirmed unchanged original `.blend` SHA/size/mtime. See the
[motion contract](../engineering/BLENDER_MOTION_RECONSTRUCTION.md) and
[new receipts](../../data/engineering/blender_motion_20261012/).
Do not repeat completed milestones or import historical full-test counts as current verification.
Floor-only geometry does not establish whole-scene collision/occlusion/walkability or human physics.

Preserve the existing MockAgent facade only in its E fixture scope. Blender retrieval does not
use Agent decisions, external models, GT or simulated annotation answers. Time/place and behavior
presets remain intent, with independent substitute tests and delta-only document history. The
original `.blend` is unchanged and uncopied, physical streams remain future work, and accounts/
deployment remain deferred. Formal research/GT/frozen Phase 2 gates and main are unchanged.
