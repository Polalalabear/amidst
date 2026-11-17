"""Evaluation-only D261 attribution: run after redetect_route and gate4_off scoring."""

import argparse
import hashlib
import json
from pathlib import Path

from detection_score import score_recording


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    # These files are opened only by this separate evaluation step, never by inference.
    grid = score_recording(
        read(a.original / "recording/evaluation_labels.json"),
        read(a.original / "diagnosis/deployed.detections.json"),
    )
    quality = {}
    for profile in ["entry005", "entry015"]:
        runs = read(a.work / "paired_replay/gate4_off" / profile / "t1_summary.json")["runs"]
        quality[profile] = {
            r["label"].split("_")[0]: {
                k: r["evaluation_only"][k]
                for k in ["target_visible_ticks", "on_target", "wrong_person", "lost"]
            }
            for r in runs
        }
    loose, strict = quality["entry005"]["a4"], quality["entry015"]["a4"]
    rule = {
        "max_wrong_delta": 0.02,
        "min_correct_delta": -0.02,
        "wrong_delta": loose["wrong_person"] - strict["wrong_person"],
        "correct_delta": loose["on_target"] - strict["on_target"],
    }
    rule["retain_entry005"] = rule["wrong_delta"] <= 0.02 and rule["correct_delta"] >= -0.02
    matched = {}
    for p in sorted((a.original / "routes/redetected").glob("*.t1raw.json")):
        old = read(p)
        new = read(a.work / "entry015" / p.name)
        assert old["redetection"]["camera_min_scores"] == {"CAM_ENTRY": 0.05}
        assert new["redetection"]["camera_min_scores"] == {"CAM_ENTRY": 0.15}
        assert len(old["infer"]) == len(new["infer"])
        mismatch = 0
        for x, y in zip(old["infer"], new["infer"]):
            assert x["tick"] == y["tick"]
            for cam, ds in x["dets"].items():
                expected = [d for d in ds if d["score"] >= 0.15] if cam == "CAM_ENTRY" else ds
                mismatch += expected != y["dets"][cam]
        matched[p.name] = {"ticks": len(old["infer"]), "mismatched_camera_batches": mismatch}
    assert not any(r["mismatched_camera_batches"] for r in matched.values()), (
        "COUNTERFACTUAL_NOT_ISOLATED"
    )
    inputs = []
    paths = (
        list((a.original / "routes/packets").rglob("*.bin"))
        + list((a.original / "routes/raw").glob("*.t1raw.json"))
        + list((a.original / "routes/redetected").glob("*.t1raw.json"))
    )
    paths += [
        a.original / "recording/MANIFEST.json",
        a.original / "recording/evaluation_labels.json",
        a.original / "diagnosis/deployed.detections.json",
    ]
    for p in sorted(paths):
        inputs.append(
            {
                "path": p.relative_to(a.original).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": sha(p),
            }
        )
    inventory = a.work / "input_inventory.json"
    inventory.write_text(
        json.dumps({"original_root": "local/evidence/cx552-20261117", "files": inputs}, indent=2)
        + "\n"
    )
    files = []
    for p in sorted(a.work.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            files.append(
                {
                    "path": p.relative_to(a.work).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": sha(p),
                }
            )
    manifest = a.work / "MANIFEST.json"
    manifest.write_text(
        json.dumps({"path_base": "$AMIDST_ARTIFACTS/cx552-d261-20261117", "files": files}, indent=2)
        + "\n"
    )
    result = {
        "decision_reference": "https://github.com/Polalalabear/amidst/issues/552#issuecomment-6940301551",
        "fixed_rgb": True,
        "new_capture": False,
        "paid_calls": 0,
        "gt_in_detector": False,
        "quality": quality,
        "a4_rule": rule,
        "counterfactual_exact_match": matched,
        "entry_grid": {
            t: grid["thresholds"][t]["by_camera"]["CAM_ENTRY"] for t in ["0.05", "0.15"]
        },
        "default_camera_min_scores": {"CAM_ENTRY": 0.05} if rule["retain_entry005"] else {},
        "source_inventory_sha256": sha(inventory),
        "artifacts": {
            "path": "$AMIDST_ARTIFACTS/cx552-d261-20261117/MANIFEST.json",
            "sha256": sha(manifest),
            "file_count": len(files),
            "bytes": sum(f["bytes"] for f in files),
        },
        "limits": [
            "one fixed recording per route, not statistical or held-out validation",
            "ENTRY 0.05 FP/frame 0.38559 is higher than 0.15 FP/frame 0",
            "modification C waits for PR561 merge; joint detector+scheduler not yet verified",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
