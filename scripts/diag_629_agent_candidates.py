"""#629 read-only diagnostic: per-layer candidate counts for A4-1/B4-1 recorded Q2.
Inputs: pinned graphs + detection index bbox (inference-side). No GT, no network, no model.
Run: AMIDST_DEMO_HOME=<owned pkg> PYTHONPATH=src:scripts python scripts/diag_629_agent_candidates.py"""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src')); sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_dependency_config import configuration, owned_path, resolve_job
from run_cross_camera_demo import read_pin, loads, load_run
from amidst.q1q5.scene_graphs import load_scene_graphs
from amidst.q1q5.candidates import _inside, transition_candidates
from amidst.q1q5.store import DocumentPin, JsonRunStore
from amidst.q1q5.cross_camera_demo import Parameters
from serve_demo_integration import scene_projection

config, root = configuration()
job = resolve_job(loads(owned_path(root, config['cross_camera_job']).read_bytes()), root)
g0 = load_scene_graphs('r004'); cp = Parameters(**job['parameters'])
for spec in job['runs']:
    tracks, clock_doc, m = load_run(spec, g0.camera, job['graph_binding'], cp)
    graphs = scene_projection(g0, m['scene_id'], job['graph_binding'])
    cams = {c['camera_id']: c for c in graphs.camera['cameras']}
    scope = graphs.tracking_scope; allowed = sorted(scope['tracking_camera_ids']); auth = graphs.transition_authorities
    store = JsonRunStore(Path(spec['inputs']['index']['path']).parent, {
        'index': DocumentPin('detection_index.json', spec['inputs']['index']['sha256'], m['schema_version'], m['content_sha256']),
        'records': DocumentPin(m['records_ref'], spec['inputs']['records']['sha256'], 'q-demo.detection-record.v1')})
    idx = store.load_detection_index('index')
    print(f"\n== {spec['label']} {m['run_id']}  graph={graphs.approval_status} scope.G4_approved={scope['G4_approved']} status={scope['status']}")
    print('  transitions total', len(graphs.camera['transitions']),
          '| approved-walkable & edge_path:', [t['transition_id'] for t in graphs.camera['transitions']
             if auth[t['transition_id']]['path_traversability'] not in ('UNKNOWN','TOPOLOGICAL_ONLY')])
    per = {}
    for r in idx.records:
        cam = r['camera_id']
        if cam not in cams: continue
        for o in r['detections']:
            if o['class_label'] != 'person' or o['score'] < .3: continue
            d = per.setdefault(cam, Counter()); d['L1_person_obs'] += 1
            x0, y0, x1, y1 = o['bbox_xyxy_px']
            if not any(_inside(((x0+x1)/2, y1), z['roi_polygon_px'], True) for z in cams[cam]['exit_zones']): continue
            d['L2_in_exit_zone'] += 1
            s = transition_candidates(graphs, from_camera_id=cam, last_bbox_xyxy_px=o['bbox_xyxy_px'], session_id='diag', top_k=3,
                                      window_us=[0, 10_000_000], exit_boundary_inclusive=True, allowed_camera_ids=allowed)
            d['L3_edges_matching_zone'] += len(s['excluded_transitions'])+len(s['candidates'])
            d['L4_candidates_after_authority'] += len(s['candidates'])
            d['L4_obs_with_candidate'] += bool(s['candidates'])
            for e in s['excluded_transitions']: d['excl:'+e['reason']] += 1
    for cam, d in sorted(per.items()): print(' ', cam, dict(d))
