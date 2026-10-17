# Codex confirmation of K0 v1.1 — 2026-10-17

Reviewed the three complete contract files from PR #45 at `be646caaebf4f62f6dd65e3f9f2774c6caa514eb`, plus K1/K5 current implementations. This confirms the engineering interpretation below, not checkpoint/merge or research approval. No Claude-owned contract or K1/K5 file was edited.

| Clause / question | Confirmation |
| --- | --- |
| IO §3, §4.1–4.4 | Accept FOOT_RAY_PIXEL_BAND for exactly LOW_INCIDENCE; same v2 component contact pixel, two full floor intersections v±k, far-end radius allowance, no head fallback, same source/walkable clips and 8-neighbour sensitivity. PASS/CONTACT_OCCLUDED/D8 remain separate. |
| IO-Q9 | Accept k=2 for each declared run, fixed before execution; head prior/tolerance may be absent or UNKNOWN for this basis. Missing/invalid k or radius gives FOOT_BAND_UNAVAILABLE. No GT tuning. |
| IO-Q10 | No signed residual export in v1.1. Do not change CONTACT_OCCLUDED classification. |
| IO-Q11 | No VISIBLE_BOTTOM_FAR_BOUND clip in v1.1; leave as a recorded future idea. |
| IO-Q12 | Keep office-demo.interval-observation.v1; consumers reject unsupported basis/enums. New producer stops the transitional head-ray fallback once implemented. Historical frozen files are not rewritten. |
| D17 transition | New producer requires FOOT_RAY_PIXEL_BAND for LOW_INCIDENCE-only. OCCLUDER_BEHIND must be NOT_APPLICABLE with null ref/hash and unchanged length; supplied masks never act, including sensitivity. |
| R2 diagnostics | Accept exact C4a raw_coordinates_use / usable_as_position / usable_as_endpoint names. UNKNOWN raw coordinates are diagnostic only; K1 takes only READY endpoints. |
| BH-Q10 | Backend keeps the sealed previous response in the same scene/session; K5 verifies it. Baseline and retrieval entries use the same canonical entry hash. No client response/GT/geometry overrides. |
| BH-Q11 | Accept per-entry mean region area over its own clock steps; previous pruning_log copied, pruned_hypotheses only this step, rank null. |
| BH-Q12(a) | Accept label-only policy: keep physical walkable result and all search/ranking/regions unchanged; add RESTRICTED_POLICY, area_refs, restricted_area_crossed. |
| BH-Q12(b–d) | Accept restricted_policy_sample_indices; C7 emits separate restricted_regions per variant, original annotation ref/file+record hashes and confirmation_ref bound to CP2 D15. Do not put policy geometry into unknown_regions or subtract it. User confirmed K1 changes remain Claude-owned; C7 supplies a small map fixture for that work. |
| D16 | Individually resolved seats/lecterns remain physical obstacles; no blanket UNKNOWN seating override. |
| FR-Q6 / FR-Q8 | C5 returns frame_evaluations keyed by real frame_ref, four exact boolean flags and measurement_count including rejected components; resolved visibility_entries and frame_outcomes are in the retrieval response. K5 pure converter can consume these as explicit arguments. |
| IO-Q7 / hashes | Use existing registry/K1 canonical bytes: Python json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8"). No rounding, Unicode normalization or type coercion; 1 and 1.0 remain distinct. output_sha256 excludes itself; entry sha256 excludes itself. Retrieval latency_ms excluded only from retrieval output hash, explicitly verified. |
| D18 / D12 | Person FRONT4.6→REAR8.2, interior4.8–8.0, no D7. Legacy4.4→8.6 unchanged. Keep [0,2]m/s config; check actual derived-map hypotheses without claiming whole-building connectivity. New foot band can reduce number of representatives; never tune to recover K=3. |
| C5 visibility | Source-static-mesh raycast, calibrated FOV/clip first, foot/torso/head union at offsets .002/.852/1.702m, per-run binding. Sampling resolution and UNKNOWN domain stay explicit. C6 planning rays and renderer target visibility/depth are not inference evidence. |

Corrections for Claude's next contract edit:

1. IO §2.1's blanket HEIGHT_PRIOR_UNAVAILABLE wording needs the explicit FOOT_RAY_PIXEL_BAND exception already defined in §4.2a.
2. The transition text naming frozen `46dd4df` as conformant is historical shorthand: that artifact recorded occlusion NOT_AVAILABLE and withheld 29 endpoints. The conformant D17 NOT_APPLICABLE freeze is `099513e`. Keep both historical receipts; point new wording at the latter.
3. Remove the producer transition paragraph when the v1.1 implementation is accepted; retain a historical note rather than retroactively changing frozen outputs.

K1/K5 source remains unchanged as explicitly selected by the user. New restricted-policy engine labels depend on Claude's implementation; this task does not manufacture them through UNKNOWN regions.
