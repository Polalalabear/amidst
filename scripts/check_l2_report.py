#!/usr/bin/env python3
"""CQ-36-T synthetic aggregate checker; production report wire is UNSELECTED.

評分端；與推論隔離。This checker recalculates report aggregates from pinned
synthetic scored rows. It does not implement the v2 scorer or authenticate a freeze.
"""
import argparse
import hashlib
import json
from pathlib import Path

PROFILE = 'CQ36_SYNTHETIC_PROJECTION_V1'
ROLE = 'SYNTHETIC_ONLY'
DECISIONS = [f'U-D{i}' for i in range(1, 11)] + ['E1', 'E2', 'E3', 'UK-8']
RECOMMENDED = dict(zip(DECISIONS, ['M1', 'REPORT_ONLY', 'O1_D93', 'E2', 'RECOMPUTE', 'REJECT',
    'TOTAL_STANDARD_CLASSES', 'NEW_MODULE', 'CLAMPED_START', 'N_MAX_MINUS_2',
    'NOT_SELECTED', 'PREFIX_SEPARATE', 'NOT_SELECTED', 'PLAN_CHECK_ONLY']))
CLASSES = {'STANDARD', 'LONG_GAP', 'LONG_LOSS'}


class CheckError(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise CheckError(reason)


def canonical(doc):
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path).absolute()
    need(path.resolve() == path and path.is_file(), 'REGULAR_CANONICAL_FILE_REQUIRED')
    raw = path.read_bytes()
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    doc = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'NONFINITE_JSON'))
    need(isinstance(doc, dict), 'OBJECT_REQUIRED')
    return raw, doc


