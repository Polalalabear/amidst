# Phase 1 Case1–3 experiment log / 當次實驗紀錄

日期：2026-10-14。**PHASE1_EXIT_GATES_PASSED；18 actual gates PASS／blockers=[]／freeze_allowed=true。**
此紀錄只涵蓋本次 actual release；primary／clean native workflows、reproduction comparisons、metadata resolution 與 repository validation 已完成。
Freeze 版本定名 `phase1-scoped-case123-20261014`；exact curated release SHA 由 annotated tag 綁定，實際 tag／remote publication 核對另存 release 的 local `publication_receipt.json`。 all_research_targets_met=false，不能把 workflow PASS 當成研究目標全達成。
Release：`data/finalization/reviewed_run_case123_formal_v2_20261014`。
完整 scope／固定參數見 [final report snapshot](PHASE1_CASE23_FINAL_REPORT.md)，CLI 見 [reproduction guide](PHASE1_CASE23_REPRODUCTION.md)。

## Definition 與原輸入

- 在 `codex/phase1-case23-formal`、checkpoint `c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d` 執行；原 producer／HR／protocol／Phase2 不回寫。
- Master `configs/finalization/case123_formal_experiment_v2.json` 在新 source simulation／inference 前固定，file SHA
  `55337cc70ac1c28ecaa4f9b0e586cb8679ef6a1b9c4b9c631ba98ac69f826fe8`；68 protected-input pins、116 producer pins，無 self-hash。
