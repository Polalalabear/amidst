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
from dataclasses import replace
from pathlib import Path

from PIL import Image
from replay_relock import inventory_file, observation_records, read_sources, score_replays

from amidst.live_mode.advisor import Advisor, LiveDecider
from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.relock import RelockConfig
from amidst.live_mode.tracker import Projector, Tracker, load_cameras

REPO = Path(__file__).resolve().parents[2]
SAME = 1.5


class OracleAdvisor(Advisor):
    """Answers with the candidate that stands where the target truly is (evaluation only), ``delay_s`` later."""

    def __init__(self, people: PeopleTracker, delay_s: float, oracle_m: float = SAME):
        self.now = 0.0
        super().__init__(provider=None, clock=lambda: self.now, run_async=False, timeout_s=5.0)
        self.people, self.delay_s, self.truth, self.oracle_m = people, delay_s, None, oracle_m
        self.ready: dict | None = None

    def ask(self, kind, cam, pids, frame):
        if self.reference is None or self._pending is not None or self.clock() - self._last_end < self.min_interval_s:
            return False
        self._pending = {"seq": 0, "t0": self.clock(), "kind": kind, "cam": cam, "pids": list(pids)}
        self.calls += 1
        d = [math.dist(self.people.tracks[p]["xy"], self.truth) if self.truth else 1e9 for p in pids]
        best = min(range(len(pids)), key=lambda i: d[i])
        self.ready = {"choice": best + 1 if d[best] <= self.oracle_m else 0}
        return True

    def poll(self):
        p = self._pending
        if p is None or self.clock() - p["t0"] < self.delay_s:
            return None
        self._pending, self._last_end = None, self.clock()
        return {"kind": p["kind"], "cam": p["cam"], "pids": p["pids"], "latency_ms": round((self.clock() - p["t0"]) * 1000),
                "choice": self.ready["choice"], "reason": "重播：依劇本位置作答", "model": "oracle", "source": "AGENT", "fallback_reason": None}


class PoolRecorder(OracleAdvisor):
    """Run the advisor's timing without using scoring positions to change tracking."""

    def __init__(self, people, delay_s):
        super().__init__(people, delay_s)
        self.tick = 0
        self.questions = []

    def ask(self, kind, cam, pids, frame):
        if not super().ask(kind, cam, pids, frame):
            return False
        self.questions.append({
            "tick": self.tick, "t_capture_s": self.now, "kind": kind, "cam": cam,
            "pool_xy": [list(self.people.tracks[pid]["xy"]) for pid in pids],
        })
        return True


def replay_pools(records, size, cameras, projector, mode, gate_m, config, delay_s, lost_min, apply):
    tracker = Tracker(projector, gate_m=gate_m, relock=config)
    people = PeopleTracker()
    advisor = PoolRecorder(people, delay_s)
    decider = LiveDecider(mode, advisor, people, gate_m=gate_m, lost_min_candidates=lost_min, apply=apply,
                          predict_horizon_s=(config.pred_horizon_s or 0.0) if config.predict else 0.0)
    frames = {cam: Image.new("RGB", size, (128, 128, 128)) for cam in cameras}
    steps = []
    for i, row in enumerate(records):
        t = row["t_capture_ms"] / 1000
        detections = copy.deepcopy(row["dets"])
        tracking = tracker.update(i, detections, size, t)
        advisor.tick, advisor.now = i, t
        tracking = decider.step(i, t, tracker, tracking, detections, frames)
        steps.append({"tracking": tracking, "dets": detections, "schedule": None})
    return steps, advisor.questions


def score_questions(entries, traces, questions, oracle_m):
    results = []
    for (label, source, recording), trace, asks in zip(entries, traces, questions, strict=True):
        for ask in asks:
            i = ask["tick"]
            truth = recording["infer"][i].get("gt_xy")
            visible = bool(recording["ticks"][i].get("gt_visible"))
            if truth is None:
                pool_miss, oracle_choice = None, None
            else:
                all_candidates = [d["est_xy"] for rows in trace[i]["dets"].values() for d in rows
                                  if d.get("color") == "red" and d.get("est_xy") is not None]
                eligible = visible and any(math.dist(truth, xy) <= SAME for xy in all_candidates)
                pool_dist = [math.dist(truth, xy) for xy in ask["pool_xy"]]
                best = min(range(len(pool_dist)), key=pool_dist.__getitem__)
                pool_miss = eligible and min(pool_dist) > SAME
                oracle_choice = best + 1 if pool_dist[best] <= oracle_m else 0
            results.append({
                "session": recording.get("session_id") or label, "source": source.name,
                "source_tick": recording["ticks"][i].get("tick", i),
                **ask, "pool_miss": pool_miss, "evaluation_oracle_choice": oracle_choice,
            })
    return results


