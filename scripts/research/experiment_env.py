#!/usr/bin/env python3
"""Validate an amidst.experiment-env.v1 manifest (PROPOSED) and print its canonical SHA-256.

Read-only. Registration of the schema grants no approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from amidst.contracts.q_demo.mini_schema import Validator  # noqa: E402

SCHEMA = REPO / 'docs/contracts/schemas/amidst.experiment-env.v1.schema.json'


def canonical_sha256(manifest):
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def utc_instant(text):
    """Parse a schema-valid UTC timestamp into an aware datetime; ValueError for non-existent dates."""
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z', text)
    if not match:
        raise ValueError(text)
    micro = (match.group(2) or '0')[:6].ljust(6, '0')
    return datetime.strptime(match.group(1) + '.' + micro, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)


def validate(manifest):
    """Return a list of error strings; empty means valid. Schema errors plus cross-field rules."""
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    errors = [str(e) for e in Validator(lambda _name: schema).validate(manifest, 'env')]
    if errors:
        return errors
    ps = manifest['parameter_set']
    if ps['status'] == 'APPROVED' and 'approval_ref' not in ps:
        errors.append('$.parameter_set: APPROVED requires approval_ref')
    if ps['status'] == 'APPROVED' and ps['parameter_set_sha256'] == 'UNKNOWN':
        errors.append('$.parameter_set: APPROVED requires a known parameter_set_sha256')
    run = manifest['run']
    start, end = run['started_at_utc'], run['finished_at_utc']
    parsed = {}
    for name, text in (('started_at_utc', start), ('finished_at_utc', end)):
        if text != 'UNKNOWN':
            try:
                parsed[name] = utc_instant(text)
            except ValueError:
                errors.append(f'$.run.{name}: not a real UTC calendar date/time')
    if len(parsed) == 2 and parsed['finished_at_utc'] < parsed['started_at_utc']:
        errors.append('$.run: finished_at_utc is before started_at_utc')
    if manifest['gt_isolation']['gt_path_scan'] == 'FAIL':
        errors.append('$.gt_isolation: gt_path_scan FAIL; run is not usable as evidence')
    if manifest['source_class'] == 'FORMAL':
        for field, value in (('git_commit', run['git_commit']), ('parameter_set_sha256', ps['parameter_set_sha256'])):
            if value == 'UNKNOWN':
                errors.append(f'$: FORMAL run requires known {field}')
        if manifest['gt_isolation']['gt_path_scan'] != 'PASS':
            errors.append('$.gt_isolation: FORMAL run requires gt_path_scan PASS')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    errors = validate(manifest)
    if errors:
        print('INVALID')
        for error in errors:
            print(f'  {error}')
        return 1
    note = ' (parameter set PROPOSED, not approved)' if manifest['parameter_set']['status'] == 'PROPOSED' else ''
    print(f'VALID env_manifest_sha256={canonical_sha256(manifest)}{note}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
