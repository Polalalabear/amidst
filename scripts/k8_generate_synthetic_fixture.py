#!/usr/bin/env python3
"""Generate the K8 SYNTHETIC Office fixture (task K8b, design D23 §8).

Runs K1/K5 (S1, S3) and the K8c candidate screen (S2) on declared endpoints and
footprints and writes ``frontend/workbench/fixtures/k8-synthetic-office.fixture.json``.
Needs the Codex C7 map (hash-pinned, never copied): ``--c7-map PATH``, ``$K8_C7_MAP``,
or a git ref that holds it (``git show origin/codex/c5-d21-strict-visibility:...``).

    PYTHONPATH=src python scripts/k8_generate_synthetic_fixture.py [--check]

``--check`` regenerates in memory and fails if the file on disk differs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from amidst.blind_hypothesis import candidate_screen as screen_module  # noqa: E402
from amidst.blind_hypothesis import engine, retrieval_evidence  # noqa: E402
from amidst.synthetic import k8_office  # noqa: E402

FIXTURE_PATH = ROOT / "frontend/workbench/fixtures/k8-synthetic-office.fixture.json"
CONFIG_PATH = ROOT / "configs/k8_synthetic_blind_hypothesis_v1.json"

# Upstream draft PR heads this fixture was generated against (design §9, K8a/K8c).
UPSTREAM = {
    "k1_base": {"pr": 48, "branch": "claude/k1-restricted", "commit": "74c6ace"},
    "k8a_synthetic_method": {
        "pr": 58,
        "branch": "claude/k8a-synthetic-method",
        "commit": "131869d127798d3deba595dd9b5c533279f8fbc8",
    },
    "k8c_candidate_screen": {
        "pr": 57,
        "branch": "claude/k8c-candidate-screen",
        "commit": "6db6eab665baf310343711b021478c685c406497",
    },
    "c7_source_map": {
        "pr": 40,
        "branch": "codex/c7-source-map",
        "commit": "4c5416662195771fc3a1015b6a8df1e47cafb886",
        "also_on": {
            "pr": 53,
            "branch": "codex/c5-d21-strict-visibility",
            "commit": "0cb2c2283451cd90946333f1a3c74b29f4c56682",
        },
        "git_blob": "6ac4bba369b44ee8dd6d437237c5bbd8e54ce6ee",
    },
    "k8_design": {"pr": 56, "branch": "claude/k8-synthetic-design", "commit": "91d944a"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--c7-map", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    c7 = args.c7_map or k8_office.locate_c7_map(ROOT)
    if c7 is None:
        print(
            "UNKNOWN: C7 map not found. Pass --c7-map, set K8_C7_MAP, or fetch "
            f"{k8_office.C7_MAP_REPO_PATH} from a Codex branch (sha256 "
            f"{k8_office.C7_MAP_SHA256}).",
            file=sys.stderr,
        )
        return 2
    fixture = k8_office.build_fixture(
        c7_map_path=c7,
        config_path=CONFIG_PATH,
        engine_files={
            "src/amidst/blind_hypothesis/engine.py": Path(engine.__file__),
            "src/amidst/blind_hypothesis/retrieval_evidence.py": Path(retrieval_evidence.__file__),
            "src/amidst/blind_hypothesis/candidate_screen.py": Path(screen_module.__file__),
        },
        generator_files={
            "scripts/k8_generate_synthetic_fixture.py": Path(__file__),
            "src/amidst/synthetic/k8_office.py": Path(k8_office.__file__),
        },
        upstream=UPSTREAM,
    )
    text = k8_office.dump_fixture(fixture)
    if args.check:
        same = args.out.is_file() and args.out.read_text(encoding="utf-8") == text
        print(f"fixture {'matches' if same else 'DIFFERS FROM'} {args.out}")
        return 0 if same else 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} fixture_sha256={fixture['fixture_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
