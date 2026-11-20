"""Offline, no LLM. Reads LOCAL D325 evidence read-only; GT used only for scoring/scene description."""
import json,sys,glob,collections,statistics,os
# Usage (repo root = ~/amidst, read-only): python analyze.py <out.json>
# Evidence root: $AMIDST_ARTIFACTS or ./local/evidence ; the LOCAL D325 scorer (scripts/score.py) is imported read-only.
E=os.path.join(os.environ.get('AMIDST_ARTIFACTS','local/evidence'),'eval-recorded-llm-20261118')
sys.path.insert(0,E+'/scripts')
import score as S
out={}
def runs(rows,pred):
    rs=[];cur=None
    for r in rows:
        if pred(r):
            if cur and r['t_us']-cur[1]==200000: cur[1]=r['t_us']
            else: cur=[r['t_us'],r['t_us']]; rs.append(cur)
    return [(a/1e6,(b+200000)/1e6) for a,b in rs]
for ev in ['A4-1','B4-1']:
    d=json.load(open(f'{E}/raw/RULE_{ev}_k0.json')); rows=d['tick_rows']
    idx=S.load_index(ev); gt=S.gt_traj(ev)
    per=collections.defaultdict(list)
    for oid,(c,t,b,k,sc) in idx.items():
        if sc>=0.3 and c in S.cams_of(ev): per[(c,t)].append(b)
    frames=len(per); multi=sum(1 for v in per.values() if len(v)>=2); maxn=max(len(v) for v in per.values())
    # non-target detection present (box not on GT body) per tick, any camera
    nontarget_ticks=0; both_ticks=0
    for r in rows:
        t=r['t_us']; foot=gt.get(t); nt=False
        for c in S.cams_of(ev):
            body=S.t_body(c,foot) if foot else None
            for b in per.get((c,t),[]):
                if not (body and S.box_on_target(b,body,0.0)): nt=True
        nontarget_ticks+=nt; both_ticks+= nt and bool(r['t_visible'])
    blind=runs(rows,lambda r: not r['t_visible'])
    missed=runs(rows,lambda r: r['cls']=='MISSED')
    # miss cause
    first_disp=min(s['range_us'][0] for s in d['single_view'] if s['kind']=='ON_CAMERA')
    sg=d['sightings']; cause=collections.Counter(); detail=[]
    for r in rows:
        if r['cls']!='MISSED': continue
        t=r['t_us']
        if t<first_disp: c='BEFORE_FIRST_SEED'
        else:
            cov=[s for s in sg if s['camera_id'] in r['t_visible'] and s['range_us'][0]<=t<s['range_us'][1]]
            c='CANDIDATE_UNSELECTED' if cov else 'NO_TRACKLET_FOR_VISIBLE_CAMERA'
        cause[c]+=1; detail.append((t/1e6,c,r['t_visible']))
    out[ev]={'duration_s':len(rows)*0.2,'cameras':len(S.cams_of(ev)),
        'det_frames':frames,'det_frames_multi_person':multi,'max_dets_per_frame':maxn,
        'ticks':len(rows),'ticks_target_detected':sum(1 for r in rows if r['t_visible']),
        'ticks_nontarget_detection_present':nontarget_ticks,'ticks_nontarget_and_target':both_ticks,
        'blind_runs_s':blind,'longest_blind_s':round(max(b-a for a,b in blind),1) if blind else 0,
        'missed_runs_s':missed,'longest_missed_s':round(max(b-a for a,b in missed),1),
        'rule_switches':len(d['switches']),'miss_cause_ticks':dict(cause),'miss_detail':detail,
        'cls':dict(collections.Counter(r['cls'] for r in rows))}
    # candidate distribution from requests (terra k0) and colours
    q=json.load(open(f'{E}/raw/terra6.1_{ev}_k0.json'))['requests']
    dist=collections.Counter(); col=collections.Counter()
    for r in q:
        el=[x for x in r.get('candidates',[]) if x.get('rule_eligible')]
        dist[f"{r['decision_point'][:3]}:{len(el)}"]+=1
        for x in r.get('candidates',[]): col['cand_colors='+'+'.join(x.get('colors') or [])]+=1
        col['current_colors='+'+'.join(r['current'].get('colors') or [])]+=1
        col['graph_edge_false']+=sum(1 for x in r.get('candidates',[]) if x.get('graph_edge') is False)
    out[ev]['dp_candidates']=dict(dist); out[ev]['colors']=dict(col)
    out[ev]['graph_status']=sorted({r['topology']['graph_status'] for r in q})
# latency over all LLM attempts
lat=collections.defaultdict(list); oc=collections.Counter()
for f in sorted(glob.glob(E+'/raw/*6.1_*_k*.json')):
    d=json.load(open(f)); m=d['model']
    for rec in d['decision_records']:
        for a in rec['attempts']:
            oc[(m,a['outcome'])]+=1
            if a['outcome']=='OK': lat[m].append(a['wall_ms'])
out['latency_ok_ms']={m:{'n':len(v),'p50':round(statistics.median(v)),'p95':round(sorted(v)[int(0.95*(len(v)-1))]),'min':round(min(v)),'max':round(max(v))} for m,v in lat.items()}
out['latency_raw']={m:v for m,v in lat.items()}
out['attempt_outcomes']={f'{m}:{o}':n for (m,o),n in oc.items()}
json.dump(out,open(sys.argv[1],'w'),indent=1,default=str)
for ev in ['A4-1','B4-1']:
    print(ev,{k:v for k,v in out[ev].items() if k not in('miss_detail',)})
print(out['latency_ok_ms'],out['attempt_outcomes'])
