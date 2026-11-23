"""CX-H6: adapt validated camera-local core sightings to the F3 main-screen protocol.

Only the demo server opts in. Parameter/status/source hashes are retained; no
approval is manufactured. The shared ServiceTrackDecider owns M1 and caching.
"""
from amidst.q1q5.core_query import execute_core_track, validate_track_request, CoreRequestError, _blind_for_track
from amidst.q1q5.cross_camera_demo import Observation, Track, Parameters, response
from amidst.q1q5.service_agent_q5 import colors_of
from amidst.q1q5.store import canonical_hash


def core_track(payload, run, *, decider=None, unavailable_reason=None, demo_default=False, display_positions=None):
    base = execute_core_track(payload, run, allow_demo_default=demo_default,
                              physical_prediction_available=True, display_positions=display_positions)
    norm = validate_track_request(payload, region_ids=run.catalog['region_ids'], class_labels=run.catalog['class_labels'],
                                  class_aliases=run.catalog['class_aliases'], color_labels=run.catalog['color_labels'],
                                  clock_mapping=run.bindings.clock)
    if base['status'] not in ('UNKNOWN', 'UNSUPPORTED'):
        obs = {o['observation_id']: (r, o) for r in run.bindings.index.records for o in r['detections'] or []}
        grouped = {}
        for sight in base['sightings']:
            target = grouped.setdefault((sight['camera_id'], sight['track_ref']), {})
            for oid in sight['observation_ids']:
                r, o = obs[oid]
                target[oid] = Observation(r['camera_id'], r['timestamp_us'], oid, o['score'], frozenset(colors_of(o)), o['class_label'])
        tracks = [Track(cam, ref, tuple(sorted(items.values(), key=lambda o: o.timestamp_us))) for (cam, ref), items in grouped.items()]
        manual = norm.get('manual_seed')
        if manual and (manual['at_us'] > base['as_of_us'] or not any(t.track_ref == manual['track_ref'] for t in tracks)):
            raise CoreRequestError('MANUAL_SEED_UNKNOWN')
        index = run.bindings.index.manifest
        interval = index['sampling']['per_camera'][0]['index_interval_us']
        values = {p['name']: p['value'] for p in run.bindings.parameter_set['parameters']}
        transitions = {(e['from_camera_id'], e['to_camera_id']): e['transition_id'] for e in run.bindings.graphs.camera['transitions']}
        doc, _, _ = response(tracks, transitions, as_of_us=base['as_of_us'],
                             parameters=Parameters(sample_interval_us=interval, min_score=values['link_min_score'],
                                                   local_track_min_score=values['link_min_score']),
                             clock_mapping_sha256=run.bindings.clock_sha256, decider=decider,
                             manual=(manual['track_ref'], manual['at_us']) if manual else None)
        # F3's single-view chain retains colour-compatible candidates. Manual
        # re-selection must also offer the remaining independent people; keep
        # them explicitly unassociated rather than merging their identity.
        emitted = {(s['track_ref'], oid) for s in doc['sightings'] for oid in s['observation_ids']}
        extra = []
        for sight in base['sightings']:
            for oid in sight['observation_ids']:
                if (sight['track_ref'], oid) in emitted:
                    continue
                row, _ = obs[oid]
                stamp = row['timestamp_us']
                if extra and extra[-1]['track_ref'] == sight['track_ref'] and extra[-1]['range_us'][1] == stamp:
                    extra[-1]['range_us'][1] = min(stamp + interval, base['as_of_us'])
                    extra[-1]['observation_ids'].append(oid)
                else:
                    extra.append({**sight, 'range_us': [stamp, min(stamp + interval, base['as_of_us'])],
                                  'observation_ids': [oid], 'selected_for_single_view': False,
                                  'link_kind': 'LOCAL_SEED', 'association_state': 'UNASSOCIATED_LOCAL_CANDIDATE'})
        doc['sightings'] = sorted(doc['sightings'] + extra, key=lambda s: (s['range_us'][0], s['camera_id'], s['track_ref']))
        doc['resolved_scope'], doc['resolved_time'] = base['resolved_scope'], base['resolved_time']
        if base['status'] == 'PARTIAL':
            doc['status'] = 'PARTIAL'
        doc['reasons'] = list(dict.fromkeys(base['reasons'] + [r for r in doc['reasons'] if r != 'GRAPH_NOT_APPROVED']))
        if manual:
            doc['manual_seed'] = dict(manual, applied=any(r.get('reason') == 'OPERATOR_SELECTION' for r in doc['association_audit']))
        if doc['single_view'] and doc['single_view'][-1]['kind'] in {'GAP', 'LOST'}:
            doc['blind'] = _blind_for_track(run, doc['sightings'], doc['as_of_us'], display_positions)
        base = doc
    base['provenance'] = {'producer': 'demo-core-agent-track', 'gt_read': False, 'formal_eligible': False,
                          'parameter_mode': run.bindings.parameter_set['approval']['status'],
                          'parameter_set_sha256': run.bindings.parameter_sha256,
                          'association_scope': 'UNCONFIRMED_CROSS_CAMERA_HYPOTHESES'}
    if payload.get('switch_mode') == 'AGENT_SEQUENTIAL':
        rows = [r for r in base.get('association_audit', []) if r.get('reason') == 'AGENT_SERVICE_DECISION']
        base['agent'] = {'switch_mode': 'AGENT_SEQUENTIAL', 'available': decider is not None, 'unavailable_reason': unavailable_reason,
                         'decisions': len(rows), 'adopted': sum(bool(r.get('adopted_track_ref')) for r in rows),
                         'fallbacks': sum(bool(r.get('fallback_reason')) for r in rows), 'model_calls_total': decider.calls if decider else 0,
                         'agent_used': any(r.get('reason') == 'AGENT_ASSOCIATION_HYPOTHESIS' for r in base.get('association_audit', []))}
    base['output_sha256'] = canonical_hash(base, exclude=('output_sha256', 'stats'))
    return base
