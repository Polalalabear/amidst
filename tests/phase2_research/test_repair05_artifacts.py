"""Read-only integration checks of registered 05 freezes; no producer/evaluator runs."""

from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import MODES
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.phase2_research import repair05_adapter, repair05_runtime
from amidst.phase2_research.repair05_pipeline import load
from amidst.phase2_research.repair05_runtime import load_service
from amidst.research_accuracy.verify import denied_sidecars

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/engineering/local_run/phase2_repair_0511/research/test/final"
RELEASE = ROOT / "data/engineering/phase2_repair_0511_20261013/research_release.json"
RUNTIME_RELEASE = (
    ROOT / "data/engineering/phase2_repair_0511_20261013/research_runtime_release.json"
)
pytestmark = pytest.mark.skipif(
    not RELEASE.is_file(), reason="local registered repair05 freeze absent"
)
Json = dict[str, Any]


def registered(output: Path = OUTPUT, *, mode: str = "photos_only") -> Any:
    release = json.loads(RUNTIME_RELEASE.read_bytes())
    return load_service(
        output,
        scene_id="accuracy-v2",
        variant="baseline",
        mode=mode,
        expected_manifest_sha256=release["manifest_sha256"],
        expected_evaluation_sha256=release["evaluation_sha256"],
        expected_runtime_sha256=release["runtime_sha256"],
    )


@pytest.mark.parametrize("mode", MODES)
def test_certified_runtime_reads_no_truth_and_preserves_original_media(mode: str) -> None:
    package, registry, manifest, _ = load(OUTPUT)
    sidecars = {
        package.simulation_export_path,
        DEFAULT_CONFIG,
        package.simulation_export_path.parent / "recipe.json",
        package.simulation_export_path.parent / "reference_annotations.json",
    }
    with denied_sidecars(sidecars, removed=True) as counts:
        service = registered(mode=mode)
        context, diagnostics = service.context(), service.diagnostics()
        assert diagnostics["status"] == "CERTIFIED_AGGREGATE"
        assert diagnostics["evaluation"]["active_variant"] == "baseline"
        assert not diagnostics["evaluation"]["acceptance"][mode]["accepted"]
        media = {row.media_ref for row in registry.frames}
        for camera in context["camera_ids"]:
            result = service.query("accuracy-v2", package.run_id, camera, 0, 24)
            assert len(result["tracks"]) <= 64
            assert (
                result["binding"]["freeze_ref"]
                == manifest["variants"]["baseline"][mode]["freeze_ref"]
            )
            for track in result["tracks"]:
                assert track["camera_id"] == camera
                assert len(track["source_frames"]) <= 8
                assert not track["identity_confirmed"]
                for frame in track["source_frames"]:
                    assert frame["camera_id"] == camera and frame["media_ref"] in media
                    assert frame["frame_ref"] == frame["media_ref"]
        rendered = json.dumps([context, diagnostics, result])
        assert str(ROOT) not in rendered
        assert "actor_identity" not in rendered and "evaluation_only_actor" not in rendered
        assert "source_locator" not in rendered and "simulation_export_path" not in rendered
        assert counts["attempted_reads"] == 0


@pytest.mark.parametrize("mutation", ["scene", "run", "camera", "end"])
def test_source_scoped_query_rejects_other_context(mutation: str) -> None:
    service = registered()
    scene, run, camera, end = (
        "accuracy-v2",
        service.binding["source_run_id"],
        sorted(service.cameras)[0],
        24,
    )
    if mutation == "scene":
        scene = "other"
    elif mutation == "run":
        run = "other"
    elif mutation == "camera":
        camera = "other"
    else:
        end = 25
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        service.query(scene, run, camera, 0, end)


@pytest.mark.parametrize(
    "mutation", ["trace", "manifest", "receipt", "evaluation", "self_certify", "symlink"]
)
def test_frozen_and_aggregate_tampering_is_refused(tmp_path: Path, mutation: str) -> None:
    copied = tmp_path / "frozen"
    shutil.copytree(
        OUTPUT, copied, ignore=shutil.ignore_patterns("evaluation_inputs", "reproduction.json")
    )
    if mutation in {"trace", "receipt"}:
        path = copied / "baseline/photos_only" / (mutation + ".json")
        value = json.loads(path.read_bytes())
        if mutation == "trace":
            value["input_contact_count"] -= 1
        else:
            value["binding"]["run_id"] = "other"
        path.write_text(json.dumps(value))
    elif mutation == "manifest":
        path = copied / "manifest.json"
        value = json.loads(path.read_bytes())
        value["source_run_id"] = "other"
        path.write_text(json.dumps(value))
    elif mutation == "symlink":
        path = copied / "evaluation.json"
        path.unlink()
        path.symlink_to(OUTPUT / "evaluation.json")
    else:
        path = copied / "evaluation.json"
        value = json.loads(path.read_bytes())
        value["variants"]["candidate"]["photos_only"]["pixel_population"][
            "fragmented_track_count"
        ] = 0
        path.write_text(json.dumps(value))
        if mutation == "self_certify":
            receipt_path = copied / "evaluation_receipt.json"
            receipt = json.loads(receipt_path.read_bytes())
            receipt["evaluation_sha256"] = digest(value)
            receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="REPAIR05_"):
        registered(copied).diagnostics()


def test_evaluation_refuses_repeat_before_any_truth_read() -> None:
    from amidst.phase2_research.repair05_evaluation import evaluate

    with pytest.raises(ValueError, match="EVALUATION_ALREADY_COMPLETE"):
        evaluate(OUTPUT, test_authorized=True)


def test_runtime_requires_independent_expected_source_hash() -> None:
    with pytest.raises(ValueError, match="RUNTIME_CERTIFICATE_MISMATCH"):
        load_service(OUTPUT, expected_runtime_sha256="0" * 64)


def test_loaded_runtime_refuses_source_change(monkeypatch: pytest.MonkeyPatch) -> None:
    service = registered()
    monkeypatch.setattr(repair05_runtime, "runtime_sha256", lambda: "0" * 64)
    with pytest.raises(ValueError, match="RUNTIME_SOURCE_CHANGED"):
        service.context()


def test_concurrent_runtime_loads_never_mutate_frozen_factory() -> None:
    factory = vars(repair05_adapter)["opaque_ref"]
    constructor = repair05_adapter.Repair05Service.__init__

    def read(index: int) -> str:
        service = registered(mode=MODES[index % 2])
        result = service.query(
            "accuracy-v2", service.binding["source_run_id"], sorted(service.cameras)[0], 0, 24
        )
        assert vars(repair05_adapter)["opaque_ref"] is factory
        assert repair05_adapter.Repair05Service.__init__ is constructor
        assert result["tracks"][0]["track_ref"].startswith("repairtrack:")
        mode: str = result["binding"]["mode"]
        return mode

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(read, range(8))) == list(MODES) * 4
