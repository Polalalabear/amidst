"""Build the E8 Colab pack (#780; design docs/evaluation/E8_DESIGN_V1.md §6.1, §4). Runs on the Mac only.

Layout written to --out:
  requests/e8_part1.jsonl                     e8_level_request_v1 rows (decision point x level x order); no GT
  part1/frames/<case>/t<tick>/<cam>_<perm>.jpg  L4 frames, option letters drawn on the boxes (service_decider._jpeg)
  part1/ref/<case>.jpg                        reference crop of B1's first displayed box after ACQUIRE (advisor.crop_jpeg)
  part2/cases.json                            per case: camera order, scene sha, B1 file
  part2/ticks/<case>.jsonl                    per tick: tracker detections (bbox, score, HSV colour) + candidates with ground_xy
  part2/b1_frozen/<case>.json                 frozen B1 b-log (expected rows of the reproduction gate V2)
  part2/scene/<sha16>.json, part2/cameras.catalog.json
  scoring_only/answer_table.json              label-only answers per decision point, written ONLY by write_colab_answer_table
  PACK_INFO.json, MANIFEST.sha256
Mac-only, OUTSIDE the pack (--mac-index): decision-point type, family, E6 gt_regime, NO_SEED flags.

GT (``gt-boxes/<case>.a-log.json``) is read here and only here, reduced to expected_answer / cameras / detection ids by
``build_e7_colab_pack.expected_for_tick`` and never copied into any other pack file. Every pack JSON passes
``_scan_forbidden_gt_fields`` and ``arms.reject_forbidden``; ``verify_colab_pack_pre_upload`` must pass, or the whole pack is deleted.
Snapshots come from the frozen B1 b-log row T-1 (design §2.2), never from a replay.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_e7_colab_pack as E7  # noqa: E402
from amidst.evaluation import e8_requests as R  # noqa: E402
from amidst.evaluation.e7_scoring_bridge import (  # noqa: E402
    _scan_forbidden_gt_fields,
    verify_colab_pack_pre_upload,
    write_colab_answer_table,
)
from amidst.live_mode.aopen.arms import reject_forbidden  # noqa: E402

PACK_SCHEMA = 'e8_colab_pack_v1'
SIZE = E7.SIZE
FRAME_SCALE = 3


# ------------------------------------------------------------------ pure core (no filesystem)
def with_ground(dets: dict, order: list[str], projector) -> list[dict]:
    """E7 candidates (rounded boxes, per-camera D ids) + ground_xy from the RAW box, the same point Tracker.update projects."""
    cands = E7.candidates_for_tick(dets, order)
    raw = [d for cam in order for d in dets.get(cam, [])]
    for c, d in zip(cands, raw):
        b = d['bbox']
        xy = projector.ground(c['camera_id'], (b[0] + b[2]) / 2, b[3], *SIZE)
        c['ground_xy'] = [round(v, 3) for v in xy] if xy is not None else None
    return cands


def keep_display(row_t: dict | None, dets_t: dict) -> dict | None:
    """B1's displayed box at T -> (camera, D id). The b-log box is the raw detection bbox; match it exactly (design §2.3, G3)."""
    tr = (row_t or {}).get('tracking') or {}
    box, cam = tr.get('box'), tr.get('active_cam')
    if box is None:
        return None
    for i, d in enumerate(dets_t.get(cam, []), start=1):
        if [float(v) for v in d['bbox']] == [float(v) for v in box]:
            return {'camera_id': cam, 'detection_id': f'D{i}'}
    raise ValueError(f'KEEP_UNRESOLVED {cam} {box}')


def reference_of(b1_rows: list[dict]) -> dict | None:
    """First displayed B1 box at or after the first ACQUIRE event: the seed reference (design §2.2)."""
    acq = next((r['tick'] for r in b1_rows if any(e.get('type') == 'ACQUIRE' for e in r.get('events') or [])), None)
    if acq is None:
        return None
    for r in b1_rows:
        tr = r['tracking']
        if r['tick'] >= acq and tr.get('box') is not None:
            return {'tick': r['tick'], 'camera_id': tr['active_cam'], 'box': list(tr['box'])}
    return None


def frame_jobs(case_id: str, tick: int, perm: str, req: dict, cands: list[dict], cams: list[str]) -> dict[str, list]:
    """{cam: [(letter, box), ...]} for every camera with a frame; merged options are labelled on every member box."""
    box_of = {(c['camera_id'], c['detection_id']): c['box'] for c in cands}
    out: dict[str, list] = {cam: [] for cam in cams}
    for o in req['options']:
        for cam, did in o['members']:
            if cam in out:
                out[cam].append((o['key'], box_of[cam, did]))
    return out


