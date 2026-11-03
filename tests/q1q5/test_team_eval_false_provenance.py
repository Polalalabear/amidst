"""#293 exact false-provenance exception, with explicit SYNTHETIC pin overrides."""
import copy

import pytest

from amidst.q1q5 import team_eval_pack as pack


NAME = 'SYNTHETIC/frozen.json'


def document():
    return {'fixture_role': 'SYNTHETIC_ONLY', 'response': {'provenance': {'gt_read': False}}}


def selected(monkeypatch, raw, name=NAME):
    pins = {name: pack.sha(raw)}
    monkeypatch.setattr(pack, 'TEAM_EVAL_SOURCE_PINS', pins)
    return pins


def test_pinned_false_only_has_scan_view_not_payload_mutation(monkeypatch):
    raw = pack.encode(document()); pins = selected(monkeypatch, raw)
    assert pack.scan_payload(raw, profile=pack.BASELINE, source_pins=pins) == raw
    assert 'gt_read' not in pack.parse(pack.frozen_scan_view(raw, pins))['response']['provenance']
    assert pack.parse(raw)['response']['provenance']['gt_read'] is False
    for profile in (None, pack.SYNTHETIC):
        with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
            pack.scan_payload(raw, profile=profile, source_pins=pins)


@pytest.mark.parametrize('value', [True, 'false', 0, None])
def test_wrong_value_rejected_even_with_test_pin(monkeypatch, value):
    doc = document(); doc['response']['provenance']['gt_read'] = value
    raw = pack.encode(doc); pins = selected(monkeypatch, raw)
    with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
        pack.scan_payload(raw, profile=pack.BASELINE, source_pins=pins)


@pytest.mark.parametrize('mutation', ['wrong-path', 'extra-key', 'string-bait'])
def test_other_forbidden_content_survives_scan_view(monkeypatch, mutation):
    doc = document()
    if mutation == 'wrong-path':
        del doc['response']['provenance']['gt_read']; doc['gt_read'] = False
    elif mutation == 'extra-key':
        doc['response']['provenance']['gt_actor_id'] = 'SYNTHETIC'
    else:
        doc['note'] = 'SYNTHETIC gt_read: false'
    raw = pack.encode(doc); pins = selected(monkeypatch, raw)
    with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
        pack.scan_payload(raw, profile=pack.BASELINE, source_pins=pins)


def test_unpinned_bytes_and_wrong_source_name_rejected(monkeypatch):
    raw = pack.encode(document()); pins = selected(monkeypatch, raw)
    for data, claimed in ((raw + b' ', pins), (raw, {}), (raw, {'SYNTHETIC/wrong.json': pack.sha(raw)})):
        with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
            pack.scan_payload(data, profile=pack.BASELINE, source_pins=claimed)


def test_collection_preserves_original_whitespace_and_requires_each_pin(monkeypatch):
    a = b' \n' + pack.encode(document()) + b'\n'
    doc = copy.deepcopy(document()); doc['case'] = 'SYNTHETIC B'
    b = pack.encode(doc)
    pins = {'SYNTHETIC/a.json': pack.sha(a), 'SYNTHETIC/b.json': pack.sha(b)}
    monkeypatch.setattr(pack, 'TEAM_EVAL_SOURCE_PINS', pins)
    raw = b'[' + a + b',' + b + b']\n'
    assert pack.scan_payload(raw, profile=pack.BASELINE, source_pins=pins) == raw
    for changed in (pack.encode(pack.parse(raw)), b'[' + a + b',' + a + b']\n', raw.replace(b'SYNTHETIC B', b'SYNTHETIC X')):
        with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
            pack.scan_payload(changed, profile=pack.BASELINE, source_pins=pins)
