"""Build a new source-pinned v2 static review folder; never grant approval."""

import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-v3-1", action="store_true")
    parser.add_argument("--base-graphs")
    parser.add_argument("--static-provenance")
    parser.add_argument("--graph-v3", action="store_true", help="D74/D77 static graph revision")
    for arg in [
        "config",
        "config-sha256",
        "membership",
        "membership-sha256",
        "prior-pack",
        "prior-manifest-sha256",
        "output",
    ]:
        parser.add_argument("--" + arg, required=arg in {"config", "config-sha256", "output"})
    args = parser.parse_args()
    path = Path(__file__).parents[1] / "src/amidst/evaluation/r004_review_v2.py"
    spec = importlib.util.spec_from_file_location("r004_review_v2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.graph_v3_1:
        if args.graph_v3 or not args.base_graphs or not args.static_provenance:
            parser.error("v3.1 requires --base-graphs and --static-provenance, without --graph-v3")
        result = module.build_graph_v3_1(args.config, args.config_sha256,
                                       args.base_graphs, args.static_provenance, args.output)
        print(json.dumps(result, ensure_ascii=False))
        return
    if not all([args.membership, args.membership_sha256, args.prior_pack,
                args.prior_manifest_sha256]):
        parser.error("membership and prior packet pins required")
    build = module.build_graph_v3 if args.graph_v3 else module.build_review
    result = build(
        args.config,
        args.config_sha256,
        args.membership,
        args.membership_sha256,
        args.prior_pack,
        args.prior_manifest_sha256,
        args.output,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
