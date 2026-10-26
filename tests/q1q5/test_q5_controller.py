"""SYNTHETIC index-tick/guard tests, never human questions or event-run answers."""
import itertools
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from amidst.q1q5.graphs import load_graphs
from amidst.q1q5.q5_controller import (
    ControllerError,
    RuleController,
    RuntimeBindings,
    file_hash,
    jsonl,
)
from test_detection_index import build, safe_run
from test_graphs import fixture as graph_fixture
from test_graphs import seal as seal_graphs

from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.detection_index import _ranges
from amidst.q1q5.store import DetectionSnapshot, canonical_hash


def repin(index):
    m=deepcopy(index.manifest);records=deepcopy(list(index.records))
    key=canonical_hash(m,exclude=('index_id','content_sha256','records_ref','records_file_sha256','stats'))[:16]
    m['index_id']=f"detidx:{m['scene_revision']}:{m['run_id']}:{key}"
    for row in records:
        for i,o in enumerate(row['detections'] or []):o['observation_id']=f"obs:{key}:{row['camera_id']}:{row['frame_index']}:{i}"
    raw=jsonl(records);m['records_file_sha256']=file_hash(raw);m['content_sha256']=canonical_hash(m,exclude=('index_id','content_sha256','stats'))
    return DetectionSnapshot(m,tuple(records))


def fixture(pattern=None,cameras=('A','B'),frames=10,stride=1):
    run=safe_run();raw=run.read_rgb(None,0);run.camera_ids=set(cameras)
    run.manifest['sampling'].update(duration_s=frames/5,sample_count_per_camera=frames)
    run.rgb_record=lambda camera,i:{'camera_id':camera,'frame_index':i,'timestamp_s':i/5,'file_sha256':file_hash(raw)}
    artifact=build(run=run,stride_samples=stride);m=deepcopy(artifact.manifest);records=[json.loads(x) for x in artifact.records_bytes.splitlines()]
    pattern=pattern if pattern is not None else {'A':{0:'STRONG',1:'STRONG'},'B':{i:'STRONG' for i in range(5,frames)}}
    for row in records:
        if row['frame_state']=='NOT_SAMPLED':continue
        value=pattern.get(row['camera_id'],{}).get(row['frame_index'])
        row['detections']=[o for o in row['detections'] if o['class_label']=='person'] if value not in {None,'MISSING','NOT_INFERRED'} else []
        if value in {'MISSING','NOT_INFERRED'}:row.update(frame_state=value,state_reason='SYNTHETIC',detections=None)
        for o in row['detections'] or []:o['color']['verdicts']['red']=value
    for meta in m['sampling']['per_camera']:
        rows=[r for r in records if r['camera_id']==meta['camera_id'] and r['frame_state']!='NOT_SAMPLED']
        step=meta['index_interval_us'];meta['inferred_ranges_us']=_ranges([[r['timestamp_us'],min(frames*200000,r['timestamp_us']+step)] for r in rows if r['frame_state']=='INFERRED'])
        meta['not_inferred']=[{'range_us':[r['timestamp_us'],min(frames*200000,r['timestamp_us']+step)],'reason':r['frame_state']} for r in rows if r['frame_state']!='INFERRED']
    index=repin(DetectionSnapshot(m,tuple(records)));m=index.manifest
    r,c=graph_fixture();r['scene_id']=c['scene_id']=m['scene_id']
    for doc in [r,c]:doc.update(approval_status='APPROVED',approval_ref='SYNTHETIC_TEST_ONLY')
    seal_graphs(r,c);graphs=load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'])
    clock={'schema_version':'q-demo.clock-mapping.v1','run_id':m['run_id'],'clock_id':m['clock_id'],'timezone':'Asia/Taipei','wall_origin':'2026-11-01T13:00:00+08:00','mapping_kind':'DECLARED_DEMO_CLOCK','t0_us':0,'rate':1,'source_duration_us':frames*200000,'mapping_version':'SYNTHETIC','declaration_source':'SYNTHETIC','declared_by':'SYNTHETIC','declared_at':'2026-10-21T00:00:00+08:00'};clock['content_sha256']=canonical_hash(clock)
    interval=200000*stride
    values={'link_iou_min':.3,'link_center_dist_max_diag_ratio':.5,'link_max_gap_us':interval*3,'link_min_score':.4,'link_color_rule':'NOT_NONE','link_ambiguity_margin':.05,
            'query_min_score':.5,'top_k':3,'search_window_us':1200000,'research_interval_us':interval*2,'session_max_research_rounds':8,'switch_min_presence':'MATCH_STRONG','evidence_max_observations':3,'fallback_budget_ms':1000,'agent_max_rounds':3,'agent_total_budget_ms':5000,'exit_rule':{'method':'BBOX_BOTTOM_MIDPOINT','boundary_inclusive':True}}
    ps={'schema_version':'q-demo.parameter-set.v1','applies_to':{'scene_revision':m['scene_revision'],'run_ids':[m['run_id']],'detection_index_ids':[m['index_id']],'index_interval_us':interval},
        'parameters':[{'name':k,'value':v,'status':'APPROVED','unit':'SYNTHETIC','proposed_by':'SYNTHETIC','proposal_ref':'synthetic://test'} for k,v in values.items()],
        'approval':{'status':'APPROVED','approved_by':'SYNTHETIC','approval_ref':'synthetic://test'}}
    seal_parameters(ps);media={camera:[[0,frames*200000]] for camera in cameras}
    return RuntimeBindings(index,m['content_sha256'],graphs,r['content_sha256'],c['content_sha256'],ClockMapping(clock),clock['content_sha256'],ps,ps['content_sha256'],media,canonical_hash(media))


