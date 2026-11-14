"""Authorized full A4/B4 5fps viewing production; immutable sources and new outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import signal
import shutil
import subprocess
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--artifacts-root',type=Path,required=True)
    p.add_argument('--stage',choices=['preflight','render'],required=True)
    p.add_argument('--evidence-root',type=Path)
    p.add_argument('--data-root',type=Path)
    a=p.parse_args()
    repo,art=a.repo.resolve(),a.artifacts_root.resolve()
    baseline=art/'evidence/codex-516-v21-feasibility-20261110/delivery-049f3b3c'
    scenario=baseline/'docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json'
    geometry=repo/'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'
    catalog=art/'data/r004-build-v2-20261021/safe_static/cameras.json'
    source=art/'data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend'
    evidence=(a.evidence_root or art/'evidence/codex-516-natural-walk-full-20261114').resolve()
    data=(a.data_root or art/'data/r004-4actor-natural-walk-20261114').resolve()
    assert evidence.parent==art/'evidence' and data.parent==art/'data'
    assert data.name.startswith('r004-4actor-natural-walk-')
    assert not (evidence/'FULL_MANIFEST.json').exists(),'frozen output: choose a new evidence/data root'
    evidence.mkdir(exist_ok=True)
    doc=json.loads(scenario.read_text())
    blender=['/Applications/Blender.app/Contents/MacOS/Blender','--background',str(source),'--python-exit-code','1','--python']
    producer=repo/'scripts/render_r004_natural_walk_sample.py'
    common=['--repo',str(repo),'--baseline-snapshot',str(baseline),'--scenario',str(scenario),
            '--geometry',str(geometry),'--catalog',str(catalog),'--start-s','0','--fps','5']

    def run(cmd,name,frame_dir=None):
        (evidence/f'{name}_command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        begin=time.monotonic()
        with (evidence/f'{name}.log').open('w') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            (evidence/'CURRENT_JOB.json').write_text(json.dumps({'stage':name,'pid':child.pid,'command':cmd},indent=2)+'\n')
            try:
                while child.poll() is None:
                    time.sleep(10)
                    frames=len(list(frame_dir.glob('*.png'))) if frame_dir else None
                    print(json.dumps({'stage':name,'completed_frames':frames,'elapsed_s':round(time.monotonic()-begin,1)}),flush=True)
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
        if child.returncode:
            print((evidence/f'{name}.log').read_text()[-5000:],flush=True)
            raise RuntimeError(f'{name} exit {child.returncode}')
        print(json.dumps({'stage':name,'status':'PASS','elapsed_s':round(time.monotonic()-begin,2)}),flush=True)

    if a.stage=='preflight':
        checker=['python','-B',str(repo/'scripts/design/check_actor_clearance.py'),str(scenario),'--out',str(evidence/'CLEARANCE_FULL.json')]
        # The caller's existing interpreter, never a new environment.
        import sys
        checker[0]=sys.executable
        run(checker,'clearance')
        shutil.copyfile(art/'evidence/codex-516-v21-feasibility-20261110/occlusion_faces.json',evidence/'occlusion_faces.json')
        endpoint=repo/'scripts/audit_r004_natural_walk_endpoints.py'
        run(blender+[str(endpoint),'--','--repo',str(repo),'--scenario',str(scenario),
                     '--baseline-snapshot',str(baseline),'--geometry',str(geometry),
                     '--out',str(evidence/'ENDPOINTS_FULL.json'),'--check-recording-end'],'endpoints')
        for scene in doc['runs']:
            label=scene['scenario']
            out=evidence/f'{label}-probe'
            run(blender+[str(producer),'--']+common+['--label',label,'--camera','CAM_W1',
                '--duration-s',str(scene['duration_us']/1e6),'--output',str(out),'--probe-only'],label+'_mesh_full')
        results={'status':'PASS','fps':5,'source_scenario_unchanged':True,
                 'clearance':'CLEARANCE_FULL.json','endpoints':'ENDPOINTS_FULL.json',
                 'mesh_probe_files':[f"{r['scenario']}-probe/probe.json" for r in doc['runs']]}
        (evidence/'PREFLIGHT_PASS.json').write_text(json.dumps(results,indent=2)+'\n')
        return
    assert json.loads((evidence/'PREFLIGHT_PASS.json').read_text())['status']=='PASS'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for scene in doc['runs']:
        check=json.loads((evidence/f"{scene['scenario']}-probe/probe.json").read_text())
        assert check['gait_code_sha256']==digest(repo/'scripts/r004_natural_walk.py')
        assert check['producer_code_sha256']==digest(producer)
        assert check['frames_checked']==scene['duration_us']//200000 and not check['surface_intersections']
    ends=json.loads((evidence/'ENDPOINTS_FULL.json').read_text())
    assert len(ends['endpoints'])==12 and all(r['status']=='PASS' for r in ends['endpoints'])
    assert ends['gait_code_sha256']==digest(repo/'scripts/r004_natural_walk.py')
    assert ends['pose_producer_sha256']==digest(producer)
    (evidence/'df_before_full_render.txt').write_text(subprocess.check_output(['df','-k',str(Path.home())],text=True))
    # Conservative estimate includes all 2050 PNG plus movies and receipts.
    assert shutil.disk_usage(art).free>=8*1024**3+int(1.7*1024**3),'need 8GiB + 1.7GiB before rendering'
    for scene in doc['runs']:
        label=scene['scenario']
        for camera in scene['render_camera_ids']:
            out=data/label/camera
            cmd=blender+[str(producer),'--']+common+['--label',label,'--camera',camera,
                '--duration-s',str(scene['duration_us']/1e6),'--output',str(out)]
            if (out/'RENDER_LOCK.json').exists():
                cmd.append('--resume')
            run(cmd,label+'_'+camera,frame_dir=out)
        print(json.dumps({'scene':label,'status':'COMPLETE'}),flush=True)
    (evidence/'df_after_full_render.txt').write_text(subprocess.check_output(['df','-k',str(Path.home())],text=True))
    (evidence/'RENDER_FULL_COMPLETE.json').write_text(json.dumps({'status':'PASS','fps':5,
        'scenes':{r['scenario']:{'duration_s':r['duration_us']/1e6,'cameras':r['render_camera_ids']} for r in doc['runs']}},indent=2)+'\n')


if __name__=='__main__':
    def stop(signum,frame):
        raise SystemExit(f'producer stopped by signal {signum}')
    signal.signal(signal.SIGTERM,stop)
    main()
