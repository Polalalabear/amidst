# Case 2 / Case 3 已核准範圍稽核
> 後續狀態：使用者已明確核准「限於既有 union 的新版 Case 2 定義」。正式 addendum 與 [human approval receipt](human_approval.json) 已保存；下列草案段落保留當時的稽核背景，不再代表等待定義核准。正式數值驗收仍由新 run 的 receipts 決定。


日期：2026-10-14。此稽核只讀既有 source-bound JSON、協定及核准收據，另外計算 annotation bbox 與核准 union 的分離、三條既有範圍內路徑的 exact-rational 連續 coverage。未讀 GT、未執行新 Blender export／physical regeneration，未修改來源、原協定、原決策、producer 或 Phase 2。[機器記錄](audit.json) 保存本次輸入 SHA256 及完整結果。

## 已核准、可直接續作

六個 exact cells 的 physical union、28 個 support faces、指定 source face 的兩個 native triangles、逐 guard 的 surface-only interior、CAM01／CAM03 calibration／landmark binding 皆有原 `EXACT_PROPOSAL_ONLY` 直接核准。Certificate 仍限 exact union，outside union 必須拒絕；它沒有授予任何 portal role，也沒有自行開啟 formal case execution。HR01–HR04、Coverage ADE < 0.50 m、K=1/2/3、5 Hz、0.7904 m/s、uniform first／departure dwell 與獨立 reference movement policy 不需再問。

原 sampled first gap 的可見入口與回復都來自 CAM03。原協定沒有要求不同 camera IDs，因此 source-bound same-camera HOLD 是工程接入，不需要新語意核准。真實 sample index 39 recovery 不能刪除或合併兩段 GAP；fresh 5 Hz run 必須依當次實際 visibility 重新分段，不強套歷史 sample index。

## Case 2 最小硬阻塞

原 [`protocol_v1.json` 第 184 行](../../../configs/benchmarks/protocol_v1.json) 明列 `PORTALS_WITH_TWO_SIDED_ACCESS`。目前 selected six-cell interior-ring instance 無法滿足此 literal gate：

- 原 source audit 有 28 個 PORTAL annotations，1F 有 16 個；所有 annotation bbox 都與六-cell footpoint union 分離。
- 最近同層 annotation 是 `PORTAL_1F_MAIN_ENTRANCE`，bbox 距 union 至少 133.9 BU／3.30733 m；其 `physical_role_approved=false`，仍是 `ANNOTATION_PROXY_NOT_PHYSICAL_CERTIFICATION`。
- 既有 `physical_authority.json` 的 28 個 scopes 皆 `portal_ids=[]`；`portal_clearance.json` 的 `approved_pair_count=0`。這是 absence-of-authority 證據，不是宣稱原場景不存在門洞。
- 新 corridor proposal 沒有 portal binding；cell 接口、camera HOLD、visible anchor 或 winding proof 都不能自動改名成 approved PORTAL。

來源：`docs/PHASE1_RESEARCH_RELEASE_HANDOFF.md:63–69`；`data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json:209–216`；`human_review/formal_settings.md:29–31`；`data/finalization/reviewed_corridor_scope_application_v1/certificate.json:615–636`。因此原 v1 literal Case 2 尚不能標 READY 或通過 full Exit。

## 最小可審決策草案：不擴 geometry 的新版 addendum

這是**尚未核准、尚未套用**的 scope-specific 問題定義，不是 automatic PASS。可供使用者審核的一項最小決策為：

> 對 `school-v3-corridor-six-cell-scope-v2`，Case 2 的研究問題限定為已核准 closed union 內、相同 source-camera 可見 anchors 間的 interior branching／multi-hypothesis reconstruction。此 instance 不宣稱穿越任何 architectural portal。`PORTALS_WITH_TWO_SIDED_ACCESS` 在這份 scope-specific addendum 中只對確實穿越 portal 的 instances 適用；任何跨 portal case 仍須原 source-bound ownership、normal、兩側可達、clearance 與 physical authority，不能以此 addendum 豁免。其餘原 v1 指標、GT isolation、distinct route K、物理／時間硬限制、search budgets、A/B/C、single-factor ablations、完整重現及 Exit gates 原樣保留。

若使用者核准，新增獨立版本／hash 的 addendum 及 direct decision receipt；保留原 `protocol_v1.json` bytes、原 checkpoint／結果，不把舊 Case 2 BLOCKED 重標為通過。新 dataset/config/run 必須同時 pin 原 v1 SHA、addendum SHA、此 decision receipt 及 exact union authority。此決策只解除「所選 interior instance 與 mandatory portal literal 的不一致」；其餘未完成的工程或結果 gate 仍必須實測。

若堅持原 v1 portal literal 對此 instance 無條件適用，就必須另選並核准真正 source-bound portal 與兩側 approach scope。目前 six-cell union 內沒有可直接復用的 approved portal；該做法超出本次「沿用已核准範圍」約束，不能自行執行。

## Geometry / route inventory 的工程缺口

既有 first-gap left route 8.363274294768582 m、east route via `(1250,680)` 15.798124754270598 m 都完全被 union 連續涵蓋，提供兩條 route 的存在證據。原 exact source witness 在 union hole 內，可沿用既有 `scoped_route_inventory` 做獨立 winding 分離；仍須以此次 frozen endpoints 重建，不能把歷史 samples 當 fresh formal evidence。

Cell 0 是完整 `[1149.9,649.9,1250.1,680.1]` rectangle，所以同端點也有 `(1150,650)→(1150,680)→(914,680)` 的合法 east connector，長約 **11.490369046569693 m**。歷史 15.798 m alternative 因此不是 network-shortest proof；其 detour ratio 1.88899 只是一條候選的存在證據。

必須建立 source-canonical directed graph，明示每個 node／edge 到 exact certified cells／surface polyline 的映射與實際 metric lengths，證明 graph routes 到 source geometry route classes 的 coverage／equivalence scope。獨立 inventory 必須使用與實際方法相同的 endpoint、length、speed、detour、camera masks，保留原引擎可重複 positive-length edge sequences 的語意；simple-cell DFS、cell nerve、兩條 winding representatives 不能代替 exhaustive denominator。完成前 Feasible Candidate Recall 為 N/A，Case 2 readiness=false。這項是工程證明，不能被當成需要新人工 geometry 語意的藉口。

## Case 3 與可繼續工作

核准 union 具有合法較長路徑及同鏡頭 recovery，足以繼續 source-bound long-gap／timing／detour stress 的工程。固定 schedule、seed、原 max-path 24.7 m、detour 2、nodes 1000、time 10 s、branch factor 3、K=1/2/3 後，fresh 5 Hz export 保留所有 recoveries，再驗證實際 gap 的 speed feasibility、uniform／departure-dwell alternatives、candidate growth、search nodes 與真實 termination。

Primary inference freeze 之前不讀 reference；moving-time error 使用已核准 MOVING／DWELL annotations，不能以固定 gap duration 製造零誤差。全部 physical timing populations 保留，A/B/C 與 single-factor ablations 同一 frozen dataset/config。Case 3 的存在證據不等於 stress、benchmark、clean-checkout reproduction 或 full Exit 已完成。

目前可以完成所有上述 adapters、canonical geometry mapping、independent inventory、fresh runs 與可執行驗證，再以本草案作為最後一項具體可審決策。Phase 2 及原 immutable bytes 保持原範圍。
