"""File-based behaviour: path guard before IO, hash pins, CLI exit codes (SYNTHETIC)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from scene_marker_fixtures import build_bundle, write_bundle

from amidst.scene_markers import loader, validate_safe_bundle

_SPEC = importlib.util.spec_from_file_location(
    "validate_controlled_scene",
    Path(__file__).resolve().parents[2] / "scripts" / "validate_controlled_scene.py",
)
assert _SPEC and _SPEC.loader
cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cli)


def rule(report: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(r for r in report["rules"] if r["rule_id"] == rule_id)


def codes(report: dict[str, Any], rule_id: str) -> set[str]:
    return {i["code"] for i in report["issues"] if i["rule_id"] == rule_id}


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs" / "ctrl-lcorr-s1-b1-5fps-v1-r001" / "safe_bundle"
    write_bundle(directory, build_bundle("b1"))
    return directory


def test_files_pass_and_allowlist_hashes_match(bundle_dir: Path) -> None:
    report = validate_safe_bundle(bundle_dir)
    assert report["status"] == "PASS", [i for i in report["issues"] if i["severity"] == "ERROR"]
    assert rule(report, "RUN-003")["result"] == "PASS"
    assert set(report["input_file_sha256"]) == {
        "scene_static",
        "manifest",
        "cameras",
        "rgb_index",
        "runtime_profile",
    }
    assert all(len(v) == 64 for v in report["input_file_sha256"].values())


def test_changed_file_after_pinning_is_a_hash_mismatch(bundle_dir: Path) -> None:
    path = bundle_dir / "rgb_index.json"
    data = json.loads(path.read_text())
    data["records"][0]["file_sha256"] = "0" * 64  # content change, manifest pin now stale
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    report = validate_safe_bundle(bundle_dir)
    assert report["status"] == "FAIL" and rule(report, "RUN-003")["result"] == "FAIL"
    assert "FILE_HASH_MISMATCH" in codes(report, "RUN-003")


def test_only_the_five_safe_files_are_opened_even_if_private_files_sit_beside_them(
    bundle_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("persons.sim.json", "production_manifest.json", "event_B1.validation.json"):
        (bundle_dir / name).write_text('{"route_waypoints_m": [[0, 0]], "seed": 1}')
    opened: list[str] = []
    real = loader.load_json_file

    def spy(path: Path) -> Any:
        opened.append(path.name)
        return real(path)

    monkeypatch.setattr(loader, "load_json_file", spy)
    report = validate_safe_bundle(bundle_dir)
    assert sorted(opened) == [
        "cameras.json",
        "manifest.json",
        "rgb_index.json",
        "runtime_profile.json",
        "scene_static.json",
    ]
    assert report["status"] == "PASS"


def test_private_location_is_rejected_before_any_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "private_evaluation" / "run" / "safe_bundle"
    write_bundle(directory, build_bundle("b1"))

    def boom(path: Path) -> Any:
        raise AssertionError(f"opened {path}")

    monkeypatch.setattr(loader, "load_json_file", boom)
    report = validate_safe_bundle(directory)
    assert report["status"] == "FAIL" and rule(report, "IO-001")["result"] == "FAIL"
    assert "FORBIDDEN_DATA_SCOPE" in codes(report, "IO-001")
    assert "private_evaluation" not in json.dumps(report, ensure_ascii=False)


def test_symlinked_input_is_rejected(bundle_dir: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_bytes((bundle_dir / "runtime_profile.json").read_bytes())
    (bundle_dir / "runtime_profile.json").unlink()
    (bundle_dir / "runtime_profile.json").symlink_to(elsewhere)
    report = validate_safe_bundle(bundle_dir)
    assert "INPUT_SYMLINK" in codes(report, "IO-001") and report["status"] == "FAIL"


def test_missing_file_is_a_failure(bundle_dir: Path) -> None:
    (bundle_dir / "runtime_profile.json").unlink()
    report = validate_safe_bundle(bundle_dir)
    assert "INPUT_MISSING" in codes(report, "IO-001") and report["status"] == "FAIL"


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ('{"a": NaN}', "non-finite"),
        ('{"a": 1, "a": 2}', "duplicate"),
        ("[1, 2]", None),
        ("{not json", None),
    ],
)
def test_unparseable_json_fails_io_002(bundle_dir: Path, text: str, needle: str | None) -> None:
    (bundle_dir / "scene_static.json").write_text(text)
    report = validate_safe_bundle(bundle_dir)
    assert rule(report, "IO-002")["result"] == "FAIL" and report["status"] == "FAIL"
    if needle:
        assert any(needle in i["message"] for i in report["issues"] if i["rule_id"] == "IO-002")


def test_cli_exit_codes_and_report_file(
    bundle_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "report.json"
    assert cli.main(["--safe-dir", str(bundle_dir), "--output", str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["status"] == "PASS" and report["rules"] and len(report["output_sha256"]) == 64
    assert "PASS" in capsys.readouterr().err
    (bundle_dir / "scene_static.json").write_text("{}")
    assert cli.main(["--safe-dir", str(bundle_dir), "--output", str(out)]) == 1


def test_cli_refuses_to_write_into_the_bundle(
    bundle_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(["--safe-dir", str(bundle_dir), "--output", str(bundle_dir / "report.json")]) == 2
    )
    assert "refusing to write" in capsys.readouterr().err
    assert not (bundle_dir / "report.json").exists()


def test_cli_param_override_and_unknown_param(
    bundle_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "r.json"
    assert (
        cli.main(
            ["--safe-dir", str(bundle_dir), "--output", str(out), "--param", "min_clearance_m=0.5"]
        )
        == 1
    )
    assert json.loads(out.read_text())["parameters"]["min_clearance_m"] == 0.5
    assert cli.main(["--safe-dir", str(bundle_dir), "--param", "nope=1"]) == 2
    assert cli.main(["--safe-dir", str(bundle_dir), "--output", str(out), "--no-design"]) == 0
    assert json.loads(out.read_text())["design_layer"] == "DISABLED"
    capsys.readouterr()
