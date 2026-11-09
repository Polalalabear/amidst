"""Synthetic selected-scene alias and bootstrap projection checks."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_api import api_fixture
from test_q1_search import aliases, fixture, request, search
from amidst.q1q5.query_alias import AliasError, region_aliases, region_catalog, resolve_alias, validate_aliases
from amidst.q1q5.q1_search import SearchError
from amidst.q1q5.store import canonical_hash


def test_config_canonical_classes_and_chinese_aliases():
    config = json.loads((Path(__file__).resolve().parents[2] / 'configs/q1q5/class_alias_v1.json').read_text())
    assert resolve_alias('筆電', config['aliases'], config['class_labels']) == 'laptop'
    assert canonical_hash(config, exclude=('content_sha256', 'stats')) == config['content_sha256']
    assert all(any(v == label and any('\u3400' <= c <= '\u9fff' for c in k) for k, v in config['aliases'].items()) for label in config['class_labels'])


@pytest.mark.parametrize('value', ['101教室', '101 教室', 'R101', 'r101'])
def test_explicit_regions_and_selected_graph(value):
    assert resolve_alias(value, region_aliases(), ['R101'], allow_unavailable=True) == 'R101'
    with pytest.raises(AliasError, match='ALIAS_TARGET_UNKNOWN'):
        resolve_alias(value, region_aliases(), ['SYN_ROOM'], allow_unavailable=True)


@pytest.mark.parametrize('value', ['不存在', ' 101教室', '101  教室'])
def test_unknown_never_guessed(value):
    with pytest.raises(AliasError, match='ALIAS_UNKNOWN'):
        resolve_alias(value, region_aliases(), ['R101'], allow_unavailable=True)


@pytest.mark.parametrize('aliases,code', [({'X':'a','x':'b'}, 'ALIAS_CONFLICT'), ({'a':'b'}, 'ALIAS_CONFLICT'), ({'字':'missing'}, 'ALIAS_TARGET_UNKNOWN')])
def test_bad_alias_config_fails_closed(aliases, code):
    with pytest.raises(AliasError, match=code):
        validate_aliases(aliases, ['a', 'b'])


def test_q1_uses_alias_validator_and_preserves_unknown_class_status():
    index = fixture(); config = aliases(index)
    config['aliases']['汽車'] = 'car'
    config['content_sha256'] = canonical_hash(config, exclude=('content_sha256', 'stats'))
    req = request(); req['condition']['class_label'] = '汽車'
    result = search(req, index=index, aliases=config, expected_aliases_sha256=config['content_sha256'])
    assert result['normalized_condition']['class_label'] == 'car'
    req['condition']['class_label'] = '不存在'
    assert search(req)['reason'] == 'CLASS_NOT_IN_CLASS_MAP'
    config['aliases']['CAR'] = 'person'
    config['content_sha256'] = canonical_hash(config, exclude=('content_sha256', 'stats'))
    with pytest.raises(SearchError) as error:
        search(index=index, aliases=config, expected_aliases_sha256=config['content_sha256'])
    assert error.value.code == 'ALIAS_CONFLICT'


def test_bootstrap_catalog_matches_selected_graph_and_preserves_old_fields():
    api, run = api_fixture()
    row = api.bootstrap()['runs'][0]
    graph = run.bindings.graphs.region
    assert row['region_catalog'] == {'scene_id': row['scene_id'], 'scene_revision': row['scene_revision'],
        'region_graph_sha256': row['region_graph_sha256'],
        'regions': [{'region_id': r['region_id'], 'label': r['region_id']} for r in graph['regions']]}
    assert row['supported_classes'] == run.aliases
    assert row['camera_ids'] == ['A', 'B']
    assert set(row['region_catalog']['regions'][0]) == {'region_id', 'label'}
    api.runs[next(iter(api.runs))] = replace(run, bindings=replace(run.bindings, graphs=None))
    assert api.bootstrap()['runs'][0]['region_catalog'] is None


@pytest.mark.parametrize('field,value', [('scene_id','OTHER_SCENE'), ('scene_revision','OTHER_REV'), ('content_sha256','0'*64)])
def test_bootstrap_rejects_changed_scene_or_graph_pin(field,value):
    api, run = api_fixture()
    graph = deepcopy(run.bindings.graphs.region)
    graph[field] = value
    altered = replace(run, bindings=replace(run.bindings, graphs=SimpleNamespace(region=graph)))
    with pytest.raises(AliasError, match='REGION_CATALOG_MISMATCH'):
        region_catalog(altered)