def seal_parameters(ps):
    ps['content_sha256']=canonical_hash(ps,exclude=('parameter_set_id','content_sha256','stats'));ps['parameter_set_id']='pset:q-demo:'+ps['content_sha256'][:16]


def change_parameter(bindings,name,value=None,status=None):
    ps=deepcopy(bindings.parameter_set);row=next(x for x in ps['parameters'] if x['name']==name)
    if value is not None:row['value']=value
    if status is not None:row['status']=status
    seal_parameters(ps);return replace(bindings,parameter_set=ps,parameter_sha256=ps['content_sha256'])


def request(b):
    return {'schema_version':'q-demo.q2-request.v1','session_ref':'SYNTHETIC','scene_id':b.index.manifest['scene_id'],'run_ids':[b.clock.run_id],
            'time':{'kind':'SOURCE','run_id':b.clock.run_id,'range_us':[0,b.clock.duration_us]},
            'seed':{'kind':'APPEARANCE','class_label':'person','color':{'label':'red','min_verdict':'STRONG'}},'switch_mode':'RULE_ONLY','parameter_set_id':b.parameter_set['parameter_set_id']}


def seed_id(b,camera='A',frame=0):
    return next(o['observation_id'] for row in b.index.records if row['camera_id']==camera and row['frame_index']==frame for o in row['detections'] or [] if o['class_label']=='person')


def port(calls):
    """Minimal frozen Q4 stand-in for controller tests; real Q4 integration is separate."""
    def evidence(index,snapshot,ref,context):
        candidate=next(c for c in snapshot['candidates'] if c['candidate_ref']==ref);calls.append((candidate['camera_id'],context['decision_time_us']))
        rows=[r for r in index.records if r['camera_id']==candidate['camera_id'] and candidate['window_us'][0]<=r['timestamp_us']<candidate['window_us'][1] and any(a<=r['timestamp_us']<b for a,b in context['available_ranges_us'])]
        counts={k:sum(r['frame_state']==state for r in rows) for k,state in [('evaluated','INFERRED'),('not_sampled','NOT_SAMPLED'),('not_inferred','NOT_INFERRED'),('missing','MISSING')]}
        observations=[]
        for row in rows:
            for o in row['detections'] or []:
                if o['class_label']!='person' or o['score']<context['query_min_score']:continue
                observations.append({'observation_id':o['observation_id'],'frame_ref':row['frame_ref'],'timestamp_us':row['timestamp_us'],'score':o['score'],
                    'color_verdict':o['color']['verdicts'][context['color_label']] if context['color_label'] else None,'bbox_xyxy_px':o['bbox_xyxy_px']})
        n=counts['evaluated']+counts['not_inferred']+counts['missing'];complete=n>0 and counts['evaluated']==n
        verdicts={o['color_verdict'] for o in observations}
        presence=('NOT_EVALUATED' if counts['evaluated']==0 else 'MATCH_STRONG' if observations and (context['color_label'] is None or 'STRONG' in verdicts)
                  else 'MATCH_WEAK' if 'WEAK' in verdicts else 'PERSON_COLOR_UNKNOWN' if 'UNKNOWN' in verdicts
                  else 'PARTIAL_EVIDENCE' if not complete else 'PERSON_NO_COLOR_MATCH' if observations else 'NO_PERSON_DETECTED')
        legal=sorted([o for o in observations if o['timestamp_us']>=context['decision_time_us'] and (context['color_label'] is None or o['color_verdict']=='STRONG')],key=lambda o:(o['timestamp_us'],-o['score'],o['observation_id']))
        entry=legal[0] if legal and presence=='MATCH_STRONG' else None
        observations.sort(key=lambda o:({'STRONG':0,'WEAK':1,'UNKNOWN':2,'NONE':3,None:0}[o['color_verdict']],-o['score'],o['timestamp_us'],o['observation_id']))
        d={'schema_version':'q-demo.candidate-evidence.v1','candidate_ref':ref,'camera_id':candidate['camera_id'],'window_us':candidate['window_us'],
           'target_presence':presence,'frames':counts,'coverage_complete':complete,'partial_basis':('PERSON_NO_COLOR_MATCH' if observations else 'NO_PERSON_DETECTED') if presence=='PARTIAL_EVIDENCE' else None,
           'decision_time_us':context['decision_time_us'],'entry_observation_id':entry['observation_id'] if entry else None,'entry_timestamp_us':entry['timestamp_us'] if entry else None,
           'best_observations':observations[:context['evidence_max_observations']],'matching_observation_count':len(legal),
           'first_match_us':min((o['timestamp_us'] for o in observations if context['color_label'] is None or o['color_verdict'] in {'STRONG','WEAK'}),default=None)}
        d['evidence_sha256']=canonical_hash(d);return d
    return evidence


