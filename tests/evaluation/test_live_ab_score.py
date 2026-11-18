"""Offline scoring contract: synthetic GT is confined to two downloaded log inputs."""

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.live_ab_score import score_logs

FIXTURE = Path(__file__).parent / "fixtures/live_ab"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/live_ab_score.py"


def logs():
    return json.loads((FIXTURE / "a.json").read_text()), json.loads(
        (FIXTURE / "b.json").read_text()
    )


def test_counts_pick_source_tick_effective_time_unknown_and_out_of_view():
    a, b = logs()
    r = score_logs(a, b)
    s = r["segments"][0]
    assert s["target_gt"] == "T" and s["start_t_op"] == 1000
    assert [row["tick"] for row in s["rows"]] == list(range(1, 8))
    assert s["counts"] == {
        "ON_TARGET": 1,
        "WRONG_PERSON": 2,
        "UNMATCHED": 1,
        "LOST": 1,
        "TARGET_OUT_OF_VIEW": 1,
        "UNKNOWN": 1,
    }
    assert s["visible_scored_ticks"] == 5 and s["rates"]["ON_TARGET"] == 0.2
    assert s["identity_switch_proxy_count"] == 1 and len(s["lost_episodes"]) == 1
    assert s["lost_episodes"][0]["seconds"] == 1 and s["camera_switches"] == 1
    assert "GT_MISSING" in r["unknown_reasons"]
    assert "pass" not in r


def test_session_mismatch_is_whole_unknown_not_a_lost_run():
    a, b = logs()
    b["session_id"] = "fedcba9876543210"
    r = score_logs(a, b)
    assert (
        r["status"] == "UNKNOWN"
        and r["unknown_reasons"] == ["SESSION_MISMATCH"]
        and r["segments"] == []
    )


@pytest.mark.parametrize("kind", ["clock", "missing", "duplicate"])
def test_bad_alignment_is_unknown_never_lost(kind):
    a, b = logs()
    if kind == "clock":
        a["ticks"][1]["t_capture"] += 1
    elif kind == "missing":
        a["ticks"] = [x for x in a["ticks"] if x["tick"] != 1]
    else:
        a["ticks"].append(copy.deepcopy(a["ticks"][1]))
    s = score_logs(a, b)["segments"][0]
    assert s["rows"][0]["status"] == "UNKNOWN" and s["counts"]["LOST"] == 1


@pytest.mark.parametrize("point,expected", [([2.5, 0], "MISPICK"), ([20, 20], "MISPICK")])
def test_mispick(point, expected):
    a, b = logs()
    b["actions"][0]["est_xy"] = point
    s = score_logs(a, b)["segments"][0]
    assert (
        s["pick_status"] == expected and s["target_gt"] is None and s["visible_scored_ticks"] == 0
    )


def test_ambiguous_pick_has_no_invented_actor():
    a, b = logs()
    a["ticks"][0]["actors"][1]["xy"] = [0.02, 0]
    s = score_logs(a, b)["segments"][0]
    assert s["pick_status"] == "AMBIGUOUS_PICK" and s["target_gt"] is None


def test_retarget_t_op_boundaries_reselect_keeps_old_until_pick_and_start_closes():
    a, b = logs()
    b["actions"] = [
        b["actions"][0],
        {"type": "reselect", "t_op": 2500},
        {"type": "pick", "tick": 0, "est_xy": [5, 0], "t_op": 4000},
        {"type": "start", "t_op": 6500},
        {"type": "stop", "t_op": 8000},
    ]
    r = score_logs(a, b)
    assert [s["target_gt"] for s in r["segments"]] == ["T", "A"]
    assert [x["tick"] for x in r["segments"][0]["rows"]] == [1, 2, 3]
    assert [x["tick"] for x in r["segments"][1]["rows"]] == [4, 5, 6]


def test_auto_single_acquire_is_deduplicated_from_repeated_events():
    a, b = logs()
    b["actions"] = []
    ev = {"type": "ACQUIRE", "tick": 1, "detail": {"by": "AUTO_SINGLE"}}
    b["ticks"][1]["tracking"]["events"] = [ev]
    b["ticks"][2]["tracking"]["events"] = [ev]
    r = score_logs(a, b)
    assert len(r["segments"]) == 1 and r["segments"][0]["target_gt"] == "T"


