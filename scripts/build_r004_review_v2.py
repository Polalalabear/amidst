"""Build a new source-pinned v2 static review folder; never grant approval."""

import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in [
        "config",
        "config-sha256",
        "membership",
        "membership-sha256",
        "prior-pack",
        "prior-manifest-sha256",
        "output",
    ]:
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    path = Path(__file__).parents[1] / "src/amidst/evaluation/r004_review_v2.py"
    spec = importlib.util.spec_from_file_location("r004_review_v2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.build_review(
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
