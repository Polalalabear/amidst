# Phase 1 Case1–3 final report / 聯合驗收報告

日期：2026-10-14。**狀態：PHASE1_EXIT_GATES_PASSED；18 actual gates PASS、blockers=[]、freeze_allowed=true。**
Primary 與 clean 的兩次 native exports、兩 child inference／joint pre-GT freeze／independent evaluations 均已實際完成，四個 scoped source cases 全 PASS；完整 repository validation 與 required demo reader checks 已 PASS。
Case3 的 ≥30% primary ADE gain 初始研究目標實測未達；Freeze 版本定名 `phase1-scoped-case123-20261014`；exact curated release SHA 由 annotated tag 綁定，實際 tag／remote publication 核對另存 release 的 local `publication_receipt.json`。 不能用 workflow PASS 代替 performance improvement。
原 primary／controller／clean FAIL outputs 保留；本報告不把 valid research execution 與 prototype target success 混為同一結論。

## 固定實驗與 authority

| 項目 | 本次值／證據 |
| --- | --- |
| Worktree／branch | `.local-worktrees/phase1-case23-formal`／`codex/phase1-case23-formal` |
| Code checkpoint | `c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d`；不替代後續實際 clean-checkout commit |
| Frozen master | `configs/finalization/case123_formal_experiment_v2.json`，SHA `55337cc70ac1c28ecaa4f9b0e586cb8679ef6a1b9c4b9c631ba98ac69f826fe8` |
| Source config | `configs/finalization/scoped_case23_export_v2.json`，SHA `d8f09bfa3fe31e420f9832deb18bed47bf55e73a9904bd757ffb6f174b876790` |
| Actual release | `data/finalization/reviewed_run_case123_formal_v2_20261014` |
| Immutable source | Canonical `blender/school_v3.blend`；468,300,506 bytes；SHA `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| Native runtime | Blender **5.2.1 LTS**, build `9e2066aef7ef`；兩個 actual export manifests 已保存 |
| Seeds／units／sampling | Export 20261005、inference 42；0.0247 m/BU；inclusive 5 Hz；Python 3.12.12／locked uv environment |
| Original search budget | Max speed 0.7904 m/s；K=1/2/3、max candidates 3、nodes 1000、path 24.7 m、time 10 s、branch factor 3、detour 2；未修改 |
| Metrics | Strict ADE <0.50 m coverage；Case1 ADE/FDE ≤0.5 m、Case3 FDE ≤1.0 m 是原 INITIAL_TARGET；缺測量保留 N/A |

Production class generation／independent inventory 各自的 resource caps 為 100000 labels／states、30 s，
由 master 分開固定，未取代原 Graph 的 1000 nodes／10 s policy。Aggregation visible-sample gap 為 0.200001 s。

Case1 選取 fresh original-office child 的原設定與 authority；其其他 office `BLOCKED`／local rows 保留，不改名為新 Case2／Case3。
後兩個 main cases 與 stress controls 只使用 `school-v3-corridor-six-cell-scope-v2` 的 exact closed union、source body guards、
原 collider／contact numerics 與 actual camera bindings。Local certificate content SHA 為
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`。
[Case2 addendum](../configs/finalization/case2_interior_branch_addendum_v1.json) 限定為該 union 的 interior branching；
不授予 architectural portal role。Global physical authority 仍 **PARTIAL_APPROVED**，不主張整校 walkability certification。

## 已完成的 bounded evidence

當次 clean input materialization receipt 記錄 297 verified files、187 missing files restored、110 existing matches、29 review-bound inputs；
review manifest SHA `923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187` 與原 checkpoint 相同。
原 durable 路徑已遺失，從保留工作樹的 `human_review` 恢復相同 bytes；未以 formal outputs 替換原 inputs，未複製 source assets。
原 physical `--verify-only` 已得到 VERIFIED，並保留 PARTIAL_APPROVED；不是新增 human approval 或擴張 source scope。
對應 receipts 是 release 下的 `clean_checkout_materialization_receipt.json`、`clean_checkout_physical_verification.json`。

