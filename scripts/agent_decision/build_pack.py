#!/usr/bin/env python3
"""Build self-contained Windows / Colab evaluation pack (WP6 / #515)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from amidst.agent_eval import windows_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='build_pack.py',
        description='Build self-contained Windows / Colab evaluation pack with MANIFEST.json and verify_pack.py.',
    )
    parser.add_argument('--out', required=True, help='Output directory for the pack')
    parser.add_argument(
        '--file',
        action='append',
        default=[],
        metavar='REL=SRC',
        help='Relative POSIX path in pack mapped to source file path (repeatable)',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.file:
        parser.error('at least one --file REL=SRC mapping is required')

    files: dict[str, Path] = {}
    for entry in args.file:
        if '=' not in entry:
            parser.error(f'invalid --file mapping {entry!r}; expected REL=SRC')
        rel, src = entry.split('=', 1)
        files[rel.strip()] = Path(src.strip())

    windows_pack.build_pack(Path(args.out), files=files)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
