"""SYNTHETIC evidence decision table and source-grid adversarial cases."""
from copy import deepcopy
import hashlib
import json
import pytest
from amidst.q1q5.detection_index import content_hash,_ranges
from amidst.q1q5.q4_evidence import EvidenceError,candidate_evidence
from amidst.q1q5.store import DetectionSnapshot,canonical_hash
from test_detection_index import build


def fixture(states=('STRONG','WEAK','NONE','UNKNOWN'),stride=1):
    artifact=build(stride_samples=stride);m=deepcopy(artifact.manifest);rows=[json.loads(x) for x in artifact.records_bytes.splitlines()]
    inferred=[];absent=[]
    for row,state in zip(rows,states):
        if row['frame_state']=='NOT_SAMPLED':continue
        if state in {'MISSING','NOT_INFERRED'}:
            row.update(frame_state=state,state_reason='SYNTHETIC' if state=='NOT_INFERRED' else None,detections=None)
            absent.append({'range_us':[row['timestamp_us'],min(800000,row['timestamp_us']+200000*stride)],'reason':state})
        else:
            row['detections']=[d for d in row['detections'] if d['class_label']=='person'] if state is not None else []
            for d in row['detections']:d['color']['verdicts']['red']=state
            inferred.append([row['timestamp_us'],min(800000,row['timestamp_us']+200000*stride)])
    meta=m['sampling']['per_camera'][0];meta['inferred_ranges_us']=_ranges(inferred);meta['not_inferred']=absent
    key=content_hash(m,('index_id','content_sha256','records_ref','records_file_sha256','stats'))[:16]
    m['index_id']=f"detidx:rSYN:SYNTHETIC_RUN:{key}"
    for row in rows:
        for i,d in enumerate(row['detections'] or []):d['observation_id']=f"obs:{key}:CAM_SYN:{row['frame_index']}:{i}"
    raw=b''.join(json.dumps(r,sort_keys=True).encode()+b'\n' for r in rows);m['records_file_sha256']=hashlib.sha256(raw).hexdigest();m['content_sha256']=content_hash(m,('index_id','content_sha256','stats'))
    return DetectionSnapshot(m,tuple(rows))


def snapshot(window=(0,800000),truncated=None,camera='CAM_SYN'):
    c={'camera_id':camera,'rank':1,'relation':'UNKNOWN','transition_id':'T_SYN','region_path':['R_SYN'],'window_us':list(window),'window_truncated_us':truncated or [],'path_traversability':'APPROVED_WALKABLE','path_has_unknown_state':False,'ranking_basis':{'relation_tier':4,'overlap_area_m2':None,'camera_id':camera},'alternative_transition_ids':[]}
    d={'schema_version':'q-demo.candidate-snapshot.v1','session_id':'SYNTHETIC','exit_resolution':'UNIQUE','candidates':[c],'excluded_transitions':[],'candidate_set_complete':True,'truncated':False,'truncated_count':0};h=canonical_hash(d);d['candidate_snapshot_sha256']=h;c['candidate_ref']=f'cand:{h[:16]}:1';return d


def evidence(index=None,snap=None,**kwargs):
    index=index or fixture();snap=snap or snapshot();args=dict(expected_index_sha256=index.manifest['content_sha256'],query_min_score=.5,color_label='red',evidence_max_observations=2,switch_min_presence='MATCH_STRONG',decision_time_us=0,available_ranges_us=[[0,800000]]);args.update(kwargs)
    return candidate_evidence(index,snap,snap['candidates'][0]['candidate_ref'],**args)


@pytest.mark.parametrize('states,presence,complete',[
    (('STRONG','MISSING','NOT_INFERRED',None),'MATCH_STRONG',False),
    (('WEAK',None,None,None),'MATCH_WEAK',True),
    (('NONE','UNKNOWN',None,None),'PERSON_COLOR_UNKNOWN',True),
    (('NONE','NONE',None,None),'PERSON_NO_COLOR_MATCH',True),
    ((None,None,None,None),'NO_PERSON_DETECTED',True),
    (('NONE','MISSING',None,None),'PARTIAL_EVIDENCE',False),
    (('MISSING','NOT_INFERRED','MISSING','NOT_INFERRED'),'NOT_EVALUATED',False),
])
def test_presence_table_never_uses_partial_coverage_for_negative(states,presence,complete):
    r=evidence(fixture(states));assert r['target_presence']==presence and r['coverage_complete']==complete
    assert canonical_hash(r,exclude=('evidence_sha256','stats'))==r['evidence_sha256']