def aggregate(inputs, decisions, *, synthetic_profile=None):
    need(synthetic_profile == PROFILE, 'PRODUCTION_PROFILE_UNSELECTED')
    input_raw, receipt = read(inputs); decisions_raw, options = read(decisions)
    need(set(receipt) == {'fixture_role', 'projection', 'files'} and receipt['fixture_role'] == ROLE
         and receipt['projection'] == PROFILE, 'SYNTHETIC_RECEIPT_REQUIRED')
    need(set(options) == {'fixture_role', 'selections'} and options['fixture_role'] == ROLE, 'SYNTHETIC_DECISIONS_REQUIRED')
    selections = options['selections']
    pending = dict.fromkeys(DECISIONS, 'PENDING')
    need(selections == pending or selections == RECOMMENDED, 'TEST_SELECTION_UNSUPPORTED')
    # D93 is fixed regardless of a PENDING test row; OVERLAP never enters main.
    active = selections == RECOMMENDED
    files = receipt['files']
    need(set(files) == {'script', 'response', 'journal', 'scored_events', 'native_inputs'}, 'INPUT_FILE_SET')
    pins, docs = {}, {}
    for role, ref in files.items():
        need(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'INPUT_REF_FIELDS')
        name = Path(ref['path'])
        need(not name.is_absolute() and '..' not in name.parts and name.as_posix() == ref['path'], 'INPUT_PATH_UNSAFE')
        raw, doc = read(Path(inputs).absolute().parent / name)
        need(sha(raw) == ref['sha256'], 'INPUT_PIN_MISMATCH')
        need(doc.get('fixture_role') == ROLE and doc.get('projection') == PROFILE, 'SYNTHETIC_INPUT_REQUIRED')
        pins[role], docs[role] = sha(raw), doc
    native = docs['native_inputs']
    need(isinstance(native['files'], dict) and isinstance(native['cases'], list), 'NATIVE_INPUT_MANIFEST')
    for name, digest in native['files'].items():
        rel = Path(name)
        need(not rel.is_absolute() and '..' not in rel.parts and rel.as_posix() == name, 'INPUT_PATH_UNSAFE')
        path = Path(inputs).absolute().parent / rel
        need(path.resolve() == path and path.is_file(), 'REGULAR_CANONICAL_FILE_REQUIRED')
        raw = path.read_bytes()
        need(sha(raw) == digest, 'INPUT_PIN_MISMATCH')
        pins['native:' + name] = digest
    for case in native['cases']:
        for ref in case['artifacts'].values():
            need(native['files'].get(ref['path']) == ref['sha256'], 'NATIVE_INPUT_MANIFEST')
    expected = docs['script']['events']; scored = docs['scored_events']['events']
    need(isinstance(expected, list) and isinstance(scored, list) and len(expected) == len(scored), 'EVENT_SET_MISMATCH')
    ids = [e['event_id'] for e in expected]
    need(len(ids) == len(set(ids)) and [e['event_id'] for e in scored] == ids
         and [c['event_id'] for c in native['cases']] == ids, 'EVENT_SET_MISMATCH')
    sessions = docs['response']['sessions']; journal_sessions = docs['journal']['sessions']
    need(sessions == journal_sessions and isinstance(sessions, dict), 'SESSION_PROJECTION_MISMATCH')
    need(all(s in {'COMPLETE', 'ENDED_BY_LIMIT'} for s in sessions.values()), 'SESSION_STATUS_UNSUPPORTED')
    provenance = {'inputs_sha256': sha(input_raw), 'decisions_sha256': sha(decisions_raw), 'file_sha256': pins}
    events, grouped = [], {}
    for plan, score in zip(expected, scored):
        need(set(plan) == {'event_id', 'session_id', 'event_class', 'entry_kind'} and set(score) == {'event_id', 'matched'}, 'EVENT_FIELDS')
        need(plan['event_class'] in CLASSES and plan['entry_kind'] in {'BLIND', 'OVERLAP', 'NONE'} and type(score['matched']) is bool, 'EVENT_VALUES')
        status = sessions[plan['session_id']]
        if not active and (plan['event_class'] != 'STANDARD' or status == 'ENDED_BY_LIMIT' or plan['entry_kind'] == 'OVERLAP'):
            bucket = 'NOT_SCORED_PENDING_DECISION'; matched = None
        else:
            bucket = ('MEASURED_PARTIAL_ENDED_BY_LIMIT' if status == 'ENDED_BY_LIMIT' else 'COMPLETE')
            matched = score['matched']
        if plan['entry_kind'] == 'OVERLAP':
            bucket += '/OVERLAP_P_OV2_UNVERIFIED'
        events.append({**plan, 'bucket': bucket, 'matched': matched, 'provenance': provenance})
        if matched is None:
            continue
        for category in ('ALL', plan['event_class']):
            key = bucket + '/' + category
            grouped.setdefault(key, []).append(matched)
    metrics = {key: {'matched': sum(values), 'total': len(values), 'ratio': sum(values) / len(values), 'provenance': provenance}
               for key, values in sorted(grouped.items())}
    report = {'fixture_role': ROLE, 'projection': PROFILE, 'provenance': provenance,
              'events': events, 'metrics': metrics, 'pending_event_count': sum(e['matched'] is None for e in events),
              'human_approval_verified': False, 'native_scorer_executed': False}
    report['content_sha256'] = sha(canonical(report))
    return report


def check(report, inputs, decisions, *, synthetic_profile=None):
    # Refuse production before parsing any report/receipt, even if it happens to look synthetic.
    need(synthetic_profile == PROFILE, 'PRODUCTION_PROFILE_UNSELECTED')
    raw, actual = read(report)
    need(not any(word in raw.decode('utf-8') for word in ('身分確認', '可通行')), 'FORBIDDEN_CLAIM')
    expected = aggregate(inputs, decisions, synthetic_profile=synthetic_profile)
    need(canonical(actual) == canonical(expected), 'REPORT_RECOMPUTE_MISMATCH')
    return {'status': 'VALID_SYNTHETIC_PROJECTION', 'report_sha256': sha(raw),
            'content_sha256': expected['content_sha256'], 'human_approval_verified': False,
            'native_scorer_executed': False, 'formal_acceptance': 'NOT_EVALUATED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--synthetic-profile', choices=[PROFILE])
    args = parser.parse_args(argv)
    try:
        result = check(args.report, args.inputs, args.decisions, synthetic_profile=args.synthetic_profile)
        code = 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'FAIL', 'reason': str(exc), 'formal_acceptance': 'NOT_EVALUATED'}
        code = 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
