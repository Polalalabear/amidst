"""Evaluation-only frozen claim sampling and human T/F scoring (#123).

This module has no model, index writer, RGB reader or inference import. Human
answers judge a frozen statement, so F on a negative statement means presence.
PILOT and uncertain reviews never enter the formal confusion table.
"""
from collections import Counter
import hashlib
import json

VERSION = 'q4-presence-eval-v1'


class EvaluationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _require(ok, message):
    if not ok:
        raise EvaluationError(message)


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def decode_jsonl(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    try:
        rows = [json.loads(line, object_pairs_hook=pairs) for line in raw.splitlines()]
        _require(all(isinstance(row, dict) for row in rows), 'Object JSONL required')
        canonical(rows)
        return rows
    except (ValueError, TypeError, UnicodeError) as exc:
        raise EvaluationError('Malformed JSONL') from exc


def select_claims(claims, *, count, seed, claims_sha256):
    """Freeze the rule/seed before labels; equal polarity strata, no replacement.

    Selection consumes complete frozen claims, never human answers. A short pool
    reduces both strata equally and reports the shortfall rather than duplicates.
    """
    _require(type(count) is int and count >= 2 and count % 2 == 0, 'Positive even sample count required')
    _require(isinstance(seed, str) and bool(seed) and _digest(claims_sha256), 'Explicit seed/input hash required')
    pools = {True: [], False: []}
    seen = set()
    for claim in claims:
        _require(isinstance(claim, dict), 'Frozen claim must be an object')
        _require(not any(k in claim for k in ['answer', 'ground_truth', 'actor_id', 'event_script']),
                 'Human answers/GT forbidden in sampling input')
        required = {'run_id', 'clock_id', 'camera_id', 'frame_index', 'rgb_file_sha256',
                    'polarity', 'statement', 'prediction_ref', 'prediction_sha256'}
        _require(isinstance(claim, dict) and required <= claim.keys(), 'Incomplete frozen claim')
        _require(type(claim['polarity']) is bool and type(claim['frame_index']) is int
                 and claim['frame_index'] >= 0, 'Explicit polarity/frame required')
        _require(all(isinstance(claim[k], str) and claim[k] for k in
                     ['run_id', 'clock_id', 'camera_id', 'statement', 'prediction_ref']), 'Missing source/claim')
        _require(_digest(claim['rgb_file_sha256']) and _digest(claim['prediction_sha256']), 'Missing source/output pin')
        key = canonical([claim[k] for k in ['run_id', 'camera_id', 'frame_index', 'statement']])
        _require(key not in seen, 'Duplicate frozen claim')
        seen.add(key)
        pools[claim['polarity']].append((sha(canonical({'seed': seed, 'key': json.loads(key)})), claim))
    n = min(count // 2, len(pools[True]), len(pools[False]))
    _require(n > 0, 'Both system-positive and system-negative pools required')
    chosen = [pair for polarity in [True, False]
              for pair in sorted(pools[polarity], key=lambda pair: pair[0])[:n]]
    selected = [claim for _, claim in sorted(chosen, key=lambda pair: pair[0])]
    plan = {'schema_version': 'q4-sampling-plan.v1', 'scorer_version': VERSION,
            'rule': 'sha256(seed,run,camera,frame,statement); equal polarity; no replacement',
            'seed': seed, 'claims_sha256': claims_sha256, 'requested': count,
            'actual': 2 * n, 'shortfall': count - 2 * n,
            'pool_counts': {'positive': len(pools[True]), 'negative': len(pools[False])},
            'selected': selected}
    plan['output_sha256'] = sha(canonical(plan))
    return plan


def _metric(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None}


def score_reviews(reviews, manifest, *, reviews_sha256, manifest_sha256):
    """Score #147 imported q4-tf-review.v1 rows against trusted manifest scope.

    Caller pins the exact input bytes before decoding. No inferred labels or
    acceptance threshold: only decided, formal human reviews contribute to TP/FN.
    """
    _require(_digest(reviews_sha256) and _digest(manifest_sha256), 'Trusted input hashes required')
    _require(isinstance(manifest, dict) and manifest.get('schema_version') == 'team-review-pack.v1'
             and type(manifest.get('evaluation_eligible')) is bool, 'Invalid review manifest')
    _require(manifest.get('version') in {'v0-pilot', 'v1'}
             and manifest['evaluation_eligible'] == (manifest['version'] == 'v1'), 'Pack version/eligibility conflict')
    samples = manifest.get('samples')
    _require(isinstance(samples, list), 'Manifest sample map missing')
    by_id = {}
    for sample in samples:
        _require(isinstance(sample, dict) and isinstance(sample.get('sample_id'), str)
                 and sample['sample_id'] and sample['sample_id'] not in by_id, 'Invalid/duplicate manifest sample')
        _require(all(isinstance(sample.get(k), str) and sample[k] for k in ['run_id', 'camera_id']), 'Missing manifest scope')
        _require(type(sample.get('frame_index')) is int and sample['frame_index'] >= 0
                 and type(sample.get('system_positive')) is bool, 'Invalid manifest frame/polarity')
        _require(_digest(sample.get('rgb_file_sha256')) and _digest(sample.get('prediction_sha256')), 'Missing manifest pins')
        by_id[sample['sample_id']] = sample
    seen = set()
    counts = Counter()
    cells = Counter({name: 0 for name in ['TP', 'FP', 'TN', 'FN']})
    by_camera = {}
    by_prediction = {}
    valid_records = []
    for row in reviews:
        _require(isinstance(row, dict) and row.get('schema_version') == 'q4-tf-review.v1', 'Invalid review schema')
        sid = row.get('sample_id')
        _require(sid in by_id and sid not in seen, 'Unknown/duplicate reviewed sample')
        seen.add(sid)
        sample = by_id[sid]
        for field in ['run_id', 'camera_id', 'frame_index', 'rgb_file_sha256', 'prediction_sha256', 'system_positive']:
            _require(type(row.get(field)) is type(sample.get(field)) and row.get(field) == sample.get(field),
                     'Frozen claim/source binding mismatch: ' + field)
        _require(type(row.get('system_positive')) is bool, 'Explicit system claim required')
        _require(row.get('frame_ref') == f"frame:{row['run_id']}:{row['camera_id']}:{row['frame_index']}", 'Frame binding mismatch')
        _require(type(row.get('pilot')) is bool and type(row.get('evaluation_eligible')) is bool
                 and row['evaluation_eligible'] == manifest['evaluation_eligible']
                 and row['pilot'] != row['evaluation_eligible'], 'Pilot/formal binding mismatch')
        _require(isinstance(row.get('statement'), str) and bool(row['statement']), 'Frozen statement missing')
        answer = row.get('answer')
        _require(answer in {'T', 'F', '不確定'}, 'Invalid human T/F answer')
        counts['reviewed'] += 1
        counts['system_positive' if row['system_positive'] else 'system_negative'] += 1
        if row['pilot']:
            counts['pilot_excluded'] += 1
            continue
        if answer == '不確定':
            counts['uncertain_excluded'] += 1
            continue
        positive = row['system_positive']
        truth = positive if answer == 'T' else not positive
        cell = ('TP' if truth else 'FP') if positive else ('FN' if truth else 'TN')
        cells[cell] += 1
        key = row['run_id'] + ':' + row['camera_id']
        by_camera.setdefault(key, Counter({x: 0 for x in cells}))[cell] += 1
        by_prediction.setdefault(row['prediction_sha256'], Counter({x: 0 for x in cells}))[cell] += 1
        valid_records.append({'sample_id': sid, 'cell': cell})
    n = sum(cells.values())
    report = {'schema_version': 'q4-presence-eval-report.v1', 'scorer_version': VERSION,
              'reviews_sha256': reviews_sha256, 'manifest_sha256': manifest_sha256,
              'pack_version': manifest.get('version'), 'evaluation_eligible': manifest['evaluation_eligible'],
              'status': 'MEASURED' if n else 'NO_FORMAL_LABELS',
              'sample_count': len(samples), 'reviewed_count': counts['reviewed'],
              'missing_review_count': len(samples) - len(seen),
              'system_claim_counts': {'positive': counts['system_positive'], 'negative': counts['system_negative']},
              'excluded': {'pilot': counts['pilot_excluded'], 'uncertain': counts['uncertain_excluded']},
              'formal_decided_count': n, 'confusion': dict(cells),
              'precision': _metric(cells['TP'], cells['TP'] + cells['FP']),
              'recall': _metric(cells['TP'], cells['TP'] + cells['FN']),
              'accuracy': _metric(cells['TP'] + cells['TN'], n),
              'review_coverage': _metric(counts['reviewed'], len(samples)),
              'formal_decided_coverage': _metric(n, len(samples)),
              'by_camera': {k: dict(v) for k, v in sorted(by_camera.items())},
              'by_prediction_sha256': {k: dict(v) for k, v in sorted(by_prediction.items())},
              'decisions': sorted(valid_records, key=lambda x: x['sample_id']),
              'limits': ['Balanced claim-strata sample metrics; no population reweighting.',
                         'No identity, physical navigation, recall over unsampled time or model acceptance claim.',
                         'No class/color subgroup inferred from natural-language statements.'],
              'acceptance_threshold': None}
    report['output_sha256'] = sha(canonical(report))
    return report
