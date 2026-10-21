"""SYNTHETIC index query tests; no questions, expected human labels or real RGB."""
from copy import deepcopy
import json
import pytest
from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.store import DetectionSnapshot,canonical_hash
from amidst.q1q5.q1_search import SearchError,search_cameras
from test_detection_index import build,safe_run,Detector


def fixture(cameras=('CAM_SYN',),missing=False,stride=1):
    run=safe_run();run.camera_ids=set(cameras)
    if missing:
        original=run.rgb_record;run.rgb_record=lambda c,i:None if i==1 else original(c,i)
        run.files['rgb_index']['missing']=[{'camera_id':c,'frame_index':1} for c in cameras]
    a=build(run=run,stride_samples=stride)
    return DetectionSnapshot(a.manifest,tuple(json.loads(x) for x in a.records_bytes.splitlines()))


def clock():
    d={'schema_version':'q-demo.clock-mapping.v1','run_id':'SYNTHETIC_RUN','clock_id':'SYNTHETIC_CLOCK','timezone':'Asia/Taipei','wall_origin':'2026-11-01T13:00:00+08:00','mapping_kind':'DECLARED_DEMO_CLOCK','t0_us':0,'rate':1,'source_duration_us':800000,'mapping_version':'SYNTHETIC','declaration_source':'SYNTHETIC','declared_by':'SYNTHETIC','declared_at':'2026-10-21T00:00:00+08:00'}
    d['content_sha256']=canonical_hash(d);return ClockMapping(d)


def aliases(index):
    d={'schema_version':'q-demo.supported-classes.v1','class_labels':['person','car'],'class_map_sha256':index.manifest['detector']['class_map']['content_sha256'],'aliases':{'人':'person','車':'car'},'color_labels':['red','blue']}
    d['content_sha256']=canonical_hash(d);return d


def parameters(index,approved=True,gap=0):
    d={'schema_version':'q-demo.parameter-set.v1','applies_to':{'scene_revision':'rSYN','run_ids':['SYNTHETIC_RUN'],'detection_index_ids':[index.manifest['index_id']],'index_interval_us':200000},'parameters':[{'name':'segment_merge_gap_us','value':gap,'unit':'us','status':'APPROVED' if approved else 'PROPOSED','proposed_by':'SYNTHETIC','proposal_ref':'synthetic://test'}],'approval':{'status':'APPROVED' if approved else 'PROPOSED','approved_by':'SYNTHETIC','approval_ref':'synthetic://test' if approved else None}}
    d['content_sha256']=canonical_hash(d);d['parameter_set_id']='pset:q-demo:'+d['content_sha256'][:16];return d


def request():
    return {'schema_version':'q-demo.q1-request.v1','session_ref':'SYNTHETIC','scene_id':'SYNTHETIC_SCENE','run_ids':['SYNTHETIC_RUN'],'time':{'kind':'SOURCE','run_id':'SYNTHETIC_RUN','range_us':[0,800000]},'condition':{'class_label':'person','min_count_per_frame':1,'color':None,'query_min_score':.5},'camera_ids':None,'region_ids':None,'page_size':20,'cursor':None,'origin':'MANUAL'}


def search(req=None,index=None,**kwargs):
    i=index or fixture();a=aliases(i);p=parameters(i)
    args=dict(index=i,expected_index_sha256=i.manifest['content_sha256'],aliases=a,expected_aliases_sha256=a['content_sha256'],clock_mapping=clock(),parameter_set=p,expected_parameter_sha256=p['content_sha256'],camera_catalog_ids=[m['camera_id'] for m in i.manifest['sampling']['per_camera']],media_token_for_frame=lambda ref:'SYNTHETIC-'+canonical_hash(ref));args.update(kwargs)
    return search_cameras(req or request(),**args)


def test_complete_search_reproducible_counts_and_half_open_segment():
    i=fixture();before=deepcopy(i);r=search(index=i)
    assert r['status']=='READY' and r['results_total']==r['returned_count']==1
    assert r['results'][0]['matched_segments'][0]['range_us']==[0,800000]
    assert r['results'][0]['matched_segments'][0]['matched_frames']==4
    assert r['results'][0]['matched_segments'][0]['representative']['frame_ref'].endswith(':0')
    assert r==search(index=i) and i==before and not r['agent_used'] and r['identity_verdict']=='UNCONFIRMED'
    assert canonical_hash(r,exclude=('output_sha256','stats'))==r['output_sha256']


def test_origin_does_not_change_query_or_output_hash():
    a=search();q=request();q['origin']='Q3_PARSED';b=search(q)
    assert a==b


@pytest.mark.parametrize('label,status',[('人','READY'),('car','NO_MATCH'),('tree','UNSUPPORTED_CLASS')])
def test_supported_zero_hit_and_unsupported_are_distinct(label,status):
    q=request();q['condition']['class_label']=label;r=search(q)
    assert r['status']==status
    if status=='NO_MATCH':assert r['no_match_cameras'][0]['coverage']['evaluated_frames']==4


@pytest.mark.parametrize('label,color,status',[('person','red','READY'),('person','blue','NO_MATCH'),('car','red','UNSUPPORTED_CONDITION'),('person','green','UNSUPPORTED_CONDITION')])
def test_color_support_and_observed_predicate(label,color,status):
    q=request();q['condition'].update(class_label=label,color={'label':color,'min_verdict':'STRONG'})
    assert search(q)['status']==status


def test_missing_source_is_partial_never_negative():
    q=request();q['condition']['class_label']='car';r=search(q,fixture(missing=True))
    assert r['status']=='PARTIAL' and not r['no_match_cameras'] and r['not_evaluated_cameras']


