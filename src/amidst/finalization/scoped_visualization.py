"""GT-free source/cell-union replay from frozen scoped inference models.

Presentation never projects, searches, evaluates, opens source assets, or reads a
dataset partition. OBSERVED pixels remain 2D; source-calibrated 3D footpoints are
PROJECTED and hypotheses remain INFERRED_GAP. Every missing sample and recovery
is retained. The exact union includes its holes and is not an outer rectangle.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from shapely import from_wkb
from shapely.geometry import MultiPolygon, Polygon

from amidst.domain.evidence import VisibilityStatus
from amidst.domain.stream import BoundGapEvent, ObservationAggregation, StreamBinding
from amidst.finalization.formal_route_inventory import _prepare_scoped_operation
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_class_search import ScopedClassSearchResult
from amidst.finalization.scoped_inference import ScopedBaselineRun, ScopedNavigationGraph
from amidst.finalization.scoped_projection import ScopedSourceContext
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.navigation.network import NavigationNetwork
from amidst.obstacle_volume_authority import content_sha256

GAP_COLORS = ((209, 119, 42), (114, 77, 181), (184, 61, 105), (38, 142, 150))


@dataclass(frozen=True, slots=True)
class ScopedDemoRecord:
    aggregation: ObservationAggregation
    run: ScopedBaselineRun
    production: ScopedClassSearchResult
    navigation: ScopedNavigationGraph
    context: ScopedSourceContext
    visibility_network: NavigationNetwork


def _name(value: str) -> str:
    return quote(value, safe="-_.")


def _wire_box(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    ratio: float,
) -> list[list[list[float]]]:
    low, high = bounds
    corners = [
        [(high[axis] if index & (1 << axis) else low[axis]) * ratio for axis in range(3)]
        for index in range(8)
    ]
    return [
        [corners[index], corners[index ^ (1 << axis)]]
        for index in range(8)
        for axis in range(3)
        if not index & (1 << axis)
    ]


def _authority(provider: ScopedUnionPhysicalProvider) -> ScopedRouteAuthorityBinding:
    certificate = provider.certificate
    return ScopedRouteAuthorityBinding(
        pins=certificate.pins,
        proposal_content_sha256=certificate.proposal_content_sha256,
        decision_content_sha256=certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=certificate.union_wkb_sha256,
    )


def build_scoped_presentation(
    records: Sequence[ScopedDemoRecord],
    provider: ScopedUnionPhysicalProvider,
    *,
    case_id: str,
) -> dict[str, Any]:
    """Validate frozen lineage without reopening numerical evidence or any GT file."""
    if case_id not in {"case2", "case3"} or not records:
        raise ValueError("scoped replay requires a nonempty Case2/Case3 frozen selection")
    expected = _authority(provider)
    prepared = _prepare_scoped_operation(provider, expected)
    provider = prepared.provider
    ratio = provider.contract.scale.metres_per_blender_unit
    floor_z = provider.proposal.floor.point[2]
    union = from_wkb(bytes.fromhex(provider.certificate.union_wkb_hex))
    if not isinstance(union, (Polygon, MultiPolygon)):
        raise ValueError("scoped replay requires the exact approved polygon union")
    polygons = [union] if isinstance(union, Polygon) else list(union.geoms)
    outlines = []
    for polygon in polygons:
        outlines.append(
            {
                "exterior_m": [
                    [float(x) * ratio, float(y) * ratio, floor_z * ratio]
                    for x, y in polygon.exterior.coords
                ],
                "holes_m": [
                    [[float(x) * ratio, float(y) * ratio, floor_z * ratio] for x, y in ring.coords]
                    for ring in polygon.interiors
                ],
            }
        )
    cells = []
    for cell in provider.proposal.cells:
        ax, ay, bx, by = cell.rectangle_xy_bu
        cells.append(
            {
                "cell_id": cell.cell_id,
                "outline_m": [
                    [x * ratio, y * ratio, floor_z * ratio]
                    for x, y in ((ax, ay), (bx, ay), (bx, by), (ax, by), (ax, ay))
                ],
                "body_guard_outline_m": _wire_box(cell.proposed_body_guard_bounds_bu, ratio),
                "proposal_content_sha256": content_sha256(cell.model_dump(mode="json")),
            }
        )
    gaps, aggregations, contexts = [], {}, {}
    gap_ids: set[str] = set()
    cameras = {b.camera.camera_id: b for b in provider.proposal.camera_landmark_bindings}
    for ordinal, record in enumerate(records):
        context = ScopedSourceContext.model_validate_json(record.context.model_dump_json())
        aggregation = ObservationAggregation.model_validate(record.aggregation.model_dump())
        run = ScopedBaselineRun.model_validate_json(record.run.model_dump_json())
        production = ScopedClassSearchResult.model_validate_json(
            record.production.model_dump_json()
        )
        navigation = ScopedNavigationGraph.model_validate_json(record.navigation.model_dump_json())
        stream = StreamBinding(
            source_id=context.source_id,
            spatial_context_id=context.spatial_context_id,
            source_asset_sha256=context.source_sha256,
        )
        if (
            context.authority != expected
            or run.authority != expected
            or production.authority != expected
            or (
                context.source_sha256 != provider.source_sha256
                or context.scope_id != provider.scope_id
                or context.metres_per_blender_unit != ratio
                or any(cameras.get(b.camera.camera_id) != b for b in context.camera_bindings)
                or run.method_id != "spatiotemporal"
                or run.ablation_id is not None
                or run.production_class_search != production
                or run.gap_binding.binding != stream
                or any(sample.binding != stream for sample in aggregation.samples)
                or content_sha256(aggregation.model_dump(mode="json"))
                != run.gap_binding.aggregation_content_sha256
                or run.frozen_config_sha256 != run.gap_binding.config_content_sha256
                or run.gap_binding.projection_observations_sha256 != context.observations_sha256
                or content_sha256(navigation.model_dump(mode="json"))
                != run.navigation_content_sha256
                or navigation.authority != expected
                or navigation.graph != record.visibility_network.navigation.config
                or production.navigation_content_sha256
                != content_sha256(
                    record.visibility_network.navigation.config.model_dump(mode="json"),
                )
                or production.topology_content_sha256
                != content_sha256(
                    record.visibility_network.topology.config.model_dump(mode="json"),
                )
                or production.source_edge_geometry_content_sha256
                != content_sha256(navigation.source_edge_polylines_bu)
            )
        ):
            raise ValueError(
                "scoped replay source/authority/aggregation/run/class/network lineage differs"
            )
        bound = BoundGapEvent(
            binding=stream,
            start=run.gap_binding.start,
            end=run.gap_binding.end,
            search_result=run.timed_result,
            event=run.event,
        )
        if bound != run.bound_gap or run.gap_binding.gap_id in gap_ids:
            raise ValueError("scoped replay cannot substitute or duplicate an independent GAP")
        gap_ids.add(run.gap_binding.gap_id)
        for candidate in run.event.candidates:
            if candidate.provenance.value != "INFERRED_GAP":
                raise ValueError("scoped replay cannot relabel truth as an inferred route")
        aggregation_sha = content_sha256(aggregation.model_dump(mode="json"))
        aggregations[aggregation_sha] = aggregation.model_dump(mode="json")
        context_sha = content_sha256(context.model_dump(mode="json"))
        contexts[context_sha] = context.model_dump(mode="json")
        gaps.append(
            {
                "ordinal": ordinal,
                "gap_id": run.gap_binding.gap_id,
                "display_color_rgb": GAP_COLORS[ordinal % len(GAP_COLORS)],
                "context_content_sha256": context_sha,
                "aggregation_content_sha256": aggregation_sha,
                "run_content_sha256": content_sha256(run.model_dump(mode="json")),
                "production_content_sha256": content_sha256(production.model_dump(mode="json")),
                "navigation_content_sha256": run.navigation_content_sha256,
                "event": run.event.model_dump(mode="json"),
                "run": run.model_dump(mode="json"),
                "production": production.model_dump(mode="json"),
            }
        )
    source_cameras = []
    for identity, binding in sorted(cameras.items()):
        matrix = binding.camera.camera_to_world
        origin = [matrix[axis][3] * ratio for axis in range(3)]
        norm = math.sqrt(sum(matrix[axis][2] ** 2 for axis in range(3)))
        if norm <= 0:
            raise ValueError("source camera optical direction is invalid")
        heading = [origin[axis] - matrix[axis][2] / norm for axis in range(3)]
        source_cameras.append(
            {
                "camera_id": identity,
                "source_calibration": binding.camera.model_dump(mode="json"),
                "calibration_content_sha256": binding.calibration_content_sha256,
                "camera_export_content_sha256": binding.source_camera_export_content_sha256,
                "position_m": origin,
                "heading_display_endpoint_m": heading,
                "heading_display_length_m": 1.0,
                "intrinsics_units": "PIXELS_UNCHANGED",
                "source_extrinsic_translation_units": "BLENDER_NATIVE_UNITS",
            }
        )
    return {
        "schema_version": "phase1-scoped-source-presentation-v1",
        "case_id": case_id,
        "status": "SCOPED_SOURCE_BOUND_VISUALIZATION",
        "formal_acceptance": False,
        "ground_truth_logged_to_primary_recording": False,
        "ground_truth_read": False,
        "gt_debug_default_visible": False,
        "source_blend_opened_saved_or_copied": False,
        "source_sha256": provider.source_sha256,
        "scope_id": provider.scope_id,
        "authority": expected.model_dump(mode="json"),
        "coordinate_units": "METRES",
        "metres_per_blender_unit": ratio,
        "source_floor_z_bu": floor_z,
        "geometry": {
            "union": outlines,
            "cells": cells,
            "outer_rectangle_used_as_domain": False,
            "hole_count": sum(len(polygon.interiors) for polygon in polygons),
        },
        "source_observation_cameras": source_cameras,
        "contexts": contexts,
        "aggregations": aggregations,
        "gaps": gaps,
        "provenance": {
            "pixels": "OBSERVED",
            "source_3d_footpoints": "PROJECTED",
            "candidate_paths_and_interpolation": "INFERRED_GAP",
        },
        "presentation_sampling_hz": 1.0,
        "source_timestamps_changed": False,
        "marker_lifetime": "CLEAR_AT_NEXT_EXISTING_SOURCE_TIMESTAMP_AFTER_GAP_END",
        "full_raw_samples_and_recoveries_retained": True,
        "requested_k_is_not_padded": True,
        "rrd_reader_verified": False,
    }


def _write_recording(
    presentation: dict[str, Any], output: Path, records: Sequence[ScopedDemoRecord]
) -> None:
    import rerun as rr
    import rerun.blueprint as rrb

    from amidst.visualization import RerunDebugVisualizationAdapter
    from amidst.visualization.rerun_adapter import EVENT_TIMELINE

    observations = {
        item.observation.observation_id: item.observation
        for record in records
        for item in record.aggregation.observations
    }
    recording = rr.RecordingStream("amidst_scoped_source_replay")
    adapter = RerunDebugVisualizationAdapter(
        observations=tuple(observations.values()), recording=recording, debug_mode=False
    )
    adapter.save(output)
    recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    recording.log(
        "debug/scoped_authority",
        rr.TextDocument(
            json.dumps(
                {
                    key: presentation[key]
                    for key in (
                        "case_id",
                        "status",
                        "source_sha256",
                        "scope_id",
                        "authority",
                        "coordinate_units",
                        "provenance",
                    )
                },
                sort_keys=True,
                indent=2,
            )
        ),
        static=True,
    )
    for index, polygon in enumerate(presentation["geometry"]["union"]):
        root = f"world/scoped_authority/union/{index}"
        recording.log(
            root + "/exterior",
            rr.LineStrips3D(
                [polygon["exterior_m"]],
                colors=(40, 145, 95),
                radii=0.012,
                labels=["Exact approved cell union"],
            ),
            static=True,
        )
        for hole_index, hole in enumerate(polygon["holes_m"]):
            recording.log(
                root + f"/holes/{hole_index}",
                rr.LineStrips3D(
                    [hole], colors=(178, 55, 67), radii=0.014, labels=["Excluded source union hole"]
                ),
                static=True,
            )
    for cell in presentation["geometry"]["cells"]:
        name = _name(cell["cell_id"])
        recording.log(
            "world/scoped_authority/cells/" + name,
            rr.LineStrips3D(
                [cell["outline_m"]],
                colors=(110, 160, 130),
                radii=0.004,
                labels=["Certified cell " + cell["cell_id"]],
            ),
            static=True,
        )
        recording.log(
            "world/scoped_authority/body_guards/" + name,
            rr.LineStrips3D(
                cell["body_guard_outline_m"],
                colors=(145, 150, 155),
                radii=0.002,
                labels=["Cell body guard"] * 12,
            ),
            static=True,
        )
    for camera in presentation["source_observation_cameras"]:
        root = "world/source_observation_cameras/" + _name(camera["camera_id"])
        recording.log(
            root + "/pose",
            rr.Points3D(
                [camera["position_m"]],
                colors=(43, 148, 185),
                radii=0.07,
                labels=["Actual source calibration " + camera["camera_id"]],
            ),
            static=True,
        )
        recording.log(
            root + "/heading",
            rr.LineStrips3D(
                [[camera["position_m"], camera["heading_display_endpoint_m"]]],
                colors=(43, 148, 185),
                radii=0.012,
                labels=["Optical heading; 1 m display length"],
            ),
            static=True,
        )
        recording.log(
            "debug/source_calibration/" + _name(camera["camera_id"]),
            rr.TextDocument(json.dumps(camera, sort_keys=True, indent=2)),
            static=True,
        )
    # Log all source samples, including those not selected as any GAP endpoint.
    seen: set[str] = set()
    for record in records:
        for sample in record.aggregation.samples:
            if sample.sample_id in seen:
                continue
            seen.add(sample.sample_id)
            camera, target = _name(sample.camera_id), _name(sample.target_id)
            pixel_path = f"cameras/{camera}/source_pixels/{target}/marker"
            point_path = f"world/source_projected/{camera}/{target}/marker"
            recording.set_time(EVENT_TIMELINE, duration=sample.timestamp)
            if sample.visibility == VisibilityStatus.GAP:
                recording.log(pixel_path, rr.Clear(recursive=True))
                recording.log(point_path, rr.Clear(recursive=True))
            else:
                if sample.uv is not None:
                    recording.log(
                        pixel_path,
                        rr.Points2D(
                            [sample.uv],
                            colors=(51, 164, 98),
                            radii=3,
                            labels=["OBSERVED source pixels"],
                        ),
                    )
                if sample.projected_point is not None:
                    recording.log(
                        point_path,
                        rr.Points3D(
                            [sample.projected_point.world_position],
                            colors=(47, 112, 184),
                            radii=0.08,
                            labels=[
                                "PROJECTED from source pixels; " + sample.projected_point.plane_id
                            ],
                        ),
                    )
                else:
                    recording.log(point_path, rr.Clear(recursive=True))
            recording.log(
                "debug/source_samples/" + _name(sample.sample_id),
                rr.TextDocument(sample.model_dump_json()),
                static=True,
            )
    for ordinal, record in enumerate(records):
        adapter.log_event(record.run.event)
        event = record.run.event
        color = GAP_COLORS[ordinal % len(GAP_COLORS)]
        for rank, candidate in enumerate(event.candidates, 1):
            recording.log(
                f"world/scoped_inferred/gap{ordinal:02d}/rank{rank}",
                rr.LineStrips3D(
                    [candidate.polyline],
                    colors=color,
                    radii=0.022,
                    labels=[
                        f"INFERRED_GAP {event.time_range[0]:g}–{event.time_range[1]:g}s Top-{rank}"
                    ],
                ),
                static=True,
            )
        future = [
            sample.timestamp
            for sample in record.aggregation.samples
            if sample.timestamp > event.time_range[1]
        ]
        if future:
            clear_time = min(future)
            recording.set_time(EVENT_TIMELINE, duration=clear_time)
            event_path = _name(event.event_id)
            for hypothesis in event.trajectories:
                recording.log(
                    f"world/events/{event_path}/hypotheses/{_name(hypothesis.hypothesis_id)}/marker",
                    rr.Clear(recursive=True),
                )
    recording.send_blueprint(
        rrb.Blueprint(
            rrb.Horizontal(
                rrb.Spatial3DView(
                    origin="/world",
                    name="Source scope / PROJECTED + INFERRED_GAP",
                    contents=[
                        "+ /world/**",
                        "- /world/projected/**",
                        "- /world/events/**/candidates/**",
                    ],
                ),
                rrb.TextDocumentView(
                    origin="/debug/scoped_authority", name="Source authority / limits"
                ),
            ),
            auto_views=False,
            auto_layout=False,
        )
    )
    adapter.close()


def _write_preview(presentation: dict[str, Any], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as PlotPolygon

    figure, (axis, info) = plt.subplots(
        1, 2, figsize=(13, 7), gridspec_kw={"width_ratios": [3.5, 1]}
    )
    figure.suptitle(presentation["case_id"].upper() + " · Source-bound scoped replay", fontsize=16)
    axis.set_title("PROJECTED footpoints · INFERRED_GAP routes · no Ground Truth", fontsize=10)
    for index, polygon in enumerate(presentation["geometry"]["union"]):
        points = polygon["exterior_m"]
        axis.add_patch(
            PlotPolygon(
                [(p[0], p[1]) for p in points],
                facecolor="#eaf3ed",
                edgecolor="#287b54",
                linewidth=1.5,
                label="Exact approved union" if index == 0 else None,
            )
        )
        for hole_index, hole in enumerate(polygon["holes_m"]):
            axis.add_patch(
                PlotPolygon(
                    [(p[0], p[1]) for p in hole],
                    facecolor="white",
                    edgecolor="#b23743",
                    hatch="///",
                    linewidth=1.1,
                    label="Excluded hole" if index == hole_index == 0 else None,
                )
            )
    for cell in presentation["geometry"]["cells"]:
        points = cell["outline_m"]
        axis.plot([p[0] for p in points], [p[1] for p in points], color="#7a9c86", linewidth=0.5)
    plotted: set[str] = set()
    all_points = []
    for aggregation in presentation["aggregations"].values():
        for item in aggregation["observations"]:
            observation = item["observation"]
            points = [p["world_position"] for p in observation["projected_path"]]
            all_points.extend(points)
            if points:
                camera = observation["camera_id"]
                axis.scatter(
                    [p[0] for p in points],
                    [p[1] for p in points],
                    s=10,
                    c="#2f70b8",
                    zorder=3,
                    alpha=0.75,
                    label="PROJECTED · " + camera if camera not in plotted else None,
                )
                plotted.add(camera)
    for gap in presentation["gaps"]:
        color = [v / 255 for v in gap["display_color_rgb"]]
        event = gap["event"]
        start, end = event["time_range"]
        for rank, candidate in enumerate(event["candidates"], 1):
            points = candidate["polyline"]
            all_points.extend(points)
            axis.plot(
                [p[0] for p in points],
                [p[1] for p in points],
                color=color,
                linestyle=("--" if rank == 1 else ":"),
                linewidth=1.8,
                label=f"GAP {gap['ordinal'] + 1} {start:g}–{end:g}s · Top-{rank}",
                zorder=4,
            )
    exterior_points = [
        p for polygon in presentation["geometry"]["union"] for p in polygon["exterior_m"]
    ]
    all_points.extend(exterior_points)
    xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    margin = max(dx, dy) * 0.07
    axis.set(
        xlim=(min(xs) - margin, max(xs) + margin),
        ylim=(min(ys) - margin, max(ys) + margin),
        xlabel="Source X (m)",
        ylabel="Source Y (m)",
    )
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.12)
    axis.legend(loc="best", fontsize=7, framealpha=0.95)
    info.axis("off")
    lines = [
        "Frozen selection",
        "",
        f"{len(presentation['gaps'])} independent GAPs",
        f"{len(presentation['geometry']['cells'])} approved cells",
        f"{presentation['geometry']['hole_count']} excluded hole(s)",
        "",
        "Each 3D source point is PROJECTED.",
        "Pixels remain OBSERVED 2D.",
        "Routes are INFERRED_GAP.",
        "",
        "Source camera calibration:",
    ]
    for camera in presentation["source_observation_cameras"]:
        lines.extend(
            [camera["camera_id"], "  XYZ m: " + ", ".join(f"{v:.3f}" for v in camera["position_m"])]
        )
    lines.extend(
        [
            "",
            "RRD: source-time replay,",
            "camera poses and cell body guards.",
            "",
            "No GT · no K padding",
            "Visualization does not grant",
            "formal research acceptance.",
        ]
    )
    info.text(
        0, 1, "\n".join(lines), transform=info.transAxes, va="top", fontsize=9, linespacing=1.4
    )
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    figure.savefig(output, dpi=130, facecolor="white")
    plt.close(figure)


def verify_scoped_recording(path: Path) -> dict[str, Any]:
    """Actually read the new RRD footer/chunks; no GT-bearing recording is accepted."""
    from rerun.chunk import RrdReader

    reader = RrdReader(path)
    recording_count = len(reader.recordings())
    store_count = len(reader.store())
    paths: set[str] = set()
    chunks = 0
    for chunk in reader.stream():
        paths.add(chunk.entity_path.lstrip("/").replace("\\", ""))
        chunks += 1
    required = (
        "debug/scoped_authority",
        "world/scoped_authority/union/",
        "world/source_observation_cameras/",
        "world/source_projected/",
        "cameras/",
    )
    if (
        recording_count != 1
        or store_count <= 0
        or chunks <= 0
        or any(not any(value.startswith(prefix) for value in paths) for prefix in required)
        or any("ground_truth" in value.lower() for value in paths)
    ):
        raise ValueError("scoped recording reader rejected missing source layers or primary GT")
    return {
        "recording_count": recording_count,
        "store_count": store_count,
        "chunk_count": chunks,
        "required_source_layers_verified": True,
        "primary_gt_entities_absent": True,
        "rrd_reader_verified": True,
    }


def write_scoped_demo(
    records: Sequence[ScopedDemoRecord],
    provider: ScopedUnionPhysicalProvider,
    output: Path,
    *,
    case_id: str,
) -> dict[str, Any]:
    """Create exclusive RRD/PNG/JSON outputs after checking only supplied frozen models."""
    if output.exists():
        raise FileExistsError("scoped visualization output must be fresh")
    presentation = build_scoped_presentation(records, provider, case_id=case_id)
    output.mkdir(parents=True)
    recording = output / "scoped.rrd"
    preview = output / "preview.png"
    _write_recording(presentation, recording, records)
    reader = verify_scoped_recording(recording)
    _write_preview(presentation, preview)
    presentation["rrd_reader_verified"] = True
    presentation["reader"] = reader
    presentation["artifacts"] = {
        "recording": {
            "filename": recording.name,
            "sha256": hashlib.sha256(recording.read_bytes()).hexdigest(),
        },
        "preview": {
            "filename": preview.name,
            "sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
        },
    }
    (output / "presentation.json").write_text(
        json.dumps(presentation, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )
    return {
        "case_id": case_id,
        "status": "SCOPED_SOURCE_BOUND_VISUALIZATION",
        "rrd_reader_verified": True,
        "ground_truth_logged_to_primary_recording": False,
        "recording": str(recording),
        "preview": str(preview),
        "presentation": str(output / "presentation.json"),
        "reader": reader,
    }
