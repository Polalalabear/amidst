"""Focused tests for scripts/capture_agent_payloads.py (issue #643): offline, no key, no real data needed."""
import base64
import io
import json
import os
import socket
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import capture_agent_payloads as cap  # noqa: E402


def _jpeg(width, height) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (width, height), (120, 130, 140)).save(buf, 'JPEG')
    return buf.getvalue()


def _data_url(raw: bytes) -> str:
    return 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()


def test_redact_images_keeps_size_hash_dimensions_and_drops_pixels():
    raw = _jpeg(64, 32)
    body = {'model': 'm', 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'hi'}, {'type': 'image_url', 'image_url': {'url': _data_url(raw)}}]}]}
    red = cap.redact_images(body)
    img = red['messages'][0]['content'][1]['image_url']['url']['_image']
    assert (img['width'], img['height'], img['bytes'], img['sha256']) == (64, 32, len(raw), cap.sha256(raw))
    assert 'base64' not in json.dumps(red)
    assert [i['path'] for i in cap.find_images(red)] == ['$.messages[0].content[1].image_url.url']


def test_scan_forbidden_finds_nested_keys_json_strings_and_local_paths():
    prefix = ''.join(('gt', '_'))
    hits = cap.scan_forbidden({'a': {prefix + 'x': 1}, 'b': [{'identity': 'p'}], 'c': json.dumps({'actor_id': 3}), 'd': '/Users/x/y.png'})
    assert any(h.endswith(prefix + 'x') for h in hits) and any(h.endswith('.identity') for h in hits)
    assert any('actor_id' in h for h in hits) and any(h.endswith(':LOCAL_PATH') for h in hits)
    assert cap.scan_forbidden({'id': 'A1', 'scores': {'n': 1}}) == []


def test_cache_report_measures_shared_prefix_and_threshold():
    sys_msg = 'S' * 5000
    a = {'messages': [{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': 'x one'}]}
    b = {'messages': [{'role': 'system', 'content': sys_msg}, {'role': 'user', 'content': 'x two'}]}
    r = cap.cache_report(a, b)
    assert r['shared_prefix_chars'] >= 5000 and r['cacheable'] is True
    short = cap.cache_report({'messages': [{'role': 'user', 'content': 'abc'}]}, {'messages': [{'role': 'user', 'content': 'abd'}]})
    assert short['cacheable'] is False and short['shared_prefix_chars'] == 2


def test_no_network_blocks_sockets_and_hides_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'real-looking-secret')
    with cap.no_network():
        assert 'OPENAI_API_KEY' not in os.environ
        with pytest.raises(RuntimeError, match='NETWORK_FORBIDDEN'):
            socket.socket().connect(('127.0.0.1', 9))
    assert os.environ['OPENAI_API_KEY'] == 'real-looking-secret'


def test_capture_live_uses_real_builders_and_never_stores_pixels(tmp_path):
    from PIL import Image
    img_dir = tmp_path / 'data' / 'img'
    img_dir.mkdir(parents=True)
    Image.new('RGB', (1200, 540), (90, 100, 110)).save(img_dir / 'x_combined.jpg', 'JPEG')
    with cap.no_network():
        [rec] = cap.capture_live(tmp_path)
    assert rec['n_images'] == 2 and rec['model'] == 'gpt-6.1-sol' and rec['forbidden_field_hits'] == []
    assert [(i['width'], i['height']) for i in rec['images']][1] == (960, 540)
    assert 'base64' not in json.dumps(rec) and 'Authorization' in rec['request_header_names']
    assert 'capture-only-placeholder' not in json.dumps(rec)


def test_capture_q5_fixture_builds_gateway_body_offline_and_writes_sha256sums(tmp_path):
    with cap.no_network():
        recs = cap.capture_q5_fixture()
    assert [r['name'] for r in recs] == ['q5_fixture_round1', 'q5_fixture_round2']
    r1 = recs[0]
    assert r1['roles'] == ['system', 'user'] and r1['n_images'] == 0 and r1['max_completion_tokens'] == 256
    assert r1['options_sent_on_wire'] == ['max_output_tokens'] and r1['forbidden_field_hits'] == []
    assert r1['cache_vs_round2']['shared_prefix_chars'] > 0
    files = cap.write_evidence(tmp_path / 'ev', recs)
    sums = (tmp_path / 'ev' / 'SHA256SUMS').read_text().splitlines()
    assert len(sums) == 2 and files[-1].name == 'SHA256SUMS'
    assert all(cap.sha256((tmp_path / 'ev' / line.split('  ')[1]).read_bytes()) == line.split('  ')[0] for line in sums)
