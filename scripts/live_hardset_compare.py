"""#597 LIVE hard-case comparison scorer: rules only vs LLM review (terra / sol) on the same scripted case.

Offline only. Reads the A logs (GT: actor xy and gt_visible, evaluation only) and B logs (tracking output, decision events)
written by ``frontend/live-mode/measure/hardset_compare.mjs``. Nothing here is an input to inference, ranking or prompts.

File names in the input directory: ``<case>.<mode>.<rep>.a-log.json`` / ``.b-log.json`` / optional ``.meta.json``,
mode in rule | terra | sol, rep = 1..K. The target is always the scripted player ``T`` (docs/evaluation/LIVE_HARDSET_V1.md §3).

Runs of different modes are aligned by simulation time ``t_sim`` (the capture ticks are wall-clock driven and differ),
and every rate is time-weighted (seconds), not a tick count. Per-tick classes follow scripts/live_ab_score.py classify()
with one difference required by the relock contract: NEEDS_CONFIRM counts as lost (RELOCK §2.1), where live_ab_score
reports it as UNKNOWN.

Known gaps (kept UNKNOWN, never filled in): the candidate pool and the rule's choice at a decision point are not in the B
log (LIVE_HARDSET §6.6 / #596 Q6), so the decision table can show the count of candidates, whether T was visible, and
what each mode did, but not whether T was in the pool.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

MODES = ("rule", "terra", "sol")
TARGET = "T"
MATCH_M = 1.5
GAP_CAP_S = 1.0          # a tick never stands for more than this many seconds (missing ticks are not counted as time)
WINDOWS = (2.0, 5.0, 10.0)
AFTER_S = 10.0
BETTER = 0.05
REPLAY_TOL_M = 0.05
FILE_RE = re.compile(r"^(?P<case>[A-Za-z0-9-]+)\.(?P<mode>rule|terra|sol)\.(?P<rep>\d+)\.a-log\.json$")
UNTRACKED_STATES = ("IDLE", "ACQUIRING", "SEARCHING", "NEEDS_PICK")
LOST_STATES = ("LOST", "TARGET_OUT_OF_VIEW", "NEEDS_CONFIRM")
TRACK_STATES = ("TRACKING", "ADJUDICATING")


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def point(v):
    return isinstance(v, list) and len(v) == 2 and all(finite(x) for x in v)


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    i = (len(s) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


# ---------------------------------------------------------------------------------------------------------------------
# one run
# ---------------------------------------------------------------------------------------------------------------------
def actor_map(a_row):
    return {a["id"]: a for a in a_row.get("actors", []) if isinstance(a, dict) and isinstance(a.get("id"), str)}


def nearest_actor(xy, actors, exclude=()):
    """The present actor within MATCH_M of xy, else None. Evaluation label only."""
    best = None
    for name, a in actors.items():
        if name in exclude or not a.get("present") or not point(a.get("xy")):
            continue
        d = math.dist(xy, a["xy"])
        if d <= MATCH_M and (best is None or d < best[0]):
            best = (d, name)
    return best[1] if best else None


def classify(tr, actors):
    """-> (status, detail). status in ON_TARGET WRONG_PERSON UNMATCHED LOST OUT_* UNKNOWN."""
    t = actors.get(TARGET)
    if t is None:
        return "UNKNOWN", "TARGET_GT_MISSING"
    visible = bool(t.get("present")) and isinstance(t.get("gt_visible"), list) and len(t["gt_visible"]) > 0
    if not isinstance(tr, dict):
        return "UNKNOWN", "TRACKING_MISSING"
    state = tr.get("state")
    if state in UNTRACKED_STATES:
        return "UNKNOWN", "NOT_TRACKING"
    if state not in TRACK_STATES + LOST_STATES:
        return "UNKNOWN", "TRACK_STATE_UNSUPPORTED"
    lost = state in LOST_STATES or (tr.get("lost_ticks") or 0) > 0 or not point(tr.get("est_xy"))
    if not visible:   # target not in any camera: not in the rates; what the system claimed is reported separately
        if lost:
            return "OUT_DECLARED_LOST", None
        near = nearest_actor(tr["est_xy"], actors)
        return ("OUT_WRONG_PERSON", near) if near else ("OUT_UNMATCHED", None)
    if lost:
        return "LOST", None
    if math.dist(tr["est_xy"], t["xy"]) <= MATCH_M:
        return "ON_TARGET", None
    near = nearest_actor(tr["est_xy"], actors, exclude=(TARGET,))
    return ("WRONG_PERSON", near) if near else ("UNMATCHED", None)


class Run:
    def __init__(self, case, mode, rep, a, b, meta=None):
        self.case, self.mode, self.rep, self.meta = case, mode, rep, meta or {}
        self.session = a.get("session_id")
        self.unknown = []
        if a.get("session_id") != b.get("session_id") or not a.get("session_id"):
            self.unknown.append("SESSION_MISMATCH")
        b_rows = {}
        for r in b.get("ticks", []):
            b_rows.setdefault(r.get("tick"), []).append(r)
        self.events = []        # B events: (tick, type, detail)
        self.rows = []
        for r in sorted((x for x in a.get("ticks", []) if finite(x.get("t_sim"))), key=lambda x: x["t_sim"]):
            br = b_rows.get(r.get("tick"), [])
            if len(br) != 1:
                continue
            br = br[0]
            for e in (br.get("tracking") or {}).get("events", []) or []:
                self.events.append((r["tick"], e.get("type"), e.get("detail") or {}, e.get("cam")))
            if not finite(r.get("t_capture")) or r["t_capture"] != br.get("t_capture"):
                continue    # clock mismatch: the tick is dropped, not scored
            actors = actor_map(r)
            status, detail = classify(br.get("tracking"), actors)
            tr = br.get("tracking") or {}
            t = actors.get(TARGET, {})
            self.rows.append({"tick": r["tick"], "t": r["t_sim"], "status": status, "detail": detail, "actors": actors,
                              "cam": tr.get("active_cam"), "est": tr.get("est_xy"), "state": tr.get("state"),
                              "vis": list(t.get("gt_visible") or []) if t.get("present") else [],
                              "src": tr.get("decision_source")})
        self.times = [x["t"] for x in self.rows]
        for i, row in enumerate(self.rows):
            nxt = self.times[i + 1] - row["t"] if i + 1 < len(self.rows) else None
            row["w"] = min(nxt, GAP_CAP_S) if nxt is not None else 0.0
        if self.rows:
            tail = [x["w"] for x in self.rows[:-1]]
            self.rows[-1]["w"] = statistics.median(tail) if tail else 0.0

    # -- time-weighted seconds by class --------------------------------------------------------------------------
    def seconds(self, t0=-math.inf, t1=math.inf):
        c = Counter()
        for r in self.rows:
            if t0 <= r["t"] < t1:
                c[r["status"]] += r["w"]
        return c

    def rate(self, t0=-math.inf, t1=math.inf):
        c = self.seconds(t0, t1)
        n = sum(c[k] for k in ("ON_TARGET", "WRONG_PERSON", "UNMATCHED", "LOST"))
        return None if n <= 0 else c["ON_TARGET"] / n

    def at(self, t):
        """The last row at or before t (None before the first row)."""
        i = bisect.bisect_right(self.times, t) - 1
        return self.rows[i] if i >= 0 else None

    # -- episodes where the system lost a visible target ------------------------------------------------------------
    def reacquire(self):
        """[{t_ref, s, found}]: t_ref = start of the visible stretch in which the loss was noticed; s = seconds to the next ON_TARGET."""
        out, was_on, open_ep, last_vis = [], False, None, False
        for r in self.rows:
            s = r["status"]
            if s == "UNKNOWN":
                continue
            vis = s in ("ON_TARGET", "WRONG_PERSON", "UNMATCHED", "LOST")
            if vis and not last_vis and open_ep is not None:
                open_ep["t_ref"] = r["t"]           # target visible again after a gap: measure from here
            if s == "ON_TARGET":
                if open_ep is not None:
                    open_ep["s"], open_ep["found"] = r["t"] - open_ep["t_ref"], True
                    out.append(open_ep)
                    open_ep = None
                was_on = True
            elif vis and was_on and open_ep is None:
                open_ep = {"t_ref": r["t"], "s": None, "found": False}
            last_vis = vis
        if open_ep is not None:
            open_ep["s"] = (self.rows[-1]["t"] - open_ep["t_ref"]) if self.rows else 0.0
            out.append(open_ep)
        return out

    def wrong_episodes(self, status="WRONG_PERSON", minimum=2):
        n, count = 0, 0
        for r in self.rows:
            if r["status"] == status:
                n += 1
                count += n == minimum
            elif r["status"] != "UNKNOWN":
                n = 0
        return count

    # -- B decision events ---------------------------------------------------------------------------------------------
    def decisions(self):
        """[{ask_tick, ask_t, kind, cands, answer_tick, answer_t, choice, applied, cleared, source, latency_ms, fallback}]"""
        by_tick = {r["tick"]: r for r in self.rows}
        out, pending = [], None
        for tick, typ, det, cam in self.events:
            if typ == "ADJUDICATE_ASK":
                pending = {"ask_tick": tick, "kind": det.get("kind"), "cands": det.get("candidates"), "cam": cam}
            elif typ == "ADJUDICATED":
                d = {"ask_tick": None, "kind": None, "cands": None, "cam": cam}
                if pending is not None:
                    d.update(pending)
                    pending = None
                d.update(answer_tick=tick, choice=det.get("choice"), applied=bool(det.get("applied")), cleared=bool(det.get("cleared")),
                         source=det.get("source"), latency_ms=det.get("latency_ms"))
                out.append(d)
        for d in out:
            ra = by_tick.get(d["ask_tick"]) if d["ask_tick"] is not None else None
            rb = by_tick.get(d["answer_tick"])
            d["ask_t"] = ra["t"] if ra else (rb["t"] if rb else None)
            d["answer_t"] = rb["t"] if rb else None
            d["answer_row"] = rb
        return out


def decision_summary(run):
    ds = run.decisions()
    calls = sum(1 for t, typ, *_ in run.events if typ == "ADJUDICATE_ASK")
    lat = [d["latency_ms"] for d in ds if finite(d.get("latency_ms"))]
    return {"calls": calls, "answered": len(ds), "agent": sum(1 for d in ds if d["source"] == "AGENT"),
            "fallback": sum(1 for d in ds if d["source"] == "RULE_FALLBACK"),
            "applied": sum(1 for d in ds if d["applied"]), "cleared": sum(1 for d in ds if d["cleared"]),
            "p50_ms": percentile(lat, 0.5), "p95_ms": percentile(lat, 0.95)}


# ---------------------------------------------------------------------------------------------------------------------
# hand-off points (GT defined, taken from the reference run) and verdicts
# ---------------------------------------------------------------------------------------------------------------------
def handoff_points(ref: Run):
    """Moments the target leaves the camera the reference run was following while it was on target (docs §3.4 / guide §3.4).

    Returns [{t_x, t_n}]; t_n = first moment at or after t_x when T is visible in any camera (None when it never returns)."""
    pts, armed = [], False
    for i, r in enumerate(ref.rows):
        if r["status"] == "UNKNOWN":
            continue
        following = r["status"] == "ON_TARGET" and r["cam"] in r["vis"]
        if following:
            armed = True
            continue
        prev = next((q for q in reversed(ref.rows[:i]) if q["status"] != "UNKNOWN"), None)
        if armed and prev is not None and prev["status"] == "ON_TARGET" and prev["cam"] and prev["cam"] not in r["vis"]:
            t_n = next((q["t"] for q in ref.rows[i:] if q["vis"]), None)
            if t_n is not None:
                pts.append({"t_x": r["t"], "t_n": t_n})
            armed = False
    return pts


def handoff_verdict(run: Run, pt, window):
    """接對 / 接錯 / 沒接上 plus the delay (s) of the first ON_TARGET tick on the camera that sees T (docs §3.4)."""
    t_n = pt["t_n"]
    wrong_run, wrong_flag, first_on = 0, False, None
    for r in run.rows:
        if r["t"] < t_n:
            continue
        s = r["status"]
        if s == "UNKNOWN":
            continue
        if s == "ON_TARGET" and r["cam"] in r["vis"]:
            first_on = r["t"]
            break
        if s in ("WRONG_PERSON", "UNMATCHED"):
            wrong_run += 1
            if wrong_run >= 2 and r["t"] < t_n + window:
                wrong_flag = True
        else:
            wrong_run = 0
    in_window = first_on is not None and first_on < t_n + window
    if in_window and not wrong_flag:
        verdict = "接對"
    elif wrong_flag:
        verdict = "接錯"
    else:
        verdict = "沒接上"
    return {"verdict": verdict, "delay_s": None if first_on is None else first_on - t_n, "late": first_on is not None and not in_window}


# ---------------------------------------------------------------------------------------------------------------------
# replay consistency (guide §3.1): same script -> same actor positions at the same t_sim
# ---------------------------------------------------------------------------------------------------------------------
def interp_xy(rows, ident, t):
    pts = [(r["t"], r["actors"][ident]["xy"]) for r in rows if ident in r["actors"] and r["actors"][ident].get("present") and point(r["actors"][ident].get("xy"))]
    if not pts:
        return None
    ts = [p[0] for p in pts]
    i = bisect.bisect_left(ts, t)
    if i == 0 or i == len(pts):
        return pts[0][1] if i == 0 and abs(ts[0] - t) < 0.3 else (pts[-1][1] if i == len(pts) and abs(ts[-1] - t) < 0.3 else None)
    (t0, p0), (t1, p1) = pts[i - 1], pts[i]
    if t1 - t0 > 1.5:
        return None
    k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return [p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k]


def replay_mismatch(ref: Run, other: Run, tol=REPLAY_TOL_M):
    worst = 0.0
    ids = sorted({i for r in ref.rows for i in r["actors"]})
    for r in other.rows[::2]:
        for ident in ids:
            a = interp_xy(ref.rows, ident, r["t"])
            b = r["actors"].get(ident)
            if a is None or not b or not b.get("present") or not point(b.get("xy")):
                continue
            worst = max(worst, math.dist(a, b["xy"]))
    return worst, worst > tol


# ---------------------------------------------------------------------------------------------------------------------
# loading and assembling
# ---------------------------------------------------------------------------------------------------------------------
def load_dir(path: Path):
    runs = {}
    for f in sorted(path.iterdir()):
        m = FILE_RE.match(f.name)
        if not m:
            continue
        case, mode, rep = m["case"], m["mode"], int(m["rep"])
        base = f.name[: -len(".a-log.json")]
        b_path = path / f"{base}.b-log.json"
        if not b_path.exists():
            continue
        meta_path = path / f"{base}.meta.json"
        meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
        runs[(case, mode, rep)] = Run(case, mode, rep, json.loads(f.read_text("utf-8")), json.loads(b_path.read_text("utf-8")), meta)
    return runs


def actor_of(row_or_none):
    if row_or_none is None:
        return "UNKNOWN"
    if row_or_none["status"] in ("LOST", "OUT_DECLARED_LOST"):
        return "失聯"
    if row_or_none["status"] == "UNKNOWN":
        return "UNKNOWN"
    if row_or_none["est"] is None:
        return "失聯"
    if row_or_none["status"] == "ON_TARGET":
        return TARGET
    return nearest_actor(row_or_none["est"], row_or_none["actors"]) or "UNMATCHED"


def case_family(case):
    return case[:2] if case[:1] == "H" else case


def score_case(case, by_mode, tol=REPLAY_TOL_M):
    """by_mode: {mode: [Run, ...]} -> dict for this case. rule must exist (it anchors hand-off points and the replay check)."""
    out = {"case": case, "status": "SCORED", "unknown": [], "modes": {}, "handoffs": [], "decisions": []}
    rule_runs = by_mode.get("rule") or []
    if not rule_runs:
        out.update(status="UNKNOWN", unknown=["RULE_RUN_MISSING"])
        return out
    ref = rule_runs[0]
    for mode, runs in by_mode.items():
        for r in runs:
            if r.unknown:
                out["unknown"] += [f"{mode}.{r.rep}:{u}" for u in r.unknown]
            if r is not ref:
                worst, bad = replay_mismatch(ref, r, tol)
                if bad:
                    out["unknown"].append(f"REPLAY_MISMATCH:{mode}.{r.rep}:{worst:.3f}m")
    if any("REPLAY_MISMATCH" in u or "SESSION_MISMATCH" in u for u in out["unknown"]):
        out["status"] = "NOT_COMPARED"
        return out
    pts = handoff_points(ref)
    out["handoff_points"] = pts
    for mode in MODES:
        for r in by_mode.get(mode, []):
            c = r.seconds()
            n = sum(c[k] for k in ("ON_TARGET", "WRONG_PERSON", "UNMATCHED", "LOST"))
            ds = decision_summary(r)
            ra = r.reacquire()
            found = [e["s"] for e in ra if e["found"]]
            hv = {w: [handoff_verdict(r, p, w) for p in pts] for w in WINDOWS}
            out["modes"].setdefault(mode, []).append({
                "rep": r.rep, "visible_s": n, "rate": c["ON_TARGET"] / n if n else None, "lost_s": c["LOST"],
                "wrong_s": c["WRONG_PERSON"], "unmatched_s": c["UNMATCHED"], "wrong_unseen_s": c["OUT_WRONG_PERSON"],
                "unmatched_unseen_s": c["OUT_UNMATCHED"], "declared_unseen_s": c["OUT_DECLARED_LOST"],
                "identity_switches": r.wrong_episodes(), "reacquire_found": found, "reacquire_missing": sum(1 for e in ra if not e["found"]),
                "reacquire_mean_s": statistics.fmean(found) if found else None, "reacquire_max_s": max(found) if found else None,
                "handoff": {str(w): [v["verdict"] for v in hv[w]] for w in WINDOWS}, "handoff_delay_s": [v["delay_s"] for v in hv[5.0]],
                "decision": ds, "meta": r.meta})
    out["decisions"] = decision_rows(case, by_mode)
    return out


def decision_rows(case, by_mode):
    """One row per LLM decision point; terra and sol of the same rep that are within 1 s of each other share a row."""
    rule = (by_mode.get("rule") or [None])[0]
    rows = []
    for rep in sorted({r.rep for m in ("terra", "sol") for r in by_mode.get(m, [])}):
        per = {}
        for m in ("terra", "sol"):
            run = next((r for r in by_mode.get(m, []) if r.rep == rep), None)
            per[m] = (run, [d for d in run.decisions() if d["answer_t"] is not None] if run else [])
        used = {"terra": set(), "sol": set()}
        raw = []
        for m, (run, ds) in per.items():
            for i, d in enumerate(ds):
                raw.append((d["ask_t"] if d["ask_t"] is not None else d["answer_t"], m, i, d))
        raw.sort(key=lambda x: x[0])
        for t, m, i, d in raw:
            if i in used[m]:
                continue
            used[m].add(i)
            other = "sol" if m == "terra" else "terra"
            pair = None
            for j, d2 in enumerate(per[other][1]):
                t2 = d2["ask_t"] if d2["ask_t"] is not None else d2["answer_t"]
                if j not in used[other] and abs(t2 - t) <= 1.0:
                    used[other].add(j)
                    pair = d2
                    break
            row = {"case": case, "rep": rep, "t": t, "only": None}
            sides = {m: d}
            if pair is not None:
                sides[other] = pair
            else:
                row["only"] = m
            rule_row = rule.at(t) if rule else None
            ref_run = per[m][0]
            at_ask = ref_run.at(t)
            vis = bool(at_ask and at_ask["vis"])
            row.update(tick=d["ask_tick"], cands=d["cands"], kind=d["kind"], t_visible=vis,
                       lost_s=_since_on(ref_run, t), rule=actor_of(rule_row),
                       correct="T" if vis else "都不是")
            for mm in ("terra", "sol"):
                dd = sides.get(mm)
                run = per[mm][0]
                row[mm] = llm_answer(dd, run) if dd else "—"
                row[mm + "_ok"] = _ok(row[mm], vis)
                row[mm + "_after"] = None if run is None or dd is None else run.rate(dd["answer_t"], dd["answer_t"] + AFTER_S)
            row["rule_ok"] = _ok(row["rule"], vis)
            row["rule_after"] = rule.rate(t, t + AFTER_S) if rule else None
            rows.append(row)
    return rows


def _since_on(run, t):
    last = None
    for r in run.rows:
        if r["t"] > t:
            break
        if r["status"] == "ON_TARGET":
            last = r["t"]
    return None if last is None else t - last


def llm_answer(d, run):
    if d["source"] != "AGENT":
        return "退回規則"
    if d["choice"] == 0:
        return "都不是"
    row = d.get("answer_row")
    return actor_of(row) if row else "UNKNOWN"


def _ok(answer, visible):
    if answer in ("—", "UNKNOWN", "退回規則"):
        return "—"
    if visible:
        return "✓" if answer == TARGET else "✗"
    return "✓" if answer in ("都不是", "失聯") else "✗"


# ---------------------------------------------------------------------------------------------------------------------
# better / same / worse (guide §4, definition written before looking at results)
# ---------------------------------------------------------------------------------------------------------------------
def compare_to_rule(case_score, mode):
    rule = case_score["modes"].get("rule") or []
    other = case_score["modes"].get(mode) or []
    if not rule or not other:
        return None
    rr = [x["rate"] for x in rule if x["rate"] is not None]
    oo = [x["rate"] for x in other if x["rate"] is not None]
    if not rr or not oo:
        return None
    d = statistics.median(oo) - statistics.median(rr)
    improved = degraded = 0
    verdicts_rule = rule[0]["handoff"]["5.0"]
    # K repetitions: a hand-off counts as changed only when the median repetition of the LLM mode agrees
    for i, v0 in enumerate(verdicts_rule):
        vs = [x["handoff"]["5.0"][i] for x in other if i < len(x["handoff"]["5.0"])]
        if not vs:
            continue
        good = sum(1 for v in vs if v == "接對") * 2 > len(vs)
        improved += v0 != "接對" and good
        degraded += v0 == "接對" and not good
    better = d >= BETTER or (improved > 0 and degraded == 0)
    worse = d <= -BETTER or (degraded > 0 and improved == 0)
    if better and worse:
        return "相同（互相抵消）"
    return "較好" if better else "較差" if worse else "相同"


# ---------------------------------------------------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------------------------------------------------
def f(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def rng(xs, nd=3):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "—"
    if len(xs) == 1 or min(xs) == max(xs):
        return f(statistics.median(xs), nd)
    return f"{statistics.median(xs):.{nd}f}（{min(xs):.{nd}f}–{max(xs):.{nd}f}）"


def render_markdown(scores, title="LIVE 難題集 規則 vs LLM 覆核"):
    L = [f"# {title}", ""]
    scored = [s for s in scores if s["status"] == "SCORED"]
    skipped = [s for s in scores if s["status"] != "SCORED"]
    L += ["## 逐案", "",
          "| 案例 | 組 | 次數 | 跟對率 | 失聯秒 | 錯人秒（可見／看不到） | 身分交換 | 找回秒 平均（未找回） | 切鏡 接對／接錯／沒接上（W=5 s） | LLM 呼叫 | 採用／退回 | 呼叫 p50／p95 ms | 花費 USD |",
          "| --- | --- | ---: | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | ---: |"]
    for s in scored:
        for mode in MODES:
            xs = s["modes"].get(mode)
            if not xs:
                continue
            hv = Counter(v for x in xs for v in x["handoff"]["5.0"])
            k = len(xs)
            cost = [x["meta"].get("cost_usd") for x in xs]
            cost_s = "—" if any(c is None for c in cost) else f"{sum(cost):.4f}"
            ds = [x["decision"] for x in xs]
            L.append(f"| {s['case']} | {mode} | {k} | {rng([x['rate'] for x in xs])} | {rng([x['lost_s'] for x in xs], 1)} | "
                     f"{rng([x['wrong_s'] for x in xs], 1)}／{rng([x['wrong_unseen_s'] for x in xs], 1)} | {rng([x['identity_switches'] for x in xs], 0)} | "
                     f"{rng([x['reacquire_mean_s'] for x in xs], 1)}（{sum(x['reacquire_missing'] for x in xs)}） | "
                     f"{hv['接對']}／{hv['接錯']}／{hv['沒接上']} | {sum(d['calls'] for d in ds)} | {sum(d['agent'] for d in ds)}／{sum(d['fallback'] for d in ds)} | "
                     f"{f(med([d['p50_ms'] for d in ds]), 0)}／{f(med([d['p95_ms'] for d in ds]), 0)} | {cost_s} |")
    L.append("")
    L += ["## 逐類型", "", "| 類型 | 段數 | 組 | 較好 | 相同 | 較差 | 跟對率（各案中位數的中位數） |", "| --- | ---: | --- | ---: | ---: | ---: | --- |"]
    fam = defaultdict(list)
    for s in scored:
        fam[case_family(s["case"])].append(s)
    for fk in sorted(fam):
        for mode in ("terra", "sol"):
            verdicts = [compare_to_rule(s, mode) for s in fam[fk]]
            verdicts = [v for v in verdicts if v]
            if not verdicts:
                continue
            same = sum(1 for v in verdicts if v.startswith("相同"))
            rates = [med([x["rate"] for x in s["modes"].get(mode, [])]) for s in fam[fk]]
            L.append(f"| {fk} | {len(verdicts)} | {mode} vs 規則 | {verdicts.count('較好')} | {same} | {verdicts.count('較差')} | {f(med(rates))}（規則 {f(med([med([x['rate'] for x in s['modes']['rule']]) for s in fam[fk]]))}） |")
    L += ["", "較好＝跟對率高 ≥ 0.05，或至少一個切鏡點由接錯／沒接上變成接對且沒有另一個變差；反過來是較差；其餘相同（先於結果寫定，guide §4）。", ""]
    L += ["## 切鏡點（W = 2／5／10 s）", "", "| 案例 | # | t_X (s) | t_N (s) | 組 | W=2 | W=5 | W=10 | 延遲 s（W=5） |", "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |"]
    for s in scored:
        for i, p in enumerate(s.get("handoff_points", [])):
            for mode in MODES:
                xs = s["modes"].get(mode) or []
                if not xs:
                    continue
                cell = lambda w: "／".join(x["handoff"][str(float(w))][i] for x in xs if i < len(x["handoff"][str(float(w))]))  # noqa: E731
                dl = "／".join(f(x["handoff_delay_s"][i], 1) for x in xs if i < len(x["handoff_delay_s"]))
                L.append(f"| {s['case']} | {i + 1} | {p['t_x']:.1f} | {p['t_n']:.1f} | {mode} | {cell(2)} | {cell(5)} | {cell(10)} | {dl} |")
    L.append("")
    L += ["## 裁決點（規則 vs LLM）", "",
          "| 案例 | 次 | tick | t (s) | 失聯秒數 | 名單人數 | 目標可見（GT） | 規則 | terra | sol | 正確答案 | 規則 | terra | sol | 之後 10 s 跟對（規則／terra／sol） | 備註 |",
          "| --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in scored:
        for d in s["decisions"]:
            note = f"只在 {d['only']} 出現；" if d["only"] else ""
            note += "候選名單未記錄，T 可見但不在名單的情形無法分辨（UNKNOWN）"
            L.append(f"| {d['case']} | r{d['rep']} | {d['tick'] if d['tick'] is not None else '—'} | {d['t']:.1f} | {f(d['lost_s'], 1)} | {d['cands'] if d['cands'] is not None else '—'} | "
                     f"{'是' if d['t_visible'] else '否'} | {d['rule']} | {d['terra']} | {d['sol']} | {d['correct']} | {d['rule_ok']} | {d['terra_ok']} | {d['sol_ok']} | "
                     f"{f(d['rule_after'], 2)}／{f(d['terra_after'], 2)}／{f(d['sol_after'], 2)} | {note} |")
    L.append("")
    if skipped:
        L += ["## 未比較", ""] + [f"- {s['case']}：{s['status']} {', '.join(s['unknown'])}" for s in skipped] + [""]
    L += ["## 方法與限制", "",
          "- 目標＝腳本玩家 T；GT（A log 的 `actors`）只用於事後評分，B 與 LLM 請求都沒有它。",
          "- 三組以 `t_sim` 對齊（擷取 tick 用牆鐘，各組不同）；比率以秒加權；同一劇本三組的演員位置不一致（> 容許值）時整案不比較（REPLAY_MISMATCH）。",
          "- `NEEDS_CONFIRM` 算失聯（RELOCK §2.1）；目標看不到時的狀態另列（看不到期間的錯人秒）。",
          "- 規則在裁決點的選擇取自規則組同一 `t_sim` 的追蹤輸出；候選名單與規則選擇沒有記進 B log（#596 Q6），名單內容為 UNKNOWN。",
          "- 樣本少，逐案比較，不寫統計顯著；感知規模（100 台以上鏡頭）未驗證。", ""]
    return "\n".join(L)


def write_csv(scores, path):
    cols = ["case", "rep", "tick", "t", "lost_s", "cands", "t_visible", "rule", "terra", "sol", "correct", "rule_ok", "terra_ok", "sol_ok",
            "rule_after", "terra_after", "sol_after", "only", "kind"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for s in scores:
            for d in s["decisions"]:
                w.writerow(d)


def run_dir(path, cases=None, tol=REPLAY_TOL_M):
    runs = load_dir(Path(path))
    grouped = defaultdict(lambda: defaultdict(list))
    for (case, mode, rep), r in sorted(runs.items()):
        if cases is None or case in cases:
            grouped[case][mode].append(r)
    return [score_case(case, dict(by_mode), tol) for case, by_mode in sorted(grouped.items())]


def _json_safe(o):
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items() if k != "answer_row"}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="directory with <case>.<mode>.<rep>.{a,b}-log.json")
    ap.add_argument("--cases", help="comma separated case ids (default: all found)")
    ap.add_argument("--out", help="output directory for report.md, score.json, decisions.csv (default: print the Markdown)")
    ap.add_argument("--replay-tol-m", type=float, default=REPLAY_TOL_M)
    args = ap.parse_args(argv)
    scores = run_dir(args.dir, set(args.cases.split(",")) if args.cases else None, args.replay_tol_m)
    md = render_markdown(scores)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(md, "utf-8")
        (out / "score.json").write_text(json.dumps(_json_safe(scores), ensure_ascii=False, indent=1), "utf-8")
        write_csv(scores, out / "decisions.csv")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
