"""Reproduction contracts preserve populations while excluding measured metadata."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import amidst.finalization.scoped_reproduction as reproduction
from amidst.finalization.reviewed_pipeline import (
    digest,
    freeze_inference,
    read_json,
    write_benchmark_tables,
    write_json,
)
from amidst.finalization.scoped_reproduction import (
    CleanCheckoutSpec,
    clean_checkout_delivery,
    compare_scoped_deliveries,
    create_scoped_poison_dataset,
    fresh_process_inference,
    verify_scoped_dataset,
    verify_scoped_reproduction,
)

CASES = ("case2", "case3", "case3_short_control", "case3_long_stress")


def _dataset(root: Path) -> Path:
    root.mkdir()
    for case in CASES:
        write_json(root / "inference" / case / "observations.json", {"source": "SYNTHETIC_TEST"})
        write_json(
            root / "evaluation" / case / "ground_truth.json",
            {
                "samples": [
                    {"timestamp": 0.0, "position": [0.0, 0.0, 0.0]},
                    {"timestamp": 1.0, "position": [1.0, 0.0, 0.0]},
                ],
            },
        )
        write_json(
            root / "evaluation" / case / "reference_movement_annotations.json",
            {"segments": [{"state": "MOVING"}]},
        )
        write_json(
            root / "simulation" / case / "recipe.json",
            {"waypoints": [{"position": [0.0, 0.0, 0.0]}]},
        )
    write_json(
        root / "manifest.json",
        {
            "schema_version": "phase1-scoped-source-dataset-v1",
            "cases": [{"case_id": case} for case in CASES],
            "artifacts": {str(p.relative_to(root)): digest(p) for p in root.rglob("*.json")},
        },
    )
    return root


def _inference(root: Path, dataset: Path, master: Path) -> Path:
    write_json(
        root / "summary.json",
        {
            "cases": [
                {
                    "case_id": case,
                    "gaps": [
                        {
                            "variants": [
                                {
                                    "variant": "spatiotemporal",
                                    "status": "EXECUTED",
                                    "termination_reason": "COMPLETE",
                                    "generation_complete": True,
                                    "inventory_complete": True,
                                }
                            ]
                        }
                    ],
                }
                for case in CASES
            ]
        },
    )
    freeze_inference(
        root,
        dataset_manifest_sha256=digest(dataset / "manifest.json"),
        config_sha256=digest(master),
    )
    return root


def _evaluation(root: Path, *, runtime: float = 1.0, container: bytes = b"RRD_TEST_ONE") -> Path:
    write_json(
        root / "summary.json",
        {
            "cases": [{"case_id": case, "status": "TEST_ONLY"} for case in CASES],
            "demos": [
                {"recording": str(root / "demos" / case / "scoped.rrd")} for case in CASES[:2]
            ],
        },
    )
    rows = [
        {
            "case_id": case,
            "k": k,
            "candidate_count": 2,
            "ade_m": None,
            "status": "N/A",
            "gap_inference_runtime_s": runtime,
            "blockers": "TEST_ONLY",
        }
        for case in CASES
        for k in (1, 2, 3)
    ]
    write_benchmark_tables(root, rows)
    for case in CASES[:2]:
        demo = root / "demos" / case
        demo.mkdir(parents=True)
        (demo / "scoped.rrd").write_bytes(container)
        (demo / "preview.png").write_bytes(b"PNG_TEST_CANONICAL")
        write_json(
            demo / "presentation.json",
            {
                "rrd_reader_verified": True,
                "reader": {"chunk_count": 8, "required_source_layers_verified": True},
                "candidate_order": ["first", "alternative"],
                "artifacts": {
                    "recording": {"filename": "scoped.rrd", "sha256": digest(demo / "scoped.rrd")},
                    "preview": {"filename": "preview.png", "sha256": digest(demo / "preview.png")},
                },
            },
        )
    charts = root / "charts"
    charts.mkdir()
    (charts / "projection_error_m.png").write_bytes(b"PNG_TEST_CANONICAL")
    (charts / "projection_error_m.pdf").write_bytes(b"PDF_TEST_CANONICAL")
    (charts / "runtime_s.png").write_bytes(str(runtime).encode())
    (charts / "runtime_s.pdf").write_bytes(str(runtime).encode())
    return root


def _packages(tmp_path: Path) -> dict[str, Path]:
    master = tmp_path / "master.json"
    write_json(master, {"source_case_ids": CASES})
    dataset = _dataset(tmp_path / "dataset")
    other = tmp_path / "fresh_dataset"
    shutil.copytree(dataset, other)
    return {
        "local_dataset": dataset,
        "fresh_dataset": other,
        "local_inference": _inference(tmp_path / "infer", dataset, master),
        "fresh_inference": _inference(tmp_path / "fresh_infer", other, master),
        "local_evaluation": _evaluation(tmp_path / "eval"),
        "fresh_evaluation": _evaluation(
            tmp_path / "fresh_eval", runtime=2.0, container=b"OTHER_RRD"
        ),
        "master": master,
    }


def test_full_comparison_excludes_only_runtime_and_container_hash_metadata(tmp_path: Path) -> None:
    packages = _packages(tmp_path)
    result = compare_scoped_deliveries(**{k: v for k, v in packages.items() if k != "master"})
    assert result["status"] == "PASS"
    assert result["report_and_demo_comparison_counts"][".rrd"] == 2
    assert not result["original_phase1_full_exit_or_freeze_granted"]
    assert not result["missing_required_reports"]


@pytest.mark.parametrize("change", ["candidate_order", "csv_population", "pdf", "rrd_receipt"])
def test_nonruntime_population_semantics_and_artifact_content_cannot_be_hidden(
    tmp_path: Path,
    change: str,
) -> None:
    packages = _packages(tmp_path)
    root = packages["fresh_evaluation"]
    if change in {"candidate_order", "rrd_receipt"}:
        path = root / "demos/case2/presentation.json"
        value = read_json(path)
        if change == "candidate_order":
            value["candidate_order"].reverse()
        else:
            value["artifacts"]["recording"]["sha256"] = "f" * 64
        path.write_text(json.dumps(value))
    elif change == "csv_population":
        path = root / "benchmark_table.csv"
        path.write_text(path.read_text().replace(",2,", ",99,", 1))
    else:
        (root / "charts/projection_error_m.pdf").write_bytes(b"CHANGED_METRIC_PDF")
    assert (
        compare_scoped_deliveries(**{k: v for k, v in packages.items() if k != "master"})["status"]
        == "FAIL"
    )


def test_poison_requires_freeze_preserves_input_bytes_and_ignores_unlisted_files(
    tmp_path: Path,
) -> None:
    packages = _packages(tmp_path)
    dataset, primary = packages["local_dataset"], packages["local_inference"]
    (dataset / "unlisted_private.txt").write_text("DO_NOT_COPY")
    poisoned = tmp_path / "poisoned"
    receipt = create_scoped_poison_dataset(dataset, poisoned, primary=primary)
    assert receipt["inference_artifacts_byte_identical"] and receipt["manifest_preserved"]
    assert all(receipt["changed_partitions"].values())
    assert not (poisoned / "unlisted_private.txt").exists()
    verify_scoped_dataset(poisoned, inference_only=True)
    with pytest.raises(ValueError, match="artifact differs"):
        verify_scoped_dataset(poisoned)
    with pytest.raises(FileExistsError):
        create_scoped_poison_dataset(dataset, poisoned, primary=primary)
    with pytest.raises(FileNotFoundError):
        create_scoped_poison_dataset(
            dataset, tmp_path / "without_freeze", primary=tmp_path / "missing"
        )


def test_fresh_process_pins_selected_root_and_invokes_real_cli_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def command(arguments: list[str], **kwargs: Any) -> Any:
        calls.append((arguments, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(reproduction.subprocess, "run", command)
    fresh_process_inference(
        tmp_path / "dataset",
        tmp_path / "master",
        tmp_path / "out",
        root=tmp_path,
        python_executable=Path("/python"),
    )
    arguments, kwargs = calls[0]
    assert arguments[:3] == [
        "/python",
        str(tmp_path / "scripts/run_phase1_scoped_case23.py"),
        "infer",
    ]
    assert kwargs["env"]["PYTHONPATH"] == str(tmp_path / "src")
    assert kwargs["cwd"] == tmp_path


def test_dirty_checkout_is_rejected_before_any_fresh_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = CleanCheckoutSpec(
        root=tmp_path,
        expected_commit="a" * 40,
        master_relative_path="master.json",
        source_config_relative_path="source.json",
        source=tmp_path / "source.blend",
        python_executable=Path("/python"),
        blender_executable=Path("/blender"),
        output=tmp_path / "fresh",
    )
    outputs = iter(("a" * 40, " M src/producer.py"))
    monkeypatch.setattr(
        reproduction.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=next(outputs))
    )
    with pytest.raises(ValueError, match="clean checkout"):
        clean_checkout_delivery(
            spec, local_dataset=tmp_path, local_inference=tmp_path, local_evaluation=tmp_path
        )
    assert not spec.output.exists()


def test_runner_reuses_provider_and_never_calls_missing_clean_checkout_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amidst.finalization import scoped_pipeline

    packages = _packages(tmp_path)
    sentinel = object()
    calls = []

    def infer(dataset: Path, master: Path, output: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        _inference(output, dataset, master)
        return {}

    def fresh(dataset: Path, master: Path, output: Path, **kwargs: Any) -> dict[str, Any]:
        _inference(output, dataset, master)
        return {"returncode": 0}

    monkeypatch.setattr(scoped_pipeline, "infer_scoped_dataset", infer)
    monkeypatch.setattr(reproduction, "fresh_process_inference", fresh)
    monkeypatch.setattr(
        reproduction,
        "_gt_metric_probe",
        lambda *a: [
            {"case_id": case, "status": "PASS", "evaluation_changed": True} for case in CASES
        ],
    )
    result = verify_scoped_reproduction(
        packages["local_dataset"],
        packages["local_inference"],
        packages["master"],
        tmp_path / "reproduction",
        root=tmp_path,
        provider=sentinel,
        primary_evaluation=packages["local_evaluation"],
    )
    assert len(calls) == 3 and all(call["provider"] is sentinel for call in calls)
    assert calls[1]["reordered"] is True
    assert result["gt_recipe_reference_annotation_poison_status"] == "PASS"
    assert result["termination_status"] == "PASS"
    assert result["status"] == "INCOMPLETE" and result["clean_checkout"]["status"] == "NOT_RUN"


def test_runtime_plot_hash_receipts_must_match_actual_bytes(tmp_path: Path) -> None:
    packages = _packages(tmp_path)
    for key in ("local_evaluation", "fresh_evaluation"):
        root = packages[key]
        summary = read_json(root / "summary.json")
        summary["charts"] = {
            "artifacts": [
                {
                    "file": "runtime_s.png",
                    "sha256": digest(root / "charts/runtime_s.png"),
                }
            ]
        }
        (root / "summary.json").write_text(json.dumps(summary))
    args = {key: value for key, value in packages.items() if key != "master"}
    assert compare_scoped_deliveries(**args)["status"] == "PASS"
    root = packages["fresh_evaluation"]
    summary = read_json(root / "summary.json")
    summary["charts"]["artifacts"][0]["sha256"] = "f" * 64
    (root / "summary.json").write_text(json.dumps(summary))
    assert compare_scoped_deliveries(**args)["status"] == "FAIL"


def test_postfreeze_gt_metric_probe_changes_actual_configured_ade_fde(tmp_path: Path) -> None:
    from test_graph_engine import _branch_network, _endpoints

    from amidst.domain.metric_config import MetricConfig
    from amidst.domain.search import MovementConstraints
    from amidst.graph.engine import SpatiotemporalGraphEngine
    from amidst.reconstruction.blind_gap import BlindGapReconstructor

    start, end = _endpoints()
    result = SpatiotemporalGraphEngine(
        _branch_network(),
        MovementConstraints(max_speed_m_s=1.0),
        clock=lambda: 0.0,
    ).propose_feasible_trajectories(start, end)
    event = BlindGapReconstructor().reconstruct_gap(start, end, result)
    assert event.trajectories
    dataset = tmp_path / "probe_dataset"
    truth = {
        "provenance": "GROUND_TRUTH",
        "source_sha256": "a" * 64,
        "spatial_context_id": "SYNTHETIC_TEST_FIXTURE",
        "target_id": start.target_id,
        "coordinate_units": "BLENDER_NATIVE_UNITS",
        "samples": [
            {
                "timestamp": round(1.0 + index / 5, 1),
                "floor_id": "1F",
                "position": [2.0 * (index / 50) / 0.0247, 0.0, 0.0],
            }
            for index in range(51)
        ],
    }
    write_json(dataset / "inference/case2/input.json", {"source": "SYNTHETIC_TEST_ONLY"})
    write_json(dataset / "evaluation/case2/ground_truth.json", truth)
    write_json(dataset / "evaluation/case2/reference_movement_annotations.json", {"segments": []})
    write_json(dataset / "simulation/case2/recipe.json", {"waypoints": []})
    write_json(
        dataset / "manifest.json",
        {
            "schema_version": "phase1-scoped-source-dataset-v1",
            "cases": [{"case_id": "case2"}],
            "artifacts": {
                str(path.relative_to(dataset)): digest(path) for path in dataset.rglob("*.json")
            },
        },
    )
    primary = tmp_path / "probe_primary"
    write_json(
        primary / "case2/gap00/spatiotemporal/run.json", {"event": event.model_dump(mode="json")}
    )
    write_json(
        primary / "config.json",
        {"movement": {"max_speed_m_s": 1.0}, "metres_per_blender_unit": 0.0247},
    )
    write_json(
        primary / "experiment.json",
        {
            "metric_config": MetricConfig(k_values=(1, 2, 3), coverage_epsilon_m=0.5).model_dump(
                mode="json"
            ),
        },
    )
    freeze_inference(
        primary, dataset_manifest_sha256=digest(dataset / "manifest.json"), config_sha256="b" * 64
    )
    poison = tmp_path / "probe_poison"
    create_scoped_poison_dataset(dataset, poison, primary=primary)
    probe = reproduction._gt_metric_probe(dataset, poison, primary)
    assert len(probe) == 1 and probe[0]["status"] == "PASS"
    assert probe[0]["normal"] != probe[0]["poisoned"]


@pytest.mark.parametrize("failure", [None, "office", "joint_population", "source_receipt"])
def test_joint_clean_checkout_runs_one_native_delivery_and_compares_both_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    from amidst.finalization import reviewed_reproduction, scoped_protocol

    packages = _packages(tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    master = checkout / "master.json"
    shutil.copyfile(packages["master"], master)
    write_json(checkout / "source.json", {"source": "SYNTHETIC_TEST_ONLY"})
    local = tmp_path / "local_joint"
    scoped = local / "scoped"
    scoped.mkdir(parents=True)
    for kind, original in (
        ("dataset", packages["local_dataset"]),
        ("inference_primary", packages["local_inference"]),
        ("evaluation", packages["local_evaluation"]),
    ):
        shutil.copytree(original, scoped / kind)
    write_json(local / "joint_inference_freeze.json", {"fixture": "SYNTHETIC_TEST_ONLY"})
    write_json(
        local / "primary_run_receipt.json",
        {"source_unchanged": True, "master_file_sha256": digest(master)},
    )
    write_json(local / "verification.json", {"population": CASES, "status": "TEST_ONLY"})
    write_json(local / "case3_growth.json", {"short_count": 1, "long_count": 2})
    write_benchmark_tables(local, [{"case_id": "case1", "k": 1, "candidate_count": 1}])
    spec = CleanCheckoutSpec(
        root=checkout,
        expected_commit="a" * 40,
        master_relative_path="master.json",
        source_config_relative_path="source.json",
        source=tmp_path / "source.blend",
        python_executable=Path("/python"),
        blender_executable=Path("/blender"),
        output=tmp_path / "fresh_joint",
        joint_release=True,
    )
    git_outputs = iter((spec.expected_commit, ""))
    monkeypatch.setattr(
        reproduction.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=next(git_outputs)),
    )
    commands: list[list[str]] = []
    boundary_calls: list[tuple[Path, Path, Path]] = []
    office_calls: list[dict[str, Path]] = []

    def native_rerun(arguments: list[str], *, root: Path) -> dict[str, Any]:
        assert root == checkout and not spec.output.exists()
        commands.append(arguments)
        shutil.copytree(local, spec.output)
        if failure == "joint_population":
            (spec.output / "case3_growth.json").write_text(
                json.dumps({"short_count": 1, "long_count": 9})
            )
        elif failure == "source_receipt":
            (spec.output / "primary_run_receipt.json").write_text(
                json.dumps({"source_unchanged": False, "master_file_sha256": digest(master)})
            )
        return {"arguments": arguments, "returncode": 0}

    def boundary(freeze: Path, config: Path, office: Path) -> None:
        boundary_calls.append((freeze, config, office))
        assert freeze.is_file() and config == master

    def office_comparison(**arguments: Path) -> dict[str, Any]:
        office_calls.append(arguments)
        return {"status": "FAIL" if failure == "office" else "PASS"}

    monkeypatch.setattr(reproduction, "_command", native_rerun)
    monkeypatch.setattr(scoped_protocol, "require_joint_inference_boundary", boundary)
    monkeypatch.setattr(reviewed_reproduction, "compare_reviewed_deliveries", office_comparison)
    arguments = dict(
        local_dataset=scoped / "dataset",
        local_inference=scoped / "inference_primary",
        local_evaluation=scoped / "evaluation",
    )
    if failure == "source_receipt":
        with pytest.raises(ValueError, match="source/master integrity"):
            clean_checkout_delivery(spec, **arguments)
        assert not office_calls
        return
    result = clean_checkout_delivery(spec, **arguments)
    assert len(commands) == 1 and commands[0][:3] == [
        "/python",
        str(checkout / "scripts/run_phase1_joint_case23.py"),
        "rerun",
    ]
    assert commands[0][-4:] == ["--config", str(master), "--output", str(spec.output)]
    assert len(boundary_calls) == 2 and len(office_calls) == 1
    assert office_calls[0]["local_inference"] == local / "office/inference_primary"
    assert office_calls[0]["fresh_dataset"] == spec.output / "office/dataset"
    assert result["scoped_comparison"]["status"] == "PASS"
    assert result["status"] == ("PASS" if failure is None else "FAIL")
    assert result["joint_release"] and result["all_stages_actually_executed"]
    assert not result["original_phase1_full_exit_or_freeze_granted"]
    assert read_json(spec.output / "delivery_comparison.json") == result
