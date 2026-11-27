"""E8 Part 2: closed loop, B1 tracks and the model decides only at hand-off triggers (#780; design E8_DESIGN_V1.md §3). INFERENCE SIDE.

The replay loop is ``e3_f4_run.replay`` itself (same CONFIG, same b-log rows); the E8 decider is injected through its
``make_decider`` hook for one call (``run_case``), so B1's tracking path is not re-implemented. The decider sits on
``live_mode.server.State._infer_tracking``'s ``decider.step`` hook, like ``ServiceLiveDecider``.

Triggers (§3.2, first that holds, ACQUIRE first, global minimum gap 1.0 s, nothing while a MEASURED answer is in flight):
  LOST       lost_ticks >= 2, then every 1.0 s while still lost
  SWITCH     a SWITCH or REACQUIRE event at this tick
  AMBIGUOUS  TRACKING, lost 0, >= 2 red candidates within 4 m of the T-1 estimate and two of them >= 1.5 m apart; at most every 2.0 s
Application (§3.3): KEEP nothing; SELECT resets the tracker onto the option's ground point (as ServiceLiveDecider's correction);
NOT_VISIBLE sets the tracker LOST and shows nothing for 1.0 s; invalid = KEEP with fallback_reason.
Latency (§3.4): ZERO_LATENCY applies at the trigger tick; MEASURED at the first tick with (t'-t)*0.2 s > latency, the SELECT box chained
with e3_f4_run.chain_box (IoU >= 0.3) or EXPIRED. No Ground Truth anywhere; identity stays UNCONFIRMED.
"""
from __future__ import annotations

import contextlib
import math
from typing import Any, Callable

from amidst.evaluation import e8_requests as R

TICK_S = 0.2
LOST_TICKS = 2
LOST_REPEAT = 5
AMBIG_REPEAT = 10
MIN_GAP = 5
SUPPRESS_TICKS = 5
GATE_M = 4.0
AMBIG_SPREAD_M = 1.5
BOX_RADIUS_M = 1.5   # = e3_f4_run.CONFIG['box_radius_m'] (display rule)


def b1_display(tracking: dict, out: dict) -> dict | None:
    """What B1 shows at this tick (the e3_f4_run.replay box rule) -> (camera, D id)."""
    active, est = tracking.get('active_cam'), tracking.get('est_xy')
    if tracking.get('state') != 'TRACKING' or tracking.get('lost_ticks') or not active or est is None:
        return None
    near = [(math.dist(d['est_xy'], est), i) for i, d in enumerate(out.get(active, []))
            if d.get('est_xy') is not None and math.dist(d['est_xy'], est) <= BOX_RADIUS_M]
    return {'camera_id': active, 'detection_id': f'D{min(near)[1] + 1}'} if near else None


def ambiguous(cands: list[dict], est) -> bool:
    if est is None:
        return False
    red = [c['ground_xy'] for c in cands if R.TARGET_COLOR in c.get('colors', []) and c.get('ground_xy') is not None
           and math.dist(c['ground_xy'], est) <= GATE_M]
    return len(red) >= 2 and max(math.dist(a, b) for a in red for b in red) >= AMBIG_SPREAD_M


