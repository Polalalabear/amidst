"""Recompute summary.json / summary.md from per-call rows (calls.jsonl) without touching a pack or rerunning anything.

    PYTHONPATH=src python -m amidst.agent_eval.wp5_resummary <dir containing calls.jsonl> [<dir> ...]

Writes summary.json and summary.md next to each calls.jsonl (the originals are overwritten; keep a copy first if needed).
Not part of the Colab pack; uses only the committed wp5.summarize_rows / render_summary_md.
"""
import json
import sys
from pathlib import Path

from amidst.agent_eval import wp5


def resummarize(d: Path) -> dict:
    rows = [json.loads(line) for line in (d / 'calls.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    summary = wp5.summarize_rows(rows)
    (d / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (d / 'summary.md').write_text(wp5.render_summary_md(summary), encoding='utf-8')
    return summary


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    for a in argv:
        s = resummarize(Path(a))
        print(f'{a}: status={s["status"]} cells={len(s["cells"])} warnings={len(s["warnings"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
