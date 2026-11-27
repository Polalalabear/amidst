#!/usr/bin/env python3
"""R-N inference-only offline replay. No GT, scenario plan, scoring or model imports."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from amidst.live_mode.aopen.neutral import NeutralTracker  # noqa: E402
from amidst.live_mode.tracker import Projector, load_cameras  # noqa: E402


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ask_kind(tick, last, lost):
    if last is None:
        return "FIRST"
    if lost and tick - last >= 5:
        return "LOST_EARLY"
    if tick - last >= 10:
        return "POLL"
    return None


class RuleNeutral:
    def __init__(self, projector, seed_tick, seed_xy, duration_s, no_candidate):
        if no_candidate not in ("UNCERTAIN", "NOT_VISIBLE"):
            raise ValueError("BAD_NO_CANDIDATE")
        self.neutral = NeutralTracker(projector)
        self.seed_tick, self.last_xy, self.last_xy_tick = seed_tick, list(seed_xy), seed_tick
        self.cap = math.ceil(duration_s / 2 * 1.5)
        self.no_candidate, self.calls, self.last_ask, self.pending = no_candidate, [], None, None

    def step(self, tick, dets):
        before = self.neutral.tracking()
        self.neutral.step(tick, self.neutral.target, dets)
        action = None
        if self.pending is not None:
            action = self.pending
            self.pending = None
            if action["answer"] == "SELECT":
                self.neutral.adopt(tick, action["camera_id"], action["selected_box"], "RULE")
                action["applied"] = True
            elif action["answer"] == "NOT_VISIBLE":
                self.neutral.clear()
                action["applied"] = True
            action.update(applied_tick=tick, pending_at_end=False)
        tr = self.neutral.tracking()
        if tr["est_xy"] is not None and self.neutral.status == "FOLLOWING":
            self.last_xy, self.last_xy_tick = list(tr["est_xy"]), tick
        kind = (
            ask_kind(tick, self.last_ask, tr["state"] == "LOST") if tick >= self.seed_tick else None
        )
        if kind and len(self.calls) < self.cap:
            candidates = []
            for cam, ds in dets.items():
                for i, d in enumerate(ds, 1):
                    box = d["bbox"]
                    xy = self.neutral.projector.ground(cam, (box[0] + box[2]) / 2, box[3], 320, 180)
                    finite = xy is not None and len(xy) == 2 and all(math.isfinite(v) for v in xy)
                    distance = math.dist(xy, self.last_xy) if finite else None
                    reasons = [] if d.get("color") == "red" else ["NOT_RED"]
                    if not finite:
                        reasons.append("NO_GROUND_POINT")
                    elif distance > 4.0:
                        reasons.append("DISTANCE_GT_4M")
                    candidates.append(
                        {
                            "camera_id": cam,
                            "detection_id": f"D{i}",
                            "box": list(box),
                            "score": d["score"],
                            "color": d.get("color"),
                            "est_xy": list(xy) if finite else None,
                            "distance_m": distance,
                            "eligible": not reasons,
                            "reasons": reasons,
                        }
                    )
            best = min(
                (c for c in candidates if c["eligible"]),
                key=lambda c: c["distance_m"],
                default=None,
            )
            rec = {
                "ask_tick": tick,
                "kind": kind,
                "own_state": copy.deepcopy(tr),
                "last_known_xy": list(self.last_xy),
                "last_known_tick": self.last_xy_tick,
                "candidate_list": candidates,
                "answer": "SELECT" if best else self.no_candidate,
                "camera_id": best["camera_id"] if best else None,
                "detection_id": best["detection_id"] if best else None,
                "selected_box": best["box"] if best else None,
                "accepted": True,
                "applied": False,
                "applied_tick": None,
                "pending_at_end": True,
            }
            self.calls.append(rec)
            self.pending, self.last_ask = rec, tick
        return {
            "tick": tick,
            "tracking": copy.deepcopy(tr),
            "ranking": [],
            "neutral_status": self.neutral.status,
            "decision_source": "RULE" if action else "NEUTRAL",
            "before": before,
            "tracker_action": action["answer"] if action else self.neutral.status,
        }


def observations(root, cid, source_hashes):
    """Independent loader; RGB only for the frozen live HSV calculation, never new detections."""
    import numpy as np
    from PIL import Image

    from amidst.live_mode.color import judge

    def read(path, expected=None):
        raw = path.read_bytes()
        h = digest(raw)
        if expected is not None and h != expected:
            raise ValueError("OBSERVATION_PIN_MISMATCH")
        source_hashes[str(path.relative_to(root))] = h
        return raw

    index_path = root / "indexes" / cid / "detection_index.json"
    index = json.loads(read(index_path))
    raw = read(index_path.parent / index["records_ref"], index["records_file_sha256"])
    rgb = json.loads(read(root / "rgb" / cid / "rgb_index.json", index["rgb_index_sha256"]))
    frames = {(r["camera_id"], r["frame_index"]): r for r in rgb["records"]}
    grouped = {}
    for row in map(json.loads, raw.splitlines()):
        grouped.setdefault(row["frame_index"], []).append(row)
    for tick, rows in sorted(grouped.items()):
        dets = {}
        for row in rows:  # frozen capture/index order; verified sorted camera order on this corpus
            cam = row["camera_id"]
            dets[cam] = []
            ds = [
                d
                for d in row["detections"]
                if d["class_label"] == "person"
                and d["score"] >= (0.05 if cam == "CAM_ENTRY" else 0.15)
            ]
            if not ds:
                continue
            path = root / frames[cam, tick]["relative_path"]
            read(path, row["rgb_file_sha256"])
            with Image.open(path) as image:
                if image.size != (320, 180):
                    raise ValueError("FRAME_SIZE")
                arr = np.asarray(image.convert("RGB"))
            dets[cam] = [
                {
                    "bbox": list(d["bbox_xyxy_px"]),
                    "score": d["score"],
                    **judge(arr, d["bbox_xyxy_px"], weak=0.2),
                }
                for d in ds
            ]
        yield tick, dets


def seed_from_b1(path):
    """Only first ACQUIRE/time/position may cross this bridge; no selected box is returned."""
    b1 = json.loads(path.read_text())
    seed = next(r for r in b1["rows"] if any(e["type"] == "ACQUIRE" for e in r["events"]))
    return {
        "tick": seed["tick"],
        "xy": seed["tracking"]["est_xy"],
        "duration_s": len(b1["rows"]) / 5,
        "b1_sha256": digest(path.read_bytes()),
        "camera_catalog_sha256": b1["camera_catalog_sha256"],
    }


def replay_case(projector, cameras, root, b1_runs, cid, out):
    """One case: seed from its B1 run, replay RN_U and RN_N on the frozen detections, write ``<out>/<cid>/<arm>.json``."""
    seed = seed_from_b1(b1_runs / cid / "B1.k1.json")
    if digest(cameras.read_bytes()) != seed["camera_catalog_sha256"]:
        raise ValueError("CALIBRATION_PIN")
    versions = {
        arm: RuleNeutral(projector, seed["tick"], seed["xy"], seed["duration_s"], answer)
        for arm, answer in [("RN_U", "UNCERTAIN"), ("RN_N", "NOT_VISIBLE")]
    }
    rows, hashes = {arm: [] for arm in versions}, {}
    for tick, dets in observations(root, cid, hashes):
        for arm, decider in versions.items():
            rows[arm].append(decider.step(tick, dets))
    for arm, decider in versions.items():
        target = out / cid / f"{arm}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "schema": "e6-rn.v1",
                    "case_id": cid,
                    "arm": arm,
                    "k": 1,
                    "tick_us": 200_000,
                    "size": [320, 180],
                    "seed": seed,
                    "identity": "UNCONFIRMED",
                    "paid_calls": 0,
                    "call_cap": decider.cap,
                    "calls": decider.calls,
                    "rows": rows[arm],
                    "sources": hashes,
                    "code_sha256": digest(Path(__file__).read_bytes()),
                    "protocol_sha256": digest(
                        (ROOT / "docs/evaluation/E6_RN_FROZEN_20261124.md").read_bytes()
                    ),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        print(cid, arm, len(rows[arm]), len(decider.calls), flush=True)


def jobs_for(a):
    """(root, B1 runs dir, case ids). Old layout (``--evidence``): the two E3 corpora, every ``E3-*`` case, as before.
    New layout (``--root`` + ``--b1-runs``): one root, ``--cases`` or every case dir under ``indexes/`` (E6 formal recording)."""
    if a.evidence is not None:
        out = []
        for corpus, folder in [
            ("e3-652-20261122", "runs-final-9"),
            ("e3-reappearances-20261122", "runs-final-665"),
        ]:
            root = a.evidence / corpus
            cases = [i.parent.name for i in sorted((root / "indexes").glob("E3-*/detection_index.json"))]
            out.append((root, a.evidence / "f4-658-20261122" / folder, cases))
        return out
    cases = list(a.cases) if a.cases else sorted(i.parent.name for i in (a.root / "indexes").glob("*/detection_index.json"))
    if not cases:
        raise ValueError("NO_CASES")
    return [(a.root, a.b1_runs, cases)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, help="old layout: local/evidence with the two E3 corpora and f4-658 B1 runs")
    p.add_argument("--root", type=Path, help="one recording root (indexes/, rgb/), e.g. local/evidence/e6-formal-20261127")
    p.add_argument("--b1-runs", type=Path, help="with --root: folder holding <case>/B1.k1.json (B1 run on that recording; seed only)")
    p.add_argument("--cases", nargs="+", help="with --root: case ids (default: every case under indexes/)")
    p.add_argument("--cameras", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    if (a.evidence is None) == (a.root is None) or (a.root is not None and a.b1_runs is None) or (a.evidence is not None and (a.b1_runs or a.cases)):
        p.error("use either --evidence, or --root with --b1-runs (and optionally --cases)")
    if a.out.exists():
        raise ValueError("OUTPUT_EXISTS")
    projector = Projector(load_cameras(str(a.cameras)))
    for root, b1_runs, cases in jobs_for(a):
        for cid in cases:
            replay_case(projector, a.cameras, root, b1_runs, cid, a.out)


if __name__ == "__main__":
    main()
