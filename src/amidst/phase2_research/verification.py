"""Fresh deterministic rebuilds under virtual evaluator-sidecar poisoning/removal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import MODES
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.phase2_research.adapter import load_service
from amidst.phase2_research.pipeline import build, frozen, load
from amidst.research_accuracy.verify import denied_sidecars


def verify(output: Path, rebuild_root: Path) -> dict[str, Any]:
    package, _, manifest, policy = load(output)
    for name in manifest["variants"]:
        for mode in MODES:
            frozen(output, name, mode, manifest)
    sidecars = {
        package.simulation_export_path,
        DEFAULT_CONFIG,
        package.simulation_export_path.parent / "recipe.json",
        package.simulation_export_path.parent / "reference_annotations.json",
    }
    checks = {}
    for condition in ("replacement", "removal"):
        target = rebuild_root / condition
        with denied_sidecars(sidecars, removed=condition == "removal") as counts:
            rebuilt = build(
                Path(manifest["source_locator"]),
                target,
                policy,
                experiment_id=manifest["experiment_id"],
            )
            if rebuilt != manifest:
                raise ValueError("RESEARCH_FRESH_REBUILD_MISMATCH")
            service = load_service(target)
            context = service.context()
            for camera in context["camera_ids"]:
                service.query(context["binding"]["scene_id"], package.run_id, camera, 0, 30)
            if counts["attempted_reads"] != 0:
                raise ValueError("RESEARCH_RUNTIME_READ_EVALUATION_SIDECAR")
            checks[condition] = {
                "runtime_sidecar_read_attempts": counts["attempted_reads"],
                "manifest_sha256": digest(rebuilt),
                "all_variant_mode_hashes_identical": True,
            }
    return {
        "schema_version": "phase2.research.reproduction.v1",
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": digest(manifest),
        "checks": checks,
        "source_sidecars_virtually_replaced_only": True,
        "formal_phase1_acceptance": False,
    }