def run(b=None,req=None,provider=None,selected=True):
    b=b or fixture();calls=[]
    controller=RuleController(req or request(b),bindings=b,evidence_provider=provider or port(calls),selected_observation_id=seed_id(b) if selected else None)
    return controller.run(),calls


def test_index_ticks_continue_same_camera_without_agent_or_evidence_calls():
    b=fixture({'A':{i:'STRONG' for i in range(10)}});r,calls=run(b)
    assert r.response['status']=='COMPLETE' and calls==[] and len(r.response['timeline'])==1
    assert r.response['timeline'][0]['range_us']==[0,2000000] and len(r.links_bytes.splitlines())==9
    assert not r.response['agent_used'] and r.response['identity_verdict']=='UNCONFIRMED'


def test_disappearance_search_guard_and_forward_gap_switch():
    r,calls=run();assert r.response['status']=='COMPLETE' and calls==[('B',800000)]
    timeline=r.response['timeline'];assert [s['kind'] for s in timeline]==['ON_CAMERA','GAP','ON_CAMERA']
    assert timeline[1]['range_us']==[400000,1000000] and timeline[1]['position'] is None and timeline[1]['camera_shown']=='A'
    assert timeline[2]['camera_id']=='B' and timeline[2]['range_us']==[1000000,2000000]
    decisions=[json.loads(x) for x in r.decisions_bytes.splitlines()];switch=next(d for d in decisions if d['executed_action']=='SWITCH')
    assert switch['decision_time_us']==800000 and switch['source_time_us']==800000 and switch['state_after']=='SWITCHING' and switch['session_agent_rounds_used']==0
    assert r.response['decisions_sha256']==file_hash(r.decisions_bytes) and r.response['links_sha256']==file_hash(r.links_bytes)
    assert canonical_hash(r.response,exclude=('output_sha256','stats'))==r.response['output_sha256']


def test_rule_replay_hashes_ignore_wall_latency_and_budget_does_not_abort(monkeypatch):
    import amidst.q1q5.q5_controller as module
    one,_=run();ticks=itertools.count(step=10);monkeypatch.setattr(module.time,'perf_counter',lambda:next(ticks));two,calls=run()
    assert two.response['stats']['latency_ms']['fallback']>1000 and calls
    assert one.response['output_sha256']==two.response['output_sha256'] and one.decisions_bytes==two.decisions_bytes and one.links_bytes==two.links_bytes


def test_blue_evidence_excluded_before_second_candidate_cut():
    pattern={'A':{0:'STRONG',1:'STRONG'},'B':{i:'NONE' for i in range(5,10)},'E':{i:'STRONG' for i in range(6,10)}}
    r,calls=run(fixture(pattern,cameras=('A','B','E')))
    assert [c[0] for c in calls]==['B','E'] and r.response['timeline'][-1]['camera_id']=='E'
    decision=next(json.loads(x) for x in r.decisions_bytes.splitlines() if json.loads(x)['executed_action']=='SWITCH')
    assert decision['candidates_considered'][0]['exclusion_reason']=='CONDITION_MISMATCH'


