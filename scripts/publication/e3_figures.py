"""Offline paper figures for #668; only frozen RGB/GT/calibration inputs.

No inference/scoring imports, recursive source discovery, network or renderer.
Run via uv with an existing environment containing numpy and Pillow.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
ROOT_PINS = {
    'base': ('e3-652-20261122', '853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e'),
    'extension': ('e3-reappearances-20261122', '5eac93379533485e754f29ebf54f409e7992bd551db822ab6aeea2022aa78517'),
}
CAL_PIN = '6deb31b032f4a7ce2e1734db07b666d118e1b0de17e8e37be7008814ba0f4f41'
TYPE_NAMES = {'A': '相似衣著交錯', 'B': '長盲區重現', 'C': '多出口', 'D': '遮擋／真正離開'}
INK = '#172c3b'
MUTED = '#536877'
BG = '#ffffff'
TEAL = '#007b82'
ORANGE = '#b45100'
CAM_COLORS = ['#3d67ac','#9c6c20','#667a3a','#a44a81','#6862a4','#227f77','#a54f3c','#427d9b']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


class Inputs:
    """Read only named inputs; hash every consumed byte, never traverse corpora."""
    def __init__(self, evidence):
        self.evidence = evidence
        self.entries = {}
        self.used = {}
        for ref, (name, pin) in ROOT_PINS.items():
            data = (evidence / name / 'MANIFEST.json').read_bytes()
            assert sha(data) == pin, f'{name}: manifest mismatch'
            self.entries[ref] = {e['path']: e for e in json.loads(data)['files']}
            self.used[f'local/evidence/{name}/MANIFEST.json'] = {'sha256': pin, 'bytes': len(data)}

    def read(self, ref, rel):
        # No case files, baseline snapshots, detections, scores, or arm outputs.
        assert rel.startswith(('rgb/', 'gt-boxes/')), rel
        assert '..' not in Path(rel).parts
        name = ROOT_PINS[ref][0]
        data = (self.evidence / name / rel).read_bytes()
        entry = self.entries[ref][rel]
        assert len(data) == entry['bytes'] and sha(data) == entry['sha256'], rel
        self.used[f'local/evidence/{name}/{rel}'] = {'sha256': sha(data), 'bytes': len(data)}
        return data


def font_path():
    candidates = ['/System/Library/Fonts/STHeiti Medium.ttc',
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for name in candidates:
        if Path(name).exists():
            return Path(name)
    raise RuntimeError('Supply --font with a Traditional Chinese capable font')


class Painter:
    def __init__(self, font):
        self.font = font
        self.fonts = {}

    def text(self, draw, xy, text, size=30, fill=INK, anchor=None):
        if size not in self.fonts:
            self.fonts[size] = ImageFont.truetype(str(self.font), size)
        draw.text(xy, text, font=self.fonts[size], fill=fill, anchor=anchor)


def save_png(im, path):
    # No time, home path, or private locator metadata in the PNG.
    im.save(path, format='PNG', compress_level=9)
    return {'path': path.name, 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size,
            'width': im.width, 'height': im.height}


def montage(out, point, phase, tick, records, inputs, cams, painter):
    im = Image.new('RGB', (2728, 1200), BG)
    d = ImageDraw.Draw(im)
    painter.text(d, (48, 30), f"{point['figure_id']}  {point['title']}", 48)
    painter.text(d, (48, 100), f"{point['case_id']}   決策錨點 {point['tick']/5:.1f} s   ｜   {phase} {tick/5:.1f} s", 34, TEAL)
    painter.text(d, (48, 151), 'LIVE WebGL 凍結 RGB  ·  八鏡頭同步  ·  原始 320×180，最近鄰放大 2 倍', 28, MUTED)
    sources = []
    for i, cam in enumerate(cams):
        x, y = 48 + (i % 4) * 664, 224 + (i // 4) * 442
        painter.text(d, (x, y), f'{i+1:02d}  {cam}', 30)
        rec = records[(cam, tick)]
        raw = inputs.read(point['root_ref'], rec['relative_path'])
        assert sha(raw) == rec['file_sha256']
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        assert image.size == (320, 180)
        im.paste(image.resize((640, 360), Image.Resampling.NEAREST), (x, y+50))
        d.rectangle((x-1, y+49, x+640, y+410), outline='#b6c4cd', width=1)
        sources.append({**rec, 'root_ref': point['root_ref']})
    painter.text(d, (48, 1133), '僅供劇本情境展示；未畫 GT 框／軌跡，未顯示任何組別答案或分數。', 29, MUTED)
    return {**save_png(im, out/f"{point['figure_id']}_{'before' if phase=='前' else 'after'}.png"),
            'kind': 'multicamera_rgb', 'figure_id': point['figure_id'], 'case_id': point['case_id'],
            'timestamp_us': tick*200000, 'cameras': cams, 'sources': sources,
            'gt_overlay': False, 'pixel_transform': 'nearest-neighbor 2x, no crop or color change'}


def clip_polygon(poly, value):
    result = []
    if not poly:
        return result
    for a, b in zip(poly, poly[1:]+poly[:1]):
        va, vb = value(a), value(b)
        if va >= 0:
            result.append(a)
        if (va >= 0) != (vb >= 0):
            t = va / (va-vb)
            result.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    return result


def footprint(camera, bounds):
    """Clip the actual 6-plane frustum at Blender z=0 to the map rectangle."""
    # Blender (x,y,0,1) -> glTF (x,0,-y,1); matrices are row-major.
    transform = np.array([[1,0,0], [0,0,0], [0,-1,0], [0,0,1]], dtype=float)
    matrix = np.array(camera['projection_matrix']) @ np.array(camera['world_to_camera']) @ transform
    poly = [(bounds[0],bounds[2]),(bounds[1],bounds[2]),(bounds[1],bounds[3]),(bounds[0],bounds[3])]
    for axis in range(3):
        for sign in [-1, 1]:
            coeff = matrix[3] + sign*matrix[axis]
            poly = clip_polygon(poly, lambda p, c=coeff: c[0]*p[0]+c[1]*p[1]+c[2])
    return poly


def target(row):
    return next(a for a in row['actors'] if a['id']=='T')


def minimap(out, point, gt, cameras, geometry, window, painter):
    ticks = gt['ticks']
    lo, hi = max(0, point['tick']+window[0]), min(len(ticks)-2, point['tick']+window[1])
    im = Image.new('RGB', (2280, 1600), BG)
    d = ImageDraw.Draw(im)
    painter.text(d, (55, 30), f"{point['figure_id']}  {point['title']}", 46)
    painter.text(d, (55, 100), 'GT，評分端', 42, '#a63d0b')
    painter.text(d, (390, 108), f"{point['case_id']}  ｜  {lo/5:.1f}–{hi/5:.1f} s  ｜  決策錨點 {point['tick']/5:.1f} s", 30)
    bounds = (-15, 23, -10, 18)
    left, top, scale = 105, 220, 42
    def xy(p):
        return (left+(p[0]-bounds[0])*scale, top+(bounds[3]-p[1])*scale)
    for x in range(-15,24,5):
        a,b=xy((x,-10)),xy((x,18)); d.line((a,b),fill='#e6ebef',width=1)
        painter.text(d,(a[0],a[1]+16),str(x),24,MUTED,anchor='mt')
    for y in range(-10,19,5):
        a,b=xy((-15,y)),xy((23,y));d.line((a,b),fill='#e6ebef',width=1)
        painter.text(d,(a[0]-18,a[1]),str(y),24,MUTED,anchor='rm')
    d.rectangle((*xy((-15,18)),*xy((23,-10))),outline='#aebec8',width=2)
    # All eight calibrated FOV footprints, uniformly styled (no GT-based camera ranking).
    for camera,color in zip(cameras,CAM_COLORS):
        overlay = Image.new('RGBA', im.size)
        od = ImageDraw.Draw(overlay)
        poly = footprint(camera,bounds)
        if len(poly)>=3:
            rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
            od.polygon([xy(p) for p in poly], fill=(*rgb,8), outline=(*rgb,130), width=3)
        im = Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB')
    d=ImageDraw.Draw(im)
    for s in geometry['clearance_segments']:
        d.line((xy(s['a']),xy(s['b'])),fill='#687780' if not s['collider'].startswith('OBSTACLE') else '#718748',width=3)
    # Full continuous GT positions within the explicit temporal crop; no interpolation.
    for a,b in zip(ticks[lo:hi],ticks[lo+1:hi+1]):
        ta,tb=target(a),target(b)
        if ta['present'] and tb['present'] and ta['xy'] and tb['xy']:
            # Orange denotes globally unseen under the frozen visibility proxy.
            color=TEAL if ta['gt_visible'] and tb['gt_visible'] else ORANGE
            d.line((xy(ta['xy']),xy(tb['xy'])),fill=color,width=7)
    marker_ticks = [(point['tick']-5,'前',TEAL,'circle'),(point['tick'],'錨點',INK,'diamond'),(point['tick']+5,'後',ORANGE,'square')]
    marker_xy=[xy(target(ticks[t])['xy']) for t,_,_,_ in marker_ticks]
    for index,(tick,label,color,shape) in enumerate(marker_ticks):
        p=marker_xy[index];r=11
        if any(j!=index and np.linalg.norm(np.array(p)-np.array(q))<24 for j,q in enumerate(marker_xy)):
            actual=p;p=(p[0]+(index-1)*38,p[1]-45)
            d.line((actual,p),fill=color,width=2)
        if shape=='circle':d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill='white',outline=color,width=4)
        elif shape=='diamond':d.polygon([(p[0],p[1]-r),(p[0]+r,p[1]),(p[0],p[1]+r),(p[0]-r,p[1])],fill=color)
        else:d.rectangle((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill='white',outline=color,width=4)
    # Offset number labels and leaders preserve temporal markers near cameras.
    for i,c in enumerate(cameras):
        m=c['camera_to_world'];p=xy((m[0][3],-m[2][3]));q=(p[0]+45,p[1]-36)
        color=CAM_COLORS[i]
        d.line((p,q),fill=color,width=3)
        d.polygon([(p[0],p[1]-7),(p[0]+7,p[1]+6),(p[0]-7,p[1]+6)],fill=color)
        d.ellipse((q[0]-18,q[1]-18,q[0]+18,q[1]+18),fill=color,outline='white',width=2)
        painter.text(d,q,f'{i+1}',24,'white',anchor='mm')
    # Dedicated legend column avoids covering the trajectory or cameras.
    lx=1780
    painter.text(d,(lx,220),'鏡頭位置',32)
    for i,c in enumerate(cameras):painter.text(d,(lx,280+i*49),f"{i+1:02d}  {c['camera_id']}",25,CAM_COLORS[i])
    painter.text(d,(lx,725),'FOV：鏡頭同色淡面',29,TEAL)
    painter.text(d,(lx,772),'地平面 z=0 投影',26,MUTED)
    painter.text(d,(lx,814),'裁至圖界，未扣遮擋',26,MUTED)
    painter.text(d,(lx,895),'GT 軌跡（非推論）',29)
    painter.text(d,(lx,946),'青：至少一鏡可見',26,TEAL)
    painter.text(d,(lx,991),'橙：全鏡不可見',26,ORANGE)
    painter.text(d,(lx,1056),'○ 前   ◆ 錨點   □ 後',27)
    for j,(tick,label,_,_) in enumerate(marker_ticks):
        a=target(ticks[tick]);vis=', '.join(c.replace('CAM_','') for c in a['gt_visible']) or 'NONE'
        painter.text(d,(lx,1110+j*75),f'{label} {tick/5:.1f} s',25)
        painter.text(d,(lx,1141+j*75),vis,22,MUTED)
    painter.text(d,(lx,1350),'重合標記以引線連回',23,MUTED)
    painter.text(d,(900,1470),'Blender 世界 X（m）／Y（m），等比例；灰：牆體，綠：屏風',27,MUTED,anchor='mm')
    painter.text(d,(55,1520),'GT 僅供評分示意；靜態牆射線代理未含人擋人。身分未確認；實體導航／碰撞 UNKNOWN。',26,MUTED)
    artifact=save_png(im,out/f"{point['figure_id']}_map.png")
    return {**artifact,'kind':'evaluation_gt_map','figure_id':point['figure_id'],'case_id':point['case_id'],
            'gt_label':'GT，評分端','actor_id':'T','time_window_us':[lo*200000,hi*200000],
            'anchor_timestamp_us':point['tick']*200000,'cameras':[c['camera_id'] for c in cameras],
            'fov_plane_blender_z_m':0,'fov_clipped_bounds_xy_m':list(bounds),'occlusion_clipped':False,
            'gt_path':f"gt-boxes/{point['case_id']}.a-log.json",'root_ref':point['root_ref'],
            'trajectory_interpolation':False}


def overview(out,cases,painter):
    im=Image.new('RGB',(2100,1700),BG);d=ImageDraw.Draw(im)
    painter.text(d,(65,38),'E3 困難劇本｜凍結語料總覽',50)
    painter.text(d,(65,112),'16 段  ·  68 個主要決策點  ·  1044.6 秒  ·  兩批既有輸入／GT',32,TEAL)
    cols=[65,400,950,1340,1640]
    headers=['來源段','類型','主要決策點數','長度（秒）','批次']
    for x,h in zip(cols,headers):painter.text(d,(x,210),h,31)
    csv_rows=[]
    for i,c in enumerate(cases):
        y=280+i*70
        if i%2==0:d.rectangle((50,y-8,2045,y+56),fill='#f0f5f6')
        values=[c['case_id'],f"{c['family']}  {TYPE_NAMES[c['family']]}",str(len(c['decision_points'])),f"{c['duration_s']:.1f}",'#663' if c['root_ref']=='base' else '#665']
        for x,v in zip(cols,values):painter.text(d,(x,y),v,29)
        csv_rows.append({'case_id':c['case_id'],'type':c['family'],'primary_decision_points':len(c['decision_points']),'duration_s':f"{c['duration_s']:.1f}",'batch':c['root_ref']})
    d.line((60,1430,2030,1430),fill=INK,width=2)
    for x,v in zip(cols,['合計','A 3 段／B 5 段／C 6 段／D 2 段','68','1044.6','9＋7 段']):painter.text(d,(x,1457),v,29)
    painter.text(d,(65,1540),'點數依已凍結 catalog；排除診斷點及 5 個重複返回，並非 68 個獨立試驗。',27,MUTED)
    painter.text(d,(65,1590),'本表是輸入規模，不代表 Agent／規則組表現；兩批 33 個 H4 返回點包含於 68 點中。',27,MUTED)
    with (out/'overview.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(csv_rows[0]));writer.writeheader();writer.writerows(csv_rows)
    return {**save_png(im,out/'overview.png'),'kind':'corpus_overview','case_count':16,'primary_decision_points':68,'duration_s':1044.6}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--font',type=Path)
    args=p.parse_args()
    # Refuse to overwrite the frozen inputs or an existing delivered result.
    assert not args.output.exists(), 'Use a fresh output directory'
    assert not any(args.output.resolve().is_relative_to(args.evidence_root.resolve()/v[0]) for v in ROOT_PINS.values())
    inputs=Inputs(args.evidence_root)
    selection_path=REPO/'configs/publication/e3_figures_20261123.json'
    selection=json.loads(selection_path.read_bytes())
    calibration_path=args.assets/'cameras.three.json'
    cal_bytes=calibration_path.read_bytes();assert sha(cal_bytes)==CAL_PIN
    cameras=json.loads(cal_bytes)['cameras'];cams=[c['camera_id'] for c in cameras]
    geometry_path=REPO/'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'
    geometry=json.loads(geometry_path.read_bytes())
    catalog_paths=[REPO/'configs/evaluation/e3_live_cases_v1.json',REPO/'configs/evaluation/e3_reappearances_v1.json']
    # Project source/GT definitions only; ignore verification, baseline and ranking fields.
    cases=[]
    for ref,path in zip(ROOT_PINS,catalog_paths):
        for c in json.loads(path.read_bytes())['cases']:
            cases.append({k:c[k] for k in ['case_id','family','duration_s','decision_points','gt_path','gt_sha256']}|{'root_ref':ref})
    assert len(cases)==16 and sum(len(c['decision_points']) for c in cases)==68
    assert round(sum(c['duration_s'] for c in cases),1)==1044.6
    font=args.font or font_path();painter=Painter(font)
    args.output.mkdir(parents=True)
    artifacts=[]
    by_id={c['case_id']:c for c in cases}
    for point in selection['points']:
        case=by_id[point['case_id']]
        assert any(e['tick']==point['tick'] and e['type']==point['event_type'] for e in case['decision_points'])
        gt_bytes=inputs.read(point['root_ref'],case['gt_path']);assert sha(gt_bytes)==case['gt_sha256']
        gt=json.loads(gt_bytes)
        rgb_bytes=inputs.read(point['root_ref'],f"rgb/{point['case_id']}/rgb_index.json")
        rgb=json.loads(rgb_bytes)
        assert rgb['run_id']==point['case_id'] and not rgb['missing']
        records={(r['camera_id'],r['frame_index']):r for r in rgb['records']}
        for offset,phase in zip(selection['offset_ticks'],['前','後']):
            tick=point['tick']+offset
            assert all(round(records[(cam,tick)]['timestamp_s']*1e6)==tick*200000 for cam in cams)
            artifacts.append(montage(args.output,point,phase,tick,records,inputs,cams,painter))
        artifacts.append(minimap(args.output,point,gt,cameras,geometry,selection['map_window_ticks'],painter))
    artifacts.append(overview(args.output,cases,painter))
    provenance={'schema':'amidst.e3-figures.v1','issue':668,'selection':selection,
                'roots':{k:f'local/evidence/{v[0]}' for k,v in ROOT_PINS.items()},
                'source_files':inputs.used,'calibration':{'path':'local/data/live-assets-20261115/cameras.three.json','sha256':CAL_PIN},
                'repo_inputs':{str(path.relative_to(REPO)):sha(path.read_bytes()) for path in [selection_path,geometry_path,*catalog_paths,Path(__file__),REPO/'scripts/publication/verify_e3_figures.py']},
                'font':{'basename':font.name,'sha256':sha(font.read_bytes()),'pillow':Image.__version__,'numpy':np.__version__},
                'artifacts':artifacts,'agent_rule_outputs_read':False,'paid_api_calls':0,'blender_renders':0,
                'source_pngs_consumed':sum(len(a.get('sources',[])) for a in artifacts)}
    dump(args.output/'PROVENANCE.json',provenance)
    # Only enumerate our freshly generated directory, never any source corpus.
    entries=[{'path':f.name,'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())} for f in sorted(args.output.iterdir())]
    dump(args.output/'MANIFEST.json',{'schema':'amidst.figure-manifest.v1','files':entries,'file_count':len(entries),
                                    'bytes':sum(e['bytes'] for e in entries),'manifest_self_excluded':True})
    print(json.dumps({'png_count':len(artifacts),'file_count':len(entries),'manifest_sha256':sha((args.output/'MANIFEST.json').read_bytes()),'bytes':sum(e['bytes'] for e in entries)}))


if __name__=='__main__':
    main()
