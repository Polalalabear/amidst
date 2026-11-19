"""#597 hard-case comparison scorer: synthetic A/B logs only (no browser, no model, no API)."""

import ast
import json
from pathlib import Path

from scripts import live_hardset_compare as C

DT = 0.2
SCRIPT = Path(C.__file__)


def build(mode, *, track, decisions=(), shift=0.0, states=None, n=100):
    """A short scripted case. T walks east at 1 m/s along y=0; D (a second red person) walks 3 m behind.
    T is visible to camera CAM_X for t < 10 and again for t >= 16 (blind gap in between).
    track(t) -> 'T' | 'D' | None says whom the system follows; decisions = [(ask_t, answer_t, detail)]."""
    a_ticks, b_ticks = [], []
    ask = {round(x[0] / DT): x for x in decisions}
    ans = {round(x[1] / DT): x for x in decisions}
    for i in range(n):
        t = i * DT
        tx, dx = -3.0 + t, -6.0 + t + shift
        vis = [] if 10 <= t < 16 else ["CAM_X"]
        a_ticks.append({"tick": i, "t_capture": 1000.0 + i, "t_sim": t, "actors": [
            {"id": "T", "present": True, "xy": [tx, 0.0], "gt_visible": vis},
            {"id": "D", "present": True, "xy": [dx, 0.0], "gt_visible": ["CAM_X"]}]})
        who = track(t)
        state = (states or {}).get(i, "TRACKING" if who else "LOST")
        tr = {"state": state, "active_cam": "CAM_X", "lost_ticks": 0 if who else 3, "events": []}
        if who:
            tr["est_xy"] = [tx, 0.0] if who == "T" else [dx, 0.0]
        if i in ask:
            tr["events"].append({"tick": i, "type": "ADJUDICATE_ASK", "cam": "CAM_X", "detail": {"kind": "LOST_WITH_CANDIDATES", "candidates": 2}})
        if i in ans:
            tr["events"].append({"tick": i, "type": "ADJUDICATED", "cam": "CAM_X", "detail": ans[i][2]})
        b_ticks.append({"tick": i, "t_capture": 1000.0 + i, "t_resp": 1000.5 + i, "tracking": tr})
    a = {"schema_version": "live-ab.a-log.v1", "session_id": "s-" + mode, "ticks": a_ticks}
    b = {"schema_version": "live-ab.b-log.v1", "session_id": "s-" + mode, "ticks": b_ticks, "actions": []}
    return a, b


def rule_track(t):          # follows T, loses it in the blind gap, then locks onto D when T comes back
    return "T" if t < 10 else None if t < 16 else "D"


def llm_track(t):           # same until the answer at t=16.8, then back on T
    return "T" if t < 10 else None if t < 16 else "D" if t < 16.8 else "T"


def run(mode, rep, a, b, meta=None):
    a["session_id"] = b["session_id"] = f"{mode}{rep}"
    return C.Run("X-1", mode, rep, a, b, meta)


def scored(rule_kw=None, **kw):
    rule = run("rule", 1, *build("rule", track=rule_track))
    terra = run("terra", 1, *build("terra", track=llm_track, decisions=[(16.2, 16.8, {"choice": 1, "applied": True, "cleared": False, "source": "AGENT", "latency_ms": 4200})]), meta={"cost_usd": 0.003})
    sol = run("sol", 1, *build("sol", track=rule_track, decisions=[(16.2, 17.0, {"choice": 0, "applied": False, "cleared": True, "source": "AGENT", "latency_ms": 5000})]))
    return C.score_case("X-1", {"rule": [rule], "terra": [terra], "sol": [sol]}, **kw)


def test_rates_are_time_weighted_and_classified():
    s = scored()
    r = s["modes"]["rule"][0]
    # visible: t<10 (10 s on target) and t>=16 (following D, wrong person)
    assert r["rate"] is not None and 0.6 < r["rate"] < 0.8   # 10 s on target, then about 4 s on D
    assert r["wrong_s"] > 3.5 and r["lost_s"] == 0
    assert r["wrong_unseen_s"] == 0 and r["declared_unseen_s"] > 5   # blind gap: the system said lost, which is correct
    assert r["identity_switches"] == 1
    t = s["modes"]["terra"][0]
    assert t["rate"] > r["rate"] + 0.15 and t["wrong_s"] < 1.0


def test_handoff_points_come_from_the_rule_run_and_verdicts_differ():
    s = scored()
    assert len(s["handoff_points"]) == 1 and abs(s["handoff_points"][0]["t_x"] - 10.0) < 0.3 and abs(s["handoff_points"][0]["t_n"] - 16.0) < 0.3
    assert s["modes"]["rule"][0]["handoff"]["5.0"] == ["接錯"]
    # the spec counts an episode of >= 2 wrong ticks inside the window as 接錯 even when the answer fixes it 0.8 s later
    assert s["modes"]["terra"][0]["handoff"]["10.0"] == ["接錯"]
    assert abs(s["modes"]["terra"][0]["handoff_delay_s"][0] - 0.8) < 0.3 and s["modes"]["rule"][0]["handoff_delay_s"][0] is None


def test_decision_table_rule_vs_llm_answers():
    s = scored()
    rows = s["decisions"]
    assert len(rows) == 1                       # terra and sol decisions at 16.2 s share one row
    d = rows[0]
    assert d["t_visible"] is True and d["correct"] == "T" and d["cands"] == 2
    assert d["rule"] == "D" and d["rule_ok"] == "✗"
    assert d["terra"] == "T" and d["terra_ok"] == "✓"
    assert d["sol"] == "都不是" and d["sol_ok"] == "✗"        # T was visible, so "none of them" is wrong
    assert d["terra_after"] > d["rule_after"] + 0.5