def test_start_response_single_candidate_can_supply_source_point_before_next_infer():
    a, b = logs()
    b["actions"] = [
        {"type": "start", "mode": "TRACKING", "t_op": 1000, "tick": 0, "est_xy": [5, 0]}
    ]
    s = score_logs(a, b)["segments"][0]
    assert s["target_gt"] == "A" and s["pick_by"] == "AUTO_SINGLE"


def test_lost_ticks_precede_tracking_point_and_no_gt_is_unknown():
    a, b = logs()
    b["ticks"][1]["tracking"]["lost_ticks"] = 1
    r = score_logs(a, b)
    assert r["segments"][0]["rows"][0]["status"] == "LOST"


@pytest.mark.parametrize("state", ["IDLE", "ACQUIRING", "SEARCHING", "NEEDS_PICK"])
def test_unlocked_state_is_unknown_even_inside_a_scoring_segment(state):
    a, b = logs()
    b["ticks"][1]["tracking"].update(state=state, est_xy=None, lost_ticks=4)
    result = score_logs(a, b)
    segment = result["segments"][0]
    assert segment["rows"][0]["status"] == "UNKNOWN"
    assert segment["counts"]["LOST"] == 1
    assert segment["visible_scored_ticks"] == 4
    assert "NOT_TRACKING" in result["unknown_reasons"]


def test_raw_and_one_second_hud_median_latency_are_distinct():
    a, b = logs()
    a["ticks"] = a["ticks"][:3]
    b["ticks"] = b["ticks"][:3]
    for i, (capture, delay) in enumerate([(0, 100), (200, 500), (400, 900)]):
        a["ticks"][i]["t_capture"] = capture
        b["ticks"][i].update(t_capture=capture, t_resp=capture + delay)
    r = score_logs(a, b)
    assert r["latency"]["raw_ms"]["p50"] == 500
    assert r["latency"]["hud_1s_median_ms"]["p50"] == 300


def test_collision_event_dedup_chain_counts_and_wait_totals():
    a, b = logs()
    a["forced_overlap"] = [
        {"tick": 10, "i": "T", "j": "A", "kind": "script", "chain": True},
        {"tick": 20, "i": "A", "j": "T", "kind": "script", "chain": False},
        {
            "tick": 30, "i": "B", "j": "C", "kind": "script", "chain": False,
            "cause": "player_phase_shift",
        },
    ]
    a["ticks"][3]["forced_overlap"] = copy.deepcopy(a["forced_overlap"])
    a["block_wait"] = [{"tick": 15, "i": "T", "j": "player", "waited_s": 10}]
    a["ticks"][-1]["block_wait"] = [{"i": "T", "j": "player", "waited_s": 3}]
    a["ticks"][-1]["pause_total_i"] = {"T": 15}
    stats = score_logs(a, b)["crowd"]
    assert stats["forced_overlap"] == {
        "chain": 1, "nonchain": 1, "player": 0, "unknown_chain": 0, "player_phase_shift": 1,
    }
    assert stats["block_wait_total_s"] == 13 and stats["pause_total_s"] == 15


@pytest.mark.parametrize("bad", ["json", "schema"])
def test_cli_bad_input_no_output(bad, tmp_path):
    a, b = logs()
    ap = tmp_path / "a.json"
    bp = tmp_path / "b.json"
    out = tmp_path / "result.json"
    if bad == "schema":
        a["schema_version"] = "future"
    ap.write_text("{" if bad == "json" else json.dumps(a))
    bp.write_text(json.dumps(b))
    r = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--operator-json",
            str(ap),
            "--system-json",
            str(bp),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 and not out.exists()


def test_cli_does_not_modify_inputs_or_allow_output_alias(tmp_path):
    a, b = logs()
    ap = tmp_path / "a.json"
    bp = tmp_path / "b.json"
    out = tmp_path / "out.json"
    ap.write_text(json.dumps(a))
    bp.write_text(json.dumps(b))
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in [ap, bp]]
    cmd = [
        sys.executable,
        "-B",
        str(SCRIPT),
        "--operator-json",
        str(ap),
        "--system-json",
        str(bp),
        "--out",
    ]
    assert subprocess.run(cmd + [str(out)], capture_output=True).returncode == 0
    assert json.loads(out.read_text())["schema_version"] == "live-ab.score.v1"
    assert subprocess.run(cmd + [str(ap)], capture_output=True).returncode != 0
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in [ap, bp]]


