"""#676 bounded synthetic observations; no API, images, renderer or GT input."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from amidst.live_mode.scheduler import CameraScheduler
from amidst.live_mode.tracker import Tracker


def replay(color):
    tracker = Tracker(SimpleNamespace(ground=lambda *_: None), target_color=color, gate_m=4)
    tracker.seed({'tick': 0, 'cam': 'CAM_W2', 'est_xy': [0, 0]}, 0, 'SYNTHETIC_USER_PICK')
    graph = {'cameras': [{'camera_id': c} for c in ('CAM_W2', 'OTHER')], 'transitions': []}
    scheduler = CameraScheduler(graph)
    if hasattr(scheduler, 'set_target_color'):
        scheduler.set_target_color(color)
    rows = []
    for tick, t_s, x, observed in [(1, .5, None, None), (2, 23.5, 5, color),
                                 (3, 24, 1, 'red' if color == 'blue' else 'blue'),
                                 (4, 24.5, 1, color)]:
        detections = {'CAM_W2': [] if x is None else [
            {'color': observed, 'score': .9, 'bbox': [0, 0, 10, 20], 'est_xy': [x, 0]}]}
        diagnostic = tracker.diagnose_candidates(detections, t_s) if hasattr(tracker, 'diagnose_candidates') else [
            {'cam': 'CAM_W2', 'color': observed, 'target_color': color, 'distance_m': x,
             'gate_m': 4, 'reason': 'NO_OBSERVATIONS' if x is None else
             'COLOR_MISMATCH' if observed != color else 'OUTSIDE_GATE' if x > 4 else 'ELIGIBLE'}]
        tracking = tracker.update(tick, detections, (320, 180), t_s, projected=True)
        scheduler.observe(detections, t_s)
        rows.append({'tick': tick, 'capture_s': t_s, 'diagnostic': diagnostic, 'tracking': tracking,
                     'distant_active_plan': scheduler.plan('OTHER', 0, ['CAM_W2', 'OTHER'], t_s=t_s)})
    tracker.seed({'tick': 5, 'cam': 'CAM_W2', 'est_xy': [5, 0]}, 25, 'USER_PICK')
    manual = tracker.update(6, {'CAM_W2': [{'color': color, 'score': .9, 'bbox': [0, 0, 10, 20],
                            'est_xy': [5, 0]}]}, (320, 180), 25.5, projected=True)
    return {'target_color': color, 'rows': rows, 'manual_reselection': manual}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    first = {color: replay(color) for color in ('red', 'blue')}
    assert first == {color: replay(color) for color in ('red', 'blue')}
    root = Path(__file__).resolve().parents[2]
    result = {'scope': 'SYNTHETIC_OBSERVATIONS_NOT_ORIGINAL_23_5S_EVENT', 'paid_api_calls': 0,
              'replay_repeats': 2, 'cases': first,
              'source_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [root / 'src/amidst/live_mode' / name
                                         for name in ('tracker.py', 'scheduler.py', 'advisor.py', 'server.py')]}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