def test_unqueried_after_accepted_switch_is_not_evaluated():
    pattern={c:{i:'STRONG' for i in range(5,10)} for c in ['B','D','E']};pattern['A']={0:'STRONG',1:'STRONG'}
    r,calls=run(fixture(pattern,cameras=('A','B','D','E')));assert [c[0] for c in calls]==['D']
    decision=next(json.loads(x) for x in r.decisions_bytes.splitlines() if json.loads(x)['executed_action']=='SWITCH')
    assert len(decision['candidates_considered'])==1 and decision['candidates_considered'][-1]['action']=='SWITCH'
    unqueried=[x for x in r.diagnostics if x.get('reason')=='NOT_QUERIED_AFTER_ACCEPTED_SWITCH']
    assert len(unqueried)==2 and all(x['target_presence']=='NOT_EVALUATED' and x['evidence_sha256'] is None for x in unqueried)


@pytest.mark.parametrize('verdict',['WEAK','UNKNOWN','NONE'])
def test_below_guard_never_cuts_and_can_reacquire_origin_at_current_time(verdict):
    pattern={'A':{0:'STRONG',1:'STRONG',**{i:'STRONG' for i in range(6,10)}},'B':{i:verdict for i in range(5,10)}}
    r,calls=run(fixture(pattern));decisions=[json.loads(x) for x in r.decisions_bytes.splitlines()]
    assert not any(d['executed_action']=='SWITCH' for d in decisions)
    assert any(d['executed_action']=='RETURN_TO_ORIGIN' and d['source_time_us']==800000 for d in decisions)
    assert r.response['timeline'][-1]['camera_id']=='A' and r.response['timeline'][-1]['range_us'][0]==1200000
    links=[json.loads(x) for x in r.links_bytes.splitlines()];assert len({x['local_segment_id'] for x in links})>1


def test_session_research_limit_bounds_new_searches_without_fake_negative():
    b=fixture({'A':{0:'STRONG',1:'STRONG'},'B':{i:'WEAK' for i in range(5,10)}});b=change_parameter(b,'session_max_research_rounds',1)
    r,_=run(b);assert r.response['status']=='ENDED_BY_LIMIT' and r.response['reason']=='SESSION_RESEARCH_ROUND_LIMIT'
    assert len(r.snapshots)==1 and r.response['timeline'][-1]['position'] is None


def test_multiple_appearance_seeds_require_user_selection():
    r,calls=run(selected=False);assert r.response['status']=='UNKNOWN' and r.response['reason']=='SEED_SELECTION_REQUIRED'
    assert len(r.seed_candidates)>1 and not r.response['timeline'] and not calls


def test_grid_mismatch_on_any_used_camera_stops_before_seed_or_evidence():
    b=fixture();m=deepcopy(b.index.manifest);m['sampling']['per_camera'][1]['index_interval_us']=400000
    index=repin(DetectionSnapshot(m,b.index.records));ps=deepcopy(b.parameter_set);ps['applies_to']['detection_index_ids']=[index.manifest['index_id']];seal_parameters(ps)
    b=replace(b,index=index,index_sha256=index.manifest['content_sha256'],parameter_set=ps,parameter_sha256=ps['content_sha256'])
    r,calls=run(b);assert r.response['reason']=='PARAMETER_GRID_MISMATCH' and r.response['status']=='UNKNOWN'
    assert not r.seed_candidates and not calls and not r.links_bytes


def test_unapproved_explicit_parameters_do_not_auto_execute():
    b=change_parameter(fixture(),'query_min_score',status='PROPOSED');r,calls=run(b)
    assert r.response['status']=='PARTIAL' and r.response['reason']=='PARAMETERS_NOT_APPROVED' and not r.response['timeline'] and not calls