def frame_rel(case_id: str, tick: int, cam: str, perm: str) -> str:
    return f'part1/frames/{case_id}/t{tick:06d}/{cam}_{perm}.jpg'


def case_requests(dp_list: list[dict], ticks_by: dict, order: list[str], b1_rows: dict, scene: dict, scene_sha: str,
                  projector, ref: dict | None, *, frames: bool = True) -> tuple[list[dict], dict, list, list[dict]]:
    """Part-1 rows for one case. Returns (requests, {base_id: p0 candidates}, frame jobs, mac rows)."""
    rows, cands_p0, jobs, mac = [], {}, [], []
    for dp in dp_list:
        tick, cid = dp['tick'], dp['case_id']
        if tick not in ticks_by or (tick - 1) not in b1_rows or tick not in b1_rows:
            raise ValueError(f'G1_MISSING_ROW {cid} t{tick}')
        dets, paths = ticks_by[tick]
        cands = with_ground(dets, order, projector)
        cams = [c for c in order if c in paths]
        snap = R.snapshot_of(b1_rows[tick - 1])
        keep = keep_display(b1_rows[tick], dets)
        no_seed = ref is None or ref['tick'] >= tick
        base = f'{cid}|t{tick}'
        cands_p0[base] = cands
        mac.append({'base_id': base, 'case_id': cid, 'tick': tick, 'dataset_group': dp['dataset_group'], 'family': dp['family'],
                    'type': dp['type'], 'gt_regime_frozen': dp.get('gt_regime'), 'no_seed': no_seed, 'keep_display': keep,
                    'b1_state_t_minus_1': snap and snap['state']})
        for perm in R.PERMS:
            e7_cands = R.permute([{k: v for k, v in c.items() if k != 'ground_xy'} for c in cands], perm, base)
            e7_row = {'variable_text': E7.variable_text(tick, e7_cands, cams), 'candidates': e7_cands, 'camera_ids': cams}
            for level in R.LEVELS:
                refs = None
                if level == 'L4':
                    refs = {'reference': None if no_seed else f'part1/ref/{cid}.jpg',
                            'frames': {cam: frame_rel(cid, tick, cam, perm) for cam in cams} if frames else {}}
                req = R.build_request(case_id=cid, dataset_group=dp['dataset_group'], tick=tick, level=level, perm=perm, cands=cands,
                                      camera_ids=cams, snapshot=snap, keep_display=keep, scene=scene, e7_row=e7_row,
                                      image_refs=refs, scene_sha256=scene_sha)
                rows.append(req)
                if level == 'L4' and frames:
                    for cam, boxes in frame_jobs(cid, tick, perm, req, cands, cams).items():
                        jobs.append((paths[cam], frame_rel(cid, tick, cam, perm), boxes))
    return rows, cands_p0, jobs, mac


def part2_rows(ticks: list, order: list[str], projector) -> list[dict]:
    return [{'tick': tick, 'dets': {cam: [dict(d) for d in dets.get(cam, [])] for cam in order}, 'cands': with_ground(dets, order, projector)}
            for tick, dets, _paths in ticks]


# ------------------------------------------------------------------ decision points (Mac)
def e3_points(corpus: Path, runs: Path) -> list[dict]:
    doc = json.loads(Path(corpus).read_text())
    return [{'case_id': c['case_id'], 'dataset_group': 'e3', 'family': f"E3-{c['family']}", 'tick': d['tick'], 'type': d['type'],
             'root': Path(corpus).parent, 'gt_root': Path(corpus).parent, 'b1': Path(runs) / c['case_id'] / 'B1.k1.json'}
            for c in doc['cases'] for d in c['decision_points']]


def e6_points(frozen: Path, det_root: Path, gt_root: Path, b1_dir: Path) -> list[dict]:
    doc = json.loads(Path(frozen).read_text())
    return [{'case_id': c['case_id'], 'dataset_group': 'e6', 'family': c['family_id'], 'tick': d['tick'], 'type': d['type'],
             'gt_regime': d['gt_regime'], 'root': Path(det_root), 'gt_root': Path(gt_root),
             'b1': Path(b1_dir) / c['case_id'] / 'B1.k1.json'}
            for c in doc['formal_cases'] for d in c['actual_decision_points']]


