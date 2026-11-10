"""Build an offline pinned r004 pre-review package without running models."""

import argparse
import importlib.util
import json
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "src/amidst/evaluation/r004_prereview_pack.py"
spec = importlib.util.spec_from_file_location("r004_prereview_pack", module_path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
PackError, build_pack = engine.PackError, engine.build_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["config", "config-sha256", "report", "report-sha256", "output"]:
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--ui-assets")
    args = parser.parse_args()
    try:
        result = build_pack(
            args.config,
            args.config_sha256,
            args.report,
            args.report_sha256,
            args.output,
            args.ui_assets,
        )
    except (PackError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
