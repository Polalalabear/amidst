"""SYNTHETIC static inputs only; no event/GT/real-scene acceptance."""
import hashlib
import json
from copy import deepcopy

import pytest

from amidst.q1q5.graphs import GraphError, load_graphs
from amidst.q1q5.store import canonical_hash

H = 'a'*64

def seal(r,c):
    for d,p in [(r,'rgraph'),(c,'cgraph')]:
        if p == 'cgraph':d['region_graph_sha256']=r['content_sha256']
        d['content_sha256']=canonical_hash(d,exclude=('graph_id','content_sha256','stats'))
        d['graph_id']=f"{p}:rSYN:static:{d['content_sha256'][:16]}"
    return r,c


def fixture():
    def region(n):return dict(region_id=f'R{n}',kind='ROOM',floor_id='F',walk_ids=[f'W{n}'],polygon_ref=f'poly:{n}',polygon_sha256=H)
    def edge(a,b,authority='APPROVED_WALKABLE'):return dict(edge_id=f'E{a}{b}',regions=[f'R{a}',f'R{b}'],via={'kind':'ADJACENT','ref':f'boundary:{a}{b}'},direction='BIDIRECTIONAL',state='OPEN',traversability=authority,basis_refs=['basis:SYNTHETIC'])
    r=dict(schema_version='q-demo.region-graph.v1',scene_id='SYNTHETIC',scene_revision='rSYN',scene_static_sha256=H,approval_status='DRAFT',approval_ref=None,regions=[region(n) for n in range(1,7)],edges=[edge(1,2),edge(2,3),edge(3,4,'TOPOLOGICAL_ONLY'),edge(2,5),edge(1,6)],inputs=[{'ref':'static:SYNTHETIC','sha256':H}])
    cameras=[]
    for name,n,exit_edge in [('A',1,'E12'),('B',3,'E23'),('C',4,'E34'),('D',6,'E16'),('E',5,'E25')]:
        cameras.append(dict(camera_id=name,calibration_sha256=H,covered_regions=[{'region_id':f'R{n}','basis':'STATIC_VISIBILITY_INDEX','visibility_ref':f'vis:{name}','visible_area_m2':None}],exit_zones=[{'exit_zone_id':name+':exit','roi_polygon_px':[[0,0],[100,0],[100,100],[0,100]],'leads_to_edge_ids':[exit_edge,'E16'] if name=='A' else [exit_edge],'mapping_basis':'MANUAL_ON_STATIC_FRAME','static_frame_ref':f'static:{name}','static_frame_sha256':H}],entry_zones=[]))
    transitions=[]
    for dest,path,eids,rel,area,authority in [('D',['R1','R6'],['E16'],'OVERLAP',3.5,'APPROVED_WALKABLE'),('B',['R1','R2','R3'],['E12','E23'],'BLIND_GAP',6,'APPROVED_WALKABLE'),('E',['R1','R2','R5'],['E12','E25'],'BLIND_GAP',None,'APPROVED_WALKABLE'),('C',['R1','R2','R3','R4'],['E12','E23','E34'],'BLIND_GAP',4,'TOPOLOGICAL_ONLY')]:
        transitions.append(dict(transition_id='T_A_'+dest,from_camera_id='A',to_camera_id=dest,via_exit_zone_ids=['A:exit'],to_entry_zone_ids=[],region_path=path,edge_path=eids,relation=rel,region_hops=len(eids),path_traversability=authority,path_has_unknown_state=False,ranking_area_m2=area,ranking_area_refs=[] if area is None else ['area:SYNTHETIC'],nominal_path_length_m=None,basis_refs=['basis:SYNTHETIC']))
    c=dict(schema_version='q-demo.camera-transition-graph.v1',scene_id='SYNTHETIC',scene_revision='rSYN',camera_catalog_sha256=H,approval_status='DRAFT',approval_ref=None,cameras=cameras,transitions=transitions,inputs=[{'ref':'static:SYNTHETIC','sha256':H}])
    return seal(r,c)


def load(r,c):return load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'])


