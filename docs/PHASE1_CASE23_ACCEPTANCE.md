# Phase 1 Case 2／Case 3 驗收與第一版 demo

日期：2026-10-14。研究基線為 `883204a`，隔離工作樹
`codex/phase1-case23-formal`；Phase 2、main demo 與服務不在此工作的寫入範圍。
**目前：primary 與 clean 的 native exports／兩 child inference／joint pre-GT freeze／evaluation 已實際完成；
repeat／fresh／order／poison comparisons、完整 recording semantics 與 bounded metadata adapter 已通過。
Actual closeout 為 PHASE1_EXIT_GATES_PASSED，18 gates PASS、freeze_allowed=true；Freeze 版本定名 `phase1-scoped-case123-20261014`；exact curated release SHA 由 annotated tag 綁定，實際 tag／remote publication 核對另存 release 的 local `publication_receipt.json`。**

| 條件 | Case 2 | Case 3 | 第一版 demo 的已知差距 |
| --- | --- | --- | --- |
| 已核准場景 | exact 六-cell union、source obstacle/body/clearance、camera/landmark binding | 相同 source-bound domain、合法繞路、端點與 timing | 展示候選／影片不證明完整場景、身份或物理通行 |
| 資料問題 | 相同可見端點間至少兩條真正不同的可行路徑，保留中間所有 recovery | 實際 long GAP 的慢走、已批准 departure dwell、detour alternatives | office 原結果只有一個主要 route class，Case 3 只完成 temporal component |
| 搜尋 | K=1/2/3 是不同 source routes；timing／null-winding backtracks 不增加 class K | 短／長／高 slack stress，記錄 candidate growth、plateau、runtime 和 termination | bounded beam／raw edge-walk Top-K 不代替完整 source inventory |
| 評估 | A/B/C 共用資料、seed、metrics、authority、bounds；eligibility 依原 declared factor，獨立完整清冊算 recall | 同一 protocol，moving-time error 從批准 MOVING/DWELL reference 計算 | 缺 fresh corridor 全流程與同 run delivery comparison |
| 重現 | repeat、fresh process、ordering、GT/recipe/annotation poison、termination、clean checkout | 同左，保留原 source/protocol/config/approval hashes | UI demo 成功不解除 formal gates |

