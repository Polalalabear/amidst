"""SYNTHETIC-only CQ-21-T; no real G4, GT, source assets or runtime implementation.

The external exercise_case driver is a TEST-ONLY integration seam, not a new
production API. It must call the chosen real implementation after U8; it must
not return fixture answers. Missing implementation skips only outside strict mode.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/g4_receipts/SYNTHETIC"
spec = importlib.util.spec_from_file_location("cq21_receipt_checker", ROOT / "scripts/check_g4_receipt.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

OPTIONS = {
    "A1": ["TOP_LEVEL_FIELDS", "HEADER_OBJECT"],
    "A2": ["DOCUMENTS_SCENE_BUNDLE", "REGISTRY_V2_PER_RUN"],
    "A3": ["COORDINATOR_PUBLICATION_BINDING", "SECOND_HUMAN_BYTES_APPROVAL"],
    "A4": ["EMBEDDED_REF_TEXT_HASHES", "FORMAT_ONLY_PROCESS_TRUST"],
    "A5": ["PINNED_RUN_REGISTRATION", "DEDICATED_BINDINGS_DOCUMENT"],
    "B1": ["EXPLICIT_GATE_TABLE", "DERIVED_ALL_SCOPE_GATES"],
    "B2": ["CONSERVATIVE_ZERO_EDGE", "EXPLICIT_SAME_REGION_AUTHORITY"],
    "B3": ["CLOSED_OPERATION_PURPOSES", "SINGLE_TRACKING_PURPOSE"],
    "C1": ["IMMUTABLE_REVALIDATED_BINDING", "ATOMIC_GENERATION_RELOAD"],
    "C2": ["VERSIONED_INLINE_PROVENANCE", "PINNED_EXTERNAL_PROVENANCE"],
    "C3": ["PINNED_FAIL_CLOSED", "LEGACY_READ_ONLY_NO_OVERLAY"],
}


def read(name):
    return json.loads((FIXTURE / name).read_bytes())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unavailable(message):
    if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def driver():
    name = os.environ.get("AMIDST_G4_OVERLAY_DRIVER", "amidst.q1q5.receipt_overlay")
    try:
        module = pytest.importorskip(name, reason="CQ-21 implementation / TEST-ONLY driver is absent")
    except pytest.skip.Exception:
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ21_IMPLEMENTATION_MISSING: strict mode forbids missing-implementation skip", pytrace=False)
        raise
    if not callable(getattr(module, "exercise_case", None)):
        unavailable("CQ21_TEST_DRIVER_UNBOUND: exercise_case is a TEST-ONLY seam, not a production API")
    return module


def contract_options():
    value = os.environ.get("AMIDST_RECEIPT_CONTRACT")
    if not value:
        unavailable("CQ21_CONTRACT_UNSELECTED: no implicit recommendation or authority")
    try:
        options = json.loads(value if value.lstrip().startswith("{") else Path(value).read_text())
    except (ValueError, OSError) as exc:
        pytest.fail("Invalid explicit test contract JSON: " + str(exc))
    if not isinstance(options, dict):
        pytest.fail("Explicit test contract JSON must be an object")
    for group, choices in OPTIONS.items():
        if options.get(group) not in choices:
            unavailable("CQ21_CONTRACT_UNSELECTED: " + group)
    return options


def selected_case_inputs(options, name):
    """Explicit future SYNTHETIC bytes; never upgrade a five-key v1 fixture."""
    case = options.get("_test", {}).get("selected_contract_cases", {}).get(name)
    if not isinstance(case, dict):
        unavailable("CQ21_SELECTED_FIXTURE_UNBOUND: " + name)
    assert case.get("fixture_role") == "SYNTHETIC_ONLY"
    assert isinstance(case.get("receipts"), list) and case["receipts"]
    result = []
    for item in case["receipts"]:
        assert isinstance(item, dict) and isinstance(item.get("raw_utf8"), str)
        raw = item["raw_utf8"].encode("utf-8")
        assert len(raw) <= 1_048_576
        assert not any(value in raw for value in (b"/Users/", b"/private/", b"file://"))
        checker.parse_json(raw)  # Only JSON framing/duplicates; no five-key projection.
        assert digest(raw) == item["file_sha256"]
        assert checker._sha(item["decisions_sha256"])
        assert isinstance(item.get("registry_fragment"), dict)
        result.append({**item, "receipt_bytes": raw})
    return result


def exercise(case_name, *, receipt_name="approved", selected_case=None, **case_inputs):
    implementation = driver()
    options = contract_options()
    graph_names = ["camera_graph.json", "region_graph.json", "tracking_scope.json"]
    before = {name: (FIXTURE / name).read_bytes() for name in graph_names}
    inputs = {
        "fixture_directory": FIXTURE,
        "receipt_bytes": (FIXTURE / ("receipt_" + receipt_name + ".json")).read_bytes(),
        "registry_fragment": read("registry_" + receipt_name + ".json"),
        **case_inputs,
    }
    selected = selected_case_inputs(options, selected_case) if selected_case else None
    if selected is not None:
        inputs["receipt_bytes"] = selected[0]["receipt_bytes"]
        inputs["registry_fragment"] = selected[0]["registry_fragment"]
        inputs["selected_contract_receipts"] = selected
    result = implementation.exercise_case(case_name, inputs=inputs, contract_options=options)
    assert isinstance(result, dict), "TEST-ONLY driver must report observations from actual implementation"
    assert {name: (FIXTURE / name).read_bytes() for name in graph_names} == before
    return result, options, {"graph_bytes_before": before, "selected_receipts": selected}


def no_authority(result):
    assert result["authority_elevated"] is False
    assert result["overlay_applied"] is False
    assert result["published_snapshots"] == []


def at(value, path):
    assert isinstance(path, list) and path and all(isinstance(key, str) and key for key in path)
    for key in path:
        value = value[key]
    return value


def test_synthetic_manifest_and_no_private_locators():
    manifest = read("MANIFEST.json")
    assert manifest["fixture_role"] == "SYNTHETIC_ONLY"
    assert manifest["contract_option"] == "UNSELECTED"
    for name, pin in manifest["files"].items():
        raw = (FIXTURE / name).read_bytes()
        assert digest(raw) == pin
        for forbidden in (b"/Users/", b"/private/", b"file://"):
            assert forbidden not in raw
    assert read("receipt_approved.json")["fixture_role"] == "SYNTHETIC_TEST_ONLY_NOT_HUMAN_APPROVAL"
    options = read("contract_options.UNSELECTED.json")
    assert all(options[group] == "UNSELECTED" for group in OPTIONS)


@pytest.mark.parametrize("name,valid", [("approved", True), ("pending", False), ("decisions_tampered", False), ("registry_pin_mismatch", False), ("draft", False), ("missing_field", False)])
def test_checker_cli_positive_and_negative_fixtures(name, valid):
    command = [sys.executable, str(ROOT / "scripts/check_g4_receipt.py"), "--receipt", str(FIXTURE / ("receipt_" + name + ".json")), "--registry", str(FIXTURE / ("registry_" + name + ".json"))]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == (0 if valid else 1), result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["format_valid"] is valid
    assert report["authority_verified"] is False


def test_checker_uses_golden_five_key_preimage_and_does_not_mutate_inputs():
    receipt = read("receipt_approved.json")
    registry = read("registry_approved.json")
    original = deepcopy((receipt, registry))
    assert checker.decisions_sha256(receipt) == read("MANIFEST.json")["approved_decisions_sha256"]
    report = checker.check_receipt((FIXTURE / "receipt_approved.json").read_bytes(), registry, receipt_relative_path="receipt_approved.json")
    assert report["authority_verified"] is False
    assert (receipt, registry) == original


@pytest.mark.parametrize("change", ["refs", "recommendation", "yyin_opinion", "status_date_provenance"])
def test_refs_opinions_recommendations_and_header_are_excluded_only_by_allowlist(change):
    doc = read("receipt_approved.json"); expected = checker.decisions_sha256(doc)
    if change == "refs":
        doc["approval_ref"] = "SYNTHETIC_DIFFERENT_REF"
        doc["human_decision_ref"] = "SYNTHETIC_DIFFERENT_DECISION_REF"
    elif change in {"recommendation", "yyin_opinion"}:
        doc["transition_decisions"][0][change] = "SYNTHETIC_DIFFERENT_METADATA"
    else:
        doc.update(status="PROPOSED", date="SYNTHETIC_DATE", provenance={"note": "SYNTHETIC"})
    assert checker.decisions_sha256(doc) == expected


@pytest.mark.parametrize("table", list(checker.PAYLOAD_FIELDS))
def test_every_payload_section_changes_hash(table):
    doc = read("receipt_approved.json"); expected = checker.decisions_sha256(doc)
    if table == "input_pins":
        doc[table]["catalog_sha256"] = "f" * 64
    elif table == "edge_decisions":
        doc[table][0]["state"] = "CLOSED"
    elif table == "transition_decisions":
        doc[table][0]["decision"] = "NOT_APPROVED"
    elif table == "region_purpose_decisions":
        doc[table][0]["allowed_purposes"] = []
    else:
        doc[table][0]["transition_ids"] = [doc["transition_decisions"][0]["transition_id"]]
    assert checker.decisions_sha256(doc) != expected


def test_hash_does_not_sort_away_path_direction_and_rejects_unsorted_tables():
    doc = read("receipt_approved.json"); expected = checker.decisions_sha256(doc)
    doc["transition_decisions"][1]["region_path"].reverse()
    assert checker.decisions_sha256(doc) != expected
    doc["transition_decisions"].reverse()
    with pytest.raises(checker.ReceiptCheckError, match="sorted"):
        checker.decisions_sha256(doc)


def test_explicit_unresolved_null_and_ascii_serialization_are_not_dropped():
    doc = read("receipt_approved.json")
    doc["edge_decisions"][0]["state"] = None
    doc["input_pins"]["scene_revision"] = "SYNTHETIC_測試"
    payload = checker.decision_payload(doc)
    assert payload["edge_decisions"][0]["state"] is None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    assert checker.decisions_sha256(doc) == digest(canonical)
    assert checker.decisions_sha256(doc) != digest(canonical + b"\n")
    assert checker.decisions_sha256(doc) != digest(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]'])
def test_checker_rejects_duplicate_nonfinite_and_nonobject_json(raw):
    with pytest.raises(checker.ReceiptCheckError):
        checker.parse_json(raw)


def test_unknown_gate_fields_are_not_silently_excluded_or_adopted():
    doc = read("receipt_approved.json")
    doc["input_pins"]["SYNTHETIC_UNADOPTED_GATE"] = True
    with pytest.raises(checker.ReceiptCheckError, match="field"):
        checker.decisions_sha256(doc)


def test_registry_pin_is_raw_bytes_and_duplicate_matching_documents_fail():
    raw = (FIXTURE / "receipt_approved.json").read_bytes()
    registry = read("registry_approved.json")
    with pytest.raises(checker.ReceiptCheckError, match="bytes pin"):
        checker.check_receipt(raw + b" ", registry, receipt_relative_path="receipt_approved.json")
    registry["documents"]["SYNTHETIC_DUPLICATE"] = deepcopy(next(iter(registry["documents"].values())))
    with pytest.raises(checker.ReceiptCheckError, match="Exactly one"):
        checker.check_receipt(raw, registry, receipt_relative_path="receipt_approved.json")


def test_missing_driver_skip_becomes_failure_in_strict_mode(monkeypatch):
    monkeypatch.setenv("AMIDST_G4_OVERLAY_DRIVER", "SYNTHETIC_CQ21_DRIVER_DOES_NOT_EXIST")
    monkeypatch.delenv("AMIDST_REQUIRE_IMPL", raising=False)
    with pytest.raises(pytest.skip.Exception):
        driver()
    monkeypatch.setenv("AMIDST_REQUIRE_IMPL", "1")
    with pytest.raises(pytest.fail.Exception, match="CQ21_IMPLEMENTATION_MISSING"):
        driver()


def test_missing_selected_contract_fixture_never_upgrades_old_v1_bytes(monkeypatch):
    options = {"_test": {"selected_contract_cases": {}}}
    monkeypatch.delenv("AMIDST_REQUIRE_IMPL", raising=False)
    with pytest.raises(pytest.skip.Exception):
        selected_case_inputs(options, "fully_bound_approved_control")
    monkeypatch.setenv("AMIDST_REQUIRE_IMPL", "1")
    with pytest.raises(pytest.fail.Exception, match="CQ21_SELECTED_FIXTURE_UNBOUND"):
        selected_case_inputs(options, "fully_bound_approved_control")


def staging_snapshot():
    from amidst.q1q5.candidates import transition_candidates
    from amidst.q1q5.graphs import load_graphs
    region, camera, scope = read("region_graph.json"), read("camera_graph.json"), read("tracking_scope.json")
    scope_raw = (FIXTURE / "tracking_scope.json").read_bytes()
    graph = load_graphs(region, camera, region_sha256=region["content_sha256"], camera_sha256=camera["content_sha256"], tracking_scope=scope, tracking_scope_sha256=digest(scope_raw), tracking_scope_bytes=scope_raw)
    return transition_candidates(graph, from_camera_id="SYNTHETIC_A", last_bbox_xyxy_px=[10, 10, 30, 30], session_id="SYNTHETIC_NO_RECEIPT", top_k=3, window_us=[0, 1_000_000], exit_boundary_inclusive=True, allowed_camera_ids=scope["tracking_camera_ids"])


def test_current_staging_no_receipt_three_camera_baseline_is_fail_closed():
    snapshot = staging_snapshot()
    assert snapshot["candidates"] == []
    assert len(snapshot["excluded_transitions"]) == 2
    assert {row["reason"] for row in snapshot["excluded_transitions"]} == {"GRAPH_NOT_APPROVED"}


def test_overlay_without_receipt_matches_current_staging_and_zero_edge_exclusion_priority():
    result, _, _ = exercise("no_receipt", receipt_missing=True)
    expected = staging_snapshot()
    assert result["candidate_snapshot"]["candidates"] == expected["candidates"]
    assert result["candidate_snapshot"]["excluded_transitions"] == expected["excluded_transitions"]
    no_authority(result)


@pytest.mark.parametrize("name", ["decisions_tampered", "registry_pin_mismatch", "missing_field"])
def test_integrity_error_refuses_whole_overlay_without_partial_publication(name):
    result, _, _ = exercise("integrity_rejection", receipt_name=name, selected_case="integrity_rejection." + name)
    assert result["error_code"] == "DataIntegrityError"
    no_authority(result)


@pytest.mark.parametrize("name", ["draft", "pending"])
def test_draft_or_nonapproved_receipt_cannot_elevate(name):
    result, _, _ = exercise("unapproved_receipt", receipt_name=name, selected_case="unapproved_receipt." + name)
    no_authority(result)


def test_fully_bound_control_exercises_real_nonzero_authority_in_selected_contract():
    result, options, _ = exercise("fully_bound_approved_control", selected_case="fully_bound_approved_control")
    assert result["authority_elevated"] is True and result["overlay_applied"] is True
    cameras = {row["camera_id"] for row in result["candidate_snapshot"]["candidates"]}
    assert "SYNTHETIC_C" in cameras, "A reject-everything adapter is not a valid positive control"
    if options["B2"] == "CONSERVATIVE_ZERO_EDGE":
        assert "SYNTHETIC_B" not in cameras


@pytest.mark.parametrize("value", ["PENDING_USER", "UNKNOWN"])
@pytest.mark.parametrize("table,key", [("edge_decisions", "state"), ("transition_decisions", "decision"), ("region_purpose_decisions", "decision")])
def test_unresolved_required_decision_never_elevates_its_transition(table, key, value):
    case = ".".join(["unresolved_decision", table, key, value])
    result, _, _ = exercise("unresolved_decision", selected_case=case, require_fully_bound_control=True,
                             mutation_description={"table": table, "key": key, "value": value})
    assert "SYNTHETIC_C" in {row["camera_id"] for row in result["control_candidate_snapshot"]["candidates"]}
    assert "SYNTHETIC_C" not in {row["camera_id"] for row in result["candidate_snapshot"]["candidates"]}


def test_overlay_preserves_original_graph_bytes_hashes_and_separate_effective_view():
    result, _, context = exercise("immutable_graph_bytes", selected_case="immutable_graph_bytes")
    before = context["graph_bytes_before"]
    assert result["graph_bytes_before"] == before
    assert result["graph_bytes_after"] == before
    assert result["graph_hashes_before"] == result["graph_hashes_after"] == {name: digest(raw) for name, raw in before.items()}


@pytest.mark.parametrize("b1", [pytest.param(value, marks=pytest.mark.contract_option("B1", value)) for value in OPTIONS["B1"]])
def test_single_transition_approval_does_not_approve_graph_scope_or_g4(b1):
    result, options, _ = exercise("single_transition_not_global_gate", selected_case="single_transition_not_global_gate." + b1)
    assert options["B1"] == b1
    no_authority(result)
    assert result["effective_graph_approved"] is False and result["effective_scope_approved"] is False
    assert result["effective_g4_approved"] is False


@pytest.mark.parametrize("c2", [pytest.param(value, marks=pytest.mark.contract_option("C2", value)) for value in OPTIONS["C2"]])
def test_receipt_changes_session_and_exact_response_journal_provenance(c2):
    result, options, context = exercise("receipt_changes_session_and_provenance", selected_case="receipt_changes_session_and_provenance." + c2)
    assert options["C2"] == c2
    sessions = result["sessions"]
    assert len(sessions) == 2 and sessions[0]["session_id"] != sessions[1]["session_id"]
    selected = context["selected_receipts"]
    assert len(selected) == 2 and selected[0]["decisions_sha256"] != selected[1]["decisions_sha256"]
    paths = options.get("_test", {}).get("C2_provenance_paths")
    if not isinstance(paths, dict):
        unavailable("C2 provenance paths are unselected; no guessed production field names")
    for session, expected in zip(sessions, selected, strict=True):
        assert session["receipt_bytes"] == expected["receipt_bytes"]
        assert session["receipt_decisions_sha256"] == expected["decisions_sha256"]
        expected_file = expected["file_sha256"]
        assert at(session, paths["response_file_sha256"]) == expected_file
        assert at(session, paths["response_decisions_sha256"]) == expected["decisions_sha256"]
        assert session["journal"], "At least one real decision/journal record is required"
        for row in session["journal"]:
            assert at(row, paths["journal_file_sha256"]) == expected_file
            assert at(row, paths["journal_decisions_sha256"]) == expected["decisions_sha256"]


def test_same_pinned_generation_bytes_changed_during_reload_fails_before_publication():
    result, _, _ = exercise("same_pinned_generation_bytes_changed", selected_case="same_pinned_generation_bytes_changed",
                             mutate_bytes_of_same_pinned_generation=True, mix_generations=False)
    assert result["error_code"] == "DataIntegrityError"
    no_authority(result)


@pytest.mark.parametrize("c3", [pytest.param(value, marks=pytest.mark.contract_option("C3", value)) for value in OPTIONS["C3"]])
def test_legacy_recording_without_receipt_never_restores_live_authority(c3):
    result, options, _ = exercise("legacy_replay_without_receipt", receipt_missing=True)
    assert options["C3"] == c3
    no_authority(result)
    assert result["live_authority_restored"] is False
    if c3 == "PINNED_FAIL_CLOSED":
        assert result["error_code"] == "DataIntegrityError"
    else:
        assert result["read_only_replay"] is True
        assert result["recorded_bytes_after"] == result["recorded_bytes_before"]
        assert isinstance(result["degraded_marker"], str) and result["degraded_marker"]
