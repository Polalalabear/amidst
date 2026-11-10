"""Export a new code snapshot; does not create a Git worktree or fetch objects."""

import argparse
import json
import subprocess
from pathlib import Path

from amidst.q1q5.source_bundle import digest, rebuild


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "composition", "composition-sha256", "output"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args(argv)
    path = Path(args.composition)
    if path.resolve() != path or path.is_symlink() or path.stat().st_size > 16_777_216:
        p.error("Canonical bounded composition file required")
    raw = path.read_bytes()
    if digest(raw) != args.composition_sha256:
        p.error("Composition file pin mismatch")
    before = subprocess.check_output(["df", "-k", str(Path(args.output).parent)], text=True)
    report = rebuild(args.repo, json.loads(raw), Path(args.output))
    report["df_before_k"] = before
    report["df_after_k"] = subprocess.check_output(["df", "-k", args.output], text=True)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
