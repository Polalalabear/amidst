"""Build a new source-bound C5 index from independently materialized static rays."""

import argparse
import hashlib
import json
from pathlib import Path

from amidst.engineering.hybrid_contact import _prior
from amidst.engineering.registry import content_hash
from amidst.geometry.floor_visibility_index import build_visibility_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["rays", "map", "safe-inputs", "hybrid-config", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() in {
        p.resolve() for p in (args.rays, args.map, args.safe_inputs, args.hybrid_config)
    }:
        raise ValueError("OUTPUT_EXISTS_OR_ALIASED")
    rays, physical, safe, hybrid = [
        json.loads(p.read_text())
        for p in (args.rays, args.map, args.safe_inputs, args.hybrid_config)
    ]
    if hashlib.sha256(args.safe_inputs.read_bytes()).hexdigest() != rays["safe_inputs_sha256"]:
        raise ValueError("SAFE_INPUTS_HASH_MISMATCH")
    result = build_visibility_index(
        rays,
        physical,
        ray_file_sha256=hashlib.sha256(args.rays.read_bytes()).hexdigest(),
        physical_file_sha256=hashlib.sha256(args.map.read_bytes()).hexdigest(),
        run_parameters=_prior(hybrid, rays["config"]["run_id"], foot_band=True),
        calibration_sha256=content_hash([c["calibration"] for c in safe["cameras"]]),
        floor_sha256=content_hash(safe["floor_plane"]),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "cameras": [
                    {k: e[k] for k in ["camera_id", "area_m2"]}
                    | {"cell_counts": e["sampling"]["cell_status_counts"]}
                    for e in result["entries"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
