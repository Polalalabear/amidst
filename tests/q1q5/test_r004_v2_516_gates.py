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
DRAFT_V21 = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json'
DRAFT_V22 = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json'  # Codex's corrected routes (D207)
FIXLOG_V22 = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_2_CODEX_FIXLOG.md'
DRAFT = DRAFT_V22 if DRAFT_V22.is_file() else DRAFT_V21  # prefer v2.2 once it exists
HSV_VERSION = 'D131-DEMO-HSV-v1'
CROP_RATIO = 0.5  # D131-DEMO-HSV-v1 (upper 50% of the bbox)
CHECKER = ROOT / 'scripts/design/check_actor_clearance.py'

REPORT_SCHEMA = 'amidst.r004-v2-feasibility.v1'
MANIFEST_SCHEMA = 'amidst.r004-v2-bundle-manifest.v1'
RUNS = {'A4-1-v2-4actor': 'A4-1', 'B4-1-v2-4actor': 'B4-1'}
RENDER_CAMERAS = {
    'A4-1-v2-4actor': ['CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_W1'],
    'B4-1-v2-4actor': ['CAM_BRANCH', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE'],
}
SPAWN_ACTORS = ('A', 'B', 'C')
STOP_LINE_GIB = 8.0
SHA256 = re.compile(r'^[0-9a-f]{64}$')
GIT_SHA = re.compile(r'^[0-9a-f]{40}$')
GT_NAME = re.compile(r'(?i)(gt_private|scoring_private|ground_?truth|renderer_?traj|visib|depth|traject|(^|[/_.-])gt([/_.-]|$))')
STAGES = ('detection_index', 'local_track', 'ranking', 'reconstruction')
DOOR_WALL_TOL_M = 0.5        # a door centre lies within width_m/2 + this of some wall segment (contract)
ROUTE_WALL_MARGIN_M = 15.0   # at least one wall lies within this of the actors' route bbox (contract)
B_BAND_MARGIN = 0.02         # B hue is at least this far from both red-band edges (scenario card v2 7.6)
OLD_RUN_IDS = ('ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1', 'ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1')


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


def rerun_clearance(report, draft, geometry=None):
    """Put the report's measured walls/furniture/doors into the draft and run the checker."""
    chk = _load_checker()
    doc = copy.deepcopy(draft)
    for run in doc['runs']:
        geo = report['geometry'][run['run_id']]
        run['walls'] = _segments(geo['walls']) + _segments(geo['furniture'])
        run['doors'] = [{'door_id': d['door_id'], 'center_xy': d['center_xy'], 'normal_xy': d['normal_xy'],
                         'width_m': d['width_m'], 'geometry_status': 'MEASURED'} for d in geo['doors']]
        run.pop('advisory_boundaries', None)
    # geometry=None: the draft's geometry_ref supplies the cameras/occluders that spawn_exit needs
    return chk.check_document(doc, geometry=geometry)


def _point_in_box(p, box):
    (x0, x1), (y0, y1) = box
    return min(x0, x1) <= p[0] <= max(x0, x1) and min(y0, y1) <= p[1] <= max(y0, y1)


def _dist_point_segment(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / n))
    return ((p[0] - ax - t * dx) ** 2 + (p[1] - ay - t * dy) ** 2) ** 0.5


def _dist_segment_bbox(a, b, bbox):
    """Distance from a segment to an axis-aligned bbox (x0, y0, x1, y1); sampled, 0 if they touch."""
    x0, y0, x1, y1 = bbox
    best = float('inf')
    for k in range(101):
        t = k / 100
        px, py = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        best = min(best, ((max(x0 - px, 0, px - x1)) ** 2 + (max(y0 - py, 0, py - y1)) ** 2) ** 0.5)
    return best


def _route_bbox(draft_run):
    pts = [w['xy'] for a in draft_run['actors'] for w in a['waypoints']]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def _hue_in_band(h, band):
    lo, hi = band
    return (lo <= h <= hi) if lo <= hi else (h >= lo or h <= hi)


