"""Acceptance gates for #516 (r004 A4/B4 4-actor scenario production, Codex), D206.

Contract: docs/contracts/R004_V2_4ACTOR_PRODUCTION_GATES_V1.md (normative; read it first).

G1 (feasibility, no render) and G2 (render delivery, separately authorised) are ``xfail(strict=True)``.
They fail today because the deliverable files do not exist; Codex turns them into PASS by
delivering the files. Strict xfail makes an XPASS that still carries the marker fail CI, which
forces the marker to be removed. A missing file makes a gate xfail (assertion), never error.

The self-tests (plain PASS) feed invented good/bad data to the same validators to prove the
gates discriminate. Synthetic data only: no GT, renders, Blender or network.
"""
import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest

from amidst.q1q5 import agent_decision as ad

ROOT = Path(__file__).resolve().parents[2]
ISSUE = '#516'
G1 = pytest.mark.xfail(strict=True, reason=f'awaiting Codex G1 feasibility report {ISSUE}')
G2 = pytest.mark.xfail(strict=True, reason=f'awaiting Codex G2 render delivery {ISSUE} (needs separate authorisation)')

REPORT = ROOT / 'docs/evaluation/R004_A4B4_V2_FEASIBILITY_REPORT.json'
BUNDLE_MANIFEST = ROOT / 'docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json'
DRAFT = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_4ACTOR_DRAFT.json'
CHECKER = ROOT / 'scripts/design/check_actor_clearance.py'

