"""Planning estimate of DP1 decision points for an authored multi-actor scenario draft (D198).

Usage: python scripts/design/estimate_plan_decision_points.py <repo_root> <scenario.json> [--variant in_band|out_of_band]

Design-time only. For each run it turns the authored waypoints into synthetic local tracks
using the draft's *assumed* floor-box camera coverage (estimate_model), perfect detection
inside a box and the planned colour labels (sample 0 keeps only the target in the declared
seed camera, modelling the explicit seed observation of the v1 drafts), then replays the unchanged DEMO_DEFAULT
associate() and counts its audit reasons, as AGENT_DECISION_V1 section 4.1 does for real runs.
Nothing here reads renders, detections, camera projections or private scoring data; the
numbers are planning estimates, not measurements. The "gold" column uses the authored
actor id of each synthetic track, which exists only because this is a plan.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

S = 1_000_000


def _inside(boxes, p):
    return any(b[0][0] <= p[0] <= b[0][1] and b[1][0] <= p[1] <= b[1][1] for b in boxes)


def _position(actor, t):
    wps = actor['waypoints']
    if t < wps[0]['t_us'] or t > wps[-1]['t_us']:
        return None
    for a, b in zip(wps, wps[1:]):
        if a['t_us'] <= t <= b['t_us']:
            f = (t - a['t_us']) / (b['t_us'] - a['t_us'])
            return (a['xy'][0] + f * (b['xy'][0] - a['xy'][0]), a['xy'][1] + f * (b['xy'][1] - a['xy'][1]))
    return tuple(wps[-1]['xy'])


def synthetic_tracks(run, variant, Observation, Track, step):
    model = run['estimate_model']
    cover = model['assumed_camera_coverage_xy_boxes']
    seed_camera = model.get('seed_camera_id')
    tracks, owner = [], {}
    for actor in run['actors']:
        is_target = actor['role'] == 'TARGET'
        labels = actor['color_rule_expectation']['expected_labels']
        if 'planned_color_label_variants' in actor:
            labels = actor['planned_color_label_variants'][variant]
        colors = frozenset(labels)
        for camera in model['tracking_camera_ids']:
            segment, n = [], 0
            for t in range(0, run['duration_us'], step):
                p = _position(actor, t)
                seen = p is not None and _inside(cover.get(camera, []), p)
                if t == 0 and seed_camera and not (is_target and camera == seed_camera):
                    seen = False  # explicit seed: only the target in the seed camera exists at sample 0
                if seen:
                    segment.append(Observation(camera, t, f"{actor['actor_id']}:{camera}:{t}", 0.9, colors))
                if segment and (not seen or t + step >= run['duration_us']):
                    ref = f"{actor['actor_id']}:{camera}:{n}"
                    tracks.append(Track(camera, ref, tuple(segment)))
                    owner[ref] = actor['actor_id']
                    segment, n = [], n + 1
    return tracks, owner


def estimate_run(run, variant, mod):
    params = mod.Parameters()
    tracks, owner = synthetic_tracks(run, variant, mod.Observation, mod.Track, params.sample_interval_us)
    transitions = {(a, b): f'T_{a}__{b}' for a, b in run['estimate_model']['transitions']}
    end = run['duration_us']
    *_, audit = mod.response(tracks, transitions, as_of_us=end, parameters=params, clock_mapping_sha256='x')
    target = next(a['actor_id'] for a in run['actors'] if a['role'] == 'TARGET')
    singles = [a for a in audit if a['reason'] == 'DEMO_ASSOCIATION_HYPOTHESIS']
    amb = collections.defaultdict(list)
    for a in audit:
        if a['reason'] == 'AMBIGUOUS_HANDOFF':
            amb[a['timestamp_us']].append(a['to_track_ref'])
    color = sorted({a['timestamp_us'] for a in audit if a['reason'] == 'COLOR_NOT_COMPATIBLE'})

    def gold(refs):
        hits = [r for r in refs if owner[r] == target]
        return 'SELECT_TARGET' if hits else 'ABSTAIN'

    single_rows = [{'t_s': a['timestamp_us'] / S, 'from': owner[a['from_track_ref']], 'to': owner[a['to_track_ref']],
                    'to_camera': a['to_camera_id'], 'rule_correct': owner[a['to_track_ref']] == target}
                   for a in singles]
    amb_rows = [{'t_s': t / S, 'candidates': sorted(owner[r] + '@' + r.split(':')[1] for r in refs),
                 'gold': gold(refs)} for t, refs in sorted(amb.items())]
    episode_rows, last = [], None
    for t in sorted(amb):
        actors = {owner[r] for r in amb[t]}
        if last is None or t - last > 200_000:
            episode_rows.append({'start_s': t / S, 'end_s': t / S, 'timestamps': 0, 'actors': set()})
        ep = episode_rows[-1]
        ep['end_s'], ep['timestamps'] = t / S, ep['timestamps'] + 1
        ep['actors'] |= actors
        last = t
    for ep in episode_rows:
        ep['has_distractor'] = any(a != target for a in ep['actors'])
        ep['actors'] = sorted(ep['actors'])
    episodes = len(episode_rows)
    seeds = sum(1 for a in audit if a['reason'] == 'AMBIGUOUS_FIRST_SEED')
    return {
        'run_id': run['run_id'], 'variant': variant, 'synthetic_track_count': len(tracks),
        'dp1_single_candidate': len(single_rows),
        'dp1_single_rule_wrong': sum(1 for r in single_rows if not r['rule_correct']),
        'dp1_ambiguous_timestamps': len(amb_rows), 'dp1_ambiguous_episodes': episodes,
        'dp1_ambiguous_episodes_with_distractor': sum(1 for e in episode_rows if e['has_distractor']),
        'dp1_ambiguous_with_distractor': sum(1 for refs in amb.values() if any(owner[r] != target for r in refs)),
        'dp1_gold_abstain': (sum(1 for r in amb_rows if r['gold'] == 'ABSTAIN')
                             + sum(1 for r in single_rows if not r['rule_correct'])),
        'dp1_total': len(single_rows) + len(amb_rows),
        'ambiguous_first_seed': seeds,
        'color_not_compatible_timestamps': len(color),
        'ambiguous_episodes': episode_rows,
        'single_candidate_events': single_rows, 'ambiguous_timestamps': amb_rows,
        'status': 'PLANNING_ESTIMATE_ASSUMED_COVERAGE_PERFECT_DETECTION',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('repo_root')
    parser.add_argument('scenario')
    parser.add_argument('--variant', default='in_band', choices=['in_band', 'out_of_band'])
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(args.repo_root) / 'src'))
    from amidst.q1q5 import cross_camera_demo as mod
    doc = json.loads(Path(args.scenario).read_text(encoding='utf-8'))
    out = [estimate_run(r, args.variant, mod) for r in doc['runs']]
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
