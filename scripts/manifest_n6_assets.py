"""Finalize a checked LOCAL asset pack with relative paths, sizes and SHA-256."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--code-root',type=Path,required=True)
    args = parser.parse_args()
    root = args.assets
    assert not (root/'MANIFEST.json').exists()
    for name in ['character.glb','scene.glb','cameras.catalog.json','cameras.three.json','REVIEW.html',
                 'character_audit.json','export_character.json','export_scene.json',
                 'verification/GLTF_VALIDATION.json','verification/VIEWER_REPORT.json',
                 'verification/GEOMETRY_REPORT.json','verification/RGB_COMPARISON.json']:
        assert (root/name).is_file(),name
    required = ['character_'+clip+'.png' for clip in ('walk','run','idle')]
    cameras = json.loads((root/'cameras.three.json').read_text())['cameras']
    required += ['variant_'+actor+'.png' for actor in ('T','A','B','C')]
    required += [camera['camera_id']+suffix for camera in cameras for suffix in ('.png','_comparison.png')]
    screenshots = []
    for name in required:
        p = root/'verification'/name
        screenshots.append(dict(path=p.relative_to(root).as_posix(),size_bytes=p.stat().st_size,sha256=sha(p)))
    (root/'verification/SCREENSHOT_LIST.json').write_text(json.dumps(dict(schema='amidst.n6-screenshots.v1',
              screenshots=screenshots),indent=2)+'\n')
    rows = []
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink()
        if p.is_file():
            assert not p.name.endswith('.raw.glb'),'Move producer intermediates to scratch before delivery'
            assert not p.name.endswith('.blend') and not p.suffix in ('.mp4','.jsonl','.sqlite')
            rows.append(dict(path=p.relative_to(root).as_posix(),size_bytes=p.stat().st_size,sha256=sha(p)))
    character = json.loads((root/'export_character.json').read_text())
    scene = json.loads((root/'export_scene.json').read_text())
    names = ['audit_n6_character.py','n6_character_rig.py','n6_gait.py','export_n6_live_assets.py',
             'package_n6_gltf.py','verify_n6_geometry.py','verify_n6_assets.mjs','capture_n6_viewer.mjs',
             'compare_n6_rgb.py','manifest_n6_assets.py','n6_viewer/index.html',
             'render_r004_natural_walk_sample.py','r004_natural_walk.py','render_r004_d124.py']
    scripts = {str(Path('scripts')/name):sha(args.code_root/'scripts'/name) for name in names}
    manifest = dict(schema='amidst.n6-live-assets-manifest.v1',date='2026-11-15',
        status='ENGINEERING_DELIVERY_REVIEW_REQUESTED',local_relative_root='data/'+root.name,
        source=dict(blend_path='data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend',
                    blend_sha256=character['source_sha256'],catalog_sha256=character['catalog_sha256']),
        code_base_main_sha=subprocess.check_output(['git','merge-base','HEAD','origin/main'],cwd=args.code_root,text=True).strip(),
        code_branch='codex/feat-n6-live-assets',code_sha256=scripts,
        blender=dict(version=character['blender_version'],build_hash=character['blender_build']),
        export_settings=dict(character=character['exporter'],scene=scene['exporter'],
                             animation_sampling_hz=960,lightmap_size_px=scene['details']['atlas_px'],
                             bake_samples=scene['details']['samples'],bake_engine=scene['details']['engine']),
        coordinate_system=character['coordinate_system'],
        runtime_requirements=dict(material_variants='KHR_materials_variants; see isolated viewer loader',
                                  appearance='Standard KHR_materials_unlit baked baseColor, no second tone map',
                                  irradiance='EXR attached in scene GLB asset.extras.n6Lighting.linearIrradiance.bufferView; UV1'),
        character_size_bytes=(root/'character.glb').stat().st_size,
        scene_size_bytes=(root/'scene.glb').stat().st_size,
        file_count=len(rows),total_size_bytes=sum(r['size_bytes'] for r in rows),
        files=rows,boundary=dict(engineering_demo=True,identity='UNCONFIRMED',physical_navigation='UNKNOWN',
           gt_trajectories_visibility_depth_exported=False,inference_or_index_run=False,
           source_saved_or_copied=False,video_rendered=False,port_8785_touched=False),
        not_verified=['Human acceptance of gait naturalness/appearance',
                      'WASD/Shift workbench integration and system tracking (separate UI owner)',
                      'Continuous articulated clearance / physical safety',
                      'Pixel equality to EEVEE #529 RGB; per-camera differences quantified separately'])
    assert manifest['character_size_bytes']<=20_000_000 and manifest['scene_size_bytes']<=150_000_000
    path = root/'MANIFEST.json'
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(path='data/'+root.name+'/MANIFEST.json',sha256=sha(path),
                         file_count=len(rows),total_size_bytes=manifest['total_size_bytes'],
                         character_size_bytes=manifest['character_size_bytes'],scene_size_bytes=manifest['scene_size_bytes']),indent=2))


if __name__=='__main__':
    main()
