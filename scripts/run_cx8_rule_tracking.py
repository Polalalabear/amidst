"""CX-8 RULE_ONLY tracking adapter for complex events (A4-1 / B4-1).

Reads only a detection-index records file produced by build_q1q5_detection_index.py
(frame_ref, camera_id, timestamp_us, frame_state, detections[score]). It never reads
scenario scripts, Ground Truth, renderer data, or any private input. Output is a
RULE_ONLY receipt: per-camera presence segments and handoff (switch) candidates.
Identity stays UNCONFIRMED; nothing here is a physical navigation claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

MIN_FREE_BYTES = 8 * 1024 ** 3  # D118
SCHEMA = "cx8-rule-tracking.v1"


def require_free_space(path, minimum=MIN_FREE_BYTES):
    free = shutil.disk_usage(path).free
    if free < minimum:
        raise SystemExit(f"Insufficient disk space (D118): {free} bytes free, need {minimum}")
    return free


def load_records(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_receipt(rows, *, run_id, score_floor, max_gap_us, records_sha256):
    """Presence = a SAMPLED frame with a detection scoring >= score_floor.

    Consecutive present frames of one camera merge into a segment when the gap is
    <= max_gap_us. A switch candidate links the end of one segment to the next
    segment that starts later on a different camera. Unsampled frames are ignored
    (UNKNOWN), never treated as absence evidence.
    """
    present = {}
    for r in rows:
        dets = r.get("detections") or []
        if r.get("frame_state") == "NOT_SAMPLED" or not any(d["score"] >= score_floor for d in dets):
            continue
        present.setdefault(r["camera_id"], []).append((r["timestamp_us"], r["frame_ref"]))
    segments = []
    for camera in sorted(present):
        for ts, ref in sorted(present[camera]):
            last = segments[-1] if segments and segments[-1]["camera_id"] == camera else None
            if last and ts - last["end_us"] <= max_gap_us:
                last["end_us"], last["end_frame_ref"] = ts, ref
            else:
                segments.append({"camera_id": camera, "start_us": ts, "end_us": ts,
                                 "start_frame_ref": ref, "end_frame_ref": ref})
    segments.sort(key=lambda s: (s["start_us"], s["camera_id"]))
    for i, s in enumerate(segments):
        s["segment_id"] = f"seg:{run_id}:{i}"
    switches = []
    for a in segments:
        later = [b for b in segments if b["camera_id"] != a["camera_id"] and b["start_us"] > a["end_us"]]
        if later:
            b = min(later, key=lambda s: (s["start_us"], s["camera_id"]))
            switches.append({"from_segment": a["segment_id"], "to_segment": b["segment_id"],
                             "from_camera": a["camera_id"], "to_camera": b["camera_id"],
                             "decision_us": a["end_us"], "gap_us": b["start_us"] - a["end_us"],
                             "evidence_frame_refs": [a["end_frame_ref"], b["start_frame_ref"]]})
    return {"schema": SCHEMA, "mode": "RULE_ONLY", "status": "AVAILABLE", "run_id": run_id,
            "identity": "UNCONFIRMED", "source_records_sha256": records_sha256,
            "parameters": {"score_floor": score_floor, "max_gap_us": max_gap_us},
            "segments": segments, "switches": switches}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "records", "run-id", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--score-floor", type=float, required=True)
    parser.add_argument("--max-gap-us", type=int, required=True)
    args = parser.parse_args(argv)
    repo, output = Path(args.repo).resolve(), Path(args.output).absolute()
    allowed = (Path.home() / "amidst-artifacts").resolve()
    if output.resolve() != output or not output.is_relative_to(allowed) or output.is_relative_to(repo):
        parser.error("Output must be canonical and under ~/amidst-artifacts, outside repo")
    if output.exists():
        parser.error("Output exists; refusing to overwrite")
    require_free_space(repo)
    records = Path(args.records)
    digest = hashlib.sha256(records.read_bytes()).hexdigest()
    receipt = build_receipt(load_records(records), run_id=args.run_id, score_floor=args.score_floor,
                            max_gap_us=args.max_gap_us, records_sha256=digest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
    print(json.dumps({"segments": len(receipt["segments"]), "switches": len(receipt["switches"]),
                      "source_records_sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
