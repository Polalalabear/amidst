"""評分端；與推論隔離。Aggregate verified v2 reports without a formal wire claim.

The caller supplies explicit pinned artifacts and, only for synthetic controls,
an in-memory scorer seam. This module never reads the projection's scored rows.
"""
from copy import deepcopy

from amidst.evaluation import q5_switch_eval as v1
from amidst.evaluation import q5_switch_eval_v2 as scorer


def summarize(reports, *, provenance):
    """Group actual native scores; unscored events enter no score denominator."""
    events, grouped, unscored = [], {}, {}
    for group, report in reports:
        v1.require(v1.digest(report, 'output_sha256') == report.get('output_sha256'), 'Native report hash mismatch')
        limited = report['cutoff_us'] is not None
        for row in report['events']:
            bucket = ('NOT_SCORED_PENDING_DECISION' if row['reason'] == 'NOT_SCORED_PENDING_DECISION'
                      else 'NOT_SCORED:' + str(row['reason'])) if row['match'] is None else (
                          'MEASURED_PARTIAL_ENDED_BY_LIMIT' if limited else 'COMPLETE')
            if row['overlap']:
                bucket += '/' + scorer.OVERLAP_LABEL
            item = {**deepcopy(row), 'session_id': group, 'matched': row['match'], 'bucket': bucket,
                    'entry_kind': 'OVERLAP' if row['overlap'] else 'BLIND' if row['expected_action'] == 'SWITCH' else 'NONE',
                    'run_id': report['run_id'], 'clock_id': report['clock_id'],
                    'response_file_sha256': report['response_file_sha256'],
                    'decisions_file_sha256': report['decisions_file_sha256'],
                    'provenance': provenance}
            events.append(item)
            if row['match'] is None:
                unscored.setdefault(bucket, []).append(row['event_id'])
                continue
            for category in ('ALL', row['event_class']):
                grouped.setdefault(bucket + '/' + category, []).append(row['match'])
    metrics = {key: {'matched': sum(values), 'total': len(values), 'ratio': sum(values) / len(values),
                     'provenance': provenance} for key, values in sorted(grouped.items())}
    result = {'status': 'ENGINEERING_AGGREGATE_NOT_FORMAL_ACCEPTANCE', 'events': events, 'metrics': metrics,
              'provenance': provenance, 'event_count': len(events),
              'scored_event_count': sum(row['matched'] is not None for row in events),
              'pending_event_count': sum(row['matched'] is None for row in events), 'not_scored': unscored,
              'has_unscored_events': bool(unscored), 'human_approval_verified': False,
              'native_scorer_executed': True, 'sessions': [report for _, report in reports],
              'limits': ['STANDARD/main, OVERLAP and LIMIT groups keep separate denominators.',
                         'Unscored events are listed by group and are never converted to zero.',
                         'No production receipt/report wire is adopted by this engineering summary.']}
    result['content_sha256'] = v1.sha(v1.canonical(result))
    return result


def score_sessions(cases, *, decisions_raw, provenance, synthetic_controls=None):
    """Freeze/check outputs through the real scorer before each private script read."""
    reports = []
    seen = set()
    for case in cases:
        source = (case['pins']['response'], case['event_id'])
        v1.require(source not in seen, 'Duplicate source event across sessions')
        seen.add(source)
        report = scorer.score_files(case['paths'], case['pins'], decisions_raw=decisions_raw,
                                    synthetic_controls=synthetic_controls)
        v1.require([row['event_id'] for row in report['events']] == [case['event_id']], 'Native event binding mismatch')
        reports.append((case['session_group'], report))
    return summarize(reports, provenance=provenance)
