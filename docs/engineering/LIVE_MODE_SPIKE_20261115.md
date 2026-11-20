> 2026-11-19 註（D338，#631）：**已被取代**。最終報告是 [`docs/evaluation/LIVE_MODE_SPIKE_20261115.md`](../evaluation/LIVE_MODE_SPIKE_20261115.md)（該文第 3 行寫明取代本草稿）；本文只保留作歷史。是否移到封存：歸檔候選，需使用者決定。現行 LIVE 規格見 [`docs/specs/LIVE_MODE_AB_V1.md`](../specs/LIVE_MODE_AB_V1.md) 與 [Q1Q5_PRODUCT_SPEC §4.4](../specs/Q1Q5_PRODUCT_SPEC.md)。

# Live mode spike (WIP, 2026-11-15) — INCOMPLETE

Status: prototype + detection-rate sweeps done; latency matrix, CPU comparison, screenshots and the final feasibility write-up are NOT done (usage limit reached). Latency runs were started in a session scratchpad (a temporary folder, cannot be rebuilt as such); their results are kept as LOCAL `local/evidence/live-mode-spike-20261115/lat/*.latency.json` (SHA-256 in `docs/evaluation/live_mode_spike_20261115/SHA256SUMS_local.txt`).

## Detection rate (RT-DETR R18, MPS, person alone, 1 m grid x 4 headings, 8 cameras, live display threshold 0.35)
Eligible = ray-visible, >=60% of box in frame, height >=16 px; detected = IoU>=0.3.
| Person model | 320x180 | 480x270 | 640x360 |
|---|---|---|---|
| capsule (436 tris) | 16.7% | 15.8% | 17.4% |
| N6 WIP character.glb (~4.0k tris, from /private/tmp, unreviewed) | 60.6% | 54.9% | 50.7% |

- Capsule people are not reliable targets for RT-DETR (score mostly 0.1–0.35). Colour label is right whenever detected.
- glTF character: ~60% at best; weak at close range (<4 m, steep downward view, large boxes: 12% at 320x180) and in CAM_R101_IN / CAM_BRANCH. Higher render resolution did not help (model input is 640x640 stretch).
- Per-threshold rates, per camera/distance/heading: `docs/engineering/live_mode_spike_data/*.summary.json`.
- Conclusion so far: real detection is NOT yet sufficient for live tracking; keep a "simulated detection" fallback until N6 realism/pose coverage improves. Not a final judgement.

## Pipeline timing seen so far (not a measurement run)
RT-DETR batch of 8 at MPS: ~0.84 s (≈105 ms/image) under load average 30 (Codex Blender render running); CPU 4 threads ≈ 0.4–0.7 s/image. That is ~1 fps for 8 cameras, far below 5 fps.

## Reproduce
Server: `PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8791 --device mps --models <rtdetr dir>` (optional `AMIDST_LIVE_CHARACTER_GLB`). Front end: `cd frontend/live-mode && npm install`; windows `/?role=operator`, `/?role=system`. Sweeps: `measure/run_sweeps.sh`; latency: `measure/run_latency.sh`. Tests: `npm test` (operator-leak guard), `pytest tests/live_mode`.
