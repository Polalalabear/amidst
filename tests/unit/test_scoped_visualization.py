"""Source-bound visualization checks; synthetic authority grants no research acceptance."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from rerun.chunk import RrdReader
from test_scoped_inference import _samples
from test_scoped_inference import approved as approved
from test_scoped_projection import _inputs_for
from test_scoped_projection import approved as _scaled_fixture

from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.finalization.formal_route_inventory import build_scoped_visibility_network
from amidst.finalization.scoped_class_search import produce_scoped_class_candidates
from amidst.finalization.scoped_inference import (
    ScopedBudgetLineage,
    ScopedInferenceConfig,
    bind_scoped_gaps,
    build_scoped_navigation,
    run_scoped_baseline,
)
from amidst.finalization.scoped_projection import ScopedSourceContext, project_scoped_observations
from amidst.finalization.scoped_visualization import (
    ScopedDemoRecord,
    build_scoped_presentation,
    write_scoped_demo,
)
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256


@pytest.fixture(scope="module")
def records(approved: Any) -> tuple[Any, list[ScopedDemoRecord]]:
    provider, config, binding = approved
    context = ScopedSourceContext(
        schema_version="phase1-scoped-source-context-v1",
        source_id=binding.source_id,
        spatial_context_id=binding.spatial_context_id,
        source_sha256=provider.source_sha256,
        scope_id=provider.scope_id,
        authority=config.authority,
        camera_bindings=provider.proposal.camera_landmark_bindings,
        coordinate_units="BLENDER_NATIVE_UNITS",
        metres_per_blender_unit=config.metres_per_blender_unit,
        observations_sha256="9" * 64,
        config_file_sha256=config.fresh_export_config_sha256,
        export_lock_file_sha256="d" * 64,
        ground_truth_available_to_inference=False,
    )
    aggregation = aggregate_frames(_samples(binding), config.aggregation_policy)
    gaps = bind_scoped_gaps(
        aggregation,
        provider,
        config,
        expected_stream_binding=binding,
        projection_observations_sha256=context.observations_sha256,
    )
    result = []
    for gap in gaps:
        navigation = build_scoped_navigation(gap, provider, config)
        network, mapping = build_scoped_visibility_network(
            provider,
            expected_binding=config.authority,
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_ids=(gap.start.observation.camera_id,),
            spatial_context_id=binding.spatial_context_id,
        )
        production = produce_scoped_class_candidates(
            provider,
            network,
            mapping,
            expected_binding=config.authority,
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_id=gap.start.observation.camera_id,
            gap_duration_s=gap.end.observation.start_time - gap.start.observation.end_time,
            movement=config.movement,
            policy=config.search_policy,
            clock=lambda: 0.0,
        )
        run = run_scoped_baseline(
            gap,
            navigation,
            "spatiotemporal",
            aggregation=aggregation,
            provider=provider,
            config=config,
            frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
            class_candidates=production,
            projection_observations_sha256=context.observations_sha256,
            clock=lambda: 0.0,
        )
        result.append(ScopedDemoRecord(aggregation, run, production, navigation, context, network))
    return provider, result


@pytest.fixture(scope="module")
def scaled_provider() -> Any:
    return _scaled_fixture.__wrapped__()


def test_presentation_retains_actual_union_hole_separate_guards_recoveries_and_provenance(
    records: Any,
) -> None:
    provider, items = records
    presentation = build_scoped_presentation(items, provider, case_id="case3")
    assert len(presentation["gaps"]) == 2
    assert len(presentation["aggregations"]) == 1
    assert presentation["geometry"]["hole_count"] == 1
    assert presentation["geometry"]["outer_rectangle_used_as_domain"] is False
    assert len(presentation["geometry"]["union"][0]["holes_m"]) == 1
    assert len(presentation["geometry"]["cells"]) == 4
    assert all(
        len(cell["body_guard_outline_m"]) == 12 for cell in presentation["geometry"]["cells"]
    )
    assert presentation["provenance"]["source_3d_footpoints"] == "PROJECTED"
    assert presentation["formal_acceptance"] is False
    assert len(next(iter(presentation["aggregations"].values()))["samples"]) == 5
    assert build_scoped_presentation(items, provider, case_id="case3") == presentation


def test_forged_source_context_or_duplicate_gap_refused_before_creating_output(
    records: Any, tmp_path: Path
) -> None:
    provider, items = records
    changed = replace(
        items[0], context=items[0].context.model_copy(update={"source_sha256": "f" * 64})
    )
    with pytest.raises(ValueError, match="lineage differs"):
        write_scoped_demo([changed], provider, tmp_path / "bad", case_id="case2")
    assert not (tmp_path / "bad").exists()
    with pytest.raises(ValueError, match="duplicate"):
        build_scoped_presentation([items[0], items[0]], provider, case_id="case2")


def test_actual_reader_contains_all_raw_samples_source_geometry_and_no_gt(
    records: Any, tmp_path: Path
) -> None:
    provider, items = records
    result = write_scoped_demo(items, provider, tmp_path / "demo", case_id="case3")
    assert result["rrd_reader_verified"] is True
    paths = {
        chunk.entity_path.lstrip("/").replace("\\", "")
        for chunk in RrdReader(Path(result["recording"])).stream()
    }
    assert len({path for path in paths if path.startswith("debug/source_samples/")}) == 5
    assert any("/holes/0" in path for path in paths)
    assert any(path.startswith("world/scoped_authority/body_guards/") for path in paths)
    assert any(path.startswith("world/source_observation_cameras/") for path in paths)
    assert any(path.startswith("cameras/") and "/source_pixels/" in path for path in paths)
    assert any(path.startswith("world/source_projected/") for path in paths)
    assert not any("ground_truth" in path.lower() for path in paths)
    with Image.open(result["preview"]) as image:
        assert image.width >= 1200 and image.height >= 700
        image.verify()
    with pytest.raises(FileExistsError):
        write_scoped_demo(items, provider, tmp_path / "demo", case_id="case3")


def test_source_camera_translation_and_union_scale_convert_once(scaled_provider: Any) -> None:
    provider = scaled_provider
    raw, context_raw = _inputs_for(provider)
    projected = project_scoped_observations(raw, context_raw, provider)
    policy = GraphSearchPolicy(max_candidate_paths=3, max_path_length_m=30.0, max_branch_factor=32)
    config = ScopedInferenceConfig(
        authority=projected.context.authority,
        fresh_export_config_sha256="c" * 64,
        source_camera_plane_ids={
            b.camera.camera_id: projected.context.plane_id
            for b in provider.proposal.camera_landmark_bindings
        },
        metres_per_blender_unit=2.0,
        movement=MovementConstraints(max_speed_m_s=100.0),
        search_policy=policy,
        budget_lineage=ScopedBudgetLineage(
            parent_inference_lock_content_sha256="d" * 64, parent_search_policy=policy
        ),
    )
    aggregation = aggregate_frames(projected.frames.samples)
    gap = bind_scoped_gaps(
        aggregation,
        provider,
        config,
        expected_stream_binding=projected.computation_context.binding,
        projection_sidecar=projected.sidecar,
        projection_observations_sha256=projected.context.observations_sha256,
    )[0]
    native = {sample.sample_id: sample for sample in projected.native_frames.samples}
    endpoints = []
    for _bound, sample_id in (
        (gap.start, gap.start.sample_ids[-1]),
        (gap.end, gap.end.sample_ids[0]),
    ):
        p = native[sample_id].projected_point.world_position
        endpoints.append((p[0], p[1], p[2] - 1.0))
    navigation = build_scoped_navigation(
        gap, provider, config, endpoint_positions_bu=tuple(endpoints)
    )
    network, mapping = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=endpoints[0],
        end_bu=endpoints[1],
        camera_ids=(gap.start.observation.camera_id,),
        spatial_context_id=gap.binding.spatial_context_id,
    )
    production = produce_scoped_class_candidates(
        provider,
        network,
        mapping,
        expected_binding=config.authority,
        start_bu=endpoints[0],
        end_bu=endpoints[1],
        camera_id=gap.start.observation.camera_id,
        gap_duration_s=0.4,
        movement=config.movement,
        policy=policy,
        clock=lambda: 0.0,
    )
    run = run_scoped_baseline(
        gap,
        navigation,
        "spatiotemporal",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        class_candidates=production,
        projection_sidecar=projected.sidecar,
        projection_observations_sha256=projected.context.observations_sha256,
        clock=lambda: 0.0,
    )
    payload = build_scoped_presentation(
        [ScopedDemoRecord(aggregation, run, production, navigation, projected.context, network)],
        provider,
        case_id="case2",
    )
    assert payload["source_observation_cameras"][0]["position_m"] == [4.0, 10.0, 20.0]
    assert payload["source_observation_cameras"][1]["position_m"] == [16.0, 10.0, 20.0]
    exterior = payload["geometry"]["union"][0]["exterior_m"]
    assert min(p[0] for p in exterior) == 4.0 and max(p[0] for p in exterior) == 16.0
    assert all(p[2] == 0.0 for p in exterior)
