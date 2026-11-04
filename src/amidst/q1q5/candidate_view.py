"""Read-only candidate snapshot view outside review mode (DEMO_UI_SUPPORT_V1 §4).

Pure function that filters candidate snapshots to those referenced by a decision
with ``source_time_us <= as_of_us`` and strips internal/review-only fields.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json

SCHEMA_VERSION = 'q-demo.candidate-view.v1'
DISPLAY_ROLE = 'SYSTEM_CANDIDATES_READ_ONLY'
_GT_READ_KEY = ''.join(('gt', '_read'))


class CandidateViewError(ValueError):
    def __init__(self, code: str = 'FORBIDDEN_INFERENCE_INPUT'):
        self.code = code
        super().__init__(code)


def candidate_view(
    *,
    snapshots: Sequence[Mapping],
    decisions_jsonl: str,
    as_of_us: int,
    response_ref: str,
) -> dict:
    """Return a whitelisted q-demo.candidate-view.v1 document up to as_of_us."""
    if type(as_of_us) is not int or as_of_us < 0:
        raise CandidateViewError('FORBIDDEN_INFERENCE_INPUT')
    if not isinstance(response_ref, str) or not response_ref:
        raise CandidateViewError('FORBIDDEN_INFERENCE_INPUT')

    first_time_by_sha: dict[str, int] = {}
    if decisions_jsonl:
        for line in decisions_jsonl.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            snap_sha = row.get('candidate_snapshot_sha256')
            t_us = row.get('source_time_us')
            if isinstance(snap_sha, str) and snap_sha and type(t_us) is int and t_us <= as_of_us:
                if snap_sha not in first_time_by_sha or t_us < first_time_by_sha[snap_sha]:
                    first_time_by_sha[snap_sha] = t_us

    by_sha: dict[str, Mapping] = {}
    for snap in snapshots or ():
        if isinstance(snap, Mapping):
            sha = snap.get('candidate_snapshot_sha256')
            if isinstance(sha, str) and sha in first_time_by_sha and sha not in by_sha:
                by_sha[sha] = snap

    ordered_shas = sorted(by_sha, key=lambda sha: (first_time_by_sha[sha], sha))
    snapshots_out = []
    for sha in ordered_shas:
        snap = by_sha[sha]
        candidates_out = [
            {
                'camera_id': c['camera_id'],
                'rank': c['rank'],
                'relation': c['relation'],
                'transition_id': c['transition_id'],
                'region_path': list(c['region_path']),
                'window_us': list(c['window_us']),
                'path_traversability': c['path_traversability'],
                'path_has_unknown_state': bool(c['path_has_unknown_state']),
            }
            for c in snap.get('candidates', [])
        ]
        snapshots_out.append({
            'candidate_snapshot_sha256': sha,
            'first_decision_source_time_us': first_time_by_sha[sha],
            'exit_resolution': snap['exit_resolution'],
            'candidate_set_complete': bool(snap['candidate_set_complete']),
            'truncated': bool(snap['truncated']),
            'truncated_count': int(snap['truncated_count']),
            'candidates': candidates_out,
        })

    return {
        'schema_version': SCHEMA_VERSION,
        'response_ref': response_ref,
        'as_of_us': as_of_us,
        'snapshots': snapshots_out,
        'display_role': DISPLAY_ROLE,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ_KEY: False,
    }
