#!/usr/bin/env python3
"""Demo pin (D171): the commit the demo checkout is approved to serve.

    demo_pin.py check                       exit 0 only if HEAD == pin and the tree is clean
    demo_pin.py approve --approved-by NAME --gate RESULT.txt

The pin lives in ``<root>/local/demo-pin.json`` (git-ignored). ``approve`` records the
current HEAD only for a clean tree and a gate result (``verify_gate.sh``) that is at most
24 hours old, has no FAIL line and has at least one PASS line. With no pin file ``check``
passes with a note: the pin applies once the owner has approved a version.
``AMIDST_DEMO_ALLOW_UNPINNED=1`` skips the check (QA ports only). Standard library only.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('AMIDST_ROOT') or REPO).expanduser().resolve()
PIN = ROOT / 'local/demo-pin.json'
GATE_MAX_AGE_S = 24 * 3600


def git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], check=True, capture_output=True, text=True).stdout.strip()


def state():
    return git('rev-parse', 'HEAD'), git('status', '--porcelain')


def check():
    if os.environ.get('AMIDST_DEMO_ALLOW_UNPINNED') == '1':
        print('DEMO_PIN: skipped (AMIDST_DEMO_ALLOW_UNPINNED=1, QA only)', file=sys.stderr)
        return 0
    if not PIN.is_file():
        print(f'DEMO_PIN: no pin at {PIN}; running unpinned', file=sys.stderr)
        return 0
    pin = json.loads(PIN.read_text(encoding='utf-8'))
    head, dirty = state()
    if head != pin.get('commit'):
        print(f"DEMO_PIN_MISMATCH: HEAD {head[:12]} != pin {str(pin.get('commit'))[:12]}. "
              'Approve the new version with demo_pin.py approve, or set AMIDST_DEMO_ALLOW_UNPINNED=1 for a QA port.',
              file=sys.stderr)
        return 1
    if dirty:
        print('DEMO_PIN_DIRTY_TREE: the pinned checkout has uncommitted changes', file=sys.stderr)
        return 1
    return 0


def approve(approved_by, gate):
    gate = Path(gate)
    if not approved_by.strip():
        raise SystemExit('APPROVED_BY_REQUIRED')
    if not gate.is_file() or time.time() - gate.stat().st_mtime > GATE_MAX_AGE_S:
        raise SystemExit('GATE_RESULT_MISSING_OR_OLDER_THAN_24H')
    lines = [line for line in gate.read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(' FAIL' in line or line.endswith('FAIL') for line in lines) or not any(line.endswith('PASS') for line in lines):
        raise SystemExit('GATE_NOT_PASSING')
    head, dirty = state()
    if dirty:
        raise SystemExit('CLEAN_TREE_REQUIRED')
    PIN.parent.mkdir(parents=True, exist_ok=True)
    record = {'commit': head, 'approved_by': approved_by, 'date': datetime.date.today().isoformat(), 'gate': str(gate)}
    temporary = PIN.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(PIN)
    print(f'DEMO_PIN approved {head}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check')
    ap = sub.add_parser('approve')
    ap.add_argument('--approved-by', required=True)
    ap.add_argument('--gate', required=True)
    args = parser.parse_args(argv)
    return check() if args.command == 'check' else approve(args.approved_by, args.gate)


if __name__ == '__main__':
    raise SystemExit(main())