REPORT_SCHEMA = 'amidst.r004-v2-feasibility.v1'
MANIFEST_SCHEMA = 'amidst.r004-v2-bundle-manifest.v1'
RUNS = {'A4-1-v2-4actor': 'A4-1', 'B4-1-v2-4actor': 'B4-1'}
RENDER_CAMERAS = {
    'A4-1-v2-4actor': ['CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_W1'],
    'B4-1-v2-4actor': ['CAM_BRANCH', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE'],
}
SPAWN_ACTORS = ('A', 'B', 'C')
STOP_LINE_GIB = 8.0
SHA256 = re.compile(r'^[0-9a-f]{64}$')
GIT_SHA = re.compile(r'^[0-9a-f]{40}$')
GT_NAME = re.compile(r'(?i)(gt_private|scoring_private|ground_?truth|renderer_?traj|visib|depth|traject|(^|[/_.-])gt([/_.-]|$))')
STAGES = ('detection_index', 'local_track', 'ranking', 'reconstruction')
TRACKED_STAGES = {'detection_index', 'local_track'}  # stages whose inputs must list frames/clock only


# ------------------------------------------------------------------ helpers

def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _is_sha(v):
    return isinstance(v, str) and bool(SHA256.match(v))


def _load_checker():
    spec = importlib.util.spec_from_file_location('check_actor_clearance', CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _segments(items):
    return [{'segment_id': s['segment_id'], 'a': list(s['a']), 'b': list(s['b'])} for s in items]


def rerun_clearance(report, draft):
    """Put the report's measured walls/furniture/doors into the draft and run the checker."""
    chk = _load_checker()
    doc = copy.deepcopy(draft)
    for run in doc['runs']:
        geo = report['geometry'][run['run_id']]
        run['walls'] = _segments(geo['walls']) + _segments(geo['furniture'])
        run['doors'] = [{'door_id': d['door_id'], 'center_xy': d['center_xy'], 'normal_xy': d['normal_xy'],
                         'width_m': d['width_m'], 'geometry_status': 'MEASURED'} for d in geo['doors']]
        run.pop('advisory_boundaries', None)
    return chk.check_document(doc)


def _rules():
    return _load_checker().DEFAULT_RULES


def _point_in_box(p, box):
    (x0, x1), (y0, y1) = box
    return min(x0, x1) <= p[0] <= max(x0, x1) and min(y0, y1) <= p[1] <= max(y0, y1)


# ------------------------------------------------------------------ G1 validators (return error list)

def check_inputs(report):
    errs = []
    inputs = report.get('inputs')
    if not isinstance(inputs, list) or not inputs:
        return ['inputs: missing or empty']
    for i, item in enumerate(inputs):
        for key in ('relative_path', 'git_sha', 'sha256'):
            if not item.get(key):
                errs.append(f'inputs[{i}]: missing {key}')
        if item.get('git_sha') and not GIT_SHA.match(item['git_sha']):
            errs.append(f'inputs[{i}]: git_sha must be 40 hex')
        if item.get('sha256') and not _is_sha(item['sha256']):
            errs.append(f'inputs[{i}]: sha256 must be 64 hex')
        rp = item.get('relative_path') or ''
        if rp.startswith('/') or rp.startswith('~'):
            errs.append(f'inputs[{i}]: relative_path must not be absolute')
    names = ' '.join(i.get('relative_path', '') for i in inputs)
    for needed in ('R004_A4B4_SCENARIO_V2_4ACTOR_DRAFT.json', 'check_actor_clearance.py', '.blend'):
        if needed not in names:
            errs.append(f'inputs: no entry for {needed}')
    return errs


def check_geometry(report):
    errs = []
    for run_id in RUNS:
        geo = (report.get('geometry') or {}).get(run_id)
        if not geo:
            errs.append(f'geometry[{run_id}]: missing')
            continue
        if not geo.get('walls'):
            errs.append(f'geometry[{run_id}]: walls empty')
        if 'furniture' not in geo:
            errs.append(f'geometry[{run_id}]: furniture key missing (use [] only if the scene has none)')
        for kind in ('walls', 'furniture'):
            for s in geo.get(kind) or []:
                ok = all(isinstance(s.get(k), list) and len(s[k]) == 2 for k in ('a', 'b'))
                hr = s.get('height_range_m')
                if not ok or not s.get('segment_id'):
                    errs.append(f'geometry[{run_id}].{kind}: segment needs segment_id and 2D a/b')
                if not (isinstance(hr, list) and len(hr) == 2 and hr[0] < hr[1]):
                    errs.append(f'geometry[{run_id}].{kind}: segment needs height_range_m [lo, hi]')
        if not isinstance(geo.get('floor_z_m'), (int, float)):
            errs.append(f'geometry[{run_id}]: floor_z_m missing')
        doors = {d.get('door_id'): d for d in geo.get('doors') or []}
        want = {'A4-1-v2-4actor': {'R004_WEST_ENTRY'}, 'B4-1-v2-4actor': {'PORTAL_R101'}}[run_id]
        for door_id in want:
            d = doors.get(door_id)
            if not d:
                errs.append(f'geometry[{run_id}]: door {door_id} missing')
                continue
            if d.get('geometry_status') != 'MEASURED':
                errs.append(f'{door_id}: geometry_status must be MEASURED (not ASSUMED)')
            if not (isinstance(d.get('width_m'), (int, float)) and d['width_m'] > 0
                    and len(d.get('center_xy') or []) == 2 and len(d.get('normal_xy') or []) == 2):
                errs.append(f'{door_id}: needs width_m, center_xy, normal_xy')
            if not _is_sha(d.get('source_sha256')):
                errs.append(f'{door_id}: source_sha256 missing')
    return errs


def check_clearance(report, draft):
    errs = []
    claimed = report.get('clearance') or {}
    if claimed.get('verdict') != 'PASS' or claimed.get('walls_status') != 'PASS':
        errs.append('clearance: report must claim verdict PASS and walls_status PASS (was UNKNOWN in the draft)')
    for key in ('command', 'checker_git_sha'):
        if not claimed.get(key):
            errs.append(f'clearance: missing {key}')
    try:
        result = rerun_clearance(report, draft)
    except Exception as exc:  # malformed geometry
        return errs + [f'clearance: rerun failed: {type(exc).__name__}: {exc}']
    for run in result['runs']:
        st = run['check_status']
        if run['verdict'] != 'PASS':
            errs.append(f"clearance: rerun {run['run_id']} verdict {run['verdict']} {st}")
        if st.get('walls') != 'PASS':
            errs.append(f"clearance: rerun {run['run_id']} walls status {st.get('walls')} (UNKNOWN means no geometry)")
    return errs


def check_spawn(report, draft):
    errs = []
    spawn = report.get('spawn_points') or {}
    for run in draft['runs']:
        run_id = run['run_id']
        rows = {(r.get('actor_id'), r.get('kind')): r for r in spawn.get(run_id) or []}
        boxes = run['estimate_model']['assumed_camera_coverage_xy_boxes']
        for actor in run['actors']:
            if actor['actor_id'] not in SPAWN_ACTORS:
                continue
            wps = actor['waypoints']
            for kind, wp in (('first', wps[0]), ('last', wps[-1])):
                row = rows.get((actor['actor_id'], kind))
                if not row:
                    errs.append(f"spawn[{run_id}]: no {kind} point for {actor['actor_id']}")
                    continue
                if row.get('xy') != list(wp['xy']):
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: xy differs from the draft waypoint "
                                '(a moved point needs a draft change from Claude)')
                if row.get('outside_all_render_cameras') is not True:
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: must be outside every render camera")
                if sorted(row.get('cameras_checked') or []) != sorted(RENDER_CAMERAS[run_id]):
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: cameras_checked != {RENDER_CAMERAS[run_id]}")
                if row.get('method') != 'static_projection':
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: method must be static_projection")
    return errs


def check_color(report):
    errs = []
    c = report.get('color') or {}
    band = c.get('red_band_hue') or []
    if len(band) != 2 or not c.get('hsv_config_sha256') or not _is_sha(c.get('hsv_config_sha256')):
        return ['color: needs red_band_hue [lo, hi] and hsv_config_sha256 (formal config, D204)']

    def in_band(h):
        lo, hi = band
        return (lo <= h <= hi) if lo <= hi else (h >= lo or h <= hi)

    if not isinstance(c.get('t_hue'), (int, float)):
        errs.append('color: t_hue (measured target hue) missing')
    rows = c.get('b_by_camera') or []
    got = {(r.get('run_id'), r.get('camera_id')) for r in rows}
    for run_id, cams in RENDER_CAMERAS.items():
        for cam in cams:
            if (run_id, cam) not in got:
                errs.append(f'color: no B measurement for {run_id}/{cam}')
    for r in rows:
        h = r.get('b_hue_measured')
        if not isinstance(h, (int, float)):
            errs.append(f"color: {r.get('camera_id')} b_hue_measured missing")
        elif not in_band(h) or r.get('in_band') is not True:
            errs.append(f"color: B hue {h} in {r.get('camera_id')} is outside the red band {band} (D204 needs inside)")
        if not isinstance(r.get('crop_ratio'), (int, float)) or abs(r['crop_ratio'] - 0.3) > 1e-9:
            errs.append(f"color: {r.get('camera_id')} crop_ratio must be 0.3 (upper 30% of bbox)")
    for who, want in (('a_in_band', True), ('c_in_band', False)):
        if c.get(who) is not want:
            errs.append(f'color: {who} must be {want}')
    return errs


def check_ambiguity(report):
    errs, total = [], 0
    amb = report.get('ambiguity') or {}
    if amb.get('unit') != 'episode':
        errs.append('ambiguity: unit must be episode (D203)')
    if amb.get('color_variant') != 'in_band':
        errs.append('ambiguity: color_variant must be in_band (D204)')
    for run_id in RUNS:
        eps = (amb.get('episodes') or {}).get(run_id)
        if eps is None:
            errs.append(f'ambiguity[{run_id}]: missing')
            continue
        for e in eps:
            if not (isinstance(e.get('start_s'), (int, float)) and isinstance(e.get('end_s'), (int, float))
                    and e['start_s'] < e['end_s']):
                errs.append(f'ambiguity[{run_id}]: bad episode window {e}')
            if e.get('has_distractor') is not True:
                errs.append(f'ambiguity[{run_id}]: episode {e.get("start_s")} has no distractor')
        total += len(eps)
    if total < 5:
        errs.append(f'ambiguity: {total} episodes in total, need >= 5 (D203)')
    if amb.get('total_episodes') != total:
        errs.append('ambiguity: total_episodes disagrees with the episode lists')
    return errs


def check_cost(report):
    errs = []
    cost = report.get('render_cost') or {}
    for run_id in RUNS:
        r = (cost.get('runs') or {}).get(run_id) or {}
        for key in ('render_seconds_estimate', 'disk_gib_estimate'):
            if not (isinstance(r.get(key), (int, float)) and r[key] > 0):
                errs.append(f'render_cost[{run_id}]: {key} must be a positive number')
    for key in ('free_gib_before', 'total_disk_gib_estimate'):
        if not isinstance(cost.get(key), (int, float)):
            errs.append(f'render_cost: {key} missing')
    if not errs:
        if cost['free_gib_before'] - cost['total_disk_gib_estimate'] < STOP_LINE_GIB:
            errs.append(f'render_cost: free after render would drop below the {STOP_LINE_GIB} GiB stop line; '
                        'report it on #516 and do not render')
        if cost.get('includes_frames') not in (True, False):
            errs.append('render_cost: includes_frames must say whether the estimate includes frames')
    return errs


def check_actor_cloning(report):
    c = report.get('actor_cloning') or {}
    errs = []
    if c.get('feasible') not in (True, False):
        errs.append('actor_cloning: feasible must be true or false')
    if c.get('feasible') is True:
        mats = c.get('materials') or {}
        if set(mats) != {'A', 'B', 'C'}:
            errs.append('actor_cloning: materials needs A, B, C')
        if c.get('shared_animation') not in (True, False):
            errs.append('actor_cloning: shared_animation must be stated (copies reuse one gait?)')
    return errs


def check_boundary(report):
    b = report.get('boundary') or {}
    errs = []
    for key, want in (('rendered', False), ('wrote_local_dir', False), ('blend_saved', False), ('gt_read', False)):
        if b.get(key) is not want:
            errs.append(f'boundary.{key} must be {want}')
    return errs


def validate_report(report, draft):
    errs = []
    if report.get('schema') != REPORT_SCHEMA:
        errs.append(f'schema must be {REPORT_SCHEMA}')
    for fn in (check_inputs, check_geometry, check_color, check_ambiguity, check_cost,
               check_actor_cloning, check_boundary):
        errs += fn(report)
    errs += check_spawn(report, draft)
    if not any(e.startswith('geometry') for e in errs):
        errs += check_clearance(report, draft)
    else:
        errs.append('clearance: skipped, geometry invalid')
    return errs


# ------------------------------------------------------------------ G2 validators

def _walk_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_keys(v)


def validate_manifest(m, report=None):
    errs = []
    if m.get('schema') != MANIFEST_SCHEMA:
        errs.append(f'schema must be {MANIFEST_SCHEMA}')
    bad = sorted(k for k in _walk_keys(m) if k in ad.FORBIDDEN_KEYS or (str(k).startswith('gt_') and k != 'gt_read'))
    if bad:
        errs.append(f'manifest keys hit FORBIDDEN_KEYS: {bad[:5]} (use relative_path, not path/file)')
    root = m.get('local_root')
    if root != '$AMIDST_ARTIFACTS':
        errs.append('local_root must be the literal $AMIDST_ARTIFACTS')
    files = m.get('files')
    if not isinstance(files, list) or not files:
        return errs + ['files: missing or empty']
    seen_bytes = 0
    for i, f in enumerate(files):
        rp = f.get('relative_path') or ''
        if not rp or rp.startswith(('/', '~')) or '..' in rp.split('/') or '/Users/' in rp:
            errs.append(f'files[{i}]: relative_path must be relative to $AMIDST_ARTIFACTS, no absolute home path')
        if GT_NAME.search(rp):
            errs.append(f'files[{i}]: {rp!r} is a GT/private/renderer-trajectory name; it cannot be in the safe bundle')
        if not _is_sha(f.get('sha256')):
            errs.append(f'files[{i}]: sha256 must be 64 hex')
        if not (type(f.get('size_bytes')) is int and f['size_bytes'] >= 0):
            errs.append(f'files[{i}]: size_bytes must be an int')
        else:
            seen_bytes += f['size_bytes']
    if m.get('file_count') != len(files):
        errs.append('file_count disagrees with files')
    if m.get('total_bytes') != seen_bytes:
        errs.append('total_bytes disagrees with the sum of size_bytes')
    if m.get('receipt', {}).get('gt_read') is not False:
        errs.append('receipt.gt_read must be false')
    if not _is_sha((m.get('receipt') or {}).get('detector_weights_sha256')):
        errs.append('receipt.detector_weights_sha256 missing')
    if not GIT_SHA.match((m.get('receipt') or {}).get('code_git_sha') or ''):
        errs.append('receipt.code_git_sha must be 40 hex')
    listed = {f.get('relative_path') for f in files}
    for run_id in RUNS:
        run = (m.get('runs') or {}).get(run_id)
        if not run:
            errs.append(f'runs[{run_id}]: missing')
            continue
        if not run.get('run_id_new') or run['run_id_new'].startswith('ctrl-lcorr-s1-') and 'r004-d124-v1' in run['run_id_new']:
            errs.append(f'runs[{run_id}]: run_id_new must be a NEW run id, not the old r004 d124 run')
        cams = run.get('cameras') or {}
        if sorted(cams) != sorted(RENDER_CAMERAS[run_id]):
            errs.append(f'runs[{run_id}]: cameras must be exactly {RENDER_CAMERAS[run_id]}')
        for cam, info in cams.items():
            if not (type(info.get('frame_count')) is int and info['frame_count'] > 0):
                errs.append(f'runs[{run_id}].{cam}: frame_count must be a positive int')
            if info.get('fps') != 5:
                errs.append(f'runs[{run_id}].{cam}: fps must be 5')
        expect = {'A4-1-v2-4actor': 50, 'B4-1-v2-4actor': 42}[run_id] * 5
        counts = {c.get('frame_count') for c in cams.values()}
        if counts and counts != {expect, expect + 1} and counts != {expect} and counts != {expect + 1}:
            errs.append(f'runs[{run_id}]: frame_count should be {expect} or {expect + 1} per camera (50 s/42 s at 5 fps)')
        idx = run.get('detection_index_relative_path')
        if not idx or idx not in listed:
            errs.append(f'runs[{run_id}]: RT-DETR detection index must exist and be listed in files')
        if run.get('detector') != 'RT-DETR':
            errs.append(f'runs[{run_id}]: detector must be RT-DETR')
    inputs = m.get('stage_inputs') or {}
    for stage in STAGES:
        lst = inputs.get(stage)
        if not isinstance(lst, list) or not lst:
            errs.append(f'stage_inputs.{stage}: missing')
            continue
        for rp in lst:
            if GT_NAME.search(rp):
                errs.append(f'stage_inputs.{stage}: {rp!r} is GT / renderer trajectory (isolation violated)')
            if rp not in listed:
                errs.append(f'stage_inputs.{stage}: {rp!r} not in files (every stage input must be in the bundle)')
    return errs


# ------------------------------------------------------------------ fake data (invented here)

def _fake_draft():
    return {'runs': [
        {'run_id': rid, 'duration_us': 10_000_000, 'rules': {}, 'doors': [], 'corridors': [], 'walls': None,
         'seed': None,
         'estimate_model': {'assumed_camera_coverage_xy_boxes': {c: [[[0, 1], [0, 1]]] for c in RENDER_CAMERAS[rid]}},
         'actors': [{'actor_id': a, 'waypoints': [{'t_us': 2_000_000, 'xy': [50.0, 50.0 + n]},
                                                 {'t_us': 9_000_000, 'xy': [60.0, 50.0 + n]}]}
                    for n, a in enumerate(('T',) + SPAWN_ACTORS)]}
        for rid in RUNS]}


def _fake_report(draft=None):
    draft = draft or _fake_draft()
    sha = 'a' * 64
    door_for = {'A4-1-v2-4actor': 'R004_WEST_ENTRY', 'B4-1-v2-4actor': 'PORTAL_R101'}
    r = {
        'schema': REPORT_SCHEMA,
        'inputs': [{'relative_path': 'docs/evaluation/R004_A4B4_SCENARIO_V2_4ACTOR_DRAFT.json', 'git_sha': 'b' * 40, 'sha256': sha},
                   {'relative_path': 'scripts/design/check_actor_clearance.py', 'git_sha': 'b' * 40, 'sha256': sha},
                   {'relative_path': 'LOCAL/r004/base_a4.blend', 'git_sha': 'b' * 40, 'sha256': sha}],
        'geometry': {rid: {
            'floor_z_m': 0.0,
            'walls': [{'segment_id': 'W1', 'a': [100.0, 0.0], 'b': [100.0, 5.0], 'height_range_m': [0.0, 2.8]}],
            'furniture': [],
            'doors': [{'door_id': door_for[rid], 'center_xy': [100.0, 2.0], 'normal_xy': [1, 0], 'width_m': 1.0,
                       'geometry_status': 'MEASURED', 'source_sha256': sha}]} for rid in RUNS},
        'clearance': {'verdict': 'PASS', 'walls_status': 'PASS', 'command': 'python scripts/design/check_actor_clearance.py x',
                      'checker_git_sha': 'b' * 40},
        'spawn_points': {run['run_id']: [
            {'actor_id': a['actor_id'], 'kind': k, 'xy': wp['xy'], 'method': 'static_projection',
             'outside_all_render_cameras': True, 'cameras_checked': list(RENDER_CAMERAS[run['run_id']])}
            for a in run['actors'] if a['actor_id'] in SPAWN_ACTORS
            for k, wp in (('first', a['waypoints'][0]), ('last', a['waypoints'][-1]))] for run in draft['runs']},
        'color': {'red_band_hue': [0.95, 0.05], 'hsv_config_sha256': sha, 't_hue': 0.0, 'a_in_band': True, 'c_in_band': False,
                  'b_by_camera': [{'run_id': rid, 'camera_id': c, 'b_hue_measured': 0.02, 'in_band': True, 'crop_ratio': 0.3}
                                  for rid, cams in RENDER_CAMERAS.items() for c in cams]},
        'ambiguity': {'unit': 'episode', 'color_variant': 'in_band', 'total_episodes': 5, 'episodes': {
            'A4-1-v2-4actor': [{'start_s': 8.0, 'end_s': 10.4, 'has_distractor': True},
                               {'start_s': 17.8, 'end_s': 25.8, 'has_distractor': True},
                               {'start_s': 29.0, 'end_s': 36.0, 'has_distractor': True}],
            'B4-1-v2-4actor': [{'start_s': 11.2, 'end_s': 12.6, 'has_distractor': True},
                               {'start_s': 14.2, 'end_s': 41.8, 'has_distractor': True}]}},
        'render_cost': {'free_gib_before': 9.4, 'total_disk_gib_estimate': 1.2, 'includes_frames': True,
                        'runs': {rid: {'render_seconds_estimate': 600, 'disk_gib_estimate': 0.6} for rid in RUNS}},
        'actor_cloning': {'feasible': True, 'materials': {'A': 'red', 'B': 'orange-red', 'C': 'blue'}, 'shared_animation': True},
        'boundary': {'rendered': False, 'wrote_local_dir': False, 'blend_saved': False, 'gt_read': False},
    }
    return r


def _fake_manifest():
    sha = 'c' * 64
    files = [{'relative_path': f'r004_v2/{n}', 'sha256': sha, 'size_bytes': 10}
             for n in ('a4/detection_index.json', 'b4/detection_index.json', 'a4/frames.tar', 'b4/frames.tar',
                       'a4/clock.json', 'b4/clock.json', 'a4/records.jsonl', 'b4/records.jsonl')]
    paths = {f['relative_path'] for f in files}
    return {
        'schema': MANIFEST_SCHEMA, 'local_root': '$AMIDST_ARTIFACTS', 'files': files, 'file_count': len(files),
        'total_bytes': 10 * len(files),
        'receipt': {'gt_read': False, 'detector_weights_sha256': sha, 'code_git_sha': 'd' * 40},
        'runs': {rid: {'run_id_new': f'{rid}-new', 'detector': 'RT-DETR',
                       'detection_index_relative_path': f"r004_v2/{'a4' if rid.startswith('A') else 'b4'}/detection_index.json",
                       'cameras': {c: {'frame_count': 250 if rid.startswith('A') else 210, 'fps': 5}
                                   for c in RENDER_CAMERAS[rid]}} for rid in RUNS},
        'stage_inputs': {s: sorted(p for p in paths if 'frames' in p or 'clock' in p or 'detection' in p or 'records' in p)
                         for s in STAGES},
    }


# ------------------------------------------------------------------ G1 gates (xfail until Codex delivers)

def _g1_report():
    assert REPORT.is_file(), f'missing {REPORT.relative_to(ROOT)}'
    return _load(REPORT)


@G1
def test_g1_report_schema_and_provenance():
    report = _g1_report()
    assert report.get('schema') == REPORT_SCHEMA
    assert check_inputs(report) == []


@G1
def test_g1_geometry_walls_furniture_doors_measured():
    assert check_geometry(_g1_report()) == []


@G1
def test_g1_clearance_unknown_becomes_pass_with_geometry():
    assert check_clearance(_g1_report(), _load(DRAFT)) == []


@G1
def test_g1_spawn_points_outside_all_render_cameras():
    assert check_spawn(_g1_report(), _load(DRAFT)) == []


@G1
def test_g1_b_stays_in_red_band_under_every_camera_light():
    assert check_color(_g1_report()) == []


@G1
def test_g1_ambiguity_episodes_at_least_five():
    assert check_ambiguity(_g1_report()) == []


@G1
def test_g1_render_cost_and_disk_estimate():
    assert check_cost(_g1_report()) == []


@G1
def test_g1_actor_cloning_and_boundary():
    report = _g1_report()
    assert check_actor_cloning(report) == []
    assert check_boundary(report) == []


# ------------------------------------------------------------------ G2 gates (render authorisation needed)

def _g2_manifest():
    assert BUNDLE_MANIFEST.is_file(), f'missing {BUNDLE_MANIFEST.relative_to(ROOT)}'
    return _load(BUNDLE_MANIFEST)


@G2
def test_g2_bundle_manifest_valid():
    assert validate_manifest(_g2_manifest()) == []


@G2
def test_g2_manifest_listing_has_no_gt_names():
    m = _g2_manifest()
    assert not [f['relative_path'] for f in m['files'] if GT_NAME.search(f['relative_path'])]


@G2
def test_g2_stage_inputs_exclude_gt_and_renderer_trajectories():
    m = _g2_manifest()
    for stage in STAGES:
        assert not [p for p in m['stage_inputs'][stage] if GT_NAME.search(p)], stage


@G2
def test_g2_runs_frames_cameras_and_rtdetr_index():
    m = _g2_manifest()
    assert set(m['runs']) == set(RUNS)
    assert all(m['runs'][r]['detector'] == 'RT-DETR' for r in RUNS)


# ------------------------------------------------------------------ self-tests (always run, plain PASS)

def test_selftest_fake_report_passes_every_g1_check():
    assert validate_report(_fake_report(), _fake_draft()) == []


@pytest.mark.parametrize('mutate,needle', [
    (lambda r: r['inputs'][0].update(sha256='xyz'), 'sha256'),
    (lambda r: r['inputs'][0].update(relative_path='/Users/x/a.json'), 'absolute'),
    (lambda r: r['geometry']['A4-1-v2-4actor']['doors'][0].update(geometry_status='ASSUMED'), 'MEASURED'),
    (lambda r: r['geometry']['B4-1-v2-4actor'].update(walls=[]), 'walls empty'),
    (lambda r: r['geometry']['A4-1-v2-4actor']['walls'][0].pop('height_range_m'), 'height_range_m'),
    (lambda r: r['clearance'].update(verdict='UNKNOWN'), 'clearance'),
    (lambda r: r['spawn_points']['A4-1-v2-4actor'][0].update(outside_all_render_cameras=False), 'outside'),
    (lambda r: r['spawn_points']['A4-1-v2-4actor'][0].update(xy=[1.0, 1.0]), 'differs from the draft'),
    (lambda r: r['color']['b_by_camera'][0].update(b_hue_measured=0.2, in_band=True), 'outside the red band'),
    (lambda r: r['color']['b_by_camera'].pop(), 'no B measurement'),
    (lambda r: r['ambiguity']['episodes']['A4-1-v2-4actor'].pop(), 'episodes in total'),
    (lambda r: r['ambiguity']['episodes']['B4-1-v2-4actor'][0].update(has_distractor=False), 'no distractor'),
    (lambda r: r['render_cost'].update(free_gib_before=8.5), 'stop line'),
    (lambda r: r['boundary'].update(rendered=True), 'boundary.rendered'),
])
def test_selftest_bad_report_is_rejected(mutate, needle):
    report = _fake_report()
    mutate(report)
    errs = validate_report(report, _fake_draft())
    assert any(needle in e for e in errs), errs


def test_selftest_clearance_gate_catches_actor_inside_wall():
    report = _fake_report()
    # a wall running through the actors' route (x 50..60, y 50) must flip the rerun to FAIL
    report['geometry']['A4-1-v2-4actor']['walls'].append(
        {'segment_id': 'W_BAD', 'a': [55.0, 40.0], 'b': [55.0, 60.0], 'height_range_m': [0.0, 2.8]})
    assert any('FAIL' in e for e in check_clearance(report, _fake_draft()))


def test_selftest_clearance_without_geometry_is_not_pass():
    report = _fake_report()
    for g in report['geometry'].values():
        g['walls'], g['furniture'] = [], []
    # no segments is not UNKNOWN to the checker (empty list), so the geometry gate must catch it
    assert any('walls empty' in e for e in check_geometry(report))


def test_selftest_real_draft_is_unknown_until_geometry_arrives():
    """Anchor: today's draft has walls=null, so the checker says UNKNOWN. G1 requires that to change."""
    result = _load_checker().check_document(_load(DRAFT))
    assert result['verdict'] == 'UNKNOWN'
    assert all(r['check_status']['walls'] == 'UNKNOWN' for r in result['runs'])


def test_selftest_fake_manifest_passes():
    assert validate_manifest(_fake_manifest()) == []


@pytest.mark.parametrize('mutate,needle', [
    (lambda m: m['files'][0].update(relative_path='/Users/me/x.json'), 'relative'),
    (lambda m: m['files'][0].update(relative_path='r004_v2/gt_private/gt.json'), 'GT'),
    (lambda m: m['files'][0].update(sha256='1'), 'sha256'),
    (lambda m: m.update(file_count=3), 'file_count'),
    (lambda m: m.update(total_bytes=1), 'total_bytes'),
    (lambda m: m['receipt'].update(gt_read=True), 'gt_read'),
    (lambda m: m['runs']['A4-1-v2-4actor']['cameras'].pop('CAM_W1'), 'cameras must be exactly'),
    (lambda m: m['runs']['A4-1-v2-4actor']['cameras']['CAM_W1'].update(frame_count=7), 'frame_count should be'),
    (lambda m: m['runs']['B4-1-v2-4actor'].update(detection_index_relative_path='r004_v2/none.json'), 'detection index'),
    (lambda m: m['stage_inputs']['ranking'].append('r004_v2/a4/renderer_trajectory.jsonl'), 'isolation'),
    (lambda m: m['stage_inputs']['reconstruction'].append('r004_v2/a4/depth.npz'), 'isolation'),
    (lambda m: m.update(scoring_private={'x': 1}), 'FORBIDDEN_KEYS'),
    (lambda m: m['runs']['A4-1-v2-4actor'].update(path='x'), 'FORBIDDEN_KEYS'),
    (lambda m: m.update(local_root='/Users/me/amidst-artifacts'), 'local_root'),
])
def test_selftest_bad_manifest_is_rejected(mutate, needle):
    m = _fake_manifest()
    mutate(m)
    errs = validate_manifest(m)
    assert any(needle in e for e in errs), errs


def test_selftest_gate_markers_are_strict_and_cover_every_gate():
    src = Path(__file__).read_text(encoding='utf-8')
    gates = re.findall(r'^@(G1|G2)\ndef (test_g[12]_\w+)', src, flags=re.M)
    assert len([g for g in gates if g[0] == 'G1']) == 8 and len([g for g in gates if g[0] == 'G2']) == 4
    assert 'strict=True' in src.split('G1 = ', 1)[1].split('\n', 1)[0]
    assert 'strict=True' in src.split('G2 = ', 1)[1].split('\n', 1)[0]
