# Q1–Q5 conformance kit fixtures — all SYNTHETIC

Every file under `SYNTHETIC/` is invented. Ids, hashes, camera names, timings and parameter values carry **no demo
storyline, no Ground Truth, no production route and no proposed threshold**. They exist only to show what a
contract-conformant document looks like and which invariant each violation breaks.

- `SYNTHETIC/valid/` — one coherent set; the kit must report `PASS` with no skipped check.
- `SYNTHETIC/violations.json` — patch cases applied to the valid set (`ops`, run before or after hash
  recomputation per `stage`); `expect_fail` is the exact set of checks that must fail.
- `build_fixtures.py` — regenerates both; `tests/unit/test_q1q5_conformance.py` fails if they drift.

Do not edit these files by hand and do not copy values from them into a real parameter set.
