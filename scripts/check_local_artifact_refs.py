#!/usr/bin/env python3
"""Check LOCAL artifact references in the docs a PR changes (#486, D218).

A LOCAL path in a changed ``.md`` or ``.json`` file must be relative to
``local/{data,evidence,archive}`` or ``$AMIDST_ARTIFACTS`` and must carry a SHA-256 (or an
explicit "cannot be rebuilt" / "not applicable") on the same line or the same table row.
JSON files also accept the SHA within three lines around the path.

Findings:
  BAD_LOCAL_PATH  /tmp, /private/tmp, absolute home paths, ~/amidst-artifacts, ~/amidst-demo-state,
                  ~/Developer/amidst*, $HOME/amidst-*
  LOCAL_REF_NO_SHA  a valid LOCAL path without a SHA-256 or an explicit exemption phrase

A line containing ``local-ref-ignore`` is skipped (for rules that name a forbidden path).
Warning mode (default) always exits 0; ``--strict`` exits 1 when there is any finding.
Reads only the text of the changed files; never opens any LOCAL artifact.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

IGNORE = 'local-ref-ignore'
SHA = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])')
EXEMPT = re.compile(r'無法重建|不適用|cannot be rebuilt|not applicable', re.IGNORECASE)
GOOD = re.compile(r'(?<![\w/.-])(?:local/(?:data|evidence|archive)/|\$\{?AMIDST_ARTIFACTS\}?/)[^\s`"\'|)\]>,;]+')
BAD = re.compile(
    r'(?:/private/tmp/|(?<![\w.-])/tmp/|/Users/[^/\s`"\']+/|/home/[^/\s`"\']+/|/Users/Shared/'
    r'|~/amidst-artifacts|~/amidst-demo-state|~/\.amidst-[\w-]+|~/Developer/amidst[\w-]*'
    r'|\$\{?HOME\}?/amidst-[\w-]+|(?<![\w/.-])amidst-artifacts/)')
FENCE = re.compile(r'^\s*(```|~~~)')


def changed_files(repo: Path, base: str) -> list[str]:
    out = subprocess.run(['git', '-C', str(repo), 'diff', '--name-only', '--diff-filter=AM', f'{base}...HEAD'],
                         check=True, capture_output=True, text=True).stdout
    return [n for n in out.splitlines() if n.endswith(('.md', '.json'))]


def _has_sha(text: str) -> bool:
    return bool(SHA.search(text) or EXEMPT.search(text))


def scan_text(name: str, text: str) -> list[dict]:
    lines = text.splitlines()
    is_json = name.endswith('.json')
    findings: list[dict] = []
    in_fence = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
        if IGNORE in line:
            continue
        for m in BAD.finditer(line):
            findings.append({'code': 'BAD_LOCAL_PATH', 'file': name, 'line': i + 1, 'match': m.group(0)})
        if in_fence and not is_json:
            continue  # commands show paths; only forbidden spellings are checked there
        good = GOOD.search(line)
        if not good:
            continue
        if is_json:
            window = ' '.join(lines[max(0, i - 3):i + 4])
        else:
            window = line
        if not _has_sha(window):
            findings.append({'code': 'LOCAL_REF_NO_SHA', 'file': name, 'line': i + 1, 'match': good.group(0)})
    return findings


def check(repo: Path, names: list[str]) -> list[dict]:
    findings: list[dict] = []
    for name in names:
        path = repo / name
        if not path.is_file() or path.is_symlink():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        if name.endswith('.json'):
            try:
                json.loads(text)
            except ValueError:
                findings.append({'code': 'INVALID_JSON', 'file': name, 'line': 1, 'match': ''})
                continue
        findings.extend(scan_text(name, text))
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--base', default='origin/main', help='compare BASE...HEAD')
    p.add_argument('--files', nargs='*', help='check these repo-relative files instead of the diff')
    p.add_argument('--strict', action='store_true', help='exit 1 when any finding exists')
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)
    names = args.files if args.files is not None else changed_files(args.repo, args.base)
    findings = check(args.repo, names)
    if args.json:
        print(json.dumps({'files': len(names), 'findings': findings}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}: {f['code']}: {f['match']}")
        print(f"checked {len(names)} file(s); {len(findings)} finding(s); mode={'strict' if args.strict else 'warn'}")
    return 1 if (findings and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
