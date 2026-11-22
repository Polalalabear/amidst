"""Publish the #652 extension after immutable GT freeze and shared-index production.

Reads the new GT freeze, safe input indexes and clean base runtime registry.
Never opens a base evaluation catalog, baseline/B log, Agent answer or group score.
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

GT_PIN_CONFIG = ROOT / "configs/evaluation/e3_reappearances_v1.json"
BASE_MANIFEST_SHA = "853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def check_safe_registry(value):
    forbidden = {"gt", "gt_visible", "gt_boxes", "actor_id", "actors", "expected", "waypoints",
                 "decision_points", "diagnostic_gaps", "baseline_snapshot"}
    if isinstance(value, dict):
        if forbidden.intersection(value):
            raise ValueError("PRIVATE_RUNTIME_INPUT")
        for child in value.values():
            check_safe_registry(child)
    elif isinstance(value, list):
        for child in value:
            check_safe_registry(child)


def release(root, base, assets):
    root = root.resolve(); base = base.resolve()
    if (root / "MANIFEST.json").exists():
        raise ValueError("REFUSE_FROZEN_RELEASE_OVERWRITE")
    freeze_path = root / "GT_FREEZE.json"
    if not GT_PIN_CONFIG.is_file() or sha(freeze_path) != sha(GT_PIN_CONFIG):
        raise ValueError("FROZEN_GT_DEFINITION_CHANGED")
    freeze = read(freeze_path)
    if freeze["status"] != "GT_AND_SCRIPT_FROZEN_BEFORE_DETECTION_AND_E3":
        raise ValueError("GT_FREEZE_REQUIRED")
    if sha(base / "MANIFEST.json") != BASE_MANIFEST_SHA:
        raise ValueError("BASE_CORPUS_MANIFEST_CHANGED")
    if len(freeze["cases"]) != 7 or {c["family"] for c in freeze["cases"]} != {"B", "C"}:
        raise ValueError("EXTENSION_CASE_SCOPE")
    cases = []; inputs = []; identities = set()
    for case in freeze["cases"]:
        case_id = case["case_id"]
        if sha(root / case["case_path"]) != case["case_sha256"] or sha(root / case["gt_path"]) != case["gt_sha256"]:
            raise ValueError("FROZEN_CASE_OR_GT_CHANGED")
        for point in case["decision_points"]:
            key = (case_id, point["gap_start_tick"], point["return_tick"])
            if key in identities or point["tick"] != point["return_tick"] or point["type"] != "REAPPEAR":
                raise ValueError("DUPLICATE_OR_NONRETURN_POINT")
            identities.add(key)
            if point["evaluation_window_us"] != [point["timestamp_us"], point["timestamp_us"] + 3_000_000]:
                raise ValueError("POINT_WINDOW_CHANGED")
        result = verify(root, case_id)
        index_path = f"indexes/{case_id}/detection_index.json"
        index = read(root / index_path)
        records_path = f"indexes/{case_id}/detection_index.records.jsonl"
        rgb_path = f"rgb/{case_id}/rgb_index.json"
        duration_us = len(read(root / case["case_path"])["inputs"]) * 50_000
        inp = {"run_id": index["run_id"], "clock_id": index["clock_id"],
               "scene_id": index["scene_id"], "scene_revision": index["scene_revision"],
               "duration_us": duration_us, "frame_interval_us": 200000, "image_size_px": [320, 180],
               "camera_ids": case["cameras"], "rgb_index_path": rgb_path, "rgb_index_sha256": sha(root / rgb_path),
               "index_path": index_path, "index_file_sha256": sha(root / index_path),
               "index_content_sha256": index["content_sha256"], "records_path": records_path,
               "records_file_sha256": sha(root / records_path)}
        inputs.append(inp)
        cases.append({**case, "duration_s": duration_us / 1_000_000, "verification": result,
                      "index_path": index_path, "index_file_sha256": inp["index_file_sha256"],
                      "rgb_index_path": rgb_path, "rgb_index_sha256": inp["rgb_index_sha256"]})
    count = len(identities)
    if count != freeze["new_reappearance_points"] or count + 3 < 30 or count + 38 < 40:
        raise ValueError("POINT_TARGET_NOT_MET")
    base_inputs_path = base / "RUNTIME_INPUTS.json"
    base_inputs = read(base_inputs_path); check_safe_registry(base_inputs)
    runtime = {"role": "SHARED_PIXEL_INPUTS_ONLY", "runs": inputs,
               "policy": "All F4 arms use these exact PNGs and frozen detection_index; never redetect per arm."}
    combined = {"role": "SHARED_PIXEL_INPUTS_ONLY", "roots": {
        "base": "local/evidence/e3-652-20261122", "extension": "local/evidence/e3-reappearances-20261122"},
        "runs": [{**r, "root_ref": "base"} for r in base_inputs["runs"]]
              + [{**r, "root_ref": "extension"} for r in inputs]}
    check_safe_registry(runtime); check_safe_registry(combined)
    if len({r["run_id"] for r in combined["runs"]}) != len(combined["runs"]):
        raise ValueError("DUPLICATE_INPUT_RUN")
    composition = {"base_manifest_path": "local/evidence/e3-652-20261122/MANIFEST.json",
        "base_manifest_sha256": BASE_MANIFEST_SHA, "base_runtime_registry_sha256": sha(base_inputs_path),
        "extension_root": "local/evidence/e3-reappearances-20261122", "gt_freeze_sha256": sha(freeze_path),
        "base_counts_source": freeze["base_counts_source"], "base_declared_h4_points": 3,
        "base_declared_primary_points": 38, "new_h4_reappearance_points": count,
        "new_primary_points": count, "combined_h4_reappearance_points": count + 3,
        "combined_primary_points": count + 38, "combined_clips": len(combined["runs"]),
        "base_group_outputs_read": False, "experiment_group_runs": 0}
    corpus = {"status": "FORMAL_RECORDED_FROZEN", "issue": 652, "cases": cases,
        "gt_freeze_sha256": sha(freeze_path), "case_count": len(cases), "decision_points": count,
        "h4_reappearance_points": count, "duration_s": round(sum(c["duration_s"] for c in cases), 3),
        "indexed_frames": sum(c["verification"]["frames"] for c in cases),
        "composition": composition, "boundary": freeze["boundary"],
        "source_assets": {f: {"bytes": (assets / f).stat().st_size, "sha256": sha(assets / f)}
                          for f in ["scene.glb", "character.glb", "cameras.three.json"]}}
    write(root / "CORPUS.json", corpus); write(root / "RUNTIME_INPUTS.json", runtime)
    write(root / "COMPOSITION.json", composition); write(root / "COMBINED_INPUTS.json", combined)
    write(root / "verification.json", [c["verification"] for c in cases])
    return corpus


def make_manifest(root):
    corpus = read(root / "CORPUS.json")
    files = {root / f for f in ["DESIGN.json", "GT_FREEZE.json", "DESIGN_V2.json", "GT_FREEZE_CANDIDATE_V1.json", "input-replay.json", "browser-replay.json",
             "CORPUS.json", "RUNTIME_INPUTS.json", "COMPOSITION.json", "COMBINED_INPUTS.json", "verification.json"]}
    for name in ["source_receipt.json", "environment.json", "focused-pytest.txt", "focused-node.txt"]:
        if (root / name).is_file():
            files.add(root / name)
    for c in corpus["cases"]:
        case_id = c["case_id"]; files.update(root.glob(f"{case_id}.*")); files.add(root / c["gt_path"])
        for rel in [f"rgb/{case_id}", f"pixels/{case_id}", f"indexes/{case_id}"]:
            files.update(p for p in (root / rel).rglob("*") if p.is_file())
        files.add(root / "predictions" / f"{case_id}.jsonl")
    entries = [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(files)]
    manifest = {"file_count": len(entries), "bytes": sum(e["bytes"] for e in entries), "files": entries,
        "regeneration": "docs/operations/E3_REAPPEARANCES_20261122.md; preserve frozen bytes for exact F4 reuse",
        "base_corpus_modified": False, "agent_or_rule_group_outputs_read": False}
    write(root / "MANIFEST.json", manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True); p.add_argument("--base-root", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    a = p.parse_args(); corpus = release(a.root, a.base_root, a.assets); manifest = make_manifest(a.root)
    print(json.dumps({"new_h4": corpus["h4_reappearance_points"], "combined_h4": corpus["composition"]["combined_h4_reappearance_points"],
        "combined_primary": corpus["composition"]["combined_primary_points"], "frames": corpus["indexed_frames"],
        "files": manifest["file_count"], "bytes": manifest["bytes"], "manifest_sha256": sha(a.root / "MANIFEST.json")}))


if __name__ == "__main__":
    main()
