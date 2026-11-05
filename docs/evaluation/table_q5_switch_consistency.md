# Table 3: Q5 Camera Switch Decision-Window Consistency

Provenance: `DATA ORIGIN: SYNTHETIC (SIMULATION FIXTURE - NOT SAFE PACK EVIDENCE)`

- Q5 decision-window consistency across KEEP, HANDOFF, LOST, and ABSTAIN categories.
- Windows with UNKNOWN observed outcome are counted in n_unknown and excluded from agreement denominator.

| decision_category | data_status | n_windows_total | n_windows_evaluated | n_agreed | n_disagreed | n_unknown | agreement_rate_pct | median_window_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KEEP | SYNTHETIC | 21 | 20 | 18 | 2 | 1 | 90.00 | 205.00 |
| HANDOFF | SYNTHETIC | 18 | 17 | 14 | 3 | 1 | 82.35 | 615.00 |
| LOST | SYNTHETIC | 14 | 12 | 10 | 2 | 2 | 83.33 | 445.00 |
| ABSTAIN | SYNTHETIC | 10 | 9 | 8 | 1 | 1 | 88.89 | 260.00 |
| ALL | SYNTHETIC | 63 | 58 | 50 | 8 | 5 | 86.21 | 260.00 |
