"""SOURCE-time event adapters for bounded policy comparisons, never image inference.

BACKEND_FLAGS uses the existing RULE_ONLY kernel. AGENT_DECISIONS uses the
existing sequential Agent kernel. This module replays their frozen results;
it cannot invent observations, change candidates, or authorize a camera cut.
"""
from copy import deepcopy
import hashlib
import json
from amidst.q1q5.store import canonical_hash, _safe_content


class EventModeError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise EventModeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def event_flags(response, *, lost_after_us):
    """No formal default. A recovery exactly at the deadline cancels LOST.

    Timer starts at the first missing SOURCE interval after an observation.
    A LOST event is emitted once per continuous unsupported interval. It is a
    support-loss notification, never a conclusion that a person is absent.
    """
    need(type(lost_after_us) is int and lost_after_us > 0, 'Explicit positive lost_after_us required')
    need(response.get('schema_version') == 'q-demo.q2-response.v1', 'Q2 response required')
    need(response.get('output_sha256') == canonical_hash(response, exclude=('output_sha256', 'stats')), 'Response hash mismatch')
    need(response.get('identity_verdict') == 'UNCONFIRMED' and response.get('provenance', {}).get('gt_read') is False, 'Inference boundary')
    _safe_content(response)
    flags = []
    camera = None
    missing_since = None
    notified = False
    last_end = None

    def emit(kind, timestamp, shown, *, previous=None, observation_ids=()):
        flag = {'type': kind, 'timestamp_us': timestamp, 'camera_id': shown,
                'previous_camera_id': previous, 'switch': kind == 'FOUND' and shown != previous,
                'observation_ids': list(observation_ids), 'source_output_sha256': response['output_sha256'],
                'identity_verdict': 'UNCONFIRMED', 'gt_read': False,
                'reason': 'OBSERVATION_SUPPORT_RECOVERED' if kind == 'FOUND' else 'OBSERVATION_SUPPORT_NOT_RECOVERED',
                'candidate_scope': 'BOUNDED_KERNEL_CANDIDATES', 'absence_verdict': 'UNKNOWN'}
        flag['content_sha256'] = canonical_hash(flag)
        flags.append(flag)

    for segment in response['timeline']:
        interval = segment.get('range_us')
        need(isinstance(interval, list) and len(interval) == 2 and all(type(x) is int for x in interval), 'Invalid SOURCE range')
        left, right = interval
        need(0 <= left < right and (last_end is None or last_end == left), 'Non-contiguous SOURCE timeline')
        last_end = right
        if segment['kind'] == 'ON_CAMERA':
            shown = segment.get('camera_id')
            ids = segment.get('observation_ids')
            need(isinstance(shown, str) and shown and isinstance(ids, list) and ids and all(isinstance(x, str) and x for x in ids), 'Observed segment lacks references')
            if camera is not None and (missing_since is not None or shown != camera):
                emit('FOUND', left, shown, previous=camera, observation_ids=ids[:1])
            camera = shown
            missing_since = None
            notified = False
        else:
            need(segment['kind'] == 'GAP', 'Unsupported timeline kind')
            if camera is None:
                continue  # no chosen seed yet: no claim of having lost a target
            if missing_since is None:
                missing_since = left
            deadline = missing_since + lost_after_us
            if not notified and deadline < right:
                emit('LOST', deadline, camera)
                notified = True
    return flags


def record_mode(mode, request, result, *, selected_seed, lost_after_us, trace=None):
    need(mode in {'BACKEND_FLAGS', 'AGENT_DECISIONS'}, 'Unknown comparison mode')
    expected = 'RULE_ONLY' if mode == 'BACKEND_FLAGS' else 'AGENT_SEQUENTIAL'
    need(request.get('switch_mode') == expected, 'Mode/kernel mismatch')
    response = result.response
    need(response['decisions_sha256'] == digest(result.decisions_bytes) and response['links_sha256'] == digest(result.links_bytes), 'Journal hash mismatch')
    decisions = [json.loads(line) for line in result.decisions_bytes.splitlines()]
    for row in decisions:
        need(row['session_id'] == response['session_id'] and row['content_sha256'] == canonical_hash(row, exclude=('content_sha256', 'stats')), 'Decision hash/scope mismatch')
    if trace is not None:
        need(trace.get('session_id') == response['session_id'] and trace.get('content_sha256') == canonical_hash(trace, exclude=('content_sha256',)), 'Trace pin mismatch')
    calls = len(trace['events']) if trace is not None else sum(len(row.get('llm_calls', [])) for row in decisions)
    if mode == 'BACKEND_FLAGS':
        need(calls == 0 and not response['agent_attempted'] and not response['agent_used'], 'Backend mode invoked Agent')
    flags = event_flags(response, lost_after_us=lost_after_us)
    clean_request = {k: deepcopy(v) for k, v in request.items() if k != 'session_ref'}
    row = {'mode': mode, 'request': clean_request, 'selected_seed': selected_seed,
           'response': deepcopy(response), 'decisions_jsonl': result.decisions_bytes.decode(),
           'links_jsonl': result.links_bytes.decode(), 'flags': flags,
           'metrics': {'provider_calls': calls, 'evidence_queries': len(result.evidence),
                       'switches': sum(x['switch'] for x in flags), 'lost_notifications': sum(x['type'] == 'LOST' for x in flags),
                       'fallback_used': response['fallback_used']}}
    row['content_sha256'] = canonical_hash(row)
    return row


def compare_modes(backend, agent, *, lost_after_us, source_kind):
    need(source_kind in {'SYNTHETIC', 'PILOT', 'RECORDED'}, 'Explicit engineering source required')
    for row, mode in [(backend, 'BACKEND_FLAGS'), (agent, 'AGENT_DECISIONS')]:
        need(row['mode'] == mode and row['content_sha256'] == canonical_hash(row, exclude=('content_sha256',)), 'Mode recording hash mismatch')
        need(row['flags'] == event_flags(row['response'], lost_after_us=lost_after_us), 'Flag policy mismatch')
    normalize = lambda q: {k: v for k, v in q.items() if k != 'switch_mode'}
    need(normalize(backend['request']) == normalize(agent['request']) and backend['selected_seed'] == agent['selected_seed'], 'Different queries/seeds')
    need(backend['response']['resolved_scope'] == agent['response']['resolved_scope'], 'Different source bindings')
    report = {'schema_version': 'q-demo.event-mode-comparison.v1', 'source_kind': source_kind,
              'counts_for_acceptance': False, 'identity_verdict': 'UNCONFIRMED', 'gt_read': False,
              'lost_after_us': lost_after_us, 'threshold_status': 'EXPERIMENT_ONLY_NOT_APPROVED',
              'scope': deepcopy(backend['response']['resolved_scope']),
              'modes': [deepcopy(backend), deepcopy(agent)], 'accuracy': None}
    report['content_sha256'] = canonical_hash(report)
    return report
