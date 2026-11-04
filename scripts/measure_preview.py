"""Port the LOCAL preview RT-DETR measurement without private poses or paths.

Only an explicit --execute authorizes loading the separately supplied official
source/weights and safe preview pixels. This command does not run on --help/import.
Reporting threshold 0.30 is PROPOSED_REPORTING_ONLY, never a runtime parameter.
"""
from __future__ import annotations
import json
from pathlib import Path
import statistics
import sys
import time
import zipfile
from r004_local_common import (argv_after_separator, authorize, checked_path, digest, disk,
    execution_options, file_sha, new_output, parser, pinned, require, write_json)

ZIP_SHA256 = 'e6014ae32d2d384799e353a7a6a511aaef1dad77763492738dfef70e714d6564'
ZIP_PREFIX = 'RT-DETR-df2a96c8c3a098567a1149bf0248da6efe6d495d/rtdetr_pytorch/'


def parse_args(argv=None):
    p = parser(__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--index-sha256', required=True)
    p.add_argument('--official-zip', type=Path, required=True)
    p.add_argument('--model-source', type=Path, required=True)
    p.add_argument('--weights', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    execution_options(p)
    return p.parse_args(argv_after_separator(argv))


def percentile(values, q):
    if not values:
        return None
    h = sorted(values)
    x = (len(h) - 1) * q
    lo = int(x)
    hi = min(lo + 1, len(h) - 1)
    return h[lo] + (h[hi] - h[lo]) * (x - lo)


def main(argv=None):
    args = parse_args(argv)
    authorize(args)
    index_path = checked_path(args.index)
    index = json.loads(pinned(index_path, args.index_sha256))
    require(index.get('event_run') is False and index.get('data_origin') == 'ACTUAL_BLENDER', 'PREVIEW_ONLY')
    official = checked_path(args.official_zip)
    require(file_sha(official) == ZIP_SHA256, 'OFFICIAL_ZIP_MISMATCH')
    with zipfile.ZipFile(official) as archive:
        expected = {name[len(ZIP_PREFIX):]: digest(archive.read(name)) for name in archive.namelist()
                    if name.startswith(ZIP_PREFIX + 'src/') and name.endswith('.py')}
    source = checked_path(args.model_source)
    actual = {p.relative_to(source).as_posix(): file_sha(p) for p in (source / 'src').rglob('*.py')}
    require(actual and actual == expected, 'OFFICIAL_CODE_MISMATCH')
    # Validate all source names/hashes before creating any result or loading a model.
    rows = index['records']
    for row in rows:
        path = checked_path(index_path.parent / row['file_ref'])
        require(path.is_relative_to(index_path.parent) and file_sha(path) == row['file_sha256'], 'RGB_PIN_MISMATCH')
    out = new_output(args.output)
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from amidst.q1q5.detection_index import OfficialRTDetrR18
    model = OfficialRTDetrR18(source, checked_path(args.weights), source_hashes=expected, seed=7, threads=2)
    groups, records = {}, []
    for row in rows:
        disk(out, 32 * 1024**2)
        path = index_path.parent / row['file_ref']
        require(file_sha(path) == row['file_sha256'], 'RGB_CHANGED')
        with Image.open(path) as raw:
            image = raw.convert('RGB')
            start = time.monotonic()
            predictions = model(image)
            elapsed = time.monotonic() - start
            image.close()
        detections = [{**d, 'class_label': model.class_labels[d['class_id']]} for d in predictions]
        records.append({'camera_id': row['camera_id'], 'preview_variant': row['preview_variant'],
            'frame_index': row['frame_index'], 'rgb_file_sha256': row['file_sha256'],
            'detections': detections, 'stats': {'forward_ms': elapsed * 1000}})
        persons = [d for d in detections if d['class_label'] == 'person' and d['score'] >= .30]
        g = groups.setdefault(row['preview_variant'], {'frames': 0, 'frames_with_person': 0,
                                                      'heights_px': [], 'forward_ms': []})
        g['frames'] += 1
        g['frames_with_person'] += bool(persons)
        g['heights_px'] += [d['bbox_xyxy_px'][3] - d['bbox_xyxy_px'][1] for d in persons]
        g['forward_ms'].append(elapsed * 1000)
    from r004_local_common import write_bytes
    raw = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in records).encode()
    write_bytes(out / 'detections.jsonl', raw)
    for group in groups.values():
        heights = group.pop('heights_px')
        group['person_boxes'] = len(heights)
        group['bbox_height_px'] = {k: percentile(heights, q) for k, q in
                                  [('min', 0), ('p25', .25), ('median', .5), ('p75', .75), ('max', 1)]}
        group['forward_median_ms'] = statistics.median(group.pop('forward_ms'))
    write_json(out / 'report.json', {'schema_version': 'q-demo.preview-measurement.v1',
        'source_sha256': index['source_sha256'], 'rgb_index_file_sha256': args.index_sha256,
        'detector': model.metadata, 'reporting_score_floor': {'value': .30,
        'status': 'PROPOSED_REPORTING_ONLY', 'not_runtime_parameter': True}, 'groups': groups,
        'ground_truth_denominator': None, 'recall': 'NOT_MEASURED', 'detections_file_sha256': digest(raw)})


if __name__ == '__main__':
    main()
