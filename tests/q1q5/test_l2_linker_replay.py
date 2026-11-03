"""SYNTHETIC native-controller tests; no P1 asset copy or live detector/provider."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import socket
import sys

import pytest
from test_q5_controller import fixture, request, seed_id
from amidst.q1q5.linker import LocalLinker
from amidst.q1q5.store import canonical_hash

PATH = Path(__file__).parents[2] / 'scripts/replay_l2_linker_options.py'
SPEC = importlib.util.spec_from_file_location('l2_linker_replay', PATH)
replay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replay
SPEC.loader.exec_module(replay)


def original(b):
    return replay.domain(replay.native_replay(b, request(b), seed_id(b)))


def test_default_executes_real_linker_and_preserves_input(monkeypatch):
    b = fixture({'A': {i: 'STRONG' for i in range(10)}})
    before = deepcopy(b.parameter_set)
    called = []
    step = LocalLinker.step

    def traced(self, row):
        called.append(row['frame_index'])
        return step(self, row)

    monkeypatch.setattr(LocalLinker, 'step', traced)
    old = original(b)
    report, outputs = replay.run_comparison(b, request(b), seed_id(b), old)
    assert called and set(report['variants']) == {'baseline'}
    assert b.parameter_set == before
    assert report['variants']['baseline']['metrics']['linked_pairs'] == 9
    assert report['variants']['baseline']['metrics']['linked_contiguous_runs'] == 1
    assert report['variants']['baseline']['metrics']['on_camera_segments'] == 1
    assert report['current_new_pairs_vs_historical'] == 0
    assert outputs['baseline']['response']['identity_verdict'] == 'UNCONFIRMED'


def test_real_q4_and_controller_execute_search_and_switch_without_network(monkeypatch):
    b = fixture()
    def reject(*args, **kwargs):
        raise AssertionError('NETWORK_FORBIDDEN')
    monkeypatch.setattr(socket, 'socket', reject)
    result = replay.native_replay(b, request(b), seed_id(b))
    assert result.response['status'] == 'COMPLETE'
    assert result.snapshots and result.evidence
    measured, _ = replay.metrics(result.response,
        [json.loads(s) for s in result.decisions_bytes.splitlines()],
        [json.loads(s) for s in result.links_bytes.splitlines()])
    assert measured['searching_entries'] == 1
    assert measured['switch_actions'] == 1
    assert measured['return_actions'] == 0


def test_proposed_sweep_uses_native_fail_closed_guard_not_fabricated_zero_gain():
    b = fixture()
    old = original(b)
    report, outputs = replay.run_comparison(b, request(b), seed_id(b), old, sweep=True)
    assert len(outputs) == 10
    for name, row in report['variants'].items():
        if name == 'baseline':
            continue
        assert row['reason'] == 'PARAMETERS_NOT_APPROVED'
        assert row['status'] == 'PARTIAL'
        assert row['metrics'] is None and row['new_linked_pairs'] is None
        assert row['delta_from_current'] is None and row['approval_promoted'] is False
        assert outputs[name]['decisions'] == outputs[name]['links'] == ''
        assert outputs[name]['response']['timeline'] == []


def test_proposal_does_not_inherit_approval_or_change_original():
    b = fixture(); before = deepcopy(b.parameter_set)
    p = replay.proposed_parameters(b.parameter_set, {'link_min_score': .3, 'link_iou_min': .225})
    assert b.parameter_set == before
    assert p['approval'] == {'status': 'PROPOSED', 'approval_ref': None, 'approved_by': None}
    for row in p['parameters']:
        if row['name'] in {'link_min_score', 'link_iou_min'}:
            assert row['status'] == 'PROPOSED'
    assert canonical_hash(p, exclude=('content_sha256', 'parameter_set_id', 'stats')) == p['content_sha256']
    assert p['content_sha256'] != b.parameter_sha256


@pytest.mark.parametrize('changes', [{}, {'query_min_score': .3}, {'link_min_score': .29},
                                    {'link_min_score': .41}, {'link_iou_min': -.01},
                                    {'link_iou_min': float('nan')}, {'link_min_score': True}])
def test_out_of_scope_options_rejected(changes):
    with pytest.raises(ValueError):
        replay.proposed_parameters(fixture().parameter_set, changes)


def test_return_metric_uses_wire_action_and_excludes_rejected_decisions():
    row = {'state_before': 'SEARCHING', 'state_after': 'RETURNED_TO_ORIGIN',
           'accepted': True, 'executed_action': 'RETURN_TO_ORIGIN'}
    measured, _ = replay.metrics({'timeline': []}, [row, {**row, 'accepted': False}], [])
    assert measured['return_actions'] == 1
    assert measured['searching_entries'] == 0


def test_runs_split_at_gaps_not_every_successful_pair():
    rows = [{'camera_id': 'A', 'local_segment_id': 'one', 'decision': kind,
             'prev_observation_id': f'o{i}', 'next_observation_id': f'o{i+1}'}
            for i, kind in enumerate(['LINKED', 'LINKED', 'NO_MATCH', 'LINKED'])]
    result, pairs = replay.metrics({'timeline': []}, [], rows)
    assert result['linked_pairs'] == len(pairs) == 3
    assert result['linked_contiguous_runs'] == 2


def test_repeated_native_outputs_are_byte_identical_after_contract_timing_exclusion():
    b = fixture(); old = original(b)
    one, first = replay.run_comparison(b, request(b), seed_id(b), old, sweep=True)
    two, second = replay.run_comparison(b, request(b), seed_id(b), old, sweep=True)
    assert replay.raw_json(one) == replay.raw_json(two)
    assert replay.raw_json(first) == replay.raw_json(second)


def test_wrong_or_symlinked_source_rejected(tmp_path):
    root = tmp_path.resolve(); (root / 'MANIFEST.json').write_text('{}')
    with pytest.raises(ValueError, match='SOURCE_MANIFEST_PIN'):
        replay.load_source(root)
    other = root / 'other'; other.write_text('{}')
    (root / 'MANIFEST.json').unlink(); (root / 'MANIFEST.json').symlink_to(other)
    with pytest.raises(ValueError, match='CANONICAL_REGULAR_INPUT_REQUIRED'):
        replay.load_source(root)
