"""Producer-to-safe boundary for complete eight-camera RGB; indexer never reads plans."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.clock_mapping import ClockMapping, _content_hash
from r004_4actor_common import CATALOG_SHA, SOURCE_SHA
from render_r004_d124 import json_bytes, no_symlink_components, png_safe, require_space, sha

CAMERAS = ['CAM_BRANCH', 'CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR',
           'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE']


def put(path, raw):
    no_symlink_components(path)
    require_space(path.parent, len(raw) + 65536)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--artifacts-root', type=Path, required=True)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--evidence-root', type=Path, required=True)
    a = p.parse_args()
    art = a.artifacts_root.resolve()
    assert a.data_root.resolve().parent == art / 'data'
    assert a.data_root.name.startswith('r004-4actor-natural-walk-eightcam-')
    assert json.loads((a.evidence_root / 'RENDER_FULL_COMPLETE.json').read_text())['status'] == 'PASS'
    root = a.data_root / 'bundle/safe'
    assert not root.exists(), 'new safe bundle only; never overwrite an existing index'
    catalog = art / 'data/r004-build-v2-20261021/safe_static/cameras.json'
    assert sha(catalog) == CATALOG_SHA
    reuse = json.loads((a.evidence_root / 'REUSE_PROOF.json').read_text())
    assert reuse['status'] == 'PASS' and not reuse['old_index_records_reused']
    reused = {tuple(x['key']): x for x in reuse['cameras']}
    inventory, run_refs = {}, []
    baseline = art / 'data/r004-4actor-v22-20261110/bundle/safe/config'
    for label, count in [('A4-1', 250), ('B4-1', 210)]:
        run_id = a.data_root.name + '-' + label.lower()
        clock_id = 'clock:' + run_id
        frames = []
        for cam in CAMERAS:
            folder = a.data_root / label / cam
            lock = json.loads((folder / 'RENDER_LOCK.json').read_text())
            receipt = json.loads((folder / 'render_receipt.json').read_text())
            assert lock['source_sha256'] == SOURCE_SHA and lock['catalog_sha256'] == CATALOG_SHA
            assert lock['label'] == label and lock['camera'] == cam and lock['gait_profile'] == 'walk'
            assert lock['gait_code_sha256'] == sha(a.repo / 'scripts/r004_natural_walk.py')
            assert lock['fps'] == 5 and lock['start_s'] == 0 and lock['duration_s'] == count / 5
            assert not receipt['surface_intersections'] and receipt['completed_render_frames'] == count
            assert not receipt['source_blend_saved'] and not receipt['camera_matrix_changed']
            if (label, cam) in reused:
                proof = reused[label, cam]
                assert sha(folder / 'RENDER_LOCK.json') == proof['lock_sha256']
                assert sha(folder / 'render_receipt.json') == proof['receipt_sha256']
                assert sha(folder / 'frame_manifest.jsonl') == proof['journal_sha256']
            else:
                assert lock['scenario_sha256'] == reuse['scenario_sha256']
                assert lock['producer_code_sha256'] == sha(a.repo / 'scripts/render_r004_natural_walk_sample.py')
            rows = [json.loads(s) for s in (folder / 'frame_manifest.jsonl').read_text().splitlines()]
            assert sorted(r['frame_index'] for r in rows) == list(range(count))
            assert sorted(f.name for f in folder.glob('*.png')) == [f'{n:06d}.png' for n in range(count)]
            for row in rows:
                n = row['frame_index']
                src = folder / f'{n:06d}.png'
                assert not src.is_symlink() and sha(src) == row['sha256']
                assert src.stat().st_size == row['size_bytes'] and row['source_time_us'] == n * 200000
                raw = src.read_bytes()
                sanitized, _ = png_safe(raw)
                # Blender PNG text is stripped at this explicit boundary; producer source stays intact.
                rel = f'rgb/{run_id}/{cam}/{n:06d}.png'
                dst = root / rel
                if sanitized == raw:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.link(src, dst, follow_symlinks=False)
                else:
                    put(dst, sanitized)
                inventory[rel] = sha(dst)
                frames.append({'camera_id': cam, 'frame_index': n, 'source_time_us': n * 200000,
                               'relative_path': rel, 'sha256': inventory[rel]})
        clock = json.loads((a.repo / f'configs/q1q5/clocks/r004_{label[:2].lower()}_v1.json').read_text())
        clock.update(run_id=run_id, clock_id=clock_id)
        clock['content_sha256'] = _content_hash(clock)
        ClockMapping.from_document(clock, expected_run_id=run_id)
        clock_ref = f'clocks/{label}.json'
        put(root / clock_ref, json_bytes(clock))
        inventory[clock_ref] = sha(root / clock_ref)
        run = {'scene_id': 'controlled-l-corridor', 'scene_revision': 'r004',
               'run_id': run_id, 'clock_id': clock_id, 'clock_ref': clock_ref,
               'duration_us': count * 200000, 'fps': 5, 'sample_count_per_camera': count,
               'image_size_px': [960, 540], 'camera_ids': CAMERAS, 'catalog_sha256': CATALOG_SHA,
               'frames': frames}
        descriptor_ref = f'runs/{label}.json'
        put(root / descriptor_ref, json_bytes(run))
        inventory[descriptor_ref] = sha(root / descriptor_ref)
        run_refs.append(descriptor_ref)
        old_cfg = json.loads((baseline / f'{label}.json').read_text())
        keys = ['profile', 'formal_eligible', 'formal_parameters', 'formal_run_allowed',
                'human_approval_verified', 'mode', 'stride_samples', 'index_grid_origin_frame',
                'index_score_floor', 'query_min_score', 'hsv_config', 'parameters', 'seed', 'threads',
                'weights_sha256']
        cfg = {k: old_cfg[k] for k in keys}
        assert cfg['hsv_config']['version'] == 'D131-DEMO-HSV-v1' and cfg['hsv_config']['crop_ratio'] == .5
        cfg.update(scene_id=run['scene_id'], scene_revision='r004', run_id=run_id, clock_id=clock_id,
                   run_descriptor=descriptor_ref, run_descriptor_sha256=inventory[descriptor_ref],
                   clock_sha256=inventory[clock_ref], catalog_sha256=CATALOG_SHA)
        cfg_ref = f'config/{label}.json'
        put(root / cfg_ref, json_bytes(cfg))
        inventory[cfg_ref] = sha(root / cfg_ref)
    for rel, src in [('provenance/camera_catalog.json', catalog),
                     ('provenance/camera_graph_v3_1.json', a.repo / 'configs/q1q5/graphs/r004/camera_graph_v3_1.json')]:
        put(root / rel, src.read_bytes())
        inventory[rel] = sha(root / rel)
    manifest = {'schema': 'amidst.r004-4actor-safe.v1', 'files': inventory, 'runs': run_refs,
                'source_blend_sha256': SOURCE_SHA, 'catalog_sha256': CATALOG_SHA,
                'scope': 'ENGINEERING_DEMO; identity UNCONFIRMED; physical navigation UNKNOWN'}
    put(root / 'SAFE_MANIFEST.json', json_bytes(manifest))
    print('EIGHT_CAMERA_SAFE_PREPARED', len(inventory), sha(root / 'SAFE_MANIFEST.json'))


if __name__ == '__main__':
    main()
