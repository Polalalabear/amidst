"""Build the E7 Colab upload pack for the old E3 16 segments (#732 G5, D385/D392/D396).

Spec: docs/evaluation/E7_COLAB_UPLOAD_PACK_SPEC_V1.md. Runs on the Mac only.

Layout written to --out:
  requests/e3_16_segments.jsonl   inference-only requests (detections + frame paths; no GT)
  frames/<case>/<cam>/<tick>.png  APFS clones (cp -c) of the frozen 320x180 frames
  baselines/e5_report_frozen.json optional frozen E5 report (decision outputs)
  scoring_only/answer_table.json  label-only answers, written ONLY by write_colab_answer_table
  PACK_INFO.json, MANIFEST.sha256

GT (``gt-boxes/<case>.a-log.json``) is read here and only here. It is reduced to
expected_answer / expected_camera_ids / expected_detection_ids by ``judge_box`` and never
copied, linked or quoted into any other pack file. ``verify_colab_pack_pre_upload`` must pass
or the whole pack is deleted.

Requests are stateless snapshots every ``--stride`` ticks (default 10 = the 2 s AO poll): they
carry no rule/tracker state, no reference crop and no STILL_HERE_OCCLUDED history, so the
answer table never expects STILL_HERE_OCCLUDED.

Expected answer per request (target actor T):
  not visible in any camera                     -> NOT_VISIBLE, no cameras
  visible, >=1 candidate hits the GT body box   -> SELECT, cameras/ids that hit (judge_box 'primary')
  visible, no candidate hits (detector miss)    -> UNCERTAIN, cameras = visible cameras
                                                  (the bridge scores OWN_BOX there as NEEDS_MAC_SCORING)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amidst.evaluation.e3_scoring import judge_box  # noqa: E402
from amidst.evaluation.e7_scoring_bridge import (  # noqa: E402
    _scan_forbidden_gt_fields,
    verify_colab_pack_pre_upload,
    write_colab_answer_table,
)

DATASET_GROUP = 'e3_16_segments'
SIZE = (320, 180)
DEFAULT_STRIDE = 10
TARGET_ACTOR = 'T'
PACK_SCHEMA = 'e7_colab_pack_v1'
VAR_HEADER = 'DETECTIONS (person score>=0.15, CAM_ENTRY>=0.05; frozen detector output, no rule state):'


# ------------------------------------------------------------------ pure core (no filesystem)
def _colors(det: dict) -> list[str]:
    return [c for c in ('red', 'blue') if det.get('color') == c or det.get(c) in ('STRONG', 'WEAK')]


def candidates_for_tick(dets: dict[str, list[dict]], camera_order: Iterable[str]) -> list[dict]:
    """Candidate list with per-camera ids D1..Dn, as in AOpenDecider.build_input. Inference-only fields."""
    out = []
    for cam in camera_order:
        for n, d in enumerate(dets.get(cam, []), start=1):
            out.append({'detection_id': f'D{n}', 'camera_id': cam, 'box': [round(float(v), 1) for v in d['bbox']],
                        'score': round(float(d['score']), 2), 'class_label': 'person', 'colors': _colors(d)})
    return out


def variable_text(tick: int, candidates: list[dict], camera_ids: list[str]) -> str:
    lines = [f'NOW t={tick / 5:.1f}s.', VAR_HEADER]
    for c in candidates:
        b = c['box']
        lines.append(f"- {c['camera_id']} {c['detection_id']}: person score {c['score']:.2f} "
                     f"box [{b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}] colours {','.join(c['colors']) or 'none'}")
    lines.append('CAMERAS THIS CALL: ' + ', '.join(sorted(camera_ids)) + '.')
    return '\n'.join(lines)


def expected_for_tick(candidates: list[dict], gt_actor: dict | None) -> dict[str, Any]:
    """Reduce the GT target entry to a label-only answer. ``gt_actor`` is the Mac-side a-log actor T (or None)."""
    visible = []
    boxes: dict[str, Any] = {}
    if gt_actor and gt_actor.get('present'):
        visible = [c for c in (gt_actor.get('gt_visible') or [])]
        boxes = gt_actor.get('gt_boxes') or {}
    if not visible:
        return {'expected_answer': 'NOT_VISIBLE', 'expected_camera_ids': [], 'expected_detection_ids': {}}
    hits: dict[str, list[str]] = {}
    for cam in sorted(visible):
        body = boxes.get(cam)
        ids = [c['detection_id'] for c in candidates if c['camera_id'] == cam
               and judge_box(c['box'], body, SIZE)['primary']]
        if ids:
            hits[cam] = ids
    if hits:
        return {'expected_answer': 'SELECT', 'expected_camera_ids': sorted(hits), 'expected_detection_ids': hits}
    return {'expected_answer': 'UNCERTAIN', 'expected_camera_ids': sorted(visible), 'expected_detection_ids': {}}


def build_case(case_id: str, ticks: list[tuple[int, dict, dict]], camera_order: list[str],
               gt_by_tick: dict[int, dict | None], stride: int) -> tuple[list[dict], dict[str, dict], list[tuple[Path, str]]]:
    """Returns (request rows, answer table entries, [(source_png, pack_relative_path)])."""
    if stride <= 0:
        raise ValueError('BAD_STRIDE')
    rows, answers, copies = [], {}, []
    first = ticks[0][0] if ticks else 0
    for tick, dets, paths in ticks:
        if (tick - first) % stride:
            continue
        cands = candidates_for_tick(dets, camera_order)
        rel = {cam: f'frames/{case_id}/{cam}/{tick:06d}.png' for cam in camera_order if cam in paths}
        rid = f'{case_id}|t{tick}'
        rows.append({'request_id': rid, 'case_id': case_id, 'dataset_group': DATASET_GROUP, 'tick': tick,
                     'camera_ids': list(rel), 'variable_text': variable_text(tick, cands, list(rel)),
                     'candidates': cands, 'image_paths': rel})
        answers[rid] = {'request_id': rid, 'case_id': case_id, 'tick': tick,
                        **expected_for_tick(cands, gt_by_tick.get(tick))}
        copies += [(Path(paths[cam]), rel[cam]) for cam in rel]
    return rows, answers, copies


# ------------------------------------------------------------------ Mac-side IO
def clone_file(src: Path, dst: Path) -> str:
    """APFS clone (cp -c); hardlink fallback; never silently byte-copies."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['cp', '-c', str(src), str(dst)], capture_output=True)
    if r.returncode == 0:
        return 'clone'
    try:
        os.link(src, dst)
        return 'hardlink'
    except OSError as exc:
        raise RuntimeError(f'CLONE_FAILED {src}: {r.stderr.decode()[:120]} / {exc}') from exc


