"""Track-to-actor IoU mapping with multi-actor support and manual-review gating (WP4, Gate 4).

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md §5.
Design: docs/design/AGENT_DECISION_V1.md §4.4.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute 2D bounding-box IoU for boxes [x0, y0, x1, y1]."""
    ix = max(0.0, float(min(a[2], b[2]) - max(a[0], b[0])))
    iy = max(0.0, float(min(a[3], b[3]) - max(a[1], b[1])))
    inter = ix * iy
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - inter
    return float(inter / union) if union > 0.0 else 0.0


def map_track_to_actor(
    observations: Sequence[Mapping],
    gt_source: Callable[[str, int], Mapping[str, Sequence[float]]],
    *,
    iou_match: float = 0.5,
    iou_manual_low: float = 0.3,
    majority_fraction: float = 0.6,
) -> dict:
    """Map a local track's observations to an actor via per-frame best IoU and majority vote.

    Each observation matches its highest-IoU actor if IoU >= ``iou_match`` (inclusive).
    If the most frequent matched actor reaches ``majority_fraction`` (inclusive) of all
    observations in the track, returns ``{"actor": actor, "needs_manual": False, "majority_fraction": frac}``;
    otherwise returns ``{"actor": None, "needs_manual": True, "majority_fraction": frac}``.
    """
    if not observations:
        return {'actor': None, 'needs_manual': True, 'majority_fraction': 0.0}

    counts: Counter[str] = Counter()
    had_uncertain = False
    for obs in observations:
        cam = str(obs['camera_id'])
        ts = int(obs['timestamp_us'])
        box = obs['box']
        gt_boxes = gt_source(cam, ts) or {}
        if not gt_boxes:
            continue
        best_actor: str | None = None
        best_val = -1.0
        for actor_name, gt_box in sorted(gt_boxes.items()):
            val = iou(box, gt_box)
            if val > best_val:
                best_val = val
                best_actor = actor_name
        if best_actor is not None and best_val >= iou_match:
            counts[best_actor] += 1
        elif best_actor is not None and best_val >= iou_manual_low:
            had_uncertain = True

    total = len(observations)
    if not counts:
        return {'actor': None, 'needs_manual': True, 'majority_fraction': 0.0}

    most_common = counts.most_common(2)
    top_actor, top_count = most_common[0]
    tie = len(most_common) > 1 and most_common[1][1] == top_count
    frac = float(top_count / total)

    if not tie and frac >= majority_fraction:
        return {'actor': top_actor, 'needs_manual': False, 'majority_fraction': frac}
    _ = had_uncertain
    return {'actor': None, 'needs_manual': True, 'majority_fraction': frac}
