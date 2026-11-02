"""評分端；與推論隔離。CQ-32-T uses SYNTHETIC controls only, never U6 adoption."""
from copy import deepcopy
import builtins
import hashlib
import importlib
import importlib.util
import inspect
import io
import itertools
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from amidst.evaluation import q5_switch_eval as v1

FIXTURES = ROOT / "tests/fixtures/q5_v2/SYNTHETIC"
SPEC = importlib.util.spec_from_file_location("cq32_legacy", ROOT / "tests/unit/test_q5_switch_eval.py")
LEGACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEGACY)


def load(name):
    return json.loads((FIXTURES / name).read_bytes())


def fixture_module():
    spec = importlib.util.spec_from_file_location("cq32_fixture_builder", FIXTURES / "build_fixtures.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def required_module():
    path = ROOT / "src/amidst/evaluation/q5_switch_eval_v2.py"
    if not path.is_file():
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ32_IMPLEMENTATION_MISSING")
        pytest.importorskip("amidst.evaluation.q5_switch_eval_v2", reason="CQ32_IMPLEMENTATION_MISSING")
        pytest.skip("CQ32_LOCAL_IMPLEMENTATION_MISSING")
    return importlib.import_module("amidst.evaluation.q5_switch_eval_v2")


def driver():
    implementation = required_module()
    selected = os.environ.get("AMIDST_Q5_V2_DRIVER")
    if not selected:
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ32_TEST_DRIVER_UNBOUND")
        pytest.skip("CQ32_TEST_DRIVER_UNBOUND")
    try:
        adapter = importlib.import_module(selected)
    except ImportError:
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ32_TEST_DRIVER_IMPORT_MISSING")
        pytest.importorskip(selected, reason="CQ32_TEST_DRIVER_IMPORT_MISSING")
    return implementation, adapter


def exercise(name, inputs, *, harness=None):
    implementation, adapter = harness or driver()
    try:
        result = adapter.exercise_case(name, inputs=inputs, implementation=implementation)
    except (pytest.skip.Exception, pytest.xfail.Exception):
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ32_REQUIRED_DRIVER_BINDING_MISSING")
        raise
    assert isinstance(result, dict)
    assert result.get("implementation_invoked") is True
    assert result.get("implementation_file_sha256") == v1.sha(Path(implementation.__file__).read_bytes())
    # TEST-ONLY observations cannot authenticate authority or adopt proposed choices.
    assert result.get("human_approval_verified") is False
    if result.get("rejected") is not True:
        assert isinstance(result.get("native_report"), dict)
    return result


def inputs(kind="phase", *, selections=True):
    metadata = load("CASES.SYNTHETIC.json")
    config = load("decisions.PENDING.SYNTHETIC.json")
    if selections:
        config.update(metadata["test_only_selections"])
        config["UK-8"] = "PENDING_USER"  # No real timing-method decision is selected.
    return {"fixture_role": "SYNTHETIC_ONLY", "response": load(kind + ".response.SYNTHETIC.json"),
            "records": [json.loads(line) for line in (FIXTURES / (kind + ".decisions.SYNTHETIC.jsonl")).read_bytes().splitlines()],
            "script": load((kind if kind != "searching" else "phase") + ".script.SYNTHETIC.json"),
            "parameters": load("parameter_set.SYNTHETIC.json"), "plan": load("plan.SYNTHETIC.json"),
            "decisions": config}


def reseal(data):
    for index, row in enumerate(data["records"]):
        row["step_index"] = index
        row["content_sha256"] = v1.digest(row, "content_sha256")
    raw = b"".join(v1.canonical(row) + b"\n" for row in data["records"])
    response = data["response"]
    response["decisions_sha256"] = v1.sha(raw)
    response["output_sha256"] = v1.digest(response, "output_sha256")
    data["raw"] = {"response": v1.canonical(response), "decisions": raw,
                   "script": v1.canonical(data["script"]), "parameters": v1.canonical(data["parameters"])}
    data["pins"] = {key: v1.sha(raw) for key, raw in data["raw"].items()}
    return data


def event(result, name=None):
    rows = result["observations"]["events"]
    return next(r for r in rows if r["event_id"] == name) if name else rows[0]


def assert_rejected(result, category):
    assert result.get("rejected") is True and result.get("native_report") is None
    assert result["observations"]["error_category"] == category


def legacy_cases():
    result = []
    for name, function in vars(LEGACY).items():
        if not name.startswith("test_") or not inspect.isfunction(function):
            continue
        variants = [{}]
        for mark in getattr(function, "pytestmark", []):
            if mark.name != "parametrize":
                continue
            names = [part.strip() for part in mark.args[0].split(",")]
            values = [value if len(names) > 1 else (value,) for value in mark.args[1]]
            variants = [{**old, **dict(zip(names, valueset))}
                        for old, valueset in itertools.product(variants, values)]
        result.extend(pytest.param(name, params, id=f"{name}-{i}") for i, params in enumerate(variants))
    return result


def test_fixture_inventory_and_independent_golden_values(tmp_path):
    manifest = load("MANIFEST.SYNTHETIC.json")
    assert manifest["fixture_role"] == "SYNTHETIC_ONLY"
    for name, pin in manifest["files"].items():
        assert v1.sha((FIXTURES / name).read_bytes()) == pin
    fixture_module().build(tmp_path)
    assert all((tmp_path / name).read_bytes() == (FIXTURES / name).read_bytes() for name in manifest["files"])
    golden = load("CASES.SYNTHETIC.json")["golden"]
    assert golden["G1_us"] == 5_200_000
    assert golden["phase_returns_us"] == [600_000, 1_600_000]
    assert golden["phase_switch_us"] == 2_600_000 and golden["phase_entry_us"] == 7_600_000
    assert golden["phase_search_windows_us"][1] == [1_600_000, 7_600_000]


def test_only_one_decision_selected_per_synthetic_variant():
    pending = load("decisions.PENDING.SYNTHETIC.json")
    assert pending and set(pending.values()) == {"PENDING_USER"} and "U-D3" not in pending
    for group, selection in load("CASES.SYNTHETIC.json")["test_only_selections"].items():
        variant = load(f"decisions.{group}.SYNTHETIC.json")
        assert set(variant) == set(pending) and variant[group] == selection
        assert sum(variant[key] != value for key, value in pending.items()) == 1


def test_complete_control_outputs_are_valid_under_unchanged_v1_freezer():
    for kind in ("phase", "standard", "searching"):
        data = reseal(inputs(kind))
        v1.freeze_output(data["raw"]["response"], data["raw"]["decisions"],
            expected_response_sha256=data["pins"]["response"], expected_decisions_sha256=data["pins"]["decisions"])
    data = reseal(inputs("limit"))
    with pytest.raises(v1.EvaluationError, match="Only COMPLETE"):
        v1.freeze_output(data["raw"]["response"], data["raw"]["decisions"],
            expected_response_sha256=data["pins"]["response"], expected_decisions_sha256=data["pins"]["decisions"])


def test_v1_bytes_are_pinned_and_never_modified():
    assert v1.sha((ROOT / "src/amidst/evaluation/q5_switch_eval.py").read_bytes()) == "0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2"
    assert v1.sha((ROOT / "tests/unit/test_q5_switch_eval.py").read_bytes()) == "786059034fe870c093d04d87d502422cc12b8ba4313768d29b20620c8a504e24"


@pytest.mark.parametrize("legacy_name,legacy_params", legacy_cases())
def test_v1_dispatch_preserves_original_case_results(legacy_name, legacy_params, monkeypatch, tmp_path):
    harness = driver()
    original = v1.compare_script
    def both(frozen, script_raw, *, expected_script_sha256):
        supplied = {"fixture_role": "SYNTHETIC_ONLY", "frozen": frozen,
                    "script_raw": script_raw, "expected_script_sha256": expected_script_sha256}
        try:
            expected = original(frozen, script_raw, expected_script_sha256=expected_script_sha256)
        except v1.EvaluationError as error:
            actual = exercise("dispatch_v1", supplied, harness=harness)
            assert actual.get("error_type") == type(error).__name__ and actual.get("error_message") == str(error)
            raise
        actual = exercise("dispatch_v1", supplied, harness=harness)
        assert v1.canonical(actual["native_report"]) == v1.canonical(expected)
        return expected
    monkeypatch.setattr(LEGACY, "compare_script", both)
    function = getattr(LEGACY, legacy_name)
    kwargs = dict(legacy_params)
    for key in inspect.signature(function).parameters:
        if key not in kwargs:
            kwargs[key] = {"tmp_path": tmp_path, "monkeypatch": monkeypatch}[key]
    function(**kwargs)


def test_standard_core_matches_v1_with_every_user_option_pending():
    data = reseal(inputs("standard", selections=False))
    doc = data["script"]; item = doc["events"][0]
    old_script = {key: doc[key] for key in ("schema_version", "status", "approval_ref", "run_id", "clock_id")}
    old_script.update(schema_version="q5-evaluation-script.v1", events=[{
        "event_id": item["event_id"], "action": item["action"], "decision_window_us": item["decision_window_us"],
        "allowed_camera_ids": list(item["entry_windows_us"]),
        "entry_window_us": item["entry_windows_us"]["SYNTHETIC_C"]["range_us"]}])
    frozen = v1.freeze_output(data["raw"]["response"], data["raw"]["decisions"],
        expected_response_sha256=data["pins"]["response"], expected_decisions_sha256=data["pins"]["decisions"])
    raw = v1.canonical(old_script)
    expected = v1.compare_script(frozen, raw, expected_script_sha256=v1.sha(raw))
    result = exercise("standard", data)
    assert event(result)["match"] == expected["events"][0]["match"] is True
    assert result["observations"]["standard_event_match_ratio"] == expected["event_match_ratio"]


def test_version_is_new_module_and_not_a_v1_extension():
    implementation = required_module()
    assert implementation.VERSION == "q5-switch-eval-v2.0"
    assert Path(implementation.__file__).resolve() == ROOT / "src/amidst/evaluation/q5_switch_eval_v2.py"


@pytest.mark.parametrize("pending", [False, True])
def test_long_gap_phase_and_pending_m1(pending):
    data = inputs()
    if pending:
        data["decisions"]["U-D1"] = "PENDING_USER"
    result = exercise("phase", reseal(data))
    assert event(result)["event_class"] == "LONG_GAP"
    if pending:
        assert result["observations"]["status"] == "NOT_SCORED_PENDING_DECISION"
        assert event(result)["match"] is None and result["observations"]["main_ratio"]["denominator"] == 0
    else:
        assert event(result)["match"] is True
        assert event(result)["return_count"] == 2 and event(result)["searching_count"] == 3
        assert result["observations"]["main_ratio"]["denominator"] == 1


@pytest.mark.parametrize("window,expected", [([700000, 3000000], 2), ([0, 3000000], 3)])
def test_searching_count_uses_opening_start_not_completion_or_index_zero(window, expected):
    data = reseal(inputs("searching")); data["searching_window_us"] = window
    result = exercise("searching_count", data)
    assert result["observations"]["searching_count"] == expected


@pytest.mark.parametrize("pending", [False, True])
def test_limit_cutoff_is_ended_source_time_and_keeps_ratios_separate(pending):
    data = inputs("limit")
    if pending:
        data["decisions"]["U-D4"] = "PENDING_USER"
    result = exercise("limit", reseal(data))
    if pending:
        assert result["observations"]["status"] == "NOT_SCORED_PENDING_DECISION"
        assert all(item["match"] is None for item in result["observations"]["events"])
    else:
        observations = result["observations"]
        assert observations["status"] == "MEASURED_PARTIAL_ENDED_BY_LIMIT"
        assert observations["cutoff_us"] == 6_800_000
        assert event(result, "SYNTHETIC_PREFIX")["match"] is True
        assert event(result, "SYNTHETIC_SUFFIX")["match"] is None
        assert event(result, "SYNTHETIC_SUFFIX")["reason"] == "COVERAGE_MISSING"
        assert observations["main_ratio"]["denominator"] == 0 and observations["partial_ratio"]["denominator"] == 1


@pytest.mark.parametrize("change", ["missing", "foreign_session"])
def test_limit_ended_binding_must_exist(change):
    data = inputs("limit")
    if change == "missing":
        data["records"].pop()
    else:
        data["records"][-1]["session_id"] = "SYNTHETIC_FOREIGN"
    assert_rejected(exercise("limit", reseal(data)), "OUTPUT_INTEGRITY")


def return_input(duration):
    data = inputs("standard"); builder = fixture_module()
    rows = []
    count = 2 if duration >= 1800000 else 1
    for index in range(1, count + 1):
        at = 600000 + (index - 1) * 1000000
        rows.append(builder.row(len(rows), at, searching=index,
                                state_before="PLAYING" if index == 1 else "RETURNING"))
        rows.append(builder.row(len(rows), at, at, "RETURN_TO_ORIGIN", index))
    rows.append(builder.row(len(rows), 12000000, searching=count, state_after="ENDED"))
    data["records"] = rows; data["response"]["timeline"] = []
    event_class = "LONG_LOSS" if duration >= 1800000 else "STANDARD"
    event = dict(event_id="SYNTHETIC_RETURN", action="RETURN_TO_ORIGIN", event_class=event_class,
                 plan_anchor_us={"t_X": 0, "t_N": duration}, decision_window_us=[0, duration + 1000000])
    if event_class == "LONG_LOSS": event["return_count_max"] = 2
    data["script"]["events"] = [event]
    return reseal(data)


@pytest.mark.parametrize("duration,classification", [(1600000, "STANDARD"), (1800000, "LONG_LOSS")])
def test_d94_endpoints_have_positive_controls(duration, classification):
    result = exercise("d94_plan", return_input(duration))
    assert event(result)["event_class"] == classification and event(result)["match"] is True


def test_d94_open_interval_is_rejected_before_scoring():
    assert_rejected(exercise("d94_plan", return_input(1700000)), "D94_FORBIDDEN_INTERVAL")


def test_standard_two_returns_remains_miss_even_when_long_m1_selected():
    data = return_input(1600000); builder = fixture_module()
    data["records"].insert(-1, builder.row(98, 1600000, searching=2, state_before="RETURNING"))
    data["records"].insert(-1, builder.row(99, 1600000, 1600000, "RETURN_TO_ORIGIN", 2))
    result = exercise("d94_plan", reseal(data))
    assert event(result)["event_class"] == "STANDARD" and event(result)["match"] is False


@pytest.mark.parametrize("pair,exit_strip,scored", [(["CAM_EXT_CAR", "CAM_EXT_CLEAR"], True, True),
    (["CAM_BRANCH", "CAM_WIDE"], False, False), (["CAM_W1", "CAM_W2"], True, False)])
def test_d93_overlap_is_fixed_o1_separate_and_closed_for_missing_exit_or_m1(pair, exit_strip, scored):
    data = inputs("standard"); item = data["script"]["events"][0]
    item.update(plan_anchor_us={"t_X": 0, "t_N_by_camera": {}}, decision_window_us=[0, 1600000],
                entry_windows_us={pair[1]: {"kind": "OVERLAP", "range_us": [0, 1600000]}})
    data["records"][0]["source_time_us"] = 600000
    data["records"][1].update(source_time_us=600000, decision_time_us=600000)
    data["response"]["timeline"][0].update(camera_id=pair[1], range_us=[600000, 12000000])
    data["binding_context"] = {"fixture_role": "SYNTHETIC_ONLY", "pair": pair, "exit_strip_present": exit_strip,
                               "real_authority": False}  # Driver seam, not graph wire or G4 approval.
    result = exercise("overlap", reseal(data)); observations = result["observations"]
    assert observations["main_ratio"]["denominator"] == observations["standard_event_match_ratio"]["denominator"] == 0
    if scored:
        assert observations["status"] == "OVERLAP_P_OV2_UNVERIFIED"
        assert event(result)["match"] is True and observations["overlap_ratio"]["denominator"] == 1
        assert event(result)["entry_window_us"] == [0, 1600000]
    else:
        assert observations["status"] == "NOT_SCORED"
        assert event(result)["match"] is None and observations["overlap_ratio"]["denominator"] == 0


def test_window_tampering_is_not_a_model_miss_even_with_fresh_script_pin():
    data = inputs(); data["script"]["events"][0]["decision_window_us"][0] += 1
    assert_rejected(exercise("phase", reseal(data)), "SCRIPT_PLAN_MISMATCH")


@pytest.mark.parametrize("key", ["FUTURE", "U-D3"])
def test_unknown_or_fixed_d93_override_config_key_is_rejected(key):
    data = inputs(selections=False); data["decisions"][key] = "O2" if key == "U-D3" else "PENDING_USER"
    assert_rejected(exercise("phase", reseal(data)), "DECISION_CONFIG_INVALID")


def test_missing_keys_behave_like_pending_not_recommendations():
    data = inputs(selections=False)
    full = exercise("phase", reseal(deepcopy(data)))
    data["decisions"] = {}
    empty = exercise("phase", reseal(data))
    assert empty["observations"]["status"] == full["observations"]["status"] == "NOT_SCORED_PENDING_DECISION"
    assert event(empty)["match"] is event(full)["match"] is None


def long_budget_input(searches):
    data = inputs(); builder = fixture_module()
    gap = 8600000 if searches == 4 else 9600000
    data["records"] = []
    for i in range(searches):
        at = 600000 + i * 1000000
        data["records"].append(builder.row(len(data["records"]), at, searching=i + 1,
                                           state_before="PLAYING" if i == 0 else "RETURNING"))
        action = "SWITCH" if i == searches - 1 else "RETURN_TO_ORIGIN"
        data["records"].append(builder.row(len(data["records"]), gap + 800000 if action == "SWITCH" else at,
            at, action, i + 1, state_after="SWITCHING" if action == "SWITCH" else "RETURNING"))
    switch_id = data["records"][-1]["decision_id"]
    data["records"].append(builder.row(len(data["records"]), 12000000, searching=searches, state_after="ENDED"))
    item = data["script"]["events"][0]
    item.update(plan_anchor_us={"t_X": 0, "t_N_by_camera": {"SYNTHETIC_C": gap}},
        decision_window_us=[0, gap + 1000000], return_count_max=searches - 1,
        entry_windows_us={"SYNTHETIC_C": {"kind": "BLIND", "range_us": [gap - 600000, gap + 1000000]}})
    data["response"]["timeline"][0].update(decision_id=switch_id, range_us=[gap + 800000, 12000000])
    return reseal(data)


def test_selected_budget_positive_control_and_excess_rejection():
    positive = exercise("planned_budget", long_budget_input(4))
    assert event(positive)["match"] is True and event(positive)["searching_count"] == 4
    assert_rejected(exercise("planned_budget", long_budget_input(5)), "PLANNED_SEARCH_BUDGET")


def test_pending_budget_conservatively_rejects_four_round_plan():
    data = long_budget_input(4); data["decisions"]["U-D10"] = "PENDING_USER"
    assert_rejected(exercise("planned_budget", data), "PLANNED_SEARCH_BUDGET")


def test_output_hash_is_checked_before_any_script_file_read(tmp_path, monkeypatch):
    harness = driver(); data = reseal(inputs("standard", selections=False))
    paths = {}
    for name, raw in data["raw"].items():
        paths[name] = tmp_path / f"SYNTHETIC_{name}.json"
        paths[name].write_bytes(raw)
    data["paths"] = paths
    script_path = paths["script"]
    opened = []
    for owner, name in [(builtins, "open"), (io, "open"), (os, "open")]:
        original = getattr(owner, name)
        def spy(file, *args, _original=original, **kwargs):
            if isinstance(file, (str, os.PathLike)) and Path(file).absolute() == script_path:
                opened.append(script_path)
            return _original(file, *args, **kwargs)
        monkeypatch.setattr(owner, name, spy)
    damaged = deepcopy(data); damaged["pins"]["response"] = "0" * 64
    result = exercise("freeze_file_order", damaged, harness=harness)
    assert_rejected(result, "OUTPUT_INTEGRITY")
    assert opened == []
    positive = exercise("freeze_file_order", data, harness=harness)
    assert not positive.get("rejected") and opened  # Reject-everything cannot pass.
