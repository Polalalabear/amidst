"""評分端；與推論隔離。SYNTHETIC returns; no actual yyin data or expected answers.

The optional driver returns a TEST_ONLY assertion view, not a production receipt
schema. Missing CQ-29 orchestration skips normally and fails with REQUIRE_IMPL.
"""

import csv
import importlib
import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
builder = pytest.importorskip("build_team_review_pack")
importer = pytest.importorskip("import_team_review_pack")


def csv_raw(columns, rows, *, bom=True, newline="\n"):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator=newline)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig" if bom else "utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def assert_no_generated_query_hash(value):
    if isinstance(value, dict):
        assert "query_sha256" not in value
        for child in value.values():
            assert_no_generated_query_hash(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_generated_query_hash(child)


@pytest.fixture
def bundle(tmp_path):
    pack = tmp_path / "SYNTHETIC-main-pack"
    pack.mkdir()
    original = [{"編號": f"Q{i:04d}"} for i in range(1, 15)]
    rows = []
    for index in range(1, 15):
        row = {column: "" for column in builder.TEXT_COLUMNS}
        row.update({"編號": f"Q{index:04d}", "使用者會說的話": f"SYNTHETIC 流程測試 {index}，不是組員題目",
                    "想找什麼(人/車/相機)": "相機", "開始時間": "13:00:00", "結束時間": "13:00:05",
                    "鏡頭或區域": "CAM_SYNTHETIC", "系統該反問嗎(是/否)": "否",
                    "預期結果(找得到/找不到/不支援/超出時間/反問)": "找得到"})
        result_column = builder.TEXT_COLUMNS[8]
        keyword, target = "完整找到", "不適用"
        if index in {3, 4}:
            row[builder.TEXT_COLUMNS[1]] += "，追這個人"
            row[builder.TEXT_COLUMNS[2]] = "人"
            row[builder.TEXT_COLUMNS[3]] = "紅" if index == 3 else "藍"
            row[result_column], keyword, target = "", "只測解析", "追人"
        elif index in {5, 6}:
            row[builder.TEXT_COLUMNS[7]] = "是"
            row[result_column], keyword = "反問", "需要澄清"
        elif index in {7, 8}:
            row[result_column] = "不支援"
            keyword = "類別不支援" if index == 7 else "條件不支援"
        elif index == 10:
            row[result_column], keyword = "找不到", "完整未找到"
        elif index == 11:
            row[result_column], keyword = "超出時間", "完全超時"
            row[builder.TEXT_COLUMNS[4]], row[builder.TEXT_COLUMNS[5]] = "14:00:00", "14:00:05"
        elif index == 12:
            row[result_column], keyword = "", "部分涵蓋"
        camera_note = "｜鏡頭=CAM_SYNTHETIC:看得到" if row[result_column] in {"找得到", "找不到"} else ""
        row[builder.TEXT_COLUMNS[-1]] = f"關鍵字={keyword}｜目標={target}{camera_note}｜說明=SYNTHETIC 格式探針 {index}，不是正式答案"
        if index == 1:
            row[builder.TEXT_COLUMNS[4]] = "2026-10-01T13:00:00+08:00"
            row[builder.TEXT_COLUMNS[5]] = "2026-10-01T13:00:05+08:00"
        rows.append(row)
    text_template = csv_raw(builder.TEXT_COLUMNS, original)
    review_template = csv_raw(builder.REVIEW_COLUMNS, [])
    frozen = {builder.TEXT_FILE: text_template, "templates/情境.csv": text_template,
              builder.REVIEW_FILE: review_template, "templates/審查表.csv": review_template,
              "fixed/SYNTHETIC.txt": b"SYNTHETIC immutable fixture\n"}
    for name, raw in frozen.items():
        path = pack / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = {"schema_version": "team-review-pack.v1", "version": "v0-pilot", "evaluation_eligible": False,
                "files": {name: builder.sha(raw) for name, raw in frozen.items()}, "samples": [],
                "editable_files": {
                    builder.TEXT_FILE: {"template_ref": "templates/情境.csv", "locked_columns": ["編號"]},
                    builder.REVIEW_FILE: {"template_ref": "templates/審查表.csv", "locked_columns": builder.REVIEW_COLUMNS[:3]}}}
    raw = builder.canonical(manifest) + b"\n"
    (pack / "MANIFEST.json").write_bytes(raw)
    returns = pack / "RETURN"
    returns.mkdir()
    s2 = returns / "情境_yyin_SYNTHETIC.csv"
    s2.write_bytes(csv_raw(builder.TEXT_COLUMNS, rows))
    # These three columns are only the test-driver view. CQ-28's real s1 CSV
    # columns/receipt are not adopted by this fixture.
    s1_columns = ["題號", "答案", "備註"]
    s1_rows = [{"題號": f"SYNTHETIC-S1-{i}", "答案": answer, "備註": "SYNTHETIC"}
               for i, answer in enumerate(["A", "都不是", "看不出來"], 1)]
    s1 = returns / "s1_審圖_SYNTHETIC.csv"
    s1.write_bytes(csv_raw(s1_columns, s1_rows))
    s0 = returns / "s0_templates_審查表.csv"
    s0.write_bytes(b"SYNTHETIC s0 hash probe, not the 10-25 template\n")
    return {"pack": pack, "manifest_sha256": builder.sha(raw), "s2_csv": s2, "s1_csv": s1,
            "s0_csv": s0, "expected_s0_sha256": builder.sha(s0.read_bytes()), "rows": rows,
            "s1_columns": s1_columns, "s1_rows": s1_rows, "output": tmp_path / "SYNTHETIC-import-output"}


def current_import(bundle):
    return importer.import_pack(bundle["pack"], manifest_sha256=bundle["manifest_sha256"],
                                text_csv=bundle["s2_csv"], output=bundle["output"])


@pytest.mark.parametrize("bom", [True, False])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_existing_importer_accepts_bom_and_csv_line_endings_without_text_rewrite(bundle, bom, newline):
    raw = csv_raw(builder.TEXT_COLUMNS, bundle["rows"], bom=bom, newline=newline)
    bundle["s2_csv"].write_bytes(raw)
    report = current_import(bundle)
    assert report["pack_manifest_sha256"] == bundle["manifest_sha256"]
    assert report["returned_files_sha256"][builder.TEXT_FILE] == builder.sha(raw)
    assert report["evaluation_eligible"] is False
    rows = read_jsonl(bundle["output"] / "invalid_rows.jsonl")
    assert len(rows) == 14
    assert {row["reason"] for row in rows} == {"PRECISE_HUMAN_ANNOTATION_REQUIRED"}
    assert rows[0]["submitted"][builder.TEXT_COLUMNS[1]] == bundle["rows"][0][builder.TEXT_COLUMNS[1]]
    for file in bundle["output"].glob("*.json*"):
        for line in file.read_bytes().splitlines():
            assert_no_generated_query_hash(json.loads(line))


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_existing_csv_reader_preserves_formula_prefix_without_apostrophe_neutralization(bundle, prefix):
    text = prefix + "SYNTHETIC formula probe"
    bundle["rows"][0][builder.TEXT_COLUMNS[1]] = text
    raw = csv_raw(builder.TEXT_COLUMNS, bundle["rows"])
    headers, rows = importer.read_csv(raw)
    assert headers == builder.TEXT_COLUMNS
    assert rows[0][builder.TEXT_COLUMNS[1]] == text
    assert not rows[0][builder.TEXT_COLUMNS[1]].startswith("'")
    # This only checks the existing decoder; rejection/recording is a pending
    # orchestration test below, not an already implemented security gate.


@pytest.mark.parametrize("mutation", ["missing_id", "duplicate_id", "changed_fixed"])
def test_existing_importer_rejects_missing_duplicate_ids_and_fixed_hash_changes(bundle, mutation):
    if mutation == "missing_id":
        bundle["rows"].pop()
    elif mutation == "duplicate_id":
        bundle["rows"][1]["編號"] = bundle["rows"][0]["編號"]
    else:
        (bundle["pack"] / "fixed/SYNTHETIC.txt").write_bytes(b"SYNTHETIC changed\n")
    bundle["s2_csv"].write_bytes(csv_raw(builder.TEXT_COLUMNS, bundle["rows"]))
    with pytest.raises(builder.PackError):
        current_import(bundle)
    assert not bundle["output"].exists()


@pytest.fixture
def driver():
    name = os.environ.get("AMIDST_YYIN_RETURN_TEST_DRIVER")
    strict = os.environ.get("AMIDST_REQUIRE_IMPL") == "1"
    def missing(**kwargs):
        pytest.fail("CQ-29 implementation MISSING: configure a real TEST_ONLY orchestration adapter", pytrace=False)
    if not name:
        if strict:
            return missing
        pytest.skip("CQ-29 orchestration MISSING; no TEST_ONLY adapter configured")
    if strict:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            return missing
    else:
        module = pytest.importorskip(name)
    assert getattr(module, "TEST_ONLY", None) == "SYNTHETIC", "Adapter must declare test scope"
    assert callable(getattr(module, "probe_return", None)), "TEST_ONLY probe_return required"
    return module.probe_return


def probe(driver, bundle):
    # The adapter maps the real implementation to this assertion view. These
    # keyword arguments and view keys are not a new production wire contract.
    return driver(**{key: bundle[key] for key in ["pack", "manifest_sha256", "s2_csv", "s1_csv",
                   "s0_csv", "expected_s0_sha256", "output"]})


@pytest.mark.parametrize("answer", ["A", "B", "C", "都不是", "看不出來"])
def test_main_flow_complete_records_manifest_and_both_csv_hashes(driver, bundle, answer):
    bundle["s1_rows"][0]["答案"] = answer
    bundle["s1_csv"].write_bytes(csv_raw(bundle["s1_columns"], bundle["s1_rows"]))
    view = probe(driver, bundle)
    assert view["test_only"] == "SYNTHETIC"
    assert view["receipt_status"] == "VALID"
    assert view["raw_verify_status"] == "VERIFIED"  # #240 tool value, not silently renamed VALID
    assert view["manifest_sha256"] == bundle["manifest_sha256"]
    assert view["s2_csv_sha256"] == builder.sha(bundle["s2_csv"].read_bytes())
    assert view["s1_csv_sha256"] == builder.sha(bundle["s1_csv"].read_bytes())
    assert all(row["status"] == "VALID" for row in view["s1_rows"])
    assert_no_generated_query_hash(view["imported_rows"])


def test_main_flow_incomplete_is_received_without_formal_denominator(driver, bundle):
    path = bundle["s2_csv"].with_name("情境_yyin_SYNTHETIC_INCOMPLETE.csv")
    bundle["s2_csv"].rename(path)
    bundle["s2_csv"] = path
    view = probe(driver, bundle)
    assert view["received"] is True
    assert view["s2_status"] == "_INCOMPLETE"
    assert view["s2_evaluation_eligible"] is False


@pytest.mark.parametrize("name", ["templates/情境.csv", "templates/審查表.csv"])
def test_main_flow_missing_template_is_warning_pending_human_decision(driver, bundle, name):
    (bundle["pack"] / name).unlink()
    view = probe(driver, bundle)
    assert view["receipt_status"] == "VALID_WITH_WARNINGS"
    assert view["raw_verify_status"] == "VALID_WITH_WARNINGS"
    assert view["pending_decisions"]
    assert name in json.dumps(view["pending_decisions"], ensure_ascii=False)
    assert view["imported"] is False  # #240 requires source-pinned restoration and re-verification


@pytest.mark.parametrize("mutation", ["changed_fixed", "extra_file"])
def test_main_flow_modified_or_extra_files_invalid_without_import(driver, bundle, mutation):
    path = bundle["pack"] / ("fixed/SYNTHETIC.txt" if mutation == "changed_fixed" else "SYNTHETIC-extra.txt")
    path.write_bytes(b"SYNTHETIC mutation\n")
    view = probe(driver, bundle)
    assert view["receipt_status"] == view["raw_verify_status"] == "INVALID"
    assert view["imported"] is False


@pytest.mark.parametrize("bom", [True, False])
def test_main_flow_accepts_bom_and_keeps_return_bytes_pin(driver, bundle, bom):
    raw = csv_raw(builder.TEXT_COLUMNS, bundle["rows"], bom=bom)
    bundle["s2_csv"].write_bytes(raw)
    assert probe(driver, bundle)["s2_csv_sha256"] == builder.sha(raw)


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_main_flow_formula_prefix_rejected_and_recorded_without_rewrite(driver, bundle, prefix):
    text = prefix + "SYNTHETIC formula probe"
    bundle["rows"][0][builder.TEXT_COLUMNS[1]] = text
    raw = csv_raw(builder.TEXT_COLUMNS, bundle["rows"])
    bundle["s2_csv"].write_bytes(raw)
    view = probe(driver, bundle)
    assert view["receipt_status"] == "INVALID"
    assert view["formula_rejections"][0]["submitted"] == text
    assert view["imported"] is False
    assert bundle["s2_csv"].read_bytes() == raw


@pytest.mark.parametrize("mutation", ["missing", "reordered"])
def test_main_flow_missing_or_reordered_ids_rejected_with_reason(driver, bundle, mutation):
    if mutation == "missing":
        bundle["rows"].pop()
    else:
        bundle["rows"][0], bundle["rows"][1] = bundle["rows"][1], bundle["rows"][0]
    bundle["s2_csv"].write_bytes(csv_raw(builder.TEXT_COLUMNS, bundle["rows"]))
    view = probe(driver, bundle)
    assert view["receipt_status"] == "INVALID"
    assert view["rejection_reasons"]
    assert view["imported"] is False


@pytest.mark.parametrize("answer", ["T", "D", "", "UNKNOWN"])
def test_main_flow_invalid_s1_row_does_not_discard_other_rows(driver, bundle, answer):
    bundle["s1_rows"][0]["答案"] = answer
    bundle["s1_csv"].write_bytes(csv_raw(bundle["s1_columns"], bundle["s1_rows"]))
    rows = probe(driver, bundle)["s1_rows"]
    assert rows[0]["status"] == "INVALID"
    assert [r["status"] for r in rows[1:]] == ["VALID", "VALID"]
    assert [r["answer"] for r in rows[1:]] == ["都不是", "看不出來"]


@pytest.mark.parametrize("mutation,expected", [("match", "MATCH"), ("mismatch", "MISMATCH"), ("missing", "MISSING")])
def test_main_flow_s0_pin_never_auto_accepts_missing_or_changed_resubmission(driver, bundle, mutation, expected):
    if mutation == "mismatch":
        bundle["s0_csv"].write_bytes(b"SYNTHETIC mismatching resubmission\n")
    elif mutation == "missing":
        bundle["s0_csv"].unlink()
    view = probe(driver, bundle)
    assert view["s0_hash_status"] == expected
    if expected != "MATCH":
        assert view["pending_decisions"]
        assert view["s0_accepted"] is False