# ------------------------------------------------------------------ IO
def _scan(obj: Any, where: str) -> None:
    _scan_forbidden_gt_fields(obj, where)
    reject_forbidden(obj, where)
    if 'gt-boxes' in json.dumps(obj) or 'a-log' in json.dumps(obj):
        raise ValueError(f'GT_PATH_STRING {where}')


def _jsonl(path: Path, rows: list[dict], where: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        for i, r in enumerate(rows):
            _scan(r, f'{where}:{i + 1}')
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n')


def _write_json(path: Path, doc: Any, where: str, *, scan: bool = True) -> None:
    if scan:
        _scan(doc, where)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=False) + '\n')


def _draw(src: Path, dst: Path, boxes: list) -> None:
    """Upscale FRAME_SCALE x (320x180 -> 960x540, the catalog resolution) before drawing: _jpeg's fixed 26x14 letter tag would
    otherwise cover a whole far person (~9x22 px at 320x180)."""
    from PIL import Image
    from amidst.live_mode.service_decider import _jpeg
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        big = im.convert('RGB').resize((im.width * FRAME_SCALE, im.height * FRAME_SCALE), Image.BICUBIC)
        dst.write_bytes(_jpeg(big, [(k, [v * FRAME_SCALE for v in b]) for k, b in boxes]))


def _crop(src: Path, dst: Path, box: list) -> None:
    from PIL import Image
    from amidst.live_mode.advisor import crop_jpeg
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        dst.write_bytes(crop_jpeg(im.convert('RGB'), box))


