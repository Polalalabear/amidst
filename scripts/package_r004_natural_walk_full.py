"""Encode full corrected viewing movies from new, journal-verified RGB only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont

CAMERAS=['CAM_EXT_CAR','CAM_EXT_CLEAR','CAM_W1','CAM_W2','CAM_BRANCH','CAM_WIDE','CAM_R101_IN','CAM_ENTRY']
W,H=1920,1260


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


@lru_cache(maxsize=16)
def font(size):
    return ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',size)


def text(im,xy,s,size=24,color='#f1f5f9'):
    ImageDraw.Draw(im).text(xy,s,font=font(size),fill=color)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--artifacts-root',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,required=True)
    p.add_argument('--scene',choices=['A4-1','B4-1','all'],default='all')
    p.add_argument('--evidence-root',type=Path)
    p.add_argument('--data-root',type=Path)
    p.add_argument('--scenario',type=Path)
    a=p.parse_args()
    art=a.artifacts_root.resolve()
    data=(a.data_root or art/'data/r004-4actor-natural-walk-20261114').resolve()
    out=(a.evidence_root or art/'evidence/codex-516-natural-walk-full-20261114').resolve()
    assert out.parent==art/'evidence' and data.parent==art/'data'
    assert data.name.startswith('r004-4actor-natural-walk-')
    assert not (out/'FULL_MANIFEST.json').exists(),'frozen output: choose a new evidence/data root'
    camera_movies=out/'cameras'
    camera_movies.mkdir(exist_ok=True)
    script=a.scenario or art/'evidence/codex-516-v21-feasibility-20261110/delivery-049f3b3c/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json'
    if not script.resolve().is_relative_to(art):
        staged=out/'inputs'/script.name
        staged.parent.mkdir(exist_ok=True)
        if staged.exists():
            assert sha(staged)==sha(script)
        else:
            shutil.copyfile(script,staged)
        script=staged
    doc=json.loads(script.read_text())
    movie_rows=[]

    def info(path):
        return {'relative_path':str(path.relative_to(art)),'size_bytes':path.stat().st_size,'sha256':sha(path)}

    def validate(path,count,duration):
        cmd=[str(a.ffmpeg),'-hide_banner','-i',str(path),'-map','0:v:0','-f','null','-',
             '-progress','pipe:1','-nostats']
        check=subprocess.run(cmd,capture_output=True,text=True)
        (out/f'{path.stem}_decode.log').write_text(check.stderr+'\n'+check.stdout)
        fields=dict(line.split('=',1) for line in check.stdout.splitlines() if '=' in line)
        assert check.returncode==0 and int(fields['frame'])==count
        assert int(fields['out_time_us'])==int(duration*1e6)
        result={'status':'PASS','decoded_frames':count,'fps':5,'duration_s':duration,'file':info(path),'command':cmd}
        movie_rows.append(result)
        return result

    options=['-an','-c:v','libx264','-preset','medium','-crf','18','-vf','scale=out_color_matrix=bt709:out_range=tv',
             '-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709',
             '-color_trc','bt709','-movflags','+faststart']
    for scene in doc['runs']:
        label=scene['scenario']
        if a.scene!='all' and label!=a.scene:
            continue
        count=scene['duration_us']//200000
        duration=scene['duration_us']/1e6
        cams=scene['render_camera_ids']
        receipts=[]
        verified=[]
        for cam in cams:
            folder=data/label/cam
            receipt=json.loads((folder/'render_receipt.json').read_text())
            lock=json.loads((folder/'RENDER_LOCK.json').read_text())
            assert receipt['fps']==5 and receipt['label']==label and receipt['frames_checked']==count
            assert receipt['completed_render_frames']==count and not receipt['surface_intersections']
            assert not receipt['source_blend_saved'] and not receipt['camera_matrix_changed']
            assert not receipt['root_route_changed'] and receipt['gait_profile']=='walk'
            assert lock['fps']==5 and lock['label']==label and lock['start_s']==0
            assert lock['source_sha256']=='466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b'
            assert lock['catalog_sha256']=='3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f'
            rows=[json.loads(s) for s in (folder/'frame_manifest.jsonl').read_text().splitlines()]
            assert sorted(r['frame_index'] for r in rows)==list(range(count))
            assert sorted(p.name for p in folder.glob('*.png'))==[f'{n:06d}.png' for n in range(count)]
            for row in rows:
                png=folder/f"{row['frame_index']:06d}.png"
                assert row['source_time_us']==row['frame_index']*200000
                assert png.stat().st_size==row['size_bytes'] and sha(png)==row['sha256']
                with Image.open(png) as image:
                    assert image.size==(960,540) and image.mode=='RGB'
                verified.append(info(png))
            receipts.append(receipt)
            path=camera_movies/f'{label}_{cam}_full_5fps.mp4'
            if not path.exists():
                cmd=[str(a.ffmpeg),'-hide_banner','-loglevel','warning','-n','-framerate','5','-start_number','0',
                     '-i',str(folder/'%06d.png'),'-frames:v',str(count)]+options+[str(path)]
                with (out/f'{path.stem}_encode.log').open('w') as log:
                    assert subprocess.run(cmd,stderr=log).returncode==0
            validate(path,count,duration)
        assert len({r['gait_code_sha256'] for r in receipts})==1
        # Original reuse receipts retain the original producer pin; safe preparation verifies equivalence.
        assert len({r['producer_code_sha256'] for r in receipts})<=2
        clock_path=data/f'bundle/safe/clocks/{label}.json'
        parent_clock=json.loads(clock_path.read_text())
        wall_origin=dt.datetime.fromisoformat(parent_clock['wall_origin'])
        template=Image.new('RGB',(W,H),'#111827')
        text(template,(22,12),f'{label} · 完整步態修正版 · {duration:g} 秒',32)
        text(template,(22,49),'5 fps／原速 · 小幅腳步＋修正擺臂 · v2.3 遮擋修正動線／原相機',18,'#a9b6c7')
        for k,cam in enumerate(CAMERAS):
            x,y=(k%3)*640,72+(k//3)*384
            ImageDraw.Draw(template).rectangle((x,y,x+638,y+382),fill='#1e293b')
            text(template,(x+12,y+2),cam+(' · 額外鏡頭' if cam=='CAM_ENTRY' else ''),20)
            if cam not in cams:
                text(template,(x+110,y+145),'本 run 未產製此鏡頭',29,'#a9b6c7')
                text(template,(x+100,y+195),'NOT RENDERED · 不代表無人出現',20,'#a9b6c7')
        for k,s in enumerate(['完整修正版',f'{len(cams)} 個實際鏡頭',f'{duration:g} 秒 · 5 fps · 原速',
                              '手肘向後／左右交叉擺臂','保留已確認的小幅腳步']):
            text(template,(1302,865+k*45),s,26 if k==0 else 23)
        text(template,(22,1232),'ACTUAL_BLENDER · LOCAL 完整觀看版 · 時鐘為宣告展示時鐘；非實體攝影機錄影時間',19,'#a9b6c7')
        montage=out/f'{label}_full_corrected_5fps.mp4'
        if not montage.exists():
            cmd=[str(a.ffmpeg),'-hide_banner','-loglevel','warning','-n','-f','rawvideo','-pix_fmt','rgb24',
                 '-s:v',f'{W}x{H}','-r','5','-i','pipe:0']+options+[str(montage)]
            with (out/f'{montage.stem}_encode.log').open('w') as log:
                proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
                for n in range(count):
                    frame=template.copy()
                    wall=wall_origin+dt.timedelta(seconds=n/5)
                    text(frame,(1070,12),f't={n/5:05.1f}s · {wall.strftime("%H:%M:%S.%f")[:-5]} +08:00',26)
                    text(frame,(1302,1130),f'影格 {n+1:03d}／{count}',26,'#67e8f9')
                    for k,cam in enumerate(CAMERAS):
                        if cam in cams:
                            with Image.open(data/label/cam/f'{n:06d}.png') as im:
                                frame.paste(im.convert('RGB').resize((640,360),Image.Resampling.LANCZOS),((k%3)*640,96+(k//3)*384))
                    if n in [0,count//2,count-1]:
                        frame.save(out/f'{label}_full_frame_{n:06d}.png')
                    proc.stdin.write(frame.tobytes())
                    if n%50==0:
                        print(label,'montage',n,'/',count,flush=True)
                proc.stdin.close()
                assert proc.wait()==0
        validate(montage,count,duration)
        result={'schema':'amidst.r004-corrected-full-view.v1','label':label,
                'display_run_id':parent_clock['run_id'],
                'clock':parent_clock,
                'clock_file':info(clock_path),'fps':5,'duration_s':duration,
                'camera_ids':cams,'rgb_files_verified':verified,'gait_code_sha256':receipts[0]['gait_code_sha256'],
                'producer_code_sha256s':sorted({r['producer_code_sha256'] for r in receipts}),
                'package_code_sha256':sha(Path(__file__)),
                'ffmpeg_executable_sha256':sha(a.ffmpeg),
                'formal_eligible':False,'inference_executed':False,'ranking_executed':False,
                'reconstruction_executed':False,'new_routes_authored':True,
                'scope':'Eight-camera viewing of the new independent indexed safe run; old #523 and #527 frozen payloads unchanged',
                'movies':[r for r in movie_rows if Path(r['file']['relative_path']).name.startswith(label)]}
        save(out/f'FULL_MEDIA_{label}.json',result)
        print(label,'FULL MOVIE READY',str(montage),flush=True)
    pages=[]
    for label in ['A4-1','B4-1']:
        metadata=out/f'FULL_MEDIA_{label}.json'
        if not metadata.exists():
            continue
        run=json.loads(metadata.read_text())
        pages.append(f'<h2>{label} · {run["duration_s"]:g} 秒</h2><video controls src="{label}_full_corrected_5fps.mp4"></video>')
        pages.append('<details><summary>各鏡頭完整影片（960×540）</summary>')
        for cam in run['camera_ids']:
            pages.append(f'<h3>{cam}</h3><video controls preload="none" src="cameras/{label}_{cam}_full_5fps.mp4"></video>')
        pages.append('</details>')
    (out/'REVIEW_FULL.html').write_text('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>完整修正版 A4／B4</title><style>body{background:#111827;color:#eef2ff;font:18px/1.7 system-ui;max-width:1500px;margin:32px auto;padding:0 24px}video{width:100%;margin:12px 0}summary{cursor:pointer}</style><h1>完整步態修正版 · 5 fps</h1><p>v2.3 動線修正、T 原時刻與原相機；已確認的小幅腳步與正確交叉擺臂。所有畫面來自本次新影格。</p>'+''.join(pages)+'</html>')
    if all((out/f'FULL_MEDIA_{label}.json').exists() for label in ['A4-1','B4-1']) and (out/'RENDER_FULL_COMPLETE.json').exists():
        repo=Path(__file__).resolve().parents[1]
        code_paths=['scripts/r004_natural_walk.py','scripts/render_r004_natural_walk_sample.py',
                    'scripts/check_r004_natural_walk_routes.py','scripts/audit_r004_natural_walk_endpoints.py',
                    'scripts/produce_r004_natural_walk_full.py','scripts/package_r004_natural_walk_sample.py',
                    'scripts/package_r004_natural_walk_full.py','tests/evaluation/test_r004_natural_walk.py',
                    'scripts/render_r004_d124.py','configs/q1q5/producers/r004_d124_v1.json',
                    'scripts/prepare_r004_eight_camera_reuse.py','scripts/prepare_r004_eight_camera_safe.py',
                    'scripts/index_r004_4actor.py','scripts/package_r004_4actor.py']
        for relative in code_paths:
            target=out/'code'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(repo/relative,target)
        base_code=art/'evidence/codex-516-v21-feasibility-20261110/delivery-049f3b3c/scripts/r004_4actor_common.py'
        target=out/'code/baseline/r004_4actor_common.py'
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(base_code,target)
        runs={label:json.loads((out/f'FULL_MEDIA_{label}.json').read_text()) for label in ['A4-1','B4-1']}
        assert sum(len(run['rgb_files_verified']) for run in runs.values())==sum(r['duration_us']//200000*len(r['render_camera_ids']) for r in doc['runs'])
        assert len({run['gait_code_sha256'] for run in runs.values()})==1
        assert all(run['producer_code_sha256s'] for run in runs.values())
        assert len({run['package_code_sha256'] for run in runs.values()})==1
        # These supervisor streams continue after this child closes the fixed payload.
        late={'FULL_MANIFEST.json','encode_review.log','postprocess.log','POSTPROCESS_COMPLETE.json'}
        files=[info(path) for folder in [data,out] for path in sorted(folder.rglob('*'))
               if path.is_file() and path.name not in late]
        full={'schema':'amidst.corrected-full-view-manifest.v1','local_root':'$AMIDST_ARTIFACTS',
              'scope':'Fixed full-view payload; later CI/closing records excluded; source render/input assets are not copied',
              'file_count':len(files),'total_bytes':sum(row['size_bytes'] for row in files),
              'rendered_png_count':sum(len(r['rgb_files_verified']) for r in runs.values()),'movie_count':sum(len(r['movies']) for r in runs.values()),'files':files,
              'source_inputs':[info(script),info(base_code),
                               info(art/'data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend'),
                               info(art/'data/r004-build-v2-20261021/safe_static/cameras.json')],
              'runs':{label:{'display_run_id':run['display_run_id'],'clock_id':run['clock']['clock_id'],
                             'fps':5,'duration_s':run['duration_s'],'camera_ids':run['camera_ids'],
                             'rendered_frames':len(run['rgb_files_verified'])} for label,run in runs.items()},
              'formal_eligible':False,'inference_executed':True,'ranking_executed':False,'reconstruction_executed':False}
        save(out/'FULL_MANIFEST.json',full)
        print(json.dumps({'full_manifest_sha256':sha(out/'FULL_MANIFEST.json'),
                          'files':len(files),'bytes':full['total_bytes']}),flush=True)


if __name__=='__main__':
    main()