def _hue_margin(h, band):
    """Circular distance (hue is 0..1, wraps) from h to the nearer band edge."""
    return min(min(abs(h - e), 1 - abs(h - e)) for e in band)


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
    for needed in (DRAFT.name, 'check_actor_clearance.py', '.blend'):
        if needed not in names:
            errs.append(f'inputs: no entry for {needed}')
    hsv = [i for i in inputs if 'hsv' in (i.get('relative_path') or '').lower()]
    if not hsv:
        errs.append('inputs: no entry for the formal HSV config (relative_path containing "hsv")')
    else:
        want = (report.get('color') or {}).get('hsv_config_sha256')
        if want and not any(i.get('sha256') == want for i in hsv):
            errs.append('inputs: color.hsv_config_sha256 matches no HSV input entry')
    return errs


def check_geometry(report, draft):
    errs = []
    draft_runs = {r['run_id']: r for r in draft['runs']}
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
        # every door the draft lists must be covered (rerun_clearance replaces the draft's doors)
        for dd in draft_runs[run_id].get('doors') or []:
            if dd['door_id'] not in doors:
                errs.append(f"geometry[{run_id}]: draft door {dd['door_id']} missing from the report")
        segs = [s for k in ('walls', 'furniture') for s in geo.get(k) or []
                if all(isinstance(s.get(q), list) and len(s[q]) == 2 for q in ('a', 'b'))]
        wall_segs = [s for s in geo.get('walls') or [] if s in segs]
        for door_id, d in doors.items():
            c, w = d.get('center_xy'), d.get('width_m')
            if not (isinstance(c, list) and len(c) == 2 and isinstance(w, (int, float)) and wall_segs):
                continue
            near = min(_dist_point_segment(c, s['a'], s['b']) for s in wall_segs)
            if near > w / 2 + DOOR_WALL_TOL_M:
                errs.append(f'geometry[{run_id}]: door {door_id} is {near:.2f} m from the nearest wall '
                            f'(must be within width_m/2 + {DOOR_WALL_TOL_M} m: the door sits in a wall)')
        if wall_segs:
            bb = _route_bbox(draft_runs[run_id])
            if min(_dist_segment_bbox(s['a'], s['b'], bb) for s in wall_segs) > ROUTE_WALL_MARGIN_M:
                errs.append(f'geometry[{run_id}]: no wall within {ROUTE_WALL_MARGIN_M} m of the actors\' route '
                            '(geometry is not from this scene)')
    return errs


def check_draft_files(draft_path, fixlog_path=FIXLOG_V22):
    """A v2.2 draft (Codex-corrected routes) must ship its FIXLOG next to it."""
    if 'V2_2' in Path(draft_path).name and not Path(fixlog_path).is_file():
        return [f'draft {Path(draft_path).name} needs {Path(fixlog_path).name} next to it (Codex route fixes are logged)']
    return []


def check_render_cameras(draft):
    errs = []
    for run in draft['runs']:
        want = RENDER_CAMERAS[run['run_id']]
        got = run.get('render_camera_ids')
        if not isinstance(got, list) or sorted(got) != sorted(want):
            errs.append(f"clearance: draft {run['run_id']} render_camera_ids must be {want} (CAM_ENTRY is a render camera), got {got}")
    return errs


def check_clearance(report, draft, geometry=None):
    errs = check_render_cameras(draft)
    claimed = report.get('clearance') or {}
    if claimed.get('verdict') != 'PASS' or claimed.get('walls_status') != 'PASS':
        errs.append('clearance: report must claim verdict PASS and walls_status PASS (was UNKNOWN in the draft)')
    for key in ('command', 'checker_git_sha'):
        if not claimed.get(key):
            errs.append(f'clearance: missing {key}')
    try:
        result = rerun_clearance(report, draft, geometry)
    except Exception as exc:  # malformed geometry
        return errs + [f'clearance: rerun failed: {type(exc).__name__}: {exc}']
    for run in result['runs']:
        st = run['check_status']
        if run['verdict'] != 'PASS':
            errs.append(f"clearance: rerun {run['run_id']} verdict {run['verdict']} {st}")
        if st.get('walls') != 'PASS':
            errs.append(f"clearance: rerun {run['run_id']} walls status {st.get('walls')} (UNKNOWN means no geometry)")
        if st.get('spawn_exit') != 'PASS':
            errs.append(f"clearance: rerun {run['run_id']} spawn_exit status {st.get('spawn_exit')} "
                        '(UNKNOWN means no geometry or render_camera_ids; FAIL means a spawn/exit point is in view)')
    return errs


