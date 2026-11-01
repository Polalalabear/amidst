"""G4-A-T: D101-1 option A checks for the selected G4 receipt copy on #348. Test-first; Codex submits the copy.

Synthetic receipts cover every rule's PASS and FAIL case. The real-head test reads
the #348 receipt: red until the selected copy lands (xfail), strict under
AMIDST_REQUIRE_IMPL=1. AMIDST_G4_RECEIPT=<path> points it at a specific file.
Depends on scripts/check_g4_receipt.py (#352) for the canonical payload hash.
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_g4_option_a.py"
RECEIPT_CHECKER = ROOT / "scripts/check_g4_receipt.py"
STRICT = os.environ.get("AMIDST_REQUIRE_IMPL") == "1"
DRAFT_HEAD = "ac70ed75e4503ab54ec58c08ec58957c179bb72c"  # #348 draft, before the selected copy
DRAFT_PATH = "docs/engineering/R004_G4_RECEIPT_DRAFT_20261028.json"

pytestmark = pytest.mark.skipif(
    not RECEIPT_CHECKER.exists() and not STRICT,
    reason="scripts/check_g4_receipt.py (#352) is not on this branch yet")

spec = importlib.util.spec_from_file_location("g4_option_a", SCRIPT)
option_a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(option_a)
A4, B4 = option_a.A4, option_a.B4
UNLISTED = ["T_CAM_EXT_CAR__CAM_W2", "T_CAM_EXT_CLEAR__CAM_W2", "T_CAM_W2__CAM_EXT_CAR", "T_CAM_W2__CAM_EXT_CLEAR"]
EDGES = ["E_CORNER_N", "E_OUT_VEST", "E_PORTAL_R101", "E_PORTAL_R102", "E_VEST_CORR", "E_W_CORNER"]


def sha(n):
    return f"{n:x}".rjust(64, "0")


def build_receipt():
    """A synthetic option-A copy shaped like #348's draft; not a real approval."""
    edges = []
    for edge_id in EDGES:
        row = {"edge_id": edge_id, "run_ids": [A4, B4], "allowed_purposes": []}
        if edge_id in option_a.APPROVED_EDGES:
            row.update(traversability="APPROVED", state="APPROVED", run_ids=option_a.APPROVED_EDGES[edge_id])
        elif edge_id == "E_PORTAL_R102":
            row.update(traversability="TOPOLOGICAL_ONLY", state="UNKNOWN")
        else:
            row.update(traversability="NOT_APPROVED", state="NOT_APPROVED")
        edges.append(row)
    transitions = []
    for run, ids in option_a.APPROVED_TRANSITIONS.items():
        transitions += [{"transition_id": t, "run_ids": [run], "decision": "APPROVED"} for t in ids]
    transitions += [{"transition_id": t, "run_ids": [], "decision": "UNKNOWN"} for t in option_a.M1]
    transitions += [{"transition_id": t, "run_ids": [], "decision": "NOT_APPROVED"} for t in UNLISTED]
    for t in transitions:
        t["allowed_purposes"] = []
        a, _, b = t["transition_id"][2:].partition("__")
        t.update(from_camera_id=a, to_camera_id=b, via_exit_zone_ids=[], to_entry_zone_ids=[],
                 region_path=[], edge_path=["E_X"] if t["decision"] == "APPROVED" else [])
    transitions.sort(key=lambda r: r["transition_id"])
    regions = [{"region_id": f"R{i}", "run_ids": [A4, B4], "decision": "UNKNOWN", "allowed_purposes": [], "exclusions": []}
               for i in range(7)]
    pins = {"scene_id": "controlled_scene_v1_s001", "scene_revision": "r004"}
    for i, key in enumerate(["source_sha256", "catalog_sha256", "static_sha256", "region_graph_content_sha256",
                             "camera_graph_content_sha256"]):
        pins[key] = sha(i + 1)
    pins.update({k: v[1] for k, v in option_a.GRAPH_PINS.items()})
    pins["run_camera_scopes"] = [
        {"run_id": A4, "camera_ids": ["CAM_W1"], "allowed_purposes": [], "exclusions": []},
        {"run_id": B4, "camera_ids": ["CAM_W1"], "allowed_purposes": [], "exclusions": []},
    ]
    doc = {
        "schema_version": "q-demo.g4-approval-receipt-draft.v1", "status": "PROPOSED", "date": "2026-11-02",
        "approval_ref": None, "human_decision_ref": None, "independent_review_ref": None,
        "input_pins": pins, "edge_decisions": edges, "transition_decisions": transitions,
        "region_purpose_decisions": regions,
        "derived_legal_transitions_by_run": [{"run_id": A4, "transition_ids": []}, {"run_id": B4, "transition_ids": []}],
        "approved_purposes": [], "exclusions": [],
        "provenance": {"gt_read": False, "graph_ref": f"#294@{option_a.GRAPH_COMMIT}"},
    }
    return rehash(doc)


