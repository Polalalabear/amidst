#!/usr/bin/env python3
"""D147: score tracking recall against the user's human reference (evaluation only).

Reads the owned detection indexes (read-only, no inference) and, optionally, real
track-response JSON files from a real-e2e run. Prints a Markdown table and writes JSON.

    AMIDST_DEMO_HOME=~/amidst-artifacts/demo-owned-v1 \
    python3 -B scripts/eval_d147_recall.py --out /tmp/d147.json \
        --track A4-1=<dir>/A4-1-track-response.json --track B4-1=<dir>/B4-1-track-response.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from amidst.evaluation.track_recall import (  # noqa: E402
    box_continuation_frames, camera_frames, load_reference, person_frames, score_frames, score_single_view, score_sightings, score_single_view_switching)

# D147 prototype candidate: person seed at the index floor, any-class continuation that may shrink to a part box.
RECOMMENDED = {'seed_score': 0.3, 'max_area_ratio': 12.0}
DEFAULT_REFERENCE = ROOT / 'configs/evaluation/d147_human_reference_v1.json'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_records(home, label):
    folder = Path(home).expanduser() / 'data/indexes' / label
    manifest = json.loads((folder / 'detection_index.json').read_text())
    records_path = folder / manifest['records_ref']
    if sha256(records_path) != manifest['records_file_sha256']:
        raise SystemExit('RECORDS_SHA256_MISMATCH ' + label)
    records = [json.loads(line) for line in records_path.read_text().splitlines() if line.strip()]
    return manifest, records


def strategies(records, cameras):
    out = {}
    out['person>=0.4 (current)'] = {c: person_frames(records, c, 0.4) for c in cameras}
    out['person>=0.3'] = {c: person_frames(records, c, 0.3) for c in cameras}
    cont = {c: box_continuation_frames(records, c) for c in cameras}
    out['box continuation (any class)'] = {c: v[0] for c, v in cont.items()}
    low = {c: box_continuation_frames(records, c, **RECOMMENDED) for c in cameras}
    out['seed>=0.3 + continuation, area<=12x (recommended)'] = {c: v[0] for c, v in low.items()}
    return out, {c: len(v[1]) for c, v in cont.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--home', default=os.environ.get('AMIDST_DEMO_HOME', '~/amidst-artifacts/demo-owned-v1'))
    ap.add_argument('--reference', default=str(DEFAULT_REFERENCE))
    ap.add_argument('--track', action='append', default=[], help='LABEL=path to a q_core_track response JSON')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    reference = load_reference(args.reference)
    tracks = dict(item.split('=', 1) for item in args.track)
    result = {'reference': {'path': os.path.relpath(args.reference, ROOT), 'sha256': sha256(args.reference)},
              'inference_run': False, 'runs': []}
    lines = ['| 場景 | 段落 | 鏡頭 | 參考格數 | ' + ' | '.join(['現行 ≥0.4', '≥0.3', '不分類別接續（起點 ≥0.4）', '建議：起點 ≥0.3＋接續（框可縮 12 倍）', '實際 sightings 召回']) + ' |',
             '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for run in reference['runs']:
        manifest, records = load_records(args.home, run['label'])
        if manifest['run_id'] != run['run_id']:
            raise SystemExit('RUN_ID_MISMATCH ' + run['label'])
        cameras = sorted({r['camera_id'] for r in records})
        found, continued = strategies(records, cameras)
        scored = {name: score_frames(records, run, frames) for name, frames in found.items()}
        totals = {name: {c: len(frames[c]) for c in cameras} for name, frames in found.items()}
        entry = {'label': run['label'], 'run_id': run['run_id'], 'index_content_sha256': manifest['content_sha256'],
                 'records_file_sha256': manifest['records_file_sha256'], 'strategies': scored,
                 'frames_per_camera': totals, 'continuation_only_frames_per_camera': continued}
        actual = None
        if run['label'] in tracks:
            path = tracks[run['label']]
            response = json.loads(Path(path).read_text())
            actual = score_sightings(records, run, response['sightings'])
            entry['single_view_switching'] = score_single_view_switching(run, response['single_view'])
            entry['single_view_per_camera_diagnostic'] = score_single_view(records, run, response['single_view'])
            entry['track_response'] = {'path': path, 'sha256': sha256(path), 'scores': actual}
        result['runs'].append(entry)
        for i, interval in enumerate(run['intervals']):
            cells = [scored[name][i] for name in found]
            pct = lambda row: '—' if row['recall'] is None else f"{row['covered_frames']} ({row['recall']*100:.0f}%)"
            act = pct(actual[i]) if actual else 'UNKNOWN'
            lines.append(f"| {run['label']} | {interval['id']} | {interval['camera_id']} | {cells[0]['reference_frames']} | "
                         + ' | '.join(pct(c) for c in cells) + f' | {act} |')
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('\n'.join(lines))
    print('\n| 場景 | 參考時間聯集 (s) | 正確切鏡 (s) | 單畫面切鏡比例 |\n|---|---:|---:|---:|')
    for entry in result['runs']:
        score = entry.get('single_view_switching')
        if score:
            print(f"| {entry['label']} | {score['reference_union_us']/1e6:g} | {score['covered_us']/1e6:g} | {score['ratio']:.2%} |")


if __name__ == '__main__':
    main()