def check_spawn(report, draft):
    errs = []
    spawn = report.get('spawn_points') or {}
    for run in draft['runs']:
        run_id = run['run_id']
        rows = {(r.get('actor_id'), r.get('kind')): r for r in spawn.get(run_id) or []}
        boxes = [b for bs in run['estimate_model']['assumed_camera_coverage_xy_boxes'].values() for b in bs]
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
                if any(_point_in_box(wp['xy'], b) for b in boxes):
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: draft point is inside an "
                                'assumed_camera_coverage_xy_boxes box; report it on #516 (Claude moves the route)')
                if row.get('outside_all_render_cameras') is not True:
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: must be outside every render camera")
                if sorted(row.get('cameras_checked') or []) != sorted(RENDER_CAMERAS[run_id]):
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: cameras_checked != {RENDER_CAMERAS[run_id]}")
                if row.get('method') != 'static_projection':
                    errs.append(f"spawn[{run_id}] {actor['actor_id']} {kind}: method must be static_projection")
    return errs


def check_color(report, draft=None):
    errs = []
    c = report.get('color') or {}
    band = c.get('red_band_hue') or []
    hsv = (draft or {}).get('hsv_config')
    if draft is not None:
        if not isinstance(hsv, dict) or hsv.get('version') != HSV_VERSION:
            errs.append(f'color: the draft must carry hsv_config {HSV_VERSION}')
        else:
            if band != hsv.get('red_hue_band'):
                errs.append(f"color: red_band_hue {band} differs from {HSV_VERSION} {hsv.get('red_hue_band')}")
            if c.get('hsv_config_sha256') != hsv.get('canonical_content_sha256'):
                errs.append(f'color: hsv_config_sha256 differs from the {HSV_VERSION} canonical_content_sha256 in the draft')
    if len(band) != 2 or not c.get('hsv_config_sha256') or not _is_sha(c.get('hsv_config_sha256')):
        return ['color: needs red_band_hue [lo, hi] and hsv_config_sha256 (formal config, D204)']
    # in-band status is recomputed from the reported hues; the self-reported flags must agree with it
    t = c.get('t_hue')
    if not isinstance(t, (int, float)):
        errs.append('color: t_hue (measured target hue) missing')
    elif not _hue_in_band(t, band):
        errs.append(f'color: T hue {t} is outside the red band {band}')
    for who, want in (('a', True), ('c', False)):
        h = c.get(f'{who}_hue')
        if not isinstance(h, (int, float)):
            errs.append(f'color: {who}_hue (measured hue) missing')
            continue
        if _hue_in_band(h, band) is not want:
            errs.append(f'color: {who.upper()} hue {h} must be {"inside" if want else "outside"} the red band {band}')
        if c.get(f'{who}_in_band') is not want:
            errs.append(f'color: {who}_in_band must be {want}')
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
        elif not _hue_in_band(h, band) or r.get('in_band') is not True:
            errs.append(f"color: B hue {h} in {r.get('camera_id')} is outside the red band {band} (D204 needs inside)")
        elif _hue_margin(h, band) < B_BAND_MARGIN:
            errs.append(f"color: B hue {h} in {r.get('camera_id')} is within {B_BAND_MARGIN} of the red-band edge "
                        '(margin, scenario card 7.6)')
        if not isinstance(r.get('crop_ratio'), (int, float)) or abs(r['crop_ratio'] - CROP_RATIO) > 1e-9:
            errs.append(f"color: {r.get('camera_id')} crop_ratio must be {CROP_RATIO} (upper 50% of bbox, {HSV_VERSION})")
    return errs


def check_ambiguity(report, draft):
    errs, total = [], 0
    dur = {r['run_id']: r['duration_us'] / 1e6 for r in draft['runs']}
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
        wins = sorted((e['start_s'], e['end_s']) for e in eps
                      if isinstance(e.get('start_s'), (int, float)) and isinstance(e.get('end_s'), (int, float)))
        if wins and (wins[0][0] < 0 or max(w[1] for w in wins) > dur[run_id]):
            errs.append(f'ambiguity[{run_id}]: episode window outside the run [0, {dur[run_id]}] s')
        if any(b[0] < a[1] for a, b in zip(wins, wins[1:])):
            errs.append(f'ambiguity[{run_id}]: episode windows overlap')
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
        if cost['total_disk_gib_estimate'] + 1e-9 < sum(cost['runs'][r]['disk_gib_estimate'] for r in RUNS):
            errs.append('render_cost: total_disk_gib_estimate is less than the sum of the per-run estimates')
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


