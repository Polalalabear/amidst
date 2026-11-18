"""Rule-based reacquisition policy over calibrated pixel observations."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from statistics import median

from .people import PeopleTracker


@dataclass(frozen=True)
class RelockConfig:
    t_short_s: float | None = None
    v_walk_m_s: float | None = None
    tau_app: float | None = None
    margin_app: float | None = None
    appearance_fields: tuple[str, ...] = ("red_ratio", "blue_ratio")
    appearance_scales: tuple[float, ...] = (1.0, 1.0)
    same_m: float = 1.5
    ref_ticks: int = 5
    predict: bool = False
    pred_horizon_s: float | None = None

    def __post_init__(self):
        metrics = (
            self.t_short_s,
            self.v_walk_m_s,
            self.tau_app,
            self.margin_app,
            self.pred_horizon_s,
        )
        if any(x is not None and (not math.isfinite(x) or x < 0) for x in metrics):
            raise ValueError("RELOCK_METRIC")
        if self.ref_ticks < 1 or not math.isfinite(self.same_m) or self.same_m <= 0:
            raise ValueError("RELOCK_REFERENCE")
        if (
            len(self.appearance_fields) != len(self.appearance_scales)
            or not set(self.appearance_fields) <= {"red_ratio", "blue_ratio"}
            or any(not math.isfinite(s) or s <= 0 for s in self.appearance_scales)
        ):
            raise ValueError("RELOCK_APPEARANCE")


def reference_points(est, velocity, unseen_s, horizon_s):
    if velocity is None or not horizon_s:
        return (est,)
    dt = min(max(0.0, unseen_s), horizon_s)
    return est, [est[i] + velocity[i] * dt for i in (0, 1)]


def distance(xy, points):
    return min(math.dist(xy, point) for point in points)


def finite_features(det, fields):
    values = [det.get(field) for field in fields]
    if not values or any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        return None
    return tuple(values)


def group_observations(candidates, same_m):
    """Build connected components at the contract radius. The first entry has the highest score."""
    groups = []
    for candidate in sorted(candidates, key=lambda item: -item[1]["score"]):
        nearby = [
            group
            for group in groups
            if any(math.dist(candidate[2], member[2]) < same_m for member in group)
        ]
        if not nearby:
            groups.append([candidate])
        else:
            nearby[0].append(candidate)
            for group in nearby[1:]:
                nearby[0].extend(group)
                groups.remove(group)
    return groups


@dataclass(frozen=True)
class Candidate:
    cam: str
    bbox: list
    xy: list
    dist_m: float
    d_app: float | None
    members: list

    def public(self, tick, rank):
        return {
            "cand_id": f"r{tick:x}.{rank:x}",
            "cam": self.cam,
            "bbox": list(self.bbox),
            "est_xy": list(self.xy),
            "dist_m": self.dist_m,
            "d_app": self.d_app,
            "rank": rank,
        }


@dataclass(frozen=True)
class Decision:
    candidate: Candidate | None = None
    mode: str | None = None
    reason: str | None = None
    options: tuple[Candidate, ...] = ()
    rejected: bool = False


class RelockPolicy:
    def __init__(self, config):
        self.config = config
        self.reference_samples = deque(maxlen=config.ref_ticks)
        self.people = PeopleTracker() if config.predict else None
        self.target_pid = None
        self.people_now = []

    @property
    def reference(self):
        if len(self.reference_samples) < self.config.ref_ticks:
            return None
        return tuple(median(axis) for axis in zip(*self.reference_samples, strict=True))

    def observe(self, t, candidates):
        if self.people is not None:
            self.people_now = self.people.update(t, candidates)

    def points(self, est, unseen_s):
        velocity = self.people.velocity(self.target_pid) if self.people is not None else None
        return reference_points(est, velocity, unseen_s, self.config.pred_horizon_s)

    def record_match(self, selected, cands):
        cam, det, xy = selected
        selected_group = next(
            group
            for group in group_observations(cands, self.config.same_m)
            if any(member[0] == cam and member[1] is det for member in group)
        )
        # Compare group members against the selected projection as well. A transitive
        # group that stretches beyond the radius is unsafe as an appearance reference.
        if all(math.dist(xy, member[2]) < self.config.same_m for member in selected_group):
            features = finite_features(det, self.config.appearance_fields)
            if features is not None:
                self.reference_samples.append(features)
        if self.people is not None:
            self.target_pid = next(
                (
                    person["pid"]
                    for person in self.people_now
                    if any(c == cam and d is det for c, d in person["dets"])
                ),
                None,
            )

    def is_short(self, unseen_s):
        cutoff = self.config.t_short_s
        return cutoff is None or (cutoff > 0 and unseen_s <= cutoff)

    def candidates(self, observations, points):
        reference = self.reference
        for group in group_observations(observations, self.config.same_m):
            cam, det, xy = group[0]
            features = finite_features(det, self.config.appearance_fields)
            d_app = (
                None
                if features is None or reference is None
                else math.sqrt(
                    sum(
                        ((x - r) / s) ** 2
                        for x, r, s in zip(
                            features, reference, self.config.appearance_scales, strict=True
                        )
                    )
                )
            )
            yield Candidate(cam, det["bbox"], xy, distance(xy, points), d_app, group)

    def find(self, observations, points, unseen_s, gate, max_gate):
        cfg = self.config
        groups = list(self.candidates(observations, points))
        inside = [c for c in groups if c.dist_m <= gate]
        if len(inside) == 1 and self.is_short(unseen_s):
            return Decision(candidate=inside[0], mode="short_gate")

        radius = max_gate if cfg.v_walk_m_s is None else gate + cfg.v_walk_m_s * unseen_s
        options = [c for c in groups if c.dist_m <= radius]
        if not options:
            return Decision()

        ranked = tuple(
            sorted(options, key=lambda c: (c.d_app is None, c.d_app or 0, c.dist_m))
        )
        if self.reference is None or any(c.d_app is None for c in ranked):
            return Decision(reason="NO_APPEARANCE_REF", options=ranked)
        if not cfg.tau_app or cfg.margin_app is None:
            return Decision(reason="APPEARANCE_NOT_SEPARABLE", options=ranked)
        passed = [c for c in ranked if c.d_app <= cfg.tau_app]
        if not passed:
            return Decision(rejected=True)
        if len(passed) > 1:
            return Decision(reason="MULTIPLE_PASS", options=ranked)
        if len(ranked) > 1 and ranked[1].d_app - passed[0].d_app < cfg.margin_app:
            return Decision(reason="LOW_MARGIN", options=ranked)
        return Decision(candidate=passed[0], mode="appearance")
