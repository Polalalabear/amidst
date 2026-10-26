"""Verify immutable originals and record a separately hashed human CSV return."""

import argparse
import importlib.util
import json
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "src/amidst/evaluation/r004_prereview_pack.py"
spec = importlib.util.spec_from_file_location("r004_prereview_pack", module_path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
PackError, import_pack, verify_pack = engine.PackError, engine.import_pack, engine.verify_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--returned-csv")
    parser.add_argument("--output")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_only:
            manifest, rows = verify_pack(args.pack, args.manifest_sha256)
            result = {
                "status": "VERIFIED",
                "immutable_files": len(manifest["files"]),
                "items": len(rows),
                "approval_granted": False,
            }
        else:
            if not args.output:
                parser.error("--output is required unless --verify-only")
            result = import_pack(args.pack, args.manifest_sha256, args.returned_csv, args.output)
    except (PackError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