def test_manual_selection_keeps_journal_and_session_counters_with_threaded_tick_gate():
    import threading
    b=fixture({'A':{i:'STRONG' for i in range(10)},'B':{i:'STRONG' for i in range(4,10)}});calls=[];failures=[]
    def gate(timestamp,controller):
        if timestamp==800000:
            prefix=deepcopy(controller.decisions)
            def choose():
                try:controller.request_manual_seed(seed_id(b,'B',4))
                except Exception as exc:failures.append(exc)
            thread=threading.Thread(target=choose);thread.start();thread.join(timeout=2);assert not thread.is_alive()
            assert controller.decisions==prefix
    controller=RuleController(request(b),bindings=b,evidence_provider=port(calls),selected_observation_id=seed_id(b),on_tick=gate)
    result=controller.run();assert not failures and not calls
    assert result.response['timeline'][-1]['camera_id']=='B' and result.response['timeline'][-1]['range_us'][0]==800000
    decisions=[json.loads(x) for x in result.decisions_bytes.splitlines()]
    assert decisions[0]['source_time_us']==0 and max(d['searching_index'] for d in decisions)==1
    assert all(d['session_agent_rounds_used']==0 for d in decisions) and any(d['decided_by']=='USER' and d['state_after']=='SEARCHING' for d in decisions)
    with pytest.raises(ControllerError):controller.request_manual_seed(seed_id(b,'A',0))


def test_manual_changes_cannot_refund_session_search_limit():
    b=change_parameter(fixture({'A':{i:'STRONG' for i in range(10)},'B':{i:'STRONG' for i in range(4,10)}}),'session_max_research_rounds',1)
    def gate(timestamp,controller):
        if timestamp==800000:controller.request_manual_seed(seed_id(b,'B',4))
        if timestamp==1200000:controller.request_manual_seed(seed_id(b,'A',6))
    result=RuleController(request(b),bindings=b,evidence_provider=port([]),selected_observation_id=seed_id(b),on_tick=gate).run()
    assert result.response['status']=='ENDED_BY_LIMIT' and len(result.snapshots)==1
    assert max(json.loads(x)['searching_index'] for x in result.decisions_bytes.splitlines())==1


def test_manual_override_during_evidence_wait_prevents_stale_automatic_cut():
    b=fixture();holder={};normal=port([])
    def provider(index,snapshot,ref,context):
        holder['controller'].request_manual_seed(seed_id(b,'B',5))
        return normal(index,snapshot,ref,context)
    controller=RuleController(request(b),bindings=b,evidence_provider=provider,selected_observation_id=seed_id(b));holder['controller']=controller
    result=controller.run();decisions=[json.loads(x) for x in result.decisions_bytes.splitlines()]
    assert result.response['status']=='COMPLETE' and not any(d['executed_action']=='SWITCH' for d in decisions)
    assert any(not d['accepted'] and d['rejection_code']=='USER_OVERRIDE' for d in decisions)
    assert max(d['searching_index'] for d in decisions)==2 and result.response['timeline'][-1]['entered_by']=='USER_SELECTION'


def test_bad_manual_scope_is_rejected_without_rewinding_or_mutating_session():
    b=fixture({'A':{i:'STRONG' for i in range(10)}})
    def gate(timestamp,controller):
        if timestamp==400000:
            before=deepcopy(controller.decisions)
            with pytest.raises(ControllerError):controller.request_manual_seed(seed_id(b,'A',0))
            assert controller.decisions==before
    result=RuleController(request(b),bindings=b,evidence_provider=port([]),selected_observation_id=seed_id(b),on_tick=gate).run()
    assert result.response['status']=='COMPLETE'


def test_no_seed_is_separate_from_incomplete_source_coverage():
    result,_=run(fixture({}),selected=False);assert result.response['status']=='NO_SEED'
    result,_=run(fixture({'A':{1:'NOT_INFERRED'}}),selected=False)
    assert result.response['status']=='PARTIAL' and result.response['reason']=='INCOMPLETE_EVIDENCE'


def test_stride_controls_presence_checks_and_no_off_grid_link_records():
    pattern={'A':{0:'STRONG',2:'STRONG'},'B':{i:'STRONG' for i in range(6,10)}}
    result,calls=run(fixture(pattern,stride=2));assert calls==[('B',1600000)]
    assert all(int(json.loads(line)['frame_ref'].split(':')[-1])%2==0 for line in result.links_bytes.splitlines())


def test_media_scope_gap_moves_entry_forward_and_keeps_partial():
    b=fixture();media=deepcopy(b.media_ranges_by_camera);media['B']=[[0,1000000],[1200000,2000000]]
    result,_=run(replace(b,media_ranges_by_camera=media,media_scope_sha256=canonical_hash(media)))
    assert result.response['status']=='PARTIAL' and result.response['timeline'][-1]['range_us'][0]==1200000
    candidate=result.snapshots[0]['candidates'][0]
    assert candidate['window_us']==[400000,1600000] and candidate['window_truncated_us']==[[1000000,1200000]]


