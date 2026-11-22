"""Evaluation-only #652 corpus freeze; joins separately frozen B1 snapshots to GT.

Does not execute inference or mutate pixels/indexes. Raw inputs and GT remain LOCAL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from verify import verify


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def bind_c(root, annotation):
    case_id = annotation["case_id"]
    baseline_path = root / "baseline" / f"{case_id}.json"
    baseline = json.loads(baseline_path.read_text())
    snapshot = baseline[annotation["metrics"]["baseline_tick"]]
    if snapshot["status"] != "READY" or len(snapshot["ranking"]) < 3:
        raise ValueError(f"{case_id}:BASELINE_UNKNOWN")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if sha(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()) != snapshot["snapshot_sha256"]:
        raise ValueError("B1_SNAPSHOT_PIN_MISMATCH")
    index = json.loads((root / "indexes" / case_id / "detection_index.json").read_text())
    if snapshot["index_sha256"] != index["content_sha256"]:
        raise ValueError("B1_INDEX_SOURCE_MISMATCH")
    if snapshot["source"]["fallback_source_sha256"] != sha((ROOT / "scripts/evaluation/e3_cases/baseline.py").read_bytes()):
        raise ValueError("B1_FALLBACK_SOURCE_MISMATCH")
    top3 = {r["camera_id"] for r in snapshot["ranking"][:3]}
    gt = json.loads((root / annotation["gt_path"]).read_text())
    rows = gt["ticks"]
    target = lambda row: next(a for a in row["actors"] if a["id"] == "T")
    # A C challenge requires a later camera set that has NO member of the frozen
    # top 3, not merely an extra wide camera during an overlap still covered by top3.
    # Primary point is fixed from script/GT reappearance, independent of B1 outputs.
    outside = rows[annotation["metrics"]["return_tick"]]
    if not target(outside)["gt_visible"] or top3.intersection(target(outside)["gt_visible"]):
        raise ValueError(f"{case_id}:FIRST_RETURN_NOT_OUTSIDE_TOP3")
    tick = outside["tick"]
    ranks = {r["camera_id"]: r["rank"] for r in snapshot["ranking"]}
    annotation["baseline"] = {"snapshot": snapshot, "snapshot_source_path": f"baseline/{case_id}.json",
        "snapshot_file_sha256": sha(baseline_path.read_bytes()), "actual_appearance_tick": tick,
        "actual_appearance_cameras": [{"camera_id": c, "rank": ranks.get(c),
            "rank_status": "RANKED" if c in ranks else "NOT_IN_CANDIDATES"} for c in target(outside)["gt_visible"]],
        "first_reappearance": {"tick": annotation["metrics"]["return_tick"],
                               "cameras": annotation["metrics"]["return_cameras"]},
        "first_reappearance_outside_top3": not top3.intersection(annotation["metrics"]["return_cameras"]),
        "limitation": "Actual B1 state is preserved, including any existing lost ticks or wrong association; no oracle reseed. Camera hop ranking does not certify physical reachability. No F2 ranking used."}
    return snapshot


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--main-sha", required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--sample", action="store_true")
    a = p.parse_args(); root = a.root.resolve()
    annotations = json.loads((root / ("annotations-sample.json" if a.sample else "annotations.json")).read_text())
    cases = []
    for annotation in annotations:
        case_id = annotation["case_id"]
        snapshot = bind_c(root, annotation) if annotation["family"] == "C" else None
        case_path = root / f"{case_id}.case.json"
        case = json.loads(case_path.read_text())
        case["status"] = "FORMAL_RECORDED_FROZEN"
        if snapshot:
            case["baseline_snapshot"] = snapshot
        dump(case_path, case)
        result = verify(root, case_id)
        index_rel = f"indexes/{case_id}/detection_index.json"
        rgb_rel = f"rgb/{case_id}/rgb_index.json"
        cases.append({**annotation, "status": "FORMAL_RECORDED_FROZEN", "verification": result,
          "case_path": f"{case_id}.case.json", "case_sha256": result["case_sha256"],
          "index_path": index_rel, "index_sha256": sha((root / index_rel).read_bytes()),
          "rgb_index_path": rgb_rel, "rgb_index_sha256": sha((root / rgb_rel).read_bytes()),
          "gt_sha256": sha((root / annotation["gt_path"]).read_bytes())})
    if not a.sample and (len(cases) < 8 or {c["family"] for c in cases} != {"A", "B", "C", "D"} or sum(c["family"] == "C" for c in cases) < 2):
        raise ValueError("CORPUS_REQUIREMENTS_NOT_MET")
    sources = {f: {"bytes": (a.assets / f).stat().st_size, "sha256": sha((a.assets / f).read_bytes())}
               for f in ["character.glb", "scene.glb", "cameras.three.json"]}
    sources.update({f: {"bytes": (ROOT / f).stat().st_size, "sha256": sha((ROOT / f).read_bytes())} for f in [
        "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json",
        "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json",
        "configs/q1q5/graphs/r004/camera_graph_v3.json", "frontend/live-mode/src/person.mjs"]})
    corpus = {"status": "TWO_CASE_FORMAT_HANDOFF" if a.sample else "FORMAL_RECORDED_FROZEN",
       "issue": 652, "baseline_main_sha": a.main_sha, "cases": cases, "source_files": sources,
       "case_count": len(cases), "decision_points": sum(len(c["decision_points"]) for c in cases),
       "duration_s": round(sum(c["duration_s"] for c in cases), 3),
       "indexed_frames": sum(c["verification"]["frames"] for c in cases),
       "boundary": {"case_and_gt": "A_PRIVATE_RENDER_OR_OFFLINE_EVALUATION_ONLY",
         "inference_allowlist": "Only rgb PNGs, RGB descriptor and detection_index manifest/records. Neither cases, GT nor this evaluation catalog.",
         "shared_input_policy": "Every F4 arm uses the same PNG bytes and detection_index; never redetect per arm.",
         "last_capture": "Endpoint guard at case duration; excluded from half-open [0,duration) detection grid.",
         "replay": "Chrome expected states and logical captures match 3 complete runs; wall clocks/JPEGs/detector outputs not asserted deterministic.",
         "sampling": "5 Hz, 320x180, 8 cameras; original N6 GLBs, no Blender render or asset modification.",
         "visibility": "Existing static-wall body-point-ray proxy; not pixel masks or person-person occlusion truth.",
         "gt_boxes": "Existing person.mjs projectBox: 0.5x0.5x1.75 m standing-body proxy; not measured pixel silhouettes.",
         "points": "38 primary decision points in 9 authored scripts; B points are reappearances. Correlated phases remain clustered by script. Blind/exit diagnostic events are separate, not extra independent trials.",
         "identity": "UNCONFIRMED", "physical_navigation": "UNKNOWN", "paid_api_calls": 0}}
    # Separate runtime registry: no private case, GT, event labels or baseline answers.
    inputs = []
    for case in cases:
        index = json.loads((root / case["index_path"]).read_text())
        records_path = str(Path(case["index_path"]).parent / index["records_ref"])
        inputs.append({"run_id": index["run_id"], "clock_id": index["clock_id"],
            "scene_id": index["scene_id"], "scene_revision": index["scene_revision"],
            "duration_us": round(case["duration_s"] * 1_000_000), "frame_interval_us": 200000,
            "image_size_px": [320, 180], "camera_ids": case["cameras"],
            "rgb_index_path": case["rgb_index_path"], "rgb_index_sha256": case["rgb_index_sha256"],
            "index_path": case["index_path"], "index_file_sha256": case["index_sha256"],
            "index_content_sha256": index["content_sha256"],
            "records_path": records_path, "records_file_sha256": index["records_file_sha256"]})
    dump(root / ("RUNTIME_INPUTS_SAMPLE.json" if a.sample else "RUNTIME_INPUTS.json"),
         {"role": "SHARED_PIXEL_INPUTS_ONLY", "runs": inputs,
          "policy": "Both arms use these exact PNGs and detection indexes; no per-arm redetection."})
    dump(root / ("CORPUS_SAMPLE.json" if a.sample else "CORPUS.json"), corpus)
    print(json.dumps({k: corpus[k] for k in ["status", "case_count", "decision_points", "duration_s", "indexed_frames"]}))


if __name__ == "__main__":
    main()