def build_e8_pack(out: Path, points: list[dict], catalog: Path, *, mac_index: Path, source_commit: str = 'UNKNOWN', frames: bool = True,
               case_loader: Callable | None = None, gt_loader: Callable = E7.load_gt, scene_fn: Callable | None = None,
               projector=None, now: dt.datetime | None = None) -> dict[str, Any]:
    import e3_f4_run as F
    case_loader = case_loader or F.load_case
    scene_fn = scene_fn or (lambda cams: F.live_scene_context(Path(catalog), cams))
    if projector is None:
        from amidst.live_mode.tracker import Projector, load_cameras
        projector = Projector(load_cameras(str(catalog)))
    out, mac_index = Path(out), Path(mac_index)
    if out.exists():
        raise FileExistsError(f'PACK_EXISTS: {out}')
    if mac_index.resolve().is_relative_to(out.resolve()):
        raise ValueError('MAC_INDEX_INSIDE_PACK')
    out.mkdir(parents=True)
    try:
        from amidst.q1q5 import scene_context as sx
        by_case: dict[str, list[dict]] = {}
        for p in points:
            by_case.setdefault(p['case_id'], []).append(p)
        requests, table, mac, cases_meta, n_jobs = [], {}, [], {}, 0
        for cid, dps in by_case.items():
            dp0 = dps[0]
            case = case_loader(dp0['root'], cid)
            order = case['cameras']
            b1_doc = json.loads(Path(dp0['b1']).read_text())
            b1_rows = {r['tick']: r for r in b1_doc['rows']}
            scene = scene_fn(order)
            sx.assert_no_forbidden(scene)
            scene_sha = sx.sha256_of(scene)
            if b1_doc.get('scene_context_sha256') not in (None, scene_sha):
                raise ValueError(f'SCENE_SHA_MISMATCH {cid}')
            ticks_by = {t: (d, p) for t, d, p in case['ticks']}
            ref = reference_of(b1_doc['rows'])
            rows, cands_p0, jobs, mac_rows = case_requests(sorted(dps, key=lambda d: d['tick']), ticks_by, order, b1_rows, scene, scene_sha,
                                                           projector, ref, frames=frames)
            gt = gt_loader(dp0['gt_root'], cid)
            for base, cands in cands_p0.items():
                tick = int(base.rsplit('|t', 1)[1])
                table[base] = {'request_id': base, 'case_id': cid, 'tick': tick, **E7.expected_for_tick(cands, gt.get(tick))}
            requests += rows
            mac += mac_rows
            if frames:
                for src, rel, boxes in jobs:
                    _draw(Path(src), out / rel, boxes)
                n_jobs += len(jobs)
                if ref is not None and any(not m['no_seed'] for m in mac_rows):
                    _crop(Path(ticks_by[ref['tick']][1][ref['camera_id']]), out / 'part1' / 'ref' / f'{cid}.jpg', ref['box'])
            _jsonl(out / 'part2' / 'ticks' / f'{cid}.jsonl', part2_rows(case['ticks'], order, projector), f'ticks/{cid}')
            _write_json(out / 'part2' / 'b1_frozen' / f'{cid}.json', b1_doc, f'b1_frozen/{cid}')
            scene_rel = f'part2/scene/{scene_sha[:16]}.json'
            if not (out / scene_rel).exists():
                (out / scene_rel).parent.mkdir(parents=True, exist_ok=True)
                (out / scene_rel).write_text(sx.serialize(scene))
            cases_meta[cid] = {'cameras': order, 'scene': scene_rel, 'scene_context_sha256': scene_sha, 'b1_frozen': f'part2/b1_frozen/{cid}.json',
                               'ticks': f'part2/ticks/{cid}.jsonl', 'dataset_group': dp0['dataset_group'], 'family': dp0['family'],
                               'inputs': {k: case.get(k) for k in ('index_content_sha256', 'records_file_sha256', 'rgb_index_sha256')}}
        ids = [r['request_id'] for r in requests]
        if len(ids) != len(set(ids)):
            raise ValueError('DUPLICATE_REQUEST_ID')
        if set(table) != {r['base_id'] for r in requests}:
            raise ValueError('G5_TABLE_REQUEST_MISMATCH')
        _jsonl(out / 'requests' / 'e8_part1.jsonl', requests, 'e8_part1')
        _write_json(out / 'part2' / 'cases.json', cases_meta, 'cases.json')
        shutil.copyfile(catalog, out / 'part2' / 'cameras.catalog.json')
        answer_sha = write_colab_answer_table(out / 'scoring_only' / 'answer_table.json', table)
        info = {'schema_version': PACK_SCHEMA, 'request_schema': R.SCHEMA, 'levels': list(R.LEVELS), 'perms': list(R.PERMS), 'seed': R.SEED,
                'cases': list(by_case), 'decision_points': len(table), 'requests': len(requests), 'frames': n_jobs, 'tick_hz': 5,
                'frame_size': list(SIZE), 'l4_frame_scale': FRAME_SCALE, 'camera_catalog_sha256': E7.sha256_file(Path(catalog)), 'source_git_commit': source_commit,
                'identity': 'UNCONFIRMED', 'answer_table_sha256': answer_sha,
                'created_utc': (now or dt.datetime.now(dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'notes': 'B1 T-1 snapshots from frozen b-logs; label-only answer table (D385/D392); Part-2 has no GT'}
        _write_json(out / 'PACK_INFO.json', info, 'PACK_INFO.json')
        manifest_sha = E7.write_manifest(out)
        gate = verify_colab_pack_pre_upload(out)
        mac_doc = {'schema_version': 'e8_mac_index_v1', 'pack_manifest_sha256': manifest_sha, 'answer_table_sha256': answer_sha,
                   'decision_points': mac, 'gt_roots': {cid: str(dps[0]['gt_root']) for cid, dps in by_case.items()}}
        mac_index.parent.mkdir(parents=True, exist_ok=True)
        mac_index.write_text(json.dumps(mac_doc, indent=2, sort_keys=True) + '\n')
        return {**info, 'manifest_sha256': manifest_sha, 'gate': gate, 'mac_index_sha256': hashlib.sha256(mac_index.read_bytes()).hexdigest(),
                'files': sum(1 for p in out.rglob('*') if p.is_file())}
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--e3', nargs=2, action='append', default=[], metavar=('CORPUS_JSON', 'B1_RUNS_DIR'))
    ap.add_argument('--e6', nargs=4, metavar=('FROZEN_JSON', 'DET_ROOT', 'GT_ROOT', 'B1_DIR'))
    ap.add_argument('--cameras', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mac-index', type=Path, required=True, help='Mac-only decision-point index (outside the pack)')
    ap.add_argument('--cases', nargs='+', help='SMOKE: restrict to these cases')
    ap.add_argument('--no-frames', action='store_true', help='SMOKE: skip L4 frames and the reference crop')
    ap.add_argument('--source-commit', default='UNKNOWN')
    a = ap.parse_args(argv)
    pts = [p for corpus, runs in a.e3 for p in e3_points(Path(corpus), Path(runs))]
    if a.e6:
        pts += e6_points(*map(Path, a.e6))
    if a.cases:
        pts = [p for p in pts if p['case_id'] in a.cases]
    res = build_e8_pack(a.out, pts, a.cameras, mac_index=a.mac_index, source_commit=a.source_commit, frames=not a.no_frames)
    print(json.dumps({k: v for k, v in res.items() if k != 'gate'}, indent=2))
    print('PRE_UPLOAD_GATE', res['gate']['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
