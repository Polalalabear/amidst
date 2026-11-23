"""Run the pinned F1 LIVE adapter against two real #652 input/GT sidecars.

INDEX_BOX_FORMAT_PROBE is a mechanical adapter check, never an E3 arm or Agent
result. Its boxes come from the first retained person detection, independently
of GT. Position-only and all-IDLE paths are checked separately.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--root", type=Path, required=True)
p.add_argument("--scorer", type=Path, required=True)
p.add_argument("--scorer-sha256", required=True)
p.add_argument("--cases", nargs="+", required=True)
a = p.parse_args()
raw = a.scorer.read_bytes()
if hashlib.sha256(raw).hexdigest() != a.scorer_sha256:
    raise ValueError("F1_SOURCE_PIN_MISMATCH")
spec = importlib.util.spec_from_file_location("f1_frozen_scorer", a.scorer)
f1 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f1
spec.loader.exec_module(f1)
results = []
for case_id in a.cases:
    gt = json.loads((a.root / "gt-boxes" / f"{case_id}.a-log.json").read_text())
    records = [json.loads(x) for x in (a.root / "indexes" / case_id / "detection_index.records.jsonl").read_text().splitlines()]
    by_tick = {}
    for r in records:
        by_tick.setdefault(r["frame_index"], []).append(r)
    showing = []; idle = []; pos = []
    for tick, rows in sorted(by_tick.items()):
        source = next(((r["camera_id"], d) for r in rows for d in r["detections"] if d["class_label"] == "person"), None)
        idle.append({"tick": tick, "tracking": {"state": "IDLE"}})
        tr = ({"state": "TRACKING", "active_cam": source[0], "est_xy": [0, 0],
               "lost_ticks": 0, "box": source[1]["bbox_xyxy_px"]} if source else {"state": "IDLE"})
        showing.append({"tick": tick, "tracking": tr})
        pos.append({"tick": tick, "tracking": {k: v for k, v in tr.items() if k != "box"}})
    paths = {}
    for name, b in [("INDEX_BOX_FORMAT_PROBE", showing), ("IDLE_FORMAT_PROBE", idle), ("POSITION_FORMAT_PROBE", pos)]:
        ticks = f1.ticks_from_live(gt["ticks"], b, "T", tick_us=200000)
        # Adapter Tick leaves image size unset. These LIVE captures are
        # 320x180, so pass that explicit size to the shared scorer.
        ticks = [replace(t, size=(320, 180)) for t in ticks]
        if len(ticks) != len(by_tick) or any(t.t_us != i * 200000 for i, t in enumerate(ticks)):
            raise ValueError("F1_TICK_ALIGNMENT")
        result = f1.score_event(ticks, tick_us=200000)
        if result["schema_version"] != "e3.score.v1":
            raise ValueError("F1_OUTPUT_SCHEMA")
        # The class API must accept both box criteria on the actual sidecar.
        for t in ticks:
            f1.classify(t, "primary"); f1.classify(t, "iou")
        paths[name] = {"ticks": len(ticks), "status": "PASS", "performance_result": False}
    results.append({"case_id": case_id, "paths": paths})
output = {"role": "FORMAT_COMPATIBILITY_ONLY_NOT_E3_RESULTS", "f1_pr": 662,
          "f1_commit": "ea31b64396b555a49cc6b9b06ff11f0536c2aa06", "f1_source_sha256": a.scorer_sha256,
          "tick_us_explicit": 200000, "image_size_px_explicit": [320, 180], "results": results}
(a.root / "f1-format-probe.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps(output, indent=2))