def rehash(doc):
    doc["decisions_sha256"] = option_a.load_receipt_checker().decisions_sha256(doc)
    return doc


def verdicts(doc):
    return {r["id"]: r["status"] for r in option_a.run_checks(doc)}


def edge(doc, name):
    return next(r for r in doc["edge_decisions"] if r["edge_id"] == name)


def trans(doc, name):
    return next(r for r in doc["transition_decisions"] if r["transition_id"] == name)


def only_fails(doc, *expected):
    failed = {k for k, v in verdicts(doc).items() if v == "FAIL"}
    assert failed == set(expected)


def test_synthetic_option_a_copy_passes_everything():
    assert set(verdicts(build_receipt()).values()) == {"PASS"}


def test_approved_set_is_16_transitions_and_4_edges():
    assert [len(v) for v in option_a.APPROVED_TRANSITIONS.values()] == [4, 12]
    assert set(option_a.APPROVED_EDGES) == {"E_OUT_VEST", "E_VEST_CORR", "E_W_CORNER", "E_PORTAL_R101"}


def test_edge_left_pending_fails():
    doc = build_receipt()
    edge(doc, "E_W_CORNER").update(traversability="PENDING_USER", state="PENDING_USER")
    only_fails(rehash(doc), "A1_edges_approved")


def test_edge_with_wrong_run_scope_fails():
    doc = build_receipt()
    edge(doc, "E_OUT_VEST")["run_ids"] = [A4, B4]
    only_fails(rehash(doc), "A1_edges_approved")


def test_extra_approved_edge_fails():
    doc = build_receipt()
    edge(doc, "E_PORTAL_R102").update(traversability="APPROVED", state="APPROVED")
    only_fails(rehash(doc), "A2_edges_rest_unapproved")


@pytest.mark.parametrize("value", ["APPROVED", "UNKNOWN", "PENDING_USER"])
def test_corner_n_must_be_not_approved(value):
    doc = build_receipt()
    edge(doc, "E_CORNER_N").update(traversability=value, state=value)
    assert verdicts(rehash(doc))["A3_corner_n_not_approved"] == "FAIL"


def test_approved_transition_pending_fails():
    doc = build_receipt()
    trans(doc, "T_CAM_W1__CAM_EXT_CAR")["decision"] = "PENDING_USER"
    only_fails(rehash(doc), "A4_transitions_approved")


def test_approved_transition_on_wrong_run_fails():
    doc = build_receipt()
    trans(doc, "T_CAM_EXT_CAR__CAM_W1")["run_ids"] = [B4]
    only_fails(rehash(doc), "A4_transitions_approved")


@pytest.mark.parametrize("direction", ["T_CAM_W1__CAM_W2", "T_CAM_W2__CAM_W1"])
@pytest.mark.parametrize("value", ["APPROVED", "NOT_APPROVED", "PENDING_USER"])
def test_m1_each_direction_must_be_unknown(direction, value):
    doc = build_receipt()
    trans(doc, direction)["decision"] = value
    assert verdicts(rehash(doc))["A5_m1_unknown"] == "FAIL"


def test_unlisted_transition_approved_fails():
    doc = build_receipt()
    trans(doc, UNLISTED[0])["decision"] = "APPROVED"
    only_fails(rehash(doc), "A6_rest_unapproved")


def test_region_approved_fails():
    doc = build_receipt()
    doc["region_purpose_decisions"][0]["decision"] = "APPROVED"
    only_fails(rehash(doc), "A6_rest_unapproved")


def test_derived_legal_transitions_must_stay_empty():
    doc = build_receipt()
    doc["derived_legal_transitions_by_run"][0]["transition_ids"] = ["T_CAM_EXT_CAR__CAM_W1"]
    only_fails(rehash(doc), "A7_derived_empty")