- Source-config v2 file SHA `d8f09bfa3fe31e420f9832deb18bed47bf55e73a9904bd757ffb6f174b876790`。
  Source SHA `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；0.0247 m/BU、export seed 20261005、inference seed 42、5 Hz。
- 保留原 0.7904 m/s、K=1/2/3、max candidates 3、1000 nodes、24.7 m、10 s、branch 3、detour 2；aggregation gap 為 0.200001 s。
  Class-generation／inventory 各 100000 labels／states、30 s 的 resource caps 與原 Graph budget 分開固定。
- Case1 為 fresh original-office child；Case2／Case3 為 exact approved 六-cell union。Case2 interior addendum 不授予 portal role，global authority 保持 PARTIAL_APPROVED。

## 已完成的 actual stages

| Stage | 已驗 facts | 證據（相對 release） |
| --- | --- | --- |
| Exact-input materialization | 297 files verified；187 restored／110 existing；29 review-bound inputs；formal outputs 未作原 inputs；source assets symlink，無 copy | `clean_checkout_materialization_receipt.json` |
| Original physical verify-only | VERIFIED；原 PARTIAL_APPROVED 保留；new scope／human approval=false | `clean_checkout_physical_verification.json` |
| Scoped native export | Blender 5.2.1 LTS／build `9e2066aef7ef`；source_saved=false；manifest SHA `a30e9da156126ee7e2b7381f55f261a95dc5c8d65b3f2e79dac37854c01a4675` | `scoped_export.log`, `scoped/dataset/manifest.json` |
| Office native export | 相同 native runtime／source；source_saved=false；manifest SHA `a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5` | `office_export.log`, `office/dataset/manifest.json` |
| Office primary freeze | FROZEN_BEFORE_EVALUATION，GT=false；SHA `add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de` | `office/inference_primary/inference_freeze.json` |
| Full scoped primary freeze | GT=false；SHA `b172144a366361f6a338a84f82ad79f637b4b2d3c51c420bbad93867ad2c8967`；372 canonical artifacts | `scoped/inference_primary/inference_freeze.json` |
| 4 cases／11 GAP | Case2／Case3／long 各 candidates `[2,1,1]`、timings `[4,2,2]`；short 2 GAP、candidates `[1,1]`、timings `[1,1]`；C 均 COMPLETE | `scoped/inference_primary/summary.json`、各 `spatiotemporal/run.json` |
| BOTH-child pre-GT freeze | SHA `ff8043a679fd242e5c9d8cffbbfdcc63677c3710d08f6610555f485af610cdba`；exact master／source／children／datasets；GT=false | `joint_inference_freeze.json` |
| Office independent evaluation | 已完成；原 PHASE1_FINALIZATION_BLOCKED／Case2 blocked scope 保留，未 remap | `office/evaluation/verification.json` |
| Scoped independent evaluation | All 4 source cases PASS；264 rows；88 metrics＝77 EVALUATED＋11 N/A；summary SHA `81365debae105b9644ef229b5dcc1fafb4dd7668fd50606c9783e6eeae8ec17a` | `scoped/evaluation/summary.json` |
| Joint primary verification | Case1–3 PASS／blockers=[]、formal_case_execution_complete=true；288 rows＝24＋264；freeze_allowed=false | `verification.json`，SHA `825d864b5b7a5610f1f2ee3ab15eef875f717c048f5778e910d978ba17c3f10f` |
| Source whole-primary integrity | SHA／size／mtime before／after 相同；source_unchanged=true；3044.5861455830163 s whole-workflow diagnostic，非 Case runtime | `primary_run_receipt.json`，SHA `66d6bdd10e605876bb204f143c6ad449bc309db8ea414a87173e59b0fedf441d` |
| Required demos／reader | Case1／Case2／Case3 verified；primary GT=false；scoped 1 recording、645／1960 chunks/store | 各 `evaluation/demos/<case>/presentation.json` |
| Static preview QA | 3 images PASS_BOUNDED_PRESENTATION_QA；不是 human approval／formal geometry grant | `static_visual_review.json`，SHA `8a15ad4352155ac32ef7ddfb972f73602434a3ed57455526fa8b1e5457729456` |
| Full repository validation | 2182 passed／0 failed／0 skipped；pytest 619.92 s，workflow 622.9199775409943 s；Ruff／mypy／diff PASS | `repository_validation.json` |
| Actual reproduction | Original-office 與 scoped repeat／fresh／order／GT-recipe-annotation poison／termination comparisons PASS；四個 scoped cases 的 GT sensitivity 已測 | `reproduction/joint_reproduction_receipt.json`／`reproduction/verification.json`；原 overall FAIL／INCOMPLETE 保留 |
| Clean native workflow | Initial clean c4a8 checkout；兩 native exports＋兩 inference＋joint freeze＋兩 evaluations 全實際執行；source_unchanged=true | clean `primary_run_receipt.json` SHA `249cd5ad1a211acb879669ac93c263fbe16a39c5ece031a744422b6acc3e2bcd` |
| Full recording semantics | Case1／2／3 完整 94／2042／6712 canonical log rows exact、0 differing；static clears／source timelines／components／log order 保留 | `rrd_semantic_comparison.json`，SHA `eb5515ad963b4569696533ef1caecc9e4d12fcc2e0381c3fd5f65e9f50118605` |
| Bounded metadata adapter | PASS；僅 exact verified output path／reader chunk-store bookkeeping；source／metrics／thresholds／order 未改，沒有重新 infer／eval | `delivery_metadata_comparison.json`，SHA `dcc0f2112e1650ef7f6438dda6328983962aa8c8826879368baedd1614159391` |
| Actual workflow closeout | PHASE1_EXIT_GATES_PASSED；18 PASS、blockers=[]、freeze_allowed=true；target miss／partial authority 保留 | `acceptance_verification.json`，SHA `094b68c3487c556108cce76555c914697fa9c07519d5ad699767657a9059bf90` |

Hydration 使用本次 wrapper 的 checkout-bound receipt，review manifest SHA
`923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187` 與原 checkpoint 相同。
原 canonical durable 路徑已不存在；fallback 是保留工作樹的同一 `human_review` bytes，沒有生成替代 review frames。
Historical 2026-10-08 receipts 只作原 pin／provenance，不當作本次全流程 PASS。

原 main v1 demo／office 的單一路徑與 temporal-component 展示不作新 branching／stress 的證據；main demo／服務未由本次回寫。
[Source-v1](../data/finalization/case23_scope_audit_20261014/integration_probe.json) 的 Case2 first GAP 為 1 class，僅 engineering probe；V2 固定較慢的 source schedule 後，actual first GAP 為 2 candidates，
且 Case2 的 recovery／GAP population 改變。這是不同固定設定與觀測人口，不以 GT 選擇 inference、不報 matched-population accuracy gain。
K 是 source class 數，timing hypotheses 分開記錄；原 raw visibility Graph 的 MAX_BRANCH_FACTOR 等 ledger 不覆蓋成 COMPLETE。
11 份 raw ledger 均為 MAX_BRANCH_FACTOR／0 candidates／expanded=1；C generation complete、selection 未 truncate、eligible denominator complete。
每 GAP 的 8 variant entries 完整保存：77 EXECUTED＋11 remove_topology N/A；部分 shortest-path MAX_PATHS_REACHED 留原值。
Case3 peak main 2 > short 1、long 2 plateau；actual anchors 不同，沒有 matched-anchor duration 因果結論。
A/B travel-time filter=false、C=true 是原 declared factor；inventory 與 eligibility 以實際 mask 定義人口。
Short-control gap00 的 B 保存 2 geometric／1 timed、recall 2/2 與 1 untimed route；C 是 1 geometric／1 timed、recall 1/1。
雖然 fractions 都是 1.0，denominators／timing availability 不同，不宣稱相同 feasibility population；main Case2／Case3 first GAP 的 B／C 則均為 2/2。
共同 source geometry、data／authority、configured speed／bounds 保留；本紀錄不改寫 metrics 或 original factor definitions。

## 已測研究目標與 validation 邊界

[PRD §20](PRD.md#20-baseline-與-ablation) 的 Case3 ≥30% relative ADE gain 初始研究目標保留。
Actual main gap00／01／02 的 A 與 C primary ADE 分別同為
`0.018171065107691734`／`0.009240328122400842`／`0.0016397145268424193` m；三個 positive baseline 的 gain 均 **0.0%**，
逐 gap 結果為 **INITIAL_RESEARCH_TARGET_NOT_MET**。Baseline=0 時 gain 為 N/A；不跨 Case 平均、不宣稱 performance improvement。
資料來自 joint freeze 之後的 metric JSON；valid execution／reproduction／Exit gates 與 target success 分開記錄，不 waive 目標或修改原 protocol。
Case1 C ADE／FDE 分別為 0.000015968095443362998／0.000007390309426983255 m，原 ≤0.5 m targets 成立；
Case3 各 gap FDE≤1 m，但不能用 FDE target 或 class recall 取代未達成的 30% primary ADE gain。
Source-readiness audit SHA `c70eacc4d441dccbe1e68c8d582bc49b805a4e359a1b6393eedcfed108fa9524` 是 immutable pre-GT receipt，
原 research-target classification=PENDING 留原值；post-GT 0% 結果在此另記。

Full suite 是 1978 original＋204 new 的當次 c4a8 checkpoint population；validation receipt SHA
`d7d190657880a8e3c5b622562e31d1db6a8a969df1228ff9d88c0fd48e9c3b78`，並確認 master／producer／source unchanged 與 Phase2 modified=false。
另 16 個 controller targeted regressions PASS 獨立計數，receipt SHA `a996b6f9bd2f9050efeb133ea502224c5c931ac4f2822cce04bb63d975393e6f`，不加進 2182；curated helper SHA
`5e09179a42a01073f1d5d20c4f1f938ec5ef2add971305c24f2b06ee3fed1d79` 不在 frozen producer／protected closure 內，不取代 actual reproduction 證據。
Actual parallel reproduction controller 的五個 fresh-interpreter workers 全已執行，mode `PARALLEL_FROZEN_PUBLIC_APIS_NOT_ORIGINAL_SEQUENTIAL_RUNNER`；
原 sequential runner 與此 curated public-API orchestration 不混稱。Original controller FAIL SHA
`d9d0e9bd288832b50140641734e7464c72bb00a3680fa2fbea4ac4ce8e97c683`、clean FAIL SHA
`f17d26970d58682067e1f60c42334bdb40b878acdc0bab53938c0b3475874047`、scoped INCOMPLETE SHA
`367bd454343c1960bb70e86a55df2f226e1035ad0ff7fc9a393ae1b3bd0dae44` 均原樣保留。
差異限定為 exact output path 與 RRD batching-derived reader counts；Case3 primary／clean chunks/stores=1960／1957，但完整 6712 semantic rows 相同。
Additive adapter resolution scope=`EXACT_OUTPUT_PATH_AND_VERIFIED_RRD_BATCH_BOOKKEEPING_ONLY`，不主張 blueprint semantics、不新增 source／metric exclusions。
Adapter SHA `c991c920b2d74160ac87224568d763fbdcd97974babda1f544e8787ea0602b16`、semantic helper SHA
`603e18096e5b84627a7069079d0a581258f037f28417e7e75c3262c4aa5b3131`；原 producers／master／FAIL receipts 不回寫。
Supplemental controller 16、closeout 59、semantic 16、metadata 26 tests 各保存 actual cohort receipts，與 2182 full-suite population 分開記錄；
actual `final_population_validation.json` SHA `b1eae21c10197c7fe2ff3ff93be37ecbc3ecc9535c5013cad5e9e56dacc5d8a0` 為 PASS。
Current collected node IDs 與 actual log／JUnit／receipt sets 的 disjoint union 精確相同：
**2299 unique executed tests＝2182＋16＋59＋26＋16，0 failed／0 skipped，missing／obsolete lists empty**；不是單次 2299 full-suite rerun。
Final full Ruff PASS，`final_ruff_v1.log` SHA `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。