def test_none_of_them_is_correct_when_target_is_unseen():
    a, b = build("sol", track=rule_track, decisions=[(11.0, 11.6, {"choice": 0, "applied": False, "cleared": True, "source": "AGENT", "latency_ms": 600})])
    rule = run("rule", 1, *build("rule", track=rule_track))
    sol = run("sol", 1, a, b)
    d = C.score_case("X-1", {"rule": [rule], "sol": [sol]})["decisions"][0]
    assert d["t_visible"] is False and d["correct"] == "都不是" and d["sol_ok"] == "✓" and d["rule"] == "失聯" and d["rule_ok"] == "✓"
    assert d["only"] == "sol" and d["terra"] == "—"


def test_fallback_is_reported_and_counted():
    rule = run("rule", 1, *build("rule", track=rule_track))
    terra = run("terra", 1, *build("terra", track=rule_track, decisions=[(16.2, 18.0, {"choice": None, "applied": False, "cleared": False, "source": "RULE_FALLBACK", "latency_ms": 5200})]))
    s = C.score_case("X-1", {"rule": [rule], "terra": [terra]})
    d = s["modes"]["terra"][0]["decision"]
    assert (d["calls"], d["agent"], d["fallback"]) == (1, 0, 1) and d["p50_ms"] == 5200
    assert s["decisions"][0]["terra"] == "退回規則" and s["decisions"][0]["terra_ok"] == "—"


def test_needs_confirm_counts_as_lost_not_unknown():
    r = run("rule", 1, *build("rule", track=lambda t: "T", states={i: "NEEDS_CONFIRM" for i in range(85, 90)}))
    assert {r.rows[i]["status"] for i in range(85, 90)} == {"LOST"}
    assert r.reacquire()[0]["found"] is True


def test_reacquire_seconds_measured_from_reappearance():
    r = run("rule", 1, *build("rule", track=lambda t: "T" if t < 10 or t >= 18 else "D" if t >= 16 else None))
    ep = r.reacquire()
    assert len(ep) == 1 and ep[0]["found"] and abs(ep[0]["s"] - 2.0) < 0.3   # visible again at 16 s, back on T at 18 s


def test_replay_mismatch_excludes_the_case():
    rule = run("rule", 1, *build("rule", track=rule_track))
    terra = run("terra", 1, *build("terra", track=llm_track, shift=0.5))
    s = C.score_case("X-1", {"rule": [rule], "terra": [terra]})
    assert s["status"] == "NOT_COMPARED" and any(u.startswith("REPLAY_MISMATCH") for u in s["unknown"])
    s = C.score_case("X-1", {"rule": [rule], "terra": [terra]}, tol=1.0)
    assert s["status"] == "SCORED"


def test_session_mismatch_excludes_the_case():
    a, b = build("rule", track=rule_track)
    rule = C.Run("X-1", "rule", 1, a, {**b, "session_id": "other"})
    assert C.score_case("X-1", {"rule": [rule]})["status"] == "NOT_COMPARED"


def test_better_same_worse_definition():
    s = scored()
    assert C.compare_to_rule(s, "terra") == "較好"
    assert C.compare_to_rule(s, "sol") == "相同"
    flip = C.score_case("X-1", {"rule": [run("rule", 1, *build("rule", track=llm_track))], "terra": [run("terra", 1, *build("terra", track=rule_track))]})
    assert C.compare_to_rule(flip, "terra") == "較差"


def test_markdown_csv_and_cli(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    for mode, kw in (("rule", dict(track=rule_track)),
                     ("terra", dict(track=llm_track, decisions=[(16.2, 16.8, {"choice": 1, "applied": True, "cleared": False, "source": "AGENT", "latency_ms": 4200})]))):
        a, b = build(mode, track=kw["track"], decisions=kw.get("decisions", ()))
        (d / f"X-1.{mode}.1.a-log.json").write_text(json.dumps(a))
        (d / f"X-1.{mode}.1.b-log.json").write_text(json.dumps(b))
    (d / "X-1.terra.1.meta.json").write_text(json.dumps({"cost_usd": 0.0031}))
    out = tmp_path / "out"
    assert C.main(["--dir", str(d), "--out", str(out)]) == 0
    md = (out / "report.md").read_text()
    assert "| X-1 | terra | 1 |" in md and "0.0031" in md and "較好" in md and "裁決點" in md and "## 未比較" not in md
    assert "case,rep,tick" in (out / "decisions.csv").read_text()
    assert json.loads((out / "score.json").read_text())[0]["status"] == "SCORED"


def test_scorer_never_feeds_gt_anywhere_else():
    """The module reads logs and writes files; it imports no network, subprocess or live-mode package."""
    tree = ast.parse(SCRIPT.read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not mods & {"urllib", "requests", "socket", "subprocess", "http", "amidst"}


def test_dry_run_estimate_uses_pinned_prices_and_makes_no_call(capsys):
    from scripts import live_hardset_dryrun as D
    lengths, prices = D.load("H5-1,H1-1")
    res = D.estimate(lengths, ["terra6.1", "sol6.1"], 3, prices)
    assert res["questions_per_case"] == {"H5-1": int(39.7 // 3.5), "H1-1": int(36.1 // 3.5)}
    n = sum(res["questions_per_case"].values()) * 3
    w = res["per_model"]["sol6.1"]["worst_case"]
    assert w["calls"] == n and abs(w["est_cost_per_call_usd"] - (1100 * 2.0 + 400 * 10.0) / 1e6) < 1e-9
    assert res["per_model"]["terra6.1"]["typical"]["est_total_usd"] < res["per_model"]["sol6.1"]["typical"]["est_total_usd"]
    assert D.main(["--cases", "nine", "--json"]) == 0 and '"total_worst_usd"' in capsys.readouterr().out
