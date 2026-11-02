"""TEST-ONLY path/pin binding; scores come exclusively from the real native API."""
import json
from pathlib import Path

from amidst.evaluation import q5_switch_eval as v1
from amidst.evaluation import q5_switch_eval_v2 as scorer


def exercise_case(*, implementation, inputs_path, decisions_path):
    root = Path(inputs_path).parent
    input_raw = Path(inputs_path).read_bytes(); receipt = json.loads(input_raw)
    choices_raw = Path(decisions_path).read_bytes(); choices = json.loads(choices_raw)
    pins = {}
    for role, ref in receipt['files'].items():
        raw = (root / ref['path']).read_bytes()
        assert v1.sha(raw) == ref['sha256']
        pins[role] = v1.sha(raw)  # Hash only: never parse scored_events or a golden report.
    native = json.loads((root / receipt['files']['native_inputs']['path']).read_bytes())
    for name, pin in native['files'].items():
        assert v1.sha((root / name).read_bytes()) == pin
        pins['native:' + name] = pin
    cases = []
    for case in native['cases']:
        artifacts = case['artifacts']
        cases.append({'event_id': case['event_id'], 'session_group': case['session_group'],
            'paths': {('decisions' if role == 'journal' else role): root / ref['path'] for role, ref in artifacts.items()},
            'pins': {('decisions' if role == 'journal' else role): ref['sha256'] for role, ref in artifacts.items()}})
    provenance = {'inputs_sha256': v1.sha(input_raw), 'decisions_sha256': v1.sha(choices_raw), 'file_sha256': pins}
    # The typed seam is confined to explicitly marked synthetic sessions/scripts.
    report = implementation.score_sessions(cases, decisions_raw=v1.canonical(choices['selections']),
        provenance=provenance, synthetic_controls=scorer.SyntheticControls(('CAM_EXT_CAR', 'CAM_EXT_CLEAR'), True))
    return {'implementation_file_sha256': v1.sha(Path(implementation.__file__).read_bytes()),
            'human_approval_verified': False, 'native_scorer_executed': report['native_scorer_executed'],
            'native_report': report, 'observations': {k: report[k] for k in ('events', 'metrics', 'provenance', 'pending_event_count')}}
