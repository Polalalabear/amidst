"""Count Agent decision points in the pinned DEMO_DEFAULT runs (AGENT_DECISION_V1 §4.1).

Usage: python scripts/design/count_agent_decision_points.py <repo_root> <owned_root>
Reads only the pinned cross-camera job inputs (index, records, local tracks, config,
clock, static graph) through run_cross_camera_demo.load_run, which rejects GT,
script, visibility and depth keys. No images, models, network or GT are read.
Design evidence only; not a formal evaluation.
"""
import sys, json, collections
sys.path[:0] = [sys.argv[1] + '/src', sys.argv[1] + '/scripts']
from run_cross_camera_demo import load_run, loads, read_pin
from demo_dependency_config import resolve_job, owned_path
from amidst.q1q5.cross_camera_demo import Parameters, response
from pathlib import Path
root = Path(sys.argv[2]).expanduser()
job = resolve_job(loads((root/'metadata/cross-camera-job.json').read_bytes()), root)
graph = loads(read_pin(job['graph']))
transitions = {(t['from_camera_id'], t['to_camera_id']): t['transition_id'] for t in graph['transitions']}
params = Parameters(**job['parameters'])
for spec in job['runs']:
    tracks, clock, m = load_run(spec, graph, job['graph_binding'], params)
    end = max(o.timestamp_us for t in tracks for o in t.observations) + params.sample_interval_us
    res, events, audit = response(tracks, transitions, as_of_us=end, parameters=params, clock_mapping_sha256='x')
    reasons = collections.Counter(a['reason'] for a in audit)
    amb = sorted({a['timestamp_us'] for a in audit if a['reason'] == 'AMBIGUOUS_HANDOFF'})
    amb_cands = collections.Counter(a['timestamp_us'] for a in audit if a['reason'] == 'AMBIGUOUS_HANDOFF')
    color = sorted({a['timestamp_us'] for a in audit if a['reason'] == 'COLOR_NOT_COMPATIBLE'})
    box = sum(1 for a in audit if a['reason'] == 'BOX_CONTINUATION')
    gaps = [s for s in res['single_view'] if s['kind'] in ('GAP', 'LOST')]
    print(json.dumps({'label': spec['label'], 'run_id': m['run_id'], 'as_of_us': end,
        'tracks': len(tracks), 'cameras': sorted({t.camera_id for t in tracks}),
        'audit_reasons': reasons, 'ambiguous_handoff_timestamps': len(amb),
        'ambiguous_candidates_per_timestamp': sorted(amb_cands.values()),
        'first_seed_ambiguous': reasons.get('AMBIGUOUS_FIRST_SEED', 0),
        'color_rejected_timestamps': len(color), 'box_continuation_rows': box,
        'events': [(e['link_kind'], e['from_camera_id'], e['to_camera_id']) for e in events],
        'single_view_gap_or_lost': [(g['kind'], g['range_us']) for g in gaps],
        'status': res['status']}, default=dict))

# continuation segments (contiguous BOX_CONTINUATION runs per track)
for spec in job['runs']:
    tracks, clock, m = load_run(spec, graph, job['graph_binding'], params)
    seg = 0; total = 0
    for t in tracks:
        prev = False
        for o in t.observations:
            c = o.evidence_kind == 'BOX_CONTINUATION'
            total += c
            if c and not prev: seg += 1
            prev = c
    print(spec['label'], 'continuation_obs', total, 'continuation_segments', seg,
          'observations', sum(len(t.observations) for t in tracks))
