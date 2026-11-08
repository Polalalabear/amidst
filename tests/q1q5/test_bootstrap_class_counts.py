"""D139 bootstrap counts: indexed detections only; frozen pins stay unchanged."""
import json
import os
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys

import pytest
from test_api import api_fixture
from amidst.q1q5.api import APIError


def test_counts_include_every_detection_sort_ties_and_keep_existing_pins():
    api, _ = api_fixture()
    run = next(iter(api.runs.values()))
    before = deepcopy((run.bindings.index, run.aliases))
    records = list(run.bindings.index.records)
    # Independent synthetic sequence: repeated observations count independently,
    # not as distinct people; missing frames have no detections.
    for row in records:
        row['detections'] = None
    records[0]['detections'] = [{'class_label': 'person'}, {'class_label': 'car'}]
    records[1]['detections'] = [{'class_label': 'person'}, {'class_label': 'car'}]
    snapshots = deepcopy((run.bindings.index, run.aliases))
    result = api.bootstrap()['runs'][0]
    assert result['detected_class_counts'] == [
        {'class_label': 'car', 'detection_count': 2},
        {'class_label': 'person', 'detection_count': 2}]
    assert result['detection_index_sha256'] == run.bindings.index_sha256
    assert result['supported_classes'] == run.aliases
    assert 'detected_class_counts' not in result['supported_classes']
    assert (run.bindings.index, run.aliases) == snapshots
    records[1]['detections'].append({'class_label': 'person'})
    assert api.bootstrap()['runs'][0]['detected_class_counts'][0] == {'class_label': 'person', 'detection_count': 3}
    assert before[1] == run.aliases


def test_empty_counts_and_invalid_labels_fail_closed():
    api, _ = api_fixture()
    run = next(iter(api.runs.values()))
    for row in run.bindings.index.records:
        row['detections'] = []
    assert api.bootstrap()['runs'][0]['detected_class_counts'] == []
    run.bindings.index.records[0]['detections'] = [{'class_label': 'gt_private'}]
    with pytest.raises(APIError) as exc:
        api.bootstrap()
    assert exc.value.status == 409


def test_count_path_does_not_read_or_publish_private_record_fields():
    api, _ = api_fixture()
    run = next(iter(api.runs.values()))
    class GuardedRecord(dict):
        def __getitem__(self, key):
            assert key == 'detections', 'counting must not read private fields'
            return super().__getitem__(key)
    records = tuple(GuardedRecord(detections=[{'class_label': 'person'}],
                                  gt_private='SECRET', script='SECRET', visibility='SECRET', depth='SECRET')
                    for _ in range(3))
    api.runs = {key: replace(value, bindings=replace(value.bindings, index=replace(value.bindings.index, records=records)))
                for key, value in api.runs.items()}
    counts = api.bootstrap()['runs'][0]['detected_class_counts']
    assert counts == [{'class_label': 'person', 'detection_count': 3}]
    assert not any(word in json.dumps(counts) for word in ['gt_private', 'SECRET', 'script', 'visibility', 'depth'])


@pytest.fixture(scope='module')
def recorded_demo(tmp_path_factory):
    # Explicit opt-in for the locally owned recorded demo; no legacy path fallback.
    if 'AMIDST_DEMO_HOME' not in os.environ:
        pytest.skip('requires transferred demo-owned-v1; pure contract tests run everywhere')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root/'scripts'))
    from demo_dependency_config import configuration, owned_path
    from serve_demo_integration import Demo
    config, owned = configuration()
    return Demo(owned_path(owned, config['artifacts_root']), owned_path(owned, config['p1_bundle']),
                tmp_path_factory.mktemp('owned-counts')/'state',
                job_path=owned_path(owned, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'], owned_root=owned)


@pytest.mark.parametrize('label', ['B-05', 'A4-1', 'B4-1'])
def test_three_recorded_runs_counts_match_all_indexed_detections(recorded_demo, label):
    api = recorded_demo.api
    run = next(r for r in api.runs.values() if r.title.startswith(label+' '))
    pins = deepcopy((run.bindings.index.manifest, run.aliases))
    row = next(r for r in api.bootstrap()['runs'] if r['run_id'] == run.bindings.index.manifest['run_id'])
    expected = Counter(d['class_label'] for record in run.bindings.index.records for d in record['detections'] or [])
    actual = row['detected_class_counts']
    assert {x['class_label']:x['detection_count'] for x in actual} == expected
    assert sum(x['detection_count'] for x in actual) == sum(len(r['detections'] or []) for r in run.bindings.index.records)
    assert all(x['class_label'] in row['supported_classes']['class_labels'] and type(x['detection_count']) is int and x['detection_count'] > 0 for x in actual)
    assert actual == sorted(actual, key=lambda x: (-x['detection_count'], x['class_label']))
    assert row['detection_index_sha256'] == run.bindings.index_sha256
    assert (run.bindings.index.manifest, run.aliases) == pins
    assert all(set(x) == {'class_label', 'detection_count'} for x in actual)
