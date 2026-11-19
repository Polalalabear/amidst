"""Evaluation-only GT scorer for r004 A4-1 / B4-1 (copied from the D325 analysis, LOCAL ``eval-recorded-llm-20261118/scripts/score.py``,
SHA-256 in docs/evaluation/VISION_AGENT_RECORDED_20261120.md; only the path root changed).

GT = r004 gt_private frame_journal (target T foot position per frame). It is read ONLY here, on the scoring side, and never feeds
inference, ranking, prompts or frame selection."""
import json,math,glob
from pathlib import Path

from amidst.paths import local_dir

D = local_dir() / 'data'
CAT=json.load(open(D/'r004-cx7r-20261104-01a19f8b/bundle/safe_bundle/provenance/camera_catalog.json'))
CAMS={c['camera_id']:c for c in CAT['cameras']}
GTDIR={'A4-1':D/'r004-cx7r-20261104-01a19f8b/A4-1/gt_private/frame_journal.jsonl','B4-1':D/'r004-cx7r-20261104-01a19f8b/B4-1/gt_private/frame_journal.jsonl'}
TICK=200000
def project(cam,p):
    c=CAMS[cam]; M=c['camera_to_world']; dv=[p[i]-M[i][3] for i in range(3)]
    x,y,z=[sum(M[i][j]*dv[i] for i in range(3)) for j in range(3)]; d=-z
    if d<=c['clip_start'] or d>=c['clip_end']: return None
    return (c['cx']+c['fx']*x/d, c['cy']-c['fy']*y/d)
def gt_traj(label):
    out={}
    for l in open(GTDIR[label]):
        r=json.loads(l); out.setdefault(r['source_time_us'],r['foot_position_world_m'])
    return out
def t_body(cam,foot,H=1.75,W=0.3):
    pts=[]
    for dx,dy in [(W,0),(-W,0),(0,W),(0,-W),(0,0)]:
        for z in (0,H):
            p=project(cam,[foot[0]+dx,foot[1]+dy,z]); 
            if p is None: return None
            pts.append(p)
    us=[p[0] for p in pts]; vs=[p[1] for p in pts]; return [min(us),min(vs),max(us),max(vs)]
def visible(cam,foot):
    """T geometrically in view (foot-to-head body box intersects image by >=50% of its area); occlusion NOT modelled."""
    c=CAMS[cam]; b=t_body(cam,foot)
    if b is None: return False,None
    a=(b[2]-b[0])*(b[3]-b[1])
    if a<=0: return False,b
    ix=max(0,min(b[2],c['width'])-max(b[0],0))*max(0,min(b[3],c['height'])-max(b[1],0))
    return ix/a>=0.5,b
def load_index(label):
    d=glob.glob(str(D/f'demo-owned-v1/data/indexes/{label}'))[0]; m=json.load(open(d+'/detection_index.json'))
    obs={}
    for l in open(d+'/'+m['records_ref']):
        r=json.loads(l)
        for det in r['detections'] or []: obs[det['observation_id']]=(r['camera_id'],r['timestamp_us'],det['bbox_xyxy_px'],det['class_label'],det['score'])
    return obs
def box_on_target(box,body,margin=0.3):
    cx=(box[0]+box[2])/2; cy=(box[1]+box[3])/2; w=body[2]-body[0]; h=body[3]-body[1]
    return body[0]-margin*w<=cx<=body[2]+margin*w and body[1]-margin*h<=cy<=body[3]+margin*h