兩次 native source exports 已完成，兩 manifests 均為 `source_saved=false`。
Office dataset manifest SHA：`a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`；
scoped dataset manifest SHA：`a30e9da156126ee7e2b7381f55f261a95dc5c8d65b3f2e79dac37854c01a4675`。
Office primary freeze 已寫入，GT=false，freeze SHA
`add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de`。
Scoped primary freeze SHA `b172144a366361f6a338a84f82ad79f637b4b2d3c51c420bbad93867ad2c8967`，GT=false；
joint freeze SHA `ff8043a679fd242e5c9d8cffbbfdcc63677c3710d08f6610555f485af610cdba`，status
`ALL_PRIMARY_CHILDREN_FROZEN_BEFORE_ANY_REFERENCE_EVALUATION`，綁定同 master／source 與 exact child manifests。
這些是當次 fresh execution evidence；相同 deterministic manifest hash 不代表沿用舊 raw run。
`primary_run_receipt.json` SHA `66d6bdd10e605876bb204f143c6ad449bc309db8ea414a87173e59b0fedf441d`，
整個 primary 的 source SHA／size／mtime before／after 完全相同；source_unchanged=true、formal_freeze_granted=false。
Whole-workflow diagnostic runtime 為 3044.5861455830163 s，與各 Case inference runtime 分開。

| Case／GAP | Actual time range (s) | C source-route candidates | Timing hypotheses | C termination |
| --- | --- | --- | --- | --- |
| Case2 gap00 | 5.8–27.2 | 2 | 4 | COMPLETE |
| Case2 gap01 | 27.2–32.6 | 1 | 2 | COMPLETE |
| Case2 gap02 | 32.6–38.8 | 1 | 2 | COMPLETE |
| Case3 gap00 | 37.4–101.2 | 2 | 4 | COMPLETE |
| Case3 gap01 | 101.8–117.8 | 1 | 2 | COMPLETE |
| Case3 gap02 | 118.2–136.0 | 1 | 2 | COMPLETE |
| Case3 long stress gap00 | 54.8–182.2 | 2 | 4 | COMPLETE |
| Case3 long stress gap01 | 183.6–215.4 | 1 | 2 | COMPLETE |
| Case3 long stress gap02 | 216.4–252.0 | 1 | 2 | COMPLETE |
| Case3 short control gap00 | 22.8–33.6 | 1 | 1 | COMPLETE |
| Case3 short control gap01 | 33.6–39.4 | 1 | 1 | COMPLETE |

K 計算 fixed-endpoint integer-winding classes 的 canonical shortest representatives；多個 timings 不增加 route K，缺少 K=3 不補候選。
此 COMPLETE 是 C 對已宣告 consumer grammar 的 termination；11 份 raw full visibility Graph 均保留 MAX_BRANCH_FACTOR、
0 candidates、expanded_nodes=1，沒有改成 COMPLETE。部分 shortest-path variants 保留 MAX_PATHS_REACHED；
不宣稱無限 continuous paths 或整個未核准 3D domain 已窮盡。
11 份 C source-eligibility receipts 的 denominator complete=true、ambiguous winding signatures 為空；
class_generation_complete=true、class_selection_truncated=false。完整 metric population 已有 88 份 scoped receipts：77 EVALUATED＋11 N/A。
11 份 C records 的 actual camera handoffs 為 0；same-camera HOLD 另驗 source-bound relation。
零 declared transition denominator 的 scoped transition rate 保持 N/A，不造 self transition 或把 N/A 改成 0。
每 GAP 保存 A/B/C＋5 個 supported ablation entries；11 個 remove_topology 為 N/A，原因是 source-bound HOLD 沒有可移除 handoff filter。
共 88 variant entries＝77 EXECUTED＋11 N/A；此 execution population 不代替 metrics／full Exit 判定。