@pytest.mark.parametrize('case',['hash','candidate','window','backdate','foreign_entry','wrong_bbox','false_coverage','null_entry'])
def test_bad_evidence_ends_session_without_unverified_cut(case):
    b=fixture();normal=port([])
    def provider(index,snapshot,ref,context):
        evidence=normal(index,snapshot,ref,context)
        if case=='hash':evidence['evidence_sha256']='0'*64;return evidence
        if case=='candidate':evidence['candidate_ref']='FOREIGN'
        elif case=='window':evidence['window_us']=[0,2000000]
        elif case=='backdate':evidence['entry_timestamp_us']=200000
        elif case=='foreign_entry':evidence['entry_observation_id']=seed_id(b,'A',0)
        elif case=='wrong_bbox':evidence['best_observations'][0]['bbox_xyxy_px']=[0,0,1,1]
        elif case=='false_coverage':evidence['frames']['missing']=1
        elif case=='null_entry':evidence['entry_observation_id']=evidence['entry_timestamp_us']=None
        evidence['evidence_sha256']=canonical_hash(evidence,exclude=('evidence_sha256','stats'));return evidence
    result,_=run(b,provider=provider)
    assert result.response['status']=='UNKNOWN' and result.response['reason']=='DataIntegrityError'
    assert not any(json.loads(line)['executed_action']=='SWITCH' for line in result.decisions_bytes.splitlines())
    assert result.response['timeline'][0]['kind']=='ON_CAMERA' and result.response['timeline'][-1]['position'] is None


def test_evidence_port_fault_never_becomes_no_person_or_missing_observation():
    def broken(*args):raise RuntimeError('SYNTHETIC port failure')
    result,_=run(provider=broken);assert result.response['status']=='UNKNOWN' and result.diagnostics
    assert all(json.loads(line)['decision']!='FRAME_MISSING' for line in result.links_bytes.splitlines())


@pytest.mark.parametrize('case',['index_pin','clock_pin','graph_pin','media_pin','param_pin','foreign_run','extra_gt'])
def test_binding_and_request_corruption_fail_before_evidence(case):
    b=fixture();q=request(b);changes={}
    if case=='foreign_run':q['run_ids']=['FOREIGN']
    elif case=='extra_gt':q['seed']['actor_id']='FORBIDDEN'
    else:changes[{'index_pin':'index_sha256','clock_pin':'clock_sha256','graph_pin':'camera_graph_sha256','media_pin':'media_scope_sha256','param_pin':'parameter_sha256'}[case]]='0'*64
    b=replace(b,**changes)
    with pytest.raises(ControllerError):run(b,req=q)