原規格來源：[protocol](PHASE1_BENCHMARK_PROTOCOL.md)、
[post-approval Exit](PHASE1_POST_APPROVAL_HANDOFF.md#最終交付與-exit-gate)、
[release handoff](PHASE1_RESEARCH_RELEASE_HANDOFF.md#尚未完成的原因與實作順序)。
所列初始數值目標仍是各分類結果，不能靠跨 Case 平均宣稱通過。

必要指標：Projection Error、ADE、FDE、minADE@K、minFDE@K、Coverage@K、Candidate Count、
Feasible Candidate Recall、Collision Rate、Constraint Violation Rate、Impossible Transition
Rate、Path Length Error、Travel-time Error、Runtime、Search Nodes、Termination Reason。
正式 Coverage 使用 ADE **嚴格小於 0.50 m**；Case 3 FDE 初始目標 **≤1.0 m**；
每個正式候選的 collision／impossible-transition rate 初始目標為 **0**。
整體 Coverage@3≥90% 的跨 Case weights 未核准，保持各 Case 分開報告。
[PRD §20](PRD.md#20-baseline-與-ablation) 的 Case3 ≥30% relative primary ADE gain 亦保留。
本次 main 三個 GAP 的 A／C primary ADE 相同，gain 各為 **0.0%**，結果為
**INITIAL_RESEARCH_TARGET_NOT_MET**；不 waive 目標、不改 protocol，也不宣稱 overall research-target PASS。

固定原設定：5 Hz、inclusive source endpoints、全部 reference timestamps、piecewise-linear
alignment、max speed 0.7904 m/s、uniform first、departure dwell only、direct slack 1 s；
K=1/2/3、max candidates 3、nodes 1000、path 24.7 m、time 10 s、branch factor 3、detour 2。
Source assets、原 HR01–HR04、protocol v1、原 producer 和歷史結果不回寫。

## Case 2 本次明確核准的限定

來源稽核證明原 PORTAL annotations 與 exact union 分離，不能把 cell 接口或 visible
anchors 自動稱為門孔。使用者已明確回覆「核准這個限於既有 union 的新版 Case 2 定義」。
獨立 [addendum](../configs/finalization/case2_interior_branch_addendum_v1.json) 與
[direct-human receipt](../data/finalization/case23_scope_audit_20261014/human_approval.json)
將此 instance 定為既有 closed union 內的 branching，使用實際 source-camera visible anchors；
它不主張任何 architectural portal crossing。真正跨 portal 的 instances 仍須原 portal gate。
只有這項問題定義不一致已解除；不自動授予 case readiness、metric PASS 或 freeze。

## 本次能力與實際驗證

Additive projection wrapper 沿用原 exact-time multiview／fixed-plane producer；保留所有 RAW/GAP
samples、原 no-plane identity、conditioning／uncertainty；footpoint 只採批准的固定 Z offset
與 BU→SI 換算，不 clip／snap／rejection。Same-camera HOLD 不偽造 self camera transition。

完整 source visibility graph、production FIFO class search、獨立 reference Dijkstra inventory
使用不同 search 實作。原 Graph 與 BlindGapReconstructor 消費 source-bound class macro paths，
原 full visibility Graph 的候選數／MAX_BRANCH_FACTOR 等 termination 另留 ledger。
原 physical/body guard 永不被 collision ablation 移除。零 handoff 的 topology ablation 若沒有
可移除 factor，明列 N/A，而不是捏造效果。

初始 source-v1 僅是 readiness probe，未讀 accuracy/reference 選設定，不升格為正式 run。
新 source-v2 在正式評估之前固定 Case 2 schedule（16 BU/s）、Case 3 主 long-gap 及
short-control／high-slack schedules；原最高可行速度與 search bounds 不變。
全部 recovery、changed populations、failed／N/A／empty rows 都要保留。

本次 primary 有 288 joint table rows、88 scoped metric receipts；Case1–3 execution 與四個 scoped cases／controls 通過。
Full repository validation 是 2182 passed／0 failed／0 skipped；外加 controller／semantic／metadata／closeout tests
各自保存 receipts，不加進 frozen-code suite count。Actual node-ID／JUnit／log union proof 核對
**2299 unique executed tests＝2182＋16＋59＋26＋16，0 failed／0 skipped**；不宣稱單次 2299 full-suite run。
`final_population_validation.json` SHA `b1eae21c10197c7fe2ff3ff93be37ecbc3ecc9535c5013cad5e9e56dacc5d8a0`。
Case3 research-target miss 與 execution results 分開列於
[final report](PHASE1_CASE23_FINAL_REPORT.md)／[experiment log](PHASE1_CASE23_EXPERIMENT_LOG.md)。

Clean checkout 的兩 native exports、兩 inference、joint freeze 及兩 evaluations 全部實際執行。
原 controller `FAIL`、clean delivery `FAIL`、scoped `INCOMPLETE` receipts 原樣保留；
additive `delivery_metadata_comparison.json` 為 PASS，resolution scope 僅
`EXACT_OUTPUT_PATH_AND_VERIFIED_RRD_BATCH_BOOKKEEPING_ONLY`。
Independent full-recording comparison 的 Case1／Case2／Case3 **94／2042／6712 rows** 精確一致、0 differing rows；
原 log order、source timelines、static clears 與 components 保留，不主張 blueprint semantics。
Reader chunk/store count 的 Case3 1960／1957 差異不是候選或 source geometry 差異；
原 metrics／thresholds／candidate order／master／producers 未改，也未重新 infer／evaluate 來產生 adapter PASS。

A/B travel-time filter=false、C=true 是原 declared factor。Short-control gap00 的 B 為
2 geometric／1 timed、recall 2/2，並保留一個 untimed route；C 為 1 geometric／1 timed、recall 1/1。
兩個 fraction 1.0 的 eligibility denominator 不同，不能宣稱相同 feasibility population。

最後交付須同一 release 的 Case1–3 dataset、A/B/C＋supported single-factor ablations、
完整數值與圖表、RRD／static PNG／reader receipt、重建指令及 clean-checkout comparison。
只有全部實際 gates 成立才標 validated/frozen；Case 4 仍 deferred。
目前 global authority 仍為 **PARTIAL_APPROVED**，限 exact approved 六-cell scope；metadata adapter 不授 formal freeze 或整校 certification。
Actual `acceptance_verification.json` SHA `094b68c3487c556108cce76555c914697fa9c07519d5ad699767657a9059bf90`，
blockers=[]、all_research_targets_met=false、overall_metric_pass=null。
Workflow acceptance 包含完整報告負面研究結果；不能把它解讀為所有 research targets 達成。
