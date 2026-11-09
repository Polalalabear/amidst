"""D148 camera-local replay of validated DEMO_DEFAULT index boxes.

Only indexed RGB detections participate. Seeds require a person and a colour
verdict; continuation is a geometric box hypothesis, never a colour verdict.
"""
import math

from amidst.q1q5.cross_camera_demo import Observation, Track

POLICY = {'seed_score': .3, 'continue_score': .3, 'min_iou': .2,
          'max_center_ratio': .6, 'max_area_ratio': 12, 'size_smoothing': .5,
          'max_miss_frames': 2}


def colors(detection):
    return frozenset(k for k, v in (detection.get('color') or {}).get('verdicts', {}).items()
                     if v in {'STRONG', 'WEAK'})


def continuation_key(detection, reference):
    if detection['score'] < POLICY['continue_score']:
        return None
    box = detection['bbox_xyxy_px']
    area = (box[2] - box[0]) * (box[3] - box[1])
    previous_area = max(1., (reference[2] - reference[0]) * (reference[3] - reference[1]))
    if area <= 0 or not 1 / POLICY['max_area_ratio'] <= area / previous_area <= POLICY['max_area_ratio']:
        return None
    height = max(1., reference[3] - reference[1])
    distance = math.hypot((box[0] + box[2] - reference[0] - reference[2]) / 2,
                          (box[1] + box[3] - reference[1] - reference[3]) / 2)
    intersection = max(0., min(box[2], reference[2]) - max(box[0], reference[0])) * max(
        0., min(box[3], reference[3]) - max(box[1], reference[1]))
    iou = intersection / (area + previous_area - intersection)
    if iou < POLICY['min_iou'] and distance > POLICY['max_center_ratio'] * height:
        return None
    cost = (1 - iou) + abs(math.log(area / previous_area)) / 2 + distance / height
    return round(cost, 6), detection['class_label'] != 'person', -detection['score']


def local_candidates(manifest, records, config, config_sha256):
    tracks, audit = [], []
    for meta in sorted(manifest['sampling']['per_camera'], key=lambda m: m['camera_id']):
        camera = meta['camera_id']
        reference, misses, observations, ref, previous_time = None, 0, [], None, None

        def finish():
            if observations:
                tracks.append(Track(camera, ref, tuple(observations)))

        for row in sorted((r for r in records if r['camera_id'] == camera), key=lambda r: r['timestamp_us']):
            # Missing index rows count as misses too; never continue across an unbounded hole.
            if reference is not None and previous_time is not None:
                misses += max(0, (row['timestamp_us'] - previous_time) // meta['index_interval_us'] - 1)
                if misses > POLICY['max_miss_frames']:
                    finish(); reference, observations, misses = None, [], 0
            previous_time = row['timestamp_us']
            detections = row['detections'] or []
            winner = None
            if reference is not None:
                options = [(continuation_key(d, reference), d) for d in detections]
                options = [(key, d) for key, d in options if key is not None]
                if options:
                    winner = min(options, key=lambda item: item[0])[1]
                    box = winner['bbox_xyxy_px']
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    w = (reference[2] - reference[0] + box[2] - box[0]) / 2
                    h = (reference[3] - reference[1] + box[3] - box[1]) / 2
                    reference, misses = [cx-w/2, cy-h/2, cx+w/2, cy+h/2], 0
                else:
                    misses += 1
                    if misses > POLICY['max_miss_frames']:
                        audit.append({'camera_id': camera, 'timestamp_us': row['timestamp_us'],
                                      'reason': 'LOCAL_MISS_LIMIT', 'track_ref': ref, 'state': 'SEARCHING'})
                        finish(); reference, observations, misses = None, [], 0
            if reference is None:
                seeds = [d for d in detections if d['class_label'] == 'person'
                         and d['score'] >= POLICY['seed_score'] and colors(d)]
                if seeds:
                    winner = max(seeds, key=lambda d: d['score'])
                    if len(seeds) > 1:
                        audit.append({'camera_id': camera, 'timestamp_us': row['timestamp_us'],
                                      'reason': 'AMBIGUOUS_SEED', 'count': len(seeds)})
                        continue
                    reference = list(winner['bbox_xyxy_px'])
                    ref = 'd148-local:' + config_sha256[:16] + ':' + winner['observation_id']
            if winner is not None:
                continued = winner['class_label'] != 'person'
                observations.append(Observation(camera, row['timestamp_us'], winner['observation_id'],
                    winner['score'], frozenset() if continued else colors(winner),
                    winner['class_label'], 'BOX_CONTINUATION' if continued else 'PERSON_DETECTION'))
        finish()
    return tracks, audit
