"""Reuse only unchanged #527 B4 RGB; never read or reuse old detection records."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def person(p):
    return ast.dump(next(n for n in ast.parse(p.read_text()).body
                         if isinstance(n, ast.ClassDef) and n.name == 'Person'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--artifacts-root', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    art = a.artifacts_root.resolve()
    frozen = art / 'evidence/codex-516-natural-walk-full-20261114'
    manifest = frozen / 'FULL_MANIFEST.json'
    assert sha(manifest) == '65f1824bec1eed94d7e20a4a49d50d49540bf77c6e85b2d1b7caf24751777b7f'
    inventory = {r['relative_path']: r for r in json.loads(manifest.read_text())['files']}
    old = json.loads((a.repo / 'docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json').read_text())
    new = json.loads(a.scenario.read_text())
    old_run = next(r for r in old['runs'] if r['scenario'] == 'B4-1')
    new_run = next(r for r in new['runs'] if r['scenario'] == 'B4-1')
    for key in ['actors', 'duration_us', 'seed']:
        assert old_run[key] == new_run[key], f'changed B4 scene: {key}'
    for r, s in zip(old['runs'], new['runs']):
        assert next(x for x in r['actors'] if x['actor_id'] == 'T') == next(x for x in s['actors'] if x['actor_id'] == 'T')
    old_code = frozen / 'code/scripts'
    assert sha(old_code / 'r004_natural_walk.py') == sha(a.repo / 'scripts/r004_natural_walk.py')
    assert person(old_code / 'render_r004_natural_walk_sample.py') == person(a.repo / 'scripts/render_r004_natural_walk_sample.py')
    assert a.data_root.resolve().parent == art / 'data'
    assert a.data_root.name.startswith('r004-4actor-natural-walk-eightcam-')
    rows = []
    for cam in old_run['render_camera_ids']:
        src = art / 'data/r004-4actor-natural-walk-20261114/B4-1' / cam
        dst = a.data_root / 'B4-1' / cam
        assert not dst.exists()
        for file in src.iterdir():
            assert file.is_file() and not file.is_symlink()
            inv = inventory[str(file.relative_to(art))]
            assert inv['sha256'] == sha(file) and inv['size_bytes'] == file.stat().st_size
        lock = json.loads((src / 'RENDER_LOCK.json').read_text())
        assert lock['scenario_sha256'] == sha(a.repo / 'docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json')
        assert lock['gait_code_sha256'] == sha(old_code / 'r004_natural_walk.py')
        assert lock['producer_code_sha256'] == sha(old_code / 'render_r004_natural_walk_sample.py')
        assert lock['geometry_sha256'] == sha(a.repo / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')
        assert lock['appearance_config_sha256'] == sha(a.repo / 'configs/q1q5/producers/r004_d124_v1.json')
        assert lock['baseline_producer_sha256'] == sha(a.repo / 'scripts/render_r004_d124.py')
        assert lock['start_s'] == 0 and lock['duration_s'] == 42 and lock['fps'] == 5
        assert lock['gait_profile'] == 'walk' and lock['camera'] == cam
        receipt = json.loads((src / 'render_receipt.json').read_text())
        assert receipt['completed_render_frames'] == 210 and not receipt['surface_intersections']
        dst.mkdir(parents=True)
        for file in src.iterdir():
            if file.suffix == '.png':
                os.link(file, dst / file.name)
            else:
                shutil.copyfile(file, dst / file.name)
        rows.append({'key': ['B4-1', cam], 'original_directory': str(src.relative_to(art)),
                     'new_directory': str(dst.relative_to(art)), 'frame_count': 210,
                     'journal_sha256': sha(dst / 'frame_manifest.jsonl'),
                     'lock_sha256': sha(dst / 'RENDER_LOCK.json'),
                     'receipt_sha256': sha(dst / 'render_receipt.json')})
    result = {'status': 'PASS', 'scenario_sha256': sha(a.scenario),
              'frozen_manifest_sha256': sha(manifest), 'cameras': rows,
              'same_b4_actors_duration_seed': True, 'same_gait_bytes': True,
              'same_person_adapter_ast': True, 'same_render_parameters': True,
              'reused_frame_count': 1050, 'old_index_records_reused': False,
              'method': 'read-only source verification; hardlink PNG; copy original receipts unchanged'}
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print('REUSE_PASS', len(rows), 1050)


if __name__ == '__main__':
    main()
