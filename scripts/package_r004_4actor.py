"""Inventory completed safe RGB, indexes and RULE_ONLY tracks; never reads producer private files."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from render_r004_d124 import json_bytes, no_symlink_components, require, require_space, sha


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifacts-root", type=Path, required=True)
    p.add_argument("--safe-root", type=Path, required=True)
    p.add_argument("--repo", type=Path, required=True)
    a = p.parse_args()
    require(
        a.safe_root.resolve().is_relative_to(a.artifacts_root.resolve()), "BUNDLE_OUTSIDE_ARTIFACTS"
    )
    files = []
    for f in sorted(a.safe_root.rglob("*")):
        no_symlink_components(f)
        if f.is_file():
            files.append(
                {
                    "relative_path": f.relative_to(a.artifacts_root).as_posix(),
                    "size_bytes": f.stat().st_size,
                    "sha256": sha(f),
                }
            )
    prefix = a.safe_root.relative_to(a.artifacts_root).as_posix() + "/"
    names = {f["relative_path"] for f in files}
    runs = {}
    detection_inputs = []
    local_inputs = []
    ranking_inputs = []
    reconstruction_inputs = []
    receipts = []
    for label in ["A4-1", "B4-1"]:
        descriptor = json.loads((a.safe_root / f"runs/{label}.json").read_text())
        manifest = json.loads((a.safe_root / f"indexes/{label}/detection_index.json").read_text())
        receipt = json.loads((a.safe_root / f"indexes/{label}/receipt.json").read_text())
        records = a.safe_root / f"indexes/{label}/detection_index.records.jsonl"
        tracks = json.loads((a.safe_root / f"indexes/{label}/cx8_rule_only.json").read_text())
        require(manifest["run_id"] == descriptor["run_id"], "RUN_PIN")
        require(
            manifest["records_file_sha256"] == sha(records) == receipt["records_sha256"],
            "RECORDS_PIN",
        )
        require(
            manifest["provenance"]["gt_read"] is False and receipt["gt_read"] is False,
            "INDEX_BOUNDARY",
        )
        require(
            tracks["source_records_sha256"] == sha(records)
            and receipt["local_tracks_sha256"]
            == sha(a.safe_root / f"indexes/{label}/cx8_rule_only.json"),
            "TRACK_PIN",
        )
        require(receipt["conformance"]["status"] == "PASS", "INDEX_CONFORMANCE")
        count = descriptor["sample_count_per_camera"]
        rid = label + "-v2-4actor"
        runs[rid] = {
            "run_id_new": descriptor["run_id"],
            "detector": "RT-DETR",
            "detection_index_relative_path": prefix + f"indexes/{label}/detection_index.json",
            "cameras": {c: {"frame_count": count, "fps": 5} for c in descriptor["camera_ids"]},
        }
        detection_inputs += [prefix + f["relative_path"] for f in descriptor["frames"]] + [
            prefix + f"runs/{label}.json",
            prefix + descriptor["clock_ref"],
            prefix + f"config/{label}.json",
        ]
        local_inputs += [
            prefix + f"indexes/{label}/detection_index.json",
            prefix + f"indexes/{label}/detection_index.records.jsonl",
            prefix + f"config/{label}.json",
        ]
        ranking_inputs += [
            prefix + f"indexes/{label}/cx8_rule_only.json",
            prefix + descriptor["clock_ref"],
        ]
        reconstruction_inputs += [
            prefix + f"indexes/{label}/detection_index.records.jsonl",
            prefix + descriptor["clock_ref"],
        ]
        receipts.append(receipt)
    detection_inputs += [prefix + "SAFE_MANIFEST.json", prefix + "provenance/camera_catalog.json"]
    ranking_inputs += [prefix + "provenance/camera_graph_v3_1.json"]
    reconstruction_inputs += [prefix + "provenance/camera_catalog.json"]
    stage_inputs = {
        "detection_index": sorted(set(detection_inputs)),
        "local_track": sorted(set(local_inputs)),
        "ranking": sorted(set(ranking_inputs)),
        "reconstruction": sorted(set(reconstruction_inputs)),
    }
    require(
        all(rp in names for values in stage_inputs.values() for rp in values),
        "STAGE_INPUT_NOT_IN_BUNDLE",
    )
    require(len({r["weights_sha256"] for r in receipts}) == 1, "MODEL_PIN_MISMATCH")
    source = json.loads((a.safe_root / "SAFE_MANIFEST.json").read_text())
    m = {
        "schema": "amidst.r004-v2-bundle-manifest.v1",
        "local_root": "$AMIDST_ARTIFACTS",
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(f["size_bytes"] for f in files),
        "receipt": {
            "gt_read": False,
            "detector_weights_sha256": receipts[0]["weights_sha256"],
            "code_git_sha": subprocess.check_output(
                ["git", "-C", str(a.repo), "rev-parse", "HEAD"], text=True
            ).strip(),
            "source_blend_sha256": source["source_blend_sha256"],
            "camera_catalog_sha256": source["catalog_sha256"],
        },
        "runs": runs,
        "stage_inputs": stage_inputs,
        "stage_execution": {
            "detection_index": "COMPLETED",
            "local_track": "COMPLETED_CAMERA_LOCAL_SELECTED_SEED",
            "ranking": "NOT_RUN_INPUT_ALLOWLIST_ONLY",
            "reconstruction": "NOT_RUN_INPUT_ALLOWLIST_ONLY",
        },
        "stage_reads_note": "ranking/reconstruction were not executed; those stage_inputs are permitted bundle inputs, not a claim that files were read",
        "scope": "ENGINEERING_DEMO; identity UNCONFIRMED; physical navigation UNKNOWN; formal_eligible=false",
    }
    # Reuse the assigned validator without changing any acceptance logic.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gates516", a.repo / "tests/q1q5/test_r004_v2_516_gates.py"
    )
    gates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gates)
    require(not gates.validate_manifest(m), "BUNDLE_GATE_FAILED:" + str(gates.validate_manifest(m)))
    out = a.repo / "docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json"
    require_space(a.safe_root, len(json_bytes(m)) + 65536)
    out.write_bytes(json_bytes(m))
    with (a.safe_root.parent / "BUNDLE_MANIFEST.json").open("xb") as f:
        f.write(json_bytes(m))
    # Validate all materialized hashes a second time, independent of inventory creation.
    require(
        all(
            sha(a.artifacts_root / f["relative_path"]) == f["sha256"]
            and (a.artifacts_root / f["relative_path"]).stat().st_size == f["size_bytes"]
            for f in files
        ),
        "FINAL_BYTE_CHECK_FAILED",
    )
    print("BUNDLE_COMPLETE", m["file_count"], m["total_bytes"], sha(out), flush=True)


if __name__ == "__main__":
    main()