def test_unindexed_camera_is_visible_not_silently_omitted():
    r=search(camera_catalog_ids=['CAM_SYN','UNBOUND']);assert r['status']=='PARTIAL'
    assert r['not_evaluated_cameras']==[{'camera_id':'UNBOUND','reason':'NO_INDEX_BINDING'}]


def test_stride_off_grid_not_sampled_does_not_pretend_model_failure():
    r=search(index=fixture(stride=2));assert r['status']=='READY'
    assert r['results'][0]['coverage']==dict(evaluated_frames=2,not_sampled_frames=2,not_inferred_frames=0,missing_frames=0)


def test_proposed_parameters_are_partial_and_unset_gap_unknown():
    i=fixture();p=parameters(i,False);r=search(index=i,parameter_set=p,expected_parameter_sha256=p['content_sha256'])
    assert r['status']=='PARTIAL' and r['reason']=='PARAMETERS_NOT_APPROVED'
    p=parameters(i,gap=None);assert search(index=i,parameter_set=p,expected_parameter_sha256=p['content_sha256'])['status']=='UNKNOWN'


def test_wall_scope_partial_and_outside_source_remain_distinct():
    q=request();q['time']={'kind':'WALL','wall_range':['2026-11-01T12:59:59+08:00','2026-11-01T13:00:00.400000+08:00']}
    assert search(q)['reason']=='TIME_SCOPE_PARTIAL'
    q['time']={'kind':'SOURCE','run_id':'SYNTHETIC_RUN','range_us':[800000,1000000]};assert search(q)['status']=='OUT_OF_RANGE'


def test_missing_clock_and_multi_run_have_no_guessed_binding():
    assert search(clock_mapping=None)['reason']=='CLOCK_MAPPING_MISSING'
    q=request();q['run_ids'].append('OTHER');r=search(q);assert r['status']=='UNKNOWN' and not r['results']


def test_pagination_preserves_total_and_absolute_rank():
    i=fixture(('B','A'));q=request();q['page_size']=1;first=search(q,i)
    assert first['results'][0]['camera_id']=='A' and first['results_total']==2 and first['next_cursor']
    q['cursor']=first['next_cursor'];last=search(q,i)
    assert last['results'][0]['camera_id']=='B' and last['results'][0]['rank']==2 and last['results_total']==2 and last['returned_count']==1 and last['next_cursor'] is None
    q['condition']['query_min_score']=.6
    with pytest.raises(SearchError):search(q,i)


@pytest.mark.parametrize('change',[{'actor_id':'FORBIDDEN'},{'page_size':0},{'cursor':'garbage'},{'camera_ids':['OUTSIDE']},{'origin':'OTHER'}])
def test_query_overreach_invalid_cursor_and_scope_fail_closed(change):
    q=request();q.update(change)
    with pytest.raises(SearchError):search(q)


@pytest.mark.parametrize('score',[.2,None,float('nan'),True])
def test_score_floor_and_explicit_value_required(score):
    q=request();q['condition']['query_min_score']=score
    with pytest.raises(SearchError):search(q)


@pytest.mark.parametrize('case',['missing_row','duplicate','frame_ref','timestamp','observation','grid','alias_pin','param_pin'])
def test_corruption_is_integrity_error_not_no_match(case):
    i=fixture();rows=deepcopy(list(i.records));kw={}
    if case=='missing_row':rows.pop()
    elif case=='duplicate':rows.append(deepcopy(rows[0]))
    elif case=='frame_ref':rows[0]['frame_ref']='frame:OTHER:CAM_SYN:0'
    elif case=='timestamp':rows[0]['timestamp_us']=1
    elif case=='observation':rows[0]['detections'][0]['observation_id']='obs:WRONG'
    elif case=='grid':rows[0]['frame_state']='NOT_SAMPLED'
    elif case=='alias_pin':kw['expected_aliases_sha256']='0'*64
    elif case=='param_pin':kw['expected_parameter_sha256']='0'*64
    with pytest.raises(SearchError):search(index=DetectionSnapshot(i.manifest,tuple(rows)),**kw)


def test_missing_region_graph_never_ignores_requested_filter():
    q=request();q['region_ids']=['REGION_SYN'];assert search(q)['reason']=='GRAPH_NOT_AVAILABLE'


def test_region_filter_uses_only_static_graph_and_preserves_draft_reason():
    from test_graphs import fixture as graph_fixture,seal,load
    r,c=graph_fixture();r['scene_id']=c['scene_id']='SYNTHETIC_SCENE';seal(r,c)
    q=request();q['region_ids']=['R1'];i=fixture(('A','B','D'))
    result=search(q,i,graphs=load(r,c))
    assert result['status']=='PARTIAL' and result['reason']=='GRAPH_NOT_APPROVED'
    assert result['resolved_scope']['camera_ids']==['A','D']


def test_segment_gap_is_explicit_and_representative_uses_score_then_time():
    class Pattern(Detector):
        def __call__(self,image):
            self.calls+=1
            return [] if self.calls==2 else [{'class_id':0,'bbox_xyxy_px':[0,0,8,8],'score':.95 if self.calls==3 else .9}]
    a=build(predictor=Pattern());i=DetectionSnapshot(a.manifest,tuple(json.loads(x) for x in a.records_bytes.splitlines()))
    split=search(index=i)['results'][0]['matched_segments'];assert [x['range_us'] for x in split]==[[0,200000],[400000,800000]]
    ps=parameters(i,gap=200000);merged=search(index=i,parameter_set=ps,expected_parameter_sha256=ps['content_sha256'])['results'][0]['matched_segments']
    assert len(merged)==1 and merged[0]['matched_frames']==3 and merged[0]['evaluated_frames']==4
    assert merged[0]['representative']['frame_ref'].endswith(':2')