A/B 的 travel-time filter=false、C=true 是原 protocol 的 declared baseline factor 差異；source inventory／eligibility 依各 method 的實際 mask 建立。
共同 source geometry、data／authority、configured speed 與 search bounds 保留，不能把不同 filter 的 recall fractions 當成相同 feasibility population。
Actual short-control gap00：B 有 **2 geometric routes／1 timed hypothesis、recall 2/2**，並在 `timing_unavailable_route_ids` 保留 1 個 untimed route；
C 有 **1 geometric route／1 timed hypothesis、recall 1/1**，untimed records 為空。兩個 1.0 的 denominator 不同，須並列 numerator／denominator 與 timing availability。
兩個 main cases 的 first GAP，B／C denominator 均為 2、recall 均 2/2；不把 short control 的 different declared universes 混為此共同人口。

相較於原 main v1 demo／office temporal-component 展示，本次新增 exact union 的 source-bound class alternatives、independent eligibility
與完整 joint delivery 入口；原展示沒有提供本次 branching／stress 驗收證據。本任務沒有回寫 main demo 或其服務。
[Source-v1](../data/finalization/case23_scope_audit_20261014/integration_probe.json) 僅是 engineering readiness probe；Case2 first GAP 有 1 class。
V2 在 reference／accuracy evaluation 前，依公開 source branch length 與原 approved speed 固定較慢的 Case2 schedule，
first GAP 現為 2 candidates；visible recoveries／GAP population 也改變。兩版本分開報告，不稱相同人口的 accuracy improvement。
Case3 的 peak C counts 為 main 2 > short 1、long 2 plateau；short 有 2 GAP，main／long 各 3 GAP。
三組實際 native anchors 已核對為不同，這是 separate source-recipe populations，不宣稱單由 GAP duration 引起的 matched-anchor 因果。

## Primary 結果與交付矩陣

`verification.json` SHA `825d864b5b7a5610f1f2ee3ab15eef875f717c048f5778e910d978ba17c3f10f`：
formal_case_execution_complete=true、Case1／Case2／Case3 各 PASS、blockers=[]。
Scoped summary SHA `81365debae105b9644ef229b5dcc1fafb4dd7668fd50606c9783e6eeae8ec17a`，main 與兩個 controls 全 PASS。

| Primary／control | Execution result | C evidence／target result |
| --- | --- | --- |
| Case1 original-office | PASS | 1 candidate；ADE 0.000015968095443362998 m、FDE 0.000007390309426983255 m，均 ≤0.5 m；recall=1、collision／constraint／impossible-transition rates=0 |
| Case2 exact union | PASS | 3 GAP，candidates `[2,1,1]`；first GAP 保留 2 source classes；C recall=1、collision／constraint／HOLD-invalid rates=0 |
| Case3 main exact union | PASS execution；30% ADE research target NOT MET | 3 GAP，candidates `[2,1,1]`；每 gap FDE≤1 m；C recall=1、collision／constraint／HOLD-invalid rates=0；ADE gain 詳下表 |
| Case3 short control | PASS control execution | 2 GAP，C candidates `[1,1]`；different actual anchors 與 B timing-unavailable record 保留 |
| Case3 long stress | PASS control execution | 3 GAP，C candidates `[2,1,1]`；peak=2 plateau，原 path／detour bounds 保留 |

Joint benchmark 有 **288 rows＝selected Office Case1 24＋scoped 264**；不把 K 重複列當成多次 runtime／count measurements。
原 Office child overall PHASE1_FINALIZATION_BLOCKED、old Case2 blocker 與 Office Case3 temporal-only scope 保留，不 remap。
Root verification 的原 output 仍為 PHASE1_FINALIZATION_BLOCKED、freeze_allowed=false、reproduction_status=PENDING；
其 repository_validation_status=PENDING 是 assembler 的原欄位，當次獨立 repository-validation PASS receipt 另列下節，未回寫 producer outputs。

Independent source readiness audit SHA `c70eacc4d441dccbe1e68c8d582bc49b805a4e359a1b6393eedcfed108fa9524`（181,764 bytes），
保存 pre-GT source/class/eligibility／recovery 證據與 11 份 raw MAX_BRANCH_FACTOR；其研究目標 classification 仍 PENDING，
這是 immutable pre-GT record，不當成 post-GT 30% gain PASS。

