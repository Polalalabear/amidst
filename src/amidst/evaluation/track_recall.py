"""D147 tracking-recall evaluation and an offline candidate-strategy prototype.

Two separate parts:

* Strategies (``person_frames``, ``box_continuation_frames``) look only at detection-index
  records. They never see the human reference.
* Scoring (``score_frames``, ``score_single_view``) compares strategy output or a real
  track response with the human reference in ``configs/evaluation/d147_human_reference_v1.json``.

This module lives outside the inference roots (``src/amidst/q1q5``, ``frontend/workbench-v2``)
and is not imported by them. The human reference is for evaluation only.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = 'amidst.human-track-reference.v1'


def load_reference(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != SCHEMA or data.get('use') != 'EVALUATION_ONLY':
        raise ValueError('REFERENCE_SCHEMA_INVALID')
    for run in data['runs']:
        for item in run['intervals']:
            start, end = item['range_us']
            if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end):
                raise ValueError('REFERENCE_INTERVAL_INVALID ' + item['id'])
    return data


def camera_frames(records, camera_id):
    """Index records of one camera, sorted by time, as {timestamp_us: record}."""
    rows = {}
    for row in records:
        if row['camera_id'] == camera_id:
            rows[row['timestamp_us']] = row
    return dict(sorted(rows.items()))


def _colors(detection):
    verdicts = (detection.get('color') or {}).get('verdicts') or {}
    return frozenset(k for k, v in verdicts.items() if v in {'STRONG', 'WEAK'})


def person_frames(records, camera_id, min_score):
    """Frames with at least one person detection at or above ``min_score``."""
    return {t for t, row in camera_frames(records, camera_id).items()
            if any(d['class_label'] == 'person' and d['score'] >= min_score for d in row['detections'] or [])}


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _area(box):
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_continuation_frames(records, camera_id, *, seed_score=0.4, continue_score=0.3, max_miss_frames=2,
                            min_iou=0.2, max_center_ratio=0.6, max_area_ratio=4.0, require_seed_color=True,
                            size_smoothing=0.5):
    """Class-agnostic box continuation.

    A track starts only from a person detection (score >= ``seed_score``, with a colour
    verdict when ``require_seed_color``). After that, any detection box of any class with
    score >= ``continue_score`` may continue it when the box overlaps the reference box
    (IoU >= ``min_iou``) or its centre lies within ``max_center_ratio`` x the reference box
    height, and its area is within ``max_area_ratio`` of it (this drops full-frame boxes such
    as 'umbrella' or 'dining table'). Among those, the box with the lowest cost
    ``(1 - IoU) + |log(area ratio)| / 2 + centre distance / height`` wins, with person boxes
    preferred at equal cost. The reference box takes the winner's centre while its size moves
    only ``size_smoothing`` of the way, so part boxes (a head, a hand) do not shrink the track.
    The track ends after ``max_miss_frames`` frames without a match.

    Returns ``(covered, continued)``: every frame on a track, and the subset of those
    frames carried only by a non-person box.
    """
    import math
    covered, continued = set(), set()
    last, misses = None, 0
    for t, row in camera_frames(records, camera_id).items():
        detections = row['detections'] or []
        if last is not None:
            best, best_key = None, None
            height = max(1.0, last[3] - last[1])
            last_area = max(1.0, _area(last))
            lc = ((last[0] + last[2]) / 2, (last[1] + last[3]) / 2)
            for d in detections:
                if d['score'] < continue_score:
                    continue
                box = d['bbox_xyxy_px']
                area = _area(box)
                if area <= 0 or area > max_area_ratio * last_area or area * max_area_ratio < last_area:
                    continue
                c = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                dist = ((c[0] - lc[0]) ** 2 + (c[1] - lc[1]) ** 2) ** 0.5
                iou = _iou(box, last)
                if iou < min_iou and dist > max_center_ratio * height:
                    continue
                cost = (1 - iou) + abs(math.log(area / last_area)) / 2 + dist / height
                key = (round(cost, 6), d['class_label'] != 'person', -d['score'])
                if best_key is None or key < best_key:
                    best, best_key = d, key
            if best is not None:
                covered.add(t)
                if best['class_label'] != 'person':
                    continued.add(t)
                b = best['bbox_xyxy_px']
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                w = (last[2] - last[0]) + size_smoothing * ((b[2] - b[0]) - (last[2] - last[0]))
                h = (last[3] - last[1]) + size_smoothing * ((b[3] - b[1]) - (last[3] - last[1]))
                last, misses = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 0
                continue
            misses += 1
            if misses > max_miss_frames:
                last, misses = None, 0
        if last is None:
            seeds = [d for d in detections if d['class_label'] == 'person' and d['score'] >= seed_score
                     and (_colors(d) or not require_seed_color)]
            if seeds:
                seed = max(seeds, key=lambda d: d['score'])
                last, misses = list(seed['bbox_xyxy_px']), 0
                covered.add(t)
    return covered, continued


def reference_frames(records, interval):
    """Index frame times of the interval's camera that fall inside the reference range."""
    start, end = interval['range_us']
    return {t for t in camera_frames(records, interval['camera_id']) if start <= t < end}


