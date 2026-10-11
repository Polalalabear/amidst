"""Extract source-bound safe Blender RGB/model inputs without rendering or scene copies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.workbench.blender_scene import materialize_blender_workbench


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--canonical-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sites", nargs="+", default=["office", "classroom101", "auditorium"])
    args = parser.parse_args()
    receipt = materialize_blender_workbench(args.repo, args.canonical_repo, args.output, args.sites)
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
