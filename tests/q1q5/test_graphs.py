"""SYNTHETIC static inputs only; no event/GT/real-scene acceptance."""
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
    r=dict(schema_version='q-demo.region-graph.v1',scene_id='SYNTHETIC',scene_revision='rSYN',scene_static_sha256=H,approval_status='DRAFT',approval_ref=None,regions=[region(n) for n in range(1,6)],edges=[edge(1,2),edge(2,3),edge(3,4,'TOPOLOGICAL_ONLY'),edge(2,5)],inputs=[{'ref':'static:SYNTHETIC','sha256':H}])
    cameras=[]
    for name,n,exit_edge in [('A',1,'E12'),('B',3,'E23'),('C',4,'E34'),('D',1,'E12'),('E',5,'E25')]:
        cameras.append(dict(camera_id=name,calibration_sha256=H,covered_regions=[{'region_id':f'R{n}','basis':'STATIC_VISIBILITY_INDEX','visibility_ref':f'vis:{name}','visible_area_m2':None}],exit_zones=[{'exit_zone_id':name+':exit','roi_polygon_px':[[0,0],[100,0],[100,100],[0,100]],'leads_to_edge_ids':[exit_edge],'mapping_basis':'MANUAL_ON_STATIC_FRAME','static_frame_ref':f'static:{name}','static_frame_sha256':H}],entry_zones=[]))
    transitions=[]
    for dest,path,eids,rel,area,authority in [('D',['R1'],[],'OVERLAP',3.5,'APPROVED_WALKABLE'),('B',['R1','R2','R3'],['E12','E23'],'BLIND_GAP',6,'APPROVED_WALKABLE'),('E',['R1','R2','R5'],['E12','E25'],'BLIND_GAP',None,'APPROVED_WALKABLE'),('C',['R1','R2','R3','R4'],['E12','E23','E34'],'BLIND_GAP',4,'TOPOLOGICAL_ONLY')]:
        transitions.append(dict(transition_id='T_A_'+dest,from_camera_id='A',to_camera_id=dest,via_exit_zone_ids=['A:exit'],to_entry_zone_ids=[],region_path=path,edge_path=eids,relation=rel,region_hops=len(eids),path_traversability=authority,path_has_unknown_state=False,ranking_area_m2=area,ranking_area_refs=[] if area is None else ['area:SYNTHETIC'],nominal_path_length_m=None,basis_refs=['basis:SYNTHETIC']))
    c=dict(schema_version='q-demo.camera-transition-graph.v1',scene_id='SYNTHETIC',scene_revision='rSYN',camera_catalog_sha256=H,approval_status='DRAFT',approval_ref=None,cameras=cameras,transitions=transitions,inputs=[{'ref':'static:SYNTHETIC','sha256':H}])
    return seal(r,c)


def load(r,c):return load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'])


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
        if t['edge_path']:t['path_has_unknown_state']=True
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
