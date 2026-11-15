#!/usr/bin/env python3
"""Build the WP5 Colab L4 and Windows local-model packs from a git checkout (no key, no GT, no media)."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from amidst.agent_eval import wp5_pack


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, help='output folder (LOCAL), e.g. local/data/wp5-packs-20261115')
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument('--commit', help='source commit (default: git rev-parse HEAD of --repo)')
    ap.add_argument('--per-type', type=int, default=40)
    a = ap.parse_args(argv)
    commit = a.commit or subprocess.run(['git', '-C', a.repo, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = [wp5_pack.build_wp5_pack(out / f'wp5-pack_{t}_{wp5_pack.PACK_DATE}', repo_root=a.repo, target=t, commit=commit, per_type=a.per_type)
               for t in wp5_pack.TARGETS]
    shutil.copyfile(Path(a.repo) / wp5_pack.NOTEBOOK, out / 'wp5_colab_l4.ipynb')
    (out / 'SHA256SUMS.txt').write_text(''.join(f"{r['zip_sha256']}  {Path(r['zip']).name}\n" for r in results) + hashlib.sha256((out / 'wp5_colab_l4.ipynb').read_bytes()).hexdigest() + '  wp5_colab_l4.ipynb\n', encoding='utf-8')
    print(json.dumps(results, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