class E8HandoffDecider:
    """``ask(request) -> (answer | None, error | None, latency_s)``; one instance per (case, group)."""
    any_color = False

    def __init__(self, ask: Callable, *, case_id: str, dataset_group: str, camera_ids: list[str], cands_by_tick: dict, level: str,
                 scene: dict | None, scene_sha256: str | None, latency: str = 'ZERO_LATENCY'):
        if level not in R.TEXT_LEVELS:
            raise ValueError('PART2_TEXT_LEVELS_ONLY')
        if latency not in ('ZERO_LATENCY', 'MEASURED'):
            raise ValueError('BAD_LATENCY')
        self.ask, self.case_id, self.group, self.cams = ask, case_id, dataset_group, list(camera_ids)
        self.cands_by_tick, self.level, self.scene, self.scene_sha, self.latency = cands_by_tick, level, scene, scene_sha256, latency
        self.prev: dict | None = None
        self.acquired = False
        self.last_ask = self.lost_ask = self.amb_ask = None
        self.suppress_until = -1
        self.pending: dict | None = None
        self.log: list[dict] = []
        # attributes e3_f4_run.replay reads at the end
        self.records, self.calls_log, self.model_latency, self.chain_log, self.calls = [], [], [], [], 0

    # ---------------------------------------------------------------- triggers
    def trigger(self, tick: int, tracking: dict) -> str | None:
        if not self.acquired or self.pending is not None:
            return None
        if self.last_ask is not None and tick - self.last_ask < MIN_GAP:
            return None
        lost = tracking.get('lost_ticks') or 0
        if lost == 0:
            self.lost_ask = None
        if tracking.get('state') in ('TRACKING', 'LOST') and lost >= LOST_TICKS and (self.lost_ask is None or tick - self.lost_ask >= LOST_REPEAT):
            return 'LOST'
        if {e.get('type') for e in tracking.get('events') or []} & {'SWITCH', 'REACQUIRE'}:
            return 'SWITCH'
        if (tracking.get('state') == 'TRACKING' and lost == 0 and (self.amb_ask is None or tick - self.amb_ask >= AMBIG_REPEAT)
                and ambiguous(self.cands_by_tick.get(tick, []), self.prev and self.prev.get('est_xy'))):
            return 'AMBIGUOUS'
        return None

    # ---------------------------------------------------------------- application
    def _select(self, tick, t_s, tracker, tracking, cam, xy):
        prev = tracker.active
        tracker.est, tracker.state, tracker.lost, tracker.active = list(xy), 'TRACKING', 0, cam
        tracker.last_seen[cam] = tick
        tracker.t_seen = t_s
        tracking.update(state='TRACKING', est_xy=list(xy), active_cam=cam, lost_ticks=0, decision_source='AGENT')
        if prev is not None and cam != prev:
            tracking.setdefault('events', []).append({'tick': tick, 'type': 'SWITCH', 'cam': cam, 'detail': {'from': prev, 'by': 'AGENT'}})

    def _apply(self, tick, t_s, tracker, tracking, entry, ans, disp, xy):
        if ans is None:
            entry['applied'] = 'FALLBACK_KEEP'
        elif ans['answer'] == 'SELECT':
            if xy is None:
                entry['applied'] = 'FALLBACK_KEEP'
                entry['fallback_reason'] = 'NO_GROUND_POINT'
            else:
                self._select(tick, t_s, tracker, tracking, disp['camera_id'], xy)
                entry['applied'] = 'SELECT'
        elif ans['answer'] == 'NOT_VISIBLE':
            tracker.state = 'LOST'
            self.suppress_until = tick + SUPPRESS_TICKS
            entry['applied'] = 'NOT_VISIBLE'
        else:
            entry['applied'] = 'KEEP'
        entry['applied_tick'] = tick

    def _ground_of(self, tick, cam, did):
        return next((c['ground_xy'] for c in self.cands_by_tick.get(tick, []) if c['camera_id'] == cam and c['detection_id'] == did), None)

    # ---------------------------------------------------------------- hook
    def step(self, tick, t_s, tracker, tracking, out, frames):
        if tracking.get('state') == 'TRACKING':
            self.acquired = True
        if self.pending is not None:
            self._advance_pending(tick, t_s, tracker, tracking, out)
        kind = self.trigger(tick, tracking)
        if kind is not None:
            self._ask(kind, tick, t_s, tracker, tracking, out)
        if tick < self.suppress_until:
            tracking.update(state='LOST', lost_ticks=max(1, tracking.get('lost_ticks') or 0))
        self.prev = R.snapshot_of({'tracking': tracking})
        return tracking

    def _ask(self, kind, tick, t_s, tracker, tracking, out):
        self.last_ask = tick
        if kind == 'LOST':
            self.lost_ask = tick
        if kind == 'AMBIGUOUS':
            self.amb_ask = tick
        cands = self.cands_by_tick.get(tick, [])
        req = R.build_request(case_id=self.case_id, dataset_group=self.group, tick=tick, level=self.level, perm='p0', cands=cands,
                              camera_ids=self.cams, snapshot=self.prev, keep_display=b1_display(tracking, out), scene=self.scene,
                              scene_sha256=self.scene_sha)
        ans, err, lat = self.ask(req)
        self.calls += 1
        disp = R.display_of(ans, req)
        entry = {'tick': tick, 'trigger': kind, 'answer': ans and ans['answer'], 'error': err, 'latency_s': lat, 'display': disp,
                 'latency_mode': self.latency}
        self.log.append(entry)
        self.model_latency.append(lat)
        self.calls_log.append({'request_id': req['request_id'], 'trigger': kind})
        self.records.append({'tick': tick, 'answer': ans and ans['answer'], 'error': err})
        xy = self._ground_of(tick, disp.get('camera_id'), disp.get('detection_id')) if disp['kind'] == 'BOX' else None
        if self.latency == 'ZERO_LATENCY' or ans is None or ans['answer'] == 'KEEP':
            self._apply(tick, t_s, tracker, tracking, entry, ans, disp, xy)
            return
        due = tick + 1
        while (due - tick) * TICK_S <= (lat or 0.0):
            due += 1
        box = None
        if ans['answer'] == 'SELECT':
            i = int(disp['detection_id'][1:]) - 1
            box = list(out[disp['camera_id']][i]['bbox'])
        self.pending = {'due': due, 'ans': ans, 'disp': disp, 'box': box, 'history': [], 'entry': entry}

    def _advance_pending(self, tick, t_s, tracker, tracking, out):
        from e3_f4_run import chain_box   # scripts/evaluation on sys.path (notebook / tests)
        p = self.pending
        p['history'].append({cam: [list(d['bbox']) for d in dets] for cam, dets in out.items()})
        if tick < p['due']:
            return
        self.pending = None
        entry, ans, disp = p['entry'], p['ans'], p['disp']
        if ans['answer'] != 'SELECT':
            self._apply(tick, t_s, tracker, tracking, entry, ans, disp, None)
            return
        chained = chain_box(p['box'], disp['camera_id'], p['history'])
        self.chain_log.append({'tick_call': entry['tick'], 'tick_effect': tick, 'expired': chained is None})
        if chained is None:
            entry.update(applied='EXPIRED', applied_tick=tick)
            return
        i = next(i for i, d in enumerate(out[disp['camera_id']]) if list(d['bbox']) == chained)
        xy = self._ground_of(tick, disp['camera_id'], f'D{i + 1}')
        self._apply(tick, t_s, tracker, tracking, entry, ans, {**disp, 'detection_id': f'D{i + 1}'}, xy)


