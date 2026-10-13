"""Rebuild inference only with evaluator-only files inaccessible; no new evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import MODES
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.phase2_research.repair05_pipeline import build, frozen, load
from amidst.research_accuracy.verify import denied_sidecars


def verify(output: Path, rebuild_root: Path, *, test_authorized: bool = False) -> dict[str, Any]:
    package, _, manifest, _ = load(output)
    if package.split == "test" and not test_authorized:
        raise ValueError("REPAIR05_TEST_COORDINATION_REQUIRED")
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
        with denied_sidecars(sidecars, removed=condition == "removal") as counts:
            rebuilt = build(
                Path(manifest["source_locator"]),
                rebuild_root / condition,
                experiment_id=manifest["experiment_id"],
                test_authorized=test_authorized,
                development_selection=json.loads(
                    (output / "development_selection.json").read_bytes()
                )
                if package.split == "test"
                else None,
            )
            if rebuilt != manifest or counts["attempted_reads"]:
                raise ValueError("REPAIR05_REBUILD_OR_GT_ISOLATION_FAILED")
            checks[condition] = {
                "manifest_sha256": digest(rebuilt),
                "all_variant_mode_hashes_identical": True,
                "runtime_sidecar_read_attempts": counts["attempted_reads"],
            }
    return {
        "schema_version": "phase2.repair05.reproduction.v1",
        "manifest_sha256": digest(manifest),
        "checks": checks,
        "fresh_empty_outputs": True,
        "source_bytes_never_mutated": True,
        "evaluation_not_repeated": True,
        "detector_or_render_not_rerun": True,
        "formal_phase1_acceptance": False,
    }
