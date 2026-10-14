"""Joint-definition and before-GT boundary tests; no school source execution."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.metric_config import MetricConfig
from amidst.finalization import scoped_protocol as protocol
from amidst.finalization.reviewed_pipeline import (
    canonical_hashes,
    digest,
    freeze_inference,
    write_json,
)
from amidst.finalization.route_inventory import ReviewedCaseInferenceConfig
from amidst.finalization.scoped_authority import ScopeAuthorityPins
from amidst.obstacle_volume_authority import content_sha256

ROOT = Path(__file__).resolve().parents[2]


def _parent() -> ReviewedCaseInferenceConfig:
    document = json.loads((ROOT / protocol.OFFICE_INFERENCE_CONFIG).read_bytes())
    return ReviewedCaseInferenceConfig.model_validate(
        document["base_inference_lock"]["base_inference_config"]
    )


def _provider(parent: ReviewedCaseInferenceConfig) -> Any:
    pins = ScopeAuthorityPins(
        source_sha256=parent.source_sha256,
        protocol_sha256=parent.protocol_sha256,
        original_human_decisions_sha256=parent.human_decisions_sha256,
        camera_export_content_sha256="a" * 64,
        floor_content_sha256="b" * 64,
        evidence_content_sha256="c" * 64,
        physical_contract_content_sha256="d" * 64,
        numerics_content_sha256="e" * 64,
    )
    return SimpleNamespace(
        certificate=SimpleNamespace(
            pins=pins,
            proposal_content_sha256="a" * 64,
            human_decision_content_sha256="b" * 64,
            union_wkb_sha256="c" * 64,
        ),
        certificate_content_sha256="d" * 64,
        source_sha256=parent.source_sha256,
        scope_id="SYNTHETIC_TEST_ONLY_NO_SCHOOL_APPROVAL",
        proposal=SimpleNamespace(
            camera_landmark_bindings=tuple(
                SimpleNamespace(camera=SimpleNamespace(camera_id="synthetic-" + letter))
                for letter in ("a", "b")
            )
        ),
        contract=SimpleNamespace(scale=SimpleNamespace(metres_per_blender_unit=0.0247)),
    )


def test_complete_original_budget_and_timing_are_carried_without_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(protocol, "validate_scoped_inference_config", lambda value, _: value)
    parent = _parent()
    result = protocol.config_from_original_parent(_provider(parent), parent, "f" * 64)
    assert result.search_policy == parent.search_policy
    assert result.movement == parent.movement
    assert result.reconstruction_policy == parent.reconstruction_policy
    assert result.aggregation_policy.max_visible_sample_gap_s == 0.200001
    assert result.budget_lineage.changed_search_fields == ()
    assert result.budget_lineage.parent_inference_lock_content_sha256 == content_sha256(
        parent.model_dump(mode="json")
    )
    assert result.fresh_export_config_sha256 == "f" * 64
    assert not any(name in result.model_dump_json() for name in ('"waypoints"', '"ground_truth"'))


def test_changed_original_budget_or_source_cannot_become_a_new_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(protocol, "validate_scoped_inference_config", lambda value, _: value)
    parent = _parent()
    altered = parent.model_copy(
        update={"search_policy": parent.search_policy.model_copy(update={"max_search_nodes": 2000})}
    )
    with pytest.raises(ValidationError, match="budgets/speed/timing"):
        protocol.config_from_original_parent(_provider(parent), altered, "f" * 64)
    provider = _provider(parent)
    provider.source_sha256 = "f" * 64
    with pytest.raises(ValueError, match="parent source/protocol/HR/scale"):
        protocol.config_from_original_parent(provider, parent, "f" * 64)


def test_producer_population_follows_lazy_and_transitive_imports_without_output_self_hash(
    tmp_path: Path,
) -> None:
    finalization = tmp_path / "src/amidst/finalization"
    finalization.mkdir(parents=True)
    (finalization / "joint.py").write_text(
        "def lazy():\n    from amidst.graph.engine import Engine\n"
    )
    graph = tmp_path / "src/amidst/graph"
    graph.mkdir()
    (graph / "engine.py").write_text("class Engine: pass\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "run_phase1_reviewed.py",
        "export_phase1_reviewed_inputs.py",
        "export_phase1_scoped_inputs.py",
        "export_blender_pilot.py",
        "phase1_projection_policy.py",
        "projection_multiview_model.py",
        "projection_mitigation_policy.py",
        "projection_uncertainty_model.py",
        "run_phase1_scoped_case23.py",
        "run_phase1_joint_case23.py",
    ):
        (scripts / name).write_text("# synthetic producer fixture\n")
    first = protocol.producer_hashes(tmp_path)
    assert "src/amidst/graph/engine.py" in first
    assert "scripts/run_phase1_joint_case23.py" in first
    write_json(tmp_path / "master.json", {"producer_hashes": first})
    assert protocol.producer_hashes(tmp_path) == first
    (graph / "engine.py").write_text("class ChangedEngine: pass\n")
    assert protocol.producer_hashes(tmp_path) != first


@pytest.mark.parametrize("changed", ["producer", "protected", "metric", "case_ids"])
def test_master_cannot_omit_pins_or_change_metrics_or_drop_source_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    monkeypatch.setattr(protocol, "validate_protocol", lambda *_: None)
    monkeypatch.setattr(protocol, "validate_scoped_inference_config", lambda value, _: value)
    parent = _parent()
    monkeypatch.setattr(
        protocol,
        "load_reviewed_collision_lock",
        lambda *_args, **_kwargs: SimpleNamespace(
            base_inference_lock=SimpleNamespace(base_inference_config=parent)
        ),
    )
    monkeypatch.setattr(protocol, "protected_input_hashes", lambda *_: {"input.json": "a" * 64})
    monkeypatch.setattr(protocol, "producer_hashes", lambda *_: {"producer.py": "b" * 64})
    source = tmp_path / "source.json"
    write_json(
        source,
        {"cases": [{"case_id": "case2"}, {"case_id": "case3"}, {"case_id": "case3_short_control"}]},
    )
    write_json(
        tmp_path / protocol.OFFICE_APPLICATION / "approved_input_lock.json",
        {
            "coverage": {
                "epsilon_m": 0.5,
                "distance_metric": "ADE",
                "comparison": "STRICTLY_LESS_THAN",
            },
            "automatic_settings": {
                "k_values": [1, 2, 3],
                "physical_policy": {"collision_tolerance_m": 0.001},
            },
        },
    )
    config = protocol.config_from_original_parent(_provider(parent), parent, digest(source))
    metrics = MetricConfig(
        metric_config_version="phase1-reviewed-metric-computation-v1",
        k_values=(1, 2, 3),
        coverage_epsilon_m=0.5,
        collision_tolerance_m=0.001,
    )
    document = {
        "source_config_path": "source.json",
        "source_config_file_sha256": digest(source),
        "source_config_content_sha256": content_sha256(json.loads(source.read_bytes())),
        "source_case_ids": ["case2", "case3", "case3_short_control"],
        "inference_config": config.model_dump(mode="json"),
        "inference_config_content_sha256": content_sha256(config.model_dump(mode="json")),
        "metric_config": metrics.model_dump(mode="json"),
        "metric_config_content_sha256": content_sha256(metrics.model_dump(mode="json")),
        "source_sha256": parent.source_sha256,
        "protocol_file_sha256": parent.protocol_sha256,
        "original_human_decisions_content_sha256": parent.human_decisions_sha256,
        "inference_seed": 42,
        "export_seed": 20261005,
        "sampling_fps": 5,
        "original_research_budget_modified": False,
        "definition_self_sha256_included": False,
        "protected_input_hashes": {"input.json": "a" * 64},
        "producer_hashes": {"producer.py": "b" * 64},
    }
    original_reader = protocol.read_json

    def public_reader(path: Path) -> dict[str, Any]:
        if path == source:
            raise AssertionError("inference gates may hash but never parse source recipes")
        return original_reader(path)

    monkeypatch.setattr(protocol, "read_json", public_reader)
    protocol.validate_master_bindings(document, tmp_path)
    if changed in {"producer", "protected"}:
        document[changed + ("_hashes" if changed == "producer" else "_input_hashes")] = {}
    elif changed == "metric":
        document["metric_config"]["coverage_epsilon_m"] = 1.0
    else:
        document["source_case_ids"] = ["case2"]
    with pytest.raises(ValueError, match="omits an exact pin"):
        protocol.validate_master_bindings(document, tmp_path)


def _joint(tmp_path: Path) -> tuple[Path, Path, Path]:
    master = tmp_path / "master.json"
    original_office_config = tmp_path / protocol.OFFICE_INFERENCE_CONFIG
    write_json(original_office_config, {"synthetic_fixture": "original inference lock bytes"})
    office_config_sha = digest(original_office_config)
    scoped_config = {"synthetic_fixture": "source inference configuration"}
    selection = {"case1": "office", "case2": "scoped", "case3": "scoped"}
    office = {
        "application_path": protocol.OFFICE_APPLICATION,
        "inference_config_path": protocol.OFFICE_INFERENCE_CONFIG,
        "export_config_path": protocol.OFFICE_EXPORT_CONFIG,
    }
    write_json(
        master,
        {
            "source_sha256": "a" * 64,
            "export_seed": 20261005,
            "inference_seed": 42,
            "sampling_fps": 5,
            "source_config_file_sha256": "c" * 64,
            "source_case_ids": ["case2", "case3"],
            "joint_release_selection": selection,
            "office_child": office,
            "original_human_decisions_content_sha256": "e" * 64,
            "protected_input_hashes": {
                protocol.OFFICE_INFERENCE_CONFIG: office_config_sha,
                protocol.OFFICE_EXPORT_CONFIG: "c" * 64,
                protocol.OFFICE_APPLICATION + "/manifest.json": "d" * 64,
            },
            "inference_config_content_sha256": content_sha256(scoped_config),
        },
    )
    children = {}
    datasets = {}
    for role in ("office", "scoped"):
        directory = tmp_path / role / "inference_primary"
        dataset = tmp_path / role / "dataset"
        manifest = {
            "dataset_version": "synthetic-" + role,
            "source_sha256": "a" * 64,
            "export_seed": 20261005,
            "inference_seed": 42,
            "sampling_fps": 5,
        }
        if role == "office":
            manifest.update(
                config_sha256="c" * 64,
                application_manifest_sha256="d" * 64,
                human_decisions_sha256="e" * 64,
            )
        else:
            manifest.update(
                full_experiment_config_file_sha256=digest(master),
                config_file_sha256="c" * 64,
                cases=[{"case_id": "case2"}, {"case_id": "case3"}],
            )
        write_json(dataset / "manifest.json", manifest)
        write_json(directory / "prediction.json", {"provenance": "INFERRED", "role": role})
        if role == "office":
            (directory / "collision_inference_lock.json").write_bytes(
                original_office_config.read_bytes()
            )
        else:
            write_json(directory / "config.json", scoped_config)
            (directory / "experiment.json").write_bytes(master.read_bytes())
        freeze_inference(
            directory,
            dataset_manifest_sha256=digest(dataset / "manifest.json"),
            config_sha256=office_config_sha if role == "office" else digest(master),
        )
        children[role] = {
            "directory": directory.relative_to(tmp_path).as_posix(),
            "freeze_file_sha256": digest(directory / "inference_freeze.json"),
        }
        datasets[role] = {
            "directory": dataset.relative_to(tmp_path).as_posix(),
            "manifest_file_sha256": digest(dataset / "manifest.json"),
            "dataset_version": manifest["dataset_version"],
        }
    joint = tmp_path / "joint_inference_freeze.json"
    write_json(
        joint,
        {
            "schema_version": "phase1-joint-inference-freeze-v1",
            "master_file_sha256": digest(master),
            "children": children,
            "datasets": datasets,
            "source_sha256": "a" * 64,
            "case_selection": selection,
            "ground_truth_read": False,
            "status": "ALL_PRIMARY_CHILDREN_FROZEN_BEFORE_ANY_REFERENCE_EVALUATION",
        },
    )
    return joint, master, tmp_path / "office/inference_primary"


def test_joint_boundary_requires_both_exact_primary_freezes(tmp_path: Path) -> None:
    joint, master, office = _joint(tmp_path)
    protocol.require_joint_inference_boundary(joint, master, office)
    (tmp_path / "scoped/inference_primary/prediction.json").write_text("{}\n")
    with pytest.raises(ValueError, match="changed after freeze"):
        protocol.require_joint_inference_boundary(joint, master, office)


def test_second_child_manifest_is_rechecked_at_each_gt_boundary(tmp_path: Path) -> None:
    joint, master, office = _joint(tmp_path)
    protocol.require_joint_inference_boundary(joint, master, office)
    manifest = tmp_path / "scoped/dataset/manifest.json"
    document = json.loads(manifest.read_bytes())
    document["dataset_version"] = "foreign-source-run"
    manifest.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="dataset manifest/source/seed/sampling"):
        protocol.require_joint_inference_boundary(joint, master, office)


@pytest.mark.parametrize("role", ["office", "scoped"])
def test_valid_foreign_child_with_same_source_and_seeds_is_not_the_frozen_joint_child(
    tmp_path: Path,
    role: str,
) -> None:
    joint, master, office = _joint(tmp_path)
    path = tmp_path / role / "inference_primary/inference_freeze.json"
    frozen = json.loads(path.read_bytes())
    frozen["config_sha256"] = "f" * 64
    path.write_text(json.dumps(frozen))
    document = json.loads(joint.read_bytes())
    document["children"][role]["freeze_file_sha256"] = digest(path)
    joint.write_text(json.dumps(document))
    with pytest.raises(
        ValueError, match="original configuration/approval|exact master/source config"
    ):
        protocol.require_joint_inference_boundary(joint, master, office)


@pytest.mark.parametrize(
    "role,artifact",
    [
        ("office", "collision_inference_lock.json"),
        ("scoped", "config.json"),
        ("scoped", "experiment.json"),
    ],
)
def test_reissued_valid_child_freeze_cannot_replace_exact_public_configurations(
    tmp_path: Path,
    role: str,
    artifact: str,
) -> None:
    joint, master, office = _joint(tmp_path)
    directory = tmp_path / role / "inference_primary"
    (directory / artifact).write_text('{"foreign_configuration": true}\n')
    freeze_path = directory / "inference_freeze.json"
    frozen = json.loads(freeze_path.read_bytes())
    frozen["artifacts"] = canonical_hashes(directory)
    freeze_path.write_text(json.dumps(frozen))
    document = json.loads(joint.read_bytes())
    document["children"][role]["freeze_file_sha256"] = digest(freeze_path)
    joint.write_text(json.dumps(document))
    with pytest.raises(
        ValueError, match="original configuration/approval|exact master/source config"
    ):
        protocol.require_joint_inference_boundary(joint, master, office)


@pytest.mark.parametrize("replacement", [None, 0, "missing"])
def test_joint_child_requires_explicit_false_ground_truth_receipt(
    tmp_path: Path,
    replacement: object,
) -> None:
    joint, master, office = _joint(tmp_path)
    path = tmp_path / "scoped/inference_primary/inference_freeze.json"
    frozen = json.loads(path.read_bytes())
    if replacement == "missing":
        del frozen["ground_truth_read"]
    else:
        frozen["ground_truth_read"] = replacement
    path.write_text(json.dumps(frozen))
    document = json.loads(joint.read_bytes())
    document["children"]["scoped"]["freeze_file_sha256"] = digest(path)
    joint.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="differs from its exact child"):
        protocol.require_joint_inference_boundary(joint, master, office)


def test_wrong_joint_child_or_master_cannot_open_office_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    joint, master, office = _joint(tmp_path)
    calls = []
    monkeypatch.setattr(protocol, "validate_master_bindings", lambda *_: None)
    monkeypatch.setattr(protocol, "evaluate_dataset", lambda *_args, **_kwargs: calls.append("GT"))
    document = json.loads(joint.read_bytes())
    del document["children"]["scoped"]
    joint.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="complete same-master"):
        protocol.evaluate_office_child(
            tmp_path, office.parent, master_path=master, joint_freeze_path=joint
        )
    assert calls == []


def test_original_office_plan_retains_configs_and_disables_blender_autoexec(tmp_path: Path) -> None:
    plan = protocol.office_child_plan(ROOT, Path("source.blend"), Path("blender"), tmp_path)
    assert "--disable-autoexec" in plan.export_argv
    assert str(ROOT / protocol.OFFICE_EXPORT_CONFIG) in plan.export_argv
    assert plan.config == ROOT / protocol.OFFICE_INFERENCE_CONFIG
    assert plan.application == ROOT / protocol.OFFICE_APPLICATION
