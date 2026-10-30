"""CQ-28 synthetic-only source integrity, return validation and closed release."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from amidst.q1q5.yyin_main_pack import PackError, build_pack, canonical, csv_bytes, sha
from amidst.q1q5.yyin_review_pack import COLUMNS, FILES, IDS, review_payloads
from make_synthetic_yyin_pack_inputs import make as make_main
from make_synthetic_yyin_review_inputs import make as make_review


@pytest.fixture
def sources(tmp_path):
    main = json.loads(make_main(tmp_path / 'SYNTHETIC-main').read_bytes())
    review = json.loads(make_review(tmp_path / 'SYNTHETIC-review').read_bytes())
    return main, review


def test_s1_bound_pack_reproducible_keeps_wire_closed(tmp_path, sources):
    main, review = sources
    first = build_pack(tmp_path / 'SYNTHETIC-a', inputs=main, s1_inputs=review, synthetic_only=True)
    second = build_pack(tmp_path / 'SYNTHETIC-b', inputs=main, s1_inputs=review, synthetic_only=True)
    assert first['zip_sha256'] == second['zip_sha256']
    assert first['phase'] == 'S1_S2_SYNTHETIC' and not first['release_authorized']
    root = Path(first['pack_path'])
    manifest = json.loads((root / 'MANIFEST.json').read_bytes())
    assert len(manifest['editable_files']) == 2 and not manifest['evaluation_eligible']
    assert (root / 's1/確認.csv').read_bytes() == (root / 'templates/s1.csv').read_bytes()
    assert 's1/review.html' in (root / 'START_HERE.html').read_text()
    for i, name in enumerate(FILES):
        assert (root / ('s1/' + IDS[i] + '.svg')).read_bytes() == (Path(review['path']) / name).read_bytes()
    with pytest.raises(PackError, match='CONTRACT_UNSELECTED'):
        build_pack(tmp_path / 'production', inputs=main, s1_inputs=review)
    assert not (tmp_path / 'production').exists()


@pytest.mark.parametrize('mutation', ['receipt_pin', 'image_pin', 'symlink', 'boundary', 'question', 'script', 'external', 'event', 'private'])
def test_review_rejects_unbound_or_unsafe_sources(sources, mutation):
    _, config = sources
    root = Path(config['path']); receipt = root / 'RECEIPT.json'
    doc = json.loads(receipt.read_bytes()); image = root / FILES[0]
    if mutation == 'receipt_pin':
        config['receipt_sha256'] = '0' * 64
    elif mutation == 'image_pin':
        image.write_bytes(image.read_bytes() + b' ')
    elif mutation == 'symlink':
        moved = root / 'original.svg'; image.rename(moved); image.symlink_to(moved)
    elif mutation == 'boundary':
        doc['gt_read'] = True
    elif mutation == 'question':
        doc['questions'][0]['allowed_answers'].append('同意更新')
    else:
        extra = {'script': '<script>alert(1)</script>', 'external': '<image href="https://example.com/x.png"/>',
                 'event': '<rect onclick="alert(1)"/>', 'private': '<text>/Users/private/info</text>'}[mutation]
        image.write_text(image.read_text().replace('</svg>', extra + '</svg>'))
        doc['files'][FILES[0]] = sha(image.read_bytes())
    if mutation not in {'receipt_pin', 'image_pin', 'symlink'}:
        receipt.write_bytes(canonical(doc)); config['receipt_sha256'] = sha(receipt.read_bytes())
    with pytest.raises(PackError):
        review_payloads(config, synthetic_only=True)


@pytest.mark.parametrize('answer,notes,expected', [('A', '', False), ('都不是', '', True), ('看不出來', 'SYNTHETIC 不確定', False), ('', '', True)])
def test_review_return_incomplete_is_not_answer_acceptance(tmp_path, sources, answer, notes, expected):
    main, review = sources
    result = build_pack(tmp_path / 'SYNTHETIC-pack', inputs=main, s1_inputs=review, synthetic_only=True)
    root = Path(result['pack_path'])
    spec = importlib.util.spec_from_file_location('review_verifier', root / 'tools/verify_pack.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    returned = tmp_path / 'returned.csv'
    rows = [dict(zip(COLUMNS, [rid, answer, notes])) for rid in IDS]
    returned.write_bytes(csv_bytes(COLUMNS, rows))
    checked = verifier.check(root, result['manifest_sha256'], s1_returned=returned)
    assert checked['s1']['incomplete_required'] == expected
    assert checked['answers_verified'] is checked['s1']['answers_verified'] is False
    for field, value in [('題號', 'wrong'), ('選項', '核准'), ('備註', '=1+1')]:
        invalid = copy.deepcopy(rows); invalid[0][field] = value
        returned.write_bytes(csv_bytes(COLUMNS, invalid))
        with pytest.raises(ValueError):
            verifier.check(root, result['manifest_sha256'], s1_returned=returned)