def predict_sweep(args):
    if args.mode == "off":
        raise ValueError("PREDICTION_SWEEP_REQUIRES_ADVISOR")
    entries = read_sources([f"primary={args.src}", *args.additional_in])
    if not entries:
        raise ValueError("PREDICTION_SWEEP_REQUIRES_RECORDINGS")
    projector = Projector(load_cameras(str(args.cameras) if args.cameras else None))
    root = Path(args.out)
    root.mkdir(parents=True)
    cfg = RelockConfig()
    if args.relock_receipt:
        cfg = RelockConfig(**json.loads(args.relock_receipt.read_text())["config"])
    results = {}
    for horizon in args.predict_horizon:
        config = replace(cfg, predict=horizon > 0, pred_horizon_s=horizon)
        pairs = [
            replay_pools(observation_records(raw), (raw["cfg"]["w"], raw["cfg"]["h"]), raw["cfg"]["cams"],
                         projector, args.mode, args.gate_m, config, args.delay_s, args.lost_min_candidates, args.apply)
            for _, _, raw in entries
        ]
        traces, asked = zip(*pairs, strict=True)
        rows, _ = score_replays(entries, traces, root / f"horizon-{horizon:g}")
        receipts = score_questions(entries, traces, asked, args.oracle_m)
        visible_rows = [r for values in rows.values() for r in values
                        if r["status"] in ("ON_TARGET", "WRONG_PERSON", "LOST")]
        wrong = sum(r["status"] == "WRONG_PERSON" for r in visible_rows)
        missed = [r for r in receipts if r["pool_miss"]]
        wrong_relocks = sum(
            row["following"] not in (None, "T") and "REACQUIRE" in row["events"]
            for recording_rows in rows.values() for row in recording_rows
        )
        results[horizon] = {
            "questions": len(receipts), "unknown_questions": sum(r["pool_miss"] is None for r in receipts),
            "pool_misses": len(missed), "pool_miss_rate": len(missed) / len(receipts) if receipts else None,
            "wrong_ticks": wrong, "visible_ticks": len(visible_rows),
            "wrong_rate": wrong / len(visible_rows) if visible_rows else None,
            "wrong_relocks": wrong_relocks,
            "max_pool_size": max((len(r["pool_xy"]) for r in receipts), default=0),
        }
        if horizon == 0:
            (root / "pool-misses.json").write_text(json.dumps({"n": len(missed), "questions": missed}, indent=2) + "\n")
    baseline = results[0.0]
    sample_ok = baseline["questions"] >= 20 and baseline["pool_misses"] >= 3
    qualified = [
        (row["pool_miss_rate"], horizon) for horizon, row in results.items()
        if horizon > 0 and row["pool_miss_rate"] is not None
        and row["pool_miss_rate"] < baseline["pool_miss_rate"]
        and row["wrong_rate"] is not None and baseline["wrong_rate"] is not None
        and row["wrong_rate"] <= baseline["wrong_rate"] and row["wrong_relocks"] == 0
        and row["max_pool_size"] <= 4
    ] if sample_ok else []
    report = {
        "n_inputs": len(entries),
        "inputs": [inventory_file(path, label=label) for label, path, _ in entries],
        "relock_receipt": inventory_file(args.relock_receipt) if args.relock_receipt else None,
        "calibration": inventory_file(args.cameras) if args.cameras else None,
        "gt_used_only_after_observation_replay": True, "provider_calls": 0, "cost_usd": 0.0,
        "answer_mode": "NO_PICK_DURING_REPLAY_ORACLE_SCORED_AFTERWARD", "oracle_m": args.oracle_m,
        "horizons": results, "qualified_sample_size": sample_ok,
        "proposed_horizon_s": min(qualified)[1] if qualified else None,
    }
    (root / "prediction.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("n_inputs", "qualified_sample_size", "horizons")}))
    return 0


def replay(raw: dict, mode: str, delay_s: float, lost_min: int, apply: str = "reseed", contest_m: float = 0.7, gate_m: float = 3.0,
           gate_growth: float = 0.0, max_gate: float = 8.0, oracle_m: float = SAME) -> dict:
    proj = Projector(load_cameras())
    tracker = Tracker(proj, gate_m=gate_m, gate_growth_m_s=gate_growth, max_gate_m=max_gate)
    people = PeopleTracker(contest_m=contest_m)
    adv = OracleAdvisor(people, delay_s, oracle_m)
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
    out["replay"] = {"mode": mode, "delay_s": delay_s, "lost_min_candidates": lost_min, "oracle_m": oracle_m, "questions": adv.calls,
                     "people_stats": dict(people.stats),
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
    ap.add_argument("--oracle-m", type=float, default=SAME, help="the stand-in answers 0 unless the nearest candidate is within this many metres of the true position "
                    "(1.5 reproduces the numbers before 2026-11-17; with people walking 1.3 m apart it names a bystander as the target)")
    ap.add_argument("--tag", default="", help="suffix for the output label")
    ap.add_argument("--only", default="", help="keep source labels containing this text (e.g. _off_)")
    ap.add_argument("--predict-horizon", type=lambda s: tuple(float(v) for v in s.split(",")),
                    help="score the offline shortlist at the given horizons, including 0")
    ap.add_argument("--additional-in", action="append", default=[], help="label=other recording directory")
    ap.add_argument("--cameras", type=Path, help="camera catalog for the prediction sweep")
    ap.add_argument("--relock-receipt", type=Path, help="source-bound config from replay_relock.py")
    a = ap.parse_args()
    if a.predict_horizon is not None:
        if (0 not in a.predict_horizon or len(set(a.predict_horizon)) != len(a.predict_horizon)
                or any(not math.isfinite(h) or h < 0 for h in a.predict_horizon)):
            ap.error("--predict-horizon requires 0 and nonnegative finite horizons")
        return predict_sweep(a)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(a.src).glob("*.t1raw.json")):
        raw = json.loads(f.read_text())
        if a.only and a.only not in raw["label"]:
            continue
        route, rep = raw["label"].split("_")[0], raw["label"].split("_")[-1]
        src_mode = "".join(raw["label"].split("_")[1:-1])
        res = replay(raw, a.mode, a.delay_s, a.lost_min_candidates, a.apply, a.contest_m, a.gate_m, a.gate_growth, a.max_gate, a.oracle_m)
        res["label"] = f"{route}_{a.mode}{a.tag}_from{src_mode}_{rep}"
        (Path(a.out) / f"{res['label']}.t1raw.json").write_text(json.dumps(res))
        print(res["label"], "questions", res["replay"]["questions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
