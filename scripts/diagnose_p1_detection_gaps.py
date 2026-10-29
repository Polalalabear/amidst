"""Diagnose the named P1 user-reported frames from existing pinned outputs only."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

MANIFEST_PIN = '6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'
RECORDING = '2777741d96ac9aff5bffb2f61a4d2938'
REPORT_REF = 'https://github.com/Polalalabear/amidst/pull/228#issuecomment-6416863116'
TARGETS = [('A', i) for i in range(50, 61)] + [('B', i) for i in
    (123, 125, 130, 132, 133, 136, 138, 143, 144, 150, 151, 154, 155, 156, 157, 158, 159)]
VISUAL_SAMPLES = {('A', 50), ('A', 58), ('B', 123), ('B', 156)}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(reference, current):
    l, t = max(reference[0], current[0]), max(reference[1], current[1])
    r, b = min(reference[2], current[2]), min(reference[3], current[3])
    area = max(0, r - l) * max(0, b - t)
    total = ((reference[2] - reference[0]) * (reference[3] - reference[1])
             + (current[2] - current[0]) * (current[3] - current[1]) - area)
    distance = math.hypot((current[0] + current[2] - reference[0] - reference[2]) / 2,
                          (current[1] + current[3] - reference[1] - reference[3]) / 2)
    diag = math.hypot(reference[2] - reference[0], reference[3] - reference[1])
    return dict(iou=area / total, center_distance_diag_ratio=distance / diag)


def diagnose(root):
    assert root.is_absolute() and root.resolve() == root
    inputs = {}

    def read(rel, expected=None):
        path = root / rel
        assert path.resolve().is_relative_to(root) and not path.is_symlink()
        raw = path.read_bytes()
        pin = digest(raw)
        assert expected is None or pin == expected, rel
        inputs[rel] = dict(sha256=pin, bytes=len(raw), mtime_ns=path.stat().st_mtime_ns)
        return raw

    manifest = json.loads(read('MANIFEST.json', MANIFEST_PIN))

    def pinned(rel):
        return read(rel, manifest['files'][rel]['sha256'])

    spec = json.loads(pinned('BUNDLE.json'))
    registry = json.loads(pinned(spec['registry_ref']))
    data_root = Path(spec['registry_ref']).parent
    docs = {}
    for name in ('index', 'records', 'parameter'):
        pin = registry['documents'][name]
        raw = pinned((data_root / pin['path']).as_posix())
        assert digest(raw) == pin['file_sha256']
        docs[name] = raw
    index = json.loads(docs['index'])
    records = [json.loads(line) for line in docs['records'].splitlines()]
    assert digest(docs['records']) == index['records_file_sha256']
    metadata = {r['camera_id']: r for r in index['sampling']['per_camera']}
    parameters = {r['name']: r['value'] for r in json.loads(docs['parameter'])['parameters']}
    rec_ref = Path(spec['recordings_ref']) / (RECORDING + '.json')
    recording = json.loads(pinned(rec_ref.as_posix()))
    assert recording['request']['seed']['color'] is None
    assert digest(recording['links'].encode()) == recording['response']['links_sha256']
    assert digest(recording['decisions'].encode()) == recording['response']['decisions_sha256']
    links = {r['frame_ref']: r for r in map(json.loads, recording['links'].splitlines())}
    frames = {(r['camera_id'], r['frame_index']): r for r in records}
    observations = {o['observation_id']: o for r in records for o in r['detections'] or []}
    rgb_doc = json.loads(pinned(spec['rgb_ref']))
    assert digest(json.dumps({k: v for k, v in recording['response'].items()
                             if k not in ('output_sha256', 'stats')}, sort_keys=True,
                            separators=(',', ':'), ensure_ascii=True).encode()) == recording['response']['output_sha256']
    rgb = {(r['camera_id'], r['frame_index']): r for r in rgb_doc['records']}
    rows = []
    for camera, frame in TARGETS:
        row = frames[camera, frame]
        assert row['frame_state'] == 'INFERRED' and row['timestamp_us'] == frame * 50000
        link = links.get(row['frame_ref'])
        assert link and link['decision'] == 'NO_CANDIDATE'
        people = [o for o in row['detections'] if o['class_label'] == 'person']
        eligible = [o for o in people if o['score'] >= parameters['link_min_score']]
        previous = observations[link['prev_observation_id']]['bbox_xyxy_px']
        audit = link.get('matching_audit') or {}
        reference = audit.get('reference_bbox_xyxy_px')
        geometry = []
        for observation in eligible:
            current = observation['bbox_xyxy_px']
            checks = {'last': measure(previous, current)}
            if reference is not None:
                checks['reference'] = measure(reference, current)
            checks['observation_id'] = observation['observation_id']
            geometry.append(checks)
        if not people:
            category = 'NO_STORED_PERSON_AT_INDEX_FLOOR'
        elif not eligible:
            category = 'PERSON_BELOW_LINK_SCORE'
        else:
            passes = any(v['iou'] >= parameters['link_iou_min']
                         and v['center_distance_diag_ratio'] <= parameters['link_center_dist_max_diag_ratio']
                         for check in geometry for k, v in check.items() if k in ('last', 'reference'))
            category = 'LINK_GEOMETRY_REJECTION' if not passes else 'UNEXPLAINED_LINK_REJECTION'
        rgb_row = rgb[camera, frame]
        rel = (Path(spec['rgb_ref']).parent / rgb_row['rgb_ref']).as_posix()
        pinned(rel)
        matching = [s for s in recording['response']['timeline']
                    if s['range_us'][0] <= row['timestamp_us'] < s['range_us'][1]]
        assert len(matching) == 1 and matching[0]['kind'] == 'GAP'
        assert matching[0]['camera_shown'] == camera
        rows.append(dict(camera_id=camera, frame_index=frame, source_time_us=row['timestamp_us'],
            frame_ref=row['frame_ref'], frame_state=row['frame_state'], visibility_evidence='REPORTED_USER_228',
            selected_for_manual_visual_review=(camera, frame) in VISUAL_SAMPLES,
            category=category, person_scores=[p['score'] for p in people],
            non_person_labels=sorted({o['class_label'] for o in row['detections'] if o['class_label'] != 'person'}),
            geometry=geometry, link_decision=link['decision'], link_schema_version=link['schema_version'],
            gap_us=matching[0]['range_us'], rgb_sha256=rgb_row['file_sha256']))
    # Verify immutable inputs have the same bytes and mtimes after the analysis.
    for rel, pin in inputs.items():
        path = root / rel
        assert digest(path.read_bytes()) == pin['sha256'] and path.stat().st_mtime_ns == pin['mtime_ns']
    public_pins = {key: {k: v for k, v in value.items() if k != 'mtime_ns'} for key, value in inputs.items()}
    return dict(schema_version='q-demo.p1-reported-gap-diagnosis.v1', source_manifest_sha256=MANIFEST_PIN,
        source_recording_id=RECORDING, source_commit=manifest['source_commit'], user_report_ref=REPORT_REF,
        input_pins=public_pins, inputs_unchanged=True, rows=rows,
        category_counts=dict(Counter(row['category'] for row in rows)),
        camera_category_counts={camera: dict(Counter(row['category'] for row in rows if row['camera_id'] == camera)) for camera in ('A', 'B')},
        thresholds={key: parameters[key] for key in ('query_min_score', 'link_min_score', 'link_iou_min', 'link_center_dist_max_diag_ratio', 'link_max_gap_us')},
        index_score_floor=index['detector']['index_score_floor'],
        index_frames=len(records), reported_frames=len(rows), visual_review_sample_frames=len(VISUAL_SAMPLES),
        inference_or_render_run=False, gt_or_renderer_outputs_read=False,
        raw_logits_below_floor='NOT_AVAILABLE_IN_NAMED_BUNDLE', recall_or_identity_accuracy=None,
        run_end_us=8000000, run_end_is_sample=False,
        source_intervals_us={camera: metadata[camera]['source_frame_interval_us'] for camera in ('A', 'B')})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = diagnose(args.bundle)
    args.output.mkdir(mode=0o700)
    (args.output / 'summary.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    fields = ['camera_id', 'frame_index', 'source_time_us', 'frame_state', 'visibility_evidence', 'selected_for_manual_visual_review',
              'category', 'person_scores', 'non_person_labels', 'geometry', 'link_decision', 'link_schema_version', 'gap_us', 'rgb_sha256', 'frame_ref']
    with (args.output / 'frames.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in result['rows']:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    print(json.dumps({key: result[key] for key in ('category_counts', 'camera_category_counts', 'reported_frames', 'inputs_unchanged')}))


if __name__ == '__main__':
    main()