def score(label,resp,idx,gt,duration_us,min_score=0.3):
    """Per-tick rows. T "detected" in camera c at tick t = some index detection (score>=min_score) whose box centre lies in T's
    projected body box (GT foot -> pinhole). This implicitly handles walls/occlusion, which pure frustum geometry cannot."""
    sv=resp['single_view']; cams=cams_of(label)
    allbox={}
    for oid,(c,t,b,k,sc_) in idx.items():
        if sc_>=min_score: allbox.setdefault((c,t),[]).append(b)
    sel={}
    for s_ in resp['sightings']:
        if s_.get('selected_for_single_view',True):
            for oid in s_['observation_ids']:
                if oid in idx: c,t,b,k,_s=idx[oid]; sel.setdefault((c,t),[]).append(b)
    rows=[]
    for t in range(0,duration_us,TICK):
        foot=gt.get(t)
        if foot is None: continue
        det={};body={}
        for c in cams:
            body[c]=t_body(c,foot)
            det[c]=bool(body[c]) and any(box_on_target(b,body[c],0.0) for b in allbox.get((c,t),[]))
        td=[c for c in cams if det[c]]
        st=next((s_ for s_ in sv if s_['range_us'][0]<=t<s_['range_us'][1]),None)
        kind=st['kind'] if st else 'NONE'; cam=st.get('camera_id') if st else None
        if kind=='ON_CAMERA':
            boxes=sel.get((cam,t),[])
            if boxes:
                hit=body[cam] is not None and any(box_on_target(b,body[cam],0.0) for b in boxes)
                cls='CORRECT' if hit else ('WRONG_PERSON' if td else 'FALSE_LOCK')
            else:   # held through a detection flicker: credit if T was detected in that camera within +-0.6 s
                near=any(det_at(allbox,body_t(cam,gt,t+d),cam,t+d) for d in (-600000,-400000,-200000,0,200000,400000,600000))
                cls='CORRECT' if (det.get(cam) or near) else ('WRONG_PERSON' if td else 'FALSE_LOCK')
        else:
            cls='MISSED' if td else 'BLIND_OK'
        rows.append({'t_us':t,'kind':kind,'camera':cam,'t_visible':td,'cls':cls})
    return rows
def body_t(cam,gt,t):
    f=gt.get(t); return t_body(cam,f) if f else None
def det_at(allbox,body,cam,t):
    return bool(body) and any(box_on_target(b,body,0.0) for b in allbox.get((cam,t),[]))
def cams_of(label): return {'A4-1':{'CAM_ENTRY','CAM_EXT_CAR','CAM_EXT_CLEAR','CAM_W1'},'B4-1':{'CAM_BRANCH','CAM_R101_IN','CAM_W1','CAM_W2','CAM_WIDE'}}[label]
def metrics(rows):
    n=len(rows); tv=[r for r in rows if r['t_visible']]; sec=TICK/1e6
    cnt=lambda c:sum(r['cls']==c for r in rows)
    def episodes(c):
        e=0;prev=False
        for r in rows:
            cur=r['cls']==c; e+=cur and not prev; prev=cur
        return e
    return {'ticks':n,'ticks_target_detected':len(tv),
      'follow_rate':round(cnt('CORRECT')/len(tv),4) if tv else None,
      'lost_s_while_visible':round(cnt('MISSED')*sec,1),
      'wrong_person_ticks':cnt('WRONG_PERSON'),'wrong_person_s':round(cnt('WRONG_PERSON')*sec,1),
      'wrong_person_episodes':episodes('WRONG_PERSON'),
      'false_lock_s_while_blind':round(cnt('FALSE_LOCK')*sec,1),'false_lock_episodes':episodes('FALSE_LOCK'),
      'wrong_total_s':round((cnt('WRONG_PERSON')+cnt('FALSE_LOCK'))*sec,1)}
def switches(rows):
    """Camera-change events of the displayed single view: (t, from, to, correct_at_switch, latency_s since T became visible there)."""
    out=[];last=None
    vis_since={}
    for i,r in enumerate(rows):
        for c in r['t_visible']: vis_since.setdefault(c,r['t_us']) if (i==0 or c not in rows[i-1]['t_visible']) else None
        for c in list(vis_since):
            if c not in r['t_visible']: del vis_since[c]
        if r['kind']=='ON_CAMERA' and r['camera']!=last:
            c=r['camera']; ok=c in r['t_visible']
            lat=None
            if ok: lat=round((r['t_us']-vis_since[c])/1e6,1) if c in vis_since else None
            out.append({'t_s':r['t_us']/1e6,'from':last,'to':c,'T_visible_in_new_cam':ok,'latency_s_since_T_visible':lat,'T_visible_cams':r['t_visible']})
            last=c
    return out