def test_no_color_has_null_verdict_but_strong_presence_and_earliest_guard():
    r=evidence(color_label=None,decision_time_us=400000)
    assert r['target_presence']=='MATCH_STRONG' and all(o['color_verdict'] is None for o in r['best_observations'])
    assert r['entry_timestamp_us']==400000


def test_best_display_cap_never_selects_entry_or_backdates_playback():
    r=evidence(fixture(('STRONG','WEAK','STRONG',None)),decision_time_us=200000,evidence_max_observations=1)
    assert r['best_observations'][0]['timestamp_us']==0 and r['entry_timestamp_us']==400000
    late=evidence(fixture(('STRONG',None,None,None)),decision_time_us=200000)
    assert late['target_presence']=='MATCH_STRONG' and late['entry_observation_id'] is None


def test_weak_guard_is_explicit_and_does_not_strengthen_verdict():
    r=evidence(fixture(('WEAK',None,None,None)),switch_min_presence='MATCH_WEAK')
    assert r['target_presence']=='MATCH_WEAK' and r['entry_timestamp_us']==0


def test_unsampled_grid_cells_are_reported_but_not_in_expected_n():
    r=evidence(fixture(stride=2));assert r['frames']=={'evaluated':2,'not_sampled':2,'not_inferred':0,'missing':0}
    assert r['coverage_complete']


def test_empty_or_unbound_camera_is_not_evaluated_and_requires_explicit_clipping():
    r=evidence(snap=snapshot(truncated=[[0,800000]]),available_ranges_us=[])
    assert r['target_presence']=='NOT_EVALUATED' and not r['coverage_complete'] and sum(r['frames'].values())==0
    r=evidence(snap=snapshot(truncated=[[0,800000]],camera='UNBOUND'))
    assert r['target_presence']=='NOT_EVALUATED'


def test_partial_window_preserves_original_window_and_counts_only_available_time():
    snap=snapshot(window=(0,1000000),truncated=[[800000,1000000]])
    r=evidence(snap=snap);assert r['window_us']==[0,1000000] and r['frames']['evaluated']==4


@pytest.mark.parametrize('change',[{'query_min_score':.2},{'color_label':'purple'},{'evidence_max_observations':0},{'switch_min_presence':'UNKNOWN'},{'decision_time_us':-1},{'expected_index_sha256':'0'*64},{'available_ranges_us':[[0,1],[0,800000]]}])
def test_invalid_parameters_and_bindings_fail_closed(change):
    with pytest.raises(EvidenceError):evidence(**change)


@pytest.mark.parametrize('case',['missing_row','timestamp','observation','frame_ref','snapshot','color','bbox','duplicate','clipping'])
def test_tampered_or_incomplete_evidence_is_not_a_negative(case):
    index=fixture();snap=snapshot();rows=deepcopy(list(index.records))
    if case=='missing_row':rows.pop()
    elif case=='timestamp':rows[0]['timestamp_us']=1
    elif case=='observation':rows[0]['detections'][0]['observation_id']='obs:WRONG'
    elif case=='frame_ref':rows[0]['frame_ref']='frame:OTHER:CAM_SYN:0'
    elif case=='snapshot':snap['candidates'][0]['camera_id']='OTHER'
    elif case=='color':rows[0]['detections'][0]['color']=None
    elif case=='bbox':rows[0]['detections'][0]['bbox_xyxy_px']=[0,0,0,0]
    elif case=='duplicate':rows.append(deepcopy(rows[0]))
    elif case=='clipping':snap=snapshot(window=(0,1000000))
    with pytest.raises(EvidenceError):evidence(DetectionSnapshot(index.manifest,tuple(rows)),snap)



def test_malformed_metadata_is_classified_integrity_error_not_no_person():
    index=fixture();m=deepcopy(index.manifest);m.pop('detector');m['content_sha256']=content_hash(m,('index_id','content_sha256','stats'))
    with pytest.raises(EvidenceError) as exc:evidence(DetectionSnapshot(m,index.records))
    assert exc.value.code=='DataIntegrityError'
