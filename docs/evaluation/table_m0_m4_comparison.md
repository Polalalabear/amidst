# Table 1: Baseline (RULE_ONLY) vs M1-M4 Event Comparison

Provenance: `DATA ORIGIN: PENDING_REAL_DATA - UNMEASURED ITEMS MARKED PENDING_REAL_DATA / UNKNOWN`

- Compares Baseline (RULE_ONLY) against M1..M4 model combinations across event metrics.
- Missing or unmeasured arms are reported as PENDING_REAL_DATA / UNKNOWN and never imputed.

| arm_id | model_combination | data_status | n_events_total | n_events_scored | n_events_abstained | action_match_rate_pct | switch_latency_median_ms | switch_latency_p90_ms | false_handoff_rate_pct | abstention_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RULE_ONLY | Baseline rule-only controller (M0) | PENDING_REAL_DATA | 20 | 17 | 3 | 70.59 | 522.50 | 790.00 | 16.67 | 15.00 |
| M1 | Sequential agent with rule fallback (M1) | PENDING_REAL_DATA | 20 | 17 | 3 | 82.35 | 580.00 | 890.00 | 33.33 | 15.00 |
| M2 | Scorer v2 guarded complex-scene evaluation (M2) | PENDING_REAL_DATA | 20 | 16 | 4 | 87.50 | 535.00 | 690.00 | 16.67 | 20.00 |
| M3 | LLM Q3 query parser with rule fallback (M3) | PENDING_REAL_DATA | 20 | 18 | 2 | 83.33 | 560.00 | 850.00 | 33.33 | 10.00 |
| M4 | Candidate LLM model sweep best-balanced arm (M4) | PENDING_REAL_DATA | 20 | 18 | 2 | 88.89 | 547.50 | 760.00 | 16.67 | 10.00 |
