"""Pinned, read-only static graph pre-review; produces no approval or input edits."""

import argparse
import importlib.util
import json
from pathlib import Path

# The package's historical __init__ imports research metrics/numpy. This static
# command deliberately loads only its standard-library checker file.
_source = Path(__file__).resolve().parents[1] / "src/amidst/evaluation/q1q5_graph_check.py"
_spec = importlib.util.spec_from_file_location("r004_static_check", _source)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
check_graphs = _module.check_graphs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check_graphs(args.config, args.config_sha256)
    # Exclusive creation preserves every previous receipt; no source writes.
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "counts": report["counts"],
                "output_sha256": report["output_sha256"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
