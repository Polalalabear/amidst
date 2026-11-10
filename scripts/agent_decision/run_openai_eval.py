#!/usr/bin/env python3
"""CLI wrapper for Agent evaluation runner (defaults to DRY_RUN; refuses unapproved LIVE stages) (#515)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from amidst.agent_eval import runner


def main(argv: Sequence[str] | None = None, *, provider: Any = None) -> int:
    return runner.main(argv, provider=provider)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
