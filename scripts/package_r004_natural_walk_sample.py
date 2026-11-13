"""LOCAL source-bound before/after preview for the natural-walk sample."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def draw(im,xy,s,size=25,color='#f1f5f9'):
    ImageDraw.Draw(im).text(xy,s,font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',size),fill=color)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--artifacts-root',type=Path,required=True)
    p.add_argument('--sample-root',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,required=True)
    p.add_argument('--previous-sample-root',type=Path)
    a=p.parse_args()
    art,root=a.artifacts_root.resolve(),a.sample_root.resolve()
    assert root.parent==art/'evidence'
    bundle=art/'data/r004-4actor-v22-20261110/bundle'
    manifest=bundle/'BUNDLE_MANIFEST.json'
    assert sha(manifest)=='50a9806d0e4549c1c9f5159aa1a7a84058bb181da40b7c6279655e36ccf7f801'
    inventory={x['relative_path']:x for x in json.loads(manifest.read_text())['files']}
    safe=bundle/'safe'
    run=json.loads((safe/'clocks/A4-1.json').read_text())['run_id']
    verified=[]
    videos=[]
    validation={}
    overview=Image.new('RGB',(1920,1280),'#111827')
    previous_inventory={}
    if a.previous_sample_root:
        assert a.previous_sample_root.resolve().parent==art/'evidence'
        assert sha(a.previous_sample_root/'MANIFEST.json')=='ad7e191124d1ccb8cd5eebf0fea385955ccfa92d498acfc6ec6d7597d456c0fc'
        old_manifest=json.loads((a.previous_sample_root/'MANIFEST.json').read_text())
        previous_inventory={x['relative_path']:x for x in old_manifest['files']}
    for row,(label,cam,start) in enumerate([('W1','CAM_W1',10),('ENTRY','CAM_ENTRY',18)]):
        receipt=json.loads((root/label/'render_receipt.json').read_text())
        assert receipt['frames_checked']==90 and not receipt['surface_intersections']
        assert not receipt['source_blend_saved'] and not receipt['root_route_changed']
        assert receipt['camera']==cam and receipt['start_s']==start and receipt['fps']==15
        for n in range(90):
            path=root/label/f'{n:06d}.png'
            with Image.open(path) as im:
                assert im.size==(960,540) and im.mode=='RGB'
        for n in range(30):
            path=safe/'rgb'/run/cam/f'{start*5+n:06d}.png'
            expected=inventory[str(path.relative_to(art))]
            assert sha(path)==expected['sha256'] and path.stat().st_size==expected['size_bytes']
            verified.append(expected)

        def composite(n,comparison):
            time=start+n/(5 if comparison else 15)
            wall=dt.datetime.fromisoformat('2026-11-01T14:00:00+08:00')+dt.timedelta(seconds=time)
            im=Image.new('RGB',(1920 if comparison else 960,640),'#111827')
            if comparison:
                draw(im,(18,10),f'{cam} · 原版 v2.2／5 fps',29)
                draw(im,(978,10),'改善步態／相同 5 fps',29)
                before=safe/'rgb'/run/cam/f'{start*5+n:06d}.png'
                with Image.open(before) as src:
                    im.paste(src,(0,60))
            else:
                draw(im,(18,10),f'{cam} · 改善步態／15 fps · 原路線',29)
            after=root/label/f'{n*3 if comparison else n:06d}.png'
            with Image.open(after) as src:
                im.paste(src,(960 if comparison else 0,60))
            draw(im,(18,606),f't={time:04.1f}s · {wall.strftime("%H:%M:%S.%f")[:-5]} +08:00（宣告展示時鐘）',21)
            if comparison:
                draw(im,(978,606),'手腳交替／腳掌支撐／髖部升降／轉向過渡；未改路線時刻',21)
            return im

        for comparison,fps,count,suffix in [(True,5,30,'before_after_5fps'),(False,15,90,'natural_15fps')]:
            path=root/f'{label}_{suffix}.mp4'
            size=(1920 if comparison else 960,640)
            cmd=[str(a.ffmpeg),'-hide_banner','-loglevel','warning','-n','-f','rawvideo','-pix_fmt','rgb24',
                 '-s:v',f'{size[0]}x{size[1]}','-r',str(fps),'-i','pipe:0','-an',
                 '-c:v','libx264','-preset','medium','-crf','18','-vf','scale=out_color_matrix=bt709:out_range=tv',
                 '-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709',
                 '-color_trc','bt709','-movflags','+faststart',str(path)]
            with (root/f'{label}_{suffix}_encode.log').open('w') as log:
                proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
                for n in range(count):
                    frame=composite(n,comparison)
                    if comparison and n==15:
                        frame.save(root/f'{label}_before_after.png')
                        overview.paste(frame,(0,row*640))
                    proc.stdin.write(frame.tobytes())
                proc.stdin.close()
                assert proc.wait()==0
            decode=[str(a.ffmpeg),'-hide_banner','-i',str(path),'-map','0:v:0','-f','null','-',
                    '-progress','pipe:1','-nostats']
            check=subprocess.run(decode,capture_output=True,text=True)
            (root/f'{label}_{suffix}_decode.log').write_text(check.stderr+'\n'+check.stdout)
            fields=dict(l.split('=',1) for l in check.stdout.splitlines() if '=' in l)
            assert check.returncode==0 and int(fields['frame'])==count
            assert int(fields['out_time_us'])==6_000_000
            videos.append({'path':str(path.relative_to(art)),'fps':fps,'frames':count,'duration_s':6,
                           'sha256':sha(path),'size_bytes':path.stat().st_size})
            validation[path.name]={'result':'PASS','decoded_frames':count,'fps':fps,'duration_s':6,
                                   'encode_command':cmd,'decode_command':decode}
            print('Encoded/decoded',path.name,flush=True)
        if a.previous_sample_root:
            path=root/f'{label}_large_vs_soft_15fps.mp4'
            cmd=[str(a.ffmpeg),'-hide_banner','-loglevel','warning','-n','-f','rawvideo','-pix_fmt','rgb24',
                 '-s:v','1920x640','-r','15','-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','18',
                 '-vf','scale=out_color_matrix=bt709:out_range=tv','-pix_fmt','yuv420p','-color_range','tv',
                 '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(path)]
            with (root/f'{label}_large_vs_soft_encode.log').open('w') as log:
                proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
                for n in range(90):
                    old=a.previous_sample_root/label/f'{n:06d}.png'
                    assert sha(old)==previous_inventory[str(old.relative_to(art))]['sha256']
                    frame=Image.new('RGB',(1920,640),'#111827')
                    draw(frame,(18,10),f'{cam} · 前版大幅屈膝（跑步設計參考）',27)
                    draw(frame,(978,10),'走路新版 · 較小屈膝／較低抬腳',27)
                    with Image.open(old) as src:
                        frame.paste(src,(0,60))
                    with Image.open(root/label/f'{n:06d}.png') as src:
                        frame.paste(src,(960,60))
                    draw(frame,(18,606),f't={start+n/15:04.1f}s · 兩邊15fps／相同路線與移動速度',21)
                    draw(frame,(978,606),'抬腳8.5→1.8cm；步幅0.95→0.85m；保留支撐腳與固定腿長',21)
                    if n==45:
                        frame.save(root/f'{label}_large_vs_soft.png')
                    proc.stdin.write(frame.tobytes())
                proc.stdin.close()
                assert proc.wait()==0
            decode=[str(a.ffmpeg),'-hide_banner','-i',str(path),'-map','0:v:0','-f','null','-',
                    '-progress','pipe:1','-nostats']
            check=subprocess.run(decode,capture_output=True,text=True)
            (root/f'{label}_large_vs_soft_decode.log').write_text(check.stderr+'\n'+check.stdout)
            fields=dict(l.split('=',1) for l in check.stdout.splitlines() if '=' in l)
            assert check.returncode==0 and int(fields['frame'])==90 and int(fields['out_time_us'])==6_000_000
            videos.append({'path':str(path.relative_to(art)),'fps':15,'frames':90,'duration_s':6,
                           'sha256':sha(path),'size_bytes':path.stat().st_size})
            validation[path.name]={'result':'PASS','decoded_frames':90,'fps':15,'duration_s':6,
                                   'encode_command':cmd,'decode_command':decode,'previous_png_hashes_verified':90}
            print('Encoded/decoded',path.name,flush=True)
    overview.save(root/'BEFORE_AFTER_OVERVIEW.png')
    write(root/'MEDIA_VALIDATION.json',{'result':'PASS','source_original_rgb_hashes_verified':len(verified),
                                      'source_original_rgb':verified,'videos':validation})
    write(root/'VIDEOS.json',videos)
    (root/'REVIEW.html').write_text('''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>#516 自然步態樣片</title>
<style>body{background:#111827;color:#eef2ff;font:18px/1.7 system-ui;max-width:1500px;padding:24px;margin:auto}video,img{width:100%}a{color:#67e8f9}</style>
<h1>人物步態改善 · 短樣片</h1><p>原路線／時刻／材質不變。原版 v2.2 保留；新姿態只是動作展示樣片，未重建索引或取代完整驗收。</p>
PREVIOUS_GAIT_COMPARISON
<h2>走廊：相同 5 fps 前後對照</h2><video controls src="W1_before_after_5fps.mp4" poster="W1_before_after.png"></video>
<h2>近景：相同 5 fps 前後對照</h2><video controls src="ENTRY_before_after_5fps.mp4" poster="ENTRY_before_after.png"></video>
<h2>改善步態 · 15 fps</h2><p>較流暢的顯示版本；不代表原資料或推論索引已改成15fps。</p>
<video controls src="W1_natural_15fps.mp4"></video><video controls src="ENTRY_natural_15fps.mp4"></video>
<p>仍是原始幾何人形；本次未製作跑步、進房間或車旁徘徊的新路線。<a href="ACTUAL_OUTPUT.md">實際產出</a> · <a href="MANIFEST.json">SHA-256</a></p></html>'''.replace('PREVIOUS_GAIT_COMPARISON', '<h2>前版大幅度／走路新版小幅度（同15fps）</h2><video controls src="W1_large_vs_soft_15fps.mp4" poster="W1_large_vs_soft.png"></video>' if a.previous_sample_root else ''))


if __name__=='__main__':
    main()
