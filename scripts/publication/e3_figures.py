"""Offline paper figures for #668; only frozen RGB/GT/calibration inputs.

No inference/scoring imports, recursive source discovery, network or renderer.
Run via uv with an existing environment containing numpy and Pillow.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from e3_coverage import BOUNDS, CELL, HEIGHTS, SCENE_SHA, camera_position, coverage, load_triangles, section_segments

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
D348_CAPTION = '僅為示意；E3 推論未使用牆面裁切（D348）。Agent 沒有拿到這張圖。'


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


def target(row):
    return next(a for a in row['actors'] if a['id']=='T')


def draw_panel(im, box, bounds, camera, mask, segments, painter, ticks=None, point=None):
    """One camera per panel: actual heading, occluded region, and optional GT."""
    d=ImageDraw.Draw(im);left,top,width,height=box
    name=camera['camera_id']
    d.rounded_rectangle((left,top,left+width,top+height),radius=18,fill='#f7f9fa',outline='#cbd5db',width=2)
    painter.text(d,(left+26,top+22),name,34)
    painter.text(d,(left+26,top+72),'箭頭：觀看方向　青色：靜態可見區',23,MUTED)
    pad=38;map_top=top+135;map_height=height-410;map_width=width-2*pad
    scale=min(map_width/(bounds[1]-bounds[0]),map_height/(bounds[3]-bounds[2]))
    ox=left+pad+(map_width-(bounds[1]-bounds[0])*scale)/2
    oy=map_top+(map_height-(bounds[3]-bounds[2])*scale)/2
    def xy(p):return (ox+(p[0]-bounds[0])*scale,oy+(bounds[3]-p[1])*scale)
    plot_w=round((bounds[1]-bounds[0])*scale);plot_h=round((bounds[3]-bounds[2])*scale)
    x0=round((bounds[0]-BOUNDS[0])/CELL);x1=round((bounds[1]-BOUNDS[0])/CELL)
    y0=round((BOUNDS[3]-bounds[3])/CELL);y1=round((BOUNDS[3]-bounds[2])/CELL)
    raster=Image.fromarray(mask[y0:y1,x0:x1].astype('uint8')*255).resize((plot_w,plot_h),Image.Resampling.NEAREST)
    im.paste('#75c9c2',(round(ox),round(oy),round(ox)+plot_w,round(oy)+plot_h),raster)
    d=ImageDraw.Draw(im)
    for a,b in segments:
        # Clip schematic walls to each panel, so no line crosses unrelated panels.
        ax,ay=a;bx,by=b;dx=bx-ax;dy=by-ay;t0=0.;t1=1.
        for v,q in [(-dx,ax-bounds[0]),(dx,bounds[1]-ax),(-dy,ay-bounds[2]),(dy,bounds[3]-ay)]:
            if abs(v)<1e-12:
                if q<0:t0=2;break
            elif v<0:t0=max(t0,q/v)
            else:t1=min(t1,q/v)
        if t0<=t1:d.line((xy((ax+t0*dx,ay+t0*dy)),xy((ax+t1*dx,ay+t1*dy))),fill='#505c65',width=4)
    if ticks is not None:
        lo=max(0,point['tick']-50);hi=min(len(ticks)-2,point['tick']+25)
        route=Image.new('RGBA',im.size);rd=ImageDraw.Draw(route)
        for a,b in zip(ticks[lo:hi],ticks[lo+1:hi+1]):
            ta,tb=target(a),target(b)
            if ta['present'] and tb['present'] and ta['xy'] and tb['xy']:
                rd.line((xy(ta['xy']),xy(tb['xy'])),fill='#a01b70',width=7)
        # Temporal marks remain visible even when the target stands still.
        positions=[xy(target(ticks[t])['xy']) for t in [point['tick']-5,point['tick'],point['tick']+5]]
        for i,pos in enumerate(positions):
            q=pos
            if any(j!=i and np.linalg.norm(np.array(pos)-np.array(other))<28 for j,other in enumerate(positions)):
                q=(pos[0]+(i-1)*38,pos[1]-42)
            camera_xy=camera_position(camera)[:2];matrix=np.array(camera['camera_to_world'])
            heading=np.array([-matrix[0,2],matrix[2,2]]);heading/=np.linalg.norm(heading)
            arrow_a=np.array(xy(camera_xy));arrow_b=np.array(xy(camera_xy+heading*min(2.,(bounds[1]-bounds[0])/7)))
            delta=arrow_b-arrow_a;fraction=np.clip(np.dot(np.array(pos)-arrow_a,delta)/np.dot(delta,delta),0,1)
            if np.linalg.norm(np.array(pos)-(arrow_a+fraction*delta))<38:
                q=(pos[0]-65,pos[1]+(i-1)*38)
            if q!=pos:rd.line((pos,q),fill='#a01b70',width=2)
            rd.ellipse((q[0]-15,q[1]-15,q[0]+15,q[1]+15),fill='white',outline='#a01b70',width=3)
            painter.text(rd,q,str(i+1),21,'#a01b70',anchor='mm')
        # Crop all trajectory annotations to this map's rectangle.
        crop=route.crop((round(ox),round(oy),round(ox)+plot_w,round(oy)+plot_h))
        im.paste(crop,(round(ox),round(oy)),crop);d=ImageDraw.Draw(im)
    position=camera_position(camera);m=np.array(camera['camera_to_world'])
    forward=np.array([-m[0,2],m[2,2]]);forward/=np.linalg.norm(forward)
    c=xy(position[:2]);length=min(2.,(bounds[1]-bounds[0])/7)
    tip=xy(position[:2]+forward*length)
    d.line((c,tip),fill=INK,width=8)
    direction=np.array(tip)-np.array(c);direction/=np.linalg.norm(direction)
    normal=np.array([-direction[1],direction[0]])
    d.polygon([tuple(tip),tuple(np.array(tip)-direction*24+normal*11),tuple(np.array(tip)-direction*24-normal*11)],fill=INK)
    d.ellipse((c[0]-10,c[1]-10,c[0]+10,c[1]+10),fill=INK,outline='white',width=2)
    # The context axes are below the plot; north is Blender +Y.
    painter.text(d,(ox+6,oy+6),'↑ +Y',22,INK)
    painter.text(d,(ox+plot_w-7,oy+plot_h+20),'+X →',22,INK,anchor='rt')
    # A metric scale remains valid for all crop aspect ratios.
    scale_y=oy+plot_h+39;scale_x=ox+8
    d.line((scale_x,scale_y,scale_x+2*scale,scale_y),fill=INK,width=4)
    d.line((scale_x,scale_y-6,scale_x,scale_y+6),fill=INK,width=3)
    d.line((scale_x+2*scale,scale_y-6,scale_x+2*scale,scale_y+6),fill=INK,width=3)
    painter.text(d,(scale_x+scale,scale_y+13),'2 m',21,INK,anchor='mt')
    yaw=np.degrees(np.arctan2(forward[1],forward[0]))
    painter.text(d,(left+25,top+height-130),f'位置 ({position[0]:.1f}, {position[1]:.1f}) m',24)
    painter.text(d,(left+25,top+height-88),f'朝向 {yaw:.1f}°（+X 起，逆時針）',23,MUTED)
    if point:
        visible=[name in target(ticks[t])['gt_visible'] for t in [point['tick']-5,point['tick'],point['tick']+5]]
        painter.text(d,(left+25,top+height-46),'凍結 GT ①／②／③：'+'／'.join('可見' if v else '不可見' for v in visible),22,MUTED)
    return {'camera_id':name,'position_blender_xyz_m':position.tolist(),
            'forward_xy_unit':forward.tolist(),'yaw_deg_ccw_from_x':float(yaw),'bounds_xy_m':list(bounds)}


def minimap(out, point, gt, cameras, window, painter, fields, sections):
    ticks=gt['ticks'];lo=max(0,point['tick']+window[0]);hi=min(len(ticks)-2,point['tick']+window[1])
    im=Image.new('RGB',(2700,1550),BG);d=ImageDraw.Draw(im)
    painter.text(d,(50,28),f"{point['figure_id']}  {point['title']}",48)
    painter.text(d,(50,105),'GT，評分端',38,'#a01b70')
    painter.text(d,(370,110),f"{point['case_id']}　錨點 {point['tick']/5:.1f} s　軌跡 {lo/5:.1f}–{hi/5:.1f} s",31)
    painter.text(d,(50,170),'每格一支鏡頭：深色箭頭＝朝向　青色區域＝經原場景遮擋後可見　紫線＝目標 GT 軌跡',29)
    by_id={c['camera_id']:c for c in cameras};panels=[]
    for i,name in enumerate(point['display_cameras']):
        panels.append(draw_panel(im,(50+i*880,235,840,1070),point['map_bounds_xy_m'],by_id[name],fields[name],sections,painter,ticks,point))
    d=ImageDraw.Draw(im)
    painter.text(d,(50,1345),f"① 前 {point['tick']/5-1:.1f} s　② 決策錨點 {point['tick']/5:.1f} s　③ 後 {point['tick']/5+1:.1f} s",30,'#a01b70')
    painter.text(d,(50,1401),'可見區：原始靜態 GLB＋校正，人體 0.15／0.9／1.6 m 三高度至少兩點可見；網格 0.05 m。',27,MUTED)
    painter.text(d,(50,1445),'不含移動人物遮擋；青色區域與凍結評分 GT 分別呈現，未改寫 GT。身分未確認，實體導航／碰撞 UNKNOWN。',25,MUTED)
    painter.text(d,(50,1490),D348_CAPTION,28,INK)
    return {**save_png(im,out/f"{point['figure_id']}_map.png"),'kind':'evaluation_gt_map','figure_id':point['figure_id'],'case_id':point['case_id'],
            'gt_label':'GT，評分端','actor_id':'T','time_window_us':[lo*200000,hi*200000],
            'anchor_timestamp_us':point['tick']*200000,'cameras':point['display_cameras'],'panels':panels,
            'd348_caption':D348_CAPTION,'occlusion_clipped':True,'coverage_source':'COVERAGE.json','gt_path':f"gt-boxes/{point['case_id']}.a-log.json",'root_ref':point['root_ref'],
            'trajectory_interpolation':False,'gt_trajectory_color':'#a01b70'}


def coverage_atlas(out,cameras,fields,sections,painter):
    im=Image.new('RGB',(3520,2400),BG);d=ImageDraw.Draw(im)
    painter.text(d,(50,30),'八鏡頭｜朝向與原場景遮擋後可見範圍',50)
    painter.text(d,(50,112),'每格一支鏡頭、同一世界座標；青色只保留穿過門洞、未被牆體／屏風／車輛擋住的區域。',30)
    panels=[]
    for i,camera in enumerate(cameras):
        panels.append(draw_panel(im,(50+(i%4)*870,200+(i//4)*1010,820,970),BOUNDS,camera,fields[camera['camera_id']],sections,painter))
    d=ImageDraw.Draw(im)
    painter.text(d,(50,2260),'深色圓點＝鏡頭位置　箭頭＝真實校正朝向　灰色＝原場景 0.9 m 高度剖面　青色＝靜態人體可見區',30)
    painter.text(d,(50,2320),'人體高度採 0.15／0.9／1.6 m，至少兩點可見；0.05 m 網格。不含人物間遮擋，非實體場域驗證。',27,MUTED)
    painter.text(d,(50,2360),D348_CAPTION,28,INK)
    return {**save_png(im,out/'camera_coverage_atlas.png'),'kind':'camera_coverage_atlas','d348_caption':D348_CAPTION,'cameras':[c['camera_id'] for c in cameras],'panels':panels,'coverage_source':'COVERAGE.json'}


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
    scene_path=args.assets/'scene.glb';assert sha(scene_path.read_bytes())==SCENE_SHA
    triangles,components=load_triangles(scene_path)
    fields={c['camera_id']:coverage(triangles,c) for c in cameras}
    sections=section_segments(triangles)
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
        artifacts.append(minimap(args.output,point,gt,cameras,selection['map_window_ticks'],painter,fields,sections))
    artifacts.append(coverage_atlas(args.output,cameras,fields,sections,painter))
    artifacts.append(overview(args.output,cases,painter))
    coverage_data={'schema':'amidst.static-camera-coverage.v2','scene_sha256':SCENE_SHA,'calibration_sha256':CAL_PIN,'triangles':len(triangles),'components':components,'bounds_xy_m':list(BOUNDS),'cell_m':CELL,'body_heights_m':list(HEIGHTS),'minimum_visible_heights':2,'dynamic_person_occlusion':False,'mask_shape':list(next(iter(fields.values())).shape),'mask_encoding':'numpy.packbits C-order, big bit order, base64','masks':{name:base64.b64encode(np.packbits(mask).tobytes()).decode('ascii') for name,mask in fields.items()},'visible_cells':{name:int(mask.sum()) for name,mask in fields.items()}}
    dump(args.output/'COVERAGE.json',coverage_data)
    provenance={'schema':'amidst.e3-figures.v1','issue':668,'selection':selection,
                'roots':{k:f'local/evidence/{v[0]}' for k,v in ROOT_PINS.items()},
                'source_files':inputs.used,'scene_mesh':{'path':'local/data/live-assets-20261115/scene.glb','sha256':SCENE_SHA,'bytes':scene_path.stat().st_size},'calibration':{'path':'local/data/live-assets-20261115/cameras.three.json','sha256':CAL_PIN},
                'repo_inputs':{str(path.relative_to(REPO)):sha(path.read_bytes()) for path in [selection_path,*catalog_paths,Path(__file__),REPO/'scripts/publication/verify_e3_figures.py',REPO/'scripts/publication/e3_coverage.py']},
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
