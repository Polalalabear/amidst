"""Authorized #516 producer. Memory-only actors; immutable blend; RGB-only safe output.

This script reads authored production plans. Never use it as inference input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from render_r004_d124 import (json_bytes, no_symlink_components, png_safe, require,
                              require_space, route_pose, sha)
from r004_4actor_common import CATALOG_SHA, SOURCE_SHA, configure_people

AUTH = 'USER_CHAT_2026-11-10_516_FULL_PIPELINE'


def write(path, raw, exclusive=False):
    no_symlink_components(path)
    require_space(path.parent, len(raw)+32768)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb' if exclusive else 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def main():
    import bpy
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--geometry', type=Path, required=True)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--label', choices=['A4-1','B4-1'], required=True)
    p.add_argument('--authorization-ref', required=True)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--camera', action='append')
    p.add_argument('--indices')
    p.add_argument('--max-new-frames', type=int)
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    require(a.authorization_ref == AUTH, 'EXPLICIT_516_AUTH_REQUIRED')
    source = Path(bpy.data.filepath)
    require(sha(source) == SOURCE_SHA and sha(a.catalog) == CATALOG_SHA, 'SOURCE_PIN_MISMATCH')
    no_symlink_components(a.output)
    require_space(a.output, 32*1024**2)
    doc = json.loads(a.scenario.read_text())
    run = next(r for r in doc['runs'] if r['scenario'] == a.label)
    geometry = json.loads(a.geometry.read_text())
    count = run['duration_us']//200000
    require(count*200000 == run['duration_us'], 'GRID_MISMATCH')
    run_id = 'ctrl-lcorr-s1-'+a.label[:2].lower()+'-5fps-v1-r004-4actor-v22-20261110'
    code_sha = subprocess.check_output(['git','-C',str(a.repo),'rev-parse','HEAD'],text=True).strip()
    root = a.output/a.label
    private = root/'gt_private'
    safe = root/'safe'
    lock = {'authorization_ref':AUTH, 'run_id':run_id, 'source_sha256':SOURCE_SHA, 'catalog_sha256':CATALOG_SHA,
            'scenario_sha256':sha(a.scenario), 'geometry_sha256':sha(a.geometry), 'driver_sha256':sha(Path(__file__)),
            'appearance_code_sha256':sha(a.repo/'scripts/r004_4actor_common.py'), 'code_git_sha':code_sha,
            'camera_ids':run['render_camera_ids'], 'sample_count_per_camera':count, 'fps':5, 'samples':16,
            'source_saved_or_copied':False, 'new_gait_authored':False}
    if root.exists():
        require(a.resume and json.loads((private/'LOCK.json').read_text()) == lock, 'RESUME_LOCK_MISMATCH')
    else:
        require(not a.resume, 'RESUME_REQUIRES_EXISTING_RUN')
        root.mkdir(parents=True)
        write(private/'LOCK.json', json_bytes(lock), True)
        write(private/'authored_plan.json', a.scenario.read_bytes(), True)
        write(private/'render_driver.py', Path(__file__).read_bytes(), True)
        write(private/'appearance_code.py', (a.repo/'scripts/r004_4actor_common.py').read_bytes(), True)
    import fcntl
    handle = (private/'.process.lock').open('a+b')
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
    cameras = {c['camera_id']:c for c in json.loads(a.catalog.read_text())['cameras']}
    people = configure_people(bpy,a.repo)
    scene = bpy.context.scene
    for name in run['render_camera_ids']:
        obj = bpy.data.objects[name]
        require(max(abs(obj.matrix_world[i][j]-cameras[name]['camera_to_world'][i][j]) for i in range(4) for j in range(4))<1e-7, 'CAMERA_CHANGED')
        require(abs(960*obj.data.lens/obj.data.sensor_width-cameras[name]['fx'])<1e-7,'CAMERA_LENS_CHANGED')
    scene.render.resolution_x, scene.render.resolution_y = 960,540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.use_stamp = False
    scene.render.fps = 5
    require(hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'),'SAMPLES_UNAVAILABLE')
    scene.eevee.taa_render_samples = 16
    plans = {}
    for actor in run['actors']:
        points = []
        for w in actor['waypoints']:
            x,y = w['xy']
            heights = [f['top_z_m'] for f in geometry['floors'] if min(f['x_m'])<=x<=max(f['x_m']) and min(f['y_m'])<=y<=max(f['y_m'])]
            points.append({'planned_source_time_us':w['t_us'], 'foot_anchor_world_m':[x,y,w.get('z_m',max(heights) if heights else 0)]})
        plans[actor['actor_id']] = points
    journal = private/'frame_journal.jsonl'
    rows = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
    done = {(r['camera_id'],r['frame_index']):r for r in rows}
    require(len(done)==len(rows),'DUPLICATE_JOURNAL')
    for (cam,i),r in done.items():
        require(cam in run['render_camera_ids'] and 0<=i<count, 'RESUME_GRID_MISMATCH')
        require(sha(safe/f'media/{cam}/{i:06d}.png')==r['safe_sha256'],'RESUME_RGB_HASH_MISMATCH')
    indices = list(range(count)) if a.indices is None else [int(i) for i in a.indices.split(',')]
    require(all(0<=i<count for i in indices) and len(set(indices))==len(indices),'INDICES_INVALID')
    selected = a.camera or run['render_camera_ids']
    require(set(selected)<=set(run['render_camera_ids']),'CAMERA_SCOPE_MISMATCH')
    temporary = private/'render_temp'
    temporary.mkdir(exist_ok=True)
    minimum_free, started, new_frames = require_space(root),time.monotonic(),0
    for cam in selected:
        scene.camera = bpy.data.objects[cam]
        for i in indices:
            if (cam,i) in done:
                continue
            free = require_space(root,32*1024**2)
            minimum_free = min(minimum_free,free)
            poses = {}
            for who,person in people.items():
                route = plans[who]
                present = route[0]['planned_source_time_us']<=i*200000<=route[-1]['planned_source_time_us']
                for obj in person['objects']:
                    obj.hide_render = not present
                if present:
                    pos,yaw = route_pose(route,i*200000,'+X')
                    person['root'].location = pos
                    person['root'].rotation_euler.z = yaw
                    poses[who] = {'foot_xyz':pos,'yaw':yaw}
            bpy.context.view_layer.update()
            fd,name = tempfile.mkstemp(prefix='owned-516-',suffix='.png',dir=temporary)
            os.close(fd)
            raw_path = Path(name)
            try:
                scene.render.filepath = str(raw_path)
                t = time.monotonic()
                bpy.ops.render.render(write_still=True)
                raw,pixels = png_safe(raw_path.read_bytes())
                target = safe/f'media/{cam}/{i:06d}.png'
                write(target,raw,True)
                record = {'camera_id':cam,'frame_index':i,'source_time_us':i*200000, 'safe_sha256':hashlib.sha256(raw).hexdigest(),
                          'pixel_chunks_sha256':pixels,'safe_bytes':len(raw),'elapsed_s':time.monotonic()-t,'poses':poses}
                require_space(root,len(json_bytes(record))+32768)
                with journal.open('ab') as f:
                    f.write(json.dumps(record,sort_keys=True).encode()+b'\n')
                    f.flush()
                    os.fsync(f.fileno())
                done[cam,i] = record
                new_frames += 1
            finally:
                raw_path.unlink(missing_ok=True)
            minimum_free = min(minimum_free,require_space(root))
            write(private/'progress.json',json_bytes({'completed_frames':len(done),'expected_frames':count*len(run['render_camera_ids']), 'minimum_free_bytes':minimum_free,'elapsed_s':time.monotonic()-started}))
            print('FRAME_DONE',a.label,cam,i,len(done),count*len(run['render_camera_ids']),flush=True)
            if a.max_new_frames and new_frames>=a.max_new_frames:
                require(sha(source)==SOURCE_SHA,'SOURCE_CHANGED')
                return
        require(sha(source)==SOURCE_SHA,'SOURCE_CHANGED')
    complete = len(done)==count*len(run['render_camera_ids'])
    if complete:
        inventory = [{'camera_id':cam,'frame_index':i,'relative_path':f'media/{cam}/{i:06d}.png','sha256':done[cam,i]['safe_sha256'],'source_time_us':i*200000}
                     for cam in run['render_camera_ids'] for i in range(count)]
        descriptor = {'scene_id':'controlled-l-corridor','scene_revision':'r004','run_id':run_id,'clock_id':'clock:r004:'+a.label[:2].lower()+':declared-demo:4actor:v22',
                      'fps':5,'duration_us':run['duration_us'],'sample_count_per_camera':count,'image_size_px':[960,540], 'camera_ids':run['render_camera_ids'],
                      'catalog_sha256':CATALOG_SHA,'frames':inventory}
        write(safe/'run.json',json_bytes(descriptor))
    write(private/'completion.json',json_bytes({'complete':complete,'completed_frames':len(done),'expected_frames':count*len(run['render_camera_ids']),
                                               'source_sha256_after':sha(source),'minimum_free_bytes':minimum_free,'elapsed_s_this_invocation':time.monotonic()-started}))
    require(sha(source)==SOURCE_SHA,'SOURCE_CHANGED')
    print('RENDER_COMPLETE',a.label,complete,flush=True)


if __name__ == '__main__':
    main()
