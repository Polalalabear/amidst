#!/usr/bin/env python3
"""Read-only tool for the D138 artifact ledger (configs/provenance/artifact_ledger_v1.json).

Subcommands
  validate  structural check of the ledger (no file system access to entries)
  compute   fill size / file count / SHA-256 for entries (streaming, read-only)
  verify    recompute entries and compare with the ledger (exit 1 on mismatch)

Manifest SHA-256 of a directory = sha256 over the lines "<file sha256>  <relative posix path>\n",
sorted by relative path. Symlinks hash the text "symlink:<target>". Directories named in
EXCLUDED_DIR_NAMES (e.g. gt_private) are never opened: only path, size and file count are recorded.
Nothing is written to, moved or deleted from the entries; only the ledger file may be written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCHEMA_VERSION = 'amidst.artifact-ledger.v1'
TYPES = ('raw_data', 'derived_data', 'evidence', 'cache', 'code_checkout', 'model', 'environment',
         'tool', 'doc', 'scratch', 'untracked_source', 'git_ref')
DISPOSITIONS = ('keep_original', 'move_to_mainline', 'archivable', 'deletable', 'user_decision')
REBUILDABLE = ('yes', 'partial', 'no', 'unknown')
HASH_POLICIES = ('full', 'files_only', 'none', 'git_head', 'path_size_only')
COMPLETENESS = ('complete', 'partial', 'not_computed', 'not_applicable')
EXCLUDED_DIR_NAMES = frozenset({'gt_private', 'ground_truth'})
SKIP_NAMES = frozenset({'.DS_Store'})
SAFETY_STATUS = ('SAFE', 'KEEP', 'UNKNOWN')
SAFETY_CHECKS = ('refs_mainline', 'running_services', 'unmerged_work', 'evidence_preservation', 'raw_assets')
SAFETY_RESULTS = ('pass', 'fail', 'unknown')
SHA = '0123456789abcdef'


def is_sha(value, n=64):
    return isinstance(value, str) and len(value) == n and all(c in SHA for c in value)


def expand(path, home=None):
    home = home or os.environ.get('AMIDST_LEDGER_HOME') or str(Path.home())
    if path == '~':
        return Path(home)
    if path.startswith('~/'):
        return Path(home) / path[2:]
    return Path(path)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def walk(root):
    """Yield (relative posix path, absolute path, is_symlink, size) for non-excluded files; collect excluded."""
    files, excluded = [], []
    stack = [(root, '')]
    while stack:
        directory, prefix = stack.pop()
        with os.scandir(directory) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            rel = prefix + entry.name
            if entry.name in SKIP_NAMES:
                continue
            if entry.is_symlink():
                files.append((rel, entry.path, True, 0))
            elif entry.is_dir(follow_symlinks=False):
                if entry.name in EXCLUDED_DIR_NAMES:
                    size = count = 0
                    for r, _, names in os.walk(entry.path):
                        for name in names:
                            try:
                                size += os.lstat(os.path.join(r, name)).st_size
                                count += 1
                            except OSError:
                                pass
                    excluded.append({'path': rel + '/', 'size_bytes': size, 'file_count': count,
                                     'reason': 'GT_PRIVATE_PATH_AND_SIZE_ONLY'})
                else:
                    stack.append((entry.path, rel + '/'))
            elif entry.is_file(follow_symlinks=False):
                files.append((rel, entry.path, False, entry.stat(follow_symlinks=False).st_size))
    files.sort(key=lambda item: item[0])
    return files, excluded


def hash_one(item):
    rel, path, is_link, _ = item
    if is_link:
        return hashlib.sha256(('symlink:' + os.readlink(path)).encode()).hexdigest()
    return file_sha256(path)


def manifest_digest(rows):
    h = hashlib.sha256()
    for rel, sha in sorted(rows):
        h.update(f'{sha}  {rel}\n'.encode())
    return h.hexdigest()


def compute_entry(entry, workers=4, hash_files=True, home=None):
    """Return the computed part of an entry (size, file_count, hash) without touching the entry."""
    path = expand(entry['path'], home)
    policy = entry.get('hash', {}).get('policy', 'full')
    out = {'policy': policy}
    if not path.exists() and not path.is_symlink():
        return {'size_bytes': None, 'file_count': None, 'hash': {**out, 'completeness': 'not_computed',
                                                                  'note': 'PATH_MISSING_AT_COMPUTE_TIME'}}
    if path.is_file():
        size = path.stat().st_size
        res = {'size_bytes': size, 'file_count': 1, 'hash': out}
        if policy in ('full', 'files_only') and hash_files:
            res['hash'].update(sha256=file_sha256(path), completeness='complete', hashed_files=1)
        else:
            res['hash'].update(completeness='not_computed')
        return res
    if policy == 'git_head':
        return {'size_bytes': None, 'file_count': None, 'hash': {**out, 'completeness': 'not_applicable'}}
    files, excluded = walk(path)
    size = sum(f[3] for f in files)
    res = {'size_bytes': size, 'file_count': len(files), 'hash': out}
    if excluded:
        out['excluded'] = excluded
        res['size_bytes'] = size
        res['excluded_size_bytes'] = sum(e['size_bytes'] for e in excluded)
        res['excluded_file_count'] = sum(e['file_count'] for e in excluded)
    if policy in ('full', 'files_only') and hash_files:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            shas = list(pool.map(hash_one, files))
        rows = [(f[0], s) for f, s in zip(files, shas)]
        out.update(manifest_sha256=manifest_digest(rows), completeness='complete', hashed_files=len(rows))
    else:
        out['completeness'] = 'not_computed'
    return res


def apply_computed(entry, comp):
    entry['size_bytes'] = comp['size_bytes']
    entry['file_count'] = comp['file_count']
    if 'excluded_size_bytes' in comp:
        entry['excluded_size_bytes'] = comp['excluded_size_bytes']
        entry['excluded_file_count'] = comp['excluded_file_count']
    keep = {k: v for k, v in entry.get('hash', {}).items() if k in ('policy', 'git', 'note')}
    keep.update(comp['hash'])
    entry['hash'] = keep


def validate(ledger):
    errors = []
    if ledger.get('schema_version') != SCHEMA_VERSION:
        errors.append('schema_version')
    for key in ('generated_at', 'baseline_ref', 'issue_ref', 'entries', 'rules'):
        if key not in ledger:
            errors.append(f'missing:{key}')
    ids = set()
    for i, e in enumerate(ledger.get('entries', [])):
        tag = e.get('id', f'#{i}')
        if tag in ids:
            errors.append(f'duplicate id {tag}')
        ids.add(tag)
        for key in ('id', 'path', 'type', 'disposition', 'purpose', 'retain_reason', 'rebuildable',
                    'referenced_by', 'hash', 'size_bytes', 'file_count'):
            if key not in e:
                errors.append(f'{tag}: missing {key}')
        if e.get('type') not in TYPES:
            errors.append(f'{tag}: type')
        if e.get('disposition') not in DISPOSITIONS:
            errors.append(f'{tag}: disposition')
        if e.get('rebuildable') not in REBUILDABLE:
            errors.append(f'{tag}: rebuildable')
        if not isinstance(e.get('referenced_by'), list):
            errors.append(f'{tag}: referenced_by')
        if not str(e.get('path', '')).startswith(('~/', '/')):
            errors.append(f'{tag}: path must be ~/ or absolute')
        for key in ('size_bytes', 'file_count'):
            v = e.get(key)
            if v is not None and (not isinstance(v, int) or v < 0):
                errors.append(f'{tag}: {key}')
        h = e.get('hash', {})
        if h.get('policy') not in HASH_POLICIES:
            errors.append(f'{tag}: hash.policy')
        if h.get('completeness') not in COMPLETENESS:
            errors.append(f'{tag}: hash.completeness')
        for key in ('sha256', 'manifest_sha256'):
            if key in h and not is_sha(h[key]):
                errors.append(f'{tag}: hash.{key}')
        if h.get('completeness') == 'complete' and not ('sha256' in h or 'manifest_sha256' in h):
            errors.append(f'{tag}: complete without digest')
        if h.get('policy') == 'git_head' and not is_sha(h.get('git', {}).get('head'), 40):
            errors.append(f'{tag}: git head')
        if e.get('type') == 'raw_data' and h.get('policy') not in ('full', 'files_only', 'path_size_only'):
            errors.append(f'{tag}: raw_data needs a digest policy')
        errors += validate_safety(tag, e)
    return errors


def validate_safety(tag, e):
    """D157: SAFE needs all five checks to pass, a verify command and a restore method; deletable needs SAFE."""
    out = []
    sf = e.get('safety')
    if not isinstance(sf, dict):
        return [f'{tag}: missing safety']
    if sf.get('status') not in SAFETY_STATUS:
        out.append(f'{tag}: safety.status')
    checks = sf.get('checks')
    if not isinstance(checks, dict) or set(checks) != set(SAFETY_CHECKS) or \
            any(v not in SAFETY_RESULTS for v in checks.values()):
        out.append(f'{tag}: safety.checks')
        checks = {}
    if not sf.get('reason'):
        out.append(f'{tag}: safety.reason')
    if sf.get('status') == 'SAFE':
        if any(v != 'pass' for v in checks.values()):
            out.append(f'{tag}: SAFE requires all checks pass')
        if not sf.get('verify_commands') or not sf.get('restore'):
            out.append(f'{tag}: SAFE requires verify_commands and restore')
    if e.get('disposition') == 'deletable' and sf.get('status') != 'SAFE':
        out.append(f'{tag}: deletable requires safety SAFE')
    if e.get('type') == 'raw_data' and sf.get('status') == 'SAFE':
        out.append(f'{tag}: raw_data can never be SAFE')
    return out


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(ledger, path):
    Path(path).write_text(json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('validate', 'compute', 'verify'):
        p = sub.add_parser(name)
        p.add_argument('--ledger', default='configs/provenance/artifact_ledger_v1.json')
        if name != 'validate':
            p.add_argument('--only', help='comma separated entry ids')
            p.add_argument('--workers', type=int, default=4)
            p.add_argument('--home', help='override ~ (or env AMIDST_LEDGER_HOME)')
        if name == 'compute':
            p.add_argument('--out')
            p.add_argument('--no-hash', action='store_true', help='sizes and file counts only')
            p.add_argument('--only-missing', action='store_true', help='skip entries already complete')
        if name == 'verify':
            p.add_argument('--skip-missing', action='store_true')
    args = ap.parse_args(argv)
    ledger = load(args.ledger)
    if args.cmd == 'validate':
        errors = validate(ledger)
        print('PASS' if not errors else 'FAIL', len(ledger.get('entries', [])), 'entries')
        for e in errors:
            print(' ', e)
        return 1 if errors else 0
    only = set(args.only.split(',')) if args.only else None
    bad = 0
    for entry in ledger['entries']:
        if only and entry['id'] not in only:
            continue
        if args.cmd == 'compute' and args.only_missing and entry.get('hash', {}).get('completeness') == 'complete':
            continue
        comp = compute_entry(entry, args.workers, not getattr(args, 'no_hash', False), args.home)
        if args.cmd == 'compute':
            if comp['hash'].get('completeness') == 'not_computed' and comp['size_bytes'] is not None and \
                    args.no_hash and entry.get('hash', {}).get('completeness') == 'complete':
                comp['hash'] = entry['hash']
            apply_computed(entry, comp)
            print(f"{entry['id']}: size={comp['size_bytes']} files={comp['file_count']} "
                  f"{comp['hash'].get('completeness')}", flush=True)
            if args.out:
                dump(ledger, args.out)
        else:
            if comp['size_bytes'] is None and args.skip_missing:
                continue
            h = entry['hash']
            want = h.get('sha256') or h.get('manifest_sha256')
            got = comp['hash'].get('sha256') or comp['hash'].get('manifest_sha256')
            if comp['size_bytes'] != entry['size_bytes'] or comp['file_count'] != entry['file_count'] or \
                    (want and got != want):
                bad += 1
                print(f"MISMATCH {entry['id']}: size {entry['size_bytes']}->{comp['size_bytes']} "
                      f"files {entry['file_count']}->{comp['file_count']} sha {want}->{got}")
    if args.cmd == 'compute' and not args.out:
        dump(ledger, args.ledger)
    if args.cmd == 'verify':
        print('PASS' if not bad else f'FAIL {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
