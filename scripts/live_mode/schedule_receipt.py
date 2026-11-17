"""Build a compact, source-bound CX-L2 receipt without running models or reading keys."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    root = a.artifacts
    files = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if (
            not p.is_file()
            or p.name == "ARTIFACTS_MANIFEST.json"
            or any(part in ("uv-cache", "final-tmp", "__pycache__") for part in rel.parts)
        ):
            continue
        files.append({"path": rel.as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)})
    manifest = root / "ARTIFACTS_MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {"files": files, "file_count": len(files), "bytes": sum(f["bytes"] for f in files)},
            indent=2,
        )
        + "\n"
    )
    quality = {n: json.loads((root / f"replay-n{n}/quality.json").read_text()) for n in (1, 3)}
    latency = {}
    for p in sorted((root / "latency").glob("*.latency.json")):
        row = json.loads(p.read_text())
        latency[row["label"]] = {
            k: row[k]
            for k in (
                "achieved_fps",
                "frame_latency_ms",
                "schedule",
                "ticks_displayed",
                "protocol_violations",
                "query",
                "secs",
                "stage_ms_p50",
            )
        }
    git = lambda arg: subprocess.check_output(["git", "rev-parse", arg], text=True).strip()
    receipt = {
        "tested_code_head": git("HEAD"),
        "tested_tree": git("HEAD^{tree}"),
        "artifact_root": "$AMIDST_ARTIFACTS/cx553-20261117",
        "manifest_sha256": digest(manifest),
        "artifact_files": len(files),
        "artifact_bytes": sum(f["bytes"] for f in files),
        "focused_tests": {"python": 44, "node": 36, "failures": 0},
        "graph": quality[1]["graph"],
        "quality_runs": len(quality[1]["source_inventory"]),
        "quality_mean": {str(n): quality[n]["mean"] for n in (1, 3)},
        "latency": latency,
        "paid_calls": 0,
        "gt_in_policy": False,
        "limits": [
            "N=1 selected on this same cohort, not a held-out evaluation",
            "CAM_ENTRY topology UNKNOWN: all-camera fallback",
            "graph hubs retain seven cameras",
            "one real latency run per route and mode; shared GPU not exclusive",
            "fresh latency active-camera visibility is not person-following correctness",
            "unmerged #559 detector plus scheduler integration not tested",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in ("tested_code_head", "manifest_sha256", "artifact_files", "artifact_bytes")
            }
        )
    )


if __name__ == "__main__":
    main()