Closeout helper SHA `71d0a031fcec47e2a6d2a4b3e3be14c229c2a7246e3c65e938a122b8cc5f8d8d`。
第一次 expected-controller CLI hash typo 的 BLOCKED receipt `acceptance_invocation_controller_hash_typo_v1.json`，SHA
`3dd5832f14c7e0b5233821daa164052e4d221c897f59634dd3ab1aab946439f5` 保留；只修 invocation hash 的第二次 actual audit PASS。
原 assembly verification 仍 BLOCKED，不回寫；新 acceptance 的 overall_metric_pass=null／all_research_targets_met=false，tag_or_publication_granted=false。

## Closeout ledger

Actual workflow 已核對；版本／publication 使用獨立 receipt，未核准的跨案例指標維持 N/A：

| 項目 | 本 snapshot 狀態 | 待填 actual evidence |
| --- | --- | --- |
| 全 scoped source cases／stress／ablations | COMPLETE_AND_FROZEN | 4 cases／11 GAP／88 variants；summary 與 scoped freeze 已核對 |
| BOTH-child pre-GT boundary | COMPLETE | Joint freeze SHA 如上；exact children／datasets hashes 已核對 |
| Independent evaluation | PRIMARY_COMPLETE | 3 formal cases／4 scoped source cases PASS；Case3 main ADE gain 0% target未達另列 |
| Tables／charts | PRIMARY_COMPLETE | 288 joint rows／88 scoped metrics receipts；N/A 保留，repeated K counts／runtime不加總 |
| Demos／actual RRD reader | VERIFIED_PRIMARY | Case1／Case2／Case3 recording／PNG／presentation／reader；static QA不授human approval |
| Original-office reproduction | PASS | Repeat／fresh-process／order／GT-recipe-annotation poison／termination；原 office blocked scope 保留 |
| Scoped reproduction | PASS_COMPARISONS_WITH_ORIGINAL_INCOMPLETE_PRESERVED | Repeat／fresh／order／poison comparisons PASS；additive metadata resolution 經 final acceptance 核對 |
| Clean-checkout full delivery | PASS_ADDITIVE_ACCEPTANCE | Exact c4a8／完整 native rerun；原 clean FAIL 保留，18-gate acceptance 確認限定 metadata resolution |
| Repository validation | PASS | 2182／0／0、Ruff／mypy／diff、immutable input checks 已完成；不自授 formal acceptance |
| Source whole-workflow integrity | PRIMARY_AND_CLEAN_VERIFIED | Primary／clean／reproduction source fingerprints 相同；沒有 .blend save／copy |
| Final workflow closeout | PHASE1_EXIT_GATES_PASSED | acceptance 18 gates PASS、freeze_allowed=true；bounded source scope／research target miss 保留 |
| Freeze 版本／tag／publication | `phase1-scoped-case123-20261014` | Exact tag/remote SHAs 另存 publication receipt，不由驗收 adapter 自授 |

Original-office child 的舊 Case2 `BLOCKED`／Case3 temporal-only scope 不 remap；新的 scoped results 有自己的 definition／dataset／receipt。
Main／short／long controls 的 actual anchors 可能不同，candidate growth 記錄必須包含各自 frozen queries；不宣稱僅由 GAP duration 造成差異。
沒有核准 cross-case weighting，不計 overall Coverage@3。Case4 DEFERRED；Phase2 本次未修改，其其他 chat 仍可 active。

Raw source／GT／recipes／numerical blobs／RRD／large plots 保持 LOCAL；本 checkout、raw receipts、hydration inputs 與 source assets 在共享工作完成前 KEEP。
不自動 DeleteCandidate、不清他人 worktree／服務；完成後依新授權與 runtime／unique-evidence 核對處理。
