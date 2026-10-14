# Phase1 scoped Case1–3 release — 2026-10-14

Authoritative workflow verdict: [acceptance_verification.json](acceptance_verification.json),
PHASE1_EXIT_GATES_PASSED,18/18 gates PASS,freeze_allowed=true.
Annotated freeze identifier: `phase1-scoped-case123-20261014`;
actual tag/remote SHAs are checked separately in local `publication_receipt.json` after publication.
The [package manifest](release_package_manifest.json) binds the reviewed payload without including itself.

[Full standards and demo comparison](../../../docs/PHASE1_CASE23_ACCEPTANCE.md),
[final report](../../../docs/PHASE1_CASE23_FINAL_REPORT.md),
[reproduction guide](../../../docs/PHASE1_CASE23_REPRODUCTION.md),
[experiment log](../../../docs/PHASE1_CASE23_EXPERIMENT_LOG.md).

The root [benchmark table](benchmark_table.md) has288 rows:255 evaluated and33 N/A.
[Full repository validation](repository_validation.json) executed2182 tests with real physical evidence;
[final population validation](final_population_validation.json) binds all2299 currently collected tests
to2182 full-suite and117 supplemental executed tests (0failed/0skipped), not one2299-test run.
[Joint inference freeze](joint_inference_freeze.json) precedes all office/scoped reference evaluations.
[Source readiness](source_readiness_audit.json) is GT-free and preserves the11 raw visibility-graph failures.

Original assembly `verification.json` stays BLOCKED; original controller/clean comparison FAIL and
scoped INCOMPLETE receipts stay unchanged in local raw folders. The strict additive
[metadata comparison](delivery_metadata_comparison.json) resolves only the verified output paths and
RRD chunk/store bookkeeping. [Full RRD data semantics](rrd_semantic_comparison.json) match94/2042/6712rows
for Cases1/2/3 with0different rows; source/event timelines, values and log order are retained.
Original UUID/log_time/creation-time/container differences are documented explicitly. Blueprint layout
semantics are outside the original data-recording reader gate and are not claimed.

`acceptance_invocation_controller_hash_typo_v1.json` is the preserved first closeout attempt, blocked
by a mistyped expected controller hash in the command. Correcting only that command argument produced
the new final acceptance receipt; frozen code/config/data/metrics were unchanged.
Older closeout/semantic helper validation versions are historical; current receipts are
`closeout_validation_v3.json`, `controller_validation.json`, `delivery_metadata_validation.json`
and `rrd_semantic_validation.json`.

Case3 primary ADE gain versus A is0%, so the initial30% research target is TARGET_MISSED.
No overall metric PASS or unapproved cross-case weighting is claimed. Authority remains
PARTIAL_APPROVED for the original office and approved six-cell union; school surface NOT_CERTIFIED;
Case4 DEFERRED. Active Phase2, main demo, source Blender and shared services were not modified.
Bulk native datasets, GT, inference, evaluation, RRDs, images, logs and JUnit remain local/ignored;
curated receipts/tables/configs/code/docs and payload hashes are committed. No cleanup was performed.