def test_scorer_imports_only_stdlib_and_never_backend_network_or_scenario():
    source = SCRIPT.read_text()
    tree = ast.parse(source)
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]
    assert all(m.split(".")[0] in sys.stdlib_module_names for m in imports)
    assert "amidst.live_mode" not in source and "R004_" not in source


def test_single_start_does_not_duplicate_its_repeated_auto_event():
    a, b = logs()
    b["actions"] = [
        {"type": "start", "mode": "TRACKING", "t_op": 1000, "tick": 0, "est_xy": [5, 0]}
    ]
    b["ticks"][1]["tracking"]["events"] = [
        {"type": "ACQUIRE", "tick": 0, "detail": {"by": "AUTO_SINGLE"}}
    ]
    r = score_logs(a, b)
    assert (
        len(r["segments"]) == 1
        and r["segments"][0]["start_t_op"] == 1000
        and r["segments"][0]["target_gt"] == "A"
    )


def test_nonfinite_or_missing_capture_is_explicit_unassigned_unknown():
    a, b = logs()
    b["ticks"][1].pop("t_capture")
    r = score_logs(a, b)
    assert any(x["tick"] == 1 and x["status"] == "UNKNOWN" for x in r["unassigned_ticks"])
    assert "CLOCK_MISMATCH" in r["unknown_reasons"]


def test_negative_response_clock_is_unknown_not_success():
    a, b = logs()
    b["ticks"][1]["t_resp"] = 999
    r = score_logs(a, b)
    assert r["segments"][0]["rows"][0]["status"] == "UNKNOWN"


def test_explicitly_absent_target_is_out_of_view_even_without_visibility_payload():
    a, b = logs()
    a["ticks"][1]["actors"][0].update(present=False, xy=None)
    a["ticks"][1]["actors"][0].pop("gt_visible")
    assert score_logs(a, b)["segments"][0]["rows"][0]["status"] == "TARGET_OUT_OF_VIEW"


def test_input_hardlink_cannot_be_output(tmp_path):
    a, b = logs()
    ap = tmp_path / "a.json"
    bp = tmp_path / "b.json"
    out = tmp_path / "alias.json"
    ap.write_text(json.dumps(a))
    bp.write_text(json.dumps(b))
    out.hardlink_to(ap)
    before = ap.read_bytes()
    r = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--operator-json",
            str(ap),
            "--system-json",
            str(bp),
            "--out",
            str(out),
        ],
        capture_output=True,
    )
    assert r.returncode != 0 and ap.read_bytes() == before


def test_penetration_raw_adjusted_and_script_forced_pair_exclusion():
    a, b = logs()
    a["ticks"][1]["actors"][1]["xy"] = [0.4, 0]
    s = score_logs(a, b)["crowd"]
    assert s["raw_player_penetrations"] == 1 and s["player_penetrations"] == 1
    a["ticks"][1]["forced_pairs"] = [["A", "T"]]
    s = score_logs(a, b)["crowd"]
    assert s["player_penetrations"] == 1 and s["invalid_forced_pair_samples"] == 1
    a, b = logs()
    for row in a["ticks"]:
        if row["actors"] is not None:
            row["actors"].append(
                {"id": "B", "present": True, "xy": [10, 0], "gt_visible": ["CAM_3"]}
            )
    a["ticks"][1]["actors"][-1]["xy"] = [0.4, 0]
    a["forced_overlap"] = [{"tick": 1, "i": "T", "j": "B", "kind": "script", "chain": True}]
    a["ticks"][1]["forced_pairs"] = [["T", "B"]]
    assert score_logs(a, b)["crowd"]["forced_pair_samples_excluded"] == 1


@pytest.mark.parametrize("delta,status", [(1.5, "PICKED"), (1.50001, "MISPICK")])
def test_pick_distance_boundary(delta, status):
    a, b = logs()
    b["actions"][0]["est_xy"] = [-delta, 0]
    assert score_logs(a, b)["segments"][0]["pick_status"] == status


def test_ambiguous_gap_boundary_is_strict():
    a, b = logs()
    a["ticks"][0]["actors"][1]["xy"] = [0.05, 0]
    assert score_logs(a, b)["segments"][0]["pick_status"] == "PICKED"
