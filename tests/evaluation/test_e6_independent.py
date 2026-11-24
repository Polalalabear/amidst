"""Focused boundaries: frozen scorer, inference isolation, AO lifecycle and R-N timing."""

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/evaluation" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rn = load("e6_rule_neutral")
diag = load("e6_independent_diagnostics")


class Projector:
    def ground(self, cam, u, v, w, h):
        return [u, v]


def det(x=0, color="red"):
    return {"CAM": [{"bbox": [x - 1, 0, x + 1, 1], "score": 0.9, "color": color}]}


def test_half_open_spans_and_trailing_gap():
    assert diag.spans([False, False, True, False], lambda x: not x) == [(0, 2), (3, 4)]


def test_scorer_frozen_and_inference_has_no_gt_or_model_imports():
    assert diag.scorer().SCHEMA == "e3.score.v1"
    tree = ast.parse((ROOT / "scripts/evaluation/e6_rule_neutral.py").read_text())
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(
        any(s in n for s in ("evaluation", "api_budget", "openai", "e3_f4_run")) for n in imports
    )


@pytest.mark.parametrize("lost", [True, False])
def test_schedule_matches_real_aopen(lost):
    from amidst.live_mode.aopen.decider import AOpenDecider

    class Observe(AOpenDecider):
        def _ask(self, tick, kind, frames, dets, rule_state):
            self.calls.append((tick, kind))
            self.last_ask_tick = tick

    ao = Observe(None, {}, Projector(), call_cap=3)
    ao.reference = b"local-test-reference"
    if not lost:
        ao.neutral.adopt(0, "CAM", det()["CAM"][0]["bbox"], "TEST")
    expected, last = [], None
    for tick in range(40):
        ao.step(tick, {} if lost else det(), {}, {})
        kind = rn.ask_kind(tick, last, lost)
        if kind and len(expected) < 3:
            expected.append((tick, kind))
            last = tick
    assert ao.calls == expected
    assert expected == (
        [(0, "FIRST"), (5, "LOST_EARLY"), (10, "LOST_EARLY")]
        if lost
        else [(0, "FIRST"), (10, "POLL"), (20, "POLL")]
    )


def test_next_tick_uses_request_box_and_own_state():
    d = rn.RuleNeutral(Projector(), 0, [0, 1], 10, "UNCERTAIN")
    assert d.step(0, det())["tracking"]["state"] == "LOST"
    assert d.calls[0]["answer"] == "SELECT"
    row = d.step(1, det(3))
    assert row["tracking"]["box"] == [-1, 0, 1, 1]  # ask-time box, not current candidate
    assert d.calls[0]["applied_tick"] == 1
    for tick in range(2, 6):
        d.step(tick, {})
    assert d.calls[1]["kind"] == "LOST_EARLY"
    assert d.calls[1]["own_state"]["est_xy"] is None
    assert d.calls[1]["last_known_xy"] == [0, 1]


@pytest.mark.parametrize("answer", ["UNCERTAIN", "NOT_VISIBLE"])
def test_no_candidate_variants_and_cap(answer):
    d = rn.RuleNeutral(Projector(), 0, [0, 1], 1, answer)
    d.neutral.adopt(0, "CAM", [-1, 0, 1, 1], "TEST")
    d.step(0, det(color="blue"))
    row = d.step(1, det(color="blue"))
    assert d.calls[0]["answer"] == answer
    assert row["tracking"]["state"] == ("TRACKING" if answer == "UNCERTAIN" else "LOST")
    for tick in range(2, 50):
        d.step(tick, {})
    assert len(d.calls) == d.cap == 1


def test_distance_color_and_projection_filter():
    d = rn.RuleNeutral(Projector(), 0, [0, 1], 10, "UNCERTAIN")
    d.step(0, {"CAM": det(8)["CAM"] + det(0, "blue")["CAM"] + det(2)["CAM"]})
    assert d.calls[0]["detection_id"] == "D3"
    assert d.calls[0]["candidate_list"][0]["reasons"] == ["DISTANCE_GT_4M"]
    assert d.calls[0]["candidate_list"][1]["reasons"] == ["NOT_RED"]