def load_gt(root: Path, case_id: str) -> dict[int, dict | None]:
    doc = json.loads((root / 'gt-boxes' / f'{case_id}.a-log.json').read_text())
    return {t['tick']: next((a for a in t['actors'] if a['id'] == TARGET_ACTOR), None) for t in doc['ticks']}


def load_case_inputs(root: Path, case_id: str):
    import e3_f4_run as frozen  # noqa: PLC0415  (needs numpy/PIL; Mac venv)
    case = frozen.load_case(root, case_id)
    return case['ticks'], case['cameras']


def discover_cases(root: Path) -> list[str]:
    return sorted(p.name for p in (root / 'indexes').iterdir() if p.is_dir())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out: Path) -> str:
    lines = [f'{sha256_file(p)}  {p.relative_to(out).as_posix()}'
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256']
    data = '\n'.join(lines) + '\n'
    (out / 'MANIFEST.sha256').write_text(data)
    return hashlib.sha256(data.encode()).hexdigest()


def build_pack(out: Path, roots: list[Path], *, stride: int = DEFAULT_STRIDE, e5_report: Path | None = None,
               source_commit: str = 'UNKNOWN', cases: list[str] | None = None,
               case_loader: Callable = load_case_inputs, gt_loader: Callable = load_gt,
               now: dt.datetime | None = None) -> dict[str, Any]:
    out = Path(out)
    if out.exists():
        raise FileExistsError(f'PACK_EXISTS: {out}')
    out.mkdir(parents=True)
    try:
        all_rows, table, copies, case_ids = [], {}, [], []
        for root in roots:
            for cid in (c for c in discover_cases(root) if cases is None or c in cases):
                ticks, order = case_loader(root, cid)
                rows, answers, cp = build_case(cid, ticks, order, gt_loader(root, cid), stride)
                dup = set(table) & set(answers)
                if dup:
                    raise ValueError(f'DUPLICATE_REQUEST_ID {sorted(dup)[:3]}')
                all_rows += rows
                table.update(answers)
                copies += cp
                case_ids.append(cid)
        (out / 'requests').mkdir()
        (out / 'requests' / 'e3_16_segments.jsonl').write_text(
            ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in all_rows))
        modes: dict[str, int] = {}
        for src, rel in copies:
            if not (out / rel).exists():
                m = clone_file(src, out / rel)
                modes[m] = modes.get(m, 0) + 1
        if e5_report is not None:
            report = json.loads(Path(e5_report).read_text())
            _scan_forbidden_gt_fields(report, 'e5_report_frozen.json')
            (out / 'baselines').mkdir()
            shutil.copyfile(e5_report, out / 'baselines' / 'e5_report_frozen.json')
        answer_sha = write_colab_answer_table(out / 'scoring_only' / 'answer_table.json', table)
        info = {'schema_version': PACK_SCHEMA, 'dataset_scopes': [DATASET_GROUP], 'cases': case_ids,
                'requests': len(all_rows), 'stride_ticks': stride, 'tick_hz': 5, 'frame_size': list(SIZE),
                'frame_copy_modes': modes, 'source_git_commit': source_commit, 'identity': 'UNCONFIRMED',
                'created_utc': (now or dt.datetime.now(dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'answer_table_sha256': answer_sha,
                'notes': 'stateless detection snapshots; label-only answer table (D385/D392)'}
        (out / 'PACK_INFO.json').write_text(json.dumps(info, indent=2) + '\n')
        manifest_sha = write_manifest(out)
        gate = verify_colab_pack_pre_upload(out)  # raises -> whole pack discarded below
        return {**info, 'manifest_sha256': manifest_sha, 'gate': gate, 'files': sum(1 for p in out.rglob('*') if p.is_file()),
                'answer_entries': len(table)}
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--roots', nargs='+', type=Path, required=True, help='E3 roots (e3-652-..., e3-reappearances-...)')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--stride', type=int, default=DEFAULT_STRIDE)
    ap.add_argument('--e5-report', type=Path)
    ap.add_argument('--source-commit', default='UNKNOWN')
    a = ap.parse_args(argv)
    res = build_pack(a.out, a.roots, stride=a.stride, e5_report=a.e5_report, source_commit=a.source_commit)
    print(json.dumps({k: v for k, v in res.items() if k != 'gate'}, indent=2))
    print('PRE_UPLOAD_GATE', res['gate']['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