# ------------------------------------------------------------------------------------------------ driver
def case_from_ticks(rows: list[dict], cameras: list[str]) -> dict:
    """Pack Part-2 tick rows -> the case dict e3_f4_run.replay reads (no frame paths: nothing opens images)."""
    return {'case_id': None, 'cameras': list(cameras), 'ticks': [(r['tick'], r['dets'], {}) for r in rows]}


@contextlib.contextmanager
def _inject(F, decider):
    orig = F.make_decider
    F.make_decider = lambda arm, transport, scene, clock: decider
    try:
        yield
    finally:
        F.make_decider = orig


def run_case(rows: list[dict], cameras: list[str], catalog, graph: dict, scene: dict, decider: E8HandoffDecider | None = None) -> dict[str, Any]:
    """B1 alone (decider None; reproduction gate V2) or B1 + an E8 decider. Returns e3_f4_run.replay rows + the decider log."""
    import e3_f4_run as F   # scripts/evaluation on sys.path
    case = case_from_ticks(rows, cameras)
    if decider is None:
        out_rows, _, _ = F.replay(case, 'B1', catalog, graph, scene)
        return {'rows': out_rows, 'log': []}
    with _inject(F, decider):
        out_rows, _, dec = F.replay(case, 'A_E8', catalog, graph, scene)
    for r in out_rows:   # the model gives no camera ranking: keep B1's (H4 input), not the empty A-arm hint
        r['ranking'] = F.rank_b1(graph, r['tracking']['active_cam'], cameras)
    return {'rows': out_rows, 'log': decider.log, 'decider': dec}


def b1_reproduced(rows: list[dict], frozen_rows: list[dict]) -> dict:
    """V2: every rows[].tracking equal to the frozen B1 b-log."""
    a = [r['tracking'] for r in rows]
    b = [r['tracking'] for r in frozen_rows]
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    ok = len(a) == len(b) and first is None
    return {'ok': ok, 'n_rows': len(a), 'n_frozen': len(b), 'first_diff_index': first}
