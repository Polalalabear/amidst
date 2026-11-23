"""Focused E3 artifact verification with the production JsonRunStore reader."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.store import DocumentPin, JsonRunStore


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root, case_id):
    root = root.resolve()
    case = json.loads((root / f"{case_id}.case.json").read_text())
    if case["schema_version"] != "live-ab.case.v1" or case["case_id"] != case_id:
        raise ValueError("CASE_SCHEMA")
    count = len(case["inputs"]) // 4
    if len(case["inputs"]) % 4 or len(case["expected"]) != len(case["inputs"]) + 1:
        raise ValueError("CASE_INPUT_GRID")
    logical = []
    for replay in (1, 2, 3):
        log = json.loads((root / f"{case_id}.replay{replay}.a-log.json").read_text())
        if len(log["ticks"]) != count + 1 or log.get("errors") or log.get("crowd_error") or log["dropped"]:
            raise ValueError("INCOMPLETE_BROWSER_REPLAY")
        signature = []
        for i, row in enumerate(log["ticks"]):
            if row["tick"] != i or row["t_infer_capture_ms"] != i * 200:
                raise ValueError("BROWSER_CAPTURE_GRID")
            expected = {a["actor_id"]: a for a in case["expected"][i * 4]["actors"]}
            for a in row["actors"]:
                p = expected[a["id"]]
                if a["present"] != p["present"] or a["xy"] != ([p["x"], p["y"]] if p["present"] else None):
                    raise ValueError("CASE_BROWSER_GT_MISMATCH")
            signature.append({k: row[k] for k in ("tick", "t_sim", "t_infer_capture_ms", "actors",
                              "pause_total_i", "pause_player_i", "pause_script_i", "active_passes", "forced_pairs")})
        logical.append(signature)
    if logical[0] != logical[1] or logical[0] != logical[2]:
        raise ValueError("BROWSER_REPLAY_DIVERGED")
    manifest_path = f"indexes/{case_id}/detection_index.json"
    records_path = f"indexes/{case_id}/detection_index.records.jsonl"
    raw = (root / manifest_path).read_bytes(); manifest = json.loads(raw)
    store = JsonRunStore(root, {
        "index": DocumentPin(manifest_path, sha(raw), "q-demo.detection-index.v1", manifest["content_sha256"]),
        "records": DocumentPin(records_path, manifest["records_file_sha256"], "q-demo.detection-record.v1"),
    })
    snapshot = store.load_detection_index("index")
    rgb = json.loads((root / "rgb" / case_id / "rgb_index.json").read_text())
    if sha((root / "rgb" / case_id / "rgb_index.json").read_bytes()) != manifest["rgb_index_sha256"]:
        raise ValueError("RGB_INDEX_PIN")
    pixels = {(r["camera_id"], r["frame_index"]): r for r in rgb["records"]}
    cameras = case["config"]["cams"]
    if len(cameras) != 8 or len(snapshot.records) != count * 8 or set(pixels) != {(c, i) for c in cameras for i in range(count)}:
        raise ValueError("INDEX_GRID_INCOMPLETE")
    observations = 0
    for row in snapshot.records:
        pin = pixels[row["camera_id"], row["frame_index"]]
        if row["frame_state"] != "INFERRED" or row["timestamp_us"] != row["frame_index"] * 200000:
            raise ValueError("INDEX_UNINFERRED_OR_CLOCK")
        if sha((root / pin["relative_path"]).read_bytes()) != row["rgb_file_sha256"]:
            raise ValueError("INDEX_PIXEL_HASH")
        observations += len(row["detections"])
    # Private GT must be a separate file, never mixed into source RGB/index metadata.
    gt_path = root / "gt-boxes" / f"{case_id}.a-log.json"
    if not gt_path.is_file():
        gt_path = root / "gt" / f"{case_id}.a-log.json"
    gt = json.loads(gt_path.read_text())
    if gt["provenance"]["role"] != "EVALUATION_ONLY" or gt["ticks"][-1]["tick"] != count:
        raise ValueError("GT_SIDECAR_GRID")
    if len(gt["ticks"]) != count + 1:
        raise ValueError("GT_CAPTURE_COUNT")
    for row, actual in zip(gt["ticks"], logical[0], strict=True):
        if row["tick"] != actual["tick"]:
            raise ValueError("GT_TICK_ALIGNMENT")
        originals = {x["id"]: x for x in actual["actors"]}
        for actor in row["actors"]:
            source = originals[actor["id"]]
            if any(actor[k] != source[k] for k in ("present", "xy", "gt_visible")):
                raise ValueError("GT_SOURCE_MISMATCH")
            if actor["id"] == "T" and "gt_boxes" in actor:
                import math
                for cam in actor["gt_visible"]:
                    box = actor["gt_boxes"].get(cam)
                    if not box or len(box) != 4 or not all(math.isfinite(v) for v in box) or box[2] <= box[0] or box[3] <= box[1]:
                        raise ValueError("GT_TARGET_BOX_MISSING")
    wire = json.loads((root / f"{case_id}.replay1.wire.json").read_text())
    for h in wire:
        if set(h) != {"tick", "t_capture_ms", "frames", "available_cameras"}:
            raise ValueError("PRIVATE_INFERENCE_HEADER")
    return {"case_id": case_id, "status": "PASS", "frames": count * 8,
            "observations": observations, "case_sha256": sha((root / f"{case_id}.case.json").read_bytes()),
            "index_sha256": sha(raw), "gt_sha256": sha(gt_path.read_bytes()),
            "reader": "JsonRunStore.load_detection_index", "replays_checked": 3}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--cases", nargs="+", required=True)
    args = p.parse_args()
    results = [verify(args.root, case_id) for case_id in args.cases]
    target = args.root / ("verification-sample.json" if len(results) == 2 else "verification.json")
    target.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