def scope_fixture(r,c,query_only=('CAM_ENTRY',)):
    tracking=sorted(x['camera_id'] for x in c['cameras']);query=sorted(tracking+list(query_only))
    by_pair={(t['from_camera_id'],t['to_camera_id']):t for t in c['transitions']}
    pairs=[]
    for source in query:
        for target in query:
            if source==target:continue
            row={'from_camera_id':source,'to_camera_id':target}
            transition=by_pair.get((source,target))
            row.update(disposition='TRANSITION',transition_id=transition['transition_id']) if transition else row.update(disposition='EXCLUDED',reason='SYNTHETIC_SCOPE_EXCLUSION')
            pairs.append(row)
    approved=any(doc['approval_status']=='APPROVED' for doc in (r,c))
    scope={'schema_version':'q-demo.r004-tracking-scope.v3','status':'APPROVED' if approved else 'PROPOSED','G4_approved':approved,
           'query_camera_ids':query,'tracking_camera_ids':tracking,'query_only_camera_ids':list(query_only),
           'directed_pairs':pairs,'north_floor_y_gt_12':'SYNTHETIC','overlap_pairs_deferred':'SYNTHETIC'}
    pin=hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()+b'\n').hexdigest()
    for doc in (r,c):doc['inputs'].append({'ref':'tracking-scope:SYNTHETIC:v3','sha256':pin})
    seal(r,c)
    return scope,pin


def load_scope(r,c,scope,pin):
    return load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'],
                       tracking_scope=scope,tracking_scope_sha256=pin)


def test_scope_uses_original_file_bytes_with_noncanonical_whitespace():
    r,c=fixture();scope,_=scope_fixture(r,c)
    raw=json.dumps(scope,indent=2).encode()+b'\n';pin=hashlib.sha256(raw).hexdigest()
    for graph in (r,c):
        next(x for x in graph['inputs'] if x['ref'].startswith('tracking-scope:'))['sha256']=pin
    seal(r,c)
    bundle=load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'],
                       tracking_scope=scope,tracking_scope_sha256=pin,tracking_scope_bytes=raw)
    assert bundle.tracking_scope_bytes==raw and bundle.tracking_scope_sha256==pin
    with pytest.raises(GraphError):
        load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'],
                    tracking_scope=scope,tracking_scope_sha256=pin,tracking_scope_bytes=raw+b' ')


def test_roundtrip_preserves_draft_and_protects_input_copies():
    r,c=fixture();bundle=load(r,c);assert bundle.approval_status=='DRAFT'
    c['cameras'].clear();x=bundle.camera;x['cameras'].clear();assert len(bundle.camera['cameras'])==5


@pytest.mark.parametrize('camera',range(5))
def test_every_camera_needs_exit(camera):
    r,c=fixture();c['cameras'][camera]['exit_zones']=[];seal(r,c)
    with pytest.raises(GraphError) as error:load(r,c)
    assert error.value.code=='EXIT_ZONES_MISSING'


@pytest.mark.parametrize('key',['actor_id','ground_truth','detections','event_script','depth','visibility'])
def test_forbidden_inputs_are_rejected_even_when_hash_matches(key):
    r,c=fixture();c[key]='SYNTHETIC';seal(r,c)
    with pytest.raises(GraphError):load(r,c)


@pytest.mark.parametrize('case',['hash','id','cross_scene','duplicate','closed','directed','unknown_state','authority','missing_edge','roi','approval','area','exit_mapping','exit_path'])
def test_integrity_failures_are_not_downgraded(case):
    r,c=fixture()
    if case=='hash':c['camera_catalog_sha256']='b'*64
    elif case=='id':c['graph_id']='cgraph:rSYN:static:'+'0'*16
    elif case=='cross_scene':c['scene_id']='OTHER'
    elif case=='duplicate':r['edges'].append(deepcopy(r['edges'][0]))
    elif case=='closed':r['edges'][0]['state']='CLOSED'
    elif case=='directed':r['edges'][0].update(direction='ONE_WAY',**{'from':'R2','to':'R1'})
    elif case=='unknown_state':c['transitions'][1]['path_has_unknown_state']=True
    elif case=='authority':c['transitions'][3]['path_traversability']='APPROVED_WALKABLE'
    elif case=='missing_edge':c['transitions'][1]['edge_path'][0]='MISSING'
    elif case=='roi':c['cameras'][0]['exit_zones'][0]['roi_polygon_px']=[[1,1]]*3
    elif case=='approval':c['approval_status']='APPROVED'
    elif case=='area':c['transitions'][0]['ranking_area_refs']=[]
    elif case=='exit_mapping':c['cameras'][0]['exit_zones'][0]['static_frame_sha256']=None
    elif case=='exit_path':c['cameras'][0]['exit_zones'][0]['leads_to_edge_ids']=['E23']
    if case not in {'hash','id'}:seal(r,c)
    with pytest.raises(GraphError):load(r,c)


