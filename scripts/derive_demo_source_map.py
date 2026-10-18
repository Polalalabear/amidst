"""Build a source-only C7 map from a pinned LOCAL evaluated mesh extract."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from amidst.geometry.source_floor_map import derive_source_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    raw = args.input.read_bytes()
    extract = json.loads(gzip.decompress(raw))
    result = derive_source_map(extract, extract_sha256=hashlib.sha256(raw).hexdigest())
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    from amidst.geometry.source_floor_map import digest

    result.pop("output_sha256")
    result["output_sha256"] = digest(result)
    with args.output.open("x") as stream:
        json.dump(result, stream, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "floor": result["floor"]["evidence"],
                "variants": {
                    k: {
                        "regions": len(v["regions"]),
                        "portals": len(v["portals"]),
                        "furniture": len(v["furniture"]),
                        "walkable_m2": v["walkable_area_m2"],
                    }
                    for k, v in result["variants"].items()
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
