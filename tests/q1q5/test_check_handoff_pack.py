"""Synthetic pack/ZIP mechanics; no original assets, answers, or real returns."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unicodedata
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from build_team_review_pack import LOCKED, REVIEW_COLUMNS, REVIEW_FILE, TEXT_COLUMNS, TEXT_FILE, csv_bytes

SCRIPT = ROOT / "scripts/check_handoff_pack.py"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(doc):
    return json.dumps(doc, ensure_ascii=False, sort_keys=True).encode() + b"\n"


def put(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def module():
    if not SCRIPT.is_file():
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("HANDOFF_CHECKER_IMPLEMENTATION_MISSING")
        pytest.importorskip("check_handoff_pack", reason="HANDOFF_CHECKER_IMPLEMENTATION_MISSING")
        pytest.skip("HANDOFF_CHECKER_LOCAL_SNAPSHOT_MISSING")
    spec = importlib.util.spec_from_file_location("handoff_checker", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fixture(tmp_path, profile="yyin-main"):
    root = tmp_path / "SYNTHETIC_PACK"
    root.mkdir()
    options = {"fixture_role": "SYNTHETIC_ONLY", "profile": profile,
        "projection": "SYNTHETIC_HANDOFF_PROFILE_V1", "readme": "README.txt",
        "zip_timestamp": [1980, 1, 1, 0, 0, 0],
        "text_ids": [f"Q{i:04d}" for i in range(1, 15)],
        "s1": {"filename": "s1/確認.csv", "template_ref": "templates/s1.csv",
               "columns": ["SYNTHETIC_題號", "SYNTHETIC_選項", "SYNTHETIC_備註"],
               "row_ids": ["SYNTHETIC_1", "SYNTHETIC_2", "SYNTHETIC_3"]},
        "return_names": {"s1": "審圖_yyin_YYYY-MM-DD.csv", "s2": "情境_yyin_YYYY-MM-DD.csv"}}
    put(root, "README.txt", ("SYNTHETIC ONLY\n## 工作內容\ns1 與 s2 自測\n"
        "## 要提交項目\nRETURN/審圖_yyin_YYYY-MM-DD.csv\nRETURN/情境_yyin_YYYY-MM-DD.csv\n"
        "未完成加 _INCOMPLETE\n## 操作\n用 CSV UTF-8\n## 不要改\n固定欄位保留\n").encode())
    put(root, "RETURN/README.txt", b"SYNTHETIC ONLY\n")
    text = csv_bytes(TEXT_COLUMNS, [{TEXT_COLUMNS[0]: rid} for rid in options["text_ids"]])
    for name in [TEXT_FILE, "templates/情境.csv"]:
        put(root, name, text)
    for name in [REVIEW_FILE, "templates/審查表.csv"]:
        put(root, name, csv_bytes(REVIEW_COLUMNS, []))
    s1 = options["s1"]
    table = csv_bytes(s1["columns"], [{s1["columns"][0]: rid} for rid in s1["row_ids"]])
    put(root, s1["filename"], table)
    put(root, s1["template_ref"], table)
    put(root, "tools/verify_pack.py", SCRIPT.read_bytes() if SCRIPT.is_file() else b"# SYNTHETIC pending checker\n")
    manifest = {"schema_version": "team-review-pack.v1", "version": "v0-pilot",
        "evaluation_eligible": False, "samples": [], "files": {},
        "editable_files": {TEXT_FILE: {"template_ref": "templates/情境.csv", "locked_columns": LOCKED[TEXT_FILE]},
                           REVIEW_FILE: {"template_ref": "templates/審查表.csv", "locked_columns": LOCKED[REVIEW_FILE]}}}
    put(root, "MANIFEST.json", encode(manifest))
    repin(root)
    options_path = tmp_path / "SYNTHETIC_OPTIONS.json"
    options_path.write_bytes(encode(options))
    return root, options_path


def repin(root):
    path = root / "MANIFEST.json"
    doc = json.loads(path.read_bytes())
    doc["files"] = {p.relative_to(root).as_posix(): sha(p.read_bytes())
                    for p in root.rglob("*") if p.is_file() and p != path}
    path.write_bytes(encode(doc))


def inspect(root, options, pack=None):
    return module().inspect_pack(pack or root, profile=json.loads(options.read_bytes())["profile"],
        manifest_sha256=sha((root / "MANIFEST.json").read_bytes()),
        options_path=options, options_sha256=sha(options.read_bytes()))


def make_zip(root, output, *, prefix="", timestamp=(1980, 1, 1, 0, 0, 0)):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(prefix + path.relative_to(root).as_posix(), timestamp)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


@pytest.mark.parametrize("profile", ["yyin-main", "team-eval"])
def test_synthetic_directory_and_zip_positive(profile, tmp_path):
    module()  # Test-first red must be a test failure, not fixture setup error.
    root, options = fixture(tmp_path, profile)
    result = inspect(root, options)
    assert result["status"] == "VALID" and result["release_authorized"] is False
    assert result["human_approval_verified"] is False and result["evaluation_eligible_verified"] is False
    first, second = tmp_path / "SYNTHETIC_1.zip", tmp_path / "SYNTHETIC_2.zip"
    make_zip(root, first); make_zip(root, second)
    assert first.read_bytes() == second.read_bytes()
    assert inspect(root, options, first)["status"] == "VALID"
    extracted = tmp_path / "SYNTHETIC_UNZIP"
    with zipfile.ZipFile(first) as archive:
        assert all(info.flag_bits & 0x800 for info in archive.infolist() if not info.filename.isascii())
        archive.extractall(extracted)
    assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == {
        p.relative_to(extracted).as_posix() for p in extracted.rglob("*") if p.is_file()}
    assert inspect(root, options, extracted)["status"] == "VALID"


def test_default_extended_profile_fails_closed(tmp_path):
    root, _ = fixture(tmp_path)
    assert module().inspect_pack(root, profile="yyin-main")["code"] == "PROFILE_UNSELECTED"


@pytest.mark.parametrize("name", ["templates/情境.csv", "templates/審查表.csv", "templates/s1.csv"])
def test_only_explicit_legacy_templates_can_warn(tmp_path, name):
    root, options = fixture(tmp_path)
    (root / name).unlink()
    result = inspect(root, options)
    if name == "templates/s1.csv":
        assert result["status"] == "INVALID"
    else:
        assert result["status"] == "VALID_WITH_WARNINGS"
        assert result["warnings"] == ["TEMPLATE_MISSING:" + name]


@pytest.mark.parametrize("mutation,code", [("changed", "FILE_SHA_MISMATCH"), ("extra", "FILE_SET_MISMATCH"),
    ("missing", "FILE_MISSING"), ("symlink", "SYMLINK_REJECTED"), ("ds", "EXCLUDED_FILE_PRESENT")])
def test_inventory_and_immutable_files(tmp_path, mutation, code):
    root, options = fixture(tmp_path)
    if mutation == "changed": (root / "README.txt").write_bytes(b"changed")
    if mutation == "extra": put(root, "extra.txt", b"SYNTHETIC")
    if mutation == "missing": (root / "README.txt").unlink()
    if mutation == "symlink": (root / "link.txt").symlink_to(root / "README.txt")
    if mutation == "ds": put(root, ".DS_Store", b"SYNTHETIC")
    assert inspect(root, options)["code"] == code


@pytest.mark.parametrize("bad", [b"wrong,header\n", csv_bytes(TEXT_COLUMNS, [{TEXT_COLUMNS[0]: "Q0002"}])])
def test_csv_headers_and_rows_even_if_rehashed(tmp_path, bad):
    root, options = fixture(tmp_path)
    put(root, TEXT_FILE, bad); put(root, "templates/情境.csv", bad); repin(root)
    assert inspect(root, options)["code"] in {"CSV_HEADER_INVALID", "CSV_IDS_INVALID"}


@pytest.mark.parametrize("missing", ["工作內容", "要提交項目", "操作", "不要改", "_INCOMPLETE", "審圖_yyin_YYYY-MM-DD.csv"])
def test_readme_required_instructions(tmp_path, missing):
    root, options = fixture(tmp_path)
    path = root / "README.txt"
    path.write_text(path.read_text().replace(missing, ""))
    repin(root)
    assert inspect(root, options)["code"] == "README_INCOMPLETE"


@pytest.mark.parametrize("text", ['{"GT": 1}', '{"nested":{"trajectory": []}}', '{"visibility":false}',
    '{"depth":0}', "t_X", "t_N", "t_V", "t_L", "decision_window_us", "entry_window_us",
    "configs/evaluation/test.json", "abc_script_plan_x.json", "q5-evaluation-script.v2", "FOO_RECEIPT.json",
    "original.blend", "/Users/SYNTHETIC/file", "/private/SYNTHETIC/file", "~/amidst-artifacts/file"])
def test_forbidden_text_and_nested_keys_in_all_files(tmp_path, text):
    root, options = fixture(tmp_path)
    put(root, "SYNTHETIC.txt", text.encode()); repin(root)
    assert inspect(root, options)["code"] == "FORBIDDEN_CONTENT"


@pytest.mark.parametrize("name,content", [
    ("SYNTHETIC.json", b'{"nested": {"G\\u0054": 1}}'),
    ("SYNTHETIC.json", b'{"reference": "t_\\u0058"}'),
    ("SYNTHETIC.jsonl", b'{"reference": "configs\\/evaluation\\/x.json"}\n'),
])
def test_decoded_json_keys_and_values_are_scanned(tmp_path, name, content):
    root, options = fixture(tmp_path)
    put(root, name, content); repin(root)
    assert inspect(root, options)["code"] == "FORBIDDEN_CONTENT"


def test_zip_requires_utf8_in_both_headers(tmp_path):
    root, options = fixture(tmp_path)
    target = tmp_path / "SYNTHETIC.zip"
    make_zip(root, target)
    data = bytearray(target.read_bytes())
    with zipfile.ZipFile(target) as archive:
        info = next(i for i in archive.infolist() if not i.filename.isascii())
        flags = struct.unpack_from("<H", data, info.header_offset + 6)[0]
        struct.pack_into("<H", data, info.header_offset + 6, flags & ~0x800)
    target.write_bytes(data)
    assert inspect(root, options, target)["code"] == "ZIP_UTF8_FLAG_MISSING"


def test_zip_nfc_duplicates_and_traversal_fail(tmp_path):
    root, options = fixture(tmp_path)
    for n, name in enumerate(["../escape.txt", unicodedata.normalize("NFD", "é.txt")]):
        target = tmp_path / f"SYNTHETIC_BAD_{n}.zip"
        make_zip(root, target)
        with zipfile.ZipFile(target, "a") as archive:
            archive.writestr(name, b"SYNTHETIC")
        assert inspect(root, options, target)["code"] in {"PATH_REJECTED", "NAME_NOT_NFC"}


def test_zip_single_root_prefix_is_supported(tmp_path):
    root, options = fixture(tmp_path)
    target = tmp_path / "SYNTHETIC_PREFIX.zip"
    make_zip(root, target, prefix="SYNTHETIC_PACKAGE/")
    assert inspect(root, options, target)["status"] == "VALID"


def test_zip_fixed_timestamp_is_checked(tmp_path):
    root, options = fixture(tmp_path)
    target = tmp_path / "SYNTHETIC_TIME.zip"
    make_zip(root, target, timestamp=(2026, 10, 29, 0, 0, 0))
    assert inspect(root, options, target)["code"] == "ZIP_TIMESTAMP_MISMATCH"


def test_explicit_s2_framework_does_not_claim_full_pack_ready(tmp_path):
    root, options = fixture(tmp_path)
    doc = json.loads(options.read_bytes())
    doc.update(phase="S2_FRAMEWORK_ONLY", return_names={"s2": doc["return_names"]["s2"]})
    options.write_bytes(encode(doc))
    (root / "s1/確認.csv").unlink(); (root / "templates/s1.csv").unlink(); repin(root)
    result = inspect(root, options)
    assert result["status"] == "VALID" and result["validated_scope"] == "S2_FRAMEWORK_ONLY"
    assert result["s0_status"] == "UNSELECTED" and result["release_authorized"] is False


def test_returned_csv_headers_and_ids_are_checked_without_changing_pack(tmp_path):
    root, options = fixture(tmp_path)
    target = tmp_path / "SYNTHETIC_RETURN.csv"
    target.write_bytes((root / TEXT_FILE).read_bytes())
    kwargs = dict(profile="yyin-main", manifest_sha256=sha((root / "MANIFEST.json").read_bytes()),
                  options_path=options, options_sha256=sha(options.read_bytes()), returned_csv=target)
    assert module().inspect_pack(root, **kwargs)["status"] == "VALID"
    target.write_bytes(b"wrong,header\n")
    assert module().inspect_pack(root, **kwargs)["code"] == "CSV_HEADER_INVALID"


def test_packed_verifier_is_standalone_and_returns_warning_and_invalid(tmp_path):
    root, options = fixture(tmp_path)
    command = [sys.executable, "-I", str(root / "tools/verify_pack.py"), "--pack", str(root),
        "--profile", "yyin-main", "--manifest-sha256", sha((root / "MANIFEST.json").read_bytes()),
        "--profile-options", str(options), "--profile-sha256", sha(options.read_bytes())]
    for expected, exit_code in [("VALID", 0), ("VALID_WITH_WARNINGS", 0), ("INVALID", 1)]:
        if expected == "VALID_WITH_WARNINGS": (root / "templates/情境.csv").unlink()
        if expected == "INVALID": (root / "README.txt").write_bytes(b"changed")
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == exit_code
        assert json.loads(result.stdout)["status"] == expected


def test_existing_importer_accepts_s2_with_header_only_review(tmp_path):
    root, _ = fixture(tmp_path)
    spec = importlib.util.spec_from_file_location("legacy_importer", ROOT / "scripts/import_team_review_pack.py")
    importer = importlib.util.module_from_spec(spec); spec.loader.exec_module(importer)
    row = {column: "" for column in TEXT_COLUMNS}
    row.update({TEXT_COLUMNS[0]: "Q0001", TEXT_COLUMNS[1]: "SYNTHETIC 自測，不是真實題目",
        TEXT_COLUMNS[2]: "相機", TEXT_COLUMNS[7]: "否", TEXT_COLUMNS[8]: "不支援"})
    returned = tmp_path / "SYNTHETIC_RETURN.csv"
    returned.write_bytes(csv_bytes(TEXT_COLUMNS, [row] + [{TEXT_COLUMNS[0]: f"Q{i:04d}"} for i in range(2, 15)]))
    annotation = {"id": "Q0001", "text": row[TEXT_COLUMNS[1]], "q3": {
        "category": "SYNTHETIC_ONLY", "expected_status": "UNSUPPORTED_CLASS", "expected_structured_query": None,
        "expected_llm_output": {"schema_version": "q-demo.q3-llm-output.v1", "intent": "UNSUPPORTED",
            "class_term": None, "color_term": None, "time_literal": None, "camera_terms": [], "region_terms": [],
            "needs_clarification": False, "clarification_question": None}}}
    notes = tmp_path / "SYNTHETIC_ANNOTATIONS.jsonl"; notes.write_bytes(encode(annotation))
    report = importer.import_pack(root, manifest_sha256=sha((root / "MANIFEST.json").read_bytes()),
        output=tmp_path / "SYNTHETIC_IMPORTED", text_csv=returned, annotations=notes)
    assert report["counts"]["queries_v1.jsonl"] == 1
    assert report["counts"]["q4_tf_review_v1.jsonl"] == 0
