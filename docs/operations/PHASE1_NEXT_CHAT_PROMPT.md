# 下一個工作 prompt / Engineering and research continuation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

直接複製以下 prompt。M1–M6工程閉環與Blender基底畫面檢索已實作；從最新已驗證
checkpoint續作，不重做已完成的工程階段，也不據此推定正式研究驗收完成。

局部跨鏡頭人物關聯、進出門／轉角／可能遊蕩事件與不全域掃描的具體 R1–R8、實驗／指標及下一對話 prompt，見 [研究交接](LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md)。它具體化本輪工程，保留原 formal gates；未提交並行草稿須先核對與續接，不以檔案存在當驗證完成。

```text
請在 Amidst 既有純模擬工程閉環上續作，保留目前可操作的 Blender camera 查詢、基底 Top-K 與來源模型展示。後續工作依最新使用者指示，將實際像素／投影／時間證據整理成可核對的物理候選曲線，再產出事件還原影片；尚未產生的曲線／影片不得標為完成。

工程可先以有限辨識／關聯精度完成，再逐步改善；來源可追溯、資料邊界、接口正確與可重現性必須通過。完整 GT 另存供 evaluation/debug，不用 GT 兜出推論答案。本階段不接真攝影機，不串接 OpenAI 或其他外部模型 API。

目前已完成的Blender milestone：

8016有六個獨立catalog情況：blender-office、blender-classroom101、blender-auditorium，以及原E0／E1／accuracy-v2三個工程fixtures。新增三情況共300張原來源camera PNG，各2鏡頭×50張，960×540、5Hz、0–9.8秒。Office／Auditorium的同名camera不能跨site/run合併。
Blender pipeline不經Agent決策，實際從PNG重算class-agnostic pixel components／local tracks，使用來源校正與核准floor plane，經camera/time有界索引輸出deterministic Top-K畫面訊息。行走、跑步、出入仍是使用者意圖，behavior UNKNOWN／identity UNCONFIRMED；品質／投影優先與鏡頭多樣性排名不是機率。
原.blend保持未改動、未複製。3D為來源evaluated mesh局部PARTIAL context，預設平滑灰材質只影響顯示，不能稱完整模型或全場walkability／occlusion核准。橙色目標與路徑是替代simulation。
三情況各自端口11/11 PASS（9 ACTUAL_BLENDER＋2 SUBSTITUTE），另1 reconstruction.video DEFERRED；Graph gap與delta history使用隔離E0 fixture的獨立source/model/run/clock/hash，不回填Blender run。Agent／外部模型calls均0，GT額外污染不改pixel index／query。
讀 docs/engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md 與 data/engineering/blender_workbench_20261011/ 的source/query/ports receipts。當次完整回歸依其新收據核對，不把下列2255、2925等歷史結果當作本次PASS。
以下原工程接口／M1–M6說明保留作契約參考；只續做尚未完成的能力，不重建已完成的pipeline或把舊MockAgent接到本階段Blender基底判斷。

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

Continue from the completed M1–M6 engineering composition and latest Blender frame retrieval
checkpoint on the existing checkout/branch. The catalog has three Blender scenarios plus three
existing E fixtures. Its 300 source-camera PNGs feed actual class-agnostic pixel measurements,
source-calibrated floor projection and bounded deterministic Top-K messages without an Agent.
Smooth gray source geometry remains PARTIAL context; the target/motion are simulated substitutes.
Each scenario passes 11 ports (nine actual, two independent E0 Graph/history substitutes), with
one reconstruction-video port deferred. Read the
[Blender contract](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md) and
[source receipts](../../data/engineering/blender_workbench_20261011/scene_inputs.json).
Do not repeat completed milestones or import historical full-test counts as current verification.
Physical candidate curves and event-restoration video are subsequent work and remain unmaterialized.

Preserve the existing MockAgent facade only in its E fixture scope. Blender retrieval does not
use Agent decisions, external models, GT or simulated annotation answers. Time/place and behavior
presets remain intent, with independent substitute tests and delta-only document history. The
original `.blend` is unchanged and uncopied, physical streams remain future work, and accounts/
deployment remain deferred. Formal research/GT/frozen Phase 2 gates and main are unchanged.