def score_frames(records, reference_run, frames_by_camera):
    """Recall of a strategy's frames against each reference interval of one run."""
    rows = []
    for interval in reference_run['intervals']:
        expected = reference_frames(records, interval)
        got = frames_by_camera.get(interval['camera_id'], set()) & expected
        rows.append({'id': interval['id'], 'camera_id': interval['camera_id'], 'range_us': interval['range_us'],
                     'reference_frames': len(expected), 'covered_frames': len(got),
                     'recall': round(len(got) / len(expected), 4) if expected else None})
    return rows


def single_view_frames(single_view, camera_id, frame_times):
    """Frame times at which a track response shows ON_CAMERA on ``camera_id``."""
    spans = [s['range_us'] for s in single_view if s.get('kind') == 'ON_CAMERA' and s.get('camera_id') == camera_id]
    return {t for t in frame_times if any(a <= t < b for a, b in spans)}


def score_single_view(records, reference_run, single_view):
    """Recall of a real track response (its single_view) against each reference interval."""
    by_camera = {}
    for interval in reference_run['intervals']:
        cam = interval['camera_id']
        by_camera[cam] = single_view_frames(single_view, cam, camera_frames(records, cam))
    return score_frames(records, reference_run, by_camera)


def score_sightings(records, reference_run, sightings):
    """D150 per-camera source observations, including simultaneous local hypotheses.

    Score actual sighting coverage only; display gap merging does not earn recall.
    """
    frames = {}
    for interval in reference_run['intervals']:
        camera = interval['camera_id']
        spans = [s['range_us'] for s in sightings if s['camera_id'] == camera]
        frames[camera] = {t for t in camera_frames(records, camera) if any(a <= t < b for a, b in spans)}
    return score_frames(records, reference_run, frames)


def score_single_view_switching(reference_run, single_view):
    """D150 time-weighted correct-camera coverage over the reference time union.

    Split at every reference/display endpoint so overlaps never double-count.
    Any camera covered by a reference interval at that time earns credit.
    """
    intervals = reference_run['intervals']
    boundaries = sorted({t for r in intervals for t in r['range_us']} |
                        {t for s in single_view for t in s['range_us']})
    total = covered = 0
    for start, end in zip(boundaries, boundaries[1:]):
        cameras = {r['camera_id'] for r in intervals if r['range_us'][0] <= start < r['range_us'][1]}
        if not cameras:
            continue
        total += end - start
        if any(s.get('kind') == 'ON_CAMERA' and s['camera_id'] in cameras
               and s['range_us'][0] <= start < s['range_us'][1] for s in single_view):
            covered += end - start
    return {'reference_union_us': total, 'covered_us': covered,
            'ratio': round(covered / total, 4) if total else None}
