"""Export D15 policy only; never alter a frozen physical map or source asset."""

import argparse
import hashlib
import json
from pathlib import Path

from amidst.geometry.restricted_policy import build_restricted_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("map", "annotations", "config", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() in {
        p.resolve() for p in (args.map, args.annotations, args.config)
    }:
        raise ValueError("OUTPUT_EXISTS_OR_ALIASED")
    config = json.loads(args.config.read_text())
    raw_map, raw_annotations = args.map.read_bytes(), args.annotations.read_bytes()
    map_sha, annotation_sha = (hashlib.sha256(v).hexdigest() for v in (raw_map, raw_annotations))
    if (
        map_sha != config["physical_map_sha256"]
        or annotation_sha != config["annotation_file_sha256"]
    ):
        raise ValueError("POLICY_INPUT_HASH_MISMATCH")
    result = build_restricted_policy(
        json.loads(raw_map),
        json.loads(raw_annotations),
        annotation_file_sha256=annotation_sha,
        physical_file_sha256=map_sha,
        confirmations=config["confirmations"],
    )
    with args.output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print(
        json.dumps(
            {
                "variants": {
                    k: len(v["restricted_regions"]) for k, v in result["variants"].items()
                },
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
