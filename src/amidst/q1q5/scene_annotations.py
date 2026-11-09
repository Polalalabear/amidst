"""Explicit static RGB annotations for search/display only, outside tracking."""
from dataclasses import replace
import hashlib
import json


def bind_annotations(run, path):
    raw = path.read_bytes()
    document = json.loads(raw)
    if document.get('schema_version') != 'q-demo.scene-annotations.v1':
        raise ValueError('SCENE_ANNOTATION_SCHEMA_INVALID')
    rows = []
    for annotation in document['annotations']:
        if annotation['run_id'] != run.catalog['run_id']:
            continue
        camera = annotation['camera_id']
        start, end = annotation['range_us']
        x0, y0, x1, y1 = annotation['bbox_xyxy_px']
        w, h = annotation['frame_size_px']
        if (camera not in run.catalog['camera_ids'] or annotation['class_label'] not in run.catalog['class_labels']
                or annotation['motion'] != 'STATIC' or not 0 <= start < end <= run.bindings.clock.duration_us
                or not 0 <= x0 < x1 <= w or not 0 <= y0 < y1 <= h):
            raise ValueError('SCENE_ANNOTATION_SCOPE_INVALID')
        indexed = {r['frame_index']: r for r in run.bindings.index.records if r['camera_id'] == camera}
        for frame in annotation['checked_frames']:
            if indexed.get(frame['frame_index'], {}).get('rgb_file_sha256') != frame['rgb_file_sha256']:
                raise ValueError('SCENE_ANNOTATION_RGB_PIN_MISMATCH')
        rows.append(annotation)
    if len({a['annotation_id'] for a in rows}) != len(rows):
        raise ValueError('SCENE_ANNOTATION_DUPLICATE')
    return replace(run, scene_annotations=tuple(rows), annotation_set_sha256=hashlib.sha256(raw).hexdigest())


def bootstrap_annotations(run):
    return [{'annotation_id': a['annotation_id'], 'class_label': a['class_label'],
             'camera_ids': [a['camera_id']]} for a in run.scene_annotations]


def search_annotations(run, feature, source_range, media_token_for_frame):
    hits = {}
    # Annotation has no colour authority. A colour filter cannot be satisfied by it.
    if feature.get('color_label'):
        return hits
    for annotation in run.scene_annotations:
        if annotation['class_label'] != feature['class_label']:
            continue
        start = max(annotation['range_us'][0], source_range[0])
        end = min(annotation['range_us'][1], source_range[1])
        if start >= end:
            continue
        camera = annotation['camera_id']
        frames = [r for r in run.bindings.index.records if r['camera_id'] == camera
                  and start <= r['timestamp_us'] < end]
        if not frames:
            continue
        first = min(frames, key=lambda r: r['timestamp_us'])
        if not callable(media_token_for_frame):
            raise ValueError('SCENE_ANNOTATION_MEDIA_ISSUER_REQUIRED')
        segment = {'range_us': [start, end], 'matched_frames': 0, 'evaluated_frames': 0,
                   'representative': {'frame_ref': first['frame_ref'], 'observation_ids': [],
                                      'media_token': media_token_for_frame(first['frame_ref'])}}
        hit = hits.setdefault(camera, {'segments': [], 'basis': []})
        hit['segments'].append(segment)
        hit['basis'].append({'kind': 'SCENE_ANNOTATION', 'class_label': annotation['class_label'],
                            'annotation_id': annotation['annotation_id'],
                            'annotation_set_sha256': run.annotation_set_sha256, 'evidence_state': 'ANNOTATED'})
    return hits
