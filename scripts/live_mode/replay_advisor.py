"""Offline replay of recorded live runs through the rule tracker and the live decider. No model, no network, no cost.

EVALUATION ONLY. The stand-in for the vision model below uses the recorded true position of the target to pick the
right candidate (or 0), after a fixed delay. It answers "what would tracking look like if the model were right, as
it was on 38 of 38 two-candidate questions in the live runs", and it exercises the decider's own logic (track ids,
late answers, holds) on real detection streams. It must never be imported by the live backend.

Input: *.t1raw.json from frontend/live-mode/measure/t1_record.mjs (detections per tick are independent of how the
run was tracked). Output: the same file shape with the replayed tracking, so measure/t1_analyze.mjs can score it.

    python scripts/live_mode/replay_advisor.py --in <dir> --out <dir> --mode off|review|lead [--delay-s 3.5]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from PIL import Image

from amidst.live_mode.advisor import Advisor, LiveDecider
from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.tracker import Projector, Tracker

REPO = Path(__file__).resolve().parents[2]
GEOMETRY = REPO / "docs" / "evaluation" / "R004_SCENE_GEOMETRY_2D_V1.json"
SAME = 1.5


class OracleAdvisor(Advisor):
    """Answers with the candidate that stands where the target truly is (evaluation only), ``delay_s`` later."""

    def __init__(self, people: PeopleTracker, delay_s: float):
        self.now = 0.0
        super().__init__(provider=None, clock=lambda: self.now, run_async=False, timeout_s=5.0)
        self.people, self.delay_s, self.truth = people, delay_s, None
        self.ready: dict | None = None

    def ask(self, kind, cam, pids, frame):
        if self.reference is None or self._pending is not None or self.clock() - self._last_end < self.min_interval_s:
            return False
        self._pending = {"seq": 0, "t0": self.clock(), "kind": kind, "cam": cam, "pids": list(pids)}
        self.calls += 1
        d = [math.dist(self.people.tracks[p]["xy"], self.truth) if self.truth else 1e9 for p in pids]
        best = min(range(len(pids)), key=lambda i: d[i])
        self.ready = {"choice": best + 1 if d[best] <= SAME else 0}
        return True

    def poll(self):
        p = self._pending
        if p is None or self.clock() - p["t0"] < self.delay_s:
            return None
        self._pending, self._last_end = None, self.clock()
        return {"kind": p["kind"], "cam": p["cam"], "pids": p["pids"], "latency_ms": round((self.clock() - p["t0"]) * 1000),
                "choice": self.ready["choice"], "reason": "重播：依劇本位置作答", "model": "oracle", "source": "AGENT", "fallback_reason": None}


def replay(raw: dict, mode: str, delay_s: float, lost_min: int, apply: str = "reseed", contest_m: float = 0.7, gate_m: float = 3.0,
           gate_growth: float = 0.0, max_gate: float = 8.0) -> dict:
    proj = Projector(json.loads(GEOMETRY.read_text())["cameras"])
    tracker = Tracker(proj, gate_m=gate_m, gate_growth_m_s=gate_growth, max_gate_m=max_gate)
    people = PeopleTracker(contest_m=contest_m)
    adv = OracleAdvisor(people, delay_s)
    dec = LiveDecider(mode, adv, people, gate_m=gate_m, lost_min_candidates=lost_min, apply=apply) if mode != "off" else None
    frames = {c: Image.new("RGB", (raw["cfg"]["w"], raw["cfg"]["h"]), (128, 128, 128)) for c in raw["cfg"]["cams"]}
    out = copy.deepcopy(raw)
    n = min(len(raw["ticks"]), len(raw["infer"]))
    for i in range(n):
        dets = {cam: [{k: v for k, v in d.items() if k != "est_xy"} for d in lst] for cam, lst in raw["infer"][i]["dets"].items()}
        t_s = raw["ticks"][i]["t_capture"] / 1000.0
        size = (raw["cfg"]["w"], raw["cfg"]["h"])
        tracking = tracker.update(i, dets, size, t_s)
        if dec is not None:
            adv.now, adv.truth = t_s, raw["infer"][i].get("gt_xy")
            tracking = dec.step(i, t_s, tracker, tracking, dets, frames)
        out["infer"][i]["dets"], out["infer"][i]["tracking"] = dets, tracking
    out["label"] = raw["label"]
    out["replay"] = {"mode": mode, "delay_s": delay_s, "lost_min_candidates": lost_min, "questions": adv.calls,
                     "note": "evaluation-only oracle answers; not a model result"}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", required=True, choices=["off", "review", "lead"])
    ap.add_argument("--delay-s", type=float, default=3.5)
    ap.add_argument("--lost-min-candidates", type=int, default=2)
    ap.add_argument("--apply", default="reseed", choices=["lock", "reseed"])
    ap.add_argument("--gate-m", type=float, default=3.0)
    ap.add_argument("--gate-growth", type=float, default=0.0, help="metres per second the rule gate widens while the target is unseen")
    ap.add_argument("--max-gate", type=float, default=8.0)
    ap.add_argument("--contest-m", type=float, default=0.7, help="0 switches the close-pass check off")
    ap.add_argument("--tag", default="", help="suffix for the output label")
    ap.add_argument("--only", default="", help="keep source labels containing this text (e.g. _off_)")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(a.src).glob("*.t1raw.json")):
        raw = json.loads(f.read_text())
        if a.only and a.only not in raw["label"]:
            continue
        route, rep = raw["label"].split("_")[0], raw["label"].split("_")[-1]
        src_mode = "".join(raw["label"].split("_")[1:-1])
        res = replay(raw, a.mode, a.delay_s, a.lost_min_candidates, a.apply, a.contest_m, a.gate_m, a.gate_growth, a.max_gate)
        res["label"] = f"{route}_{a.mode}{a.tag}_from{src_mode}_{rep}"
        (Path(a.out) / f"{res['label']}.t1raw.json").write_text(json.dumps(res))
        print(res["label"], "questions", res["replay"]["questions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
