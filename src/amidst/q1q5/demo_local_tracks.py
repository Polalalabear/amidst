"""All camera-local candidates from already validated DEMO_DEFAULT index records.

Pure in-memory replay with the frozen IoU/grid parameters. New seeds have new
segment references; reacquisition never resurrects a terminated local identity.
"""
from collections import Counter
from copy import deepcopy

from amidst.q1q5.cross_camera_demo import Observation, Track
from amidst.q1q5.linker import LinkParameters, LocalLinker


def local_candidates(manifest, records, config, config_sha256):
    values = {item['name']: item['value'] for item in config['parameters']}
    metadata = {item['camera_id']: item for item in manifest['sampling']['per_camera']}
    tracks, audit = [], []
    for camera, meta in sorted(metadata.items()):
        params = LinkParameters(
            'demo-default:' + config_sha256[:16], config_sha256, manifest['index_id'],
            config['run_id'], meta['index_interval_us'], values['link_max_gap_us'],
            values['link_max_gap_samples'], values['link_iou_min'],
            values['link_center_dist_max_diag_ratio'], values['link_min_score'],
            values['link_color_rule'], values['link_ambiguity_margin'])
        sequence = sorted((dict(row, run_id=config['run_id'], clock_id=config['clock_id'])
                           for row in records if row['camera_id'] == camera),
                          key=lambda row: row['frame_index'])
        active, segments = [], {}

        def observe(tracker, row, oid):
            detection = next(d for d in row['detections'] if d['observation_id'] == oid)
            colors = frozenset(k for k, v in (detection.get('color') or {}).get('verdicts', {}).items()
                               if v in {'STRONG', 'WEAK'})
            segments.setdefault(tracker.segment_id, []).append(Observation(
                camera, row['timestamp_us'], oid, detection['score'], colors))

        for row in sequence:
            previews = []
            for tracker in active:
                preview = deepcopy(tracker)
                step = preview.step(row)
                previews.append((preview, step))
            claims = Counter(step.link['next_observation_id'] for _, step in previews
                             if step and step.link['next_observation_id'])
            active, used, ambiguous = [], set(), set()
            for tracker, step in previews:
                if step is not None:
                    oid = step.link['next_observation_id']
                    if step.link['decision'] == 'AMBIGUOUS_LINK' or (oid and claims[oid] > 1):
                        ambiguous.update(step.ambiguous_observation_ids)
                        if oid:
                            ambiguous.add(oid)
                        audit.append({'camera_id': camera, 'timestamp_us': row['timestamp_us'],
                                      'reason': 'AMBIGUOUS_LINK', 'track_ref': tracker.segment_id})
                        continue
                    if oid:
                        observe(tracker, row, oid)
                        used.add(oid)
                    else:
                        audit.append({'camera_id': camera, 'timestamp_us': row['timestamp_us'],
                                      'reason': step.link['decision'], 'track_ref': tracker.segment_id,
                                      'state': step.state})
                    if step.state == 'SEARCHING':
                        continue
                active.append(tracker)
            eligible = [d for d in row['detections'] or []
                        if d['class_label'] == 'person' and d['score'] >= params.min_score
                        and d['observation_id'] not in used | ambiguous]
            if len(eligible) > 1:
                audit.append({'camera_id': camera, 'timestamp_us': row['timestamp_us'],
                              'reason': 'AMBIGUOUS_SEED', 'count': len(eligible)})
            elif eligible:
                tracker = LocalLinker(row, eligible[0]['observation_id'], parameters=params,
                                      stride_samples=meta['stride_samples'],
                                      index_grid_origin_frame=meta['index_grid_origin_frame'])
                observe(tracker, row, eligible[0]['observation_id'])
                active.append(tracker)
        tracks.extend(Track(camera, ref, tuple(observations)) for ref, observations in segments.items())
    return tracks, audit