def test_missing_exit_on_any_graph_camera_fails_closed():
    b=fixture();r,c=b.graphs.region,b.graphs.camera;c['cameras'][-1]['exit_zones']=[];seal_graphs(r,c)
    from amidst.q1q5.graphs import GraphBundle
    b=replace(b,graphs=GraphBundle(r,c),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    result,_=run(b)
    assert result.response['status']=='UNKNOWN' and result.response['reason']=='EXIT_ZONES_MISSING'
    assert result.response['timeline']==[] and result.response['reasons']==['EXIT_ZONES_MISSING']


def test_declared_unavailable_dependencies_return_unknown_without_seed_choice():
    b=fixture();q=request(b)
    for patch,reason in [({'index':None},'INDEX_NOT_AVAILABLE'),({'clock':None},'CLOCK_MAPPING_MISSING'),({'graphs':None},'GRAPH_NOT_AVAILABLE'),({'parameter_set':None},'PARAMETERS_NOT_APPROVED')]:
        calls=[];result=RuleController(q,bindings=replace(b,**patch),evidence_provider=port(calls),selected_observation_id=seed_id(b)).run()
        assert result.response['status']=='UNKNOWN' and result.response['reason']==reason and not calls and not result.seed_candidates


def test_controller_is_single_use_even_for_early_unknown_result():
    b=fixture();controller=RuleController(request(b),bindings=replace(b,index=None),evidence_provider=port([]));controller.run()
    with pytest.raises(ControllerError):controller.run()


def test_input_index_request_and_parameter_documents_remain_unchanged():
    b=fixture();q=request(b);before=(deepcopy(b.index),deepcopy(q),deepcopy(b.parameter_set))
    run(b,req=q);assert (b.index,q,b.parameter_set)==before


def scoped_fixture():
    from test_graphs import load_scope, scope_fixture
    b=fixture({'A':{0:'STRONG',1:'STRONG'},'B':{5:'STRONG'},'CAM_ENTRY':{0:'STRONG'}},
              cameras=('A','B','CAM_ENTRY'))
    r,c=b.graphs.region,b.graphs.camera;scope,pin=scope_fixture(r,c)
    return replace(b,graphs=load_scope(r,c,scope,pin),region_graph_sha256=r['content_sha256'],
                   camera_graph_sha256=c['content_sha256'])


def test_tracking_intersection_excludes_query_only_camera_from_seeds_and_candidates():
    b=scoped_fixture();result,calls=run(b)
    assert result.response['resolved_scope']['camera_ids']==['A','B']
    assert {row['camera_id'] for row in result.seed_candidates}<={'A','B'}
    assert all(row.get('camera_id',row.get('camera_shown'))!='CAM_ENTRY' for row in result.response['timeline'])
    assert all(camera in {'A','B'} for camera,_ in calls)
    assert all(row['camera_id'] in {'A','B'} for snapshot in result.snapshots for row in snapshot['candidates'])


def test_explicit_query_only_observation_seed_is_unknown_and_never_executes():
    b=scoped_fixture();q=request(b);q['seed']={'kind':'OBSERVATION','observation_id':seed_id(b,'CAM_ENTRY')}
    calls=[];result=RuleController(q,bindings=b,evidence_provider=port(calls)).run()
    assert result.response['status']=='UNKNOWN' and result.response['reason']=='SEED_CAMERA_NOT_TRACKED'
    assert result.response['timeline']==[] and not result.seed_candidates and not calls


def test_declared_missing_scope_returns_unknown_without_silent_camera_fallback():
    from amidst.q1q5.graphs import GraphBundle
    b=scoped_fixture();b=replace(b,graphs=GraphBundle(b.graphs.region,b.graphs.camera))
    result,calls=run(b)
    assert result.response['status']=='UNKNOWN' and result.response['reason']=='TRACKING_SCOPE_MISSING'
    assert result.response['timeline']==[] and not calls


def test_independent_clock_parameter_grid_and_exit_blockers_all_survive_with_stable_hash():
    from amidst.q1q5.graphs import GraphBundle
    b=fixture();q=request(b);m=deepcopy(b.index.manifest)
    m['sampling']['per_camera'][1]['index_interval_us']=400000
    index=repin(DetectionSnapshot(m,b.index.records));p=deepcopy(b.parameter_set)
    p['applies_to']['detection_index_ids']=[index.manifest['index_id']]
    p['approval']['status']='PROPOSED';seal_parameters(p);q['parameter_set_id']=p['parameter_set_id']
    r,c=b.graphs.region,b.graphs.camera;c['cameras'][0]['exit_zones']=[];seal_graphs(r,c)
    b=replace(b,index=index,index_sha256=index.manifest['content_sha256'],clock=None,
              graphs=GraphBundle(r,c),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'],
              parameter_set=p,parameter_sha256=p['content_sha256'])
    results=[]
    for _ in range(2):
        calls=[];result=RuleController(q,bindings=b,evidence_provider=port(calls)).run();results.append(result.response)
        assert result.response['status']=='UNKNOWN' and result.response['reason']=='CLOCK_MAPPING_MISSING'
        assert result.response['reasons']==['CLOCK_MAPPING_MISSING','PARAMETERS_NOT_APPROVED',
                                           'PARAMETER_GRID_MISMATCH','EXIT_ZONES_MISSING']
        assert result.response['timeline']==[] and not result.seed_candidates and not calls
    assert results[0]['output_sha256']==results[1]['output_sha256']


def test_user_stop_returns_partial_and_preserves_real_observed_prefix():
    b=fixture({'A':{i:'STRONG' for i in range(10)}})
    def stop(timestamp,controller):
        if timestamp==600000:controller.request_stop()
    result=RuleController(request(b),bindings=b,evidence_provider=port([]),
                          selected_observation_id=seed_id(b),on_tick=stop).run()
    assert result.response['status']=='PARTIAL' and result.response['reason']=='USER_STOPPED'
    observed=[row for row in result.response['timeline'] if row['kind']=='ON_CAMERA']
    assert observed and all(row['range_us'][1]<=600000 for row in observed)
    assert json.loads(result.decisions_bytes.splitlines()[-1])['control_reason']=='USER_STOPPED'


@pytest.mark.parametrize('name,value',[('research_interval_us',300000),('link_max_gap_us',400001)])
def test_exit_failure_cannot_hide_other_independent_parameter_grid_failures(name,value):
    from amidst.q1q5.graphs import GraphBundle
    b=change_parameter(fixture(),name,value=value)
    r,c=b.graphs.region,b.graphs.camera;c['cameras'][0]['exit_zones']=[];seal_graphs(r,c)
    b=replace(b,graphs=GraphBundle(r,c),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    result,calls=run(b)
    assert result.response['reason']=='PARAMETER_GRID_MISMATCH'
    assert result.response['reasons']==['PARAMETER_GRID_MISMATCH','EXIT_ZONES_MISSING']
    assert not result.response['timeline'] and not calls


def test_exit_failure_cannot_hide_unapproved_linker_parameters():
    from amidst.q1q5.graphs import GraphBundle
    b=change_parameter(fixture(),'link_iou_min',status='PROPOSED')
    r,c=b.graphs.region,b.graphs.camera;c['cameras'][0]['exit_zones']=[];seal_graphs(r,c)
    b=replace(b,graphs=GraphBundle(r,c),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    result,calls=run(b)
    assert result.response['reasons']==['PARAMETERS_NOT_APPROVED','EXIT_ZONES_MISSING']
    assert not result.response['timeline'] and not calls


@pytest.mark.parametrize('g4',[False,True])
def test_modern_scope_draft_graph_blocks_before_seed_evidence_or_execution(g4):
    from test_graphs import load_scope, repin_scope
    b=scoped_fixture();r,c=b.graphs.region,b.graphs.camera;scope=b.graphs.tracking_scope
    for doc in (r,c):doc.update(approval_status='DRAFT',approval_ref=None)
    scope.update(G4_approved=g4,status='FROZEN' if g4 else 'PROPOSED')
    pin=repin_scope(r,c,scope)
    b=replace(b,graphs=load_scope(r,c,scope,pin),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    result,calls=run(b)
    assert result.response['status']=='UNKNOWN' and result.response['reasons']==['GRAPH_NOT_APPROVED']
    assert not result.response['timeline'] and not result.seed_candidates and not calls
    assert not result.decisions_bytes and not result.links_bytes and not result.snapshots


def test_legacy_draft_graph_without_scope_retains_partial_engineering_execution():
    from amidst.q1q5.graphs import load_graphs
    b=fixture();r,c=b.graphs.region,b.graphs.camera
    for doc in (r,c):doc.update(approval_status='DRAFT',approval_ref=None)
    seal_graphs(r,c)
    b=replace(b,graphs=load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256']),
              region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    result,_=run(b)
    assert result.response['status']=='PARTIAL' and result.response['reason']=='GRAPH_NOT_APPROVED'
    assert result.response['timeline'] and result.decisions_bytes


def test_unapproved_modern_graph_never_calls_agent_provider():
    from amidst.q1q5.q5_agent import AgentController
    from test_graphs import load_scope, repin_scope
    from test_q5_agent import settings
    b=scoped_fixture();r,c=b.graphs.region,b.graphs.camera;scope=b.graphs.tracking_scope
    for doc in (r,c):doc.update(approval_status='DRAFT',approval_ref=None)
    scope.update(G4_approved=False,status='PROPOSED');pin=repin_scope(r,c,scope)
    b=replace(b,graphs=load_scope(r,c,scope,pin),region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256'])
    class NeverProvider:
        calls=0
        def generate(self,**kwargs):
            self.calls+=1
            raise AssertionError('G4 gate must precede model calls')
    provider=NeverProvider();q=request(b);q['switch_mode']='AGENT_SEQUENTIAL';calls=[]
    result=AgentController(q,bindings=b,evidence_provider=port(calls),provider=provider,
        agent_settings=settings(),round_scheduler=lambda *args:None,clock=lambda:0,
        selected_observation_id=seed_id(b)).run()
    assert result.response['status']=='UNKNOWN' and result.response['reason']=='GRAPH_NOT_APPROVED'
    assert provider.calls==0 and not result.response['timeline'] and not calls
