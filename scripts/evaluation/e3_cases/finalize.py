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
    top3 = {r["camera_id"] for r in snapshot["ranking"][:3]}
    gt = json.loads((root / annotation["gt_path"]).read_text())
    rows = gt["ticks"]
    target = lambda row: next(a for a in row["actors"] if a["id"] == "T")
    # A C challenge requires a later camera set that has NO member of the frozen
    # top 3, not merely an extra wide camera during an overlap still covered by top3.
    outside = next((r for r in rows if r["tick"] > snapshot["tick"] and target(r)["gt_visible"]
                    and not top3.intersection(target(r)["gt_visible"])), None)
    if outside is None:
        raise ValueError(f"{case_id}:NOT_OUTSIDE_TOP3")
    tick = outside["tick"]
    ranks = {r["camera_id"]: r["rank"] for r in snapshot["ranking"]}
    annotation["baseline"] = {"snapshot": snapshot, "snapshot_source_path": f"baseline/{case_id}.json",
        "snapshot_file_sha256": sha(baseline_path.read_bytes()), "actual_appearance_tick": tick,
        "actual_appearance_cameras": [{"camera_id": c, "rank": ranks.get(c),
            "rank_status": "RANKED" if c in ranks else "NOT_IN_CANDIDATES"} for c in target(outside)["gt_visible"]],
        "first_reappearance": {"tick": annotation["metrics"]["return_tick"],
                               "cameras": annotation["metrics"]["return_cameras"]},
        "limitation": "Later exclusive transfer can be outside top3 even if the first reappearance was inside top3. No F2 ranking used."}
    for point, index in zip(annotation["decision_points"][2:], [tick, tick + 5, tick + 15], strict=True):
        if index >= len(rows):
            raise ValueError("C_FOLLOWUP_MISSING")
        point.update(tick=index, timestamp_us=index * 200000,
                     cameras=target(rows[index])["gt_visible"], source_ref=f"ticks[{index}]")
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
    if not a.sample and (len(cases) < 8 or sum(c["family"] == "C" for c in cases) < 2):
        raise ValueError("CORPUS_REQUIREMENTS_NOT_MET")
    sources = {f: {"bytes": (a.assets / f).stat().st_size, "sha256": sha((a.assets / f).read_bytes())}
               for f in ["character.glb", "scene.glb", "cameras.three.json"]}
    sources.update({f: {"bytes": (ROOT / f).stat().st_size, "sha256": sha((ROOT / f).read_bytes())} for f in [
        "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json",
        "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json",
        "configs/q1q5/graphs/r004/camera_graph_v3.json"]})
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
         "points": "5 declared opportunities per clip, correlated phases within 9 authored scripts; not independent observations or model decisions.",
         "identity": "UNCONFIRMED", "physical_navigation": "UNKNOWN", "paid_api_calls": 0}}
    dump(root / ("CORPUS_SAMPLE.json" if a.sample else "CORPUS.json"), corpus)
    print(json.dumps({k: corpus[k] for k in ["status", "case_count", "decision_points", "duration_s", "indexed_frames"]}))


if __name__ == "__main__":
    main()
