"""Register the actual curated 05 runtime schema; injected service tests cannot cover it."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.phase2_research import repair05_runtime
from amidst.workbench.phase2_suite import Phase2Suite, SuiteRequest

ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "data/engineering/phase2_repair_0511_20261013/research_runtime_release.json"
Json = dict[str, Any]


def prepare(repo: Path) -> tuple[Path, Path, Json]:
    output = repo / "data/engineering/local_run/phase2_repair_0511/research/test/final"
    output.mkdir(parents=True)
    release_path = (
        repo / "data/engineering/phase2_repair_0511_20261013/research_runtime_release.json"
    )
    release_path.parent.mkdir(parents=True)
    release = json.loads(CURATED.read_bytes())
    release_path.write_text(json.dumps(release))
    return output, release_path, release


def install_loader(
    monkeypatch: pytest.MonkeyPatch, release: Json, output: Path, *, mismatch: str | None = None
) -> list[Json]:
    calls: list[Json] = []

    def load(path: Path, **fields: Any) -> Any:
        assert path == output
        assert fields["variant"] == "baseline"
        assert fields["expected_manifest_sha256"] == release["manifest_sha256"]
        assert fields["expected_evaluation_sha256"] == release["evaluation_sha256"]
        assert fields["expected_runtime_sha256"] == release["runtime_sha256"]
        mode = fields["mode"]
        calls.append(fields)
        binding = {
            "scene_id": "local-camera-accuracy-v2",
            "source_run_id": release["source_run_id"],
            "source_sha256": release["source_sha256"],
            "mode": mode,
            "freeze_ref": release["modes"][mode]["freeze_ref"],
        }
        if mismatch is not None and mode == "photos_plus_observations":
            binding[mismatch] = "wrong-binding"
        return SimpleNamespace(context=lambda: {"binding": binding, "available": True})

    monkeypatch.setattr(repair05_runtime, "load_service", load)
    return calls


def workbench() -> Any:
    return SimpleNamespace(product_bridge=None, product_bridges={})


def test_actual_curated_runtime_schema_registers_both_modes_and_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _, release = prepare(tmp_path)
    assert release["schema_version"] == "phase2.repair05.runtime-release.v1"
    calls = install_loader(monkeypatch, release, output)
    suite = Phase2Suite(workbench(), tmp_path)
    assert list(suite.repair05) == ["photos_only", "photos_plus_observations"]
    assert [row["mode"] for row in calls] == list(suite.repair05)
    scene = SimpleNamespace(
        scene_id="local-camera-accuracy-v2",
        run_id=release["source_run_id"],
        source_hash=release["source_sha256"],
    )
    for mode in suite.repair05:
        result = suite.context(
            SuiteRequest.model_validate(
                {
                    "session_ref": "research-owner-credential-for-test",
                    "scene_id": scene.scene_id,
                    "observation_mode": mode,
                }
            ),
            scene,
        )
        assert result["repair05"]["available"]
        binding = result["repair05"]["binding"]
        assert binding["mode"] == mode and binding["source_run_id"] == release["source_run_id"]
        assert binding["freeze_ref"] == release["modes"][mode]["freeze_ref"]
    assert "repair05" not in suite.unavailable_reasons


@pytest.mark.parametrize("failure", ["wrong_schema", "symlink", "candidate", "accepted"])
def test_registration_refuses_untrusted_release_before_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    output, path, release = prepare(tmp_path)
    calls = install_loader(monkeypatch, release, output)
    if failure == "symlink":
        target = tmp_path / "elsewhere.json"
        path.rename(target)
        path.symlink_to(target)
    else:
        value = dict(release)
        key, changed = {
            "wrong_schema": ("schema_version", "phase2.repair05.release.v1"),
            "candidate": ("active_variant", "candidate"),
            "accepted": ("acceptance_outcome", "ACCEPTED_LOCAL_CONTINUITY_GAIN"),
        }[failure]
        value[key] = changed
        path.write_text(json.dumps(value))
    suite = Phase2Suite(workbench(), tmp_path)
    assert suite.repair05 == {} and calls == []
    assert suite.unavailable_reasons["repair05"] == "REPAIR05_RELEASE_NOT_VERIFIED"


@pytest.mark.parametrize("field", ["freeze_ref", "source_sha256", "source_run_id"])
def test_second_mode_binding_failure_clears_all_registered_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    output, _, release = prepare(tmp_path)
    calls = install_loader(monkeypatch, release, output, mismatch=field)
    suite = Phase2Suite(workbench(), tmp_path)
    assert len(calls) == 2
    assert suite.repair05 == {}
    assert suite.unavailable_reasons["repair05"] == "REPAIR05_RELEASE_NOT_VERIFIED"
