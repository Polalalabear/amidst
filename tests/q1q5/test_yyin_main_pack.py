"""Future #317 builder acceptance. Inputs are explicit TEST-ONLY synthetic pins."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unicodedata
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from build_team_review_pack import LOCKED, REVIEW_FILE, TEXT_FILE


def missing(reason):
    if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def builder_inputs():
    module_path = ROOT / "src/amidst/q1q5/yyin_main_pack.py"
    if not module_path.is_file():
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CQ27_IMPLEMENTATION_MISSING")
        pytest.importorskip("amidst.q1q5.yyin_main_pack", reason="CQ27_IMPLEMENTATION_MISSING")
        pytest.skip("CQ27_LOCAL_SNAPSHOT_IMPLEMENTATION_MISSING")
    spec = importlib.util.spec_from_file_location("amidst.q1q5.yyin_main_pack", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = os.environ.get("AMIDST_YYIN_BUILDER_INPUTS")
    if not source:
        missing("CQ27_SYNTHETIC_INPUTS_MISSING")
    path = Path(source)
    assert path.is_file() and "SYNTHETIC" in str(path), "Explicit SYNTHETIC config required"
    return module, json.loads(path.read_bytes())


def test_builder_synthetic_framework_keeps_existing_wire_and_release_closed(tmp_path):
    module, inputs = builder_inputs()
    receipt = module.build_pack(tmp_path / "SYNTHETIC_FRAMEWORK", inputs=inputs, synthetic_only=True)
    root = Path(receipt["pack_path"])
    raw = (root / "MANIFEST.json").read_bytes()
    manifest = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == receipt["manifest_sha256"]
    assert manifest["schema_version"] == "team-review-pack.v1"
    assert manifest["evaluation_eligible"] is False and manifest["samples"] == []
    assert set(manifest["editable_files"]) == {TEXT_FILE, REVIEW_FILE}
    assert all(manifest["editable_files"][name]["locked_columns"] == LOCKED[name] for name in LOCKED)
    assert receipt["phase"] == "S2_FRAMEWORK_ONLY" and receipt["release_authorized"] is False


def test_builder_zip_is_reproducible_and_utf8_names_survive(tmp_path):
    module, inputs = builder_inputs()
    first = module.build_pack(tmp_path / "SYNTHETIC_FIRST", inputs=inputs, synthetic_only=True)
    second = module.build_pack(tmp_path / "SYNTHETIC_SECOND", inputs=inputs, synthetic_only=True)
    left, right = Path(first["zip_path"]).read_bytes(), Path(second["zip_path"]).read_bytes()
    assert left == right
    assert hashlib.sha256(left).hexdigest() == first["zip_sha256"] == second["zip_sha256"]
    with zipfile.ZipFile(first["zip_path"]) as archive:
        for entry in archive.infolist():
            assert unicodedata.normalize("NFC", entry.filename) == entry.filename
            if not entry.filename.isascii():
                assert entry.flag_bits & 0x800
        names = {info.filename.rstrip("/") for info in archive.infolist() if not info.is_dir()}
        expected = {p.relative_to(first["pack_path"]).as_posix() for p in Path(first["pack_path"]).rglob("*") if p.is_file()}
        if "MANIFEST.json" not in names:
            prefix = next(name[:-len("MANIFEST.json")] for name in names if name.endswith("/MANIFEST.json"))
            names = {name[len(prefix):] for name in names}
        assert names == expected
