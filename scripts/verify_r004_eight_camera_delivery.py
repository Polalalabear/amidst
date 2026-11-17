"""Independent byte/grid/clock checks after production; no inference or renderer calls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.clock_mapping import ClockMapping
from render_r004_d124 import png_safe


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--artifacts-root', type=Path, required=True)
    p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--data-root', type=Path, required=True)
    a = p.parse_args()
    art, evidence, data = (p.resolve() for p in [a.artifacts_root, a.evidence_root, a.data_root])
    safe = data / 'bundle/safe'
    full_path = evidence / 'FULL_MANIFEST.json'
    bundle_path = data / 'bundle/BUNDLE_MANIFEST.json'
    full, bundle = (json.loads(p.read_text()) for p in [full_path, bundle_path])
    for m in [full, bundle]:
        assert len(m['files']) == m['file_count']
        assert sum(r['size_bytes'] for r in m['files']) == m['total_bytes']
        assert len({r['relative_path'] for r in m['files']}) == m['file_count']
        for row in m['files']:
            rel = Path(row['relative_path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            file = art / rel
            assert not file.is_symlink() and file.stat().st_size == row['size_bytes'] and sha(file) == row['sha256']
    spec = importlib.util.spec_from_file_location('gates', a.repo / 'tests/q1q5/test_r004_v2_516_gates.py')
    gates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gates)
    assert not gates.validate_manifest(bundle)
    assert not gates.validate_report(json.loads(gates.REPORT.read_text()), json.loads(gates.DRAFT.read_text()))
    assert full['rendered_png_count'] == 3680 and full['movie_count'] == 18
    result = {'status': 'PASS', 'bundle_manifest_sha256': sha(bundle_path),
              'full_manifest_sha256': sha(full_path), 'all_listed_bytes_verified': True,
              'raw_safe_idat_pairs_verified': 0, 'old_records_reused': False, 'runs': {}}
    clocks = []
    for label, count in [('A4-1', 250), ('B4-1', 210)]:
        descriptor = json.loads((safe / f'runs/{label}.json').read_text())
        clock = json.loads((safe / descriptor['clock_ref']).read_text())
        ClockMapping.from_document(clock, expected_run_id=descriptor['run_id'])
        assert descriptor['run_id'] == data.name + '-' + label.lower()
        assert descriptor['clock_id'] == 'clock:' + descriptor['run_id'] == clock['clock_id']
        clocks.append(clock['clock_id'])
        assert set(descriptor['camera_ids']) == set(gates.RENDER_CAMERAS[label + '-v2-4actor'])
        assert len(descriptor['frames']) == 8 * count
        for row in descriptor['frames']:
            n, cam = row['frame_index'], row['camera_id']
            raw = data / label / cam / f'{n:06d}.png'
            sanitized, _ = png_safe(raw.read_bytes())
            assert sanitized == (safe / row['relative_path']).read_bytes()
            result['raw_safe_idat_pairs_verified'] += 1
        receipt = json.loads((safe / f'indexes/{label}/receipt.json').read_text())
        assert receipt['stats'] == {'model_calls': 8 * count, 'frames': 8 * count}
        assert receipt['conformance']['status'] == 'PASS' and receipt['gt_read'] is False
        rows = [json.loads(s) for s in (safe / f'indexes/{label}/detection_index.records.jsonl').read_text().splitlines()]
        assert len(rows) == 8 * count and all(r['frame_ref'].startswith('frame:' + descriptor['run_id'] + ':') for r in rows)
        media = json.loads((evidence / f'FULL_MEDIA_{label}.json').read_text())
        assert media['clock'] == clock and media['display_run_id'] == descriptor['run_id']
        assert len(media['movies']) == 9 and all(m['status'] == 'PASS' and m['decoded_frames'] == count for m in media['movies'])
        result['runs'][label] = {'run_id': descriptor['run_id'], 'clock_id': clock['clock_id'],
                                'frames': 8 * count, 'model_calls': receipt['stats']['model_calls'],
                                'index_sha256': receipt['index_sha256'], 'records_sha256': receipt['records_sha256']}
    assert len(set(clocks)) == 2
    assert sha(art / 'data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend') == bundle['receipt']['source_blend_sha256']
    assert sha(art / 'data/r004-build-v2-20261021/safe_static/cameras.json') == bundle['receipt']['camera_catalog_sha256']
    original = art / 'evidence/codex-516-natural-walk-full-20261114/FULL_MANIFEST.json'
    assert sha(original) == '65f1824bec1eed94d7e20a4a49d50d49540bf77c6e85b2d1b7caf24751777b7f'
    # Verify frozen originals independently, including all prior RGB and movies.
    frozen = json.loads(original.read_text())
    for row in frozen['files']:
        assert sha(art / row['relative_path']) == row['sha256']
    result['all_frozen_527_files_verified'] = len(frozen['files'])
    (evidence / 'DELIVERY_VERIFICATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
