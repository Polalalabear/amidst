"""E5 pixel-only continuation. No colours, graph gates, cross-camera association or new acquisition."""
from __future__ import annotations

import math
from copy import deepcopy

IOU_MIN = 0.3
COAST_TICKS = 2
OCCLUDED_TICKS = 10


def box_iou(a, b):
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def chain_box(box, camera, history):
    """Strict AO-L chain, including the application tick; no coasting across a missing detection."""
    cur = list(box)
    for dets in history:
        best = max(dets.get(camera, []), key=lambda d: box_iou(cur, d['bbox']), default=None)
        if best is None or box_iou(cur, best['bbox']) < IOU_MIN:
            return None
        cur = list(best['bbox'])
    return cur


class NeutralTracker:
    def __init__(self, projector, size=(320, 180)):
        self.projector, self.size = projector, size
        self.target = None
        self.status = 'LOST'
        self.reason = None

    def _ground(self, camera, box, previous):
        point = self.projector.ground(camera, (box[0] + box[2]) / 2, box[3], *self.size)
        if point is not None and len(point) == 2 and all(math.isfinite(x) for x in point):
            return list(point)
        return deepcopy(previous)

    def adopt(self, tick, camera, box, source):
        prev = self.target.get('est_xy') if self.target else None
        self.target = {'camera_id': camera, 'box': list(box), 'est_xy': self._ground(camera, box, prev),
                       'source': source, 'since_tick': tick, 'misses': 0, 'hold_until': None}
        self.status = 'FOLLOWING'
        self.reason = 'NO_GROUND_POINT' if self.target['est_xy'] is None else None

    def clear(self):
        self.target, self.status, self.reason = None, 'LOST', None

    def occlude(self, tick, camera):
        if self.target is None or camera != self.target['camera_id']:
            return False
        self.target.update(box=None, hold_until=tick + OCCLUDED_TICKS, misses=0)
        self.status = 'OCCLUDED_HOLD'
        return True

    def step(self, tick, target, dets_by_cam):
        self.target = deepcopy(target)
        self.reason = None
        if self.target is None:
            self.status = 'LOST'
        elif self.target.get('hold_until') is not None:
            if tick >= self.target['hold_until']:
                self.clear()
            else:
                self.status = 'OCCLUDED_HOLD'
        else:
            cam, box = self.target['camera_id'], self.target['box']
            best = max(dets_by_cam.get(cam, []), key=lambda d: box_iou(box, d['bbox']), default=None)
            if best is not None and box_iou(box, best['bbox']) >= IOU_MIN:
                new_box = list(best['bbox'])
                self.target.update(box=new_box, est_xy=self._ground(cam, new_box, self.target['est_xy']), misses=0)
                self.status = 'FOLLOWING'
            else:
                self.target['misses'] += 1
                if self.target['misses'] > COAST_TICKS:
                    self.clear()
                else:
                    self.status = 'COASTING'
        if self.target is not None and self.target['est_xy'] is None:
            self.reason = 'NO_GROUND_POINT'
        return deepcopy(self.target), self.status

    def tracking(self):
        t = self.target
        shown = t is not None and t['est_xy'] is not None
        return {'state': 'TRACKING' if shown else 'LOST', 'active_cam': t['camera_id'] if shown else None,
                'est_xy': deepcopy(t['est_xy']) if shown else None, 'lost_ticks': 0 if shown else 1,
                'box': deepcopy(t['box']) if shown else None}