Required Case1／Case2／Case3 primary recordings 的 reader checks 已 verified，primary GT=false。
Scoped Case2／Case3 分別有 1 recording、645／1960 chunks/store，required source layers 與 primary GT absence=true；
各 RRD／preview hashes 與 presentation receipts 相符。
`static_visual_review.json` SHA `8a15ad4352155ac32ef7ddfb972f73602434a3ed57455526fa8b1e5457729456`：
三張 actual preview 為 PASS_BOUNDED_PRESENTATION_QA；human_approval_granted=false、formal_authority_granted_by_visual_review=false。

## Case3 初始研究目標：實測 ADE gain 未達 30%

[PRD §20](PRD.md#20-baseline-與-ablation) 保留 `ADE_C ≤ 0.7 × ADE_A` 的 ≥30% relative ADE gain 初始研究目標。
下列值讀自本次已建立 joint freeze 之後產生的 `scoped/evaluation/metrics/case3/<gap>/{shortest_path,spatiotemporal}.json`，
不讀取 reference GT／recipe。Gain＝`100 × (ADE_A − ADE_C) / ADE_A`；baseline ADE=0 時為 N/A。

| Case3 main GAP | A primary ADE (m) | C primary ADE (m) | Relative gain | Research-target result |
| --- | --- | --- | --- | --- |
| gap00 | 0.018171065107691734 | 0.018171065107691734 | 0.0% | INITIAL_RESEARCH_TARGET_NOT_MET |
| gap01 | 0.009240328122400842 | 0.009240328122400842 | 0.0% | INITIAL_RESEARCH_TARGET_NOT_MET |
| gap02 | 0.0016397145268424193 | 0.0016397145268424193 | 0.0% | INITIAL_RESEARCH_TARGET_NOT_MET |

A 與 C 的 primary timed points 相同，實測 primary ADE 也相同；候選 alternatives 的增加不是 primary ADE performance improvement。
逐 gap 報告，不跨 Case 平均；此目標不移除、不 waive、不改寫原 protocol JSON。
`overall_pass_fail=false` 的 protocol execution／Exit evidence 與研究目標成敗各自報告，不能以 execution complete 宣稱達成 30%。

## 當次 repository validation

`repository_validation.json`：SHA `d7d190657880a8e3c5b622562e31d1db6a8a969df1228ff9d88c0fd48e9c3b78`，
code／master 分別綁定上述 `c4a8a0...`／`55337cc...`。Full population＝1978 original＋204 new＝**2182 passed、0 failed、0 skipped**。
Pytest stdout 為 **619.92 s**；receipt 的全 validation workflow elapsed 為 **622.9199775409943 s**，兩者 measurement boundary 不同。
Ruff／mypy／diff checks PASS；master／producer／source unchanged=true、Phase2 modified=false；`formal_joint_acceptance_granted=false`。

主線另外執行 16 個 controller targeted regressions PASS，controller-validation receipt SHA
`a996b6f9bd2f9050efeb133ea502224c5c931ac4f2822cce04bb63d975393e6f`，不加總進上述 2182 的 frozen-code suite population。
Curated orchestration helper `scripts/reproduce_case23_parallel.py` SHA
`5e09179a42a01073f1d5d20c4f1f938ec5ef2add971305c24f2b06ee3fed1d79` 在 master producer／protected closure 外，
不改 frozen inference producers；controller unit PASS 也不是 actual reproduction／clean delivery PASS。
Actual reproduction 已完成 curated parallel controller 的五個 fresh-interpreter workers，mode 為 `PARALLEL_FROZEN_PUBLIC_APIS_NOT_ORIGINAL_SEQUENTIAL_RUNNER`。
兩 child 的 repeat／fresh／order／GT-recipe-annotation poison comparisons 與 termination gates PASS；與原 sequential CLI 分開記錄。
Original-office wrapper reproduction PASS，原 office scope／blocked rows 保留；scoped 四個 cases 的 GT metric sensitivity 已測且 unavailable 清單為空。

## Clean delivery 與 bounded additive resolution

實際 clean checkout 是 `.local-worktrees/phase1-case23-clean`，HEAD `c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d`；
clean spec SHA `90ecd007b3a36bf531b20d02bb13fcbbf2e1913221e23a02b55defad532e4501`。
Clean 的兩 native exports／兩 inference／joint freeze／兩 evaluations 全部實際執行；joint freeze SHA 與 primary 同為 `ff8043a679fd242e5c9d8cffbbfdcc63677c3710d08f6610555f485af610cdba`。
Clean `primary_run_receipt.json` SHA `249cd5ad1a211acb879669ac93c263fbe16a39c5ece031a744422b6acc3e2bcd`，source_unchanged=true；
1860.2107627909863 s 為整個 clean workflow diagnostic，非 Case inference runtime。

原 `reproduction/joint_reproduction_receipt.json` 仍為 **FAIL**，SHA `d9d0e9bd288832b50140641734e7464c72bb00a3680fa2fbea4ac4ce8e97c683`；
clean `delivery_comparison.json` 仍為 **FAIL**，SHA `f17d26970d58682067e1f60c42334bdb40b878acdc0bab53938c0b3475874047`；
原 scoped reproduction `INCOMPLETE` receipt SHA `367bd454343c1960bb70e86a55df2f226e1035ad0ff7fc9a393ae1b3bd0dae44`。
它們未被覆寫或重新標 PASS。差異是 Case3 presentation 的 reader chunk/store counts 及 summary 的同項 bookkeeping／exact output paths。

Independent `rrd_semantic_comparison.json` SHA `eb5515ad963b4569696533ef1caecc9e4d12fcc2e0381c3fd5f65e9f50118605`：
Case1／Case2／Case3 的完整 data recordings 分別 **94／2042／6712 canonical log rows** 精確一致、0 differing rows；
all components、source event-time／sequence、static clears 與 equal-time log order 保留。
只排除 container IDs、SDK wallclock／creation time、store UUID、chunk segmentation 與其 derived flags；不主張 blueprint semantics。
Case3 primary／clean 的 reader chunk/store counts 實際為 1960／1957，兩 recording 的 source payload 相同。

Additive `delivery_metadata_comparison.json` SHA `dcc0f2112e1650ef7f6438dda6328983962aa8c8826879368baedd1614159391` 為 **PASS**；
scope=`EXACT_OUTPUT_PATH_AND_VERIFIED_RRD_BATCH_BOOKKEEPING_ONLY`，重新核 original comparators 與完整 semantic proof。
僅新增 exact verified output path、reader chunk/store count 的三個明列 exclusions；其餘 frozen comparison rules 不變。
Master／producer／source／metrics／thresholds／candidate order 未改，未重新 export／infer／evaluate；原 FAIL receipts 保留。
Adapter／semantic helper SHA 分別為 `c991c920b2d74160ac87224568d763fbdcd97974babda1f544e8787ea0602b16`／`603e18096e5b84627a7069079d0a581258f037f28417e7e75c3262c4aa5b3131`。
其 targeted validation 是 metadata 26 tests、semantic 16 tests；final closeout helper `71d0a031fcec47e2a6d2a4b3e3be14c229c2a7246e3c65e938a122b8cc5f8d8d` 的 59 tests PASS，均不加總進 2182。
Adapter 與上述 validation receipts 均不自行授 formal acceptance／freeze。
Actual `final_population_validation.json` SHA `b1eae21c10197c7fe2ff3ff93be37ecbc3ecc9535c5013cad5e9e56dacc5d8a0` 核對
current collected node IDs 與五份 executed cohorts 的 log／JUnit／receipt union：
**2299 unique tests＝2182 full＋16 controller＋59 closeout＋26 metadata＋16 semantic，0 failed／0 skipped**，沒有 missing／obsolete node IDs。
這是已實際執行 cohorts 的 disjoint union，不是單次 2299 full-suite run；frozen-code 2182 execution 的 scope 不變。
Final full Ruff PASS，`final_ruff_v1.log` SHA `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。

## Actual workflow closeout 與 benchmark handoff

Actual `acceptance_verification.json` SHA `094b68c3487c556108cce76555c914697fa9c07519d5ad699767657a9059bf90`：
**PHASE1_EXIT_GATES_PASSED、18 gates PASS、blockers=[]、freeze_allowed=true**。
Scope=`COMPLETE_CASE1_3_WORKFLOW_WITH_VALID_NEGATIVE_RESEARCH_RESULTS`；
all_research_targets_met=false、overall_metric_pass=null、overall_pass_fail_enabled=false。
School surface authority=NOT_CERTIFIED，global authority=PARTIAL_APPROVED；同 camera transition rate 保留 N/A 並另驗 HOLD。
第一次 closeout CLI 的 expected-controller hash 輸入錯誤正確觸發 BLOCKED，receipt
`acceptance_invocation_controller_hash_typo_v1.json` SHA `3dd5832f14c7e0b5233821daa164052e4d221c897f59634dd3ab1aab946439f5` 原樣保留。
第二次只修正 invocation 的 expected hash；actual files／master／producers 未變，未重新 inference 或 metrics。
這份 additive acceptance 才是當次 workflow Exit 結果；原 assembly `verification.json` 仍 BLOCKED／freeze_allowed=false，不回寫。

| Gate／交付 | 此 snapshot 狀態 | Closeout 必要證據 |
| --- | --- | --- |
| Scoped controls／完整 inference | COMPLETE_AND_FROZEN | 4 cases／11 GAP／88 variant entries，保留 N/A 與原 raw termination；scoped freeze SHA 如上 |
| BOTH-child joint freeze | COMPLETE | 兩 child exact manifest／source／seed／config／GT=false；joint freeze SHA 如上，在任何 GT evaluation 之前 |
| Independent metrics／tables／charts | PRIMARY_COMPLETE | 288 joint rows、88 scoped receipts；Case1–3／controls execution PASS；Case3 ADE gain 0% target未達 |
| Source-bound demos／RRD reader | VERIFIED_PRIMARY_AND_CLEAN | Required artifacts／reader；full semantics 94／2042／6712 rows exact，static QA 不授 human approval |
| Repeat／fresh／order／poison | PASS_COMPARISONS | 兩 child 實際執行與 comparisons PASS；四個 scoped cases 的 GT sensitivity 已測，原 termination ledger 保留 |
| Clean-checkout full delivery | EXECUTED_AND_ADDITIVE_COMPARISON_PASS | 原 controller／clean FAIL 保留；actual native full rerun＋bounded metadata adapter PASS，不自行授 Exit |
| Full repository validation | PASS | 2182／0／0、619.92 s pytest；Ruff／mypy／diff checks及 receipt 已完成 |
| Full Exit workflow | PHASE1_EXIT_GATES_PASSED | 新 acceptance receipt 的 18 gates PASS／freeze_allowed=true，原 FAIL outputs 保留 |
| Freeze 版本 | `phase1-scoped-case123-20261014` | Exact curated release SHA 以 annotated tag target 為準；producer milestone c4a8a0ac 保留 |
| Tag／publication | SEPARATE_VERSIONED_PUBLICATION_RECEIPT | 實際 local tag、remote sprint/tag SHAs 與 payload hashes 另存 local publication receipt；不由驗收 adapter 自授 |

重建入口見 [reproduction guide](PHASE1_CASE23_REPRODUCTION.md)，當次進度與填表入口見
[experiment log](PHASE1_CASE23_EXPERIMENT_LOG.md)。當次 original FAIL 與 additive PASS 均須保留；freeze tag 與實際 remote publication 由獨立 publication receipt 記錄。
Cross-case Coverage@3 weighting 未核准，保持 separate case／gap populations；不算未授權 overall target PASS。

Raw datasets、GT／recipes、native source、physical blobs、RRD／large plots 保持 LOCAL。
此工作樹、raw outputs 與 receipts 在共享工作／驗證完成前分類為 KEEP；清理規則依 reproduction guide，沒有自動 DeleteCandidate。
Case4 是 DEFERRED。Phase2 未由本任務修改；其他 chat 的 active work 不在本報告中標為 frozen。
