"""評分端；與推論隔離。CQ-25-T uses SYNTHETIC annotations and frozen outputs only."""

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_p2_report.py"
if not SCRIPT.is_file():
    if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
        pytest.fail("CQ-25-T checker implementation required", pytrace=False)
    pytest.skip("CQ-25-T checker implementation not delivered", allow_module_level=True)
spec = importlib.util.spec_from_file_location("p2_report_check", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture
def sample(tmp_path):
    folder = tmp_path / "SYNTHETIC"
    shutil.copytree(ROOT / "tests/fixtures/p2_report/SYNTHETIC", folder)
    return folder, folder / "receipt.json", folder / "report.json"


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_bytes(m.canonical(value) + b"\n")


def mutate_ref(sample, key, change):
    folder, receipt, _ = sample
    document = read(receipt)
    ref = document[key]
    value = read(folder / ref["path"])
    change(value)
    write(folder / ref["path"], value)
    ref["sha256"] = m.sha((folder / ref["path"]).read_bytes())
    write(receipt, document)


def regenerate(sample):
    _, receipt, report = sample
    value = m.recompute(receipt, synthetic_only=True)
    write(report, value)
    report.with_suffix(".md").write_text(m.markdown(value))
    return value


def test_frozen_synthetic_report_recomputes_exactly(sample):
    _, receipt, report = sample
    result = m.check_report(report, receipt, synthetic_only=True)
    assert result["ok"] and result["status"] == "SYNTHETIC_ONLY_PASS"
    value = read(report)
    assert value["formal_eligible"] is False
    assert value["identity"] == "UNCONFIRMED" and value["physical"] == "UNKNOWN"


def test_default_refuses_unadopted_formal_envelope_before_script_read(sample, monkeypatch):
    _, receipt, report = sample
    monkeypatch.setattr(m, "read_reference", lambda *a: pytest.fail("must reject before reading inputs"))
    assert "FORMAL_FORMAT_UNKNOWN" in m.check_report(report, receipt)["errors"][0]


def test_hand_calculated_q5_ratios_are_separate_and_unscored_events_are_explicit(sample):
    value = regenerate(sample)
    modes = value["q5"]["RUN_X"]
    assert set(modes) == {"RULE_ONLY", "AGENT_SEQUENTIAL"}
    assert modes["RULE_ONLY"]["measurement"]["event_match_ratio"] == {"numerator": 1, "denominator": 1, "value": 1.0}
    assert modes["AGENT_SEQUENTIAL"]["measurement"]["event_match_ratio"] == {"numerator": 0, "denominator": 1, "value": 0.0}
    for mode in modes.values():
        assert mode["non_scoring_event_ids"] == ["SYNTHETIC-NONSCORING"]
        assert mode["measurement"]["coverage_missing_event_ids"] == ["SYNTHETIC-NO-SWITCH"]
        assert mode["measurement"]["event_count"] == 2


def test_hand_annotated_q1_and_q3_details_without_formal_synthetic_credit(sample):
    value = regenerate(sample)
    q1, q3 = value["q1"], value["q3"]
    assert q1["synthetic_metrics"]["status"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert q1["synthetic_metrics"]["camera_micro_recall"] == {"numerator": 2, "denominator": 4, "value": 0.5}
    assert q1["formal_case_count"] == q3["formal_case_count"] == 0
    assert q3["status_accuracy"] == {"numerator": 0, "denominator": 0, "value": None}
    assert [d["status_correct"] for d in q3["details"]] == [True, True]
    assert q3["details"][0]["fields"] == {k: True for k in ["intent", "class", "color", "time_us", "camera", "region"]}
    assert q3["details"][1]["fields"]["class"] is False
    assert value["q3_synthetic_aggregate"] == "MISSING_IN_PINNED_SCORER"


def test_changed_output_byte_is_rejected_before_script_read(sample, monkeypatch):
    folder, receipt, report = sample
    ref = read(receipt)["outputs"][0]
    path = folder / ref["path"]
    path.write_bytes(path.read_bytes() + b" ")
    original = m.read_reference
    def checked(root, reference):
        assert "script" not in reference["path"]
        return original(root, reference)
    monkeypatch.setattr(m, "read_reference", checked)
    result = m.check_report(report, receipt, synthetic_only=True)
    assert "FILE_HASH_MISMATCH" in result["errors"][0]


@pytest.mark.parametrize("change,needle", [
    (lambda d: d["outputs"].pop(0), "OUTPUT_REFERENCE_MISSING"),
    (lambda d: d.update(frozen_at="2030-01-01T00:00:00Z"), "FREEZE_ORDER_INVALID"),
    (lambda d: d.update(formal_eligible=True), "TEST_ONLY_INPUT_REQUIRED"),
    (lambda d: d["runs"][0]["modes"].pop("RULE_ONLY"), "BOTH_MODES_REQUIRED"),
    (lambda d: d["annotations"].update(sha256="0" * 64), "FILE_HASH_MISMATCH"),
])
def test_receipt_fail_closed_mutations(sample, change, needle):
    _, receipt, report = sample
    value = read(receipt)
    change(value)
    write(receipt, value)
    assert needle in m.check_report(report, receipt, synthetic_only=True)["errors"][0]


@pytest.mark.parametrize("status", ["PARTIAL", "ENDED_BY_LIMIT"])
def test_noncomplete_v1_modes_are_listed_without_score(sample, status):
    folder, receipt, _ = sample
    value = read(receipt)
    ref = next(r for r in value["outputs"] if r["path"] == "rule.response.json")
    response = read(folder / ref["path"])
    response["status"] = status
    response["output_sha256"] = m.q5.digest(response, "output_sha256")
    write(folder / ref["path"], response)
    ref["sha256"] = m.sha((folder / ref["path"]).read_bytes())
    write(receipt, value)
    measured = regenerate(sample)["q5"]["RUN_X"]["RULE_ONLY"]
    assert measured["measurement"] is None
    assert measured["not_scored_reason"] == status


def test_non_scoring_event_cannot_sneak_into_denominator(sample):
    folder, receipt, report = sample
    value = read(receipt)
    ref = value["runs"][0]["script"]
    script = read(folder / ref["path"])
    script["events"][1]["event_id"] = "SYNTHETIC-NONSCORING"
    write(folder / ref["path"], script)
    ref["sha256"] = m.sha((folder / ref["path"]).read_bytes())
    write(receipt, value)
    assert "SCRIPT_ANNOTATION_EVENT_SPLIT_MISMATCH" in m.check_report(report, receipt, synthetic_only=True)["errors"][0]


@pytest.mark.parametrize("kind", ["json_number", "md_number", "md_identity", "md_physical", "md_untraced"])
def test_report_mutation_fails_recomputation_or_exact_markdown(sample, kind):
    _, receipt, report = sample
    if kind == "json_number":
        value = read(report)
        value["q1"]["synthetic_metrics"]["status"]["value"] = 0.99
        write(report, value)
    else:
        md = report.with_suffix(".md")
        replacements = {"md_number": ("0.5", "0.9"), "md_identity": ("UNCONFIRMED", "身分確認"),
                        "md_physical": ("UNKNOWN", "可通行"), "md_untraced": ("SYNTHETIC", "SYNTHETIC 987654")}
        a, b = replacements[kind]
        md.write_text(md.read_text().replace(a, b, 1))
    result = m.check_report(report, receipt, synthetic_only=True)
    assert not result["ok"]


def test_all_numeric_leaves_have_input_hash_provenance_and_md_rows(sample):
    value = regenerate(sample)
    numbers = dict(m.numeric_leaves(value, exclude={"numeric_provenance"}))
    assert set(numbers) == set(value["numeric_provenance"])
    known = set(value["input_hashes"].values())
    text = sample[2].with_suffix(".md").read_text()
    for pointer, number in numbers.items():
        hashes = value["numeric_provenance"][pointer]
        assert hashes and set(hashes) <= known
        assert f"`{pointer}` | `{json.dumps(number)}`" in text
    assert value["latency_ms"]["RUN_X"]["AGENT_SEQUENTIAL"] is None
    assert value["latency_ms"]["RUN_X"]["RULE_ONLY"] == 12


def test_symlink_ref_is_rejected(sample):
    folder, receipt, report = sample
    ref = read(receipt)["outputs"][0]
    original = folder / ref["path"]
    target = folder / "SYNTHETIC-symlink-target.json"
    original.rename(target)
    original.symlink_to(target)
    assert "REGULAR_RELATIVE_FILE_REQUIRED" in m.check_report(report, receipt, synthetic_only=True)["errors"][0]


def test_cli_requires_opt_in_and_recomputes_static_fixture(sample, capsys):
    _, receipt, report = sample
    args = ["--report", str(report), "--inputs", str(receipt)]
    assert m.main(args) == 1
    assert m.main(args + ["--synthetic-only"]) == 0
    assert "SYNTHETIC_ONLY_PASS" in capsys.readouterr().out