@pytest.mark.parametrize("where", ["edge", "transition", "region", "scope"])
def test_allowed_purposes_must_be_empty(where):
    doc = build_receipt()
    target = {"edge": edge(doc, "E_OUT_VEST"), "transition": trans(doc, "T_CAM_WIDE__CAM_W1"),
              "region": doc["region_purpose_decisions"][0], "scope": doc["input_pins"]["run_camera_scopes"][0]}[where]
    target["allowed_purposes"] = ["CORR_W"]
    assert verdicts(rehash(doc))["B_allowed_purposes_empty"] == "FAIL"


def test_hash_mismatch_fails():
    doc = build_receipt()
    trans(doc, "T_CAM_WIDE__CAM_W1")["decision"] = "UNKNOWN"  # edited after hashing
    assert verdicts(doc)["C_hash_recompute"] == "FAIL"


@pytest.mark.parametrize("name", ["draft_pending", "reference"])
def test_forbidden_hashes_fail(name):
    doc = build_receipt()
    doc["decisions_sha256"] = option_a.FORBIDDEN_HASHES[name]
    failed = {k for k, v in verdicts(doc).items() if v == "FAIL"}
    assert failed == {"C_hash_recompute", "D_hash_not_forbidden"}


def test_forbidden_hash_values_are_the_full_ones():
    draft, ref = option_a.FORBIDDEN_HASHES["draft_pending"], option_a.FORBIDDEN_HASHES["reference"]
    assert len(draft) == len(ref) == 64
    assert draft.startswith("7ea8c5e5") and draft.endswith("6323")
    assert ref.startswith("f1e0bfe6") and ref.endswith("09a3")


@pytest.mark.parametrize("key", ["camera_graph_file_sha256", "region_graph_file_sha256", "tracking_scope_file_sha256"])
def test_graph_pin_mismatch_fails(key):
    doc = build_receipt()
    doc["input_pins"][key] = sha(99)
    only_fails(rehash(doc), "E_graph_pins")


def test_graph_ref_must_name_0c34287():
    doc = build_receipt()
    doc["provenance"]["graph_ref"] = "#294@" + "1" * 40
    only_fails(rehash(doc), "E_graph_pins")


@pytest.mark.parametrize("key", ["ground_truth", "gt_position", "visibility", "visible_frames", "depth_map", "renderer_trajectory"])
def test_forbidden_keys_fail(key):
    doc = build_receipt()
    doc["provenance"][key] = 1
    only_fails(rehash(doc), "F_no_forbidden_keys")


def test_nested_forbidden_key_and_gt_read_true_fail():
    doc = build_receipt()
    doc["transition_decisions"][0]["recommendation"] = {"depth": 1}
    assert verdicts(rehash(doc))["F_no_forbidden_keys"] == "FAIL"
    doc = build_receipt()
    doc["provenance"]["gt_read"] = True
    assert verdicts(rehash(doc))["F_no_forbidden_keys"] == "FAIL"


def test_malformed_receipt_fails_instead_of_crashing():
    results = option_a.run_checks({"edge_decisions": "nope"})
    assert any(r["status"] == "FAIL" for r in results)


def test_cli_prints_per_check_json_and_exit_code(tmp_path):
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(build_receipt()))
    doc = build_receipt()
    edge(doc, "E_CORNER_N").update(traversability="APPROVED", state="APPROVED")
    bad.write_text(json.dumps(rehash(doc)))
    for path, code, overall in ((good, 0, "PASS"), (bad, 1, "FAIL")):
        run = subprocess.run(["python3", str(SCRIPT), str(path)], capture_output=True, text=True)
        out = json.loads(run.stdout)
        assert (run.returncode, out["overall"]) == (code, overall)
        assert all(c["status"] in {"PASS", "FAIL"} for c in out["checks"])


def real_receipt():
    path = os.environ.get("AMIDST_G4_RECEIPT")
    if path:
        return Path(path).read_bytes()
    if (ROOT / DRAFT_PATH).exists():
        return (ROOT / DRAFT_PATH).read_bytes()
    shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{DRAFT_HEAD}:{DRAFT_PATH}"], capture_output=True)
    return shown.stdout if shown.returncode == 0 else None


def test_real_348_receipt():
    raw = real_receipt()
    if raw is None:
        if STRICT:
            pytest.fail("#348 receipt not found; set AMIDST_G4_RECEIPT or fetch pull/348/head")
        pytest.skip("#348 receipt not available locally")
    doc = option_a.load_receipt_checker().parse_json(raw)
    failed = [r["id"] for r in option_a.run_checks(doc) if r["status"] == "FAIL"]
    if STRICT:
        assert not failed, failed
    elif failed:
        pytest.xfail("selected option A copy not submitted yet; failing: " + ", ".join(failed))
