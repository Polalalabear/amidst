"""D81 production boundary tests using synthetic metadata, never formal outputs."""
import hashlib
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from test_api import TOKEN, authorize, q1, q2, run_binding
from test_baseline_runner import fixture_api
from test_q5_controller import seed_id

from amidst.q1q5.api import QAPI
from amidst.q1q5.baseline_runner import export_domain
from amidst.q1q5.engineering_scope import bind_engineering_scope
from amidst.q1q5.graphs import GraphBundle
from amidst.q1q5.store import canonical_hash


def test_q1_q3_scope_has_nullable_key_even_when_tracking_is_unused():
    api, _, _ = fixture_api()
    run = next(iter(api.runs.values()))
    q1_response = api.call('q1_camera_search', q1(run), authorize)
    q3_response = api.call('q3_parse', dict(schema_version='q-demo.q3-parse-request.v1',
        session_ref=TOKEN, text='找人', locale='zh-TW', parser_mode='RULE_ONLY',
        context={'scene_id': run.catalog['scene_id'], 'run_ids': [run.catalog['run_id']],
        'clock_mapping_sha256': run.bindings.clock_sha256}), authorize)
    for response in (q1_response, q3_response):
        assert 'tracking_scope_sha256' in response['resolved_scope']
        assert response['resolved_scope']['tracking_scope_sha256'] is None
        assert response['output_sha256'] == canonical_hash(response, exclude=('output_sha256', 'stats'))


def test_scope_file_byte_pin_reaches_q2_and_every_journal_and_export(tmp_path):
    api, _, _ = fixture_api()
    run = next(iter(api.runs.values()))
    response = api.call('q2_select_seed', {'request': q2(run),
        'selected_observation_id': seed_id(run.bindings)}, authorize)
    assert response['status'] == 'COMPLETE'
    pin = run.bindings.graphs.tracking_scope_sha256
    assert pin == hashlib.sha256(run.bindings.graphs.tracking_scope_bytes).hexdigest()
    assert response['resolved_scope']['tracking_scope_sha256'] == pin
    bundle = next(b for b in api.responses.values() if b['response'] == response)
    assert all(row['input_pins']['tracking_scope_sha256'] == pin
               for row in map(json.loads, bundle['decisions'].splitlines()))
    root = tmp_path / 'domain'
    export_domain(root, q2(run), bundle, run)
    assert (root / 'tracking_scope.json').read_bytes() == run.bindings.graphs.tracking_scope_bytes


def test_production_binding_without_legacy_scope_is_unknown_before_seed_or_calls():
    run = run_binding()
    b = replace(run.bindings, tracking_scope_required=True)
    api = QAPI([replace(run, bindings=b)], max_responses=128, max_media_refs=4096)
    seeds = api.call('q2_seed_candidates', q2(run), authorize)
    response = api.call('q2_session', q2(run), authorize)
    assert seeds['reason'] == response['reason'] == 'TRACKING_SCOPE_MISSING'
    assert seeds['candidates'] == [] and response['status'] == 'UNKNOWN'
    assert response['timeline'] == [] and not response['agent_attempted']
    assert not next(iter(api.responses.values()))['decisions']


def test_declared_missing_scope_is_unknown_and_tampered_scope_is_integrity_error():
    api, _, _ = fixture_api()
    run = next(iter(api.runs.values()))
    b = run.bindings
    missing = replace(b, graphs=GraphBundle(b.graphs.region, b.graphs.camera))
    api = QAPI([replace(run, bindings=missing)], max_responses=128, max_media_refs=4096)
    response = api.call('q2_session', q2(run), authorize)
    assert response['status'] == 'UNKNOWN' and response['reason'] == 'TRACKING_SCOPE_MISSING'
    corrupt = replace(b, graphs=replace(b.graphs, _tracking_scope_bytes=b.graphs.tracking_scope_bytes + b' '))
    api = QAPI([replace(run, bindings=corrupt)], max_responses=128, max_media_refs=4096)
    with pytest.raises(ValueError, match='Malformed runtime metadata'):
        api.call('q2_session', q2(run), authorize)


def test_synthetic_scope_cannot_grant_r004_approval():
    api, _, _ = fixture_api()
    run = next(iter(api.runs.values()))
    r, c = deepcopy(run.bindings.graphs.region), deepcopy(run.bindings.graphs.camera)
    r['scene_revision'] = c['scene_revision'] = 'r004'
    with pytest.raises(ValueError, match='SYNTHETIC'):
        bind_engineering_scope(r, c)