def validate_report(report, draft, geometry=None):
    errs = []
    if report.get('schema') != REPORT_SCHEMA:
        errs.append(f'schema must be {REPORT_SCHEMA}')
    for fn in (check_inputs, check_cost, check_actor_cloning, check_boundary):
        errs += fn(report)
    errs += check_color(report, draft)
    errs += check_geometry(report, draft)
    errs += check_ambiguity(report, draft)
    errs += check_spawn(report, draft)
    if not any(e.startswith('geometry') for e in errs):
        errs += check_clearance(report, draft, geometry)
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


def validate_manifest(m):
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
    new_ids = []
    for run_id in RUNS:
        run = (m.get('runs') or {}).get(run_id)
        if not run:
            errs.append(f'runs[{run_id}]: missing')
            continue
        if not run.get('run_id_new') or run['run_id_new'] in OLD_RUN_IDS:
            errs.append(f'runs[{run_id}]: run_id_new must be a NEW run id, not the old r004 d124 run')
        new_ids.append(run.get('run_id_new'))
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
    if len(set(new_ids)) != len(new_ids):
        errs.append('runs: the two run_id_new values must differ from each other')
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
        {'run_id': rid, 'duration_us': {'A4-1-v2-4actor': 50_000_000, 'B4-1-v2-4actor': 42_000_000}[rid], 'rules': {}, 'doors': [], 'corridors': [], 'walls': None,
         'seed': None, 'render_camera_ids': list(RENDER_CAMERAS[rid]),
         'estimate_model': {'assumed_camera_coverage_xy_boxes': {c: [[[0, 1], [0, 1]]] for c in RENDER_CAMERAS[rid]}},
         'actors': [{'actor_id': a, 'waypoints': [{'t_us': 2_000_000, 'xy': [50.0, 50.0 + n]},
                                                 {'t_us': 9_000_000, 'xy': [60.0, 50.0 + n]}]}
                    for n, a in enumerate(('T',) + SPAWN_ACTORS)]}
        for rid in RUNS],
        'hsv_config': {'version': HSV_VERSION, 'canonical_content_sha256': 'a' * 64, 'red_hue_band': [0.95, 0.05],
                       'crop_ratio': CROP_RATIO}}


def _fake_geometry():
    """Synthetic catalog (no real scene): every render camera sits at x=100 looking +x, so the fake
    actors (x 50..60, behind it) are out of view."""
    def cam(cid):
        return {'camera_id': cid, 'camera_to_world': [[0, 0, -1, 100.0], [-1, 0, 0, 50.0], [0, 1, 0, 1.5], [0, 0, 0, 1]],
                'fx': 480.0, 'fy': 480.0, 'cx': 480.0, 'cy': 270.0, 'width': 960, 'height': 540,
                'clip_start': 0.05, 'clip_end': 100.0}
    cams = sorted({c for cs in RENDER_CAMERAS.values() for c in cs})
    return {'schema': 'fake', 'clearance_segments': [{'segment_id': 'far', 'a': [900, 900], 'b': [901, 900]}],
            'occluders_full_height': [{'occluder_id': 'far', 'a': [900, 900], 'b': [901, 900]}],
            'cameras': [cam(c) for c in cams], 'floors': []}