def test_unknown_state_and_relation_are_preserved_and_not_approved():
    r,c=fixture();r['edges'][0]['state']='UNKNOWN'
    for t in c['transitions']:
        if 'E12' in t['edge_path']:t['path_has_unknown_state']=True
    c['transitions'][1]['relation']='UNKNOWN';seal(r,c);bundle=load(r,c)
    assert bundle.camera['transitions'][1]['relation']=='UNKNOWN'
    assert bundle.approval_status=='DRAFT'


@pytest.mark.parametrize('where', ['root', 'camera', 'transition', 'edge', 'zone'])
def test_unrecognized_fields_cannot_smuggle_dynamic_ranking_input(where):
    r,c=fixture()
    target={'root':c, 'camera':c['cameras'][0], 'transition':c['transitions'][0],
            'edge':r['edges'][0], 'zone':c['cameras'][0]['exit_zones'][0]}[where]
    target['person_count']=99;seal(r,c)
    with pytest.raises(GraphError):load(r,c)


def test_explicit_tracking_scope_is_pinned_and_does_not_grant_approval():
    r,c=fixture();scope,pin=scope_fixture(r,c);bundle=load_scope(r,c,scope,pin)
    assert bundle.tracking_scope_sha256==pin and bundle.approval_status=='DRAFT'
    assert bundle.tracking_scope['query_only_camera_ids']==['CAM_ENTRY']
    scope['query_only_camera_ids'].clear();copy=bundle.tracking_scope;copy['tracking_camera_ids'].clear()
    assert bundle.tracking_scope['query_only_camera_ids']==['CAM_ENTRY']
    assert len(bundle.tracking_scope['tracking_camera_ids'])==5


def test_declared_tracking_scope_missing_does_not_fall_back_to_graph_cameras():
    r,c=fixture();scope_fixture(r,c)
    with pytest.raises(GraphError) as error:load(r,c)
    assert error.value.code=='TRACKING_SCOPE_MISSING'


@pytest.mark.parametrize('change',['bytes_pin','partition','pair_missing','transition_ref','extra_field'])
def test_invalid_tracking_scope_fails_closed_even_with_recomputed_graph_pins(change):
    r,c=fixture();scope,pin=scope_fixture(r,c)
    if change=='bytes_pin':pin='0'*64
    elif change=='partition':scope['query_only_camera_ids'].append('A')
    elif change=='pair_missing':scope['directed_pairs'].pop()
    elif change=='transition_ref':next(x for x in scope['directed_pairs'] if x['disposition']=='TRANSITION')['transition_id']='MISSING'
    else:scope['actor_id']='FORBIDDEN'
    if change!='bytes_pin':
        pin=hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()+b'\n').hexdigest()
        for doc in (r,c):doc['inputs'][-1]['sha256']=pin
        seal(r,c)
    with pytest.raises(GraphError):load_scope(r,c,scope,pin)


def repin_scope(r,c,scope):
    pin=hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()+b'\n').hexdigest()
    for doc in (r,c):
        next(row for row in doc['inputs'] if row['ref'].startswith('tracking-scope:'))['sha256']=pin
    seal(r,c)
    return pin


@pytest.mark.parametrize('side',['region','camera'])
@pytest.mark.parametrize('change',['G4_false','PROPOSED'])
def test_unapproved_scope_keeps_effective_graph_draft(side,change):
    r,c=fixture();doc=r if side=='region' else c
    doc.update(approval_status='APPROVED',approval_ref='SYNTHETIC_TEST_ONLY')
    scope,_=scope_fixture(r,c)
    if change=='G4_false':scope['G4_approved']=False
    else:scope['status']='PROPOSED'
    pin=repin_scope(r,c,scope)
    assert load_scope(r,c,scope,pin).approval_status=='DRAFT'


@pytest.mark.parametrize('status',['FROZEN','APPROVED'])
def test_both_approved_graphs_accept_approved_g4_scope(status):
    r,c=fixture()
    for doc in (r,c):doc.update(approval_status='APPROVED',approval_ref='SYNTHETIC_TEST_ONLY')
    scope,_=scope_fixture(r,c);scope['status']=status;pin=repin_scope(r,c,scope)
    assert load_scope(r,c,scope,pin).approval_status==('APPROVED' if status=='APPROVED' else 'DRAFT')


def test_scope_g4_approval_cannot_elevate_draft_graphs():
    r,c=fixture();scope,_=scope_fixture(r,c)
    scope.update(status='FROZEN',G4_approved=True);pin=repin_scope(r,c,scope)
    bundle=load_scope(r,c,scope,pin)
    assert bundle.tracking_scope['G4_approved'] is True and bundle.approval_status=='DRAFT'