def _fake_report(draft=None):
    draft = draft or _fake_draft()
    sha = 'a' * 64
    door_for = {'A4-1-v2-4actor': 'R004_WEST_ENTRY', 'B4-1-v2-4actor': 'PORTAL_R101'}
    r = {
        'schema': REPORT_SCHEMA,
        'inputs': [{'relative_path': f'docs/evaluation/{DRAFT.name}', 'git_sha': 'b' * 40, 'sha256': sha},
                   {'relative_path': 'scripts/design/check_actor_clearance.py', 'git_sha': 'b' * 40, 'sha256': sha},
                   {'relative_path': 'LOCAL/r004/base_a4.blend', 'git_sha': 'b' * 40, 'sha256': sha},
                   {'relative_path': 'configs/red_band_hsv.json', 'git_sha': 'b' * 40, 'sha256': sha}],
        'geometry': {rid: {
            'floor_z_m': 0.0,
            'walls': [{'segment_id': 'W1', 'a': [70.0, 45.0], 'b': [70.0, 60.0], 'height_range_m': [0.0, 2.8]}],
            'furniture': [],
            'doors': [{'door_id': door_for[rid], 'center_xy': [70.0, 50.0], 'normal_xy': [1, 0], 'width_m': 1.0,
                       'geometry_status': 'MEASURED', 'source_sha256': sha}]} for rid in RUNS},
        'clearance': {'verdict': 'PASS', 'walls_status': 'PASS', 'command': 'python scripts/design/check_actor_clearance.py x',
                      'checker_git_sha': 'b' * 40},
        'spawn_points': {run['run_id']: [
            {'actor_id': a['actor_id'], 'kind': k, 'xy': wp['xy'], 'method': 'static_projection',
             'outside_all_render_cameras': True, 'cameras_checked': list(RENDER_CAMERAS[run['run_id']])}
            for a in run['actors'] if a['actor_id'] in SPAWN_ACTORS
            for k, wp in (('first', a['waypoints'][0]), ('last', a['waypoints'][-1]))] for run in draft['runs']},
        'color': {'red_band_hue': [0.95, 0.05], 'hsv_config_sha256': sha, 't_hue': 0.0, 'a_hue': 0.99, 'c_hue': 0.6,
                  'a_in_band': True, 'c_in_band': False,
                  'b_by_camera': [{'run_id': rid, 'camera_id': c, 'b_hue_measured': 0.99, 'in_band': True, 'crop_ratio': CROP_RATIO}
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
    assert check_geometry(_g1_report(), _load(DRAFT)) == []


@G1
def test_g1_clearance_unknown_becomes_pass_with_geometry():
    assert check_clearance(_g1_report(), _load(DRAFT)) == []
    assert check_draft_files(DRAFT) == []


@G1
def test_g1_spawn_points_outside_all_render_cameras():
    assert check_spawn(_g1_report(), _load(DRAFT)) == []


@G1
def test_g1_b_stays_in_red_band_under_every_camera_light():
    assert check_color(_g1_report(), _load(DRAFT)) == []


@G1
def test_g1_ambiguity_episodes_at_least_five():
    assert check_ambiguity(_g1_report(), _load(DRAFT)) == []


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
    assert validate_report(_fake_report(), _fake_draft(), _fake_geometry()) == []


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
    # P2-1: far-away wall with the door moved onto it (x=900) must be refused
    (lambda r: [g.update(walls=[{'segment_id': 'W1', 'a': [900.0, 0.0], 'b': [900.0, 5.0], 'height_range_m': [0.0, 2.8]}])
                or g['doors'][0].update(center_xy=[900.0, 2.0]) for g in r['geometry'].values()], 'no wall within'),
    (lambda r: r['geometry']['A4-1-v2-4actor']['doors'][0].update(center_xy=[75.0, 50.0]), 'nearest wall'),
    # P2-2: HSV input, B margin, recomputed T/A/C
    (lambda r: r['inputs'].pop(), 'HSV config'),
    (lambda r: r['inputs'][-1].update(sha256='e' * 64), 'matches no HSV input'),
    (lambda r: r['color']['b_by_camera'][0].update(crop_ratio=0.3), 'crop_ratio must be 0.5'),
    (lambda r: r['color'].update(red_band_hue=[0.9, 0.1]), 'differs from D131-DEMO-HSV-v1'),
    (lambda r: r['color'].update(hsv_config_sha256='d' * 64), 'canonical_content_sha256'),
    (lambda r: r['color']['b_by_camera'][0].update(b_hue_measured=0.04), 'red-band edge'),
    (lambda r: r['color']['b_by_camera'][0].update(b_hue_measured=0.96), 'red-band edge'),
    (lambda r: r['color'].update(t_hue=0.5), 'T hue'),
    (lambda r: r['color'].update(a_hue=0.5), 'A hue'),
    (lambda r: r['color'].update(c_hue=0.99), 'C hue'),
    (lambda r: r['color'].update(c_in_band=True), 'c_in_band'),
    # P3
    (lambda r: r['spawn_points']['A4-1-v2-4actor'][0].update(xy=[-11.0, -1.6]), 'differs from the draft'),
    (lambda r: r['ambiguity']['episodes']['A4-1-v2-4actor'][0].update(end_s=60.0), 'outside the run'),
    (lambda r: r['ambiguity']['episodes']['A4-1-v2-4actor'][1].update(start_s=9.0), 'overlap'),
    (lambda r: r['render_cost'].update(total_disk_gib_estimate=0.5), 'sum of the per-run'),
])
def test_selftest_bad_report_is_rejected(mutate, needle):
    report = _fake_report()
    mutate(report)
    errs = validate_report(report, _fake_draft(), _fake_geometry())
    assert any(needle in e for e in errs), errs


def test_selftest_clearance_gate_catches_actor_inside_wall():
    report = _fake_report()
    # a wall running through the actors' route (x 50..60, y 50) must flip the rerun to FAIL
    report['geometry']['A4-1-v2-4actor']['walls'].append(
        {'segment_id': 'W_BAD', 'a': [55.0, 40.0], 'b': [55.0, 60.0], 'height_range_m': [0.0, 2.8]})
    assert any('FAIL' in e for e in check_clearance(report, _fake_draft(), _fake_geometry()))


def test_selftest_clearance_without_geometry_is_not_pass():
    report = _fake_report()
    for g in report['geometry'].values():
        g['walls'], g['furniture'] = [], []
    # no segments is not UNKNOWN to the checker (empty list), so the geometry gate must catch it
    assert any('walls empty' in e for e in check_geometry(report, _fake_draft()))


def test_selftest_real_draft_passes_the_checker_on_repo_geometry():
    """Anchor: the v2.1+ draft carries geometry_ref, so the checker (walls, spawn_exit) is PASS today.
    G1 still needs Codex's report to reproduce that on its own measured geometry."""
    result = _load_checker().check_document(_load(DRAFT))
    assert result['verdict'] == 'PASS', result['runs']
    assert all(r['check_status']['walls'] == 'PASS' and r['check_status']['spawn_exit'] == 'PASS' for r in result['runs'])
    assert check_render_cameras(_load(DRAFT)) == []
    assert check_draft_files(DRAFT) == []


def test_selftest_spawn_exit_pass_fail_and_unknown():
    report, geo = _fake_report(), _fake_geometry()
    assert check_clearance(report, _fake_draft(), geo) == []
    # first point of A moved in front of the cameras (cameras at x=100 look +x): in view -> FAIL
    draft = _fake_draft()
    for run in draft['runs']:
        a = next(a for a in run['actors'] if a['actor_id'] == 'A')
        a['waypoints'][0]['xy'] = [104.0, 50.0]
    errs = check_clearance(report, draft, geo)
    assert any('spawn_exit status FAIL' in e for e in errs), errs
    # draft without render_camera_ids -> UNKNOWN is not a pass
    draft = _fake_draft()
    for run in draft['runs']:
        run.pop('render_camera_ids')
    errs = check_clearance(report, draft, geo)
    assert any('render_camera_ids must be' in e for e in errs) and any('spawn_exit status UNKNOWN' in e for e in errs), errs
    # CAM_ENTRY missing from the A4 render set is refused
    draft = _fake_draft()
    draft['runs'][0]['render_camera_ids'].remove('CAM_ENTRY')
    assert any('CAM_ENTRY' in e for e in check_clearance(report, draft, geo))


def test_selftest_v22_draft_needs_its_fixlog(tmp_path):
    assert check_draft_files(DRAFT_V21) == []
    draft = tmp_path / 'R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json'
    assert check_draft_files(draft, tmp_path / 'LOG.md')
    (tmp_path / 'LOG.md').write_text('x')
    assert check_draft_files(draft, tmp_path / 'LOG.md') == []


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
    (lambda m: m['runs']['A4-1-v2-4actor'].update(run_id_new='ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1'), 'NEW run id'),
    (lambda m: m['runs']['B4-1-v2-4actor'].update(run_id_new=m['runs']['A4-1-v2-4actor']['run_id_new']), 'must differ'),
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


def test_selftest_spawn_point_inside_assumed_coverage_box_is_rejected():
    draft = _fake_draft()
    for run in draft['runs']:  # draft waypoints at (50, 50) / (60, 50) now fall in a coverage box
        run['estimate_model']['assumed_camera_coverage_xy_boxes']['CAM_W1'] = [[[49.0, 61.0], [49.0, 54.0]]]
    errs = check_spawn(_fake_report(draft), draft)
    assert any('inside an assumed_camera_coverage_xy_boxes' in e for e in errs), errs


def test_selftest_draft_door_missing_from_report_is_rejected():
    draft = _fake_draft()
    draft['runs'][0]['doors'] = [{'door_id': 'EXTRA_DOOR'}]
    errs = check_geometry(_fake_report(draft), draft)
    assert any('EXTRA_DOOR' in e for e in errs), errs
